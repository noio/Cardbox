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
import pprint

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

# Local Imports
import models


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
    return respond(request,'front.html')
    
def help(request):
    """ Help page """
    return respond(request, 'help.html')
    
def list_view(request, name):
    factsheet = models.Factsheet.get_by_name(name)
    return respond(request, 'list_view.html',{'list':factsheet})
    
@login_required
def list_edit(request, name):
    LIST_HEADER_FORMAT = 'list-header-%d'
    LIST_CELL_FORMAT   = 'list-row-%d-col-%d'
    factsheet = models.Factsheet.get_by_name(name)
    errors = []
    if request.method == 'POST':
        # return HttpResponse(pprint.pformat(dict(request.POST.copy())))
        # Extract columns
        columns = [request.POST[LIST_HEADER_FORMAT%v] for v in range(10) if LIST_HEADER_FORMAT%v in request.POST]
        # Extract rows
        i, rows = 0, []
        while LIST_CELL_FORMAT%(i,0) in request.POST:
            row = [request.POST[LIST_CELL_FORMAT%(i,j)] for j in xrange(len(columns))]
            if any(row):
                rows.append(row)
            i += 1
        # Extract meta
        meta_book    = request.POST['list-meta-book'];
        meta_subject = request.POST['list-meta-subject'];
        try:
            factsheet.set_meta(meta_book,meta_subject)
            factsheet.set_columns_and_rows(columns,rows)
            factsheet.save()
        except models.FactsheetError, e:
            errors.append(str(e))
            
        # Process cardset form
        if 'cardset-id' in request.POST:
            cids      = request.POST.getlist('cardset-id')
            mappings  = request.POST.getlist('cardset-mapping')
            templates = request.POST.getlist('cardset-template')
            titles    = request.POST.getlist('cardset-title')
            for cid, mapping, template, title in zip(cids, mappings, templates, titles):
                # Check if an existing set is edited
                if cid.isdigit():
                    cardset = models.Cardset.get_by_id(int(cid))
                    if cardset is None:
                        errors.append('Edited Cardset not found')
                else:
                    cardset = models.Cardset()
                    cardset.factsheet = factsheet
                try:
                    cardset.set_mapping(simplejson.loads(mapping))
                    cardset.set_title(title)
                    cardset.set_template(template)
                    cardset.put()
                except models.CardsetError, e:
                    errors.append('Error in Cardset "%s"(%s) : %s'%(title, cid, str(e)))
        
    return respond(request, 'list_edit.html',{'list':factsheet,'errors':errors})
    
@login_required
def list_create(request):
    factsheet = models.Factsheet()
    return respond(request, 'list_edit.html',{'list':factsheet})
    
def list_browse(request):
    return respond(request, 'list_browse.html', {'lists':models.Factsheet.all()})

@login_required
def box_create(request):
    return box_edit(request)

@login_required
def box_edit(request, box_id=None):
    box = models.Box() if (box_id is None) else get_by_id_or_404(request, models.Box, box_id)
    if request.method == 'POST':
        box.title = request.POST['title']
        box.cardsets = [int(x) for x in request.POST['cardsets'].split(',') if x != '']
        box.update_cards()
        box.put()
        return HttpResponseRedirect(reverse('cardbox.views.frontpage'))
    
    cardsets = models.Cardset.all().fetch(1000)
    return respond(request, 'box.html',{'box':box, 'cardsets':cardsets})
    
@login_required
def box_stats(request, box_id):
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True)
    #print box.charts()['n_cards'].img()
    return respond(request, 'box_stats.html',{'box':box})

@login_required
def study(request, box_id):
    if not request.user.has_studied:
        request.user.has_studied = True
        request.user.put()
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True)
    return respond(request, 'study.html',{'box':box})
    
@login_required
def update_card(request,box_id):
    """ Updates the total scores of card through POST.
    """
    if request.method != 'POST':
        raise Http404
    card_id = request.POST['card_id']
    correct = request.POST['correct'] == 'true'
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True)
    studied_card = models.Card.get_by_key_name(card_id, parent=box)
    studied_card.answered(correct)
    return HttpResponse('success')

@login_required
def next_card(request, box_id):
    """ Returns a random next card from given box.
    """
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True)
    card = box.card_to_study()
    return respond(request, 'card_study.html',{'box':box,'card':card})

    
@login_required
def card_view(request, box_id, card_id):
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True)
    card = models.Card.get_by_key_name(card_id, parent=box)
    return respond(request, 'card_view.html', {'card':card})
    
def template_view_ajax(request, template_name):
    return HttpResponse(models.CardTemplate(template_name).render_fields())

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


def get_by_id_or_404(request, kind, entity_id, require_owner=True):
    """ Gets an entity by id. If the id is not found, will error,
        unless new_if_id_none, in that case a new entity is returned.
    """
    entity_id = int(entity_id) if isinstance(entity_id, basestring) else entity_id
    entity = kind.get_by_id(entity_id)
    account = models.Account.current_user_account
    if entity is None:
        raise Http404
    if (require_owner and (request.user is None or entity.owner != request.user.google_user)):
        raise Http404
    return entity
