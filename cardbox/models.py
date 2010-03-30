### Imports ###

# Python Imports
import re
import datetime
import time
import yaml
import random
import logging
import base64

# AppEngine Imports
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext.db import Key

# Django Imports
import django.template as django_templates
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.utils import simplejson

# Library Imports
import tools.diff_match_patch as dmp
import tools.textile as textile

# Local Imports

### Abstract Models ###
    
class Page(db.Model):
    content = db.TextProperty(default='')
    modified = db.DateTimeProperty(auto_now=True)
    editor = db.UserProperty(auto_current_user=True)
    revision_number = db.IntegerProperty(default=1)
    
    @classmethod
    def get_by_name(cls, name):
        """ Returns a page subclass with the given name, creates one if required.
        """
        if re.match("^factsheet:", name) and cls in [Factsheet, Page]:
            kind = Factsheet
        elif re.match("^template:", name) and cls in [Template, Page]:
            kind = Template
        elif re.match("^scheduler:", name) and cls in [Scheduler, Page]:
            kind = Scheduler
        else:
            return None
        page = kind.get_by_key_name(name)
        if page is None:
            page = kind(key_name=name)
        return page
    
    def __init__(self, is_revision=False, **kwds):
        self._edited = None
        self._errors = []
        self._validated = False
        self._parsed = None
        self._is_revision = is_revision
        db.Model.__init__(self, **kwds)
    
    def name(self, prefix=True):
        nm = self.key().name()
        if not prefix:
            nm = nm.split(':')[1]
        nm = nm.replace(':',':_')
        nm = ' '.join([w.capitalize() for w in nm.split('_')])
        return nm
        
    def edit(self, new_content):
        self._edited = new_content
        self._validate_main()
        if not self._errors:
            self._save()
            
    def parsed(self):
        if not self._validated:
            self._validate_main()
        return self._parsed if not self._errors else {}
    
    def html_preview(self):
        return None
        
    def source(self):
        return self._edited if self._edited is not None else self.content
        
    def errors(self):
        if not self._validated:
            self._validate_main()
        return self._errors
    
    def _validate_main(self):
        self._errors = []
        self._validated = True
        t = self._edited if self._edited is not None else self.content
        try:
            obj = yaml.safe_load(t)
            self._validate(obj)
        except yaml.parser.ParserError, e:
            self._errors.append({'message':'YAML syntax error.','content':e.problem_mark})
        except Exception, e:
            logging.exception(self._errors)
            self._errors.append({'message':'Error in %s format.'% self.__class__.__name__,
                                 'content':e.message}) #TODO: e.message is deprecated
    
    def _validate(self, parsed):
        self._parsed = parsed
    
    def _save(self):
        """ Modifies the content of page, creates rev if necessary. 
        """
        def txn(fs, nc, patch):
            r = Revision(parent=fs,
                         editor=fs.editor,
                         content=patch,
                         number=fs.revision_number)
            fs.content = nc
            fs.revision_number += 1
            r.put()
            fs.put()
            
        if self._is_revision:
            raise Exception("Cannot save revision.")
        if self.content != '' and self.content != self._edited:
            differ = dmp.diff_match_patch()
            patch = differ.patch_toText(differ.patch_make(self._edited, self.content))
            db.run_in_transaction(txn, self, self._edited, patch)
        else:
            self.content = self._edited
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

### Custom Properties ###

class PageProperty(db.Property):
    data_type = Page
    # TODO: Fix this caching
    def get_value_for_datastore(self, model_instance):
        page = super(PageProperty, self).get_value_for_datastore(model_instance)
        if isinstance(page, basestring):
            return page
        return page.key().name()
    
    def make_value_from_datastore(self, value):
        #if not hasattr(self, '_resolved'):
        #    self._resolved = Page.get_by_name(value)
        return Page.get_by_name(value)

class TimeDeltaProperty(db.Property):
    def get_value_for_datastore(self, model_instance):
        td = super(TimeDeltaProperty, self).get_value_for_datastore(model_instance)
        if td is not None:
            return td.microseconds + (td.seconds + td.days * 86400) * 1000000
        return None

    def make_value_from_datastore(self, value):
        if value is not None:
            return datetime.timedelta(microseconds=value)
 

### Models ###

