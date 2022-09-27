import secrets
import yaml
import os, sys
import pathlib
import time
import shutil
import logging
from typing import List
from jinja2 import Environment, FileSystemLoader
from ipydex import Container  # for functionality
from git import Repo
import re

if not os.environ.get("ACKREP_ENVIRONMENT_NAME"):
    # this env var is set in Dockerfile of env
    import pyerk as p
from ackrep_core_django_settings import settings

# settings might be accessed from other modules which import this one (core)
# noinspection PyUnresolvedReferences
from django.conf import settings
from django.core import management
from django.db import connection as django_db_connection, connections as django_db_connections

from yamlpyowl import core as ypo

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception  # for debugging only

# activate_ips_on_exception()

from . import models
from . import model_utils

# noinspection PyUnresolvedReferences
from .model_utils import get_entity_dict_from_db, get_entity_types, resolve_keys, get_entity

# noinspection PyUnresolvedReferences
from .util import (
    mod_path,
    core_pkg_path,
    root_path,
    data_path,
    ci_results_path,
    ObjectContainer,
    ResultContainer,
    InconsistentMetaDataError,
    DuplicateKeyError,
    DockerError,
    run_command,
)

from . import util


# initialize logging with default loglevel (might be overwritten by command line option)
# see https://docs.python.org/3/howto/logging-cookbook.html
defaul_loglevel = os.environ.get("ACKREP_LOG_LEVEL", logging.INFO)
logger = logging.getLogger("ackrep_logger")
FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
DATEFORMAT = "%H:%M:%S"
formatter = logging.Formatter(fmt=FORMAT, datefmt=DATEFORMAT)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(defaul_loglevel)


last_loaded_entities = []  # TODO: HACK! Data should be somehow be passed directly to import result view


valid_types = [
    "problem_class",
    "problem_specification",
    "problem_solution",
    "method",
    "doc",
    "dataset",
    "comment",
]


required_generic_meta_data = {
    "pk": "=5",
    "type": valid_types,
    "name": ">3, <100",
    "short_description": "<500",
    "version": ">5, <10",
    "tags": None,
    "creator": ">3, <100",
    "editors": None,
    "creation_date": None,
    "related_docs": None,
    "related_datasets": None,
    "external_references": None,
    "notes": None,
}


db_name = django_db_connection.settings_dict["NAME"]


def send_debug_report(send=None):
    """
    Send debug information such as relevant environmental variables to designated output (logger or stdout).

    :param send:    Function to be used for sending the message. Default: logger.debug. Alternatively: print.
    """

    if send is None:
        send = logger.debug

    row_template = "  {:<30}: {}"

    send("** ENVIRONMENT VARS: **")
    for k, v in os.environ.items():
        if k.startswith("ACKREP_"):
            send(row_template.format(k, v))

    send("** DB CONNECTION:  **")
    send(django_db_connections["default"].get_connection_params())
    send("\n")


def gen_random_entity_key():
    return "".join([c for c in secrets.token_urlsafe(10).upper() if c.isalnum()])[:5]


def get_metadata_from_file(path, check_sanity=False):
    """
    Load metadata
    :param path:
    :param check_sanity:       flag whether to check the sanity of the metadata against the models
    :return:
    """
    with open(path) as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)

    # TODO: this check is outdated -> temporarily deactivated
    if check_sanity and not set(required_generic_meta_data.keys()).issubset(data.keys()):
        msg = f"In the provided file `{path}` at least one required key is missing."
        raise KeyError(msg)

    # TODO: add more consistency checks

    return data


def convert_dict_to_yaml(data, target_path=None):
    class MyDumper(yaml.Dumper):
        """
        This class results in the preferred indentation style
        source: https://stackoverflow.com/a/39681672/333403
        """

        def increase_indent(self, flow=False, indentless=False):
            return super(MyDumper, self).increase_indent(flow, False)

    yml_txt = yaml.dump(data, Dumper=MyDumper, default_flow_style=False, sort_keys=False, indent=4)

    if target_path is not None:
        with open(target_path, "w") as f:
            f.write(yml_txt)

    return yml_txt


