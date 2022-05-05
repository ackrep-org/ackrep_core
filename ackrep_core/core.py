import secrets
import yaml
import os, sys
import pathlib
import time
import subprocess
import shutil
import logging
from typing import List
from jinja2 import Environment, FileSystemLoader
from ipydex import Container  # for functionality
from git import Repo

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
    ObjectContainer,
    ResultContainer,
    InconsistentMetaDataError,
    DuplicateKeyError,
)

from . import util

# initialize logging with default loglevel (might be overwritten by command line option)
# see https://docs.python.org/3/howto/logging-cookbook.html
defaul_loglevel = os.environ.get("ACKREP_LOG_LEVEL", logging.WARNING)
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

    def load_ontology(self, startdir, entity_list: List[models.GenericEntity]) -> None:
        """
        load the yml file of the ontology and create instances based on entity_list
        :param startdir:
        :param entity_list:    list of ackrep entities
        :return:
        """

        if isinstance(self.OM, ypo.OntologyManager):
            # Nothing to do
            return

        assert len(models.ProblemSpecification.objects.all()) > 0, "no ProblemSpecification found"
        assert len(entity_list) > 0, "empty entity_list"

        path = os.path.join(startdir, "ontology", "ocse-prototype-01.owl.yml")
        self.OM = ypo.OntologyManager(path, world=ypo.owl2.World())

        mapping = {}
        for cls in self.OM.n.ACKREP_Entity.subclasses():
            mapping[cls.name.replace("ACKREP_", "")] = cls

        for e in entity_list:
            cls = mapping.get(type(e).__name__)
            if cls:
                # instantiation of owlready classes has side effects -> instances are tracked
                # noinspection PyUnusedLocal
                instance = cls(has_entity_key=e.key, name=e.name)

                tag_list = util.smart_parse(e.tag_list)
                assert isinstance(tag_list, list), f"unexpexted type of e.tag_list: {type(tag_list)}"
                for tag in tag_list:
                    if tag.startswith("ocse:"):
                        ocse_concept_name = tag.replace("ocse:", "")

                        # see yamlpyowl doc (README) wrt proxy_individuals
                        proxy_individual_name = f"i{ocse_concept_name}"
                        res = self.OM.onto.search(iri=f"*{proxy_individual_name}")
                        if not len(res) == 1:
                            msg = f"Unknown tag: {tag}. Maybe a spelling error?"
                            raise NameError(msg)
                        proxy_individual = res[0]
                        instance.has_ontology_based_tag.append(proxy_individual)
                    # IPS(e.key == "M4PDA")
            else:
                logger.warning(f"unknown entity type: {e}")

        if len(list(self.OM.n.ACKREP_ProblemSolution.instances())) == 0:
            msg = "Instances of ACKREP_ProblemSolution are missing. This is unexpected."
            IPS()
            raise ValueError(msg)

        for ocse_entity in self.OM.n.OCSE_Entity.instances():
            self.ocse_entity_mapping[ocse_entity.name] = ocse_entity

        self.generate_bottom_up_tag_relations()

    def generate_bottom_up_tag_relations(self) -> None:
        """
        Tags should be as specific as possible, e.g. if applicable `Linear_State_Space_System` is prefererred over
        `State_Space_System`. However, as every Linear_State_Space_System also is a State_Space_System, a search for the
        latter (more general tag) should also contain entities which are tagged with the former (more special tag).

        This is achieved by this function which automatically adds tags of superclasses.

        :return:    None
        """

        for ackrep_entity, ocse_entity in self.OM.n.has_ontology_based_tag.get_relations():
            ocse_class = ocse_entity.is_a[0]
            self._recursively_add_tags(ackrep_entity, ocse_class)

    def _recursively_add_tags(self, ackrep_entity: ypo.Thing, ocse_class: ypo.owl2.ThingClass) -> None:

        final_class = self.OM.n.OCSE_Entity
        if ocse_class == final_class:
            return

        parent_classes = ocse_class.is_a
        assert len(parent_classes) == 1  # ensure asserted single inheritance (otherwise things get more complicated)
        parent_class = parent_classes[0]
        # this is faster then access via the ontology
        proxy_individual_name = f"i{parent_class.name}"
        proxy_individual = self.ocse_entity_mapping.get(proxy_individual_name)

        if proxy_individual is None:
            msg = f"could not find {proxy_individual_name} in the ontology"
            raise NameError(msg)

        ackrep_entity.has_ontology_based_tag.append(proxy_individual)

        self._recursively_add_tags(ackrep_entity, parent_class)

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

    def run_sparql_query_and_translate_result(self, qsrc, raw=False) -> (list, list):
        """

        :param qsrc:    sparl source of the query
        :param raw:     flag to return the complete result in onto_entites

        :return:        2-tuple of lists: (ackrep_entities, onto_entites)
                        (onto_entites contains everything which is not an ACKREP_Entity)
        """

        self.load_ontology(data_path, entity_list=model_utils.all_entities())

        assert isinstance(self.OM, ypo.OntologyManager)
        res = list(self.OM.make_query(qsrc))
        if raw:
            return [], res

        ackrep_entities = []
        onto_entites = []
        for onto_nty in res:
            ae, oe = self.wrap_onto_entity(onto_nty)
            if ae is not None:
                ackrep_entities.append(ae)
            if oe is not None:
                onto_entites.append(oe)
        return ackrep_entities, onto_entites

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
        logger.debug(e.key, e.base_path)

        duplicates = get_entities_with_key(e.key)
        if (
            merge_request is None
            or not duplicates
            or all([d.status() == models.MergeRequest.STATUS_OPEN for d in duplicates])
        ):
            # try to import entity
            if duplicates:
                raise DuplicateKeyError(e.key)

            # store to db
            e.save()
            entity_list.append(e)

    logger.info("Added %d new entities to DB" % (len(entity_list)))
    return entity_list


