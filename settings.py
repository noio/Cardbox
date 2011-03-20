"""Minimal Django settings."""

import os

APPEND_SLASH = False
DEBUG = True
INSTALLED_APPS = ('cardbox',)
ROOT_PATH = os.path.dirname(__file__)
ROOT_URLCONF = 'urls'
MIDDLEWARE_CLASSES = (
    #'google.appengine.ext.appstats.recording.AppStatsDjangoMiddleware',
    #'firepython.middleware.FirePythonDjango',
    #'appstats.recording.AppStatsDjangoMiddleware',
    'django.middleware.common.CommonMiddleware',
    #'django.middleware.http.ConditionalGetMiddleware',
    'cardbox.middleware.AddUserToRequestMiddleware'
)
TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.request',
)
TEMPLATE_STRING_IF_INVALID = 'ERROR IN %s' if DEBUG else ''
TEMPLATE_DEBUG = DEBUG
TEMPLATE_DIRS = (
    os.path.join(ROOT_PATH, 'templates'),
)
MEDIA_URL = '/static/'

