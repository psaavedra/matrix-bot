import time

from matrixbot import utils

class EchoPlugin:
    def __init__(self, bot, settings):
        self.name = "EchoPlugin"
        self.bot = bot
        self.logger = utils.get_logger()
        self.logger.info(settings)
        self.settings = settings
        self.period  = self.settings.get('period', 3)  # 3 seconds.
        self.last_time = time.time()
        self.broadcast(self.compose_message())

    def compose_message(self):
        username = self.settings['username']
        message = self.settings['message']
        return "EchoPlugin (" + username + "): " + message

    def broadcast(self, message):
        for each in self.settings['rooms']:
            room_id = self.bot.get_real_room_id(each)
            self.send(room_id, message)

    def send(self, room_id, message):
        self.logger.info(message)
        self.bot.send_html(room_id, message, msgtype="m.notice")

    def async(self, handler):
        self.logger.debug("Echo::async")

        # Exit if now is within time interval.
        now = time.time()
        if now < self.last_time + self.period:
            return
        self.last_time = now

        # Do action.
        self.logger.debug('EchoPlugin::Send message')
        self.broadcast(self.compose_message())
