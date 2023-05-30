import os
from textwrap import dedent as twdd
from urllib.parse import quote, unquote

from django.test import SimpleTestCase, TestCase as DjangoTestCase, LiveServerTestCase
from django.urls import reverse
from django.test.utils import override_settings
from unittest import skipUnless
from ackrep_core.test._test_utils import load_repo_to_db_for_ut, reset_repo
from ackrep_web.views import get_item
import json
from ackrep_core_django_settings import settings
if not os.environ.get("ACKREP_ENVIRONMENT_NAME"):
    import pyerk as p
from bs4 import BeautifulSoup

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


python3 manage.py test --keepdb --nocapture --rednose --ips ackrep_web.test.test_web:TestCases1
python manage.py test --keepdb -v 2 --nocapture ackrep_web.test.test_web

For more infos see doc/devdoc/README.md.
"""


# set the environment variables and update the CONF object

# inform the core module which path it should consinder as data repo
ackrep_data_test_repo_path = os.path.join(core.CONF.ACKREP_ROOT_PATH, "ackrep_data_for_unittests")
# this must also be set as env var because the tests will call some functions of ackrep
# via command line
os.environ["ACKREP_DATA_PATH"] = ackrep_data_test_repo_path

# due to the command line callings we also need to specify the test-database
os.environ["ACKREP_DATABASE_PATH"] = os.path.join(core.CONF.ACKREP_ROOT_PATH, "ackrep_core", "db_for_unittests.sqlite3")

# prevent cli commands to get stuck in unexpected IPython shell on error
# (comment out for debugging)
os.environ["NO_IPS_EXCEPTHOOK"] = "True"

# inform the core module which path it should consider as results repo
ackrep_ci_results_test_repo_path = os.path.join(core.CONF.ACKREP_ROOT_PATH, "ackrep_ci_results_for_unittests")
os.environ["ACKREP_CI_RESULTS_PATH"] = ackrep_ci_results_test_repo_path

core.CONF.define_paths()


class TestCases1(DjangoTestCase):
    def test_00(self):
        # for debugging
        pass
        # IPS()

    def test_landing_page(self):
        url = reverse("landing-page")
        response = self.client.get(url)
        self.assertEqual(url, "/")

        # this should be a standard response for successful HTTP requests
        self.assertEqual(response.status_code, 200)

        bad_url = "foo-bar/baz"
        response = self.client.get(bad_url)
        self.assertEqual(response.status_code, 404)

    def test_entity_list(self):
        url = reverse("entity-list")
        response = self.client.get(url)

        # this should be a standard response for successful HTTP requests
        self.assertEqual(response.status_code, 200)


class TestCases2(SimpleTestCase):
    """
    These tests expect the database to be loaded
    """

    databases = "__all__"

    def setUp(self):
        reset_repo(ackrep_data_test_repo_path)
        self.load_db()

    def load_db(self):
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)
        load_repo_to_db_for_ut(ackrep_data_test_repo_path)

    def test_entity_detail(self):
        url = reverse("entity-detail", kwargs={"key": "UKJZI"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")
        self.assertContains(response, "Success")

        url = reverse("entity-detail", kwargs={"key": "UXMFA"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")
        self.assertContains(response, "Success")

        # skip test if done in CI, see https://ackrep-doc.readthedocs.io/en/latest/devdoc/design_considerations.html#ci
        # if os.environ.get("CI") != "true":
        #     self.assertContains(response, "utc_img_url")

        #     regex = re.compile("utc_img_url:<(.*?)>")
        #     img_url = regex.findall(response.content.decode("utf8"))

        #     response = self.client.get(img_url)

        #     # TODO test that this url returns a file

    @override_settings(DEBUG=True)
    def test_debug_message_printing(self):

        # broken lorenz system
        url = reverse("entity-detail", kwargs={"key": "LRHZX"})

        # prevent expected error logs from showing during test
        loglevel = core.logger.level
        # core.logger.setLevel(50)

        # first: check if debug message shows when it should
        settings.DEBUG = True
        response = self.client.get(url)

        expected_error_infos = ["utc_debug", "SyntaxError", "parameters.py", "line"]
        for info in expected_error_infos:
            self.assertContains(response, info)
        self.assertNotContains(response, "utc_output")

        # second: check if debug message shows when it shouldn't
        settings.DEBUG = False
        response = self.client.get(url)

        expected_error_infos = ["utc_debug", "SyntaxError"]
        for info in expected_error_infos:
            self.assertNotContains(response, info)
        self.assertNotContains(response, "utc_output")

        core.logger.setLevel(loglevel)

    def test_show_last_passing(self):
        url = reverse("entity-detail", kwargs={"key": "LRHZX"})
        response = self.client.get(url)
        infos = ["Entity passed last:", "2022-06-24 00:00:00"]
        for info in infos:
            self.assertContains(response, info)

    def test_sparql_query1(self):

        url = reverse("search-sparql")

        sparql_src = twdd(
            f"""
        PREFIX : {settings.SPARQL_PREFIX_MAPPING[':']}
        PREFIX ocse: {settings.SPARQL_PREFIX_MAPPING['ocse']}
        SELECT ?s
        WHERE {{
            ?s :R16 ocse:I7733.

        }}
        """
        )
        response = self.client.get(f"{url}?query={quote(sparql_src)}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UXMFA")
        self.assertContains(response, "utc_template_name=ackrep_web/search_sparql.html")

        soup = BeautifulSoup(response.content.decode("utf8"), "lxml")
        res = soup.find(id="utjd_n_results")
        self.assertGreaterEqual(json.loads(res.string), 2)

    def test_sparql_query2(self):
        # test preprocessing of query
        url = reverse("search-sparql")
        sparql_src = twdd(
            f"""
        PREFIX : {settings.SPARQL_PREFIX_MAPPING[':']}
        PREFIX ocse: {settings.SPARQL_PREFIX_MAPPING['ocse']}
        SELECT ?s
        WHERE {{
            ?s :R16__has_property ocse:I7733__time_invariance.

        }}
        """
        )
        response = self.client.get(f"{url}?query={quote(sparql_src)}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UXMFA")
        self.assertContains(response, "utc_template_name=ackrep_web/search_sparql.html")

        soup = BeautifulSoup(response.content.decode("utf8"), "lxml")
        res = soup.find(id="utjd_n_results")
        self.assertGreaterEqual(json.loads(res.string), 2)

    def test_sparql_query3(self):
        # test for correct display of sparql results in table form
        url = reverse("search-sparql")

        sparql_src = twdd(
            f"""
        PREFIX : {settings.SPARQL_PREFIX_MAPPING[':']}
        PREFIX ocse: {settings.SPARQL_PREFIX_MAPPING['ocse']}
        PREFIX ack: {settings.SPARQL_PREFIX_MAPPING['ack']}
        SELECT ?s ?p ?o
        WHERE {{
            ?s ?p ?o.
            ?s :R4__is_instance_of ocse:I5356__general_system_property.
        }}
        """
        )

        response = self.client.get(f"{url}?query={quote(sparql_src)}")
        self.assertEqual(response.status_code, 200)

        soup = BeautifulSoup(response.content.decode("utf8"), "lxml")

        soup = BeautifulSoup(response.content.decode("utf8"), "lxml")
        res = soup.find(id="utjd_n_results")

        n_results = json.loads(res.string)
        self.assertGreaterEqual(n_results, 43)

        rows = soup.findAll("tr")
        self.assertEqual(len(rows), n_results + 1)
        row0 = rows[0].findAll("th")
        tablehead = ["s", "p", "o"]
        for i in range(3):
            self.assertEqual(row0[i].contents[0], tablehead[i])

    def test02_search_api(self):
        url = "/search/?q=set"
        res = self.client.get(url)

        soup = BeautifulSoup(res.content.decode("utf8"), "lxml")

        script_tags = soup.findAll("script")

        for tag in script_tags:
            # this assumes that Item I13 has not changed its label since the test was written
            if tag.contents and (tag.contents[0] == '\\"I13[\\\\\\"mathematical set\\\\\\"]\\"'):
                break
        else:
            self.assertTrue(False, "could not find expected copy-string in response")

    def test03_search_api(self):
        # this tests:
        # - partial matching (out of order search of key words)
        # - sorting of pyerk entities in relevant order
        class C:
            pass

        request = C()
        request.GET = {"q": "system model general"}

        res = get_item(request)

        soup = BeautifulSoup(res.content.decode("utf8"), "lxml")

        script_tags = soup.findAll("script")

        self.assertTrue(script_tags[0].contents[0], '\\"\\"')
        self.assertTrue(script_tags[1].contents[0], '\\"I7641[\\\\\\"general system model\\\\\\"]\\"')
        self.assertTrue(script_tags[2].contents[0], '\\"ocse:I7641__general_system_model\\"')

    def tearDown(self) -> None:
        reset_repo(ackrep_data_test_repo_path)
        return super().tearDown()


class TestBugs(DjangoTestCase):
    """
    Test for specific bugs
    """

    def setUp(self):
        load_repo_to_db_for_ut(ackrep_data_test_repo_path)

    def test_entity_detail(self):
        url = reverse("entity-detail", kwargs={"key": "YJBOX"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")


@skipUnless(splinter_available, reason="browser automation is not installed")
class TestUI(LiveServerTestCase):
    """
    Itegration tests via browser automation (package: splinter)

    Note: this class automatically launches a server in the background.
    Its url is automatically determinded and avaliable as `self.live_server_url`.
    """

    def setUp(self):
        super().setUp()
        d = dict()
        d["loggingPrefs"] = {"browser": "ALL"}
        self.options_for_browser = dict(driver_name="chrome", headless=True, desired_capabilities=d)

        self.browsers = []

    def tearDown(self):
        # quit all browser instances (also those which where not created by setUp)
        for browser in self.browsers:
            browser.quit()

        super().tearDown()

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
