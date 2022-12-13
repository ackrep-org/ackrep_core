import os
import yaml

from unittest import skipIf, skipUnless
from django.test import TestCase as DjangoTestCase, SimpleTestCase
from django.conf import settings
from git import Repo, InvalidGitRepositoryError

from ackrep_core import core, system_model_management, util

from ._test_utils import load_repo_to_db_for_ut, reset_repo
from ackrep_core.util import run_command, utf8decode

from ipydex import IPS  # only for debugging

from distutils.spawn import find_executable
if not os.environ.get("ACKREP_ENVIRONMENT_NAME"):
    import pyerk as p

from ackrep_core_django_settings import settings

"""
This module contains the tests of the core module (not ackrep_web).

The order of classes in the file reflects the execution order, see also
<https://docs.djangoproject.com/en/4.0/topics/testing/overview/#order-of-tests>.


Possibilities to run (some of) the tests:

The option `--keepdb` is important such that the execscript has access to the same db as the test.

`python3 manage.py test --keepdb --nocapture --rednose --ips ackrep_core.test.test_core`
`python manage.py test --keepdb -v 2 --nocapture ackrep_core.test.test_core`
`python3 manage.py test --keepdb --nocapture --rednose --ips ackrep_core.test.test_core:TestCases01`
`python3 manage.py test --keepdb --nocapture --rednose --ips ackrep_core.test.test_core:TestCases03.test_get_metadata_path_from_key`

See also devdocs for tipps on speeding tests.
"""


# inform the core module which path it should consinder as data repo
ackrep_data_test_repo_path = os.path.join(core.CONF.ACKREP_ROOT_PATH, "ackrep_data_for_unittests")
# this must also be set as env var because the tests will call some functions of ackrep
# via command line
os.environ["ACKREP_DATA_PATH"] = ackrep_data_test_repo_path

# due to the command line callings we also need to specify the test-database
os.environ["ACKREP_DATABASE_PATH"] = os.path.join(core.CONF.ACKREP_ROOT_PATH, "ackrep_core", "db_for_unittests.sqlite3")


os.environ["ERK_DATA_PATH"] = pyerk_ocse_path = os.path.split(settings.CONF.ERK_DATA_OCSE_UT_MAIN_PATH)[0]

os.environ["ERK_DATA_MAIN_PATH"] = pyerk_ocse_main_path = settings.CONF.ERK_DATA_OCSE_UT_MAIN_PATH

# prevent cli commands to get stuck in unexpected IPython shell on error
# (comment out for debugging)
os.environ["NO_IPS_EXCEPTHOOK"] = "True"

# inform the core module which path it should consinder as results repo
ackrep_ci_results_test_repo_path = core.CONF.ACKREP_CI_RESULTS_PATH = os.path.join(
    core.CONF.ACKREP_ROOT_PATH, "ackrep_ci_results_for_unittests"
)
os.environ["ACKREP_CI_RESULTS_PATH"] = ackrep_ci_results_test_repo_path

core.CONF.define_paths()


pyerk_ocse_name = "ocse/0.2"

# use `git log -1` to display the full hash
default_repo_head_hash = "834aaad12256118d475de9eebfdaefb7746a28bc"  # 2022-09-13 branch for_unittests
# useful to get the currently latest sha strings:
# git log --pretty=oneline | head
TEST_DATA_REPO_COMMIT_SHA = "14cfbc0023c18d774dc039e94d2d5fb455639649"


