### Imports ###

# Python Imports
import os
import re
import datetime
import time
import yaml
import random
import logging
import base64
import math
import csv

# AppEngine Imports
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext.db import Key
from google.appengine.ext.db import BadValueError, KindError

# Django Imports
import django.template as django_template
from django.template import Context, TemplateDoesNotExist
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string, get_template
from django.utils import simplejson
from django.core.urlresolvers import reverse

# Library Imports
import tools.diff_match_patch as dmp

# Local Imports
import draw

### Constants ###
NUM_INTERVALS = 12

EMPTY_FIELD            = mark_safe('&#160;&#160;')
RE_DJANGO_VARIABLE_TAG = re.compile(r'{{([a-z0-9_]+)}}')
RE_CARD_FRONT          = re.compile('<!--FRONT-->(.*?)<!--/FRONT-->',re.S)
RE_CARD_BACK           = re.compile('<!--BACK-->(.*?)<!--/BACK-->',re.S)

RESERVED_TITLES      = ['create','tags','list','edit','view','cardset','cardbox','stats'] 
VALID_CARDSET_TITLE  = r'^[a-z][\- a-z0-9]{4,49}$'
VALID_FACTSHEET_NAME = r'^[a-z][\_a-z0-9]{4,49}$'

### Exceptions ###
class FactsheetError(Exception):
    pass

class CardsetError(Exception):
    pass


### Abstract Models ###

class Page(db.Model):
    pass

class TimeDeltaProperty(db.Property):
    def get_value_for_datastore(self, model_instance):
        td = super(TimeDeltaProperty, self).get_value_for_datastore(model_instance)
        if td is not None:
            return (td.seconds + td.days * 86400)
        return None

    def make_value_from_datastore(self, value):
        if value is not None:
            return datetime.timedelta(seconds=value)


### Models ###

class Account(db.Model):
    user_id       = db.StringProperty(required=True)
    google_user   = db.UserProperty(auto_current_user_add=True)
    created       = db.DateTimeProperty(required=True, auto_now_add=True)
    modified      = db.DateTimeProperty(required=True, auto_now=True)
    editor        = db.UserProperty(required=True, auto_current_user=True)
    nickname      = db.StringProperty(required=True)
    year_of_birth = db.IntegerProperty()
    has_studied   = db.BooleanProperty(default=False)
    
    # Current user's Account.  Updated by middleware.AddUserToRequestMiddleware.
    current_user_account = None
    
    def my_boxes(self):
        boxes = Box.all().filter('owner',self.google_user)
        return boxes


class Revision(db.Model):
    content = db.TextProperty()
    editor = db.UserProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)
    number = db.IntegerProperty(required=True)
    
