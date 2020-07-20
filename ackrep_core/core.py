import secrets
import yaml
import os
import pathlib
import time
import subprocess
import shutil
from jinja2 import Environment, FileSystemLoader
from ipydex import Container  # for functionality
from git import Repo
import hashlib
from .util import *
from . import models

# noinspection PyUnresolvedReferences
from ipydex import IPS  # for debugging only

# settings might be accessd from other modules which import this one (core)
# noinspection PyUnresolvedReferences
from django.conf import settings

from . import models

# path of this module (i.e. the file core.py)
mod_path = os.path.dirname(os.path.abspath(__file__))

# path of this package (i.e. the directory ackrep_core)
core_pkg_path = os.path.dirname(mod_path)

# path of the general project root (expedted to contain ackrep_data, ackrep_core, ackrep_deployment, ...)
root_path = os.path.abspath(os.path.join(mod_path, "..", ".."))

# paths for (ackrep_data and its test-related clone)
data_path = os.path.join(root_path, "ackrep_data")
data_test_repo_path = os.path.join(root_path, "ackrep_data_for_unittests")

last_loaded_entities = []  # TODO: HACK! Data should be somehow be passed directly to import result view


class ResultContainer(Container):
    pass

class InconsistentMetaDataError(ValueError):
    """Raised when an entity with inconsistent metadata is loaded."""
    pass


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
        data = yaml.load(f, Loader=yaml.FullLoader)

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


def get_entity(key, hint=None):
    # TODO: remove argument `hint`

    assert hint is None, "the path-hint in the caller must be removed now"

    results = []
    for entity_type in models.all_entities:
        res = entity_type.objects.filter(key=key)
        results.extend(res)

    if len(results) == 0:
        msg = f"No entity with key '{key}' could be found. Make sure that the database is in sync with repo."
        # TODO: this should be a 404 Error in the future
        raise ValueError(msg)
    elif len(results) > 1:
        msg = f"There have been multiple entities with key '{key}'. "
        raise ValueError(msg)

    entity = results[0]

    return entity


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
        time_string = time.strftime("%Y-%m-%d %H:%M:%S")
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

    for e in models.all_entities:
        e.objects.all().delete()


def load_repo_to_db(startdir, check_consistency=True):
    print("Completely rebuilding DB from file system")

    print("Clearing DB...")
    clear_db()

    entity_list = crawl_files_and_load_to_db(startdir)

    if check_consistency:
        # TODO: this should be disabled during unittest to save time
        print("Create internal links between entities (only for consistency checking) ...")
        entity_dict = get_entity_dict_from_db()

        for etype, elist in entity_dict.items():
            for entity in elist:
                resolve_keys(entity)

    global last_loaded_entities
    last_loaded_entities = entity_list
    
    return entity_list


def extend_db(startdir):
    print("Extending database with entities in repository")

    entity_list = crawl_files_and_load_to_db(startdir, warn_duplicate_key=False)
    global last_loaded_entities
    last_loaded_entities = entity_list

    return entity_list


def crawl_files_and_load_to_db(startdir, warn_duplicate_key=True):
    print("Searching '%s' and subdirectories for 'metadata.yml'..." % (os.path.abspath(startdir)))
    meta_data_files = list(get_files_by_pattern(startdir, lambda fn: fn == "metadata.yml"))
    entity_list = []
    print("Found %d entity metadata files" % (len(meta_data_files)))

    print("Creating DB objects...")
    for md_path in meta_data_files:

        md = get_metadata_from_file(md_path)
        e = models.create_entity_from_metadata(md)
        # absolute path of directory containing metadata.yml
        base_path_abs = os.path.abspath(os.path.dirname(md_path))
        # make path relative to ackrep root path, meaning the directory that contains 'ackrep_core' and 'ackrep_data'
        # example: C:\dev\ackrep\ackrep_data\problem_solutions\solution1 --> ackrep_data\problem_solutions\solution1
        base_path_rel = os.path.relpath(base_path_abs, root_path)
        e.base_path = base_path_rel
        print(e.key, e.base_path)

        # check DB if key already exists, if so, skip entity
        duplicates = get_entities_with_key(e.key)
        if duplicates:
            if (warn_duplicate_key):
                print(yellow("Warning: key %s already used in '%s'" % (e.key, duplicates[0].base_path)))
            print("Skipping...")
            continue

        # store to db
        e.save()
        entity_list.append(e)

    print("Added %d new entities to DB" % (len(entity_list)))
    return entity_list


# This function is needed during the prototype phase due to some design simplification
# once the models have stabilized this should be deprecated
def resolve_keys(entity):
    """
    For quick progress almost all model fields are strings. This function converts those fields, which contains keys
    to contain the real reference (or list of references).
    :param entity:
    :return:
    """

    entity_type = type(entity)
    fields = entity_type.get_fields()

    # endow every entity with an object container:

    entity.oc = Container()

    for field in fields:
        if isinstance(field, models.EntityKeyField):

            # example: get the content of entity.predecessor_key
            refkey = getattr(entity, field.name)
            if refkey:
                try:
                    ref_entity = get_entity(refkey)
                except ValueError as ve:
                    msg = f"Bad refkey detected when processing field {field.name} of {entity}. " \
                        f"Original error: {ve.args[0]}"
                    raise InconsistentMetaDataError(msg)
            else:
                ref_entity = None

            # save the real object to the object container (allow later access)
            setattr(entity.oc, field.name, ref_entity)

        elif isinstance(field, models.EntityKeyListField):
            refkeylist_str = getattr(entity, field.name)

            if refkeylist_str is None:
                msg = f"There is a problem with the field {field.name} in entity {entity.key}."
                raise InconsistentMetaDataError(msg)

            refkeylist = yaml.load(refkeylist_str, Loader=yaml.FullLoader)
            if refkeylist in (None, [], [""]):
                refkeylist = []

            try:
                entity_list = [get_entity(refkey) for refkey in refkeylist]
            except ValueError as ve:
                msg = f"Bad refkey detected when processing field {field.name} of {entity}. "\
                      f"Original error: {ve.args[0]}"
                raise InconsistentMetaDataError(msg)
            setattr(entity.oc, field.name, entity_list)