def render_template(tmpl_path, context, target_path=None, base_path=None, special_str="template_"):
    """
    Render a jinja2 template and save it to target_path. If target_path ist `None` (default),
    autogenerate it by dropping the then mandatory `template_` substring of the templates filename
    (or another nonempty special string).

    :param tmpl_path:   template path (relative to the modules path, usually starts with "templates/")
    :param context:     dict with context data for rendering
    :param target_path: None or string
    :param base_path:   None or string (if None then the absolute path of this module will be used)
    :param target_path: None or string
    :param special_str: default: "template_"; will be replaced by '' if target_path is given
    :return:
    """

    path, fname = os.path.split(tmpl_path)
    assert path != ""

    if base_path is None:
        base_path = mod_path

    path = os.path.join(base_path, path)

    jin_env = Environment(loader=FileSystemLoader(path))

    if target_path is None:
        assert 1 < len(special_str) < len(fname) and (fname.count(special_str) == 1)
        res_fname = fname.replace(special_str, "")
        target_path = os.path.join(path, res_fname)

    template = jin_env.get_template(fname)
    if "warning" not in context:
        time_string = current_time_str()
        context["warning"] = f"This file was autogenerated from the template: {fname} ({time_string})."
    result = template.render(context=context)

    with open(target_path, "w") as resfile:
        resfile.write(result)

    # also return the result (useful for testing)
    return target_path


def get_files_by_pattern(directory, match_func):
    """
    source:  https://stackoverflow.com/questions/8505457/how-to-crawl-folders-to-index-files
    :param directory:
    :param match_func:      example: `lambda fn: fn == "metadata.yml"`
    :return:
    """
    for path, dirs, files in os.walk(directory):
        # TODO: this should be made more robust
        if "_template" in path:
            continue
        for f in filter(match_func, files):
            yield os.path.join(path, f)


def clear_db():
    logger.info("Clearing DB...")
    management.call_command("flush", "--no-input")


# noinspection PyPep8Naming
class ACKREP_OntologyManager(object):
    """
    Manages the ontology related tasks in ackrep-core
    """

    def __init__(self):
        # noinspection PyTypeChecker
        self.OM: ypo.OntologyManager = None
        self.ocse_entity_mapping = {}

    def load_ontology(self, startdir=None, entity_list=None):
        ERK_ROOT_DIR = p.aux.get_erk_root_dir()
        TEST_DATA_PATH = os.path.join(ERK_ROOT_DIR, "erk-data", "control-theory", "control_theory1.py")
        mod1 = p.erkloader.load_mod_from_path(modpath=TEST_DATA_PATH, prefix="ct")
        p.ackrep_parser.load_ackrep_entities(startdir)
        self.ds = p.core.ds
        self.ds.rdfgraph = p.rdfstack.create_rdf_triples()

    def get_list_of_all_ontology_based_tags(self):
        qsrc = f"""PREFIX P: <{self.OM.iri}>
            SELECT ?entity
            WHERE {{
              ?entity rdf:type ?type.
              ?type rdfs:subClassOf* P:OCSE_Entity.
            }}
        """
        res = list(self.OM.make_query(qsrc))
        return res

    def run_sparql_query_and_translate_result(self, qsrc, raw=False) -> list:
        self.load_ontology()
        qsrc = self.preprocess_query(qsrc)
        res = self.ds.rdfgraph.query(qsrc)
        erk_entitites = p.aux.apply_func_to_table_cells(p.rdfstack.convert_from_rdf_to_pyerk, res)

        ackrep_entities = []
        onto_entites = []
        for tuples in erk_entitites:
            for i, e in enumerate(tuples):
                # entity is system model
                try:
                    re = e.get_relations("ct__R2950__has_corresponding_ackrep_key")
                    entity_key = re[0].relation_tuple[2]
                    assert isinstance(entity_key, str)
                    entity = get_entity(entity_key)
                    ackrep_entities.append(("?" + str(res.vars[i]), entity))
                except:
                    try:
                        entity = [e.short_key, e.R1]
                    except:
                        entity = e
                    onto_entites.append(("?" + str(res.vars[i]), entity))
        return ackrep_entities, onto_entites

    def preprocess_query(self, query):
        if "__" in query:
            prefixes = re.findall(r"[\w]*:[ ]*<.*?>", query)
            prefix_dict = {}
            for prefix in prefixes:
                parts = prefix.split(" ")
                key = parts[0]
                value = parts[-1].replace("<", "").replace(">", "")
                prefix_dict[key] = value
            print(prefix_dict)

            entities = re.findall(r"[\w]*:[\w]+__[\w]+", query)
            for e in entities:
                # check sanity
                prefix, rest = e.split(":")
                prefix = prefix + ":"
                erk_key, description = rest.split("__")

                entity_uri = prefix_dict.get(prefix) + erk_key
                entity = self.ds.get_entity_by_uri(entity_uri)

                label = description.replace("_", " ")

                msg = f"Entity label '{entity.R1}' for entity '{e}' and given label '{label}' do not match!"
                assert entity.R1 == label, msg

            new_query = re.sub(r"__[\w]+", "", query)
        else:
            new_query = query

        return new_query

    def wrap_onto_entity(self, onto_nty):
        """

        :param onto_nty:    class or instance from the ontology
        :return:            template-compatible representation
        """

        ae, oe = None, None
        if isinstance(onto_nty, self.OM.n.ACKREP_Entity):
            key = onto_nty.has_entity_key
            ae = get_entity(key)
        else:
            oe = str(onto_nty)

        return ae, oe


