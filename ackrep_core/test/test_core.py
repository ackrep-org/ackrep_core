import os
import subprocess

from unittest import skipUnless
from django.test import TestCase as DjangoTestCase
from git import Repo, InvalidGitRepositoryError

from ackrep_core import core

from ipydex import IPS  # only for debugging

"""
This module contains the tests of the core module (not ackrep_web)


one possibility to run these (some of) the tests

python3 manage.py test --nocapture --rednose --ips ackrep_core.test.test_core:TestCases1

For more infos see doc/devdoc/README.md.
"""


ackrep_data_test_repo_path = core.data_test_repo_path
default_repo_head_hash = "f2a7ca9322334ce65e78daaec11401153048ceb6"  # 2021-04-12 00:45:46


class TestCases1(DjangoTestCase):
    def setUp(self):
        core.clear_db()

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

        msg = f"There are uncommited changes in the repo {ackrep_data_test_repo_path}"
        self.assertFalse(repo.is_dirty(), msg=msg)

        # Ensure that the repository is in the expected state. This actual state (and its hash) will change in the
        # future. This test prevents that this happens without intention.
        repo_head_hash = repo.head.commit.hexsha
        msg = (
            f"Repository {ackrep_data_test_repo_path} is in the wrong state. "
            f"HEAD is {repo_head_hash[:7]} but should be {default_repo_head_hash[:7]}."
        )

        self.assertEqual(repo_head_hash, default_repo_head_hash, msg=msg)

    def test_import_repo(self):
        """

        :return:
        """

        entity_dict = core.get_entity_dict_from_db()
        # key: str, value: list

        # the lists should be each of length 0
        all_values = sum(entity_dict.values(), [])
        self.assertEqual(len(all_values), 0)

        # the number of keys should be the same as the number of entity types

        self.assertEqual(len(entity_dict), len(core.model_utils.get_entity_types()))

        # TODO: load repo and assess the content
        # core.load_repo_to_db(core.data_path)


