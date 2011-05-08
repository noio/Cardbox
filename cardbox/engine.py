### Imports ###

# Python Imports
import datetime
import logging
import yaml


# AppEngine Imports
from google.appengine.dist import use_library
use_library('django', '1.2')
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
    # Set to run mapper in a specific queue
    QUEUE = 'default'

    def __init__(self, next_mapper=None, ancestor=None):
        self.to_put = []
        self.to_delete = []
        self.next_mapper = next_mapper
        self.ancestor = ancestor

    def map(self, entity):
        """ Updates a single entity.
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
        q = db.Query(self.KIND,keys_only=self.KEYS_ONLY)
        for prop, value in self.FILTERS:
            q.filter("%s =" % prop, value)
        if self.ancestor:
            q.ancestor(self.ancestor)
        q.order(self.ORDER_BY)
        return q

    def run(self, batch_size=20):
        """Starts the mapper running."""
        logging.info('%s: Starting.'% (self.__class__.__name__))
        deferred.defer(self._continue, None, batch_size, _queue=self.QUEUE)

    def _batch_write(self):
        """Writes updates and deletes entities in a batch."""
        if self.to_put:
            db.put(self.to_put)
            self.to_put = []
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
            deferred.defer(self._continue, continue_key, batch_size, _queue=self.QUEUE)
            return

        if continue_key is not None:
            logging.info('%s: batch of %d finished, enqueing.' % (self.__class__.__name__,
                                                                 batch_size))
            deferred.defer(self._continue, continue_key, batch_size, _queue=self.QUEUE)
        else:
            self.finish()
            
### Card Cleaner/Creator ###

def update_cards(card_ids, box):
    c = CardCleaner(card_ids=card_ids,ancestor=box)
    c.run()

def clean_all_cards():
    c = CardCleaner(card_ids=None, ancestor=None)
    c.run()

class CardCleaner(Mapper):
    """ Runs through all the cards in a given box (ancestor),
        and checks whether the card is still part of that box.
        At the end, the remaining cards that should be in the box but are not
        will be added by calling create_cards()
    """
    KIND = models.Card
    QUEUE = 'cardcleaner'
    
    def __init__(self, card_ids=None, **kwds):
        self.card_ids = card_ids
        Mapper.__init__(self, **kwds)
    
    def map(self, card):
        box = card.parent()
        if box is None:
            return ([],[card])
        if not self.ancestor:
            return ([],[])
        a,b = card.key().name().split('-',1)
        id_tuple = (int(a),b)
        if  id_tuple not in self.card_ids:
            if (card.modified - datetime.datetime.now()).days > 30:
                return ([],[card])
            elif card.enabled:
                card.enabled = False
                return ([card],[])
            else:
                return ([],[])
        else:
            card.enabled = True
            self.card_ids.remove(id_tuple)
            return ([card],[])
                
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
                   box_key, _queue='cardcleaner')
   
   
### Box Stats Creator ###

def create_box_stats(for_box, days_back=10):
    logging.info("Creating stats for box %s"%(str(for_box)))
    if isinstance(for_box, basestring):
        for_box = db.Key(for_box)
    for d in range(1, days_back + 1):
        td = datetime.timedelta(days=d)
        day = datetime.date.today() - td
        mapper = BoxStatsMapper(day, ancestor=for_box)
        deferred.defer(mapper.run, _countdown = 6 * (d-1))
        
class BoxStatsMapper(Mapper):
    
    KIND = models.Card
    FILTERS = [('enabled',True)]
    QUEUE = 'boxstats'
    
    def __init__(self, date, **kwds):
        self.date = date
        self.n_cards = 0
        self.n_learned = 0
        self.total_interval = 0
        self.min_interval = 1000
        self.max_interval = 0
        self.intervals = [0]*12
        #self.stats = str(stats.key())
        Mapper.__init__(self, **kwds)
        
    def map(self, card):
        state = card.state_at(self.date)
        iv = state['interval']
        self.intervals[iv-1] += 1
        self.min_interval = min(iv, self.min_interval)
        self.max_interval = max(iv, self.max_interval)
        if state['studied']:
            self.n_cards += 1
            self.total_interval += iv
            if state['learned']:
                self.n_learned += 1
        return ([],[])
    
    def finish(self):
        date_string = self.date.strftime('%d-%m-%Y')
        avg_interval = (self.total_interval / float(self.n_cards)) if self.n_cards > 0 else 0.0
        stats = models.DailyBoxStats(key_name=date_string, 
                                     parent=self.ancestor, 
                                     day=self.date,
                                     n_cards=self.n_cards,
                                     n_learned=self.n_learned,
                                     avg_interval=avg_interval,
                                     intervals=self.intervals,
                                     max_interval=self.max_interval,
                                     min_interval=self.min_interval)
        stats.put()
