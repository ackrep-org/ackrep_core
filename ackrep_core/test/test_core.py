import os
import sys
import platform
import subprocess

from unittest import skipUnless
from django.test import TestCase as DjangoTestCase, SimpleTestCase
from django.conf import settings
from git import Repo, InvalidGitRepositoryError

from ackrep_core import core, system_model_management

from ._test_utils import load_repo_to_db_for_tests, reset_repo

from ipydex import IPS  # only for debugging

"""
This module contains the tests of the core module (not ackrep_web).

The order of classes in the file reflects the execution order, see also
<https://docs.djangoproject.com/en/4.0/topics/testing/overview/#order-of-tests>.


Possibilities to run (some of) the tests:

`python3 manage.py test --keepdb --nocapture --rednose --ips ackrep_core.test.test_core`
`python3 manage.py test --keepdb --nocapture --rednose --ips ackrep_core.test.test_core:TestCases1`
`python3 manage.py test --keepdb --nocapture --rednose --ips ackrep_core.test.test_core:TestCases3.test_get_metadata_path_from_key`

See also devdocs for tipps on speeding tests.
"""


# inform the core module which path it should consinder as data repo
ackrep_data_test_repo_path = core.data_path = os.path.join(core.root_path, "ackrep_data_for_unittests")
# this must also be set as env var because the tests will call some functions of ackrep
# via command line
os.environ["ACKREP_DATA_PATH"] = ackrep_data_test_repo_path

# due to the command line callings we also need to specify the test-database
os.environ["ACKREP_DATABASE_PATH"] = os.path.join(core.root_path, "ackrep_core", "db_for_unittests.sqlite3")

# prevent cli commands to get stuck in unexpected IPython shell on error
# (comment out for debugging)
os.environ["NO_IPS_EXCEPTHOOK"] = "True"

# use `git log -1` to display the full hash
default_repo_head_hash = "c931f25b3eacad8e0ca495de49c3c488135bdb61"  # 2022-04-16 branch for_unittests


class TestCases1(DjangoTestCase):
    """
    The tests in this class should be run first.

    These test cases do not access the database at all, so they should use SimpleTestCase
    as base class. However, due to [1] instance of DjangoTestCase (i.e. django.test.TestCase)
    are run first. 

    [1] https://docs.djangoproject.com/en/4.0/topics/testing/overview/#order-of-tests
    """
    def setUp(self):
        pass

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


class TestCases2(DjangoTestCase):
    """
    These tests expect the database to be regenerated every time.
    
    Database changes should not be persistent outside this each case.
    -> Use DjangoTestCase as base class which ensures this behavior ("Transactions")
    """
    
    def setUp(self):
        core.load_repo_to_db(ackrep_data_test_repo_path)

    def test_ontology(self):

        # check the ontology manager
        OM = core.AOM.OM
        self.assertFalse(OM is None)
        self.assertTrue(len(list(OM.n.ACKREP_ProblemSpecification.instances())) > 0)

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

    def test_import_repo(self):

        # ensure database is empty
        core.clear_db()

        entity_dict = core.get_entity_dict_from_db()
        # key: str, value: list

        # the lists should be each of length 0
        all_values = sum(entity_dict.values(), [])
        self.assertEqual(len(all_values), 0)

        # the number of keys should be the same as the number of entity types

        self.assertEqual(len(entity_dict), len(core.model_utils.get_entity_types()))

        # TODO: load repo and assess the content
        # core.load_repo_to_db(ackrep_data_test_repo_path)


