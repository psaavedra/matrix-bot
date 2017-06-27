from datetime import datetime, timedelta
from matrixbot import utils

class BroadcastPlugin:
    def __init__(self, bot, settings):
        self.logger = utils.get_logger()
        self.bot = bot
        self.settings = settings
        self.logger.info("BroadcastPlugin loaded")

    def async(self, handler):
        return

    def command(self, sender, room_id, body, handler):
        self.logger.debug("BroadcastPlugin command")
        plugin_name = self.settings["name"]

        command_list = body.split()[1:]
        
        if len(command_list) > 0 and command_list[0] == plugin_name: 
            if sender not in self.settings["users"]:
                self.logger.debug("User %s not autorized to use BroadcastPlugin" % self)
                return
            announcement = body[body.find(plugin_name) + len(plugin_name) + 1:]
            html = "<h3>%s</h3> <pre>%s</pre>" % ('Announcement:', announcement)
            for room_id in self.settings["rooms"]:
                room_id = self.bot.get_real_room_id(room_id)
                self.logger.debug(
                    "BroadcastPlugin announcement in %s: %s" % (
                        room_id, announcement
                    )
                )
                self.bot.send_html(room_id,html)

    def help(self, sender, room_id, handler):
        self.logger.debug("BroadcastPlugin help")
        if room_id in self.settings["rooms"]:
            res = []
            res.append("%(username)s: %(name)s Announcement\n" % self.settings)
            message = "\n".join(res)
            handler(room_id, message)
