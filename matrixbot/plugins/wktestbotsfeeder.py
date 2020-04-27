import json
import pytz
import requests
import urllib
import time
import re

from datetime import datetime, timedelta
from matrixbot import utils
from dateutil import parser

def utcnow():
    now = datetime.utcnow()
    return now.replace(tzinfo=pytz.utc)


def set_property(settings, builder, setting, default=None):
    if setting in builder:
        return
    if setting in settings:
        builder[setting] = settings[setting]
    else:
        builder[setting] = default


class WKTestBotsFeederPlugin:
    def __init__(self, bot, settings):
        self.name = "WKTestBotsFeederPlugin"
        self.logger = utils.get_logger()
        self.bot = bot
        self.settings = settings
        self.logger.info("WKTestBotsFeederPlugin loaded (%(name)s)" % settings)
        for builder_name, builder in self.settings["builders"].iteritems():
            if 'builder_name' not in builder:
                builder['builder_name'] = builder_name
            builder['last_buildjob'] = -1
            set_property(self.settings, builder, "last_buildjob_url_squema")
            set_property(self.settings, builder, "builds_url_squema")
            set_property(self.settings, builder, "only_failures", default=True)
            set_property(self.settings, builder, "notify_recoveries", default=True)
            self.logger.info("WKTestBotsFeederPlugin loaded (%(name)s) builder: " % settings + json.dumps(builder, indent = 4))
        self.lasttime = time.time()
        self.period = self.settings.get('period', 60)

    def pretty_entry(self, builder):
        url = builder['last_buildjob_url_squema'] % {
            'builder_name': urllib.quote(builder['builder_name']),
            'last_buildjob': builder['last_buildjob'],
        }

        res = "%(builder_name)s " % builder
        res += "(<a href='%s'>" % url
        res += "%(last_buildjob)s </a>): " % builder

        if builder['recovery']:
            res += "<p><font color='green'><strong>%s</strong></font> (%s)</p>" % ('Recovery', builder['summary'])
            return res

        if builder['failed']:
            res += "<p><font color='red'><strong>%s</strong></font> (%s)</p>" % ('Exiting early', builder['summary'])
        else:
            res += "<p><font color='green'><strong>%s</strong></font> (%s)</p>" % ('Success', builder['summary'])
        return res

    def sent(self, message):
        for room_id in self.settings["rooms"]:
            room_id = self.bot.get_real_room_id(room_id)
            self.bot.send_html(room_id, message, msgtype="m.notice")

    def has_failed(self, build):
        for each in build['text']:
            if (re.search('exiting early', each, re.IGNORECASE)):
                return True
        return False

    def summary(self, build):
        return " ".join(build['text'])

    def comments(self, build):
        return build['sourceStamp']['changes'][0]['comments']

    def build_number(self, build):
        return build['number']

    def async(self, handler):
        self.logger.debug("WKTestBotsFeederPlugin async")
        now = time.time()
        if now < self.lasttime + self.period:
            return  # Feeder is only updated each 'period' time
        self.lasttime = now

        res = []
        for builder_name, builder in self.settings["builders"].iteritems():
            self.logger.debug("WKTestBotsFeederPlugin async: Fetching %s ..." % builder_name)
            try:
                r = requests.get(builder['builds_url_squema'] % builder).json()
                b = r['-2']
                if builder['last_buildjob'] >= self.build_number(b):
                    continue

                if ('failed' in builder and builder['failed']) and not failed:
                    builder["recovery"] = True
                else:
                    builder["recovery"] = False

                builder["failed"] = self.has_failed(b)
                builder["last_buildjob"] = self.build_number(b)
                builder["last_comments"] = self.comments(b)

                send_message = False
                if not builder['only_failures']:
                    send_message = True
                if builder["failed"]:
                    send_message = True
                if builder["notify_recoveries"] and builder["recovery"]:
                    send_message = True

                if send_message:
                    builder["summary"] = self.summary(b)
                    message = self.pretty_entry(builder)
                    self.sent(message)
            except Exception as e:
                self.logger.error("WKTestBotsFeederPlugin got error in builder %s: %s" % (builder_name,e))


    def command(self, sender, room_id, body, handler):
        self.logger.debug("WKTestBotsFeederPlugin command")
        return

    def help(self, sender, room_id, handler):
        self.logger.debug("WKTestBotsFeederPlugin help")
        return
