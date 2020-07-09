import os

from django.test import TestCase as DjangoTestCase
from git import Repo, InvalidGitRepositoryError

from ackrep_core import core
from ipydex import IPS

"""
This module contains the tests of the core module (not ackrep_web)


possibilities to run these tests
(normal `python -m unittest <path>` will not work because we need django to create an empty test-database for us):

# all tests (of including ackrep_wev)

python3 manage.py test --nocapture

# with rednose and its ips-extension installed 
python3 manage.py test --nocapture --rednose --ips


specific module class or method:

python3 manage.py test --nocapture --rednose --ips ackrep_core.test.test_core
python3 manage.py test --nocapture --rednose --ips ackrep_core.test.test_core:TestCases1
python3 manage.py test --nocapture --rednose --ips ackrep_core.test.test_core:TestCases1.test_00
"""


ackrep_data_test_repo_path = core.data_test_repo_path
default_repo_head_hash = "f8be6de4e850139e9366d321ef044e11c156991b"


class TestCases1(DjangoTestCase):

    def test_00_unittest_repo(self):
        """
        Test whether the repository to which the unittests refer is in a defined state.

        The name should ensure that this test runs first (do not waste time with further tests if this fails).
        """

        msg = "Test repo not found. It must be created manually."
        self.assertTrue(os.path.isdir(ackrep_data_test_repo_path), msg=msg)

        try:
            repo = Repo(ackrep_data_test_repo_path)
        except InvalidGitRepositoryError:
            msg = f"The directory {ackrep_data_test_repo_path} is not a git repository!"
            self.assertTrue(False, msg=msg)
            repo = None

        self.assertFalse(repo.is_dirty())

        # Ensure that the repository is in the expected state. This actual state (and its hash) might change in the
        # future. This test prevents that this happens without intention.
        msg = f"Repo is in the wrong state. Expected HEAD to be {default_repo_head_hash[:7]}."
        self.assertEqual(repo.head.commit.hexsha, default_repo_head_hash, msg=msg)

    def test_import_repo(self):
        """

        :return:
        """

        entity_dict = core.get_entity_dict_from_db()
        # key: str, value: list

        # the lists should be each of length 0
        all_values = sum(entity_dict.values(), [])
        self.assertEqual(len(all_values), 0)

        # the number of key should be the same as the number of entity types

        self.assertEqual(len(entity_dict), len(core.models.get_entities()))


