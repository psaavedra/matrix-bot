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
        self.allowed_join_rooms_ids = settings["allowed-join"]["rooms"]
        self.default_allowed_join_rooms = settings["allowed-join"]["default"]

        self.client = MatrixClient(self.uri)
        self.token = self.client.login_with_password(username=self.username,
                                                     password=self.password)
        self.api = MatrixHttpApi(self.uri, token=self.token)

        self.rooms = []
        self.room_aliases = {}

    def _get_selected_users(self, groups_users_list):
        def _add_or_remove_user(users, username, append):
            username = self.normalize_user_id(username)
            if append and username not in users["in"]:
                users["in"].append(username)
            if not append and username not in users["out"]:
                users["out"].append(username)

        ldap_settings = self.settings["ldap"]
        append = True
        users = {
            "in": [],
            "out": []
        }
        for item in groups_users_list:
            if item == ("but"):
                append = False
            elif item.startswith("+"):
                group_name = item[1:]
                groups_members = bot_ldap.get_ldap_groups_members(ldap_settings)
                if group_name in groups_members.keys():
                    map(
                        lambda x: _add_or_remove_user(users, x, append),
                        groups_members[group_name])
            else:
                _add_or_remove_user(users, item, append)

        selected_users = filter(
            lambda x: x not in users["out"],
            users["in"])
        return selected_users

    def get_user_id(self, username=None):
        if not username:
            username = self.username
        return "@%s:%s" % (username, self.domain)

    def normalize_user_id(self, user_id):
        if not user_id.startswith("@"):
            user_id = "@" + user_id
            self.logger.debug("Adding missing '@' to the username: %s" % user_id)
        if user_id.count(":") == 0:
            user_id = "%s:%s" % (user_id, self.domain)
        return user_id

    def get_real_room_id(self, room_id):
        if room_id.startswith("#"):
            room_id = self.api.get_room_id(room_id)
        return room_id

    def do_command(self, action, sender, room_id, body, attempts=3):
        body_arg_list = body.split()[2:]
        dry_mode = False
        if (
            len(body_arg_list) > 0 and
            body_arg_list[0] == "dryrun"
        ):
            dry_mode = True
            body_arg_list = body.split()[3:]
        target_room_id = room_id
        if (
            len(body_arg_list) > 0 and
            (
                body_arg_list[0].startswith('!') or
                body_arg_list[0].startswith('#')
            )
        ):
            target_room_id = self.get_real_room_id(body_arg_list[0])
            body_arg_list = body_arg_list[1:]

        selected_users = self._get_selected_users(body_arg_list)

        if dry_mode:
            self.send_private_message(
                sender,
                "Simulated '%s' action in room '%s' over: %s" % (
                    action,
                    target_room_id,
                    " ".join(selected_users)),
                room_id)
        else:
            if len(selected_users) > 0:
                for user in selected_users:
                    self.logger.info(
                        " do_command (%s,%s,%s,dry_mode=%s)" % (
                            action,
                            room_id,
                            user,
                            dry_mode))
                    self.call_api(action, attempts, target_room_id, user)
            else:
                self.send_private_message(sender,
                                          "No users found",
                                          room_id)

    def invite_subscriptions(self):
        for room_id in self.subscriptions_room_ids:
            sender_id = self.username
            body = "bender: invite " + self.settings["subscriptions"][room_id]
            self.do_command("invite_user", sender_id, room_id, body, attempts=1)

    def kick_revokations(self):
        for room_id in self.revokations_rooms_ids:
            sender_id = self.username
            body = "bender: kick " + self.settings["revokations"][room_id]
            self.do_command("kick_user", sender_id, room_id, body, attempts=1)

    def call_api(self, action, max_attempts, *args):
        method = getattr(self.api, action)
        attempts = max_attempts
        while attempts > 0:
            try:
                response = method(*args)
                self.logger.info("Call %s action with: %s" % (action, args))
                self.logger.debug("Call response: %s" % (response))
                return response
            except MatrixRequestError, e:
                self.logger.error("Fail (%s/%s) in call %s action with: %s - %s" % (attempts, max_attempts, action, args, e))
                attempts -= 1
                time.sleep(5)
        return str(e)

    def send_message(self, room_id, message):
        return self.call_api("send_message", 3,
                             room_id, message)

    def send_private_message(self, user_id, message, room_id=None):
        user_room_id = self.get_private_room_with(user_id)
        if room_id and room_id != user_room_id:
            self.call_api(
                "send_message",
                3,
                room_id,
                "Replying command as PM to %s" % user_id)
        return self.call_api("send_message", 3,
                             user_room_id, message)

    def leave_empty_rooms(self):
        self.logger.debug("leave_empty_rooms")
        rooms = self.get_rooms()
        for room_id in rooms:
            res = self.call_api("get_room_members", 1,
                                room_id)
            try:
                members_list = res.get('chunk', [])
            except Exception, e:
                members_list = []
                self.logger.debug("Error getting the list of members in room %s: %s" % (room_id, e))

            if len(members_list) > 2:
                continue  # We are looking for a 1-to-1 room

            for r in res.get('chunk', []):
                if 'user_id' in r and 'membership' in r:
                    if r['membership'] == 'leave':
                        self.call_api("kick_user", 1, room_id, self.get_user_id())
                        try:
                            self.call_api("forget_room", 1, room_id)
                        except Exception, e:
                            self.logger.warning("Some kind of error during the forget_room action: %s" % (e))
        return room_id

    def get_private_room_with(self, user_id):
        self.leave_empty_rooms()
        self.logger.debug("get_private_room_with")

        rooms = self.get_rooms()
        for room_id in rooms:
            if self.is_private_room(room_id, self.get_user_id(), user_id):
                return room_id

        # Not room found
        room_id = self.call_api("create_room", 3,
                                None, False,
                                [user_id])['room_id']
        self.call_api(
            "send_message",
            3,
            room_id,
            "Hi! Get info about how to interact with me typing: %s help" % self.username
        )
        return room_id

    def is_private_room(self, room_id, user1_id, user2_id):
        me = False  # me is true if the user1_id is in the room
        him = False  # him is true if the user2_id join or is already

        res = self.call_api("get_room_members", 3, room_id)
        try:
            members_list = res.get('chunk', [])
        except Exception, e:
            members_list = []
            self.logger.debug(
                "Error getting the members of the room %s: %s" % (room_id, e))

        if len(members_list) != 2:
            self.logger.debug("Room %s is not a 1-to-1 room" % room_id)
            return False  # We are looking for a 1-to-1 room

        for r in res.get('chunk', []):
            if 'state_key' in r and 'membership' in r:
                if r['state_key'] == user2_id and r['membership'] == 'invite':
                    him = True
                if r['state_key'] == user2_id and r['membership'] == 'join':
                    him = True
                if r['state_key'] == user1_id and r['membership'] == 'join':
                    me = True
                if me and him:
                    self.logger.debug(
                        "A 1-to-1 room for %s and %s found: %s" % (
                            user2_id,
                            user1_id,
                            room_id))
                    return True
        return False

    def is_command(self, body, command="command_name"):
        res = False
        if (
            body.lower().strip().startswith("%s:" % self.username.lower())
            or body.lower().strip().startswith("%s " % self.username.lower())
        ):
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
                self.settings["revokations"][new_room_id] = self.settings["revokations"][old_room_id]
            except MatrixRequestError, e:
                self.logger.error("Join action for revoke users in room %s failed: %s" %
                                  (room_id, e))
        self.revokations_rooms_ids = new_revokations_room_ids

    def do_join(self, sender, room_id, body):
        self.logger.debug("do_join")

        body_arg_list = body.split()[2:]
        dry_mode = False
        msg_dry_mode = " (dryrun)" if dry_mode else ""

        if len(body_arg_list) > 0 and body_arg_list[0] == "dryrun":
            dry_mode = True
            body_arg_list = body.split()[3:]
        original_room_id = body_arg_list[0]
        join_room_id = body_arg_list[0]

        if not join_room_id.endswith(":%s" % self.domain):
            msg = '''Invalid room id (%s): Join is only for rooms in %s domain''' % (join_room_id, self.domain)
            self.send_private_message(sender, msg, room_id)
            return

        if not join_room_id.startswith("#"):
            msg = '''Invalid room id (%s): Join is only valid using room aliases''' % (join_room_id)
            self.send_private_message(sender, msg, room_id)
            return

        try:
            join_room_id = self.get_real_room_id(join_room_id)
        except Exception, e:
            msg = '''Room not %s found: %s''' % (join_room_id, e)
            self.send_private_message(sender, msg, room_id)
            self.logger.warning(msg)
            return

        allowed_users = self.default_allowed_join_rooms
        original_room_name = original_room_id.split(":")[0]
        if (original_room_name in self.allowed_join_rooms_ids):
            allowed_users = self.settings["allowed-join"][original_room_name]

        selected_users = self._get_selected_users(allowed_users.split())

        self.logger.debug("Checking if %s is in %s" % (sender, selected_users))
        if sender not in selected_users:
            msg = '''User %s can't join in room %s''' % (sender, original_room_id) + msg_dry_mode
            self.send_private_message(sender, msg, room_id)
            return

        try:
            if not dry_mode:
                self.logger.info(
                    "do_join (%s,%s)" % (
                        join_room_id,
                        sender
                    )
                )
                res = self.call_api("invite_user", 3, join_room_id, sender)
                if type(res) == dict:
                    msg_ok = '''Invitation sent to user %s to join in %s%s''' % (
                        sender,
                        original_room_id,
                        msg_dry_mode)
                    self.send_private_message(sender, msg_ok, room_id)
                else:
                    msg_fail = '''Fail in invitation sent to user %s to join in %s%s: %s''' % (
                        sender,
                        original_room_id,
                        msg_dry_mode,
                        res)
                    self.send_private_message(sender, msg_fail, room_id)
        except MatrixRequestError, e:
            self.logger.warning(e)

    def do_list_groups(self, sender, room_id):
        self.logger.debug("do_list_groups")
        groups = ', '.join(map(
            lambda x: "+%s" % x,
            self.settings["ldap"]["groups"]
        ))
        try:
            msg = "Groups: %s" % groups
            self.send_private_message(sender, msg, room_id)
        except MatrixRequestError, e:
            self.logger.warning(e)

    def do_list_rooms(self, sender, room_id):
        self.logger.debug("do_list_rooms")
        msg = "Room list:\n"
        rooms = self.get_rooms()
        rooms_msg_list = []
        for r in rooms:
            aliases = self.get_room_aliases(r)
            if len(aliases) < 1:
                self.logger.debug("Room %s hasn't got aliases. Skipping" % (r))
                continue  # We are looking for rooms with alias
            try:
                name = self.api.get_room_name(r)['name']
            except Exception, e:
                self.logger.debug("Error getting the room name %s: %s" % (r, e))
                name = "No named"
            rooms_msg_list.append("* %s - %s" % (name, " ".join(aliases)))
        msg += "\n".join(sorted(rooms_msg_list))
        try:
            self.send_private_message(sender, msg, room_id)
        except MatrixRequestError, e:
            self.logger.warning(e)

    def do_list(self, sender, room_id, body):
        self.logger.debug("do_list")
        body_arg_list = body.split()[2:]
        selected_users = self._get_selected_users(body_arg_list)
        msg_list = " ".join(
            map(lambda x: self.normalize_user_id(x), selected_users)
        )
        try:
            self.send_private_message(sender, msg_list, room_id)
        except MatrixRequestError, e:
            self.logger.warning(e)

    def do_count(self, sender, room_id, body):
        self.logger.debug("do_count")
        body_arg_list = body.split()[2:]
        selected_users = self._get_selected_users(body_arg_list)
        msg_list = "Count: %s" % len(selected_users)
        try:
            self.send_private_message(sender, msg_list, room_id)
        except MatrixRequestError, e:
            self.logger.warning(e)

    def do_help(self, sender, room_id, body):
        vars_ = self.settings["matrix"].copy()
        vars_["aliases"] = "\n".join(map(lambda x: "%s: " % vars_["username"] + "%s ==> %s" % x,
                                     utils.get_aliases(self.settings).items()))
        try:
            self.logger.debug("do_help")
            msg_help = '''Examples:
%(username)s: help
%(username)s: help extra
%(username)s: join <room_id>
%(username)s: invite [dryrun] [<room_id>] (@user|+group) ... [ but (@user|+group) ]
%(username)s: kick [dryrun] [<room_id>] (@user|+group) ... [ but (@user|+group) ]
%(username)s: count [ (@user|+group) ... [ but (@user|+group) ] ]
%(username)s: list [ (@user|+group) ... [ but (@user|+group) ] ]
%(username)s: list-rooms
%(username)s: list-groups
''' % vars_
            if body.find("extra") >= 0:
                msg_help += '''
Available command aliases:

%(aliases)s
''' % vars_
            self.send_private_message(sender, msg_help, room_id)
        except MatrixRequestError, e:
            self.logger.warning(e)

    def _set_rooms(self, response_dict):
        new_room_list = []
        for rooms_types in response_dict['rooms'].keys():
            for room_id in response_dict['rooms'][rooms_types].keys():
                new_room_list.append(room_id)
                self._set_room_aliases(room_id, response_dict['rooms'][rooms_types][room_id])
        self.rooms = new_room_list

    def _set_room_aliases(self, room_id, room_dict):
        try:
            aliases = []
            for e in room_dict['state']['events']:
                if e['type'] == 'm.room.aliases':
                    aliases = e['content']['aliases']
            self.room_aliases[room_id] = aliases
        except Exception, e:
            self.logger.debug("Error getting aliases for %s: %s" % (room_id, e))
            self.logger.debug("Dict: %s" % (room_dict))

    def get_rooms(self):
        return self.rooms

    def get_room_aliases(self, room_id):
        return self.room_aliases[room_id] if room_id in self.room_aliases else []

    def sync(self, ignore=False, timeout_ms=30000):
        response = self.api.sync(self.sync_token, timeout_ms, full_state='true')
        self._set_rooms(response)
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
            self.logger.debug(">>> (join) %s" % (room_id))
            for event in sync_room["timeline"]["events"]:
                self._process_event(room_id, event)

    def _process_event(self, room_id, event):
        if not (
            event["type"] == 'm.room.message'
            and "content" in event
            and "msgtype" in event["content"]
            and event["content"]["msgtype"] == 'm.text'
        ):
            return

        sender = event["sender"]
        body = event["content"]["body"]
        body = utils.get_command_alias(body, self.settings)
        if not body.lower().strip().startswith("%s" % self.username):
            return
        if self.is_command(body, "invite"):
            self.do_command("invite_user", sender, room_id, body)
        elif self.is_command(body, "kick"):
            self.do_command("kick_user", sender, room_id, body)
        elif self.is_command(body, "join"):
            self.do_join(sender, room_id, body)
        elif self.is_command(body, "count"):
            self.do_count(sender, room_id, body)
        elif self.is_command(body, "list"):
            self.do_list(sender, room_id, body)
        elif self.is_command(body, "list-rooms"):
            self.do_list_rooms(sender, room_id)
        elif self.is_command(body, "list-groups"):
            self.do_list_groups(sender, room_id)
        elif self.is_command(body, "help"):
            self.do_help(sender, room_id, body)
        else:
            self.do_help(sender, room_id, body)