def get_solution_data_files(sol_base_path, endswith_str=None, create_media_links=False):
    """
    walk through <base_path>/_solution_data and return the path of all matching files

    :param sol_base_path:
    :param endswith_str:
    :param create_media_links:  if True, create symlinks in `settings.MEDIA_ROOT` to these files
    :return:
    """

    startdir = os.path.join(root_path, sol_base_path, "_solution_data")

    if not os.path.isdir(startdir):
        return []

    if endswith_str is None:
        def matchfunc(fn): return True
    else:
        def matchfunc(fn): return fn.endswith(endswith_str)

    abs_solution_files = list(get_files_by_pattern(startdir, matchfunc))

    # convert absolute paths into relative paths (w.r.t. `root_path`)

    solution_files = [f.replace(f"{root_path}{os.path.sep}", "") for f in abs_solution_files]

    if create_media_links:
        result = []
        for abs_path, rel_path in zip(abs_solution_files, solution_files):
            link = rel_path.replace(os.path.sep, "_")
            abs_path_link = os.path.join(settings.MEDIA_ROOT, link)
            if not os.path.exists(abs_path_link):
                os.symlink(abs_path, abs_path_link)
            result.append(f"{settings.MEDIA_URL}{link}")

        return result
    else:
        return solution_files


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


def get_entity_dict_from_db():
    """
    get all entities which are currently in the database
    :return:
    """
    entity_type_list = models.get_entities()

    entity_dict = {}

    for et in entity_type_list:
        object_list = list(et.objects.all())

        entity_dict[et.__name__] = object_list

    return entity_dict


# TODO: merge with `get_entity_dict_from_db`
def get_entities_with_key(key):
    """
    get all entities in the database that have a specific key
    """
    entity_types = models.get_entities()
    entities_with_key = []

    for et in entity_types:
        entities_with_key += list(et.objects.filter(key=key))

    return entities_with_key


def get_available_solutions(problem):
    all_solutions = models.ProblemSolution.objects.all()

    available_solutions = []
    for sol in all_solutions:
        resolve_keys(sol)
        solved_problem_keys = [prob.key for prob in sol.oc.solved_problem_list]
        if (problem.key in solved_problem_keys):
            available_solutions.append(sol)

    return available_solutions


def check_solution(key):
    """

    :param key:                 entity key of the ProblemSolution
    :return:
    """

    sol_entity = get_entity(key)
    resolve_keys(sol_entity)

    assert isinstance(sol_entity, models.ProblemSolution)

    # get path for solution
    solution_file = sol_entity.solution_file

    if solution_file != "solution.py":
        msg = "Arbitrary filename will be supported in the future"
        raise NotImplementedError(msg)

    c = Container()  # this will be our easily accessible context dict for the template

    # TODO: handle the filename (see also template)
    c.solution_path = os.path.join(root_path, sol_entity.base_path)

    c.ackrep_core_path = core_pkg_path

    assert len(sol_entity.oc.solved_problem_list) >= 1

    if sol_entity.oc.solved_problem_list == 0:
        msg = f"{sol_entity}: Expected at least one solved problem."
        raise InconsistentMetaDataError(msg)

    elif sol_entity.oc.solved_problem_list == 1:
        problem_spec = sol_entity.oc.solved_problem_list[0]
    else:
        print("Applying a solution to multiple problems is not yet supported. Taking the last one.")
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

    context = dict(c.item_list())

    print("  ... Creating exec-script ... ")

    scriptname = "execscript.py"

    assert not sol_entity.base_path.startswith(os.path.sep)

    # determine whether the entity comes from ackrep_data or ackrep_data_for_unittests ore ackrep_data_import
    data_repo_path = pathlib.Path(sol_entity.base_path).parts[0]
    scriptpath = os.path.join(root_path, data_repo_path, scriptname)
    render_template("templates/execscript.py.template", context, target_path=scriptpath)

    print(f"  ... running exec-script {scriptpath} ... ")

    # TODO: plug in containerization here:
    # Note: this hangs on any interactive element inside the script (such as IPS)
    res = subprocess.run(["python", scriptpath], capture_output=True)
    res.exited = res.returncode
    res.stdout = res.stdout.decode("utf8")
    res.stderr = res.stderr.decode("utf8")

    return res


def clone_external_data_repo(url, remove_existing=True):
    m = hashlib.sha1()
    m.update(url.encode())
    url_hash = m.hexdigest()

    external_repo_dir = os.path.join(root_path, "external_repos")
    if not os.path.isdir(external_repo_dir):
        os.mkdir(external_repo_dir)

    target_dir = os.path.join(external_repo_dir, url_hash)

    if remove_existing and os.path.isdir(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)

    repo = Repo.clone_from(url, target_dir)
    repo.close()

    return target_dir


def clone_git_repo(giturl):

    raise NotImplementedError ("just a dummy, not yet tested")
    res = subprocess.run(["git", "clone", giturl], capture_output=True)
    res.exited = res.returncode
    res.stdout = res.stdout.decode("utf8")
    res.stderr = res.stderr.decode("utf8")
