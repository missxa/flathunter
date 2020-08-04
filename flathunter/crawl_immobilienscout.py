"""Expose crawler for ImmobilienScout"""
import logging
import re
import datetime

import ipdb

from flathunter.abstract_crawler import Crawler
from flathunter.idmaintainer import IdMaintainer

class CrawlImmobilienscout(Crawler):
    """Implementation of Crawler interface for ImmobilienScout"""

    __log__ = logging.getLogger('flathunt')
    URL_PATTERN = re.compile(r'https://www\.immobilienscout24\.de')
    RESULT_LIMIT = 50

    def __init__(self):
        logging.getLogger("requests").setLevel(logging.WARNING)
        self.id_watch = IdMaintainer('processed_ids.db' )

    def get_results(self, search_url, max_pages=None):
        """Loads the exposes from the ImmoScout site, starting at the provided URL"""
        # convert to paged URL
        # if '/P-' in search_url:
        #     search_url = re.sub(r"/Suche/(.+?)/P-\d+", "/Suche/\1/P-{0}", search_url)
        # else:
        #     search_url = re.sub(r"/Suche/(.+?)/", r"/Suche/\1/P-{0}/", search_url)
        if '&pagenumber' in search_url:
            search_url = re.sub(r"&pagenumber=[0-9]", "&pagenumber={0}", search_url)
        else:
            search_url = search_url + '&pagenumber={0}'
        self.__log__.debug("Got search URL %s", search_url)

        # load first page to get number of entries
        page_no = 1
        soup = self.get_page(search_url, page_no)
        try:
            no_of_results = int(
                soup.find_all(lambda e: e.has_attr('data-is24-qa') and \
                                        e['data-is24-qa'] == 'resultlist-resultCount')[0]\
                    .text.replace('.', ''))
        except IndexError:
            self.__log__.debug('Index Error occurred')
            no_of_results = 0

        # get data from first page
        entries = self.extract_data(soup)

        # iterate over all remaining pages
        while len(entries) < min(no_of_results, self.RESULT_LIMIT) and \
                (max_pages is None or page_no < max_pages):
            self.__log__.debug(
                'Next Page, Number of entries : %d, no of results: %d',
                len(entries), no_of_results)
            page_no += 1
            soup = self.get_page(search_url, page_no)
            cur_entry = self.extract_data(soup)
            if cur_entry is list():
                break
            entries.extend(cur_entry)
            break
        return entries

    def get_page(self, search_url, page_no=None):
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""
        return self.get_soup_from_url(search_url.format(page_no))

    def get_expose_details(self, expose):
        """Loads additional details for an expose by processing the expose detail URL"""
        soup = self.get_soup_from_url(expose['url'])
        date = soup.find('dd', {"class": "is24qa-bezugsfrei-ab"})
        expose['from'] = datetime.datetime.now().strftime("%2d.%2m.%Y")
        if date is not None:
            if not re.match(r'.*sofort.*', date.text):
                expose['from'] = date.text.strip()
        return expose

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-branches
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = list()

        title_elements = soup.find_all(
            lambda e: e.name == 'a' and e.has_attr('class') and \
                      'result-list-entry__brand-title-container' in e['class'])
        expose_ids = list()
        expose_urls = list()
        for link in title_elements:
            expose_id = int(link.get('href').split('/')[-1].replace('.html', ''))
            expose_ids.append(expose_id)
            if len(str(expose_id)) > 5:
                expose_urls.append('https://www.immobilienscout24.de/expose/' + str(expose_id))
            else:
                expose_urls.append(link.get('href'))
        self.__log__.debug(expose_ids)

        attr_container_els = soup.find_all(lambda e: e.has_attr('data-is24-qa') and \
                                                     e['data-is24-qa'] == "attributes")
        address_fields = soup.find_all(lambda e: e.has_attr('class') and \
                                                 'result-list-entry__address' in e['class'])
        gallery_elements = soup.find_all(lambda e: e.has_attr('class') and \
                                         'result-list-entry__gallery-container' in e['class'])
        first = True
        for idx, title_el in enumerate(title_elements):
            # if first:
            #     first = False
            #     print(idx)
            attr_els = attr_container_els[idx].find_all('dd')
            try:
                address = address_fields[idx].text.strip()
            except AttributeError:
                address = "No address given"
            # photos = []
            # sp_images = gallery_elements[idx].find("div", {"class": "sp-image-container"})
            # import ipdb; ipdb.set_trace()
            # if sp_images is not None:
            #     self.__log__.info("yay, images are not empty!")
            #     it = sp_images.find("img")
            #     img = it["src"]
            #     self.__log__.info(img)
            # else:
            #     self.__log__.error("Not found")

            gallery_tag = gallery_elements[idx].find("div", {"class": "gallery-container"})
            if gallery_tag is not None:
                image_tag = gallery_tag.find("img")
                try:
                    image = image_tag["src"]
                except KeyError:
                    image = image_tag["data-lazy-src"]
            else:
                image = None
            image_urls, total_price, free_from = self.extract_details(expose_ids[idx],expose_urls[idx])
            details = {
                'id': expose_ids[idx],
                'url': expose_urls[idx],
                'image': image,
                'photos': image_urls,
                'title': title_el.text.strip().replace('NEU', ''),
                'free_from': free_from,
                'total_price': total_price,
                'address': address,
                'crawler': self.get_name()
            }
            # ipdb.set_trace()
            if len(attr_els) > 2:
                details['price'] = attr_els[0].text.strip().split(' ')[0].strip()
                details['size'] = attr_els[1].text.strip().split(' ')[0].strip() + " qm"
                details['rooms'] = attr_els[2].text.strip().split(' ')[0].strip()
            else:
                # If there are less than three elements, it is unclear which is what.
                details['price'] = ''
                details['size'] = ''
                details['rooms'] = ''
            # print entries
            exist = False
            for expose in entries:
                if expose_id == expose["id"]:
                    exist = True
                    break
            if not exist:
                entries.append(details)
            # else:
            #     print("skipping")
            

        # self.__log__.info('extracted: %d', entries)
        return entries

    def extract_details(self, id, url):
        db_entry = self.id_watch.get_expose_by_id(id)
        if db_entry is None:
            self.__log__.info(f"searching {url}")
            # ipdb.set_trace()
            image_urls = []
            soup = self.get_page(url)
            image_tags = soup.find_all(lambda e: e.has_attr('class') and 'sp-image' in e['class'])
            for t in image_tags:
                try:
                    image_url = t['data-src'].split("/ORIG")[0]
                    image_urls.append(image_url)
                except:
                    self.__log__.debug("cant get the image url")
            total_price_tag = soup.find(lambda e: e.has_attr('class') and 'is24qa-gesamtmiete' in e['class'])
            total_price = "-"
            if total_price_tag is not None:
                total_price = total_price_tag.text.strip()
            free_from = "-"
            free_from_tag = soup.find(lambda e: e.has_attr('class') and 'is24qa-bezugsfrei-ab' in e['class'])
            if free_from_tag is not None:
                free_from = free_from_tag.text.strip()
            return image_urls, total_price, free_from
        else:
            return db_entry["photos"], db_entry["total_price"], db_entry["free_from"]