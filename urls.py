from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',

   (r"^$", "cardbox.views.frontpage"),
   (r"^help$","cardbox.views.help"),
   (r"^list/create","cardbox.views.list_create"),
   (r"^list/(?P<name>[a-z]+:?[a-z0-9\_]+)/view$", "cardbox.views.list_view"),
   (r"^list/(?P<name>[a-z]+:?[a-z0-9\_]+)/edit$", "cardbox.views.list_edit"),
   (r"^list/all/browse$", "cardbox.views.list_browse"),
   
   (r"^box/create$","cardbox.views.box_create"),
   (r"^box/([0-9]+)/edit$","cardbox.views.box_edit"),
   (r"^box/([0-9]+)/stats$","cardbox.views.box_stats"),
   
   (r"^box/([0-9]+)/study$","cardbox.views.study"),
   (r"^box/([0-9]+)/next_card$","cardbox.views.next_card"),
   (r"^box/([0-9]+)/update_card","cardbox.views.update_card"),
   
   (r"^box/(?P<box_id>[0-9]+)/card/(?P<card_id>[0-9]+\-[A-Za-z0-9\-\_\.]+)/view$","cardbox.views.card_view"),
   
   (r"^template/([a-z0-9\_]+)/view","cardbox.views.template_view_ajax"),
   
)
