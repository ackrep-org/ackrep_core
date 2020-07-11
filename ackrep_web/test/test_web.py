
from django.test import TestCase as DjangoTestCase
from django.urls import reverse
import re

from ackrep_core import core
from ipydex import IPS

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
        url = reverse('landing-page')
        response = self.client.get(url)
        self.assertEqual(url, "/")

        # this should be an standard response for successful HTTP requests
        self.assertEqual(response.status_code, 200)

        bad_url = "foo-bar/baz"
        response = self.client.get(bad_url)
        self.assertEqual(response.status_code, 404)

    def test_entity_list(self):
        url = reverse('entity-list')
        response = self.client.get(url)

        # this should be an standard response for successful HTTP requests
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_short")
        self.assertNotContains(response, "utc_entity_full")


class TestCases2(DjangoTestCase):
    """
    These tests expect the database to be loaded
    """

    def setUp(self):
        core.load_repo_to_db(core.data_test_repo_path)

    def test_entity_detail(self):
        url = reverse('entity-detail', kwargs={"key": "UKJZI"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")

    def test_check_solution(self):
        url = reverse('check-solution', kwargs={"key": "UKJZI"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")
        self.assertContains(response, "utc_check_solution")
        self.assertContains(response, "utc_img_url")

        regex = re.compile("utc_img_url:<(.*?)>")
        img_url = regex.findall(response.content.decode("utf8"))

        response = self.client.get(img_url)

        # TODO test that this url returns a file


class TestBugs(DjangoTestCase):
    """
    Test for specific bugs
    """

    def setUp(self):
        core.load_repo_to_db(core.data_test_repo_path)

    def test_entity_detail(self):
        url = reverse('entity-detail', kwargs={"key": "YJBOX"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "utc_entity_full")