class TestCases3(SimpleTestCase):
    """
    These tests expect the database to be loaded.

    We use `SimpleTestCase` [1] as base class to allow for persistent changes in the database.
    This is the simples way to test the db related behavior of cli commands.

    [1] https://docs.djangoproject.com/en/4.0/topics/testing/tools/#django.test.SimpleTestCase.databases
    """
    databases = '__all__'

    def setUp(self):
        load_repo_to_db_for_tests(ackrep_data_test_repo_path)

    def tearDown(self):
        # optionally check if repo is clean
        pass
        repo = Repo(ackrep_data_test_repo_path)
        assert not repo.is_dirty()


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
        res = subprocess.run(
            ["ackrep", "-cs", "problem_solutions/acrobot_swingup_with_pytrajectory/metadata.yml"], capture_output=True
        )
        res.exited = res.returncode
        res.stdout = utf8decode(res.stdout)
        res.stderr = utf8decode(res.stderr)
        if res.returncode != 0:
            print(res.stderr)

        self.assertEqual(res.returncode, 0)

    def test_check_system_model(self):

        # first: run directly

        res = core.check_system_model("UXMFA")
        self.assertEqual(res.returncode, 0)

        # second: run via commandline
        os.chdir(ackrep_data_test_repo_path)

        # this assumes the acrep script to be available in $PATH
        res = subprocess.run(["ackrep", "-csm", "UXMFA"], capture_output=True)
        res.exited = res.returncode
        res.stdout = utf8decode(res.stdout)
        res.stderr = utf8decode(res.stderr)
        if res.returncode != 0:
            print(res.stderr)

        self.assertEqual(res.returncode, 0)

        # ensure repo is clean again
        # TODO: remove this if png is removed from repo
        reset_repo(ackrep_data_test_repo_path)

    def test_check_key(self):
        res = subprocess.run(["ackrep", "--key"], capture_output=True)
        self.assertEqual(res.returncode, 0)

        self.assertTrue(strip_decode(res.stdout).lower().startswith("random entity-key:"))

    def test_get_metadata_path_from_key(self):

        key = "UKJZI"
        # first: relative path
        res = subprocess.run(["ackrep", "--get-metadata-rel-path-from-key", key], capture_output=True)
        self.assertEqual(res.returncode, 0)
        
        relpath = strip_decode(res.stdout).strip()
        expected_relpath = os.path.join(
            "ackrep_data_for_unittests",
            "problem_solutions",
            "double_integrator_transition_with_pytrajectory",
            "metada.yml"
            )
        self.assertEqual(relpath, expected_relpath)

        # second: absolute path
        res = subprocess.run(["ackrep", "--get-metadata-abs-path-from-key", key], capture_output=True)
        self.assertEqual(res.returncode, 0)
        
        abspath = strip_decode(res.stdout).strip()
    
        self.assertIn(relpath, abspath)
        self.assertTrue(len(abspath) > len(relpath))
        
    def test_get_solution_data_files(self):
        res = core.check_solution("UKJZI")
        self.assertEqual(res.returncode, 0, msg=utf8decode(res.stderr))
        sol_entity = core.model_utils.get_entity("UKJZI")

        files_dict = get_data_files_dict(sol_entity.base_path, endings=[".png"])

        self.assertEqual(len(files_dict["all"]), 1)
        self.assertEqual(len(files_dict[".png"]), 1)

        plot_file_path = files_dict[".png"][0]
        self.assertTrue(plot_file_path.endswith("plot.png"))

        self.assertTrue(os.path.isfile(os.path.join(core.root_path, plot_file_path)))

    def test_get_system_model_data_files(self, key="UXMFA"):
        res = core.check_system_model(key)
        self.assertEqual(res.returncode, 0, msg=utf8decode(res.stderr))
        system_model_entity = core.model_utils.get_entity(key)

        files_dict = get_data_files_dict(system_model_entity.base_path, endings=[".png", ".pdf", ".tex"])

        self.assertEqual(len(files_dict["all"]), 4)
        self.assertEqual(len(files_dict[".png"]), 1)
        self.assertEqual(len(files_dict[".pdf"]), 1)
        self.assertEqual(len(files_dict[".tex"]), 2)

        plot_file_path = files_dict[".png"][0]
        self.assertTrue(plot_file_path.endswith("plot.png"))

        self.assertTrue(os.path.isfile(os.path.join(core.root_path, plot_file_path)))

    def test_create_media_links(self):
        # first: delete existing links
        # ensure repo is clean again
        # TODO: remove this if png is removed from repo
        reset_repo(ackrep_data_test_repo_path)
        
        media_path = settings.MEDIA_ROOT
        files = os.listdir(media_path)
        for file in files:
            if file != "empty":
                os.remove(os.path.join(media_path, file))

        # second: try creating new link
        system_model_entity = core.model_utils.get_entity("UXMFA")
        try:
            result = core.get_data_files(system_model_entity.base_path, endswith_str=".png", create_media_links=True)
        except OSError:
            result = []
        self.assertTrue(len(result) > 0)

    def test_get_available_solutions(self):
        problem_spec = core.model_utils.get_entity("4ZZ9J")
        problem_sol1 = core.model_utils.get_entity("UKJZI")

        res = problem_spec.available_solutions_list()

        self.assertEqual(res, [problem_sol1])

    def test_get_related_problems(self):
        system_model = core.model_utils.get_entity("UXMFA")
        problem_spec = core.model_utils.get_entity("S2V8V")

        res = system_model.related_problems_list()

        self.assertEqual(res, [problem_spec])

    def test_entity_tag_list(self):
        e = core.model_utils.all_entities()[0]
        tag_list = core.util.smart_parse(e.tag_list)
        self.assertTrue(isinstance(tag_list, list))


