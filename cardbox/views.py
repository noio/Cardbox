""" Views for recmd. Views are all classes that return html pages or process forms.
"""

### Imports ###

# Python imports
import logging
import random
import re
import unicodedata
import operator
import hashlib
import datetime

# AppEngine imports
from google.appengine.ext import db
from google.appengine.ext.db import Key
from google.appengine.api import users
from google.appengine.api import memcache

# Django imports
from django import forms
from django.shortcuts import render_to_response
from django.conf import settings as django_settings
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.template import Template, Context
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils import simplejson
#from django.core.exceptions import ValidationError

# Library imports
import yaml
import tools.textile as textile

# Local Imports
import models

### Statics ###

page_kinds = {'list':models.Factsheet,
              'template':models.Template,
              'scheduler':models.Scheduler}

### Decorators for Request Handlers ###

def login_required(func):
    """Decorator that redirects to the login page if you're not logged in."""
    
    def login_wrapper(request, *args, **kwds):
        if request.user is None:
            return HttpResponseRedirect(
                users.create_login_url(request.get_full_path().encode('utf-8')))
        return func(request, *args, **kwds)
    
    return login_wrapper


def admin_required(func):
    """Decorator that insists that you're logged in as administratior."""
    
    def admin_wrapper(request, *args, **kwds):
        if request.user is None:
            return HttpResponseRedirect(
                users.create_login_url(request.get_full_path().encode('utf-8')))
        if not request.user_is_admin:
            return HttpResponseForbidden('You must be admin for this function')
        return func(request, *args, **kwds)
    
    return admin_wrapper


### Page Handlers ###

def frontpage(request):
    """ Renders the frontpage
    """
    factsheets = models.Factsheet.all().order('-modified').fetch(10)
    return respond(request,'front.html', {'factsheets':factsheets})
    
@login_required
def page_create(request, kind):
    return page_edit(request, kind, None)
   
def page_view(request, kind, name):
    model = page_kinds[kind]
    page = model.get_by_name(name)
    return respond(request,'page_view.html', {'page':page})

def page_preview(request, kind, name):
    model = page_kinds[kind]
    page = model.get_by_name(name)
    return HttpResponse(page.html_preview())
    
@login_required
def page_edit(request, kind, name):
    model = page_kinds[kind]
    page = model.get_by_name(name) if name is not None else model()
    if request.method == 'POST':
        content = request.POST['content']
        title = request.POST.get('title',None)
        page.edit(content, title)
        if page.errors():
            return respond(request, 'page_edit.html',{'page':page,'errors':page.errors()})
        return HttpResponseRedirect(reverse('cardbox.views.page_view',kwargs={'kind':kind,'name':page.name}))
    return respond(request,'page_edit.html', {'page':page})
    
def page_json(request, kind, name):
    model = page_kinds[kind]
    page = model.get_by_name(name)
    return HttpResponse(page.json())

@login_required
def cardset_create(request):
    return cardset_edit(request)
    
def cardset_view(request, set_id):
    cardset = get_by_id_or_404(request, models.Cardset, set_id, require_owner=False)
    return respond(request, 'cardset.html',{'cardset':cardset})

@login_required
def cardset_edit(request, set_id=None):
    cardset = get_by_id_or_404(request, models.Cardset, set_id, require_owner=True, new_if_id_none=True)
    factsheets = models.Factsheet.all().fetch(1000)
    templates = models.Template.all().fetch(1000)
    if request.method == 'POST':
        cardset.title = request.POST['title']
        cardset.factsheet = models.Factsheet.get_by_name(request.POST['factsheet'])
        cardset.template = models.Template.get_by_name(request.POST['template'])
        #TODO: Validate mapping
        cardset.mapping = yaml.dump(simplejson.loads(request.POST['mapping']))
        cardset.set_meta_data()
        cardset.put()
        return HttpResponseRedirect(reverse('cardbox.views.cardset_view',args=[cardset.key().id()]))
    return respond(request, 'cardset_edit.html',{'cardset':cardset, 'factsheets':factsheets,'templates':templates})

@login_required
def box_create(request):
    return box_edit(request)

@login_required
def box_edit(request, box_id=None):
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True, new_if_id_none=True)
    if request.method == 'POST':
        box.title = request.POST['title']
        box.cardsets = [int(x) for x in request.POST['cardsets'].split(',') if x != '']
        box.put()
        return HttpResponseRedirect(reverse('cardbox.views.frontpage'))
    
    cardsets = models.Cardset.all().fetch(1000)
    return respond(request, 'box.html',{'box':box, 'cardsets':cardsets})
    
