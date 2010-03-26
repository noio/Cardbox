### Imports ###

# Python Imports
import hashlib

# AppEngine imports
from google.appengine.api import users

# Local Imports
from models import Account, Box

class AddUserToRequestMiddleware(object):
  """Add a user object and a user_is_admin flag to each request."""

  def process_request(self, request):
    """ This function sets up the user object
        Depending on the value of require_login, it
        can return None as 'profile'.
    """
    #Get Google user_id
    google_user = users.get_current_user()
    account = None
    is_admin = False
    if google_user:
        #Check if the user already has a site profile
        user_id = google_user.user_id()
        is_admin = users.is_current_user_admin()
        q = Account.all()
        q.filter('google_user =', google_user)
        account = q.get()
        
        if not account:
            nickname = hashlib.md5(google_user.nickname()).hexdigest()[:10]
            account = Account(user_id = user_id, nickname = nickname)
            account.put()
            box = Box(title='My Box')
            box.put()
            
    request.user = account
    Account.current_user_account = account
    request.user_is_admin = is_admin
