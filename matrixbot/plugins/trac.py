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
        self.logger.debug("TracPlugin command")
        return ""

    def help(self, handler):
        self.logger.debug("TracPlugin help")
        return ""