class TestCases2(DjangoTestCase):
    """
    These tests expect the database to be loaded
    """

    def setUp(self):
        core.load_repo_to_db(core.data_test_repo_path)

    def test_resolve_keys(self):
        entity = core.model_utils.get_entity("UKJZI")

        # ensure that the object container is yet empty
        self.assertTrue(len(entity.oc.item_list()) == 0)

        core.model_utils.resolve_keys(entity)
        self.assertTrue(len(entity.oc.item_list()) > 0)

        self.assertTrue(isinstance(entity.oc.solved_problem_list, list))
        self.assertEquals(len(entity.oc.solved_problem_list), 1)
        self.assertEquals(entity.oc.solved_problem_list[0].key, "4ZZ9J")
        self.assertTrue(isinstance(entity.oc.method_package_list, list))
        self.assertEquals(entity.oc.method_package_list[0].key, "UENQQ")
        self.assertTrue(entity.oc.predecessor_key is None)

        default_env = core.model_utils.get_entity("YJBOX")
        # TODO: this should be activated when ackrep_data is fixed
        if 0:
            self.assertTrue(isinstance(entity.oc.compatible_environment, core.models.EnvironmentSpecification))
            self.assertTrue(entity.oc.compatible_environment, default_env)

    @skipUnless(os.environ.get("DJANGO_TESTS_INCLUDE_SLOW") == "True", "skipping slow test. Run with --include-slow")
    def test_check_solution(self):

        # first: run directly

        res = core.check_solution("UKJZI")
        self.assertEqual(res.returncode, 0)

        # second: run via commandline
        os.chdir(ackrep_data_test_repo_path)

        # this assumes the acrep script to be available in $PATH
        res = subprocess.run(["ackrep", "-cs", "playground/acrobot_solution/metadata.yml"], capture_output=True)
        res.exited = res.returncode
        res.stdout = utf8decode(res.stdout)
        res.stderr = utf8decode(res.stderr)

        self.assertEqual(res.returncode, 0)

    def test_check_key(self):
        res = subprocess.run(["ackrep", "--key"], capture_output=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(utf8decode(res.stdout).lower().startswith("random entity-key:"))

    def test_get_solution_data_files(self):
        res = core.check_solution("UKJZI")
        self.assertEqual(res.returncode, 0, msg=utf8decode(res.stderr))
        sol_entity = core.model_utils.get_entity("UKJZI")

        all_files = core.get_solution_data_files(sol_entity.base_path)
        png_files = core.get_solution_data_files(sol_entity.base_path, endswith_str=".png")
        txt_files = core.get_solution_data_files(sol_entity.base_path, endswith_str=".txt")

        self.assertEqual(len(all_files), 1)
        self.assertEqual(len(png_files), 1)
        self.assertEqual(len(txt_files), 0)

        plot_file_path = png_files[0]
        self.assertTrue(plot_file_path.endswith("plot.png"))

        self.assertTrue(os.path.isfile(os.path.join(core.root_path, plot_file_path)))

    def test_get_available_solutions(self):
        problem_spec = core.model_utils.get_entity("4ZZ9J")
        problem_sol1 = core.model_utils.get_entity("UKJZI")

        res = problem_spec.available_solutions_list()

        self.assertEqual(res, [problem_sol1])

    def test_entity_tag_list(self):
        e = core.model_utils.all_entities()[0]
        tag_list = core.util.smart_parse(e.tag_list)
        self.assertTrue(isinstance(tag_list, list))

    def test_ontology(self):

        # check the ontology manager
        OM = core.AOM.OM
        self.assertFalse(OM is None)
        self.assertTrue(len(OM.n.ACKREP_ProblemSpecification.instances()) > 0)

        qsrc = f'PREFIX P: <{OM.iri}> SELECT ?x WHERE {{ ?x P:has_entity_key "4ZZ9J".}}'
        res = OM.make_query(qsrc)
        self.assertEqual(len(res), 1)
        ps_double_integrator_transition = res.pop()

        qsrc = f"PREFIX P: <{OM.iri}> SELECT ?x WHERE {{ ?x P:has_ontology_based_tag P:iLinear_State_Space_System.}}"
        res = OM.make_query(qsrc)
        self.assertTrue(ps_double_integrator_transition in res)

        # get list of all possible tags (instances of OCSE_Entity and its subclasses)
        qsrc = f"""PREFIX P: <{OM.iri}>
            SELECT ?entity
            WHERE {{
              ?entity rdf:type ?type.
              ?type rdfs:subClassOf* P:OCSE_Entity.
            }}
        """
        res = OM.make_query(qsrc)
        self.assertTrue(len(res) > 40)

        res2 = core.AOM.get_list_of_all_ontology_based_tags()

        qsrc = f"""PREFIX P: <{OM.iri}>
            SELECT ?entity
            WHERE {{
              ?entity P:has_entity_key "J73Y9".
            }}
        """
        ae, oe = core.AOM.run_sparql_query_and_translate_result(qsrc)
        self.assertEqual(oe, [])
        self.assertTrue(isinstance(ae[0], core.models.ProblemSpecification))

        qsrc = f"""PREFIX P: <{OM.iri}>
            SELECT ?entity
            WHERE {{
              ?entity P:has_ontology_based_tag P:iTransfer_Function.
            }}
        """
        ae, oe = core.AOM.run_sparql_query_and_translate_result(qsrc)
        self.assertTrue(len(ae) > 0)

        qsrc = f"""
        PREFIX P: <https://ackrep.org/draft/ocse-prototype01#>
        SELECT ?entity
        WHERE {{
          ?entity P:has_entity_key "M4PDA".
        }}
        """
        ae, oe = core.AOM.run_sparql_query_and_translate_result(qsrc)
        self.assertTrue(len(ae) == 1)
        # IPS(print_tb=-1)


def utf8decode(obj):
    if hasattr(obj, "decode"):
        return obj.decode("utf8")
    else:
        return obj
