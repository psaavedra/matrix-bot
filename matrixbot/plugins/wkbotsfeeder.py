import json
import logging
import os
import pytz
import requests
import sys
import time
import urllib

from datetime import datetime, timedelta
from dateutil import parser

if os.path.dirname(__file__) == "matrixbot/plugins":
    sys.path.append(os.path.abspath("."))

from matrixbot import utils

puts = utils.puts


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


class WKBotsFeederPlugin:
    def __init__(self, bot, settings):
        self.name = "WKBotsFeederPlugin"
        self.logger = utils.get_logger()
        self.bot = bot
        self.settings = settings
        self.logger.info("WKBotsFeederPlugin loaded (%(name)s)" % settings)
        for builder_name, builder in self.settings["builders"].iteritems():
            if 'builder_name' not in builder:
                builder['builder_name'] = builder_name
            builder['last_buildjob'] = -1
            set_property(self.settings, builder, "last_buildjob_url_schema")
            set_property(self.settings, builder, "builds_url_schema")
            set_property(self.settings, builder, "only_failures", default=True)
            set_property(self.settings, builder, "notify_recoveries", default=True)
            self.logger.info("WKBotsFeederPlugin loaded (%(name)s) builder: " % settings + json.dumps(builder, indent = 4))
        self.lasttime = time.time()
        self.period = self.settings.get('period', 60)

    def format(self, text, **kwargs):
       ret="{content}"
       for key in kwargs:
          if key == "color":
             ret = ret.format(content="<font color='{color}'>{{content}}</font>".format(color=kwargs['color']))
          else:
             ret = ret.format(content="<{tag}>{{content}}</{tag}>".format(tag=key))
       return ret.format(content=text)

    def pretty_entry(self, builder):
        url = self.last_build_url(builder)

        res = "%(builder_name)s " % builder
        res += "(<a href='%s'>" % url
        res += "%(last_buildjob)s </a>): " % builder

        if builder['recovery']:
            res += self.format("recovery", color="green", strong="")
        elif builder['failed']:
            res += self.format("failed", color="red", strong="")
        else:
            res += self.format("success", color="green", strong="")
        return res

    def last_build_url(self, builder):
        builderid = int(builder['builderid'])
        build_number = int(builder['last_buildjob'])
        return builder['last_buildjob_url_schema'] % (builderid, build_number)

    def send(self, message):
        for room_id in self.settings["rooms"]:
            room_id = self.bot.get_real_room_id(room_id)
            self.bot.send_html(room_id, message, msgtype="m.notice")

    def should_send_message(self, builder, failed):
        return failed or (not builder['only_failures']) or (builder['notify_recoveries'] and builder['recovery'])

    def build_failed(self, build):
        return not self.build_succeeded(build)

    def build_succeeded(self, build):
        return 'state_string' in build and build['state_string'] == "build successful"

    def get_last_build(self, builder):
        url = builder['builds_url_schema'] % builder['builderid']
        ret = requests.get(url).json()
        return ret['builds'][0]

    def async(self, handler=None):
        self.logger.debug("WKBotsFeederPlugin async")

        now = time.time()
        if now < self.lasttime + self.period:
            return  # Feeder is only updated each 'period' time
        self.lasttime = now

        res = []
        for builder_name, builder in self.settings["builders"].iteritems():
            self.logger.debug("WKBotsFeederPlugin async: Fetching %s ..." % builder_name)
            try:
                build = self.get_last_build(builder)
                if builder['last_buildjob'] >= build['number']:
                    continue
                failed = self.build_failed(build)
                builder.update({
                    'failed': failed,
                    'last_buildjob': int(build['number']),
                    'recovery': 'failed' in builder and builder['failed'] and not failed
                })

                if self.should_send_message(builder, failed):
                    self.logger.debug("WKBotsFeederPlugin: Should send message")
                    message = self.pretty_entry(builder)
                    self.send(message)
            except Exception as e:
                self.logger.error("WKBotsFeederPlugin got error in builder %s: %s" % (builder_name,e))


    def command(self, sender, room_id, body, handler):
        self.logger.debug("WKBotsFeederPlugin command")
        return

    def help(self, sender, room_id, handler):
        self.logger.debug("WKBotsFeederPlugin help")
        return

def selftest():
    print("selftest: " + os.path.basename(__file__))
    settings = {
        "name": "wk",
        "last_buildjob_url_schema": "https://build.webkit.org/#/builders/%d/builds/%d",
        "builds_url_schema": "https://build.webkit.org/api/v2/builders/%d/builds?complete=true&order=-number&limit=1",
        "only_failures": False,
        "rooms": ["0"],
        "builders": {
            "GTK-Linux-64-bit-Release-Ubuntu-LTS-Build": {
                "builderid": 68,
            },
        },
    }
    plugin = WKBotsFeederPlugin(utils.MockBot(), settings)

    test_async(plugin)
    test_can_fetch_last_build(plugin)

def test_async(plugin):
    print("test_async: ")
    logging.basicConfig(level = logging.DEBUG)
    plugin.lasttime = 0
    plugin.period = 0
    plugin.async()
    print("")
    print("Ok")

def test_can_fetch_last_build(plugin):
    puts("test_can_fetch_last_build: ")
    builder = plugin.settings['builders']["GTK-Linux-64-bit-Release-Ubuntu-LTS-Build"]
    build = plugin.get_last_build(builder)
    assert(build)
    print("Ok")

if __name__ == '__main__':
    selftest()