def load_repo_to_db(startdir, check_consistency=True):
    logger.info("Completely rebuilding DB from file system")

    clear_db()

    entity_list = crawl_files_and_load_to_db(startdir)

    if check_consistency:
        # TODO: this should be disabled during unittest to save time
        logger.debug("Create internal links between entities (only for consistency checking) ...")
        entity_dict = model_utils.get_entity_dict_from_db()

        for etype, elist in entity_dict.items():
            for entity in elist:
                resolve_keys(entity)

    global last_loaded_entities
    last_loaded_entities = entity_list

    if not os.environ.get("ACKREP_ENVIRONMENT_NAME"):
        # this env var is set in Dockerfile of env
        AOM.load_ontology(startdir, entity_list)

    return entity_list


def crawl_files_and_load_to_db(startdir, merge_request=None):
    """
    Crawl directory for metadata.yml files and import found entities. Exception
    occurs when trying to import an entity whose key already exists in the database.

    If merge_request is None:
        Try to import every entity in the directory.
    If merge_request is a MR key:
        Try to import every entity whose key doesn't already exists in the DB OR which has
        status `open` in the database. Also set merge_request to supplied key on new
        entities.
    """
    logger.debug("Searching '%s' and subdirectories for 'metadata.yml'..." % (os.path.abspath(startdir)))
    meta_data_files = list(get_files_by_pattern(startdir, lambda fn: fn == "metadata.yml"))
    meta_data_files.sort(key=str.casefold)
    entity_list = []
    logger.debug("Found %d entity metadata files" % (len(meta_data_files)))

    logger.info("Creating DB objects...")
    for md_path in meta_data_files:

        md = get_metadata_from_file(md_path)
        e = model_utils.create_entity_from_metadata(md)
        e.merge_request = merge_request

        # absolute path of directory containing metadata.yml
        base_path_abs = os.path.abspath(os.path.dirname(md_path))
        # make path relative to ackrep root path, meaning the directory that contains 'ackrep_core' and 'ackrep_data'
        # example: C:\dev\ackrep\ackrep_data\problem_solutions\solution1 --> ackrep_data\problem_solutions\solution1
        base_path_rel = os.path.relpath(base_path_abs, root_path)
        e.base_path = base_path_rel
        logger.debug((e.key, e.base_path))

        # check for duplicate keys
        get_entity(e.key, raise_error_on_empty=False)

        # store to db
        e.save()
        entity_list.append(e)

    logger.info("Added %d new entities to DB" % (len(entity_list)))
    return entity_list


def get_data_files(base_path, endswith_str=None, create_media_links=False):
    """
    walk through <base_path>/_data depending on the base_path
    and return the path of all matching files

    :param base_path: entity.base_path
    :param endswith_str:
    :param create_media_links:  if True, create symlinks in `settings.MEDIA_ROOT` to these files
    :return:
    """
    if "_data" in base_path:
        startdir = os.path.join(root_path, base_path, "_data")
    else:
        startdir = os.path.join(root_path, base_path)

    if not os.path.isdir(startdir):
        return []

    if endswith_str is None:
        # noinspection PyUnusedLocal
        def matchfunc(fn):
            return True

    else:

        def matchfunc(fn):
            return fn.endswith(endswith_str)

    abs_files = list(get_files_by_pattern(startdir, matchfunc))

    # convert absolute paths into relative paths (w.r.t. `root_path`)

    files = [f.replace(f"{root_path}{os.path.sep}", "") for f in abs_files]

    if create_media_links:
        result = []
        for abs_path, rel_path in zip(abs_files, files):
            link = rel_path.replace(os.path.sep, "_")
            abs_path_link = os.path.join(settings.MEDIA_ROOT, link)
            # always recreate link. In the previous version, removing and rebuilding the media file
            # would not renew the link and thus show the old file
            if os.path.exists(abs_path_link):
                os.unlink(abs_path_link)
            os.symlink(abs_path, abs_path_link)
            result.append(f"{settings.MEDIA_URL}{link}")

        return result
    else:
        return files