class Factsheet(db.Model):
    content         = db.TextProperty(default='')
    name            = db.StringProperty()
    modified        = db.DateTimeProperty(auto_now=True)
    editor          = db.UserProperty(auto_current_user=True)
    revision_number = db.IntegerProperty(default=1)
    
    meta_subject = db.StringProperty() # TODO: REMOVE FROM DATASTORE
    meta_book    = db.StringProperty() # TODO: REMOVE FROM DATASTORE
    
    @classmethod
    def get_by_name(cls, name):
        """ Returns a factsheet with the given name.
        """
        factsheet = Factsheet.all().filter('name =',name).get()
        if factsheet is None:
            raise Exception('Page "%s" not found'%name)
        return factsheet
        
    def __init__(self, is_revision=False, **kwds):
        db.Model.__init__(self, **kwds)
        self._parsed      = None
        self._is_revision = is_revision
        self.new_content  = None
    
    @property
    def url(self):
        """ Returns the view-url for this page. 
        """
        return reverse('cardbox.views.list_view',kwargs={'name':self.name})
        
    def title(self):
        return name_to_title(self.name) if self.name != '' else ''
        
    
    def set_title(self, new_title):
        name       = title_to_name(new_title)
        if not re.match(VALID_FACTSHEET_NAME, name):
            raise FactsheetError("""Title (%s / %s) can only contain letters, numbers, and spaces.
                                    It has to start with a letter, and it has to be between 5 and 
                                    50 letters long. Additionally, it cannot start with: %s.
                                 """%(new_title,name,", ".join(RESERVED_TITLES)))
        if self.name != name:
            other = Factsheet.all().filter('name', name).get()
            if other:
                raise FactsheetError(mark_safe("There is already a page with this title. ( <a href='%s'>%s</a> )"
                    %(other.url, name_to_title(other.name))))
        self.name = name
        
    def set_columns_and_rows(self, columns, rows):
        self.parse(columns, rows)
        self.new_content = yaml.safe_dump({'columns':columns, 'rows':rows})
        
    def parse(self, columns=[], rows=[]):
        row_dict  = {}
        row_order = []
        if isinstance(rows, dict):
            rows = rows.values()
        for row in rows:
            if not isinstance(row[0],basestring):
                raise FactsheetError("Incorrect format in [%s]"%u','.join([unicode(b) for b in i]))
            row_key = uri_b64encode(row[0].encode('utf-8'))
            if len(columns) != len(row):
                raise FactsheetError("Row %s (%s) has wrong length." % (row_key,u','.join([unicode(b) for b in row])))
            if row_key in row_dict:
                raise FactsheetError("Row %s (%s) has same first word as (%s)." % (row_key,
                    u','.join([unicode(b) for b in row]), 
                    u','.join(row_dict[row_key].values())))
            row_order.append(row_key)
            row_dict[row_key] = dict(zip(columns, row))
        self._parsed = {'rows':row_dict,'order':row_order,'columns':columns}
    
    def parsed(self):
        if not self._parsed:
            if self.content == '':
                self.parse()
            else:
                yaml_obj = yaml.safe_load(self.content)
                self.parse(yaml_obj['columns'], yaml_obj['rows'])
        return self._parsed
    
    def save(self):
        """ Modifies the content of page, creates rev if necessary. 
        """
        def txn(factsheet, new_content, patch):
            r = Revision(parent=factsheet,
                         editor=factsheet.editor,
                         content=patch,
                         number=factsheet.revision_number)
            factsheet.content = new_content
            factsheet.revision_number += 1
            r.put()
            factsheet.put()
        
        if self._is_revision:
            raise Exception("Cannot save revision.")
        if self.content != '' and self.content != self.new_content:
            differ = dmp.diff_match_patch()
            patch = differ.patch_toText(differ.patch_make(self.new_content, self.content))
            db.run_in_transaction(txn, self, self.new_content, patch)
            logging.info("Created new revision (%d) for factsheet %s"%(self.revision_number,self.name))
        else:
            self.content = self.new_content
            self.put()

    def revision(self, number):
        """ Returns a given revision
        """
        if self._is_revision:
            raise Exception("Cannot get revision of revision.")
        differ = dmp.diff_match_patch()
        history = Revision.all().ancestor(self)
        history.filter('number >=',number).order('-number')
        revised_content = self.content
        for r in history:
            patch = differ.patch_fromText(unicode(r.content))
            revised_content = differ.patch_apply(patch, revised_content)[0]
            earliest = r
        revised_page = self.__class__(key_name=self.key().name(),
                                      content=revised_content,
                                      editor=earliest.editor,
                                      modified=earliest.created,
                                      number=earliest.number,
                                      is_revision=True)
        return revised_page
        
    def row_order(self):
        return self.parsed().get('order',[])
    
    def columns(self):
        return self.parsed().get('columns',[])
        
    def row_ids(self):
        return self.parsed()['rows'].keys()
        
    def rows(self):
        return self.parsed()['rows']

class Template(Page):
    pass

class Scheduler(Page):
    pass

