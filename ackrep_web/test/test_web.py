
from django.test import TestCase as DjangoTestCase
from django.urls import reverse

from ackrep_core import core
from ipydex import IPS

"""
This module contains the tests for the web application module (not ackrep_core)


possibilities to run these tests
(normal `python -m unittest <path>` will not work because we need django to create an empty test-database for us):

python3 manage.py test --nocapture

# with rednose and its ips-extension installed 
python3 manage.py test --nocapture --rednose --ips

specific class or method:

python3 manage.py test --nocapture --rednose --ips ackrep_web.test.test_web:TestCases1
python3 manage.py test --nocapture --rednose --ips ackrep_web.test.test_web:TestCases1.test_00
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
