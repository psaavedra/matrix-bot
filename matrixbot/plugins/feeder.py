#!/usr/bin/env python3

import feedparser
import pytz
import time
from datetime import datetime, timedelta
from matrixbot import utils
from dateutil import parser

def utcnow():
    now = datetime.utcnow()
    return now.replace(tzinfo=pytz.utc)

class FeederPlugin:
    def __init__(self, bot, settings):
        self.name = "FeederPlugin"
        self.logger = utils.get_logger()
        self.bot = bot
        self.settings = settings
        self.logger.info("FeederPlugin loaded (%(name)s)" % settings)
        self.timestamp = {}
        for feed in list(self.settings["feeds"].keys()):
            self.timestamp[feed] = utcnow()
        self.lasttime = time.time()
        self.period = self.settings.get('period', 60)

    def pretty_entry(self, entry):
        title = entry.get("title", "New post")
        author = entry.get("author", "")
        if author is not "":
            author = " by %s" % author
        link = entry.get("link", "")
        if link is not "":
            link = " (%s)" % link
        res = """%s%s%s""" % (title, author, link)
        return res

    def dispatch(self, handler):
        self.logger.debug("FeederPlugin dispatch")
        now = time.time()
        if now < self.lasttime + self.period:
            return  # Feeder is only updated each 'period' time
        self.lasttime = now

        res = []
        for feed_name, feed_url in list(self.settings["feeds"].items()):
            self.logger.debug("FeederPlugin dispatch: Fetching %s ..." % feed_name)
            try:
                feed = feedparser.parse(feed_url)
                updated = feed.get('feed',{}).get(
                                                  'updated',
                                                  utcnow().isoformat()
                                                 )
                updated_dt = parser.parse(updated)
                if updated_dt > self.timestamp[feed_name]:
                    actual_updated_dt = self.timestamp[feed_name]
                    for entry in feed['entries']:
                        entry_dt = parser.parse(entry["updated"])
                        if entry_dt > self.timestamp[feed_name]:
                            res.append(entry)
                        actual_updated_dt = max (entry_dt, actual_updated_dt)
                    self.timestamp[feed_name] = actual_updated_dt
            except Exception as e:
                self.logger.error("FeederPlugin got error in feed %s: %s" % (feed_name,e))

        if len(res) == 0:
            return

        res = list(map(
            self.pretty_entry,
            res
        ))
        message = "\n".join(res)
        for room_id in self.settings["rooms"]:
            room_id = self.bot.get_real_room_id(room_id)
            self.bot.send_notice(room_id, message)

    def command(self, sender, room_id, body, handler):
        self.logger.debug("FeederPlugin command")
        return

    def help(self, sender, room_id, handler):
        self.logger.debug("FeederPlugin help")
        return
