# -*- coding:utf-8 -*-
#
# Author: Pablo Saavedra
# Maintainer: Pablo Saavedra
# Contact: saavedra.pablo at gmail.com

from matrix_client.api import MatrixHttpApi, MatrixRequestError
from matrix_client.client import MatrixClient

# import pprint
import time

from . import utils
from . import ldap as bot_ldap


class MatrixBot():
    def __init__(self, settings):
        self.sync_token = None

        self.logger = utils.get_logger()

        self.settings = settings
        self.period = settings["DEFAULT"]["period"]
        self.uri = settings["matrix"]["uri"]
        self.username = settings["matrix"]["username"].lower()
        self.password = settings["matrix"]["password"]
        self.room_ids = settings["matrix"]["rooms"]
        self.domain = self.settings["matrix"]["domain"]

        self.subscriptions_room_ids = settings["subscriptions"]["rooms"]
        self.revokations_rooms_ids = settings["revokations"]["rooms"]

        self.client = MatrixClient(self.uri)
        self.token = self.client.login_with_password(username=self.username,
                                                     password=self.password)
        self.api = MatrixHttpApi(self.uri, token=self.token)

    def normalize_user_id(self, user_id):
        if not user_id.startswith("@"):
            user_id = "@" + user_id
            self.logger.debug("Adding missing '@' to the username: %s" % user_id)
        if user_id.count(":") == 0:
            user_id = "%s:%s" % (user_id, self.domain)
        return user_id

    def do_command(self, action, room_id, body, attempts=3):
        def add_or_remove_user(users, username, append):
            username = self.normalize_user_id(username)
            if append and username not in users["in"]:
                users["in"].append(username)
            if not append and username not in users["out"]:
                users["out"].append(username)

        ldap_settings = self.settings["ldap"]
        body_arg_list = body.split()[2:]
        dry_mode = False
        if len(body_arg_list) > 0 and body_arg_list[0] == "dryrun":
            dry_mode = True
            body_arg_list = body.split()[3:]
        append = True
        users = {
            "in": [],
            "out": []
        }
        for body_arg in body_arg_list:
            if body_arg == ("but"):
                append = False
            elif body_arg.startswith("+"):
                group_name = body_arg[1:]
                groups_members = bot_ldap.get_ldap_groups_members(ldap_settings)
                if group_name in groups_members.keys():
                    for group_member in groups_members[group_name]:
                        add_or_remove_user(users, group_member, append)
            else:
                add_or_remove_user(users, body_arg, append)

        selected_users = filter(lambda x: x not in users["out"], users["in"])
        if dry_mode:
            self.send_message(room_id,
                              "Simulated '%s' action over: %s" % (action,
                                                                  " ".join(selected_users)))
        else:
            if len(selected_users) > 0:
                for user in selected_users:
                    self.logger.debug(" do_command (%s,%s,%s,dry_mode=%s)" % (action, room_id,
                                                                              user, dry_mode))
                    self.call_api(action, attempts, room_id, user)
            else:
                self.send_message(room_id, "No users found")

    def invite_subscriptions(self):
        for room_id in self.subscriptions_room_ids:
            body = "bender: invite " + self.settings["subscriptions"][room_id]
            self.do_command("invite_user", room_id, body, attempts=1)

    def kick_revokations(self):
        for room_id in self.revokations_rooms_ids:
            body = "bender: kick " + self.settings["revokations"][room_id]
            self.do_command("kick_user", room_id, body, attempts=1)

    def call_api(self, action, max_attempts, *args):
        method = getattr(self.api, action)
        attempts = max_attempts
        while attempts > 0:
            try:
                response = method(*args)
                self.logger.info("Call %s action with: %s" % (action, args))
                return response
            except MatrixRequestError, e:
                self.logger.error("Fail (%s/%s) in call %s action with: %s - %s" % (attempts, max_attempts, action, args, e))
                attempts -= 1
                time.sleep(5)

    def send_message(self, room_id, message):
        return self.call_api("send_message", 3,
                             room_id, message)

    def is_command(self, body, command="command_name"):
        res = False
        if body.lower().strip().startswith("%s:" % self.username.lower()):
            command_list = body.split()[1:]
            if len(command_list) == 0:
                if command == "help":
                    res = True
            else:
                if command_list[0] == command:
                    res = True
        self.logger.debug("is_%s: %s" % (command, res))
        return res

    def join_rooms(self, silent=True):
        for room_id in self.room_ids:
            try:
                room = self.client.join_room(room_id)
                room_id = room.room_id  # Ensure we are using the actual id not the alias
                if not silent:
                    self.send_message(room_id, "Mornings!")
            except MatrixRequestError, e:
                self.logger.error("Join action in room %s failed: %s" %
                                  (room_id, e))

        new_subscriptions_room_ids = []
        for room_id in self.subscriptions_room_ids:
            try:
                old_room_id = room_id
                room_id = room_id + ':' + self.domain
                room = self.client.join_room(room_id)
                new_room_id = room.room_id  # Ensure we are using the actual id not the alias
                new_subscriptions_room_ids.append(new_room_id)
                if not silent:
                    self.send_message(new_room_id, "Mornings!")
                self.settings["subscriptions"][new_room_id] = self.settings["subscriptions"][old_room_id]
            except MatrixRequestError, e:
                self.logger.error("Join action for subscribe users in room %s failed: %s" %
                                  (room_id, e))
        self.subscriptions_room_ids = new_subscriptions_room_ids

        new_revokations_room_ids = []
        for room_id in self.revokations_rooms_ids:
            try:
                old_room_id = room_id
                room_id = room_id + ':' + self.domain
                room = self.client.join_room(room_id)
                new_room_id = room.room_id  # Ensure we are using the actual id not the alias
                new_revokations_room_ids.append(new_room_id)
                if not silent:
                    self.send_message(new_room_id, "Mornings!")
                self.settings["revokations"][new_room_id] = self.settings["revokations"][old_room_id]
            except MatrixRequestError, e:
                self.logger.error("Join action for revoke users in room %s failed: %s" %
                                  (room_id, e))
        self.revokations_rooms_ids = new_revokations_room_ids

    def do_list(self, room_id, body):
        self.logger.debug("do_list")
        ldap_settings = self.settings["ldap"]
        body_arg_list = body.split()[2:]
        msg_list = ""

        if len(body_arg_list) == 0:
            msg_list = "groups:"
            groups = bot_ldap.get_groups(ldap_settings)
            for g in groups:
                msg_list += " %s" % g
            try:
                self.send_message(room_id, msg_list)
            except MatrixRequestError, e:
                self.logger.warning(e)
            return

        groups_members = bot_ldap.get_ldap_groups_members(ldap_settings)
        self.logger.error(groups_members)
        for body_arg in body_arg_list:
            if body_arg.startswith("+"):
                group_name = body_arg[1:]
                if group_name in groups_members.keys():
                    msg_list = "group %s members:" % group_name
                    for group_member in groups_members[group_name]:
                        user_id = self.normalize_user_id(group_member)
                        msg_list += " %s" % user_id
                else:
                    msg_list = "group %s not found" % group_name
            else:
                user_id = self.normalize_user_id(body_arg)
                msg_list = "user: %s" % (user_id)
            try:
                self.send_message(room_id, msg_list)
            except MatrixRequestError, e:
                self.logger.warning(e)

    def do_help(self, room_id, body):
        vars_ = self.settings["matrix"].copy()
        vars_["groups"] = ', '.join(self.settings["ldap"]["groups"])
        vars_["aliases"] = "\n".join(map(lambda x: "%s: " % vars_["username"] + "%s ==> %s" % x,
                                     utils.get_aliases(self.settings).items()))
        try:
            self.logger.debug("do_help")
            msg_help = '''Examples:
%(username)s: help
%(username)s: invite  [dryrun] (@user|+group) ... [ but (@user|+group) ]
%(username)s: kick    [dryrun] (@user|+group) ... [ but (@user|+group) ]
%(username)s: list    [+group]

Available command aliases:

%(aliases)s

Available groups: %(groups)s
''' % vars_
            self.send_message(room_id, msg_help)
        except MatrixRequestError, e:
            self.logger.warning(e)

    def sync(self, ignore=False, timeout_ms=30000):
        response = self.api.sync(self.sync_token, timeout_ms)
        self.sync_token = response["next_batch"]
        self.logger.info("!!! sync_token: %s" % (self.sync_token))
        self.logger.debug("Sync response: %s" % (response))
        if not ignore:
            self.sync_invitations(response['rooms']['invite'])
            self.sync_joins(response['rooms']['join'])
        time.sleep(self.period)

    def sync_invitations(self, invite_events):
        for room_id, invite_state in invite_events.items():
            self.logger.info("+++ (invite) %s" % (room_id))
            for event in invite_state["invite_state"]["events"]:
                if event["type"] == 'm.room.member' and \
                        "membership" in event and \
                        event["membership"] == 'invite' and \
                        "sender" in event and \
                        event["sender"].endswith(self.domain):
                    self.call_api("join_room", 3, room_id)

    def sync_joins(self, join_events):
        for room_id, sync_room in join_events.items():
            self.logger.info(">>> (join) %s" % (room_id))
            for event in sync_room["timeline"]["events"]:
                if event["type"] == 'm.room.message' and \
                        "content" in event and \
                        "msgtype" in event["content"] and \
                        event["content"]["msgtype"] == 'm.text':
                    body = event["content"]["body"]
                    body = utils.get_command_alias(body, self.settings)
                    self.logger.error(body)
                    if body.lower().strip().startswith("%s:" % self.username):
                        if self.is_command(body, "invite"):
                            self.do_command("invite_user", room_id, body)
                        elif self.is_command(body, "kick"):
                            self.do_command("kick_user", room_id, body)
                        elif self.is_command(body, "list"):
                            self.do_list(room_id, body)
                        elif self.is_command(body, "help"):
                            self.do_help(room_id, body)
                        else:
                            self.do_help(room_id, body)
