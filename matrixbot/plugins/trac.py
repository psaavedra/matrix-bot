import xmlrpclib
from datetime import datetime, timedelta
from matrixbot import utils

class TracPlugin:
    def __init__(self, settings):
        self.logger = utils.get_logger()
        self.settings = settings
        self.logger.info("TracPlugin loaded")
        self.timestamp = datetime.utcnow()
        self.server = xmlrpclib.ServerProxy(
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

    def async(self, handler):
        self.logger.debug("TracPlugin async")
        server = self.server
        multicall = xmlrpclib.MultiCall(server)

        d = self.timestamp
        self.timestamp = datetime.utcnow()
        res = []
        for t in server.ticket.getRecentChanges(d):
            # self.logger.info(t)
            ticket = server.ticket.get(t)
            changes = server.ticket.changeLog(t)
            if len(changes) == 0 and 'new' in self.settings['status']:  # No changes implies New ticket
                res.append(ticket)
            for c in changes:
                # self.logger.info(c)
                if (
                    c[0] > d and c[2] == 'status'
                    and c[4] in self.settings['status']
                ):
                    res.append(ticket)

        if len(res) == 0:
            return

        res = map(
            self.pretty_ticket,
            res
        )
        message = "\n".join(res)
        for room_id in self.settings["rooms"]:
            handler(room_id, message)

    def command(self, sender, room_id, body, handler):
        self.logger.warning("TracPlugin command")
        self.logger.warning(body)
        plugin_name = self.settings["name"]
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
                )

    def help(self, sender, room_id, handler):
        self.logger.debug("TracPlugin help")
        if room_id in self.settings["rooms"]:
            res = []
            res.append("%(username)s: %(name)s create Issue summary\n" % self.settings)
            message = "\n".join(res)
            handler(room_id, message)


