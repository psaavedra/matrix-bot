#!/usr/bin/env python3

import xmlrpc.client
from datetime import datetime, timedelta
from matrixbot import utils

class TracPlugin:
    def __init__(self, bot, settings):
        self.logger = utils.get_logger()
        self.name = "TracPlugin"
        self.bot = bot
        self.settings = settings
        self.logger.info("TracPlugin loaded (%(name)s)" % settings)
        self.timestamp = datetime.utcnow()
        self.server = xmlrpc.client.ServerProxy(
            '%(url_protocol)s://%(url_auth_user)s:%(url_auth_password)s@%(url_domain)s%(url_path)s/login/xmlrpc' % self.settings
        )

    def pretty_ticket(self, ticket):
        ticket[3]["ticket_id"] = ticket[0]
        url = '%(url_protocol)s://%(url_domain)s%(url_path)s' % self.settings
        ticket[3]["ticket_url"] = "%s/ticket/%s" % (url, ticket[0])
        res = """%(summary)s:
    * URL: %(ticket_url)s
    * [severity: %(severity)s] [owner: %(owner)s] [reporter: %(reporter)s] [status: %(status)s]""" % ticket[3]
        return res

    def dispatch(self, handler):
        self.logger.debug("TracPlugin dispatch")
        server = self.server

        d = self.timestamp
        self.timestamp = datetime.utcnow()
        res = []
        for t in server.ticket.getRecentChanges(d):
            ticket = server.ticket.get(t)
            changes = server.ticket.changeLog(t)
            if len(changes) == 0 and 'new' in self.settings['status']:  # No changes implies New ticket
                res.append(ticket)
            for c in changes:
                if (
                    c[0] > d and c[2] == 'status'
                    and c[4] in self.settings['status']
                ):
                    res.append(ticket)

        if len(res) == 0:
            return

        res = list(map(
            self.pretty_ticket,
            res
        ))
        message = "\n".join(res)
        for room_id in self.settings["rooms"]:
            room_id = self.bot.get_real_room_id(room_id)
            self.bot.send_notice(room_id, message)

    def command(self, sender, room_id, body, handler):
        self.logger.debug("TracPlugin command")
        plugin_name = self.settings["name"]

        # TODO: This should be a decorator
        if self.bot.only_local_domain and not self.bot.is_local_user_id(sender):
            self.logger.warning(
                "TracPlugin %s plugin is not allowed for external sender (%s)" % (plugin_name, sender)
            )
            return

        sender = sender.replace('@','')
        sender = sender.split(':')[0]
        command_list = body.split()[1:]
        if len(command_list) > 0 and command_list[0] == plugin_name: 
            if command_list[1] == "create": 
                summary = ' '.join(command_list[2:])
                self.logger.debug(
                    "TracPlugin command: %s(%s)" % (
                        "create", summary
                    )
                )
                self.server.ticket.create(
                    summary, 
                    "",
                    {"cc": sender},
                    True
                )

    def help(self, sender, room_id, handler):
        self.logger.debug("TracPlugin help")
        if self.bot.is_private_room(room_id, self.bot.get_user_id()):
            message = "%(name)s create This is the issue summary\n" % self.settings
        else:
            message = "%(username)s: %(name)s create This is the issue summary\n" % self.settings
        handler(room_id, message)