def make_method_build(method_package, accept_existing=True):
    """
    Assumption: the method is inside the repo only with its source code. In general there is a build step necessary
    (e.g. compiling source files), which is triggered by this function.

    Currently the build-step consist only of copying the source to _build/

    :param method_package:
    :param accept_existing:

    :return: full_build_path
    """

    full_base_path = os.path.join(root_path, method_package.base_path)
    full_build_path = os.path.join(full_base_path, "_build")
    full_source_path = os.path.join(full_base_path, "src")

    if os.path.isdir(full_build_path):
        if not accept_existing:
            msg = f"The path {full_build_path} does already exist, which is not expected!"
            raise ValueError(msg)
        else:
            return full_build_path

    # TODO: test for and run makescript here

    # For now just copy the source:

    shutil.copytree(full_source_path, full_build_path)

    return full_build_path


def check_generic(key: str):
    """create entity and context, create execscript, run execscript.
    This is the successor of check_solution and check_system_model

    Args:
        key (str): entity key

    Returns:
        CompletedProcess: result of execscript
    """
    entity, c = get_entity_context(key)
    scriptpath = create_execscript_from_template(entity, c)
    res = run_execscript(scriptpath)

    return res


def get_entity_context(key: str):
    """get entity and build context based on key

    Args:
        key (str): entity key

    Returns:
        models.GenericEntity, Container: entity, context dict
    """

    entity = get_entity(key)
    resolve_keys(entity)

    assert isinstance(entity, (models.SystemModel, models.ProblemSolution))

    # test entity type and get path to relevant file
    if isinstance(entity, models.ProblemSolution):
        python_file = entity.solution_file
        if python_file != "solution.py":
            msg = "Arbitrary filename will be supported in the future"
            raise NotImplementedError(msg)

    elif isinstance(entity, models.SystemModel):
        python_file = entity.system_model_file
        if python_file != "system_model.py":
            msg = "Arbitrary filename will be supported in the future"
            raise NotImplementedError(msg)
    else:
        raise NotImplementedError

    c = Container()  # this will be our easily accessible context dict for the template

    if isinstance(entity, models.ProblemSolution):
        c.solution_path = os.path.join(root_path, entity.base_path)
        assert len(entity.oc.solved_problem_list) >= 1

        if entity.oc.solved_problem_list == 0:
            msg = f"{entity}: Expected at least one solved problem."
            raise InconsistentMetaDataError(msg)

        elif len(entity.oc.solved_problem_list) == 1:
            problem_spec = entity.oc.solved_problem_list[0]
        else:
            logger.warning("Applying a solution to multiple problems is not yet supported. Taking the last one.")
            problem_spec = entity.oc.solved_problem_list[-1]

        if problem_spec.problem_file != "problem.py":
            msg = "Arbitrary filename will be supported in the future"
            raise NotImplementedError(msg)

        # TODO: handle the filename (see also template)
        c.problem_spec_path = os.path.join(root_path, problem_spec.base_path)

        # list of the build_paths
        c.method_package_list = []
        for mp in entity.oc.method_package_list:
            full_build_path = make_method_build(mp, accept_existing=True)
            assert os.path.isdir(full_build_path)
            c.method_package_list.append(full_build_path)

    elif isinstance(entity, models.SystemModel):
        c.system_model_path = os.path.join(root_path, entity.base_path)
    else:
        raise NotImplementedError

    c.ackrep_core_path = core_pkg_path

    # noinspection PyUnresolvedReferences
    assert isinstance(entity.oc, ObjectContainer)

    return entity, c


def create_execscript_from_template(entity: models.GenericEntity, c: Container, scriptpath=None):
    """create execscript from template. if scriptpath is None, the default script path
    in the respective data repo is used.
    return scriptpath

    Args:
        entity (models.GenericEntity): entity
        c (Container): context dict
        scriptpath (str or None, optional): specify where to store the script. Only usefull for
        ackrep --prepare-script. Defaults to None.

    Raises:
        NotImplementedError: if entity is neither system model nor solution

    Returns:
        path_like: path to execscript
    """

    assert isinstance(entity, (models.SystemModel, models.ProblemSolution))

    context = dict(c.item_list())

    logger.info("  ... Creating exec-script ... ")

    scriptname = "execscript.py"

    assert not entity.base_path.startswith(os.path.sep)

    # determine whether the entity comes from ackrep_data or ackrep_data_for_unittests or ackrep_data_import
    data_repo_path = pathlib.Path(entity.base_path).parts[0]
    if scriptpath is None:
        scriptpath = os.path.join(root_path, data_repo_path, scriptname)
    else:
        scriptpath = os.path.join(scriptpath, scriptname)

    logger.info(f"execscript-path: {scriptpath}")

    if isinstance(entity, models.ProblemSolution):
        render_template("templates/execscript.py.template", context, target_path=scriptpath)
    elif isinstance(entity, models.SystemModel):
        render_template("templates/execscript_system_model.py.template", context, target_path=scriptpath)
    else:
        raise NotImplementedError

    return scriptpath


