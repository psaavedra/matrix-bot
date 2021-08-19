#!/usr/bin/env python3

import json
import os
import pytz
import re
import requests
import sys
import urllib.request, urllib.parse, urllib.error
import time

if os.path.dirname(__file__) == "matrixbot/plugins":
    sys.path.append(os.path.abspath("."))

from matrixbot import utils

pp, set_property = utils.pp, utils.set_property

class WKTestBotsFeederPlugin:
    def __init__(self, bot, settings):
        self.name = "WKTestBotsFeederPlugin"
        self.logger = utils.get_logger()
        self.bot = bot
        self.settings = settings
        self.logger.info("WKTestBotsFeederPlugin loaded (%(name)s)" % settings)
        for builder_name, builder in list(self.settings["builders"].items()):
            if 'builder_name' not in builder:
                builder['builder_name'] = builder_name
            builder['last_buildjob'] = -1
            set_property(self.settings, builder, "last_buildjob_url_schema")
            set_property(self.settings, builder, "builds_url_schema")
            set_property(self.settings, builder, "only_failures", default=True)
            set_property(self.settings, builder, "notify_recoveries", default=True)
            self.logger.info("WKTestBotsFeederPlugin loaded (%(name)s) builder: " % settings + json.dumps(builder, indent = 4))
        self.lasttime = time.time()
        self.period = self.settings.get('period', 60)

    def pretty_entry(self, builder, summary):
        url = self.last_build_url(builder)

        res = "%(builder_name)s " % builder
        res += "(<a href='%s'>" % url
        res += "%(last_buildjob)s </a>): " % builder

        if builder['recovery']:
            res += "<p>%s (%s)</p>" % (pp("Recovery", color="green", strong=True),
                                       pp(summary, color="green"))
        elif builder['failed']:
            res += "<p>%s (%s)</p>" % (pp("Exiting early", color="red", strong=True),
                                       pp(summary, color="red"))
        else:
            res += "<p>%s (%s)</p>" % (pp("Success", color="green", strong=True),
                                       pp(summary, color="green"))
        return res

    def last_build_url(self, builder):
        builderid = int(builder['builderid'])
        build_number = int(builder['last_buildjob'])
        return builder['last_buildjob_url_schema'] % (builderid, build_number)

    def send(self, message):
        for room_id in self.settings["rooms"]:
            room_id = self.bot.get_real_room_id(room_id)
            self.bot.send_html(room_id, message, msgtype="m.notice")

    def has_failed(self, build):
        return re.search('exiting early', build['state_string'], re.IGNORECASE) != None

    def was_exception(self, build):
        return re.search('exception', build['state_string'], re.IGNORECASE) != None

    def summary(self, build):
        return build['state_string']

    def dispatch(self):
        self.logger.debug("WKTestBotsFeederPlugin dispatch")
        now = time.time()
        if now < self.lasttime + self.period:
            return  # Feeder is only updated each 'period' time
        self.lasttime = now

        res = []
        for builder_name, builder in list(self.settings["builders"].items()):
            self.logger.debug("WKTestBotsFeederPlugin dispatch: Fetching %s ..." % builder_name)
            try:
                build = self.get_last_build(builder)
                if builder['last_buildjob'] >= int(build['number']):
                    continue

                failed = self.has_failed(build)
                builder.update({
                    'failed': failed,
                    'last_buildjob': int(build['number']),
                    'recovery': 'failed' in builder and builder['failed'] and not failed and not self.was_exception(build),
                })

                if self.should_send_message(builder, failed):
                    message = self.pretty_entry(builder, self.summary(build))
                    self.send(message)
            except Exception as e:
                self.logger.error("WKTestBotsFeederPlugin got error in builder %s: %s" % (builder_name,e))

    def should_send_message(self, builder, failed):
        return failed or (not builder['only_failures']) or (builder['notify_recoveries'] and builder['recovery'])

    def get_last_build(self, builder):
        url = builder['builds_url_schema'] % builder['builderid']
        ret = requests.get(url).json()
        return ret['builds'][0]

    def command(self, sender, room_id, body, handler):
        self.logger.debug("WKTestBotsFeederPlugin command")
        return

    def help(self, sender, room_id, handler):
        self.logger.debug("WKTestBotsFeederPlugin help")
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
            "GTK-Linux-64-bit-Debug-Tests": {
                "builderid": 63,
            },
        },
    }
    plugin = WKTestBotsFeederPlugin(utils.MockBot(), settings)

    test_dispatch(plugin)
    test_can_fetch_last_build(plugin)

def test_dispatch(plugin):
    print("test_dispatch: ")
    import logging
    logging.basicConfig(level = logging.DEBUG)
    plugin.lasttime = 0
    plugin.period = 0
    plugin.dispatch()
    print("")
    print("Ok")

def test_can_fetch_last_build(plugin):
    puts = sys.stdout.write
    puts("test_can_fetch_last_build: ")
    builder = plugin.settings['builders']["GTK-Linux-64-bit-Debug-Tests"]
    build = plugin.get_last_build(builder)
    assert(build)
    print("Ok")

if __name__ == '__main__':
    selftest()
