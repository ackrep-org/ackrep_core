from django.test import TestCase as DjangoTestCase, LiveServerTestCase
from django.urls import reverse
from unittest import skipUnless
import re
import json

try:
    # noinspection PyPackageRequirements
    from splinter import Browser
except ImportError:
    Browser = None
    splinter_available = False
else:
    splinter_available = True

from ackrep_core import core

# noinspection PyUnresolvedReferences
from ipydex import IPS


url_of_external_test_repo = "https://codeberg.org/cknoll/ackrep_data_demo_fork.git"

"""
This module contains the tests for the web application module (not ackrep_core)


python3 manage.py test --nocapture --rednose --ips ackrep_web.test.test_web:TestCases1

For more infos see doc/devdoc/README.md.
"""


class TestCases1(DjangoTestCase):
    def test_00(self):
        # for debugging
        pass
        # IPS()

    def test_landing_page(self):
        url = reverse("landing-page")
        response = self.client.get(url)
        self.assertEqual(url, "/")

        # this should be an standard response for successful HTTP requests
        self.assertEqual(response.status_code, 200)

        bad_url = "foo-bar/baz"
        response = self.client.get(bad_url)
        self.assertEqual(response.status_code, 404)

    def test_entity_list(self):
        url = reverse("entity-list")
        response = self.client.get(url)

        # this should be an standard response for successful HTTP requests
        self.assertEqual(response.status_code, 200)

        # no entities in database yet
        self.assertNotContains(response, "utc_entity_short")

        self.assertNotContains(response, "utc_entity_full")


class TestCases2(DjangoTestCase):
    """
    These tests expect the database to be loaded
    """

    def setUp(self):
        core.load_repo_to_db(core.data_test_repo_path)

    def test_entity_detail(self):
        url = reverse("entity-detail", kwargs={"key": "UKJZI"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")

    def test_check_solution(self):
        url = reverse("check-solution", kwargs={"key": "UKJZI"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")
        self.assertContains(response, "utc_check_solution")
        self.assertContains(response, "utc_img_url")

        regex = re.compile("utc_img_url:<(.*?)>")
        img_url = regex.findall(response.content.decode("utf8"))

        response = self.client.get(img_url)

        # TODO test that this url returns a file

    def test_check_system_model(self):
        url = reverse("check-system_model", kwargs={"key": "UXMFA"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")
        self.assertContains(response, "utc_check_system_model")
        self.assertContains(response, "utc_img_url")

        regex = re.compile("utc_img_url:<(.*?)>")
        img_url = regex.findall(response.content.decode("utf8"))

        response = self.client.get(img_url)

        # TODO test that this url returns a file

    def test_sparql_query(self):

        url = reverse("search-sparql")
        query = (
            "query=%23+example+query%3A+select+all+possible+tags%0D%0A%0D%0APREFIX+P%3A+"
            "<https%3A%2F%2Fackrep.org%2Fdraft%2Focse-prototype01%23>%0D%0A++++++++++++SELECT"
            "+%3Fentity%0D%0A++++++++++++WHERE+{%0D%0A++++++++++++++%3Fentity+P%3Ahas_ontology_based_tag"
            "+P%3AiTransfer_Function.%0D%0A++++++++++++}%0D%0A"
        )
        response = self.client.get(f"{url}?{query}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "utc_template_name=ackrep_web/search_sparql.html")


class TestBugs(DjangoTestCase):
    """
    Test for specific bugs
    """

    def setUp(self):
        core.load_repo_to_db(core.data_test_repo_path)

    def test_entity_detail(self):
        url = reverse("entity-detail", kwargs={"key": "YJBOX"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")


@skipUnless(splinter_available, reason="browser automation is not installed")
class TestUI(LiveServerTestCase):
    """
    Itegration tests via browser automation (package: splinter)
    """

    # live_server_url = "http://localhost:8082/"

    def setUp(self):
        d = dict()
        d["loggingPrefs"] = {"browser": "ALL"}
        self.options_for_browser = dict(driver_name="chrome", headless=True, desired_capabilities=d)

        self.browsers = []

    def tearDown(self):
        # quit all browser instances (also those which where not created by setUp)
        for browser in self.browsers:
            browser.quit()

    def local_reverse(self, *args, **kwargs):
        return f"{self.live_server_url}{reverse(*args, **kwargs)}"

    # noinspection PyMethodMayBeStatic
    def get_status_code(self, browser):
        """
        for design reasons splinter does not grant access to http-status-codes.
        Thus, we write them to the base-template via a middleware, fetch them from the html source in the test

        :return:
        """

        elt_list = browser.find_by_xpath('//script[@id="http_status_code"]')
        if len(elt_list) == 0:
            # the http_status_code was not in the recieved page
            return None
        elif len(elt_list) == 1:
            raw_data = elt_list.first.html
            return json.loads(raw_data)
        else:
            msg = "Multiple http_status_code-tags were found unexpectedly. Check template!"
            raise ValueError(msg)

    @staticmethod
    def get_browser_log(browser):
        res = browser.driver.get_log("browser")
        browser.logs.append(res)
        return res

    def new_browser(self):
        """
        create and register a new browser

        :return: browser object and its index
        """
        browser = Browser(**self.options_for_browser)
        browser.logs = []
        self.browsers.append(browser)

        return browser

    def test_list_entities(self):
        b = self.new_browser()
        url1 = self.local_reverse("landing-page")
        b.visit(url1)
        status_code = self.get_status_code(b)
        self.assertEqual(status_code, 200)

        link = b.find_by_id("link_entity_list")
        link.click()

        status_code = self.get_status_code(b)
        self.assertEqual(status_code, 200)

    def test_list_merge_requests(self):
        b = self.new_browser()
        url1 = self.local_reverse("landing-page")
        b.visit(url1)
        status_code = self.get_status_code(b)
        self.assertEqual(status_code, 200)

        link = b.find_by_id("link_merge_request_list")
        link.click()

        status_code = self.get_status_code(b)
        self.assertEqual(status_code, 200)

    def test_open_new_merge_request_form(self):
        b = self.new_browser()
        url1 = self.local_reverse("landing-page")
        b.visit(url1)
        status_code = self.get_status_code(b)
        self.assertEqual(status_code, 200)

        link = b.find_by_id("link_new_merge_request")
        link.click()

        status_code = self.get_status_code(b)
        self.assertEqual(status_code, 200)

    def test_sparql_search_dialog(self):
        b = self.new_browser()
        url1 = self.local_reverse("landing-page")
        b.visit(url1)
        status_code = self.get_status_code(b)
        self.assertEqual(status_code, 200)

        button = b.find_by_id("link_search_sparql")
        button.click()

        status_code = self.get_status_code(b)
        self.assertEqual(status_code, 200)