def run_execscript(scriptpath):
    """run the execscript at a given location in subprocess. logs errors, returns result

    Args:
        scriptpath (path_like): path to execscript

    Returns:
        CompletedProcess: result of execscript
    """
    logger.info(f"  ... running exec-script {scriptpath} ... ")

    res = run_command(["python", scriptpath], logger=logger, capture_output=True)
    if res.returncode == 0:
        # propagate output of execscript through multiple subprocesses
        print((res.stdout), file=sys.stdout)

    return res


def clone_external_data_repo(url, mr_key):
    """Clone git repository from url into external_repos/[MERGE_REQUEST_KEY], return path"""

    external_repo_dir = os.path.join(root_path, "external_repos")
    if not os.path.isdir(external_repo_dir):
        os.mkdir(external_repo_dir)

    target_dir = os.path.join(external_repo_dir, mr_key)

    repo = Repo.clone_from(url, target_dir)
    repo.close()

    return target_dir


def current_time_str():
    time_string = time.strftime("%Y-%m-%d %H:%M:%S")
    return time_string


def create_merge_request(repo_url, title, description):
    assert title, "Merge request title can't be empty"

    key = gen_random_entity_key()
    mr_dir = clone_external_data_repo(repo_url, key)

    crawl_files_and_load_to_db(mr_dir, merge_request=key)

    last_update = current_time_str()

    mr = models.MergeRequest(
        key=key,
        title=title,
        repo_url=repo_url,
        last_update=last_update,
        description=description,
        status=models.MergeRequest.STATUS_OPEN,
    )

    with mr.repo() as repo:
        current_commit_hash = str(repo.commit())
        mr.fork_commit = current_commit_hash

    mr.save()

    return mr


def delete_merge_request(mr):
    assert mr.status == models.MergeRequest.STATUS_OPEN, "Merged merge requests may not be deleted"

    # delete associated entities from database
    delete_merge_request_entities(mr)

    # noinspection PyBroadException,PyUnusedLocal
    try:
        mr_dir = mr.repo_dir()
        shutil.rmtree(mr_dir)
    except Exception as e:
        pass  # TODO: deleting a git repository sometimes doesn't work under Windows, but isn't that important

    mr.delete()


def delete_merge_request_entities(mr):
    for e in mr.entity_list():
        e.delete()


def get_merge_request(key):
    mrs_with_key = list(models.MergeRequest.objects.filter(key=key))
    assert len(mrs_with_key) == 1, f"No or more than one merge request with key '{key}' found"

    return mrs_with_key[0]


def get_merge_request_dict():
    mr_dict = {
        status: list(models.MergeRequest.objects.filter(status=status))
        for status, _ in models.MergeRequest.STATUS_CHOICES
    }

    return mr_dict


def send_log_messages() -> None:
    """
    Create a log message of every category. Main purpose: to be used in unit tests.
    """
    # this serves as a delimiter to distinguish these messages from others
    logger.critical("- - - demo log messages - - -")
    logger.critical("critical")
    logger.error("error")
    logger.warn("warning")
    logger.info("info")
    logger.debug("debug")


def print_entity_info(key: str) -> None:
    """
    Print a report on an entity to stdout.

    :param key:    key of the respective entity
    """
    entity = get_entity(key)

    # this uses print and not logging because the user expects this output independently
    # from loglevel
    print("Entity Info")
    row_template = "  {:<20}: {}"
    print(row_template.format("name", entity.name))
    print(row_template.format("key", entity.key))
    print(row_template.format("short description", entity.short_description))
    print(row_template.format("base path", entity.base_path))
    print()


AOM = ACKREP_OntologyManager()


