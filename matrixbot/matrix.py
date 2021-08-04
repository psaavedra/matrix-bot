# -*- coding:utf-8 -*-
#
# Author: Pablo Saavedra
# Maintainer: Pablo Saavedra
# Contact: saavedra.pablo at gmail.com

from matrix_client.api import MatrixRequestError
from matrix_client.client import MatrixClient
from matrix_client.room import Room

import asyncio
# import pprint
import time
import traceback
import re

import email
import smtplib
import ssl
from email.mime.text import MIMEText

from . import utils
from . import ldap as bot_ldap

EXTRA_DEBUG = 5

class MatrixBotError(Exception):
    pass

class MatrixBot():
    def __init__(self, settings):
        self.sync_token = None

        self.logger = utils.get_logger()
        self.cache = utils.create_cache(settings)
        self.cache_timeout = int(settings["memcached"]["timeout"])

        self.settings = settings
        self.period = settings["DEFAULT"]["period"]

        matrix = settings.get("matrix", {})
        self.uri = matrix["uri"]
        self.username = matrix["username"].lower()
        self.password = matrix["password"]
        self.room_ids = matrix["rooms"]
        self.domain = matrix["domain"]
        self.only_local_domain = matrix["only_local_domain"]
        self.super_users = matrix.get("super_users", [])

        self.commands_enable = settings\
            .get("commands", {})\
            .get("enable", True)

        self.subscriptions_room_ids = settings.get("subscriptions", {}).keys()
        self.revokations_rooms_ids = settings.get("revokations", {}).keys()
        self.allowed_join_rooms_ids = [x for x in list(settings["allowed-join"].keys()) if x != 'default']
        self.default_allowed_join_rooms = settings\
            .get("allowed-join", {})\
            .get("default", "")

        self.enable_list_rooms_commands = settings\
            .get("commands", {})\
            .get("list-rooms", {})\
            .get("enable", False)
        self.visible_subset_list_rooms_commands = settings\
            .get("commands", {})\
            .get("list-rooms", {})\
            .get("visible_subset", [])

        self.client = MatrixClient(self.uri)
        self.token = self.client.login_with_password(username=self.username,
                                                     password=self.password)

        self.rooms = []
        self.room_aliases = {}
        self.plugins = []
        for plugin in list(settings['plugins'].values()):
            mod = __import__(plugin['module'], fromlist=[plugin['class']])
            klass = getattr(mod, plugin['class'])
            self.plugins.append(klass(self, plugin['settings']))

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
                if group_name in list(groups_members.keys()):
                    list([_add_or_remove_user(users, x, append) for x in groups_members[group_name]])
            else:
                _add_or_remove_user(users, item, append)

        selected_users = [x for x in users["in"] if x not in users["out"]]
        return selected_users

    def normalize_user_id(self, user_id):
        if not user_id.startswith("@"):
            user_id = "@" + user_id
            self.logger.debug("Adding missing '@' to the username: %s" % user_id)
        if user_id.count(":") == 0:
            user_id = "%s:%s" % (user_id, self.domain)
        return user_id

    def get_user_id(self, username=None, normalized=True):
        if not username:
            username = self.username
        normalized_username = self.normalize_user_id(username)
        if normalized:
            return normalized_username
        else:
            return normalized_username[1:].split(':')[0]

    def is_local_user_id(self, username):
        normalized_username = self.get_user_id(username, normalized=True)
        if normalized_username.split(':')[1] == self.domain:
            return True
        return False

    def get_real_room_id(self, room_id):
        if room_id.startswith("#"):
            room_id = self.client.api.get_room_id(room_id)
        return room_id

    def get_room_members(self, room_id):
        key = "get_room_members-%s" % room_id
        res = self.cache.get(key)
        if res:
            self.logger.debug("get_room_members (cached): %s" % (key))
            return res
        res = self.call_api("get_room_members", 2, room_id)
        self.cache.set(key, res, self.cache_timeout)
        self.logger.debug("get_room_members (non cached): %s" % (key))
        return res

    def refresh_room_members(self, room_id):
        key = "get_room_members-%s" % room_id
        self.cache.delete(key)
        self.logger.debug("refresh_room_members: %s" % (key))

    def is_room_member(self, room_id, user_id):
        try:
            r = Room(self.client, room_id)
            return user_id in list(r.get_joined_members().keys())
        except Exception as e:
            return False
        return False

    def check_send_mail_allowed(self, send_to):
        def _(f, if_, else_):
            if f == 'all':
                return if_
            if isinstance(f, list):
                for i in f:
                    if '@' in i:  # assumes is an explicit mailbox
                        if send_to == i:
                            return if_
                    else:  # assumes is a domain
                        if send_to.split('@')[1] == i:
                            return if_
            if not f:  # None
                return else_
            return else_

        s = self.settings.get('mail', {})
        p = s.get('to_policy', 'deny')
        f = s.get('to_policy_filter', 'all')

        if p == 'allow':
            return _(f, True, False)
        if p == 'deny':
            return _(f, False, True)
        return False

    def send_mail(self, message, send_to):
        s = self.settings.get('mail', {})
        if not self.check_send_mail_allowed(send_to):
            raise MatrixBotError("Outgoing mails to %s are not allowed" % send_to)
        mail = MIMEText(message)
        mail['Subject'] = s.get('subject')
        mail['From'] = s.get('from')
        mail['To'] = send_to
        mail['Reply-To'] = send_to
        mail['Date'] = email.utils.formatdate()
        self.logger.debug("Send mail to %s from %s" % (s.get('to'), s.get('from')))
        self.logger.debug("Send mail content: %s" % message)
        if self.settings['mail']['ssl']:
            smtp = smtplib.SMTP_SSL(s.get('host'), s.get('port'),
                                  context=ssl.create_default_context())
            smtp.login(s.get('username'), s.get('password'))
        else:
            smtp = smtplib.SMTP(self.settings['mail']['host'],
                                self.settings['mail']['port'])
        smtp.send_message(mail)

    def do_command(self, action, sender, room_id, command, attempts=3):
        """
        action  : The action to execute
        sender  : The sender of the message
        room_id : The actual Id of the room where the message was sent. It is
                  used as default target_room_id if there is not other room id as
                  paramenter in the command
        command : Format: user: action [dryrun] #room:domain @user:domain [!group:domain] ...
        attempts: Maximum number of retries to execute the action
        """
        if sender:
            sender = self.normalize_user_id(sender)

        # TODO: This should be a decorator
        if self.only_local_domain and not self.is_local_user_id(sender):
            self.logger.warning(
                "do_command is not allowed for external sender (%s)" % sender
            )
            return

        # command: bot invite #room:domain @user:domain ...
        #          [0] [1]    [2]          [3:]
        command_arg_list = command.split()[2:]
        dry_mode = False
        if (
            len(command_arg_list) > 0 and
            command_arg_list[0] == "dryrun"
        ):
            dry_mode = True
            command_arg_list = command_arg_list[1:]
        target_room_id = room_id
        if (
            len(command_arg_list) > 0 and
            (
                command_arg_list[0].startswith('!') or
                command_arg_list[0].startswith('#')
            )
        ):
            target_room_id = self.get_real_room_id(command_arg_list[0])
            command_arg_list = command_arg_list[1:]

        if sender and not self.is_room_member(target_room_id, sender):
            msg = "%s is not allowed for not members (%s) of the room (%s)" % (action, sender, target_room_id)
            self.logger.warning(msg)
            self.send_private_message(sender,
                                      msg,
                                      room_id)
            return

        room_members = set(map(lambda x: x['user_id'],
                               self.get_room_members(target_room_id)["chunk"]))

        if action == "invite_user":
            selected_users = set(self._get_selected_users(command_arg_list)).difference(room_members)
            self.refresh_room_members(target_room_id)
        if action == "kick_user":
            selected_users = set(self._get_selected_users(command_arg_list)).intersection(room_members)
            self.refresh_room_members(target_room_id)

        if dry_mode and sender:
            self.send_private_message(
                sender,
                "Simulated '%s' action in room '%s' over: %s" % (
                    action,
                    target_room_id,
                    utils.list_to_str(selected_users)),
                room_id)
        else:
            if len(selected_users) > 0:
                for user in selected_users:
                    self.logger.info(
                        " do_command (%s,%s,%s,dry_mode=%s)" % (
                            action,
                            target_room_id,
                            user,
                            dry_mode))
                    res = self.call_api(action, attempts, target_room_id, user)
                if sender:
                    msg = '''Action '%s' in room %s over %s''' % (
                        action,
                        target_room_id,
                        utils.list_to_str(selected_users)
                    )
                    self.send_private_message(sender, msg, room_id)
            elif sender:
                self.send_private_message(sender,
                                          "No users found",
                                          room_id)

    def invite_subscriptions(self):
        for room_id in self.subscriptions_room_ids:
            command = self.username.lower() + ": invite " + self.settings["subscriptions"][room_id]
            self.do_command("invite_user", None, room_id, command, attempts=1)

    def kick_revokations(self):
        for room_id in self.revokations_rooms_ids:
            command = self.username.lower() + ": kick " + self.settings["revokations"][room_id]
            self.do_command("kick_user", None, room_id, command, attempts=1)

    def call_api(self, action, max_attempts, *args):
        method = getattr(self.client.api, action)
        attempts = max_attempts
        while attempts > 0:
            try:
                response = method(*args)
                self.logger.info("Call %s action with: %s" % (action, args))
                self.logger.debug("Call response: %s" % (response))
                return response
            except MatrixRequestError as e:
                self.logger.debug("Fail (%s/%s) in call %s action with: %s - %s" % (attempts, max_attempts, action, args, e))
                attempts -= 1
                time.sleep(5)
        return None

    def send_emote(self, room_id, message):
        return self.call_api("send_emote", 3,
                             room_id, message)

    def send_html(self, room_id, message, msgtype="m.text"):
        content = {
            "body": re.sub('<[^<]+?>', '', message),
            "msgtype": msgtype,
            "format": "org.matrix.custom.html",
            "formatted_body": message
        }
        return self.client.api.send_message_event(
            room_id, "m.room.message",
            content
        )

    def send_message(self, room_id, message):
        return self.call_api("send_message", 3,
                             room_id, message)

    def send_notice(self, room_id, message):
        return self.call_api("send_notice", 3,
                             room_id, message)

    def send_private_message(self, user_id, message, room_id=None):
        # Just add a first case: if the channel is 1-to-1 then reply
        # directly using this channel
        if room_id and self.is_private_room(room_id, self.get_user_id(), user_id):
            return self.call_api("send_message", 3, room_id, message)

        user_room_id = self.get_private_room_with(user_id)
        if room_id and room_id != user_room_id:
            self.call_api(
                "send_message",
                3,
                room_id,
                "Replying command as PM to %s" % user_id)
        return self.send_message(room_id, message)

    async def loop(self):
        loop_pool = []
        loop_max = 10
        await self.sync(ignore=True)  # Ignoring pending old messages
        while True:
            try:
                loop_pool.append(asyncio.ensure_future(self.sync()))
                await asyncio.sleep(self.period)
                if loop_pool == loop_max:
                    while len(loop_pool) > 0:
                        task = loop_pool.pop()
                        try:
                            await task
                        except asyncio.CancelledError as e:
                            self.logger.error("matrixbot: Sync cancelled: %s" % e)
            except Exception as e:
                self.logger.error("matrixbot: Unexpected error: %s" % e)
                self.logger.error("matrixbot: Unexpected error: %s" % traceback.print_exc())

    def leave_empty_rooms(self):
        self.logger.debug("leave_empty_rooms")
        rooms = self.get_rooms()
        for room_id in rooms:
            res = self.get_room_members(room_id)
            try:
                members_list = res.get('chunk', [])
            except Exception as e:
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
                        except Exception as e:
                            self.logger.warning("Some kind of error during the forget_room action: %s" % (e))

    def get_private_room_with(self, user_id):
        self.leave_empty_rooms()
        self.logger.debug("get_private_room_with")

        rooms = self.get_rooms()
        for room_id in rooms:
            if self.is_private_room(room_id, self.get_user_id(), user_id):
                return room_id

        # Not room found then ...
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

    def is_private_room(self, room_id, user1_id, user2_id=None):
        me = False  # me is true if the user1_id is in the room
        him = False  # him is true if the user2_id join or is already

        res = self.get_room_members(room_id)
        try:
            members_list = res.get('chunk', [])
        except Exception as e:
            members_list = []
            self.logger.debug(
                "Error getting the members of the room %s: %s" % (room_id, e))

        if len(members_list) != 2:
            self.logger.debug("Room %s is not a 1-to-1 room" % room_id)
            return False  # We are looking for a 1-to-1 room

        if not user2_id:
            self.logger.debug("Room %s is a 1-to-1 with the user %s" % (room_id, user1_id))
            return True  # I just check if the room is 1-to-1 for user1_id


        # TODO: This code must be cleaned up
        for r in res.get('chunk', []):
            if (
                'content' in r
                and 'state_key' in r
                and 'membership' in r['content']
            ):
                if r['state_key'] == user2_id and r['content']['membership'] == 'invite':
                    him = True
                if r['state_key'] == user2_id and r['content']['membership'] == 'join':
                    him = True
                if r['state_key'] == user1_id and r['content']['membership'] == 'join':
                    me = True
                if me and him:
                    self.logger.debug(
                        "A 1-to-1 room for %s and %s found: %s" % (
                            user2_id,
                            user1_id,
                            room_id))
                    return True

        for r in res.get('chunk', []):
            if (
                'prev_content' in r
                and 'state_key' in r['prev_content']
                and 'membership' in r['prev_content']
            ):
                p = r['prev_content']
                if p['state_key'] == user2_id and p['membership'] == 'invite':
                    him = True
                if p['state_key'] == user2_id and p['membership'] == 'join':
                    him = True
                if p['state_key'] == user1_id and p['membership'] == 'join':
                    me = True
                if me and him:
                    self.logger.debug(
                        "A 1-to-1 room for %s and %s found: %s" % (
                            user2_id,
                            user1_id,
                            room_id))
                    return True
        return False

    def is_explicit_call(self, body):
        if (
            body.lower().strip().startswith("%s:" % self.username.lower())
            or body.lower().strip().startswith("%s " % self.username.lower())
        ):
            return True
        res = False
        self.logger.debug("is_explicit_call: %s" % res)
        return res

    def is_command(self, body, command="command_name"):
        res = False
        if self.is_explicit_call(body):
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
            except MatrixRequestError as e:
                self.logger.error("Join action in room %s failed: %s" %
                                  (room_id, e))

        new_subscriptions_room_ids = []
        for room_id in list(self.subscriptions_room_ids):
            try:
                old_room_id = room_id
                room_id = room_id + ':' + self.domain
                room = self.client.join_room(room_id)
                new_room_id = room.room_id  # Ensure we are using the actual id not the alias
                new_subscriptions_room_ids.append(new_room_id)
                self.settings["subscriptions"][new_room_id] = self.settings["subscriptions"][old_room_id]
            except MatrixRequestError as e:
                self.logger.error("Join action for subscribe users in room %s failed: %s" %
                                  (room_id, e))
        self.subscriptions_room_ids = new_subscriptions_room_ids

        new_revokations_room_ids = []
        for room_id in list(self.revokations_rooms_ids):
            try:
                old_room_id = room_id
                room_id = room_id + ':' + self.domain
                room = self.client.join_room(room_id)
                new_room_id = room.room_id  # Ensure we are using the actual id not the alias
                new_revokations_room_ids.append(new_room_id)
                self.settings["revokations"][new_room_id] = self.settings["revokations"][old_room_id]
            except MatrixRequestError as e:
                self.logger.error("Join action for revoke users in room %s failed: %s" %
                                  (room_id, e))
        self.revokations_rooms_ids = new_revokations_room_ids

    def do_join(self, sender, room_id, body):
        self.logger.debug("do_join")

        # TODO: This should be a decorator
        if self.only_local_domain and not self.is_local_user_id(sender):
            self.logger.warning(
                "do_join is not allowed for external sender (%s)" % sender
            )
            return

        body_arg_list = body.split()[2:]
        dry_mode = False
        msg_dry_mode = " (dryrun)" if dry_mode else ""

        if len(body_arg_list) > 0 and body_arg_list[0] == "dryrun":
            dry_mode = True
            body_arg_list = body.split()[3:]
        original_room_id = body_arg_list[0]
        join_room_id = body_arg_list[0]

        # If the user did not specify a domain, try to append our
        # domain to the room that they passed us.
        domain_suffix = ":%s" % self.domain
        if not ":" in join_room_id:
            join_room_id += domain_suffix

        if not join_room_id.endswith(domain_suffix):
            msg = '''Invalid room id (%s): Join is only for rooms in %s domain''' % (join_room_id, self.domain)
            self.send_private_message(sender, msg, room_id)
            return

        if not join_room_id.startswith("#"):
            msg = '''Invalid room id (%s): Join is only valid using room aliases''' % (join_room_id)
            self.send_private_message(sender, msg, room_id)
            return

        try:
            join_room_id = self.get_real_room_id(join_room_id)
        except Exception as e:
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
        except MatrixRequestError as e:
            self.logger.warning(e)

    def do_list_groups(self, sender, room_id):
        self.logger.debug("do_list_groups")
        # TODO: This should be a decorator
        if self.only_local_domain and not self.is_local_user_id(sender):
            self.logger.warning(
                "do_list_groups is not allowed for external sender (%s)" % sender
            )
            return

        groups = ', '.join(["+%s" % x for x in self.settings["ldap"]["groups"]])
        try:
            msg = "Groups: %s" % groups
            self.send_private_message(sender, msg, room_id)
        except MatrixRequestError as e:
            self.logger.warning(e)

    def do_list_rooms(self, sender, room_id):
        self.logger.debug("do_list_rooms")
        # TODO: This should be a decorator
        if self.only_local_domain and not self.is_local_user_id(sender):
            self.logger.warning(
                "do_list_rooms is not allowed for external sender (%s)" % sender
            )
            return
        is_super_user = sender in self.super_users
        msg = ""
        if is_super_user:
            msg = "[*] Your are a super-user"
            if self.enable_list_rooms_commands:
                msg = msg + ". Showing full list of rooms.\n\n"
            else:
                msg = msg + " but super-user support for this command is DISABLED.\n\n"
        msg = msg + "Room list:\n"
        rooms = self.get_rooms()
        rooms_msg_list = []
        for r in rooms:
            aliases = self.get_room_aliases(r)
            if len(aliases) < 1:
                self.logger.debug("Room %s hasn't got aliases. Skipping" % (r))
                continue  # We are looking for rooms with alias
            try:
                name = self.client.api.get_room_name(r)['name']
            except Exception as e:
                self.logger.debug("Error getting the room name %s: %s" % (r, e))
                name = "No named"
            if self.enable_list_rooms_commands:
                is_visible_room = False
                for alias in self.visible_subset_list_rooms_commands:
                    if alias in aliases:
                        is_visible_room = True
                        break
                if not is_visible_room and not is_super_user:
                    continue
            status = ""
            if self.enable_list_rooms_commands and is_super_user:
                if is_visible_room:
                    status = " [visible]"
                else:
                    status = " [hidden]"
            rooms_msg_list.append("* %s - %s%s" % (name, "".join(aliases), status))
        msg += "\n".join(sorted(rooms_msg_list))
        try:
            self.send_private_message(sender, msg, room_id)
        except MatrixRequestError as e:
            self.logger.warning(e)

    def do_list(self, sender, room_id, body):
        self.logger.debug("do_list")
        # TODO: This should be a decorator
        if self.only_local_domain and not self.is_local_user_id(sender):
            self.logger.warning(
                "do_list is not allowed for external sender (%s)" % sender
            )
            return

        body_arg_list = body.split()[2:]
        selected_users = self._get_selected_users(body_arg_list)
        msg_list = " ".join(
            [self.normalize_user_id(x) for x in selected_users]
        )
        try:
            self.send_private_message(sender, msg_list, room_id)
        except MatrixRequestError as e:
            self.logger.warning(e)

    def do_count(self, sender, room_id, body):
        # TODO: This should be a decorator
        if self.only_local_domain and not self.is_local_user_id(sender):
            self.logger.warning(
                "do_count is not allowed for external sender (%s)" % sender
            )
            return

        self.logger.debug("do_count")
        body_arg_list = body.split()[2:]
        selected_users = self._get_selected_users(body_arg_list)
        msg_list = "Count: %s" % len(selected_users)
        try:
            self.send_private_message(sender, msg_list, room_id)
        except MatrixRequestError as e:
            self.logger.warning(e)

    def do_help(self, sender, room_id, body, pm=False):
        vars_ = self.settings["matrix"].copy()
        if pm:
            vars_["prefix"] = ""
        else:
            vars_["prefix"] = "%(username)s: " % vars_

        vars_["aliases"] = "\n".join(["%s: " % vars_["username"] + "%s ==> %s" % x for x in list(utils.get_aliases(self.settings).items())])
        try:
            self.logger.debug("do_help")
            msg_help = '''Examples:
%(prefix)shelp
%(prefix)shelp extra
%(prefix)sjoin <room_id>
%(prefix)sinvite [dryrun] [<room_id>] (@user|+group) ... [ but (@user|+group) ]
%(prefix)skick [dryrun] [<room_id>] (@user|+group) ... [ but (@user|+group) ]
%(prefix)scount [ (@user|+group) ... [ but (@user|+group) ] ]
%(prefix)slist [ (@user|+group) ... [ but (@user|+group) ] ]
%(prefix)slist-rooms
%(prefix)slist-groups
%(prefix)sforward-to-email mailbox@example.domain (as reply for a message)
''' % vars_
            if body.find("extra") >= 0:
                msg_help += '''
Available command aliases:

%(aliases)s
''' % vars_

            # TODO: This should be a decorator ???
            if self.only_local_domain and not self.is_local_user_id(sender):
                self.logger.warning(
                    "do_help is not allowed for external sender (%s)" % sender
                )
            else:
                self.send_private_message(sender, msg_help, room_id)

            # get plugin help to plugins
            for plugin in self.plugins:
                plugin.help(
                    sender,
                    room_id,
                    lambda r,m: self.send_private_message(sender, m, None)
                )

        except MatrixRequestError as e:
            self.logger.warning(e)

    def do_forward_to_email(self, sender, room_id, body, in_reply_to=None):
        self.logger.debug("do_forward_to_email")
        # TODO: This should be a decorator
        if self.only_local_domain and not self.is_local_user_id(sender):
            self.logger.warning(
                "do_forward_to_email is not allowed for external sender (%s)" % sender
            )
            return

        if not in_reply_to:
            msg = "🙋‍♀️: The forward-to-email only works as reply of a previous message"
            try:
              self.send_private_message(sender, msg, room_id)
            except MatrixRequestError as e:
                self.logger.warning(e)
            return

        body_arg_list = body.split()[2:]
        send_to = ""
        if (len(body_arg_list) > 0):
            send_to = body_arg_list[0]

        if not send_to:
            msg = "🙋‍♀️: The forward-to-email command has to be completed with a mail destination"
            try:
              self.send_private_message(sender, msg, room_id)
            except MatrixRequestError as e:
                self.logger.warning(e)
            return
        messages = []
        replies = {}
        end = False
        token = self.sync_token
        max_iters = 10
        for i in range(max_iters):
            r = self.call_api("get_room_messages", 1, room_id, token, "b", 500)
            for c in r["chunk"]:
                command = self._get_command(room_id, c)
                if self.is_command(command, "forward-to-email"):
                    continue  # 'forward-to-email' are delivery skipped
                if c.get("type", "") == "m.room.message":
                    c_in_reply_to = utils.get_in_reply_to(c)
                    if c_in_reply_to:
                        if c_in_reply_to in replies:
                            replies[c_in_reply_to].append(c)
                        else:
                            replies[c_in_reply_to]= [c]
                    else:
                        messages.append(c)
                if c['event_id'] == in_reply_to:
                    end = True
                    break
            if end:
                break
            token = r["end"]

        content = ""
        for message in reversed(messages):
            content += utils.mail_format_event(message, replies)

        aliases = self.get_room_aliases(room_id)
        message = '''
Thread forwarded from %s,

- 8< ----------------------------------------------------------------

%s
- 8< ----------------------------------------------------------------

''' % (aliases if aliases else room_id, content)

        msg = "Messages forwarded to %s" % send_to

        try:
            self.send_mail(message, send_to)
        except MatrixBotError as e:
            msg = "🙋‍♀️: Messages can not be forwarded: %s" % (e)
            self.logger.error("matrixbot: error: %s" % e)
            traceback.print_exc()
        except Exception as e:
            msg = "🙋‍♀️: Messages can not be forwarded to %s: %s" % (send_to, e)
            self.logger.error("matrixbot: error: %s" % e)
            traceback.print_exc()

        try:
            self.send_message(room_id, msg)
        except MatrixRequestError as e:
            self.logger.warning(e)

    def _set_rooms(self, response_dict):
        new_room_list = []
        for rooms_types in list(response_dict['rooms'].keys()):
            for room_id in list(response_dict['rooms'][rooms_types].keys()):
                new_room_list.append(room_id)
                self._set_room_aliases(room_id)
        self.rooms = new_room_list

    def _set_room_aliases(self, room_id):
        room_dict_state = None
        try:
            aliases = []
            room_dict_state = self.client.api.get_room_state(room_id)
            for e in room_dict_state:
                if e['type'] == 'm.room.canonical_alias':
                    aliases = e['content']['alias']
            self.room_aliases[room_id] = aliases
        except Exception as e:
            self.logger.log(EXTRA_DEBUG, "Error getting aliases for %s: %s" % (room_id, e))
            self.logger.log(EXTRA_DEBUG, "Dict: %s" % (room_dict_state))

    def get_rooms(self):
        return self.rooms

    def get_room_aliases(self, room_id):
        return self.room_aliases[room_id] if room_id in self.room_aliases else []

    async def _dispatch(self, response):
        _tasks = []

        if not response:
            return

        async def _(plugin, callback):
            try:
                plugin.dispatch(callback)
            except Exception as e:
                self.logger.error(
                    "Error in plugin %s: %s" % (plugin.name, e)
                )

        for plugin in self.plugins:
            _tasks.append(asyncio.create_task(_(plugin, self.send_message)))
        _tasks.append(asyncio.ensure_future(
            self.sync_invitations(response['rooms']['invite'])))
        _tasks.append(asyncio.ensure_future(
            self.sync_joins(response['rooms']['join'])))
        for task in _tasks:
            await task

    async def sync(self, ignore=False, timeout_ms=30000):
        response = None
        try:
            response = self.client.api.sync(self.sync_token, timeout_ms, full_state=True)
            self._set_rooms(response)
            self.sync_token = response["next_batch"]
            self.logger.info("!!! sync_token: %s" % (self.sync_token))
            self.logger.log(EXTRA_DEBUG, "Sync response: %s" % (response))
        except Exception as e:
            self.logger.error("Error in sync: %s" % e)
        if not ignore:
            await self._dispatch(response)

    async def sync_invitations(self, invite_events):
        _tasks = []
        # TODO Clean code and also use only_local_domain setting
        for room_id, invite_state in list(invite_events.items()):
            self.logger.info("+++ (invite) %s" % (room_id))
            for event in invite_state["invite_state"]["events"]:
                if event["type"] == 'm.room.member' and \
                        "content" in event and \
                        "membership" in event["content"] and \
                        event["content"]["membership"] == 'invite' and \
                        "sender" in event and \
                        event["sender"].endswith(self.domain):
                    _tasks.append(asyncio.create_task(
                        self.call_api("join_room", 3, room_id)
                    ))
        for task in _tasks:
            await task


    async def sync_joins(self, join_events):
        _tasks = []
        for room_id, sync_room in list(join_events.items()):
            self.logger.debug(">>> (join) %s" % (room_id))
            for event in sync_room["timeline"]["events"]:
                _tasks.append(asyncio.ensure_future(
                    self._process_event(room_id, event)
                ))
        for task in _tasks:
            await task

    def _get_command(self, room_id, event):
        body = event["content"]["body"]
        if utils.is_reply(event):
            body = "\n\n".join(body.split("\n\n")[1:])

        is_pm = self.is_private_room(room_id, self.get_user_id())

        if is_pm and not self.is_explicit_call(body):
            body = "%s: " % self.username.lower() + body

        body = utils.get_command_alias(body, self.settings)
        return body

    async def _process_event(self, room_id, event):
        if not (
            event["type"] == 'm.room.message'
            and "content" in event
            and "msgtype" in event["content"]
            and event["content"]["msgtype"] == 'm.text'
        ):
            return

        if self.commands_enable:
            sender = event["sender"]
            is_pm = self.is_private_room(room_id, self.get_user_id())
            in_reply_to = utils.get_in_reply_to(event)
            command = self._get_command(room_id, event)

            if sender == self.get_user_id():
                return

            if not command.lower().strip().startswith("%s" % self.username):
                return
            if self.is_command(command, "invite"):
                self.do_command("invite_user", sender, room_id, command)
            elif self.is_command(command, "kick"):
                self.do_command("kick_user", sender, room_id, command)
            elif self.is_command(command, "join"):
                self.do_join(sender, room_id, command)
            elif self.is_command(command, "count"):
                self.do_count(sender, room_id, command)
            elif self.is_command(command, "list"):
                self.do_list(sender, room_id, command)
            elif self.is_command(command, "list-rooms"):
                self.do_list_rooms(sender, room_id)
            elif self.is_command(command, "list-groups"):
                self.do_list_groups(sender, room_id)
            elif self.is_command(command, "forward-to-email"):
                self.do_forward_to_email(sender, room_id, command, in_reply_to)
            elif self.is_command(command, "help"):
                self.do_help(sender, room_id, command, is_pm)
            elif len (command.split()[1:]) == 0 :
                self.do_help(sender, room_id, command, is_pm)

        # push to plugins
        for plugin in self.plugins:
            plugin.command(
                sender, room_id, command,
                self.send_message
            )
