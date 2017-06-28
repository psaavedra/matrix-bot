import feedparser
import pytz
from datetime import datetime, timedelta
from matrixbot import utils
from dateutil import parser

def utcnow():
    now = datetime.utcnow()
    return now.replace(tzinfo=pytz.utc)

class FeederPlugin:
    def __init__(self, bot, settings):
        self.logger = utils.get_logger()
        self.logger.info("FeederPlugin loaded")
        self.bot = bot
        self.settings = settings
        self.timestamp = {}
        for feed in self.settings["feeds"].keys():
            self.timestamp[feed] = utcnow()

    def pretty_entry(self, entry):
        entry["title"]
        entry["author"]
        entry["link"]
        res = """%(title)s by %(author)s (%(link)s)""" % entry
        return res

    def async(self, handler):
        self.logger.debug("FeederPlugin async")

        res = []
        for feed_name, feed_url in self.settings["feeds"].iteritems():
            self.logger.debug("FeederPlugin async: Fetching %s ..." % feed_name)
            try:
                feed = feedparser.parse(feed_url)
                updated = feed['feed']['updated']
                updated_dt = parser.parse(updated)
                if updated_dt > self.timestamp[feed_name]:
                    for entry in feed['entries']:
                        entry_dt = parser.parse(entry["updated"])
                        if entry_dt > self.timestamp[feed_name]:
                            res.append(entry)
                    self.timestamp[feed_name] = updated_dt
            except Exception as e:
                self.logger.error("FeederPlugin got error in feed %s: %s" % (feed_name,e))

        if len(res) == 0:
            return

        res = map(
            self.pretty_entry,
            res
        )
        message = "\n".join(res)
        for room_id in self.settings["rooms"]:
            # handler(room_id, message)
            self.bot.send_notice(room_id, message)

    def command(self, sender, room_id, body, handler):
        self.logger.debug("FeederPlugin command")
        return

    def help(self, sender, room_id, handler):
        self.logger.debug("FeederPlugin help")
        return
