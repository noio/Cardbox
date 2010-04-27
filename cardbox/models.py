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
from google.appengine.ext.db import BadValueError, KindError

# Django Imports
import django.template as django_templates
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.utils import simplejson
from django.core.urlresolvers import reverse


# Library Imports
import tools.diff_match_patch as dmp
import tools.textile as textile

# Local Imports


### Exceptions ###
class PageException(Exception):
    pass


### Abstract Models ###
    
class Page(db.Model):
    content = db.TextProperty(default='')
    name = db.StringProperty()
    modified = db.DateTimeProperty(auto_now=True)
    editor = db.UserProperty(auto_current_user=True)
    revision_number = db.IntegerProperty(default=1)
    
    meta_keys = {}
    
    @classmethod
    def get_by_name(cls, name):
        """ Returns a page subclass with the given name, creates one if required.
        """
        if cls == Page:
            raise Exception('Page is not a storable model.')
        else:
            page = cls.all().filter('name =',name).get()
        if page is None:
            raise Exception('Page "%s" not found'%name)
        return page
    
    def __init__(self, is_revision=False, **kwds):
        self._edited = None
        self._errors = []
        self._validated = False
        self._parsed = None
        self._is_revision = is_revision
        db.Model.__init__(self, **kwds)
        
    @property
    def title(self):
        """ Returns a formatted title for this page. 
        """
        nm = self.name if self.name else ''
        if(nm.split(':')[0] in ['factsheet','template','scheduler']):
            nm = nm.split(':')[-1]
        nm = nm.replace(':',':_')
        nm = ' '.join([w.capitalize() for w in nm.split('_')])
        return nm
        
    def get_name(self):
        if self.name is not None:
            return self.name
        else:            
            return self.key().name()
    
    @property
    def kind_name(self):
        return self.__class__.__name__.lower()
    
    @property
    def url(self):
        """ Returns the view-url for this page. 
        """
        return reverse('cardbox.views.page_view',kwargs={'kind':self.kind_name,'name':self.name})
        
    def edit(self, new_content, new_title=None):
        self._edited = new_content
        self._new_title = new_title if new_title is not None else self.key().name()
        self._validate_main()
        if not self._errors:
            self._save()
            
    def parsed(self):
        if not self._validated:
            self._validate_main()
        return self._parsed if not self._errors else {}
    
    def html_preview(self):
        return None
        
    def html_meta(self):
        s = []
        for key, attr_name in self.meta_keys.items():
            if getattr(self, attr_name):
                s.append('%s: %s' % (key, getattr(self, attr_name)))
        return ', '.join(s)
        
    def json(self):
        return simplejson.dumps({'name':self.name,
                                 'content':self.content
                                })
        
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
            meta = obj['meta'] if (obj and 'meta' in obj) else {}
            self._set_meta_data(meta)
        except yaml.parser.ParserError, e:
            self._errors.append({'message':'YAML syntax error.','content':e.problem_mark})
        except PageException, e:
            self._errors.append({'message':'Error in %s format.'% self.kind_name,
                                 'content':(e.args[0])})
            logging.info(self._errors)
                                 
        #Validate title
        if hasattr(self, '_new_title') and self._new_title is not None:
            try:
                self._validate_title(self._new_title)
            except PageException, e:
                self._errors.append({'message':'Error in title.',
                                     'content':(e.args[0])})
                logging.info(self._errors)
    
    def _validate_title(self, title):
        REMOVE = r'[ \_\-:;]+'
        VALID_TITLE = r'^[a-z]+(\_[a-z0-9]+)*$'
        if len(title) < 5:
            raise PageException("Title is too short.")
        name = re.sub(REMOVE,'_',title).lower()
        if self.name == name:
            return
        matched = re.match(VALID_TITLE, name)
        if not matched:
            raise PageException("Title (%s / %s) can only contain letters, numbers, and spaces."%(title,name))
        q = self.__class__.all()
        q.filter('name', name)
        if q.fetch(1):
            raise PageException("There is already a page with this title.")
        self.name = name
        return name
    
    def _validate(self, parsed):
        self._parsed = parsed
    
    def _save(self):
        """ Modifies the content of page, creates rev if necessary. 
        """
        def txn(page, new_content, patch):
            r = Revision(parent=page,
                         editor=page.editor,
                         content=patch,
                         number=page.revision_number)
            page.content = new_content
            page.revision_number += 1
            r.put()
            page.put()
        
        #Check title before saving
        if self.key().name() == 'none':
            raise Exception("Cannot save unnamed page.")
        if self._is_revision:
            raise Exception("Cannot save revision.")
        if self.content != '' and self.content != self._edited:
            differ = dmp.diff_match_patch()
            patch = differ.patch_toText(differ.patch_make(self._edited, self.content))
            db.run_in_transaction(txn, self, self._edited, patch)
        else:
            self.content = self._edited
            self.put()
    
    def _set_meta_data(self, meta):
        for key, attr_name in self.meta_keys.items():
            if key in meta and hasattr(self,attr_name):
                value = meta[key]
                if not re.match(r'^[a-zA-Z0-9 ]+$',value):
                    raise PageException("Meta value for '%s' can only contain letters, numbers and spaces."%m)
                value = re.sub(r' +',' ',value).lower()
                setattr(self, attr_name, value)
        if len(self.meta_keys.keys()):
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

    def __init__(self,
                 reference_class=None,
                 verbose_name=None,
                 **attrs):
      super(PageProperty, self).__init__(verbose_name, **attrs)
      
      if reference_class not in [Factsheet, Template, Scheduler]:
          raise KindError('reference_class must be a Page subclass.')
      self.reference_class = self.data_type = reference_class
   
    def __get__(self, model_instance, model_class):
        if model_instance is None:
            return self
        if hasattr(model_instance, self.__id_attr_name()):
            reference_id = getattr(model_instance, self.__id_attr_name())
        else:
            reference_id = None
        resolved = getattr(model_instance, self.__resolved_attr_name())
        if resolved is not None:
            return resolved
        else:
            instance = self.reference_class.get_by_name(reference_id)
            if instance is None:
                raise Error('PageProperty encountered invalid page name.')
            setattr(model_instance, self.__resolved_attr_name(), instance)
            return instance
   
    def __set__(self, model_instance, value):
        """Set reference."""
        value = self.validate(value)
        if value is not None:
            if isinstance(value, basestring):
                setattr(model_instance, self.__id_attr_name(), value)
                setattr(model_instance, self.__resolved_attr_name(), None)
            elif isinstance(value, db.Key):
                setattr(model_instance, self.__id_attr_name(), value)
                setattr(model_instance, self.__resolved_attr_name(), None)            
            else:
                setattr(model_instance, self.__id_attr_name(), value.key().name())
                setattr(model_instance, self.__resolved_attr_name(), value)
        else:
            setattr(model_instance, self.__id_attr_name(), None)
            setattr(model_instance, self.__resolved_attr_name(), None)
   
    def get_value_for_datastore(self, model_instance):
        """Get key of reference rather than reference itself."""
        return getattr(model_instance, self.__id_attr_name())
   
    def validate(self, value):
        return value
        if isinstance(value, basestring):
            return value
        if value is not None and not isinstance(value, db.Key) and not value.key():
            raise BadValueError(
            '%s instance must have a complete key before it can be stored as a '
            'reference' % self.reference_class.kind())
        value = super(PageProperty, self).validate(value)
        if value is not None and not isinstance(value, self.reference_class):
            raise KindError('Property %s must be an instance of %s' %
                          (self.name, self.reference_class.kind()))
        return value
   
    def __id_attr_name(self):
        return self._attr_name()
   
    def __resolved_attr_name(self):
        return '_RESOLVED' + self._attr_name()


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
    
    has_studied = db.BooleanProperty(default=False)
    
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
    kind_name = 'list'
    meta_keys = {'subject':'meta_subject',
                 'book':'meta_book'}
    meta_subject = db.StringProperty()
    meta_book = db.StringProperty()
    
    def _validate(self, yaml_obj):
        if yaml_obj is None:
            raise PageException('The list is empty.')
        columns = yaml_obj['columns']
        rows = yaml_obj['rows']
        d = {}
        row_order =[]
        for index,i in enumerate(rows):
            if isinstance(rows,dict):
                row_key, row = str(i), rows[i]
            else:
                if not isinstance(i[0],basestring):
                    raise PageException("Incorrect format in [%s]"%u','.join([unicode(b) for b in i]))
                row_key, row = uri_b64encode(i[0].encode('utf-8')), i
            if not re.match(r'^[A-Za-z0-9\.=\-_]+$',row_key):
                raise PageException("Error in row %s (%s). Row names can only contain letters, numbers and . (period)" % (row_key,u','.join([unicode(b) for b in row])))
            if len(columns) != len(row):
                raise PageException("Row %s (%s) has wrong length." % (row_key,u','.join([unicode(b) for b in row])))
            row_order.append(row_key)
            d[row_key] = dict(zip(columns, row))
        self._parsed = {'rows':d,'order':row_order,'columns':columns}
        
    def html_preview(self):
        if not self.errors():
            return render_to_string('factsheet.html',{'order':self.parsed()['order'],'rows':self.rows()})
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
        if not isinstance(yaml_obj, dict):
            raise PageException('A template cannot be empty.')
        front_template = yaml_obj.get('front','')
        back_template = yaml_obj.get('back','')
        if(self.DJANGO_CONTROL_TAG.search(front_template) or 
           self.DJANGO_CONTROL_TAG.search(back_template)):
           raise PageException('Control tags ( {% tag %} ) are not allowed.')
        background = yaml_obj.get('background', '#fff9cc')
        front_vars = self.DJANGO_VARIABLE_TAG.findall(front_template)
        back_vars = self.DJANGO_VARIABLE_TAG.findall(back_template)
        all_vars = set(front_vars).union(set(back_vars))
        self._parsed = {'front':front_template,
                        'back' :back_template,
                        'background_color': background,
                        'variables' : all_vars,
                        'front_vars': front_vars,
                        'back_vars': back_vars}
                        
    def variables(self):
        return self.parsed().get('variables',[])
        
    def front_vars(self):
        return self.parsed().get('front_vars',[])
    
    def back_vars(self):
        return self.parsed().get('back_vars',[])
    
    def html_preview(self):
        v = self.variables()
        row = dict(zip(v,v))
        return mark_safe(
            '<div class="splitview">'+
            render_to_string('card.html',{'card':CardRenderer(row=row,template=self)})
            +'</div>')


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
    modified = db.DateTimeProperty(auto_now=True)
    public = db.BooleanProperty(default=True)
    factsheet = db.ReferenceProperty(Factsheet)
    template = db.ReferenceProperty(Template)
    mapping = db.TextProperty(default='')
    
    meta_keys = {'subject':'meta_subject',
                 'book':'meta_book'}
    meta_subject = db.StringProperty()
    meta_book = db.StringProperty()
    
    @property
    def url(self):
        """ Returns the view url for this cardset. 
        """
        return reverse('cardbox.views.cardset_view',args=[self.key().id()])
        
    def html_meta(self):
        s = []
        for key, attr_name in self.meta_keys.items():
            if getattr(self, attr_name):
                s.append('%s: %s' % (key, getattr(self, attr_name)))
        return ', '.join(s)
        
    def set_meta_data(self):
        keys = self.meta_keys.keys()
        for sub in [self.factsheet, self.template]:
            for k in keys:
                if k in sub.meta_keys:
                    setattr(self, self.meta_keys[k], getattr(sub, sub.meta_keys[k]))
            
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
        if self.factsheet is not None and not self.factsheet.errors():
            k = self.key().id()
            return [(k, c_id) for c_id in self.factsheet.row_ids()]
        else:
            return []
        
    def mapping_as_json(self):
        return simplejson.dumps(yaml.load(self.mapping))