class Cardset(db.Model):

    title         = db.StringProperty(default='New Cardset')
    owner         = db.UserProperty(auto_current_user_add=True)
    created       = db.DateTimeProperty(auto_now_add=True)
    modified      = db.DateTimeProperty(auto_now=True)
    public        = db.BooleanProperty(default=True)
    factsheet     = db.ReferenceProperty(Factsheet)
    template      = db.ReferenceProperty(Template) #TODO: REMOVE FROM DATASTORE
    template_name = db.StringProperty(default='default')
    mapping       = db.TextProperty(default='')
        
    def sample(self):
        """ Renders a random card from connected factsheet. Renders a 'None'
            card if factsheet not found or is empty.
        """
        if self.factsheet is not None:
            ids = self.factsheet.row_ids()
            if ids:
                row           = self.factsheet.rows()[random.choice(ids)]
                template_name = self.get_template_name()
                mapping       = yaml.load(self.mapping)
                return CardTemplate(template_name, mapping).render(row)
                
    def get_template_name(self):
        if self.template:
            self.template_name = self.template.key().name().split(':')[1]
            self.template = None
            self.put()
        return self.template_name
    
    def contents(self):
        o = []
        renderer = CardTemplate(self.get_template_name(), yaml.load(self.mapping))
        for row in self.factsheet.rows().values():
            renderer.set_content(row)
            o.append({'front':renderer.front_data, 'back':renderer.back_data})
        return o
        
    def set_title(self, title):
        reserved = [title.lower().startswith(r) for r in RESERVED_TITLES]
        if any(reserved) or not re.match(VALID_CARDSET_TITLE, title.lower()):
            raise CardsetError("""Title (%s) must start with a letter. It can contain 
                                  only letters, numbers, spaces, and dashes. Additionally,
                                  it cannot start with any of the words: %s."""%(title,', '.join(RESERVED_TITLES)))
        self.title = title
        
    def set_template(self, template):
        if (template+'.html') not in os.listdir('templates/cards/'):
            raise CardsetError("Template (%s) not found."%template)
        self.template_name = template
        
    def set_mapping(self, mapping):
        t = CardTemplate(self.get_template_name(), mapping)
        mapping = dict((f,v) for (f,v) in mapping.items() if (f in t.fields and v != 'None'))
        for v in mapping.values():
            if v != '' and v not in self.factsheet.columns():
                raise CardsetError('Mapping contains non-existent column name "%s".'%v)
        self.mapping = yaml.safe_dump(mapping)
        
    def get_mapping(self):
        return yaml.load(self.mapping)
                
    def mapping_json(self):
        return simplejson.dumps(yaml.load(self.mapping))
        
    def all_ids(self):
        if self.factsheet is not None:
            k = self.key().id()
            return [(k, c_id) for c_id in self.factsheet.row_ids()]
        else:
            return []