class Account(db.Model):
    user_id = db.StringProperty(required=True)
    google_user = db.UserProperty(auto_current_user_add=True)
    created = db.DateTimeProperty(required=True, auto_now_add=True)
    modified = db.DateTimeProperty(required=True, auto_now=True)
    editor = db.UserProperty(required=True, auto_current_user=True)
    nickname = db.StringProperty(required=True)
    year_of_birth = db.IntegerProperty()

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
    
class Factsheet(Page):
    def _validate(self, yaml_obj):
        if yaml_obj is None:
            raise Exception('Factsheet is empty.')
        columns = yaml_obj['columns']
        rows = yaml_obj['rows']
        d = {}
        for i in rows:
            if isinstance(rows,dict):
                row_key, row = str(i), rows[i]
            else:
                row_key, row = uri_b64encode(i[0].encode('utf-8')), i
            if not re.match(r'^[A-Za-z0-9\.=\-_]+$',row_key):
                raise Exception("Error in row %s. Row names can only contain letters, numbers and . (period)" % row_key)
            if len(columns) != len(row):
                raise Exception("Row %s has wrong length." % row_key)
            d[row_key] = dict(zip(columns, row))
        self._parsed = {'rows':d,'columns':columns}
        
    def html_preview(self):
        if not self.errors():
            return render_to_string('factsheet.html',{'rows':self.rows()})
        else:
            return "No preview"
        
    def columns(self):
        return self.parsed().get('columns',[])
        
    def row_ids(self):
        return iter(self.parsed()['rows'])
        
    def rows(self):
        return self.parsed()['rows']


class Template(Page):
    
    DJANGO_VARIABLE_TAG = re.compile(r'{{([a-z0-9_]+)}}')
    DJANGO_CONTROL_TAG = re.compile(r'{%.+%}')
    
    def _validate(self, yaml_obj):
        front_template = yaml_obj['front']
        back_template = yaml_obj['back']
        if(self.DJANGO_CONTROL_TAG.search(front_template) or 
           self.DJANGO_CONTROL_TAG.search(back_template)):
           raise Exception('Control tags ( {% tag %} ) are not allowed.')
        background = yaml_obj.get('background', '#fff9cc')
        m = set(self.DJANGO_VARIABLE_TAG.findall(front_template)).union(
            set(self.DJANGO_VARIABLE_TAG.findall(back_template)))
        self._parsed = {'front':front_template,
                        'back' :back_template,
                        'background_color': background,
                        'variables' : m}
                        
    def variables(self):
        return self.parsed().get('variables',[])
    
    def html_preview(self):
        v = self.variables()
        row = dict(zip(v,v))
        return render_to_string('card.html',{'card':CardRenderer(row=row,template=self)})
        

class Scheduler(Page):
    def _validate(self, yaml_obj):
        self._parsed = compile(yaml_obj,'<string>','eval')
        
    def reschedule(self, card):
        def days(d):
            return datetime.timedelta(days=d)
        def minutes(m):
            return datetime.timedelta(minutes=m)
        gb = {'__builtins__':{}}
        lc = {'days':days,
              'minutes':minutes,
              'max':max,
              'min':min,
              'last_correct':card.last_correct,
              'last_studied':card.last_studied,
              'interval':card.interval}
        card.learned_until = eval(self.parsed(),gb,lc).replace(microsecond=0)

class Cardset(db.Model):
    title = db.StringProperty(default='New Cardset')
    owner = db.UserProperty(auto_current_user_add=True)
    created = db.DateTimeProperty(auto_now_add=True)
    public = db.BooleanProperty(default=True)
    factsheet = PageProperty()
    template = PageProperty(default='template:default')
    mapping = db.TextProperty(default='')
    
    def render_card(self, card_id):
        return CardRenderer(template=self.template,
                            factsheet=self.factsheet,
                            card_id=card_id,
                            mapping=self.mapping)
       
    
    def random_card(self):
        """ Renders a random card from connected factsheet. Renders a 'None'
            card if factsheet not found or is empty.
        """
        if self.factsheet is not None:
            ids = list(self.factsheet.row_ids())
            if len(ids) > 0:
                return self.render_card(random.choice(ids))
        return self.render_card(None)
        
    def all_ids(self):
        a = []
        if self.factsheet is not None and not self.factsheet.errors():
            k = self.key().id()
            a = [(k, c_id) for c_id in self.factsheet.row_ids()]
        return a
        
    def mapping_as_json(self):
        return simplejson.dumps(yaml.load(self.mapping))

