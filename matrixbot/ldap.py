# -*- coding:utf-8 -*-
#
# Author: Pablo Saavedra
# Maintainer: Pablo Saavedra
# Contact: saavedra.pablo at gmail.com

from __future__ import absolute_import

import ldap as LDAP

from . import utils

def get_custom_ldap_group_members(ldap_settings, group_name):
    logger = utils.get_logger()
    ldap_server = ldap_settings["server"]
    ldap_base = ldap_settings["base"]
    get_uid = lambda x: x[1]["uid"][0]
    members = []
    try:
        conn = LDAP.initialize(ldap_server)
        g_ldap_filter = ldap_settings[group_name]
        logger.debug("Searching members for %s: %s" % (group_name, 
                                                       g_ldap_filter))
        items = conn.search_s(ldap_base, LDAP.SCOPE_SUBTREE,
                              attrlist=['uid'],
                              filterstr=g_ldap_filter)
        members = map(get_uid, items)
    except Exception, e:
        logger.error("Error getting custom group %s from LDAP: %s" %(group_name, e))
    return members


def get_ldap_group_members(ldap_settings, group_name):
    # base:dc=example,dc=com
    # filter:(&(objectClass=posixGroup)(cn={group_name}))
    logger = utils.get_logger()
    ldap_server = ldap_settings["server"]
    ldap_base = ldap_settings["groups_base"]
    ldap_filter = "(&%s(%s={group_name}))" % (ldap_settings["groups_filter"],ldap_settings["groups_id"])
    get_uid = lambda x: x.split(",")[0].split("=")[1]
    try:
        ad_filter = ldap_filter.replace('{group_name}', group_name)
        conn = LDAP.initialize(ldap_server)
        logger.debug("Searching members for %s: %s - %s - %s" % (group_name,
                                                                 ldap_server,
                                                                 ldap_base,
                                                                 ad_filter))
        res = conn.search_s(ldap_base, LDAP.SCOPE_SUBTREE, ad_filter)
    except Exception, e:
        logger.error("Error getting group from LDAP: %s" % e)

    return map(get_uid, res[0][1]['uniqueMember'])


def get_ldap_groups(ldap_settings):
    '''Returns the a list of found LDAP groups filtered with the groups list in
the settings
    '''
    # filter:(objectClass=posixGroup)
    # base:ou=Group,dc=example,dc=com
    logger = utils.get_logger()
    ldap_server = ldap_settings["server"]
    ldap_base = ldap_settings["groups_base"]
    ldap_filter = ldap_settings["groups_filter"]
    ldap_groups = ldap_settings["groups"]
    get_uid = lambda x: x[1]["cn"][0]
    try:
        conn = LDAP.initialize(ldap_server)
        logger.debug("Searching groups: %s - %s - %s" % (ldap_server, 
                                                         ldap_base, 
                                                         ldap_filter))
        res = conn.search_s(ldap_base, LDAP.SCOPE_SUBTREE, ldap_filter)
        return filter((lambda x: x in ldap_groups), map(get_uid, res))
    except Exception, e:
        logger.error("Error getting groups from LDAP: %s" % e)


def get_ldap_groups_members(ldap_settings):
    logger = utils.get_logger()
    ldap_groups = ldap_settings["groups"]
    groups = get_ldap_groups(ldap_settings)
    res = {}
    for g in groups:
        res[g] = get_ldap_group_members(ldap_settings, g)

    # pending groups to get members. filters for those groups are explicitelly
    # defined in the settings
    custom_groups = filter((lambda x: x not in groups), ldap_groups)
    logger.error("custom_groups: %s", custom_groups)
    for g in custom_groups:
        res[g] = get_custom_ldap_group_members(ldap_settings, g)
    return res


def get_groups(ldap_settings):
    return ldap_settings["groups"]
