### Imports ###

# Python Imports
import datetime
import logging

# AppEngine Imports
from google.appengine.dist import use_library
use_library('django', '1.0')
from google.appengine.ext import deferred
from google.appengine.runtime import DeadlineExceededError
from google.appengine.ext import db

# Django Imports
from django.template import Template

# Local Imports
import models


### Mapper class ###

class Mapper(object):
    """ Mapper class for iterating through all entities of a model.
        Copied from: 
            http://code.google.com/appengine/articles/deferred.html
        Improved by: 
            http://www.arikfr.com/blog/app-engine-mapping-entities-using-deferred-tasks.html
    """
    # Subclasses should replace this with a model class (eg, model.Person).
    KIND = None
    # Subclasses can replace this with the property the entities should be ordered by.
    ORDER_BY = '__key__'
    # Subclasses can replace this with a list of (property, value) tuples to filter by.
    FILTERS = []
    # Set this only keys have to be returned
    KEYS_ONLY = False

    def __init__(self, next_mapper=None, ancestor=None):
        self.to_put = []
        self.to_put_dict = {}
        self.to_delete = []
        self.next_mapper = next_mapper
        self.ancestor = ancestor

    def map(self, entity):
        """Updates a single entity.

        Implementers should return a tuple containing two iterables (to_update, to_delete).
        """
        return ([], [])

    def finish(self):
        """Called when the mapper has finished, to allow for any final work to be done."""
        logging.info(str(self) + ' Mapper finished.')
        if self.next_mapper is not None:
            logging.info(str(self) + ' Next: ' + str(self.next_mapper))
            self.next_mapper.run()
        pass

    def get_query(self):
        """Returns a query over the specified kind, with any appropriate filters applied."""
        q = self.KIND.all(keys_only=self.KEYS_ONLY)
        for prop, value in self.FILTERS:
            q.filter("%s =" % prop, value)
        if self.ancestor:
            q.ancestor(self.ancestor)
        q.order(self.ORDER_BY)
        return q

    def run(self, batch_size=20):
        """Starts the mapper running."""
        logging.info('%s: Starting.'% (self.__class__.__name__))
        deferred.defer(self._continue, None, batch_size)

    def _batch_write(self):
        """Writes updates and deletes entities in a batch."""
        if self.to_put:
            db.put(self.to_put)
            self.to_put = []
        if self.to_put_dict:
            db.put(self.to_put_dict.values())
            self.to_put_dict = {}
        if self.to_delete:
            db.delete(self.to_delete)
            self.to_delete = []

    def _continue(self, start_key, batch_size):
        q = self.get_query()

        # If we're resuming, pick up where we left off last time.
        if start_key:
            q.filter("%s >" % self.ORDER_BY, start_key)

        # Keep updating records until we run out of time.
        continue_key = None
        try:
            # Steps over the results, returning each entity and its index.
            res = q.fetch(batch_size)
            for i, entity in enumerate(res):
                map_updates, map_deletes = self.map(entity)
                self.to_put.extend(map_updates)
                self.to_delete.extend(map_deletes)
                
                if self.KEYS_ONLY:
                    continue_key = entity
                else:
                    if self.ORDER_BY == '__key__':
                        continue_key = entity.key()
                    else:
                        continue_key = getattr(entity, self.ORDER_BY)

            self._batch_write()
        except DeadlineExceededError:
            logging.info('%s: hit DeadlineExceededError' % (self.__class__.__name__))
            # Write any unfinished updates to the datastore.
            self._batch_write()
            # Queue a new task to pick up where we left off.
            deferred.defer(self._continue, continue_key, batch_size)
            return

        if continue_key is not None:
            logging.info('%s: batch of %d finished, enqueing.' % (self.__class__.__name__,
                                                                 batch_size))
            deferred.defer(self._continue, continue_key, batch_size)
        else:
            self.finish()
            
### Cleaner Mapper ###

def update_cards(card_ids, box):
    c = CardCleaner(card_ids=card_ids,ancestor=box)
    c.run()
    

class CardCleaner(Mapper):
    """ Runs through all the cards in a given box (ancestor),
        and checks whether the card is still part of that box.
        At the end, the remaining cards that should be in the box but are not
        will be added by calling create_cards()
    """
    KIND = models.Card
    
    def __init__(self, card_ids=None, **kwds):
        self.card_ids = card_ids
        Mapper.__init__(self, **kwds)
    
    def map(self, card):
        box = card.parent()
        if box is None:
            return ([],[card])
        a,b = card.key().name().split('-',1)
        id_tuple = (int(a),b)
        if (id_tuple[0] not in box.cardsets) or (id_tuple not in self.card_ids):
            if card.history == '':
                return ([],[card])
            else: 
                if (card.modified - datetime.datetime.now()).days > 30:
                    return ([],[card])
                card.enabled = False
                return ([card],[])
        else:
            try:
                self.card_ids.remove(id_tuple)
            except ValueError:
                logging.warning('CardCleaner %s was not found in %s'%(id_tuple,self.card_ids))
            return ([],[])
                
    def finish(self):
        if self.card_ids:
            logging.info("CardCleaner finished. Creating %d cards."%len(self.card_ids))
            create_cards(self.card_ids, self.ancestor)
        else:
            logging.info("CardCleaner finished. No cards to add.")
                
def create_cards(card_ids, box_key):
    """ Adds Card entities for the given ids, with the given parent.
        Adds in batches and re-queues itself. 
    """
    if len(card_ids) == 0:
        return
    BATCH_SIZE = 20
    batch = card_ids[:BATCH_SIZE]
    logging.info("Adding cards for %s (%d remaining). Batch: %s"%(box_key,len(card_ids),batch))
    for id_tuple in batch:
        key = '-'.join([str(p) for p in id_tuple])
        card = models.Card.get_by_key_name(key, parent=box_key)
        if card is None:
            logging.info("Creating card for %s"%(str(id_tuple)))
            card = models.Card(key_name=key, parent=box_key)
        card.enabled = True
        card.put()
    deferred.defer(create_cards,
                   card_ids[BATCH_SIZE:],
                   box_key)
   