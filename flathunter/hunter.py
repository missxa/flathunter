"""Default Flathunter implementation for the command line"""
import logging
from itertools import chain

from flathunter.config import Config
from flathunter.filter import Filter
from flathunter.processor import ProcessorChain

from telegram import TelegramError
from telegram.ext import Updater, CallbackQueryHandler

class Hunter:
    """Hunter class - basic methods for crawling and processing / filtering exposes"""
    __log__ = logging.getLogger('flathunt')

    def __init__(self, config, id_watch):
        self.config = config
        if not isinstance(self.config, Config):
            raise Exception("Invalid config for hunter - should be a 'Config' object")
        self.id_watch = id_watch
        self.bot_token = self.config.get('telegram', dict()).get('bot_token', '')
        self.telegram_updater = Updater(token=self.bot_token, use_context=True)
        self.telegram_updater.start_polling()
        self.telegram_updater.dispatcher.add_error_handler(self.error)
        self.handlers = []

    def crawl_for_exposes(self, max_pages=None):
        """Trigger a new crawl of the configured URLs"""
        return chain(*[searcher.crawl(url, max_pages)
                       for searcher in self.config.searchers()
                       for url in self.config.get('urls', list())])

    def hunt_flats(self, max_pages=None):
        """Crawl, process and filter exposes"""
        filter_set = Filter.builder() \
                           .read_config(self.config) \
                           .filter_already_seen(self.id_watch) \
                           .build()

        processor_chain = ProcessorChain.builder(self.config) \
                                        .save_all_exposes(self.id_watch) \
                                        .apply_filter(filter_set) \
                                        .resolve_addresses() \
                                        .calculate_durations() \
                                        .send_telegram_messages(self.telegram_updater) \
                                        .build()

        result = []
        # We need to iterate over this list to force the evaluation of the pipeline
        for expose in processor_chain.process(self.crawl_for_exposes(max_pages)):
            self.__log__.info('New offer: %s', expose['title'])
            result.append(expose)

        cur_handler = processor_chain.get_telegram_handler()
        if cur_handler is not None:
            self.handlers.append(cur_handler)
            self.__log__.info("cleaned telegram handlers")
            if len(self.handlers) > 1:
                self.telegram_updater.dispatcher.remove_handler(self.handlers[0])
        return result

    def error(self, update, context):
        """
        Log Errors caused by Updates.
        """

        self.__log__.error(f'Update {update} caused error {context.error}')
        # raise context.error