def get_data_files(base_path, endswith_str=None, create_media_links=False):
    """
    walk through <base_path>/_solution_data or <base_path>/_system_model_data depending on the base_path
    and return the path of all matching files

    :param base_path: entity.base_path
    :param endswith_str:
    :param create_media_links:  if True, create symlinks in `settings.MEDIA_ROOT` to these files
    :return:
    """
    if "system_models" in base_path:
        startdir = os.path.join(root_path, base_path, "_system_model_data")
    elif "problem_solutions" in base_path:
        startdir = os.path.join(root_path, base_path, "_solution_data")
    else:
        raise FileNotFoundError("invalid path!")

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
            if not os.path.exists(abs_path_link):
                os.link(abs_path, abs_path_link)
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


# TODO: merge with `get_entity_dict_from_db`
def get_entities_with_key(key, raise_error_on_empty=False):
    """
    get all entities in the database that have a specific key
    """
    entity_types = model_utils.get_entity_types()
    entities_with_key = []

    for et in entity_types:
        entities_with_key += list(et.objects.filter(key=key))

    if raise_error_on_empty and not entities_with_key:
        n = len(model_utils.all_entities())

        msg = (
            f"No entity with key {key} could be found among the {n} entities in database. "
            f"Make sure the database was correctly initialized.\n`dbname`='{db_name}'\n\n"
            "If this occurs in a unit test, see devdocs for details."
        )
        raise KeyError(msg)

    return entities_with_key