def check(key, try_to_use_local_image=True):
    """General function to check system model or solution, calculated inside docker image.
    The image is chosen from the compatible environment of the given entity
    structogram:
    - get_entity
    - get env key
    - try to find running env container id
    - if container exists
        - if container has INcorrect db loaded
            - shutdown
    - if container NOT already running:
        - if image available locally:
            - docker-compose run --detached env_name bash
        - else: # pull image from remote
            - docker run --detached ghcr.io/../env_name bash
        - wait for container to load its database
        - get container id
    - docker exec id ackrep -c key


    Args:
        key (str): entity key
        try_to_use_local_image (bool, optional): prefer locally build images. Only relevant for devs. Defaults to True.


    Raises:
        NotImplementedError: if key is neither solution nor system_model

    Returns:
        CompletedProcess: result of check
    """
    entity = get_entity(key)
    assert isinstance(
        entity, (models.ProblemSolution, models.SystemModel, models.Notebook)
    ), f"key {key} is of neither solution, system model nor notebook. Unsure what to do."

    # get environment name
    env_key = entity.compatible_environment
    if env_key == "" or env_key is None:
        logger.info("No environment specification found. Using default env.")
        env_key = settings.DEFAULT_ENVIRONMENT_KEY
    env_name = get_entity(env_key).name
    logger.info(f"running with environment spec: {env_name}")

    # check if environment container is already running
    container_id = look_for_running_container(env_name)

    # Container not yet running, start container, load db, wait
    # container is running detached, so the script can continue
    if container_id is None:
        logger.info(f"no container for {env_name} found, starting new one.")
        container_id = start_idle_container(env_name, try_to_use_local_image)

    # run ackrep command in already running container
    logger.info(f"Ackrep command running in Container: {container_id}")
    host_uid = get_host_uid()
    cmd = ["docker", "exec", "--user", host_uid, container_id, "ackrep", "-c", key]
    res = run_command(cmd, logger=logger, capture_output=True)
    return res


def look_for_running_container(env_name):
    """check if a container with the image in question if already running.
    If so, check if the correct db is loaded inside (this is done implicitly by comparing env vars).
    If a valid container is found, return this containers id.
    Otherwise shut down invalid containers and return None.

    Args:
        env_name (str): name of environment (e.g. default_environment)

    Returns:
        str or None: container_id
    """
    container_id = None

    # check if image is up to date with remote
    image_name = f"ghcr.io/ackrep-org/{env_name}:latest"
    cmd = ["docker", "pull", image_name]
    pull = run_command(cmd, logger=logger, capture_output=True)
    assert pull.returncode == 0, f"Unable to pull image from remote. Does '{image_name}' exist?"

    up_to_date = "Image is up to date" in pull.stdout

    if up_to_date:
        logger.info("image was up to date")
        cmd = ["docker", "ps", "--filter", f"name={env_name}", "--format", "{{.ID}}::{{.Names}}"]
        active_containers = run_command(cmd, logger=logger, capture_output=True)
        for container in active_containers.stdout.split("\n"):
            # disregard last split item
            if container != "":
                container_id = container.split("::")[0]
                logger.info(f"Running Container found: {container}")

                # check if environment container has the correct db loaded by comparing env vars
                cmd = ["docker", "exec", container_id, "printenv", "ACKREP_DATA_PATH"]
                res = run_command(cmd, capture_output=True)
                data_path_container = res.stdout.replace("\n", "").split("/")[-1]
                logger.info(f"data_path inside container: {data_path_container}")

                # no db or wrong db in container:
                if data_path_container != data_path.split("/")[-1]:
                    logger.info("Running container has wrong db loaded. Shutting down.")
                    cmd = ["docker", "stop", container_id]
                    res = run_command(cmd, logger=logger, capture_output=True)
                    assert res.returncode == 0
                    container_id = None
                break
    else:
        logger.info("image was NOT up to date")
    return container_id


