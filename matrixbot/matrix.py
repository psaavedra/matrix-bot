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

        self.logger = utils.create_logger(settings)

        self.settings = settings
        self.period = settings["DEFAULT"]["period"]
        self.uri = settings["matrix"]["uri"]
        self.username = settings["matrix"]["username"]
        self.password = settings["matrix"]["password"]
        self.room_ids = settings["matrix"]["rooms"]
        self.domain = self.settings["matrix"]["domain"]

        self.client = MatrixClient(self.uri)
        self.token = self.client.login_with_password(username=self.username,
                                                     password=self.password)
        self.api = MatrixHttpApi(self.uri, token=self.token)

    def do_invite(self, room_id, body):
        ldap_settings = self.settings["ldap"]
        arg_list = body.split()[2:]
        for arg in arg_list:
            if arg.startswith("+"):
                group_name = arg[1:]
                logger.info("Sending invitation for group (%s)" % (group_name))
                send_message(room_id,
                             "Sending invitation for group (%s)" % (group_name))
                groups_members = bot_ldap.get_ldap_group_members(ldap_settings,
                                                        logger=self.logger)
                if group_name in groups_members.keys():
                    for group_member in groups_members[group_name]:
                        self.do_invite_user(group_member, room_id)
            else:
                self.do_invite_user(arg, room_id)

    def do_invite_user(self, user_id, room_id):
        if not user_id.startswith("@"):
            user_id = "@" + user_id
            self.logger.debug("Adding missing '@' to the username: %s" % user_id)
        user_id = "%s:%s" % (user_id, domain)
        try:
            self.api.invite_user(room_id, user_id)
            self.logger.info("do_invite (%s, %s)" % (room_id, user_id))
            self.send_message(room_id, "Invitation to room %s sent to %s" % (room_id, user_id))
        except MatrixRequestError, e:
            self.logger.warning(e)
            self.send_message(room_id, "Oops!!!: %s" % (e))

    def send_message(self, room_id, message, max_attempts=3, wait=60):
        attempts = max_attempts
        while attempts:
            try:
                response = self.api.send_message(room_id, message)
                return response
            except MatrixRequestError, e:
                logger.error("Error sending message (%s/%s) to room %s: %s (%s)" %
                             (attempts, max_attempts, room_id, message, e))
                max_attempts -= 1
    
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
                    # room.send_text("Mornings!")
                    pass
            except MatrixRequestError, e:
                logger.error("Error joining in the room %s: %s" %
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

Available groups: %(groups)s
''' % vars_
            self.send_message(room_id, msg_help)
        except MatrixRequestError, e:
            self.logger.warning(e)

    def sync(self, timeout_ms=30000):
        username = self.username.lower()

        response = self.api.sync(self.sync_token, timeout_ms)
        self.sync_token = response["next_batch"]
        self.logger.info("+++ sync_token: %s" % (self.sync_token))

        for room_id, sync_room in response['rooms']['join'].items():
            self.logger.info(">>> %s: %s" % (room_id, sync_room))
            # pp = pprint.PrettyPrinter(indent=4)
            # pp.pprint(sync_room)
            for event in sync_room["timeline"]["events"]:
                if event["type"] == 'm.room.message' and \
                        "content" in event and \
                        "msgtype" in event["content"] and \
                        event["content"]["msgtype"] == 'm.text':
                    body = event["content"]["body"]
                    if body.lower().strip().startswith("%s:" % username):
                        if self.is_command(body, "invite"):
                            self.do_invite(room_id, body)
                        elif self.is_command(body, "help"):
                            self.do_help(room_id, body)
                        else:
                            self.do_help(room_id, body)

        time.sleep(self.period)
