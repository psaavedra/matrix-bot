#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Author: Pablo Saavedra
# Maintainer: Pablo Saavedra
# Contact: saavedra.pablo at gmail.com

import getconf
import sys
import logging
import copy


def get_default_settings():
    settings = {}
    settings["DEFAULT"] = {
        "loglevel": 10,
        "logfile": "/dev/stdout",
        "period": 30,
    }
    settings["matrix"] = {
        "uri": "http://localhost:8000",
        "username": "username",
        "password": "password",
        "domain": "matrix.org",
        "rooms": []
    }
    settings["ldap"] = {
        "server": "ldap://ldap.local",
        "base": "ou=People,dc=example,dc=com",
        "groups": [],
        "groups_id": "cn",
        "groups_filter": "(objectClass=posixGroup)",
        "groups_base": "ou=Group,dc=example,dc=com",
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
    return settings


def debug_conffile(settings, logger):
    for s in settings.keys():
        for k in settings[s].keys():
            key = "%s.%s" % (s, k)
            value = settings[s][k]
            logger.debug("Configuration setting - %s: %s" % (key, value))

def setup(conffile, settings):
    try:
        reload(sys)
        # Forcing UTF-8 in the enviroment:
        sys.setdefaultencoding('utf-8')
        # http://stackoverflow.com/questions/3828723/why-we-need-sys-setdefaultencodingutf-8-in-a-py-scrip
    except Exception:
        pass
    execfile(conffile)

def create_logger(settings):
    hdlr = logging.FileHandler(settings["DEFAULT"]["logfile"])
    hdlr.setFormatter(logging.Formatter('%(levelname)s %(asctime)s %(message)s'))
    logger = logging.getLogger('matrixbot')
    logger.addHandler(hdlr)
    logger.setLevel(settings["DEFAULT"]["loglevel"])
    logger.debug("Default encoding: %s" % sys.getdefaultencoding())
    debug_conffile(settings, logger)
    return logger


def get_logger():
    return logging.getLogger('matrixbot')


def get_command_alias(command, settings):
    prefix = command.strip().split()[0]
    command = " ".join(command.strip().split()[1:])
    if command in settings["aliases"].keys():
        return prefix + " " + settings["aliases"][command]
    return prefix + " " + command


def get_aliases(settings):
    res = copy.copy(settings["aliases"])
    return res