class Box(db.Model):
    study_set_size = 10
    
    title = db.StringProperty(default='New Box')
    owner = db.UserProperty(auto_current_user_add=True)
    modified = db.DateTimeProperty(auto_now=True)
    cardsets = db.ListProperty(int)
    scheduler = db.ReferenceProperty(Scheduler)
    selector = db.TextProperty()
    last_studied = db.DateTimeProperty(default=datetime.datetime(2010,1,1))
    time_studied = TimeDeltaProperty(default=datetime.timedelta(0))
    
    def put(self, *args, **kwds):
        db.Model.put(self, *args, **kwds)
        self._update_cards()
        
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
        
    def stats(self):
        if not hasattr(self, '_stats') or self._stats is None:
            n_cards = len(list(self.all_card_ids()))
            available = Card.all(keys_only=True).ancestor(self)
            available.order('learned_until')
            available.filter('learned_until <', datetime.datetime.now())
            available.filter('enabled',True)
            n_available = available.count()
            n_learned = n_cards - n_available
            percentage = (n_learned/float(n_cards))*100.0 if n_cards > 0 else 0.0
            self._stats = {'percent_learned':percentage,'n_learned':n_learned,'n_cards':n_cards}
        return self._stats
        
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
        if len(study_set) < self.study_set_size/2:
            available = Card.all().ancestor(self)
            available.filter('enabled',True)
            available.filter('learned_until <', datetime.datetime.now())
            available = list(available.fetch(100))
            logging.info("available cards: %d"%len(available))
            
            available = filter(lambda x: not x.in_study_set, available)
            logging.info("available cards filtered: %d"%len(available))
            
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
        output = []
        cardsets = Cardset.get_by_id(self.cardsets)
        for c in cardsets:
            output.extend(c.all_ids())
        return output
    
    def render_card(self, id_tuple):
        set_id, card_id = id_tuple
        set_id = int(set_id)
        if set_id in self.cardsets:
            cardset = Cardset.get_by_id(set_id)
            return cardset.render_card(card_id)
        else:
            raise Exception("Trying to render card from set that is not in box.")

                    