def start_idle_container(env_name, try_to_use_local_image=True, port_dict=None):
    """start container for given environment in background (detached). Use local image or pull image from remote.
    set all necessary env vars. Then wait for db to be loaded inside container.
    Note: this command does not execute ackrep commands, that is done by 'exec-ing' into the idle container.

    Args:
        env_name (str): name of environment (e.g. default_environment)
        try_to_use_local_image (bool, optional): prefer locally build images. Only relevant for devs. Defaults to True.
        port_dict (dict, optional): port dictionary {container_port:host_port} to publish data from inside container.

    Returns:
        str: container_id
    """
    # try to use local docker image (for development)
    image_name = "ackrep_deployment_" + env_name
    cmd = ["docker", "images", "-q", image_name]
    res = run_command(cmd, logger=logger, capture_output=True)
    local_image_id = res.stdout.replace("\n", "")
    logger.info(f"local image id: {local_image_id}")
    if len(local_image_id) == 12 and try_to_use_local_image:  # 12 characters image id + \n
        logger.info("running local image")
        image_name = env_name  # since docker-compose doesnt use prefix

        assert os.path.isdir(f"{root_path}/ackrep_deployment"), "docker-compose file not found"
        cmd = ["docker-compose", "--file", f"{root_path}/ackrep_deployment/docker-compose.yml", "run", "-d", "--rm"]

    # no local image -> use image from github
    # this is the default for everyone who doesnt build images locally
    else:
        logger.info("running remote image")
        image_name = "ghcr.io/ackrep-org/" + env_name + ":latest"

        # ! pull image first to ensure latest version is available
        logger.info("pulling docker image")
        pull_cmd = ["docker", "pull", image_name]
        res = run_command(pull_cmd, logger=logger, capture_output=True)
        assert res.returncode == 0, f"Unable to pull image from remote. Does '{image_name}' exist?"

        logger.info("stopping old containers")
        # stop all running containers with env_name to ensure name uniqueness
        find_cmd = ["docker", "ps", "--filter", f"name={env_name}", "-q"]
        res = run_command(find_cmd, logger=logger, capture_output=True)
        if len(res.stdout) > 0:
            ids = res.stdout.split("\n")[:-1]
            for i in ids:
                stop_cmd = ["docker", "stop", i]
                run_command(stop_cmd, logger=logger, capture_output=True)

        cmd = ["docker", "run", "-d", "-ti", "--rm", "--name", env_name]
        # * Note: even though we are running the container in the background (detached -d), we still have to
        # * specify -ti (terminal, interactive) to keep the container running in idle (waiting for bash input).
        # * Otherwise, the container would stop after running the entrypoint script (load db). This is noteworthy,
        # * since -d and -ti seem to be contradictory.

    # building the docker command
    if port_dict is not None:
        cmd.extend(get_port_mapping(port_dict))

    cmd.extend(get_docker_env_vars())

    cmd.extend(get_volume_mapping())

    cmd.extend([image_name, "bash"])

    logger.info(f"docker command: {cmd}")
    res = run_command(cmd, logger=logger, capture_output=True)
    if res.returncode != 0:
        raise DockerError("container was not started correctly")
    else:
        # running a container detached returns its id
        container_id = res.stdout.replace("\n", "")

    # wait for db to be loaded, since the container is running detached
    start = time.time()
    while True:
        logger.info("waiting for db to be loaded...")
        # Test with "definately existing" key UXMFA and not {key} to avoid potential issues with new keys
        cmd = ["docker", "exec", container_id, "ackrep", "--show-entity-info", "UXMFA"]
        res = run_command(cmd, capture_output=True)
        if res.returncode == 0:
            break
        else:
            time.sleep(1)
            if time.time() - start > 60:
                logger.error(
                    f"Timeout: Cant find key UXMFA in database, \
                    which probably did not load correctly. Aborting."
                )
                raise TimeoutError(
                    f"Timeout: Cant find key UXMFA in database, \
                    which probably did not load correctly. Aborting."
                )
    logger.info(f"New env container started after {round(time.time() - start, 1)} seconds.")
    return container_id


def get_docker_env_vars():
    """rebuild environment variables suitable inside docker container
    env var is set by unittest
    return array with flags and paths to extend docker cmd
    """
    # ut case
    if os.environ.get("ACKREP_DATABASE_PATH") is not None and os.environ.get("ACKREP_DATA_PATH") is not None:
        msg = (
            f'env variables set: ACKREP_DATABASE_PATH={os.environ.get("ACKREP_DATABASE_PATH")}\n'
            + ' ACKREP_DATA_PATH=os.environ.get("ACKREP_DATA_PATH")'
        )
        logger.info(msg)
        database_path = os.path.join("/code/ackrep_core", os.path.split(os.environ.get("ACKREP_DATABASE_PATH"))[-1])
        ackrep_data_path = os.path.join("/code", os.path.split(os.environ.get("ACKREP_DATA_PATH"))[-1])
        cmd_extension = ["-e", f"ACKREP_DATABASE_PATH={database_path}", "-e", f"ACKREP_DATA_PATH={ackrep_data_path}"]
    # nominal case
    else:
        logger.info(
            f"env var ACKREP_DATABASE_PATH, ACKREP_DATA_PATH no set, using defaults: db.sqlite3 and {data_path}"
        )
        database_path = os.path.join("/code/ackrep_core", "db.sqlite3")
        ackrep_data_path = os.path.join("/code", data_path)
        cmd_extension = ["-e", f"ACKREP_DATABASE_PATH={database_path}", "-e", f"ACKREP_DATA_PATH={ackrep_data_path}"]
    logger.info(f"ACKREP_DATABASE_PATH {database_path}")
    logger.info(f"ACKREP_DATA_PATH {ackrep_data_path}")

    # user id of host
    host_uid = get_host_uid()
    cmd_extension.extend(["-e", f"HOST_UID={host_uid}"])

    return cmd_extension


