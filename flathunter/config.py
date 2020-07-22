"""Wrap configuration options as an object"""
import os
import logging
import yaml

from flathunter.crawl_ebaykleinanzeigen import CrawlEbayKleinanzeigen
from flathunter.crawl_immobilienscout import CrawlImmobilienscout
from flathunter.crawl_wggesucht import CrawlWgGesucht
from flathunter.crawl_immowelt import CrawlImmowelt
from flathunter.filter import Filter

class Config:
    """Class to represent flathunter configuration"""

    __log__ = logging.getLogger('flathunt')
    __searchers__ = [CrawlImmobilienscout(),
                     CrawlWgGesucht(),
                     CrawlEbayKleinanzeigen(),
                     CrawlImmowelt()]

    def __init__(self, filename=None, string=None):
        if string is not None:
            self.config = yaml.safe_load(string)
            return
        if filename is None:
            filename = os.path.dirname(os.path.abspath(__file__)) + "/../config.yaml"
        self.__log__.info("Using config %s", filename)
        with open(filename) as file:
            self.config = yaml.safe_load(file)

    def __iter__(self):
        """Emulate dictionary"""
        return self.config.__iter__()

    def __getitem__(self, value):
        """Emulate dictionary"""
        return self.config[value]

    def get(self, key, value=None):
        """Emulate dictionary"""
        return self.config.get(key, value)

    def database_location(self):
        """Return the location of the database folder"""
        if "database_location" in self.config:
            return self.config["database_location"]
        return os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/..")

    @staticmethod
    def set_searchers(searchers):
        """Update the active search plugins"""
        Config.__searchers__ = searchers

    @staticmethod
    def searchers():
        """Get the list of search plugins"""
        return Config.__searchers__

    def get_filter(self):
        """Read the configured filter"""
        builder = Filter.builder()
        builder.read_config(self.config)
        return builder.build()
