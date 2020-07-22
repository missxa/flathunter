"""Functions and classes related to sending Telegram messages"""
import urllib.request
import urllib.parse
import urllib.error
import logging
import requests

from telegram import TelegramError
from telegram.ext import Updater, CallbackQueryHandler
from telegram.files.inputmedia import InputMediaPhoto
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from flathunter.abstract_processor import Processor
from flathunter.idmaintainer import IdMaintainer

import ipdb

class SenderTelegram(Processor):
    """Expose processor that sends Telegram messages"""
    __log__ = logging.getLogger('flathunt')

    def __init__(self, config, receivers=None):
        self.config = config
        self.bot_token = self.config.get('telegram', dict()).get('bot_token', '')
        if receivers is None:
            self.receiver_ids = self.config.get('telegram', dict()).get('receiver_ids', list())
        else:
            self.receiver_ids = receivers

        self.id_watch = IdMaintainer('%s/processed_ids.db' % config.database_location())

        self.updater = Updater(token=self.bot_token, use_context=True)
        self.updater.dispatcher.add_handler(CallbackQueryHandler(self.button))
        self.updater.dispatcher.add_error_handler(self.error)
        self.updater.start_polling()
        self.bot = self.updater.bot

    def button(self, update, context):
        query = update.callback_query
        chat_id = update.callback_query.message.chat_id
        # ipdb.set_trace()
        try:
            # ipdb.set_trace()    
            expose = self.id_watch.get_expose_by_id(query.data)
            media = expose['photos']
            if len(media) > 2:
                if len(media) < 10:
                    tg_media = [InputMediaPhoto(m) for m in media]
                    self.bot.send_media_group(chat_id=chat_id, media=tg_media, 
                                            reply_to_message_id=query.message.message_id)
                else:
                    n_batch = len(media)//10
                    for b in range(n_batch):
                        tg_media = [InputMediaPhoto(m) for m in media[b*10:(b+1)*10]]
                        self.bot.send_media_group(chat_id=chat_id, media=tg_media,
                                                reply_to_message_id=query.message.message_id)
                self.bot.answer_callback_query(update.callback_query.id, text='')
            else:
                self.bot.answer_callback_query(update.callback_query.id, text='Sorry, I dont have pics for this one')
            
        # else:
        except Exception as e:
            self.__log__.error(e)
            self.bot.answer_callback_query(update.callback_query.id, text='Sorry, I dont have pics for this one')

    def error(self, update, context):
        """
        Log Errors caused by Updates.
        """
        self.__log__.error(f'Update {update} caused error {context.error}')


    def process_expose(self, expose):
        """Send a message to a user describing the expose"""
        message = self.config.get('message', "").format(
            title=expose['title'] + '\n',
            rooms=expose['rooms'],
            size=expose['size'],
            price=expose['price'],
            url=expose['url'],
            address=expose['address'],
            image=expose['image'],
            total_price=expose['total_price'],
            free_from=expose['free_from'],
            durations="" if 'durations' not in expose else expose['durations']).strip()
        self.send_msg(message, expose)
        return expose

    def send_msg(self, message, expose=None):
        """Send messages to each of the receivers in receiver_ids"""
        if self.receiver_ids is None:
            return
        for chat_id in self.receiver_ids:
            url = 'https://api.telegram.org/bot%s/sendMessage?chat_id=%i&text=%s'
            # text = urllib.parse.quote_plus(message.encode('utf-8'))
            self.__log__.debug(('token:', self.bot_token))
            self.__log__.debug(('chatid:', chat_id))
            # self.__log__.debug(('text', text))
            reply_markup = None
            if expose is not None and len(expose['photos']) > 0:
                pics_button = InlineKeyboardButton("show pics", callback_data=expose['id'])
                keyboard = [[pics_button]]
                reply_markup = InlineKeyboardMarkup(keyboard,one_time_keyboard=True)
                self.bot.send_photo(chat_id=chat_id, photo=expose['photos'][0],
                                    reply_markup=reply_markup, caption=message)

            else:
                self.bot.send_message(chat_id=chat_id, text=message,
                                    disable_web_page_preview=False)
            
            # if media is not None and len(media) > 1:
            #     n_batch = len(media)//10
            #     for b in range(n_batch):
            #         tg_media = [InputMediaPhoto(m) for m in media[b*10:(b+1)*10]]
            #         self.bot.send_media_group(chat_id=chat_id, media=tg_media)
            # qry = url % (self.bot_token, chat_id, text)
            # self.__log__.debug("Retrieving URL %s", qry)
            # resp = requests.get(qry)
            # self.__log__.debug("Got response (%i): %s", resp.status_code, resp.content)
            # data = resp.json()

            # # handle error
            # if resp.status_code != 200:
            #     status_code = resp.status_code
            #     self.__log__.error("When sending bot message, we got status %i with message: %s",
            #                        status_code, data)