def get_host_uid():
    # user id of host
    host_uid = os.environ.get("HOST_UID")
    if host_uid is not None:
        logger.info(f"HOST_UID env var set {host_uid}")
    else:
        logger.info(f"HOST_UID env var not set.")
        host_uid = os.getuid()
    logger.info(f"Using host uid {host_uid} inside the container.")
    return str(host_uid)


def get_volume_mapping():
    """mount the appropriate data repo"""

    # nominal case
    if os.environ.get("CI") != "true":
        logger.info(f"data path: {data_path}")
        target = os.path.split(data_path)[1]
        cmd_extension = ["-v", f"{data_path}:/code/{target}"]
    # circleci unittest case
    else:
        # volumes cant be mounted in cirlceci, this is the workaround,
        # see https://circleci.com/docs/2.0/building-docker-images/#mounting-folders
        # dummy is created in .circleci/config.yaml
        cmd_extension = ["--volumes-from", "dummy"]

    cmd_extension.extend(["-v", "/etc/localtime:/etc/localtime"])

    return cmd_extension


def get_port_mapping(port_dict):
    """port_dict {container_port:host_port}"""
    assert type(port_dict) == dict, f"Port dictionary {port_dict} is not a dict."
    cmd_extension = []
    for key, value in port_dict.items():
        cmd_extension.extend(["-p", f"{key}:{value}"])
    return cmd_extension


def download_and_store_artifacts(branch_name):
    """download artifacts using the directory structure established in CI"""
    save_cwd = os.getcwd()
    os.chdir(root_path)

    circle_token = settings.SECRET_CIRCLECI_API_KEY
    cmd = [
        f"""curl -H 'Circle-Token: {circle_token}' \
    https://circleci.com/api/v1.1/project/github/ackrep-org/ackrep_data/latest/artifacts?branch={branch_name} \
    | grep -o 'https://[^"]*' \
    | wget --force-directories --no-host-directories --cut-dirs=6 --verbose --header 'Circle-Token: {circle_token}' \
    --input-file -"""
    ]
    #
    # --force-directories       keeps directory structure
    # --no-host-directories     omits directory with host url
    # --cut-dirs=6              omits next 6 directories --> artifact dir

    res = run_command(cmd, logger=logger, capture_output=True, shell=True)
    assert res.returncode == 0, "Unable to collect results from circleci."

    # it is assumed, that the last CI reports on github and the manually downloaded one (artifact) are identical
    repo = Repo(f"{root_path}/ackrep_ci_results")
    # run_command(["git", "-C", "./ackrep_ci_results", "fetch"], capture_output=False)
    # run_command(["git", "-C", "./ackrep_ci_results", "status"], capture_output=False)
    # for file in repo.untracked_files:
    #     os.remove(os.path.join(ci_results_path, file))
    # run_command(["git", "-C", "./ackrep_ci_results", "status"], capture_output=False)
    repo.remotes.origin.pull()
    # run_command(["git", "-C", "./ackrep_ci_results", "status"], capture_output=False)

    os.chdir(save_cwd)


"""
Debug Commands:

for debugging containers:
docker-compose --file ../ackrep_deployment/docker-compose.yml run --rm -e ACKREP_DATABASE_PATH=/code/ackrep_core/db.sqlite3 -e ACKREP_DATA_PATH=/home/julius/Documents/ackrep/ackrep_data -v /home/julius/Documents/ackrep/ackrep_data:/code/ackrep_data -e HOST_UID=1000 default_conda_environment bash
docker run --rm -ti -e ACKREP_DATABASE_PATH=/code/ackrep_core/db.sqlite3 -e ACKREP_DATA_PATH=/home/julius/Documents/ackrep/ackrep_data -v /home/julius/Documents/ackrep/ackrep_data:/code/ackrep_data ghcr.io/ackrep-org/default_environment bash

downloading artifacts from circle
curl -H "Circle-Token: $CIRCLE_TOKEN" https://circleci.com/api/v1.1/project/github/ackrep-org/ackrep_data/latest/artifacts \
   | grep -o 'https://[^"]*' \
   | wget --force-directories --no-host-directories --cut-dirs=5 --verbose --header "Circle-Token: $CIRCLE_TOKEN" --input-file -
"""
