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

### Constants ###
NEW_TEMPLATES = [models.CardTemplate(n) for n in ['default','large_centered']]
MOBILE_NAMES = re.compile(r"android|avantgo|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\\/|plucker|pocket|psp|symbian|treo|up\\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino", re.I|re.M)
MOBILE_CODES = re.compile(r"1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\\-(n|u)|c55\\/|capi|ccwa|cdm\\-|cell|chtm|cldc|cmd\\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\\-s|devi|dica|dmob|do(c|p)o|ds(12|\\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\\-|_)|g1 u|g560|gene|gf\\-5|g\\-mo|go(\\.w|od)|gr(ad|un)|haie|hcit|hd\\-(m|p|t)|hei\\-|hi(pt|ta)|hp( i|ip)|hs\\-c|ht(c(\\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\\-(20|go|ma)|i230|iac( |\\-|\\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\\/)|klon|kpt |kwc\\-|kyo(c|k)|le(no|xi)|lg( g|\\/(k|l|u)|50|54|e\\-|e\\/|\\-[a-w])|libw|lynx|m1\\-w|m3ga|m50\\/|ma(te|ui|xo)|mc(01|21|ca)|m\\-cr|me(di|rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\\-2|po(ck|rt|se)|prox|psio|pt\\-g|qa\\-a|qc(07|12|21|32|60|\\-[2-7]|i\\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\\-|oo|p\\-)|sdk\\/|se(c(\\-|0|1)|47|mc|nd|ri)|sgh\\-|shar|sie(\\-|m)|sk\\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\\-|v\\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\\-|tdg\\-|tel(i|m)|tim\\-|t\\-mo|to(pl|sh)|ts(70|m\\-|m3|m5)|tx\\-9|up(\\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|xda(\\-|2|g)|yas\\-|your|zeto|zte\\-", re.I|re.M)


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
    """Decorator that insists that you're logged in as administrator."""
    
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
    """ Renders the frontpage/redirects to mobile front page
    """
    
    if request.META.has_key('HTTP_USER_AGENT'):
        user_agent = request.META['HTTP_USER_AGENT']
        b = MOBILE_NAMES.search(user_agent)
        v = MOBILE_CODES.search(user_agent[0:4])
        if b or v:
            return HttpResponseRedirect(reverse("cardbox.views.mobile_front"))
    
    return respond(request,'front.html')
    
def help(request):
    """ Help page """
    return respond(request, 'help.html')
    
def list_view(request, name):
    factsheet = models.Factsheet.get_by_name(name)
    return respond(request, 'list_view.html',{'list':factsheet})
    
    
@login_required
def list_edit(request, name=None):
    LIST_HEADER_FORMAT = 'list-header-%d'
    LIST_CELL_FORMAT   = 'list-row-%d-col-%d'
    if name is None:
        factsheet = models.Factsheet()
    else:
        factsheet = models.Factsheet.get_by_name(name)
    errors = []
    if request.method == 'POST':
        # Extract columns and trim last column if unused
        columns = [request.POST[LIST_HEADER_FORMAT%v] for v in range(10) if LIST_HEADER_FORMAT%v in request.POST]
        columns = columns if columns[-1] else columns[:-1]
        # Extract rows
        logging.info(request.POST)
        i, rows = 0, []
        logging.info(LIST_CELL_FORMAT%(i,0))
        while LIST_CELL_FORMAT%(i,0) in request.POST:
            row = [request.POST[LIST_CELL_FORMAT%(i,j)] for j in xrange(len(columns))]
            logging.info(row)
            if any(row):
                rows.append(row)
            i += 1
        try:
            factsheet.set_title(request.POST['title'])
            factsheet.set_columns_and_rows(columns, rows)
            factsheet.save()
            name = factsheet.name
        except models.FactsheetError, e:
            errors.append(u'Error in List: %s'%(unicode(e)))
        # Process cardset form
        if 'cardset-id' in request.POST:
            cids      = request.POST.getlist('cardset-id')
            mappings  = request.POST.getlist('cardset-mapping')
            templates = request.POST.getlist('cardset-template')
            titles    = request.POST.getlist('cardset-title')
            logging.info(mappings)
            logging.info(templates)
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
        if not errors:
            return HttpResponseRedirect(reverse('cardbox.views.list_view',args=[name]))
        
    return respond(request, 'list_edit.html',{'list':factsheet,'errors':errors,'templates':NEW_TEMPLATES})
    
@login_required
def list_create(request):
    return list_edit(request,None)
    
def list_browse(request):
    return respond(request, 'list_browse.html', {'lists':models.Factsheet.all()})

@login_required
def box_create(request):
    return box_edit(request)

@login_required
def box_edit(request, box_id=None):
    box = models.Box() if (box_id is None) else get_by_id_or_404(request, models.Box, box_id)
    if request.method == 'POST':
        if 'title' in request.POST:
            box.title = request.POST['title']
        if 'add-cardset' in request.POST:
            cid = int(request.POST['add-cardset'])
            if cid not in box.cardsets:
                box.cardsets.append(cid)
        if 'cardset-id' in request.POST:
            box.cardsets = [int(x) for x in request.POST.getlist('cardset-id') if x != '']
        box.put()
        box.update_cards()
        if request.is_ajax():
            return HttpResponse('success')
        return HttpResponseRedirect(reverse('cardbox.views.frontpage'))

    return respond(request, 'box.html',{'box':box})
    
@login_required
def box_stats(request, box_id):
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True)
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
    correct = request.POST['correct'] == '1'
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
    
def templates(request):
    return respond(request, 'templates.html',{'templates':NEW_TEMPLATES})
            
def template_view(request, template_name):
    return HttpResponse(models.CardTemplate(template_name).render_fields())
    
def template_fields(request, template_name):
    m = models.CardTemplate(template_name)
    return HttpResponse(simplejson.dumps({'front':m.front_fields,'back':m.back_fields}))
    
@login_required
def mobile_front(request):
    return respond(request, 'mobile_front.html')
    
def mobile_study(request, box_id):
    box = get_by_id_or_404(request, models.Box, box_id, require_owner=True)
    if request.method == 'POST':
        card_id = request.POST['card_id']
        correct = request.POST['correct'] == '1'
        logging.info(correct)
        studied_card = models.Card.get_by_key_name(card_id, parent=box)
        studied_card.answered(correct)
    card = box.card_to_study()
    logging.info(card.get_cardset())
    return respond(request, 'mobile_study.html',{'box':box,'card':card})
    

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
    if (require_owner and 
        (not request.user_is_admin) and 
        (request.user is None or entity.owner != request.user.google_user)):
        raise Http404
    return entity
