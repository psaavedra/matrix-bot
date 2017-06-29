from matrixbot import utils

class BroadcastPlugin:
    def __init__(self, bot, settings):
        self.logger = utils.get_logger()
        self.bot = bot
        self.settings = settings
        self.logger.info("BroadcastPlugin loaded (%(name)s)" % settings)

    def async(self, handler):
        return

    def command(self, sender, room_id, body, handler):
        self.logger.debug("BroadcastPlugin command")
        plugin_name = self.settings["name"]

        command_list = body.split()[1:]
        
        if len(command_list) > 0 and command_list[0] == plugin_name: 
            if sender not in self.settings["users"]:
                self.logger.warning("User %s not autorized to use BroadcastPlugin" % self)
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
        if sender in self.settings["users"]:
            if self.bot.is_private_room(room_id, self.bot.get_user_id()):
                message = "%(name)s Announcement to be sent\n" % self.settings
            else:
                message = "%(username)s: %(name)s Announcement to be sent\n" % self.settings
            handler(room_id, message)