class TestCases01(DjangoTestCase):
    """
    The tests in this class should be run first.

    These test cases do not access the database at all, so they should use SimpleTestCase
    as base class. However, due to [1] instance of DjangoTestCase (i.e. django.test.TestCase)
    are run first.

    [1] https://docs.djangoproject.com/en/4.0/topics/testing/overview/#order-of-tests
    """

    def setUp(self):
        pass

    def test_00_ackrep_data_unittest_repo(self):
        """
        Test whether the ackrep_data repository to which the unittests refer is in a defined state.

        Construct a list of all sha-strings which where commited in the current branch and assert that
        the expected string is among them. This heuristics assumes that it is OK if the data-repo is newer than
        expected. But the tests fails if it is older (or on an unexpeced branch).

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

        log_list = repo.git.log("--pretty=oneline").split("\n")
        sha_list = [line.split(" ")[0] for line in log_list]

        msg = (
            f"Repository {ackrep_data_test_repo_path} is in the wrong state. "
            f"Current branch does unexpectedly not contain commit {TEST_DATA_REPO_COMMIT_SHA[:7]}."
        )

        self.assertIn(TEST_DATA_REPO_COMMIT_SHA, sha_list, msg=msg)

    def test_01_pyerk_dependency(self):
        from packaging import version
        from pyerk import release
        pyerk_version = version.parse(release.__version__)
        self.assertTrue(pyerk_version >= version.parse("0.6.2"))

    def test_01_pyerk_data_unittest_repo(self):
        """
        Test whether the erk_data repository to which the unittests refer is in a defined state.

        The name should ensure that this test runs first (do not waste time with further tests if this fails).
        """
        msg = "Test repo not found. It must be created manually."
        self.assertTrue(os.path.isdir(pyerk_ocse_path), msg=msg)

        try:
            repo = Repo(pyerk_ocse_path)
        except InvalidGitRepositoryError:
            msg = f"The directory {pyerk_ocse_path} is not a git repository!"
            self.assertTrue(False, msg=msg)
            repo = None

        msg = f"There are uncommited changes in the repo {pyerk_ocse_path}"
        self.assertFalse(repo.is_dirty(), msg=msg)

        ut_branch = repo.active_branch.name
        self.assertIn("ut__ackrep__", ut_branch)

        core_branch = Repo(os.path.join(core.CONF.ACKREP_ROOT_PATH, "ackrep_core")).active_branch.name
        msg = f"Pyerk UT Repo is on branch {util.bred(ut_branch)} while your core project is on branch {util.bred(core_branch)}"

        if not ut_branch == f"ut__ackrep__{core_branch}":
            core.logger.warning(msg)




        # Ensure that the repository is in the expected state. This actual state (and its hash) will change in the
        # future. This test prevents that this happens without intention.
        # repo_head_hash = repo.head.commit.hexsha
        # msg = (
        #     f"Repository {ackrep_data_test_repo_path} is in the wrong state. "
        #     f"HEAD is {repo_head_hash[:7]} but should be {pyerk_ocse_path[:7]}."
        # )

        # self.assertEqual(repo_head_hash, pyerk_ocse_path, msg=msg)

    def test_logging(self):
        res = run_command(["ackrep", "--test-logging", "--log=10"])
        nl = os.linesep
        relevant_output = res.stdout.strip().split(f"- - - demo log messages - - -{nl}")[-1]
        lines = relevant_output.split(nl)
        self.assertEqual(len(lines), 5)
        self.assertIn("critical", lines[0])
        self.assertIn("debug", lines[-1])

        res = run_command(["ackrep", "--test-logging", "--log=30"])
        relevant_output = res.stdout.strip().split(f"- - - demo log messages - - -{nl}")[-1]
        lines = relevant_output.split(nl)
        self.assertEqual(len(lines), 3)
        self.assertIn("critical", lines[0])
        self.assertIn("warning", lines[-1])


class ErkHandlerMixin:

    def setUp(self):
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)
        core.load_repo_to_db(ackrep_data_test_repo_path)

    def tearDown(self) -> None:

        repo = Repo(ackrep_data_test_repo_path)
        assert not repo.is_dirty()

        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            # prevent an error here to mask other error messages
            cls = self.__class__
            method_repr = f"{cls.__module__}:{cls.__qualname__}.{self._testMethodName}"
            try:
                p.unload_mod(mod_id)
            except KeyError as err:
                print(f"Error in tearDown of {method_repr}:",  err)


class TestCases02(ErkHandlerMixin, DjangoTestCase):
    """
    These tests expect the database to be regenerated every time.

    Database changes should not be persistent outside this each case.
    -> Use DjangoTestCase as base class which ensures this behavior ("Transactions")
    """

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


class TestCases03(ErkHandlerMixin, SimpleTestCase):
    """
    These tests expect the database to be loaded.

    We use `SimpleTestCase` [1] as base class to allow for persistent changes in the database.
    This is the simples way to test the db related behavior of cli commands.

    [1] https://docs.djangoproject.com/en/4.0/topics/testing/tools/#django.test.SimpleTestCase.databases
    """

    databases = "__all__"

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

        default_env = core.model_utils.get_entity(core.settings.DEFAULT_ENVIRONMENT_KEY)
        # TODO: this should be activated when ackrep_data is fixed
        if 0:
            self.assertTrue(isinstance(entity.oc.compatible_environment, core.models.EnvironmentSpecification))
            self.assertTrue(entity.oc.compatible_environment, default_env)

    @skipUnless(os.environ.get("DJANGO_TESTS_INCLUDE_SLOW") == "True", "skipping slow test. Run with --include-slow")
    def test_check_solution(self):

        # first: run directly

        res = core.check_generic("UKJZI")
        self.assertEqual(res.returncode, 0)

        # second: run via commandline
        os.chdir(ackrep_data_test_repo_path)

        # this assumes the acrep script to be available in $PATH
        res = run_command(["ackrep", "-c", "problem_solutions/acrobot_swingup_with_pytrajectory/metadata.yml"])

        self.assertEqual(res.returncode, 0)

    def test_check_system_model(self):

        # first: run directly

        res = core.check_generic("UXMFA")
        if res.returncode != 0:
            print(res.stdout)
        self.assertEqual(res.returncode, 0)

        # second: run via commandline
        os.chdir(ackrep_data_test_repo_path)

        # this assumes the acrep script to be available in $PATH
        res = run_command(["ackrep", "-c", "UXMFA"])
        self.assertEqual(res.returncode, 0)

        # ensure repo is clean again
        # TODO: remove this if png is removed from repo
        reset_repo(ackrep_data_test_repo_path)

    @skipUnless(os.environ.get("CI") == "true", "only run test in CI (due to complicated image copying)")
    def test_check_all_entities(self):
        # this test only works in ci, not locally, due to the way plots are copied (docker cp dummy -> artifacts)
        res = run_command(["ackrep", "--check-all-entities", "-ut"])
        core.logger.info(res)
        self.assertEqual(res.returncode, 1)

        # test results.yaml
        yaml_path = os.path.join(core.CONF.ACKREP_ROOT_PATH, "artifacts", "ci_results")
        yamls = os.listdir(yaml_path)
        core.logger.info(yamls)
        self.assertEqual(len(yamls), 1)
        with open(os.path.join(yaml_path, yamls[0])) as file:
            results = yaml.load(file, Loader=yaml.FullLoader)
        self.assertIn("ackrep_core", results["commit_logs"].keys())
        self.assertIn("ackrep_data_for_unittests", results["commit_logs"].keys())
        self.assertEqual(results["UXMFA"]["result"], 0)
        self.assertEqual(results["LRHZX"]["result"], 1)
        self.assertIn("SyntaxError", results["LRHZX"]["issues"])

        # test plots
        plot_path = "../artifacts/ackrep_plots/UXMFA"
        plots = os.listdir(plot_path)
        self.assertEqual(len(plots), 1)
        self.assertEqual("plot.png", plots[0])

    def test_check_key(self):
        res = run_command(["ackrep", "--key"])
        self.assertEqual(res.returncode, 0)

        self.assertTrue(res.stdout.lower().startswith("random entity-key:"))

    def test_get_metadata_path_from_key(self):

        key = "UKJZI"
        # first: relative path
        res = run_command(["ackrep", "--get-metadata-rel-path-from-key", key])
        self.assertEqual(res.returncode, 0)

        relpath = res.stdout.strip()
        expected_relpath = os.path.join(
            "ackrep_data_for_unittests",
            "problem_solutions",
            "double_integrator_transition_with_pytrajectory",
            "metadata.yml",
        )
        self.assertEqual(relpath, expected_relpath)

        # second: absolute path
        res = run_command(["ackrep", "--get-metadata-abs-path-from-key", key])
        self.assertEqual(res.returncode, 0)

        abspath = res.stdout.strip()

        self.assertIn(relpath, abspath)
        self.assertTrue(len(abspath) > len(relpath))

    def test_get_solution_data_files(self):
        res = core.check_generic("UKJZI")
        self.assertEqual(res.returncode, 0, msg=utf8decode(res.stderr))
        sol_entity = core.model_utils.get_entity("UKJZI")

        files_dict = get_data_files_dict(sol_entity.base_path, endings=[".png"])

        self.assertEqual(len(files_dict["all"]), 1)
        self.assertEqual(len(files_dict[".png"]), 1)

        plot_file_path = files_dict[".png"][0]
        self.assertTrue(plot_file_path.endswith("plot.png"))

        self.assertTrue(os.path.isfile(os.path.join(core.CONF.ACKREP_ROOT_PATH, plot_file_path)))

    def test_get_system_model_data_files(self, key="UXMFA"):
        res = core.check_generic(key)
        self.assertEqual(res.returncode, 0, msg=utf8decode(res.stderr))
        system_model_entity = core.model_utils.get_entity(key)

        files_dict = get_data_files_dict(system_model_entity.base_path, endings=[".png", ".pdf", ".tex"])

        self.assertEqual(len(files_dict["all"]), 4)
        self.assertEqual(len(files_dict[".png"]), 1)
        self.assertEqual(len(files_dict[".pdf"]), 1)
        self.assertEqual(len(files_dict[".tex"]), 2)

        plot_file_path = files_dict[".png"][0]
        self.assertTrue(plot_file_path.endswith("plot.png"))

        self.assertTrue(os.path.isfile(os.path.join(core.CONF.ACKREP_ROOT_PATH, plot_file_path)))

        # reset unittest_repo
        reset_repo(ackrep_data_test_repo_path)

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
        system_model = core.model_utils.get_entity("BID9I")
        problem_spec = core.model_utils.get_entity("H9FRP")

        res = system_model.related_problems_list()

        self.assertIn(problem_spec, res)

    def test_entity_tag_list(self):
        e = core.model_utils.all_entities()[0]
        tag_list = util.smart_parse(e.tag_list)
        self.assertTrue(isinstance(tag_list, list))

    def test_print_entity_info(self):
        # Note: this test case does not work as a method of a `DjangoTestCase` subclass but only
        # in a `SimpleTestCase` subclass.
        key = "UXMFA"
        res = run_command(["ackrep", "--show-entity-info", key])
        self.assertEqual(res.returncode, 0)
        lines = res.stdout.strip().split(os.linesep)
        self.assertGreaterEqual(len(lines), 4)

    @skipUnless(find_executable("latex"), "skip test if latex not installed")
    def test_update_parameter_tex(self):
        # call directly
        res = system_model_management.update_parameter_tex("UXMFA")
        self.assertEqual(res, 0)

        # call command line
        os.chdir(ackrep_data_test_repo_path)
        res = run_command(["ackrep", "--update-parameter-tex", "UXMFA"])

        self.assertEqual(res.returncode, 0)

        # reset unittest_repo (for this test seems only necessary on Windows)
        reset_repo(ackrep_data_test_repo_path)

    @skipUnless(find_executable("latex"), "skip test if latex not installed")
    def test_create_pdf(self):
        # TODO: test this somehow with CI

        # first check if pdflatex is installed and included in path
        # Note: if there is a problem with this, `shell=True` might solve it on Windows
        res = run_command(["pdflatex", "--help"])
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
        res = run_command(["ackrep", "--create-pdf", "UXMFA"])
        self.assertEqual(res.returncode, 0)

        # # check leftover files
        files_dict = get_data_files_dict(system_model_entity.base_path, endings=[".pdf", ".png", ".tex"])
        self.assertEqual(len(files_dict["all"]), 4)
        self.assertEqual(len(files_dict[".png"]), 1)
        self.assertEqual(len(files_dict[".pdf"]), 1)
        self.assertEqual(len(files_dict[".tex"]), 2)

        # reset unittest_repo
        reset_repo(ackrep_data_test_repo_path)

    def test_ackrep_parser1(self):
        # unload modules, since they would already be loaded due to load_repo_to_db
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)
        mod1 = p.erkloader.load_mod_from_path(pyerk_ocse_main_path, prefix="ct", modname=pyerk_ocse_name)
        p1 = os.path.join(ackrep_data_test_repo_path, "system_models", "lorenz_system")
        res = core.ackrep_parser.load_ackrep_entities(p1)
        self.assertEqual(res, 0)

    def test_ackrep_parser2(self):
        # unload modules, since they would already be loaded due to load_repo_to_db
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)

        n_items1 = len(p.ds.items)
        _ = p.erkloader.load_mod_from_path(pyerk_ocse_main_path, prefix="ct", modname=pyerk_ocse_name)
        n_items2 = len(p.ds.items)
        self.assertGreater(n_items2, n_items1)

        p1 = os.path.join(ackrep_data_test_repo_path, "system_models", "lorenz_system")
        _ = core.ackrep_parser.load_ackrep_entities(p1)

        # assert that ocse-ct was loaded with expected prefix (this should be done in setUp)
        self.assertEqual(p.ds.uri_prefix_mapping.a["erk:/ocse/0.2/control_theory"], "ct")
        n_items3 = len(p.ds.items)
        self.assertGreater(n_items3, n_items2)

        self.assertEqual(core.ackrep_parser.ensure_ackrep_load_success(strict=False), 1)

        with self.assertRaises(p.aux.ModuleAlreadyLoadedError):
            core.ackrep_parser.load_ackrep_entities(p1)

        p.unload_mod(core.ackrep_parser.__URI__)
        self.assertEqual(core.ackrep_parser.ensure_ackrep_load_success(strict=False), 0)

        # after unloading it should work again
        core.ackrep_parser.load_ackrep_entities_if_necessary(p1, strict=False)
        self.assertEqual(core.ackrep_parser.ensure_ackrep_load_success(strict=False), 1)

    def test_ackrep_parser3(self):
        # unload modules, since they would already be loaded due to load_repo_to_db
        for mod_id in list(p.ds.mod_path_mapping.a.keys()):
            p.unload_mod(mod_id)

        mod1 = p.erkloader.load_mod_from_path(pyerk_ocse_main_path, prefix="ct", modname=pyerk_ocse_name)

        n_items1 = len(p.ds.items)
        items1 = set(p.ds.items.keys())
        core.ackrep_parser.load_ackrep_entities()
        n_items2 = len(p.ds.items)
        items2 = set(p.ds.items.keys())

        self.assertGreater(n_items2 - n_items1, 30)

        # unload ACKREP entities
        p.unload_mod(core.ackrep_parser.__URI__)
        n_items3 = len(p.ds.items)
        items3 = set(p.ds.items.keys())
        self.assertEqual(n_items1, n_items3)
        self.assertEqual(items3.difference(items1), set())

        # load again ACKREP entities
        core.ackrep_parser.load_ackrep_entities_if_necessary()
        core.ackrep_parser.ensure_ackrep_load_success(strict=True)
        n_items4 = len(p.ds.items)
        items4 = set(p.ds.items.keys())
        self.assertEqual(n_items2, n_items4)
        self.assertEqual(items4.difference(items2), set())

        # omit loading again ACKREP entities
        core.ackrep_parser.load_ackrep_entities_if_necessary()
        n_items5 = len(p.ds.items)
        items5 = set(p.ds.items.keys())
        self.assertEqual(n_items2, n_items5)
        self.assertEqual(items5.difference(items2), set())


class TestCases04(ErkHandlerMixin, DjangoTestCase):
    """
    These tests expect the database to be regenerated every time.

    Database changes of **these tests** should **not** be persistent outside each case, e.g. from cli.
    -> DjangoTestCase ist used as base class which ensures this behavior ("Transactions" [1]).

    [1] https://docs.djangoproject.com/en/4.0/topics/testing/tools/#testcase
    """

    def test_import_parameters(self, key="UXMFA"):
        # test with correct data
        parameters = system_model_management.import_parameters(key)
        self.assertEqual(parameters.parameter_check, 0)

        # prevent expected error logs from showing during test
        loglevel = core.logger.level
        core.logger.setLevel(50)

        # test with incorrect data
        delattr(parameters, "pp_sf")
        res = system_model_management.check_system_parameters(parameters)
        self.assertEqual(res, 3)

        delattr(parameters, "pp_symb")
        res = system_model_management.check_system_parameters(parameters)
        self.assertEqual(res, 2)

        core.logger.setLevel(loglevel)


class TestCases05(ErkHandlerMixin, SimpleTestCase):
    """
    Docker related test cases


    For info on base class choice see TestCases03.
    """

    databases = "__all__"

    def test_01_get_docker_env_vars(self):

        cmd_extension = core.get_docker_env_vars()

        self.assertIn("db_for_unittests.sqlite3", cmd_extension[1])
        self.assertIn("ackrep_data_for_unittests", cmd_extension[3])

    def test_run_interactive_environment(self):
        cmd = [
            "ackrep",
            "--run-interactive-environment",
            core.settings.DEFAULT_ENVIRONMENT_KEY,
            "ackrep -c UXMFA; \
            cd ../; ls; cd ackrep_data_for_unittests; ls",
        ]
        res = run_command(cmd, logger=core.logger, capture_output=True)
        self.assertEqual(res.returncode, 0)
        expected_directories = ["system_models", "Success"]
        for info in expected_directories:
            self.assertIn(info, res.stdout)

    def test_check_with_docker(self):
        # first: run directly
        # when testing locally, also test local image
        if os.environ.get("CI") != "true":
            res = core.check("UXMFA")
            if res.returncode != 0:
                print(res.stdout)
            self.assertEqual(res.returncode, 0)
        # test remote image
        res = core.check("UXMFA", try_to_use_local_image=False)
        if res.returncode != 0:
            print(res.stdout)
        self.assertEqual(res.returncode, 0)

        # second: run via commandline
        res = run_command(["ackrep", "-cwd", "UXMFA"])
        self.assertEqual(res.returncode, 0)

    def test_check_notebook(self):

        # run via commandline
        os.chdir(ackrep_data_test_repo_path)

        # this assumes the acrep script to be available in $PATH
        res = run_command(["ackrep", "-cwd", "7WIQH"])
        self.assertEqual(res.returncode, 0)

        # ensure repo is clean again
        reset_repo(ackrep_data_test_repo_path)

    def test_error_messages(self):
        ## test error message of check_system_model and execscript
        # create syntax error in file
        parameter_path = os.path.join(ackrep_data_test_repo_path, "system_models", "lorenz_system")
        os.chdir(parameter_path)
        file = open("parameters.py", "rt+")
        lines = file.readlines()
        for i, line in enumerate(lines):
            if "=" in line:
                lines[i] = line.replace("=", "=_")
                break

        file.seek(0)
        file.writelines(lines)
        file.close()

        # test for retcode != 0
        res = run_command(["ackrep", "-c", "UXMFA"])
        self.assertEqual(res.returncode, 1)

        # check error message for existance (and readability?)
        expected_error_infos = ["SyntaxError", "parameters.py", "line"]
        for info in expected_error_infos:
            self.assertIn(info, res.stdout)

        # reset unittest_repo
        reset_repo(ackrep_data_test_repo_path)

        ## test error message of check_solution and execscript
        # create syntax error in file
        parameter_path = os.path.join(
            ackrep_data_test_repo_path, "problem_specifications", "double_integrator_transition"
        )
        os.chdir(parameter_path)
        file = open("problem.py", "rt+")
        lines = file.readlines()
        for i, line in enumerate(lines):
            if "=" in line:
                lines[i] = line.replace("=", "=_")
                break

        file.seek(0)
        file.writelines(lines)
        file.close()

        # test for retcode != 0
        res = run_command(["ackrep", "-c", "UKJZI"])
        self.assertEqual(res.returncode, 1)

        # check error message for existance (and readability?)

        expected_error_infos = ["SyntaxError", "problem.py", "line"]
        for info in expected_error_infos:
            self.assertIn(info, res.stdout)

        # reset unittest_repo
        reset_repo(ackrep_data_test_repo_path)

        ## test error messages of notebooks
        # test for retcode != 0 (entity already broken)
        res = run_command(["ackrep", "-cwd", "ARMBC"])
        self.assertEqual(res.returncode, 1)

        # check error message for existance (and readability?)

        expected_error_infos = ["ZeroDivisionError", "In [2]", "<cell line: 3>"]
        for info in expected_error_infos:
            self.assertIn(info, res.stdout)

        # reset unittest_repo
        reset_repo(ackrep_data_test_repo_path)


class TestCases06(DjangoTestCase):
    """
    ERK related test cases
    """

    def test_01_erk_loading(self):
        mods = core.p.ds.uri_prefix_mapping.a

        # this is an assumption on pyerk
        self.assertIn("erk:/builtins", mods)

        # only builtins is loaded by default
        self.assertEqual(len(mods), 1)

        # now load the full ackrep data
        core.load_repo_to_db(ackrep_data_test_repo_path)

        # this ensures that all necessary pyerk modules for correct ackrep functionality are loaded
        self.assertIn("erk:/ocse/0.2/math", mods)
        self.assertIn("erk:/ocse/0.2/control_theory", mods)
        self.assertIn("erk:/ackrep", mods)


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
