from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
   (r"^$", "cardbox.views.frontpage"),
   (r"^view/([a-z]+:?[a-z0-9\_]+)$", "cardbox.views.page_view"),
   (r"^edit/([a-z]+:?[a-z0-9\_]+)$", "cardbox.views.page_edit"),
   (r"^revision/([a-z]+:?[a-z0-9\_]+)/([0-9]+)$", "cardbox.views.page_revision"),
   
   (r"^create$", "cardbox.views.create"),
   
   (r"^cardset$","cardbox.views.cardset_new"),
   (r"^cardset/([0-9]+)$","cardbox.views.cardset_view"),
   (r"^edit_cardset/([0-9]+)$","cardbox.views.cardset_edit"),
   
   (r"^box$","cardbox.views.box_new"),
   (r"^box/([0-9]+)$","cardbox.views.box_edit"),
   
   (r"^study/([0-9]+)$","cardbox.views.study"),
   (r"^next_card/([0-9]+)$","cardbox.views.next_card"),
   (r"^update_card/([0-9]+)","cardbox.views.update_card"),
   
   (r"^browse$","cardbox.views.browse"),
   (r"^browse_data/(?P<kind>factsheet|template|scheduler|cardset)$","cardbox.views.browse_data"),
   
   (r"^template_preview/([a-z]+:?[a-z0-9\_]+)$", "cardbox.views.template_preview")
)
