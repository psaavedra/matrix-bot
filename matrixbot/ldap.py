# -*- coding:utf-8 -*-
#
# Author: Pablo Saavedra
# Maintainer: Pablo Saavedra
# Contact: saavedra.pablo at gmail.com

import ldap

def get_ldap_group_members(ldap_settings, groups=None, logger=None):
    ldap_server = ldap_settings["server"]
    ldap_base = ldap_settings["base"]
    ldap_groups = ldap_settings["groups"]
    get_uid = lambda x: x[1]["uid"][0]
    if groups:
        ldap_groups = filter(lambda x: x in groups, ldap_groups)
    res = {}
    try:
        conn = ldap.initialize(ldap_server)
        for g in ldap_groups:
            g_ldap_filter = ldap_settings[g]
            logger.debug("Searching members for %s: %s" % (g, g_ldap_filter))
            items = conn.search_s(ldap_base, ldap.SCOPE_SUBTREE,
                                  attrlist=['uid'],
                                  filterstr=g_ldap_filter)
            members = map(get_uid, items)
            res[g] = members
    except Exception, e:
        if logger:
            logger.error("Error getting groups from LDAP: %s" % e)
    return res



