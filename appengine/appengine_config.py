import logging, os, re

# Declare the Django version we need.
import django

# Custom Django configuration.
# NOTE: All "main" scripts must import webapp.template before django.
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from django.conf import settings
settings._target = None