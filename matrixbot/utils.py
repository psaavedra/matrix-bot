#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# Author: Pablo Saavedra
# Maintainer: Pablo Saavedra
# Contact: saavedra.pablo at gmail.com

import sys
import logging
import copy
import memcache
import imp

from datetime import datetime, timedelta
from dateutil import parser

puts = sys.stdout.write

def get_default_settings():
    settings = {}
    settings["DEFAULT"] = {
        "loglevel": 10,
        "logfile": "/dev/stdout",
        "period": 30,
    }
    settings["memcached"] = {
        "ip": "127.0.0.1",
        "port": 11211,
        "timeout": 300,
    }
    settings["matrix"] = {
        "uri": "http://localhost:8000",
        "username": "username",
        "password": "password",
        "domain": "matrix.org",
        "rooms": [],
        "only_local_domain": False,
        "super_users": [],
    }
    settings["ldap"] = {
        "server": "ldap://ldap.local",
        "base": "ou=People,dc=example,dc=com",
        "groups": [],
        "groups_id": "cn",
        "groups_filter": "(objectClass=posixGroup)",
        "groups_base": "ou=Group,dc=example,dc=com",
        "users_aliases": {},
    }
    settings["aliases"] = {
    }
    settings["subscriptions"] = {
    }
    settings["revokations"] = {
    }
    settings["allowed-join"] = {
        "default": ""
    }
    settings["plugins"] = {}
    settings["commands"] = {
        "enable": True,
        "list-rooms": {
            "enable": False,
            "visible_subset": [],
        },
    }
    return settings


def debug_conffile(settings, logger):
    for s in list(settings.keys()):
        for k in list(settings[s].keys()):
            key = "%s.%s" % (s, k)
            value = settings[s][k]
            logger.debug("Configuration setting - %s: %s" % (key, value))


def setup(conffile, settings):
    try:
        imp.reload(sys)
        # Forcing UTF-8 in the enviroment:
        sys.setdefaultencoding('utf-8')
        # http://stackoverflow.com/questions/3828723/why-we-need-sys-setdefaultencodingutf-8-in-a-py-scrip
    except Exception:
        pass
    exec(compile(open(conffile).read(), conffile, 'exec'))


def create_cache(settings):
    cache = memcache.Client(['%(ip)s:%(port)s' % settings["memcached"]], debug=0)
    return cache

def create_logger(settings):
    logfile = settings["DEFAULT"]["logfile"]
    if (logfile == "/dev/stdout"):
        hdlr = logging.StreamHandler(sys.stdout)
    elif (logfile == "/dev/stderr"):
        hdlr = logging.StreamHandler(sys.stderr)
    else:
        hdlr = logging.FileHandler(logfile)
    hdlr.setFormatter(logging.Formatter('%(levelname)s %(asctime)s %(message)s'))
    logger = logging.getLogger('matrixbot')
    logger.addHandler(hdlr)
    logger.setLevel(settings["DEFAULT"]["loglevel"])
    logger.debug("Default encoding: %s" % sys.getdefaultencoding())
    debug_conffile(settings, logger)
    return logger


def get_logger():
    return logging.getLogger('matrixbot')


def get_command_alias(message, settings):
    prefix = message.strip().split()[0]
    command = " ".join(message.strip().split()[1:])
    if command in list(settings["aliases"].keys()):
        return prefix + " " + settings["aliases"][command]
    return message


def get_aliases(settings):
    res = copy.copy(settings["aliases"])
    return res


def set_property(settings, builder, setting, default=None):
    if setting in builder:
        return
    if setting in settings:
        builder[setting] = settings[setting]
    else:
        builder[setting] = default


def utcnow():
    now = datetime.utcnow()
    return now.replace(tzinfo=pytz.utc)


def pp(text, **kwargs):
   ret="{content}"
   for key in kwargs:
      if key == "color":
         ret = ret.format(content="<font color='{color}'>{{content}}</font>".format(color=kwargs['color']))
      else:
         ret = ret.format(content="<{tag}>{{content}}</{tag}>".format(tag=key))
   return ret.format(content=text)


class MockBot:
    def __init__(self):
        pass

    def get_real_room_id(self, room_id):
        return room_id or 0

    def send_html(self, room_id, message, **kwargs):
        puts("Room #{}: {}".format(room_id, message))
