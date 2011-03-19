from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',

   (r"^$", "cardbox.views.frontpage"),
   (r"^help$","cardbox.views.help"),
   (r"^(?P<kind>(list|template))/create$", "cardbox.views.page_create"),
   (r"^(?P<kind>(list|template))/(?P<name>[a-z]+:?[a-z0-9\_]+)/view$", "cardbox.views.page_view"),
   (r"^(?P<kind>(list|template|scheduler))/(?P<name>[a-z]+:?[a-z0-9\_]+)/edit$", "cardbox.views.page_edit"),
   (r"^(?P<kind>(list|template))/(?P<name>[a-z]+:?[a-z0-9\_]+)/preview$", "cardbox.views.page_preview"),
   (r"^(?P<kind>(list))/(?P<name>[a-z]+:?[a-z0-9\_]+)/json$","cardbox.views.page_json"),
   
   (r"^cardset/create$","cardbox.views.cardset_create"),
   (r"^cardset/([0-9]+)/view$","cardbox.views.cardset_view"),
   (r"^cardset/([0-9]+)/edit$","cardbox.views.cardset_edit"),
   
   (r"^box/create$","cardbox.views.box_create"),
   (r"^box/([0-9]+)/edit$","cardbox.views.box_edit"),
   (r"^box/([0-9]+)/stats$","cardbox.views.box_stats"),
   
   (r"^box/([0-9]+)/study$","cardbox.views.study"),
   (r"^box/([0-9]+)/next_card$","cardbox.views.next_card"),
   (r"^box/([0-9]+)/update_card","cardbox.views.update_card"),
   
   (r"^box/(?P<box_id>[0-9]+)/card/(?P<card_id>[0-9]+\-[A-Za-z0-9\-\_\.]+)/view$","cardbox.views.card_view"),
      
   (r"^(?P<kind>list|template|scheduler|cardset)/all/browse$","cardbox.views.browse"),
   (r"^(?P<kind>list|template|scheduler|cardset)/all/data$","cardbox.views.browse_data")
   
)