def check_solution(key):
    """

    :param key:                 entity key of the ProblemSolution
    :return:
    """
    sol_entity, c = _create_entity(key, "solution")

    assert len(sol_entity.oc.solved_problem_list) >= 1

    if sol_entity.oc.solved_problem_list == 0:
        msg = f"{sol_entity}: Expected at least one solved problem."
        raise InconsistentMetaDataError(msg)

    elif len(sol_entity.oc.solved_problem_list) == 1:
        problem_spec = sol_entity.oc.solved_problem_list[0]
    else:
        logger.warning("Applying a solution to multiple problems is not yet supported. Taking the last one.")
        problem_spec = sol_entity.oc.solved_problem_list[-1]

    if problem_spec.problem_file != "problem.py":
        msg = "Arbitrary filename will be supported in the future"
        raise NotImplementedError(msg)

    # TODO: handle the filename (see also template)
    c.problem_spec_path = os.path.join(root_path, problem_spec.base_path)

    # list of the build_paths
    c.method_package_list = []
    for mp in sol_entity.oc.method_package_list:
        full_build_path = make_method_build(mp, accept_existing=True)
        assert os.path.isdir(full_build_path)
        c.method_package_list.append(full_build_path)

    res = _run_execscript_from_template(sol_entity, c, "solution")

    return res


def check_system_model(key):
    """
    run the script that executes the simulation
    similar to check_solution
    :param key:                 entity key of the SystemModel
    :return:    result of evaluation of simulation
    """
    system_model_entity, c = _create_entity(key, "system_model")

    res = _run_execscript_from_template(system_model_entity, c, "system_model")

    return res


def _create_entity(key, type):
    """create entity for check solution and check system model"""
    assert type in ("solution", "system_model")

    entity = get_entity(key)
    resolve_keys(entity)

    # test entity type and get path to relevant file
    if type == "solution":
        assert isinstance(entity, models.ProblemSolution)
        python_file = entity.solution_file
        if python_file != "solution.py":
            msg = "Arbitrary filename will be supported in the future"
            raise NotImplementedError(msg)

    else:
        assert isinstance(entity, models.SystemModel)
        python_file = entity.system_model_file
        if python_file != "system_model.py":
            msg = "Arbitrary filename will be supported in the future"
            raise NotImplementedError(msg)

    c = Container()  # this will be our easily accessible context dict for the template

    if type == "solution":
        c.solution_path = os.path.join(root_path, entity.base_path)
    else:
        c.system_model_path = os.path.join(root_path, entity.base_path)

    c.ackrep_core_path = core_pkg_path

    # noinspection PyUnresolvedReferences
    assert isinstance(entity.oc, ObjectContainer)

    return entity, c


def _run_execscript_from_template(entity, c, type):
    assert type in ("solution", "system_model")

    context = dict(c.item_list())

    logger.info("  ... Creating exec-script ... ")

    scriptname = "execscript.py"

    assert not entity.base_path.startswith(os.path.sep)

    # determine whether the entity comes from ackrep_data or ackrep_data_for_unittests ore ackrep_data_import
    data_repo_path = pathlib.Path(entity.base_path).parts[0]
    scriptpath = os.path.join(root_path, data_repo_path, scriptname)
    if type == "solution":
        render_template("templates/execscript.py.template", context, target_path=scriptpath)
    else:
        render_template("templates/execscript_system_model.py.template", context, target_path=scriptpath)

    logger.info(f"  ... running exec-script {scriptpath} ... ")

    # TODO: plug in containerization here:
    # Note: this hangs on any interactive element inside the script (such as IPS)
    res = subprocess.run(["python", scriptpath], text=True, capture_output=True)
    res.exited = res.returncode
    if res.returncode == 2:
        if res.stdout:
            logger.warning(res.stdout)
    elif res.returncode != 0:
        logger.error(f"Error in execscript: {scriptpath}")
        # some error messages live on stderr, some on stderr
        if res.stdout:
            logger.error(res.stdout)
        if res.stderr:
            logger.error(res.stderr)

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
    (entity,) = get_entities_with_key(key, raise_error_on_empty=True)

    # this uses print and not logging because the user expects this output independently
    # from loglevel
    print("Entity Info",)
    row_template = "  {:<20}: {}"
    print(row_template.format("name", entity.name))
    print(row_template.format("key", entity.key))
    print(row_template.format("short description", entity.short_description))
    print(row_template.format("base path", entity.base_path))
    print()


AOM = ACKREP_OntologyManager()
