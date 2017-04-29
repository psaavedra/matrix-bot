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

        self.client = MatrixClient(self.uri)
        self.token = self.client.login_with_password(username=self.username,
                                                     password=self.password)
        self.api = MatrixHttpApi(self.uri, token=self.token)

    def normalize_user_id(self, user_id):
        if not user_id.startswith("@"):
            user_id = "@" + user_id
            self.logger.debug("Adding missing '@' to the username: %s" % user_id)
        user_id = "%s:%s" % (user_id, self.domain)
        return user_id

    def do_command(self, action, room_id, body):
        ldap_settings = self.settings["ldap"]
        body_arg_list = body.split()[2:]
        for body_arg in body_arg_list:
            if body_arg.startswith("+"):
                group_name = body_arg[1:]
                self.send_message(room_id,
                             "Doing (%s) for group (%s)" % (action, group_name))
                groups_members = bot_ldap.get_ldap_group_members(ldap_settings)
                if group_name in groups_members.keys():
                    for group_member in groups_members[group_name]:
                        user_id = self.normalize_user_id(group_name)
                        self.call_api(action, 1, room_id, user_id)
            else:
                user_id = self.normalize_user_id(body_arg)
                self.call_api(action, 1, room_id, user_id)

    def call_api(self, action, max_attempts, *args):
        method = getattr(self.api, action)
        attempts = max_attempts
        while attempts:
            try:
                response = method(*args)
                self.logger.info("Call %s action with: %s" % (action, args))
                return response
            except MatrixRequestError, e:
                self.logger.error("Fail (%s/%s) in call %s action with: %s - %s" % (attempts, max_attempts, action, args, e))
                max_attempts -= 1

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
                if not silent:
                    self.send_message(room_id, "Mornings!")
            except MatrixRequestError, e:
                logger.error("Join action in room %s failed: %s" %
                             (room_id, e))
    
    def do_help(self, room_id, body):
        vars_ = self.settings["matrix"].copy()
        vars_["groups"] = ', '.join(self.settings["ldap"]["groups"])
        try:
            self.logger.debug("do_help")
            msg_help = '''Examples:
%(username)s: help
%(username)s: invite @user
%(username)s: invite +group
%(username)s: kick @user
%(username)s: kick +group


Available groups: %(groups)s
''' % vars_
            self.send_message(room_id, msg_help)
        except MatrixRequestError, e:
            self.logger.warning(e)

    def sync(self, timeout_ms=30000):
        response = self.api.sync(self.sync_token, timeout_ms)
        self.sync_token = response["next_batch"]
        self.logger.info("!!! sync_token: %s" % (self.sync_token))
        self.logger.debug("Sync response: %s" % (response))

        self.sync_invitations(response['rooms']['invite'])
        self.sync_joins(response['rooms']['join'])
        time.sleep(self.period)

    def sync_invitations(self, invite_events):
        for room_id, invite_state in invite_events.items():
            self.logger.info("+++ (invite) %s" % (room_id))
            for event in invite_state["invite_state"]["events"]:
                if event["type"] == 'm.room.member' and \
                        "membership" in event and \
                        event["membership"] == 'invite':
                    self.call_api("join_room", 1, room_id)

    def sync_joins(self, join_events):
        for room_id, sync_room in join_events.items():
            self.logger.info(">>> (join) %s" % (room_id))
            for event in sync_room["timeline"]["events"]:
                if event["type"] == 'm.room.message' and \
                        "content" in event and \
                        "msgtype" in event["content"] and \
                        event["content"]["msgtype"] == 'm.text':
                    body = event["content"]["body"]
                    if body.lower().strip().startswith("%s:" % self.username):
                        if self.is_command(body, "invite"):
                            self.do_command("invite_user", room_id, body)
                        elif self.is_command(body, "kick"):
                            self.do_command("kick_user", room_id, body)
                        elif self.is_command(body, "help"):
                            self.do_help(room_id, body)
                        else:
                            self.do_help(room_id, body)