class Box(db.Model):
    title = db.StringProperty(default='New Box')
    owner = db.UserProperty(auto_current_user_add=True)
    modified = db.DateTimeProperty(auto_now=True)
    cardsets = db.ListProperty(int)
    scheduler = PageProperty(default='scheduler:default')
    selector = db.TextProperty()
    last_studied = db.DateTimeProperty(default=datetime.datetime(2010,1,1))
    time_studied = TimeDeltaProperty(default=datetime.timedelta(0))
    
    def put(self, *args, **kwds):
        db.Model.put(self, *args, **kwds)
        self._update_cards()
        
    def get_cardsets(self):
        items = zip(self.cardsets, Cardset.get_by_id(self.cardsets))
        return dict([(k,v) for (k,v) in items if v is not None])
        
    def _update_cards(self):
        from engine import update_cards
        update_cards(self.all_card_ids(), self.key())
    
    def update_time_studied(self):
        now = datetime.datetime.now()
        diff = (now - self.last_studied)
        if diff.seconds < 300:
            self.time_studied += diff
        self.last_studied = now
        self.put()
        
    def percentage_learned(self):
        n_cards = len(list(self.all_card_ids()))
        if n_cards == 0:
            return 0.0;
        available = Card.all(keys_only=True).ancestor(self)
        available.order('learned_until')
        available.filter('learned_until <', datetime.datetime.now())
        available.filter('enabled',True)
        n_available = available.count()
        return (1-(n_available/float(n_cards)))*100.0
        
    def card_to_study(self):
        study_set_size = 10
        study_set = Card.all().ancestor(self)
        study_set.filter('in_study_set',True)
        study_set.filter('enabled',True)
        study_set = list(study_set.fetch(study_set_size))
        if len(study_set) < study_set_size/2:
            available = Card.all().ancestor(self)
            available.filter('enabled',True)
            available.filter('learned_until <', datetime.datetime.now())
            available = filter(lambda x: not x.in_study_set, list(available.fetch(100)))
            refill = random.sample(available,min(len(available),study_set_size))
            for c in refill:
                c.in_study_set = True
                c.put()
            study_set.extend(refill)
        #Return first available card.
        if len(study_set) == 0:
            return Card.all().ancestor(self).order('learned_until').filter('enabled',True).get()
        study_set.sort(key=lambda x: x.last_studied)
        next_card = random.choice(study_set[:len(study_set)//2+1])
        next_card.studied()
        return next_card
    
    def all_card_ids(self):
        a = []
        for cardset in self.get_cardsets().values():
            a.extend(cardset.all_ids())
        return a
    
    def render_card(self, id_tuple):
        set_id, card_id = id_tuple
        set_id = int(set_id)
        if set_id in self.get_cardsets():
            cardset = self.get_cardsets()[set_id]
            return cardset.render_card(card_id)
    

                    
class Card(db.Model):
    cardset = db.ReferenceProperty(Cardset)
    modified = db.DateTimeProperty(auto_now=True)
    enabled = db.BooleanProperty(default=True)
    in_study_set = db.BooleanProperty(default=False)
    last_correct = db.DateTimeProperty(default=datetime.datetime(2010,1,2))
    last_studied = db.DateTimeProperty(default=datetime.datetime(2010,1,1))
    learned_until = db.DateTimeProperty(default=datetime.datetime(2010,1,2))
    interval = db.IntegerProperty(default=1)
    n_correct = db.IntegerProperty(default=0)
    n_wrong = db.IntegerProperty(default=0)
    history = db.TextProperty(default='')
    
    def answered(self, correct=False):
        """ Update the card with correct/wrong stats."""
        def txn():
            if correct:
                self.last_correct = now
                self.n_correct += 1
                self.interval += 1
                self.in_study_set = False
            else:
                self.n_wrong += 1
                self.interval -= 1
            self.last_studied = now
            self.interval = min(12,max(1, self.interval))
            scheduler.reschedule(self)
            log_line = yaml.dump([[now,
                                   int(self.n_correct), 
                                   int(self.n_wrong), 
                                   int(self.interval),
                                   self.learned_until]])
            self.history += log_line
            self.put()
        
        box = self.parent()
        scheduler = box.scheduler
        now = datetime.datetime.now().replace(microsecond=0)
        db.run_in_transaction(txn)
        box.update_time_studied()
        
    def studied(self):
        self.last_studied = datetime.datetime.now().replace(microsecond=0)
        self.put()
        
    def get_cardset(self):
        if not self.cardset:
            self.cardset = Cardset.get_by_id(int(self.key().name().split('-',1)[0]))
        return self.cardset
        
    def is_learned(self):
        return self.learned_until > datetime.datetime.now()
        
    def stats(self, start_at=None, end_at=None):
        RANGE = 100.0
        timestamps = []
        labels = []
        intervals = []
        learned_until = []
        last_date = datetime.datetime(2010,1,1)
        for line in self.history.split('\n'):
            obj = yaml.load(line)
            if obj:
                obj = obj[0]
                timestamps.append(time.mktime(obj[0].timetuple()))
                if obj[0] - last_date > datetime.timedelta(days=3):
                    labels.append(obj[0].strftime('%b %d'))
                    last_date = obj[0]
                else:
                    labels.append('')
                intervals.append(obj[3])
                learned_until.append(time.mktime(obj[4].timetuple()))
        if len(timestamps) < 2:
            return {'timestamps':[],'labels':[],'intervals':[],'learned_ranges':[]}
        first = min(timestamps)
        span = max(timestamps)-first
        timestamps = map(lambda x: ((x-first)/float(span)) * RANGE,timestamps)
        learned_from = map(lambda x: x/RANGE,timestamps)
        learned_until = map(lambda x: ((x-first)/float(span)),learned_until)
        learned = zip(timestamps, learned_until)
        return {'timestamps':timestamps,
                'labels':labels,
                'intervals':intervals,
                'learned_ranges':['%s,%s'%s for s in zip(learned_from,learned_until)]}
        
    def rendered(self):
        if not hasattr(self, '_rendered'):
            self._rendered = self.parent().render_card(self.key().name().split('-',1))
        return self._rendered


### Non-model Classes ###

class CardRenderer():
    
    def __init__(self,template, row=None, factsheet=None, card_id=None, mapping='',safe_mode=True):
        self.template = template
        self.row = row
        self.factsheet = factsheet
        self.card_id = card_id
        self.mapping = mapping
        self.safe_mode = safe_mode
    
    def rendered(self):        
        if not hasattr(self, '_rendered'):
            self._rendered = self._render()        
        return self._rendered
    
    def front(self):
        return self.rendered()['front']
    
    def back(self):
        return self.rendered()['back']
        
    def background_color(self):
        return self.rendered()['background_color']
    
    def _render(self):
        #Errors first
        if self.template is None:
            return self._error_card("Template not found or empty.")
        if self.template.errors():
            return self._error_card("Template contains errors.")
        if self.row is None:
            if self.factsheet is None:
                return self._error_card("Factsheet not found or empty.")
            if self.factsheet.errors():
                return self._error_card("Factsheet contains errors.")
            if self.card_id is None or self.card_id not in self.factsheet.rows():
                return self._error_card("Card not found in factsheet.")
            self.row = self.factsheet.rows()[self.card_id]
        #Actual rendering
        base = dict([(v,mark_safe('&#160;')) for v in self.template.variables()])
        base.update(self.row)        
        mapping = yaml.load(self.mapping)
        if mapping is not None and mapping != 'None' and mapping != '':
            base.update([(newkey, base[oldkey]) for newkey, oldkey in mapping.items() if oldkey not in [None,'None']])
        #Wrap all fields in a span with their ID
        for k in base.keys():
            base[k] = mark_safe('<span class="tfield" id="tfield_%s">%s</span>'%(k,encode_html(base[k])))
        front = django_templates.Template(
            self.template.parsed()['front']).render(django_templates.Context(base))
        back = django_templates.Template(
            self.template.parsed()['back']).render(django_templates.Context(base))
        front = mark_safe(textile.textile(front))
        back = mark_safe(textile.textile(back))
        return {'front':front, 
                'back':back, 
                'background_color':self.template.parsed()['background_color']}
                
    def _error_card(self, error):
        logging.info('errorcard')
        return {'front':error, 'back':error, 'background_color':'#fba6aa'}
        

### Helper Functions ###



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
    
### Mappers ###