class Box(db.Model):
    study_set_size = 10
    
    title        = db.StringProperty(default='New Box')
    owner        = db.UserProperty(auto_current_user_add=True)
    modified     = db.DateTimeProperty(auto_now=True)
    cardsets     = db.ListProperty(int)
    scheduler    = db.ReferenceProperty(Scheduler) # TODO: REMOVE FROM DATASTORE
    last_studied = db.DateTimeProperty(default=datetime.datetime(2010,1,1))
    time_studied = TimeDeltaProperty(default=datetime.timedelta(0))
    
    def update_cards(self):
        from engine import update_cards
        update_cards(self.all_card_ids(), self.key())
    
    def update_time_studied(self):
        now = datetime.datetime.now()
        diff = (now - self.last_studied)
        if diff.seconds < 300:
            self.time_studied += diff
        self.last_studied = now
        self.put()
        
    def fetch_cardsets(self):
        return Cardset.get_by_id(self.cardsets)
        
    def reschedule_card(self, card):
        """ Returns new date when card will be available """
        days         = lambda d: datetime.timedelta(days=d)
        minutes      = lambda m: datetime.timedelta(minutes=m)
        last_correct = card.last_correct
        last_studied = card.last_studied
        interval     = card.interval
        # Schedule
        learned_until = max(last_studied + minutes(1), last_correct + days((interval-1)*4))
        logging.info("Card (i: %d, lc: %s) rescheduled to %s"%(interval, last_correct, learned_until))
        return learned_until.replace(microsecond=0)
        
    def stats(self):
        if not hasattr(self, '_stats') or self._stats is None:
            n_cards = len(list(self.all_card_ids()))
            now = datetime.datetime.now()
            n_learned = Card.all().ancestor(self).filter('enabled',True).filter('learned_until >', now).count(n_cards)
            percentage = (n_learned/float(n_cards))*100.0 if n_cards > 0 else 0.0
            self._stats = {'percent_learned':percentage,'n_learned':n_learned,'n_cards':n_cards}
        return self._stats
        
    def interval_chart(self):
        if not hasattr(self, '_interval_chart') or self._stack_charts is None:
            latest_stats = DailyBoxStats.all().ancestor(self).order('-day').get()
            if latest_stats is None:
                intervals = [self.stats['n_cards']] + [0] * (NUM_INTERVALS-1)
            else:
                intervals = latest_stats.intervals
            scale = min(1,10.0/max(intervals))
            ch = []
            for i in range(len(intervals)):
                svg = draw.svg_cardstack(math.ceil(intervals[i]*scale),'cbx')
                ch.append({'num':intervals[i],'svg':mark_safe(svg)})
                logging.info(svg)
            self._interval_chart = ch
        return self._interval_chart
        
    def charts(self):
        if not hasattr(self, '_charts'):
            recent =  datetime.date.today() - datetime.timedelta(days=2)
            recentstats = DailyBoxStats.all().ancestor(self).filter('day >',recent)
            if recentstats.count(limit=1) < 1:
                from engine import create_box_stats
                create_box_stats(self, days_back=40)
            stats = DailyBoxStats.all().ancestor(self).order('day').fetch(limit=60)
            data = [(s.day, s.n_cards, s.n_learned, s.min_interval, s.max_interval, s.avg_interval) for s in stats]
            (dates, n_cards, n_learned, min_interval, max_interval, avg_interval) = (zip(*data) if len(data) > 0 else
                ([],[],[],[],[],[]))
            chart = TimelineChart(size='630x250')
            chart.add_line(dates, n_cards, label='Studied',color='7290A6')
            chart.add_line(dates, n_learned, label='Learned',color='94c15d')
            interval_chart = TimelineChart(size='630x250')
            interval_chart.add_line(dates, max_interval, label='Max Interval',color='CCC699')
            interval_chart.add_line(dates, avg_interval, label='Average Interval',color='000000')
            interval_chart.add_line(dates, min_interval, label='Min Interval',color='CCC699')
            interval_chart.add_line_fill('FFF9CC88',0,2)
            self._charts = {'n_cards':chart,'interval':interval_chart}
        return self._charts
        
    def is_empty(self):
        cards = Card.all().ancestor(self).filter('enabled',True).count(limit=1)
        return (cards <= 0)
        
    def study_set(self):
        study_set = Card.all().ancestor(self)
        study_set.filter('in_study_set',True)
        study_set.filter('enabled',True)
        return list(study_set.fetch(self.study_set_size))
        
    def card_to_study(self):
        study_set = self.study_set()
        # Add cards to the 'study set', a subset to focus on.
        if len(study_set) < self.study_set_size/2:
            available = Card.all().ancestor(self)
            available.filter('enabled',True)
            available.filter('learned_until <', datetime.datetime.now())
            available.filter('in_study_set', False)
            available = list(available.fetch(self.study_set_size * 10))
            logging.info("available cards: %d"%len(available))
            # available = filter(lambda x: not x.in_study_set, available)
            
            refill = random.sample(available,min(len(available),self.study_set_size))
            for c in refill:
                c.in_study_set = True
                c.put()
            study_set.extend(refill)
        #Return one of first available cards.
        if len(study_set) == 0:
            next_unlearned = Card.all().ancestor(self).order('learned_until').filter('enabled',True)
            return random.choice(next_unlearned.fetch(limit=20))
        study_set.sort(key=lambda x: x.last_studied)
        next_card = random.choice(study_set[:len(study_set)//2+1])
        next_card.studied()
        return next_card
    
    def all_card_ids(self):
        output = []
        cardsets = Cardset.get_by_id(self.cardsets)
        for c in cardsets:
            output.extend(c.all_ids())
        return output

                    
class Card(db.Model):
    modified      = db.DateTimeProperty(auto_now=True)
    enabled       = db.BooleanProperty(default=True)
    in_study_set  = db.BooleanProperty(default=False)
    last_correct  = db.DateTimeProperty(default=datetime.datetime(2010,1,2))
    last_studied  = db.DateTimeProperty(default=datetime.datetime(2010,1,1))
    learned_until = db.DateTimeProperty(default=datetime.datetime(2010,1,2))
    interval      = db.IntegerProperty(default=1)
    n_correct     = db.IntegerProperty(default=0)
    n_wrong       = db.IntegerProperty(default=0)
    history       = db.TextProperty(default='')
    
    def answered(self, correct=False):
        """ Update the card with correct/wrong stats."""
        now = datetime.datetime.now().replace(microsecond=0)
        box = self.parent()
        self.last_studied = now
        if correct:
            self.last_correct = now
            self.n_correct += 1
            self.interval += 1
            self.in_study_set = False
        else:
            self.n_wrong += 1
            self.interval -= 1
        self.interval = min(NUM_INTERVALS,max(1, self.interval))
        self.learned_until =  box.reschedule_card(self)
        log_line = yaml.dump([[now,
                               int(self.n_correct), 
                               int(self.n_wrong), 
                               int(self.interval),
                               self.learned_until]])
        self.history += log_line
        self.put()
        box.update_time_studied()
        
    def studied(self):
        self.last_studied = datetime.datetime.now().replace(microsecond=0)
        self.put()
        
    def get_cardset(self):
        if not hasattr(self, '_cardset'):
            self._cardset = Cardset.get_by_id(int(self.key().name().split('-',1)[0]))
        return self._cardset
        
    def is_learned(self):
        return self.learned_until > datetime.datetime.now()
        
    def state_at(self, date):
        dt = datetime.datetime.combine(date, datetime.time(0))
        last_state = {'learned':False,'studied':False,'interval':1}
        history = yaml.load(self.history)
        if history: 
            for entry in history:
                if dt > entry[0]:
                    last_state = {
                        'interval':entry[3],
                        'learned':dt < entry[4],
                        'studied':True
                    }
        return last_state
        
    def template(self):
        if not hasattr(self, '_template'):
            factsheet      = self.get_cardset().factsheet
            mapping        = self.get_cardset().get_mapping()
            template_name  = self.get_cardset().get_template_name()
            row_id         = self.key().name().split('-',1)[1]
            row            = factsheet.rows().get(row_id,None)
            self._template = CardTemplate()
            if factsheet is None:
                self._template.error = "List not found or empty."
                logging.error("Factsheet(%s) was not found from Card(%s)"%(self.get_cardset().title, self.key().name()))
                return self._template
            if row is None:
                self._template.error = "Card not found in list."
                logging.error("Row(%s) was not found in Factsheet(%s) from card(%s). "%(row_id, factsheet.name, self.key().name()))
                return self._template
            # Actual rendering
            self._template = CardTemplate(template_name, mapping)
            self._template.set_content(row)
        return self._template
        
    def render(self):
        return self.template().render()
    
    def render_mobile(self):
        return self.template().render(mode="mobile")
    
    def data(self):
         return {'front':self.template().front_data,'back':self.template().back_data}

class DailyBoxStats(db.Model):
    """ Keeps track of daily stats for parent box. """
    day          = db.DateProperty()
    n_learned    = db.IntegerProperty()
    n_cards      = db.IntegerProperty()
    intervals    = db.ListProperty(int,default=[0]*NUM_INTERVALS)
    avg_interval = db.FloatProperty(default=1.0)
    min_interval = db.IntegerProperty(default=1)
    max_interval = db.IntegerProperty(default=1)


### Non-model Classes ###

class CardTemplate(object):
    """ Contains methods for loading and rendering cardtemplates,
        and extracting variables
    """
    def __init__(self, template_name=None, mapping=None):
        self.mapping = {}
        self.front_vars = []
        self.back_vars = []
        if template_name is not None:
            self.load(template_name)
        if mapping is not None:
            self.set_mapping(mapping)

    def load(self,template_name):
        try:
            self.template_name   = template_name
            self.template_string = open('templates/cards/'+template_name+'.html').read()
            self.template        = django_template.Template(self.template_string)
            self.front_fields    = set(RE_DJANGO_VARIABLE_TAG.findall(RE_CARD_FRONT.findall(self.template_string)[0]))
            self.back_fields     = set(RE_DJANGO_VARIABLE_TAG.findall(RE_CARD_BACK.findall(self.template_string)[0]))
            self.fields          = self.front_fields | self.back_fields
            self.front_fields    = sorted(self.front_fields,key=lambda v: v[-1])
            self.back_fields     = sorted(self.back_fields,key=lambda v: v[-1])
            self.back_fields     = [f for f in self.back_fields if f not in self.front_fields]
            self.error           = False
        except IOError:
            self.error           = "Template not found."
            self.template_string = None

    def set_mapping(self,mapping):
        self.mapping    = mapping
        self.front_vars = [mapping[f] for f in self.front_fields if f in mapping]
        self.back_vars  = [mapping[f] for f in self.back_fields if f in mapping]
        self.back_vars  = [v for v in self.back_vars if v not in self.front_vars]
        
    def set_content(self, row):
        self.row = row
        self.front_data = [row[v] for v in self.front_vars if v in row]
        self.back_data  = [row[v] for v in self.back_vars if v in row]
        self.back_data  = [b for b in self.back_data if b not in self.front_data]
            
    def render(self,row=None,mode='normal'):
        if self.error:
            return self.render_error(self.error)
        if row:
            self.set_content(row)
        base = dict((v,EMPTY_FIELD) for v in self.fields)
        base.update(self.row) # This allows fields to be filled by their original name.
        # Update the values of the dict with the row's values.
        base.update(((field, self.row[var]) for (field, var) in self.mapping.items() if var in self.row))
        # Wrap all fields in a span with their ID
        for k in base.keys():
            base[k] = mark_safe('<span class="tfield tfield_%s" id="tfield_%s">%s</span>'%(k,k,encode_html(base[k])))
        # Apply the template
        base['render_mode'] = mode
        return self.template.render(Context(base))
        
    def render_fields(self):
        return self.render(dict(((f,f) for f in self.fields)))
        
    def render_icon(self):
        return self.render(dict(((f,f) for f in self.fields)),mode='icon')
        
    @classmethod
    def render_error(cls, message):
        return render_to_string('cards/error.html',{'message':message})
        
class TimelineChart(object):
    
    max_date_labels = 7
    
    def __init__(self, **kwds):
        self.gcparams = {}
        self.lines = []
        self.line_fills = []
        self.ranges = []
        self.size = kwds.get('size','470x200')
        self.times = set([])
    
    def add_line(self, times, data, label='', color='94c15d',thickness=3):
        if len(times) > 1:
            self.times = self.times.union(times)
            self.lines.append({'times':times,
                               'data':data,
                               'label':label,
                               'color':color,
                               'thickness':thickness})
    
    def add_line_fill(self, color, start_line, end_line):
        self.line_fills.append({'color':color,'start_line':start_line,'end_line':end_line})
        
    def add_range_markers(self, range_starts, range_ends):
        self.ranges.append({'starts':range_starts,'ends':range_ends})
        
    def rescale_all(self, rng=100):
        if len(self.times) > 1:
            times = sorted(self.times)
            first,last = times[0],times[-1]
            scaledtimes = rescale_datetimes(times, first, last, new_range_max=rng)
            for l in self.lines:
                l['scaled'] = rescale_datetimes(l['times'],first, last, new_range_max=rng)
            for r in self.ranges:
                r['scaled'] = zip(rescale_datetimes(r['starts'],first, last, new_range_max=1),
                                rescale_datetimes(r['ends'],first, last, new_range_max=1))
            self.labels = []
            self.labels.append((first, scaledtimes[0]))
            min_distance = (last-first)/self.max_date_labels
            for (t,s) in zip(times, scaledtimes):
                if t > self.labels[-1][0] + min_distance:
                    self.labels.append((t,s))

    def render(self):
        if len(self.times) < 2:
            self.empty_chart()
            return
        self.rescale_all()
        lines = [','.join(['%.1f'%t for t in l['scaled']]) + '|' + 
                 ','.join(['%.1f'%d for d in l['data']]) 
                    for l in self.lines]
        lines = '|'.join(lines)
        ranges = [['R,94c15d44,0,%s,%s'%(a,b) for (a,b) in r['scaled']] 
                    for r in self.ranges]
        ranges = '|'.join(ranges)
        linefills = '|'.join(['b,%s,%d,%d,0'%(lf['color'],
                                              lf['start_line'],
                                              lf['end_line']) for lf in self.line_fills])
        legend = '|'.join([l['label'] for l in self.lines])
        colors = ','.join([l['color'] for l in self.lines])
        linestyle = '|'.join([str(l['thickness']) for l in self.lines])
        labels = '|'.join([l[0].strftime("%b %d %%27%y") for l in self.labels])
        label_positions = ','.join(['%.1f'%l[1] for l in self.labels])
        max_val = max(0.1,max([max(l['data']) for l in self.lines]))
        ideal_spacing = (100/float(max_val)) * max(max_val//5.0,1)
        # Set parameters
        self.gcparams['cht']  = 'lxy'
        self.gcparams['chxt'] = 'x,y'
        self.gcparams['chds'] = ','.join([('0,100,0,%.0f'%(max_val)) for i in range(len(self.lines))])
        self.gcparams['chg']  = '0,%.1f'%ideal_spacing
        self.gcparams['chf']  = 'bg,s,65432100'
        # Dynamic parameters
        self.gcparams['chd']  = 't:'+lines
        self.gcparams['chco'] = colors
        self.gcparams['chls'] = linestyle
        self.gcparams['chm']  = ranges + ('|' if ranges and linefills else '') + linefills
        self.gcparams['chdl'] = legend
        self.gcparams['chxr'] = '1,0,%.2f'%max_val
        self.gcparams['chxl'] = '0:|'+labels
        self.gcparams['chxp'] = '0,'+label_positions
        
    def empty_chart(self):
        self.gcparams['chst'] = 'd_text_outline'
        self.gcparams['chld'] = '8A1F11|16|h|FFFFFF|b|Generating+data.+Come+back+in+a+minute.'

    def url(self):
        self.render()
        return ("http://chart.apis.google.com/chart?chs=%s&%s"%(self.size,
            '&'.join(['%s=%s'%(k,v) for (k,v) in self.gcparams.items()])))
            
    def img(self):
        return mark_safe("<img src='%s'/>"%self.url())

### Helper Functions ###

def title_to_name(title):
    SPACES = r'[ \_\-]+'
    return re.sub(SPACES,'_',title).lower()
    
def name_to_title(name):
    if name is None: 
        return ''
    nm = ' '.join([w.capitalize() for w in name.split('_')])
    return nm
    

def rescale_datetimes(dates, old_range_min=None, old_range_max=None, new_range_min=0, new_range_max=1):
    ascending = sorted(dates)
    if old_range_min is None: 
        old_range_min = ascending[0]
    if old_range_max is None:
        old_range_max = ascending[-1]
    omn = time.mktime(old_range_min.timetuple())
    omx = time.mktime(old_range_max.timetuple())
    nmn,nmx = new_range_min, new_range_max
    timestamps = map(lambda x: time.mktime(x.timetuple()), dates)
    scaled =  map(lambda x: ((x-omn)/float(omx-omn)) * (nmx-nmn) + nmn, timestamps)
    return scaled

### Generic Helper Functions

def encode_html(text):
    a = ((r'&(?!\#160;)', '&#38;'),
         ('<', '&#60;'),
         ('>', '&#62;'),
         ("'", '&#39;'),
         ('"', '&#34;'))
    for k, v in a:
        text = text.replace(k, v)
    return text

def uri_b64encode(s):
    return base64.urlsafe_b64encode(s).strip('=')

def uri_b64decode(s):
    return base64.urlsafe_b64decode(s + '=' * (4 - ((len(s) % 4) or 4)))