class TestCases4(DjangoTestCase):
    """
    These tests expect the database to be regenerated every time.
    
    Database changes should not be persistent outside this each case.
    -> Use DjangoTestCase as base class which ensures this behavior ("Transactions")
    """
    
    def setUp(self):
        core.load_repo_to_db(ackrep_data_test_repo_path)

    def test_update_parameter_tex(self):
        # call directly
        res = system_model_management.update_parameter_tex("UXMFA")
        self.assertEqual(res, 0)

        # call command line
        os.chdir(ackrep_data_test_repo_path)
        res = subprocess.run(["ackrep", "--update-parameter-tex", "UXMFA"], capture_output=True)
        res.exited = res.returncode
        res.stdout = utf8decode(res.stdout)
        res.stderr = utf8decode(res.stderr)
        if res.returncode != 0:
            print(res.stderr)

        self.assertEqual(res.returncode, 0)

    def test_create_pdf(self):
        # first check if pdflatex is installed and included in path
        # TODO: if there is a problem with this, `shell=True` might solve it on Windows
        res = subprocess.run(["pdflatex", "--help"], capture_output=True)
        res.exited = res.returncode
        res.stdout = utf8decode(res.stdout)
        res.stderr = utf8decode(res.stderr)
        if res.returncode != 0:
            print(res.stderr)
        self.assertEqual(res.returncode, 0, msg="pdflatex not found! Check installation and its existence in PATH!")

        system_model_entity = core.model_utils.get_entity("UXMFA")

        ## call directly
        res = system_model_management.create_pdf("UXMFA")
        res.exited = res.returncode
        res.stdout = utf8decode(res.stdout)
        res.stderr = utf8decode(res.stderr)
        if res.returncode != 0:
            print(res.stderr)
        self.assertEqual(res.returncode, 0)

        # check leftover files
        files_dict = get_data_files_dict(system_model_entity.base_path, endings=[".pdf", ".png", ".tex"])
        self.assertEqual(len(files_dict["all"]), 4)
        self.assertEqual(len(files_dict[".png"]), 1)
        self.assertEqual(len(files_dict[".pdf"]), 1)
        self.assertEqual(len(files_dict[".tex"]), 2)

        ## call command line
        res = subprocess.run(["ackrep", "--create-pdf", "UXMFA"], capture_output=True)
        res.exited = res.returncode
        res.stdout = utf8decode(res.stdout)
        res.stderr = utf8decode(res.stderr)
        if res.returncode != 0:
            print(res.stderr)
        self.assertEqual(res.returncode, 0)

        # # check leftover files
        files_dict = get_data_files_dict(system_model_entity.base_path, endings=[".pdf", ".png", ".tex"])
        self.assertEqual(len(files_dict["all"]), 4)
        self.assertEqual(len(files_dict[".png"]), 1)
        self.assertEqual(len(files_dict[".pdf"]), 1)
        self.assertEqual(len(files_dict[".tex"]), 2)

        # reset unittest_repo
        reset_repo(ackrep_data_test_repo_path)

    def test_parameter_import(self, key="UXMFA"):
        # test with correct data
        parameters = system_model_management.import_parameters(key)
        self.assertEqual(parameters.parameter_check, 0)

        # test with incorrect data
        delattr(parameters, "pp_sf")
        res = system_model_management.check_system_parameters(parameters)
        self.assertEqual(res, 3)

        delattr(parameters, "pp_symb")
        res = system_model_management.check_system_parameters(parameters)
        self.assertEqual(res, 2)


def utf8decode(obj):
    if hasattr(obj, "decode"):
        return obj.decode("utf8")
    else:
        return obj


def get_data_files_dict(path, endings=[]):
    """fetch all data filed from given path and put them in dict with the following keys:
    - "all"
    - entries of endings

    Args:
        path: entity.base_path
        endings : array of ending strings, e.g. [".png", ".pdf"]

    Returns:
        dict: dictionary of files
    """
    ending_files_dict = dict()
    ending_files_dict["all"] = core.get_data_files(path)
    for ending in endings:
        ending_files_dict[ending] = core.get_data_files(path, ending)
    return ending_files_dict


def strip_decode(obj) -> str:

    # get rid of some (ipython-related boilerplate bytes (ended by \x07))
    delim = b"\x07"
    obj = obj.split(delim)[-1]
    return utf8decode(obj)
