import json
import logging
import os
import pytz
import requests
import sys
import urllib.request, urllib.parse, urllib.error
import time

if os.path.dirname(__file__) == "matrixbot/plugins":
    sys.path.append(os.path.abspath("."))

from matrixbot import utils

pp, puts, set_property = utils.pp, utils.puts, utils.set_property

class WKBotsFeederPlugin:
    def __init__(self, bot, settings):
        self.name = "WKBotsFeederPlugin"
        self.logger = utils.get_logger()
        self.bot = bot
        self.load(settings)

    def load(self, settings):
        self.settings = settings
        self.logger.info("WKBotsFeederPlugin loaded (%(name)s)" % settings)
        for builder_name, builder in list(self.settings["builders"].items()):
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

    def pretty_entry(self, builder):
        url = self.last_build_url(builder)

        res = "%(builder_name)s " % builder
        res += "(<a href='%s'>" % url
        res += "%(last_buildjob)s </a>): " % builder

        if builder['recovery']:
            res += pp("recovery", color="green", strong="")
        elif builder['failed']:
            res += pp("failed", color="red", strong="")
        else:
            res += pp("success", color="green", strong="")
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
        if "mute" in builder:
            return False
        return failed or (not builder['only_failures']) or (builder['notify_recoveries'] and builder['recovery'])

    def failed(self, build, value = "build successful"):
        return not self.succeeded(build, value)

    def succeeded(self, build, value = "build successful"):
        return 'state_string' in build and build['state_string'] == value

    def get_step(self, builder, build, stepname):
        builderid = int(builder['builderid'])
        buildNumber = int(build['number'])
        url = "https://build.webkit.org/api/v2/builders/%d/builds/%d/steps?name=%s" % (builderid, buildNumber, stepname)
        ret = requests.get(url).json()
        return ret['steps'][0]

    def get_last_build(self, builder):
        url = builder['builds_url_schema'] % builder['builderid']
        ret = requests.get(url).json()
        return ret['builds'][0]

    def dispatch(self, handler=None):
        self.logger.debug("WKBotsFeederPlugin dispatch")
        now = time.time()
        if now < self.lasttime + self.period:
            return  # Feeder is only updated each 'period' time
        self.lasttime = now

        res = []
        for builder_name, builder in list(self.settings["builders"].items()):
            self.logger.debug("WKBotsFeederPlugin dispatch: Fetching %s ..." % builder_name)
            try:
                build = self.get_last_build(builder)
                if builder['last_buildjob'] >= build['number']:
                    continue
                if 'target_step' in builder:
                    target_step = builder['target_step']
                    step = self.get_step(builder, build, target_step['name'])
                    failed = self.failed(step, target_step['text'])
                else:
                    failed = self.failed(build)
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

    def command(self, sender, room_id, body, handler = None):
        self.logger.debug("WKBotsFeederPlugin command: %s" % body)
        if len(body) == 0:
            return
        command = body.split()
        if command[0] != self.settings["name"]:
            return
        if len(command) > 1 and command[1].lower() == "mute":
            self.command_mute(sender, room_id, command[2:], handler)
        else:
            self.bot.send_html(room_id, "<p>Unknown command: %s</p>" % body)

    def command_mute(self, sender, room_id, command, handler):
        # Command: mute <builder-name> [ON|OFF].
        if len(command) == 0:
            self.help(sender, room_id, handler)
            return
        builders = self.settings["builders"]
        builderName = command[0]
        if builderName not in builders.keys():
            self.help(sender, room_id, handler)
            return
        value = (command[1] if command[1:] else "on").lower()
        if value not in ["on", "off"]:
            self.help(sender, room_id, handler)
            return
        if value == "on":
            builders[builderName]["mute"] = True
        else:
            builders[builderName].pop("mute")
        self.bot.send_html(room_id, "<p>Builder '%s' was set to mute %s</p>" % (builderName, value))

    def help(self, sender, room_id, handler):
        if not handler:
            return
        self.logger.debug("WKBotsFeederPlugin help")
        message = "mute <builder-name> [ON|OFF]"
        handler(room_id, message)

def selftest():
    print("selftest: " + os.path.basename(__file__))

    def webkitBuilderSettings():
        return {
            "name": "WKBotsFeederPlugin",
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
    def jsCoreBuilderSettings():
        ret = webkitBuilderSettings()
        ret["builders"] = {
            "JSCOnly-Linux-MIPS32el-Release": {
                "builderid": 31,
                "target_step": {
                    "name": "compile-webkit",
                    "text": "compiled"
                }
            }
        }
        return ret

    plugin = WKBotsFeederPlugin(utils.MockBot(), webkitBuilderSettings())

    test_dispatch(plugin)
    test_can_fetch_last_build(plugin)

    plugin.load(jsCoreBuilderSettings())
    test_dispatch(plugin)

    plugin.load(webkitBuilderSettings())
    test_mute_command(plugin)

def test_dispatch(plugin):
    print("test_dispatch: ")
    logging.basicConfig(level = logging.DEBUG)
    plugin.lasttime = 0
    plugin.period = 0
    plugin.dispatch()
    print("")
    print("Ok")

def test_can_fetch_last_build(plugin):
    puts("test_can_fetch_last_build: ")
    builder = plugin.settings['builders']["GTK-Linux-64-bit-Release-Ubuntu-LTS-Build"]
    build = plugin.get_last_build(builder)
    assert(build)
    print("Ok")

def test_mute_command(plugin):
    puts("test_mute_command: ")
    logging.basicConfig(level = logging.DEBUG)

    builder = plugin.settings['builders']["GTK-Linux-64-bit-Release-Ubuntu-LTS-Build"]
    sender = "user"
    room_id = plugin.settings["rooms"][0]

    # mute <builder-name>.
    body = "WKBotsFeederPlugin mute GTK-Linux-64-bit-Release-Ubuntu-LTS-Build"
    plugin.command(sender, room_id, body)
    assert(plugin.settings['builders']["GTK-Linux-64-bit-Release-Ubuntu-LTS-Build"]["mute"])
    print("")

    # mute <builder-name> off.
    body = "WKBotsFeederPlugin mute GTK-Linux-64-bit-Release-Ubuntu-LTS-Build off"
    plugin.command(sender, room_id, body)
    assert("mute" not in plugin.settings['builders']["GTK-Linux-64-bit-Release-Ubuntu-LTS-Build"])
    print("")

    # mute <builder-name>.
    body = "WKBotsFeederPlugin mute GTK-Linux-64-bit-Release-Ubuntu-LTS-Build on"
    plugin.command(sender, room_id, body)
    assert(plugin.settings['builders']["GTK-Linux-64-bit-Release-Ubuntu-LTS-Build"]["mute"])
    print("")

    print("Ok")

if __name__ == '__main__':
    selftest()
