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

# AppEngine imports
from google.appengine.ext import db
from google.appengine.ext.db import Key
from google.appengine.api import users
from google.appengine.api import memcache

# Django imports
from django import forms
from django.shortcuts import render_to_response
from django.conf import settings as django_settings
from django.http import HttpResponse, HttpResponseRedirect
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.template import Template, Context
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse
#from django.utils.safestring import mark_safe
from django.utils import simplejson
#from django.core.exceptions import ValidationError

# Library imports
import yaml
import tools.textile as textile

# Local Imports
import models

### Form classes ###

class CardsetForm(forms.Form):
    title = forms.CharField(widget=forms.TextInput(attrs={'class':'title'}))
    factsheet = forms.CharField()
    template = forms.CharField()
    mapping = forms.CharField(widget=forms.Textarea())
    

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

def page_view(request, pagename):
    fs = models.Page.get_by_name(pagename)
    return respond(request,'page.html', {'editable':False,
                                         'page':fs})
    
@login_required
def page_edit(request, pagename):
    fs = models.Page.get_by_name(pagename)
    if fs is None:
        return HttpResponseForbidden('Name not allowed.')
    if request.method == 'POST':
        content = request.POST['content']
        fs.edit(content)
    return respond(request,'page.html',{'editable':True,
                                        'page':fs})

def page_revision(request, pagename, revision):
    fs = models.Page.get_by_name(pagename)
    fs = fs.revision(int(revision))
    return respond(request,'page.html',{'page':fs})

@login_required
def cardset_new(request):
    return cardset_edit(request)
    
def cardset_view(request, set_id):
    cardset = get_by_id_or_error(request, models.Cardset, set_id)
    return respond(request, 'cardset.html',{'cardset':cardset})

@login_required
def cardset_edit(request, set_id=None):
    cardset = get_by_id_or_error(request, models.Cardset, set_id, require_owner=True, new_if_id_none=True)
    factsheets = models.Factsheet.all().fetch(1000)
    templates = models.Template.all().fetch(1000)
    if request.method == 'POST':
        cardset.title = request.POST['title']
        cardset.factsheet = request.POST['factsheet']
        cardset.template = request.POST['template']
        #TODO: Validate mapping
        cardset.mapping = yaml.dump(simplejson.loads(request.POST['mapping']))
        cardset.put()
        return HttpResponseRedirect(reverse('cardbox.views.cardset_edit',args=[cardset.key().id()]))
    return respond(request, 'cardset_edit.html',{'cardset':cardset, 'factsheets':factsheets,'templates':templates})

def template_preview(request, template_name):
    template = models.Template.get_by_name(template_name)
    return HttpResponse(template.html_preview())

@login_required
def box_new(request):
    return box_edit(request)

@login_required
def box_edit(request, box_id=None):
    box = get_by_id_or_error(request, models.Box, box_id, require_owner=True, new_if_id_none=True)
    if request.method == 'POST':
        box.title = request.POST['title']
        box.cardsets = [int(x) for x in request.POST['cardsets'].split(',') if x != '']
        box.put()
        return HttpResponseRedirect(reverse('cardbox.views.box_edit',args=[box.key().id()]))
    
    cardsets = models.Cardset.all().fetch(1000)
    return respond(request, 'box.html',{'box':box, 'cardsets':cardsets})

@login_required
def study(request, box_id):
    box = get_by_id_or_error(request, models.Box, box_id, require_owner=True, new_if_id_none=False)
    return respond(request, 'study.html',{'box':box})
    
@login_required
def update_card(request,box_id):
    """ Updates the total scores of card through POST.
    """
    card_id = request.POST['card_id']
    correct = request.POST['correct'] == 'true'
    box = get_by_id_or_error(request, models.Box, box_id, require_owner=True, new_if_id_none=False)
    studied_card = models.Card.get_by_key_name(card_id, parent=box)
    studied_card.update(correct)
    return HttpResponse('success')

@login_required
def next_card(request, box_id):
    """ Returns a random next card from given box.
    """
    box = get_by_id_or_error(request, models.Box, box_id, require_owner=True, new_if_id_none=False)
    card = box.card_to_study()
    return respond(request, 'card_study.html',{'box':box,'card':card})

def create(request):
    return respond(request, 'create.html',{})

def browse(request):
    #print request.GET.items()
    return respond(request, 'browse.html')
    
def browse_data(request,kind):
    if kind == 'factsheet':
        entities = models.Factsheet.all().fetch(1000)
        headers = ['id','url','name','columns','modified','revision']
        rows = [ (e.key().name(),
                  reverse('cardbox.views.page_view',args=[e.key().name()]),
                  e.name(False), 
                  ','.join(e.columns()),
                  e.modified.strftime('%d/%m/%Y'), 
                  e.revision_number) for e in entities]
    elif kind == 'template':
        entities = models.Template.all().fetch(1000)
        headers = ['id','url','name','variables','modified','revision']
        rows = [ (e.key().name(),
                  reverse('cardbox.views.page_view',args=[e.key().name()]),
                  e.name(False), 
                  ','.join(e.variables()), 
                  e.modified.strftime('%d/%m/%Y'), 
                  e.revision_number) for e in entities]
    elif kind == 'scheduler':
        entities = models.Scheduler.all().fetch(1000)
        headers = ['id','url','name','modified','revision']
        rows = [ (e.key().name(),
                  reverse('cardbox.views.page_view',args=[e.key().name()]),
                  e.name(False), 
                  e.modified.strftime('%d/%m/%Y'), 
                  e.revision_number) for e in entities]
    elif kind == 'cardset':
        if 'box' in request.GET:
            box = get_by_id_or_error(request,models.Box,request.GET['box'])
            entities = models.Cardset.get_by_id(box.cardsets)
        else:
            entities = models.Cardset.all().fetch(1000)
        headers = ['id','url','name','factsheet','created']
        rows = [ (e.key().id(),
                  reverse('cardbox.views.cardset_view',args=[e.key().id()]),
                  e.title,
                  e.factsheet.name(False) + ' ('+ ','.join(e.factsheet.columns()) +')',
                  e.created.strftime('%d/%m/%Y')) for e in entities]
    else:
        return HttpResponseForbidden('Kind not found.')
                  
    return HttpResponse(simplejson.dumps({'headers':headers,'rows':rows}))

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
        params['sign_in'] = users.create_login_url(full_path)
    else:
        params['sign_out'] = users.create_logout_url(full_path)
    return render_to_response(template, params)
    
def get_by_id_or_error(request, kind, entity_id, require_owner=True, new_if_id_none=True):
    """ Gets an entity by id. If the id is not found, will error,
        unless new_if_id_none, in that case a new entity is returned.
    """
    if isinstance(entity_id, basestring):
        entity_id = int(entity_id)
    if new_if_id_none and entity_id is None:
        return kind()
    entity = kind.get_by_id(entity_id)
    account = models.Account.current_user_account
    if entity is None or (require_owner and 
        (request.user is None or entity.owner != request.user.google_user)):
        return HttpResponseForbidden('This link is invalid or you\'re not allowed to view it.')
    return entity