class Card(db.Model):
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
        
    def cardset(self):
        if not hasattr(self, '_cardset'):
            self._cardset = Cardset.get_by_id(int(self.key().name().split('-',1)[0]))
        return self._cardset
        
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
        if not hasattr(self, '_rendered') or self._rendered is None:
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
        if not hasattr(self, '_rendered') or self._rendered is None:
            self._rendered = self._render()        
        return self._rendered
    
    def front(self):
        return self.rendered()['front']
    
    def back(self):
        return self.rendered()['back']
        
    def front_data(self):
        return self.rendered()['front_data']

    def back_data(self):
        return self.rendered()['back_data']
        
    def background_color(self):
        return self.rendered()['background_color']
    
    def _render(self):
        EMPTY_FIELD = mark_safe('&#160;&#160;')
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
        # Actual rendering
        base = dict([(v,EMPTY_FIELD) for v in self.template.variables()])
        base.update(self.row)        
        mapping = yaml.load(self.mapping)
        if mapping is not None and mapping != 'None' and mapping != '':
            base.update([(newkey, base[oldkey]) for newkey, oldkey in mapping.items() if oldkey not in [None,'None']])
        # Extract the base values first, without wrapping or templating
        front_data = filter(lambda x: x != EMPTY_FIELD,[mark_safe(base[d]) for d in self.template.front_vars()])
        back_data = filter(lambda x: x != EMPTY_FIELD,[mark_safe(base[d]) for d in self.template.back_vars()])
        back_data = filter(lambda x: x not in front_data, back_data)
        # Wrap all fields in a span with their ID
        for k in base.keys():
            base[k] = mark_safe('<span class="tfield" id="tfield_%s">%s</span>'%(k,encode_html(base[k])))
        # Apply the template
        front = django_templates.Template(
            self.template.parsed()['front']).render(django_templates.Context(base))
        back = django_templates.Template(
            self.template.parsed()['back']).render(django_templates.Context(base))
        front = mark_safe(textile.textile(front))
        back = mark_safe(textile.textile(back))
        return {'front':front, 'front_data':front_data, 
                'back':back,   'back_data' :back_data,
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

