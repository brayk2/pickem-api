from functools import cached_property

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from src.config.base_service import BaseService
from src.util.injection import dependency, inject


@dependency
class BaseScraper(BaseService):
    @inject
    def __init__(self, base_url: str):
        self.base_url = base_url

    @cached_property
    def client(self):
        self.logger.info(f"creating client for: {self.base_url}")
        return httpx.Client(base_url=self.base_url, timeout=60)

    def _get_static_soup(self, url: str) -> BeautifulSoup:
        """
        Generate BeautifulSoup for a static HTML site. Fetch site using httpx client and parse response with BS4.
        :param url: the endpoint to init BeautifulSoup [full url is base_url/url]
        :return: BeautifulSoup object setup with the url param
        """
        self.logger.info(f"generating static soup: {url}")
        page = self.client.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        return soup

    def _get_dynamic_soup(self, url: str) -> BeautifulSoup:
        """
        Generate BeautifulSoup for a dynamic JS site. Open site in chromium browser then init BeautifulSoup with page contents, closing the browser on exit.
        :param url: the endpoint to init BeautifulSoup [full url is base_url/url]
        :return: BeautifulSoup object setup with the url param
        """
        self.logger.info(f"generating dynamic soup: {url}")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"{self.base_url}/{url}")
            soup = BeautifulSoup(page.content(), "html.parser")
            browser.close()
            return soup

    def get_soup(self, url: str, dynamic: bool = False) -> BeautifulSoup:
        """
        Generate BeautifulSoup for given URL and dynamic flag.
        :param url: the endpoint to init BeautifulSoup [full url is base_url/url]
        :param dynamic: flag to indicate dynamic site
        :return: BeautifulSoup object setup with the url param
        """
        self.logger.info(
            f"generating soup for request, url = {url}, dynamic = {dynamic}"
        )
        if dynamic:
            return self._get_dynamic_soup(url=url)
        return self._get_static_soup(url=url)