@login_required
def box_stats(request, box_id):
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True, new_if_id_none=False)
    return respond(request, 'box_stats.html',{'box':box})

@login_required
def study(request, box_id):
    if not request.user.has_studied:
        request.user.has_studied = True
        request.user.put()
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True, new_if_id_none=False)
    return respond(request, 'study.html',{'box':box})
    
@login_required
def update_card(request,box_id):
    """ Updates the total scores of card through POST.
    """
    if request.method != 'POST':
        raise Http404
    card_id = request.POST['card_id']
    correct = request.POST['correct'] == 'true'
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True, new_if_id_none=False)
    studied_card = models.Card.get_by_key_name(card_id, parent=box)
    studied_card.answered(correct)
    return HttpResponse('success')

@login_required
def next_card(request, box_id):
    """ Returns a random next card from given box.
    """
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True, new_if_id_none=False)
    card = box.card_to_study()
    return respond(request, 'card_study.html',{'box':box,'card':card})

def browse(request, kind):
    #print request.GET.items()
    return respond(request, 'browse.html',{'kind':kind})
    
@login_required
def card_view(request, box_id, card_id):
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True, new_if_id_none=False)
    card = models.Card.get_by_key_name(card_id, parent=box)
    print card.stats()
    return respond(request, 'card_view.html', {'card':card})

def browse_data(request,kind):
    """ Returns a json object with a list of data of the requested kind
    """
    if kind == 'list':
        model = models.Factsheet
    elif kind == 'template':
        model = models.Template
    elif kind == 'scheduler':
        model = models.Scheduler
    elif kind == 'cardset':
        model = models.Cardset
    else:
        raise Http404('Kind not found.')
    # Apply  filters
    if 'ids' in request.GET:
        ids = [int(i) for i in request.GET['ids'].split(',') if i != '']
        entities = model.get_by_id(ids)
    else:
        entities = model.all()
        for key,value in request.GET.items():
            if value != '' and hasattr(model,'meta_keys') and key in model.meta_keys:
                attr_name = model.meta_keys[key]
                entities.filter(attr_name+' >=',value)
                entities.filter(attr_name+' <',value+u"\ufffd")
    headers = ['id','url','title','tags','date']
    rows = [(e.name if hasattr(e,'name') else e.key().id_or_name(),
            e.url,
            e.title,
            e.html_meta(),
            e.modified.strftime('%d/%M/%Y'))
            for e in entities]
    return HttpResponse(simplejson.dumps({'headers':headers,'rows':rows}))
    
def maintenance(request):
    return HttpResponse("Doing some maintenance, we'll be back really soon.")

### Helper functions ###


def respond(request, template, params=None):
    """ Helper to render a response, passing standard stuff to the response.
        
        Args:
         request: The request object.
         template: The template name; '.html' is appended automatically.
         params: A dict giving the template parameters; modified in-place.
    """
    if params is None:
        params = {}     
    params['request'] = request
    params['user'] = request.user
    params['is_admin'] = request.user_is_admin
    params['media_url'] = django_settings.MEDIA_URL
    full_path = request.get_full_path().encode('utf-8')
    if request.user is None:
        params['sign_in'] = users.create_login_url('/')
        params['notifications'] = params.get('notifications',[]) + [
            """Welcome! New here? Feel free to look around. If you want to start studying, 
            click LOGIN above and log in with your google account."""]
    else:
        #Pass notifications if the user hasn't edited his box, or never studied.
        if not request.user.has_studied:
            edited_box = False
            for b in request.user.my_boxes():
                if b.modified > (request.user.created + datetime.timedelta(seconds=15)):
                    edited_box = True
            if not edited_box:
                params['notifications'] = params.get('notifications',[]) + [
                    u"""You haven't selected any cards to study. Click 'edit' on
                    your box (below), select some cardsets, and click 'Save'"""]
            else:
                params['notifications'] = params.get('notifications',[]) + [
                    u"""To start studying, click 'study' on the box you want to study."""]
                
        params['sign_out'] = users.create_logout_url(full_path)
    return render_to_response(template, params)


def get_by_id_or_404(request, kind, entity_id, require_owner=True, new_if_id_none=True):
    """ Gets an entity by id. If the id is not found, will error,
        unless new_if_id_none, in that case a new entity is returned.
    """
    if isinstance(entity_id, basestring):
        entity_id = int(entity_id)
    if new_if_id_none and entity_id is None:
        return kind()
    entity = kind.get_by_id(entity_id)
    account = models.Account.current_user_account
    if entity is None:
        raise Http404
    if (require_owner and (request.user is None or entity.owner != request.user.google_user)):
        raise Http404
    return entity