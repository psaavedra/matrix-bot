import feedparser
import pytz
import requests
import time
from datetime import datetime, timedelta
from matrixbot import utils
from matrixbot import plugins
from matrixbot.plugins.feeder import FeederPlugin
from dateutil import parser

WK_BUGS_API="https://bugs.webkit.org/rest/bug/"

def utcnow():
    now = datetime.utcnow()
    return now.replace(tzinfo=pytz.utc)

class WKBugsFeederPlugin(FeederPlugin):
    def pretty_entry(self, entry):
        title = entry.get("title", "New post")
        author = entry.get("author", "")
        id_ = entry.get("id", "id=NONE").split("=")[1]
        try:
            bug_json = requests.get(WK_BUGS_API + id_).json()
            if author == "":
                author = " by %s (%s)" % (author,
                                          bug_json['bugs'][0]['creator'].split("@")[0])
            status = bug_json['bugs'][0]['status']
            if status == "RESOLVED":
                resolution = bug_json['bugs'][0]['resolution']
                status = " (%s %s)" % (status, resolution)
            else:
                last_change_time = bug_json['bugs'][0]['last_change_time']
                creation_time = bug_json['bugs'][0]['creation_time']
                if last_change_time == creation_time:
                    status = " (NEW)"
                else:
                    status = " (UPDATED)"
        except Exception:
            status = ""
        link = entry.get("link", "")
        if link is not "":
            link = " (%s)" % link
        res = """%s%s%s%s""" % (title, author, link, status)
        return res
