from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

import os
import settings
import cgi
import httplib2
import logging
import urllib
from google.appengine.api import memcache

from oauth2client.appengine import OAuth2Decorator
from apiclient.discovery import build
import datetime

http = httplib2.Http(memcache)
httpUnauth = httplib2.Http(memcache)

decorator = OAuth2Decorator(
    client_id=settings.CLIENT_ID,
    client_secret=settings.CLIENT_SECRET,
    scope = 'https://www.googleapis.com/auth/plus.me' )

# Get discovery document
ul = urllib.urlopen(settings.DISCOVERY_DOCUMENT)
discovery_doc = ul.read()
ul.close()

service = build("plus", "v1", http=http)
serviceUnauth = build("plus", "v1", http=http, developerKey=settings.API_KEY)

def decode_timestamp(timestamp):
    #RFC 3339 timestamp.
    #e.g.     2011-10-05T15:23:21.000Z
    d, t = timestamp.split('T')
    return datetime.datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), int(t[:2]), int(t[3:5]), int(t[6:8]))

def shorten_title(title):
    if len(title) > 40:
        return title[:37] + '...'
    return title

def prepare_activity(a):
    if a.has_key('published'):
        timestamp = decode_timestamp(a['published'])
        delta = timestamp - datetime.datetime.now()
        a['published_today'] = delta.days == 0
        a['published_dt'] = timestamp
    if a.has_key('title'):
        a['short_title'] = shorten_title(a['title'])

    if a.has_key('object'):
        for attach in a['object'].get('attachments', []):
            if attach.has_key('fullImage'):
                image = attach['fullImage']
                if (image.get('height', 400) * image.get('width', 400)) < 160000:
                    image['small'] = True

def prepare_comment(c):
    if c.has_key('published'):
        timestamp = decode_timestamp(c['published'])
        delta = timestamp - datetime.datetime.now()
        c['published_today'] = delta.days == 0
        c['published_dt'] = timestamp

def prepare_activities(activities):
    for a in activities:
        prepare_activity(a)

def prepare_comments(comments):
    for c in comments:
        prepare_comment(c)

class MainPage(webapp.RequestHandler):
    '''The main blog page, including the most recent stories (activities)'''

    def get(self):
        activities_doc = serviceUnauth.activities().list(userId=settings.GPLUS_ID, collection='public').execute(httpUnauth)
        activities = activities_doc.get('items', [])
        prepare_activities(activities)
        template_values = {
            'activities': activities
        }
        path = os.path.join(os.path.dirname(__file__), 'templates/main.html')
        self.response.out.write(template.render(path, template_values))

class ActivityPage(webapp.RequestHandler):
    '''A page to display the specified activity, including the most recent comments'''

    def get(self, activityId):
        activity = serviceUnauth.activities().get(activityId=activityId).execute(httpUnauth)
        prepare_activity(activity)
        comments = serviceUnauth.comments().list(activityId=activityId).execute(httpUnauth).get('items', [])
        prepare_comments(comments)
        template_values = {
            'activity': activity,
            'comments': comments
        }
        path = os.path.join(os.path.dirname(__file__), 'templates/activity.html')
        self.response.out.write(template.render(path, template_values))

class SplashPage(webapp.RequestHandler):
    def get(self):
#        path = os.path.join(os.path.dirname(__file__), 'templates/index.html')
#        self.response.out.write(template.render(path, {}))
        #Temporarily disable the website landing page and go straight to the blog:
        self.redirect("/blog/")

application = webapp.WSGIApplication(
                                     [(r'/', SplashPage),
                                      (r'/blog/', MainPage),
                                      (r'/blog/activity/(.*)/', ActivityPage)],
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

