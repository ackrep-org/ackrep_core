import os
from django.db import models
from typing import Union, Optional, Dict, Tuple
from django.template.loader import get_template
from django.urls import reverse
import urllib
import itertools
from django.db.utils import OperationalError
from django.db import transaction
from addict import Addict as Container
from ipydex import IPS, activate_ips_on_exception
import re

from ackrep_core_django_settings import settings
from ackrep_core.models import PyerkEntity, LanguageSpecifiedString

activate_ips_on_exception()

if not os.environ.get("ACKREP_ENVIRONMENT_NAME"):
    # this env var is set in Dockerfile of env
    import pyerk as p
    from pyerk.auxiliary import get_erk_root_dir

    ERK_ROOT_DIR = get_erk_root_dir()

    # Flag to determine if tests are running
    RUNNING_TESTS = False

    # TODO: This should be read from a config file
    ERK_DATA_PATH = os.path.join(ERK_ROOT_DIR, settings.ERK_DATA_REL_PATH)
    ERK_DATA_MOD_NAME = os.path.split(ERK_DATA_PATH)[1]



def _entity_sort_key(entity, subqueries) -> Tuple[int, str, int]:
    """
    Convert an short_key of an entity to a tuple which is used for sorting.

    (Reminder: second character is either a digit or "a" for autocreted items)

    "I25" -> ("I", 25)
    "I1200" -> ("I", 1200)      (should come after I25)
    "Ia1100" -> ("xI", 8234)    (auto-created items should come last)


    :param entity:
    :return:
    """

    uri = entity.uri
    label = p.ds.get_entity_by_uri(uri).R1
    descr = entity.description

    relevance = 0
    for sq in subqueries:
        if sq in uri:
            relevance -= 5
        if label and sq in label:
            relevance -= 2
        if descr and sq in descr:
            relevance -= 1

    mod_uri, sk = uri.split(p.settings.URI_SEP)

    if sk[1].isdigit():
        num = int(sk[1:])
        letter = sk[0]
        # return
    else:
        num = int(sk[2:])
        letter = f"x{sk[0]}"

    return relevance, letter, num


def render_entity_inline(entity: Union[PyerkEntity, p.Entity], **kwargs) -> str:

    # allow both models.Entity (from db) and "code-defined" pyerk.Entity
    if isinstance(entity, p.Entity):
        code_entity = entity
    elif isinstance(entity, PyerkEntity):
        code_entity = p.ds.get_entity_by_uri(entity.uri)
    else:
        # TODO: improve handling of literal values
        assert isinstance(entity, (str, int, float, complex))
        code_entity = entity

    entity_dict = represent_entity_as_dict(code_entity)
    template = get_template(entity_dict["template"])

    highlight_text = kwargs.pop("highlight_text", None)

    if highlight_text:
        new_data = {}
        replacement_exceptions = entity_dict.get("_replacement_exceptions", [])
        for key in entity_dict.keys():
            if key.startswith("_") or key in replacement_exceptions:
                continue
            value = entity_dict[key]
            new_key = f"hl_{key}"

            raw = ""
            for ht in highlight_text:
                if len(raw) > 0:
                    raw += "|"
                raw += f"(?:{ht})"
            pattern = re.compile(raw, re.I)

            def repl(match):
                for ht in highlight_text:
                    if match.group(0).lower() == ht.lower():
                        return f"<strong>{ht}</strong>"
                assert False

            new_data[new_key] = value = re.sub(pattern, repl, value)

        entity_dict.update(new_data)

    entity_dict.update(kwargs)

    ctx = {
        "c": entity_dict,
        #  copy some items to global context (where the template expects them)
        # background: these options are in global context because the template is also used like
        # {% include main_entity.template with c=main_entity omit_label=True %}
        # where `with c.omit_label=True` is invalid template syntax
        **{k: v for k, v in kwargs.items() if k in ("omit_label", "include_description")},
    }
    rendered_entity = template.render(context=ctx)
    return rendered_entity


def represent_entity_as_dict(code_entity: Union[PyerkEntity, object]) -> dict:

    if isinstance(code_entity, p.Entity):

        # this is used where the replacement for highlighting is done
        _replacement_exceptions = []
        try:
            generalized_label = code_entity.get_ui_short_representation()
            _replacement_exceptions.append("label")
        except AttributeError:
            generalized_label = code_entity.R1

        res = {
            "short_key": code_entity.short_key,
            "label": generalized_label,
            "description": str(code_entity.R2),
            "template": "ackrep_web/widgets/widget-entity-inline.html",
            "_replacement_exceptions": _replacement_exceptions,
            "sparql_text": get_sparql_text(code_entity),
        }
    else:
        # assume we have a literal
        res = {
            "value": repr(code_entity),
            "template": "ackrep_web/widgets/widget-literal-inline.html",
        }

    return res


def reload_data_if_necessary(force: bool = False, speedup: bool = True) -> Container:
    res = Container()
    res.modules = reload_modules_if_necessary(force=force)

    # TODO: test if db needs to be reloaded
    res.db = load_erk_entities_to_db(speedup=speedup)

    return res


def reload_modules_if_necessary(force: bool = False) -> int:
    count = 0

    # load ocse
    if force or p.settings.OCSE_URI not in p.ds.uri_prefix_mapping.a:
        mod = p.erkloader.load_mod_from_path(
            ERK_DATA_PATH,
            prefix="ct",
            modname=ERK_DATA_MOD_NAME,
        )
        count += 1

    # load ackrep entities
    # if force or p.ackrep_parser.__URI__ not in p.ds.uri_prefix_mapping.a:
    #     p.ackrep_parser.load_ackrep_entities(base_path=None, strict=True)
    #     count += 1

    return count


def load_erk_entities_to_db(speedup: bool = True) -> int:
    """
    Load data from python-module into data base to allow simple searching

    :param speedup:     default True; flag to determine if transaction.set_autocommit(False) should be used
                        this significantly speeds up the start of the development server but does not work well
                        with django.test.TestCase (where we switch it off)

    :return:            number of entities loaded
    """

    # delete all existing data (if database already exisits)
    try:
        PyerkEntity.objects.all().delete()
        LanguageSpecifiedString.objects.all().delete()
    except OperationalError:
        # db does not yet exist. The functions is probably called during `manage.py migrate` or similiar.
        return 0

    if RUNNING_TESTS:
        speedup = False

    # repopulate the databse with items and relations (and auxiliary objects)
    _load_entities_to_db(speedup=speedup)

    n = len(PyerkEntity.objects.all())
    n += len(LanguageSpecifiedString.objects.all())

    return n


def _load_entities_to_db(speedup: bool) -> None:

    # this pattern is based on https://stackoverflow.com/a/31822405/333403
    try:
        if speedup:
            transaction.set_autocommit(False)
        __load_entities_to_db(speedup=speedup)
    except Exception:
        if speedup:
            transaction.rollback()
        raise
    else:
        if speedup:
            transaction.commit()
    finally:
        if speedup:
            from ipydex import IPS, activate_ips_on_exception

            transaction.set_autocommit(True)


def __load_entities_to_db(speedup: bool) -> None:
    """

    :param speedup:     default True; determine if db-commits are switched to "manual mode" to leverate bullk operations
    :return:
    """

    import time

    t0 = time.time()
    entity_list = []
    label_list = []
    for ent in itertools.chain(p.ds.items.values(), p.ds.relations.values()):
        label = create_lss(ent, "R1")
        entity = PyerkEntity(uri=ent.uri, description=getattr(ent, "R2", None))

        label_list.append(label)
        entity_list.append(entity)

    # print(p.auxiliary.bcyan(f"time1: {time.time() - t0}"))
    PyerkEntity.objects.bulk_create(entity_list)
    LanguageSpecifiedString.objects.bulk_create(label_list)

    if speedup:
        transaction.commit()

    assert len(PyerkEntity.objects.all()) == len(
        LanguageSpecifiedString.objects.all()
    ), "Mismatch in Entities and corresponding Labels."
    for entity, label in zip(PyerkEntity.objects.all(), LanguageSpecifiedString.objects.all()):
        entity.label.add(label)

    # print(p.auxiliary.bcyan(f"time2: {time.time() - t0}"))


def unload_data(strict=False):

    # unload modules
    # p.unload_mod(p.ackrep_parser.__URI__, strict=strict)
    p.unload_mod(p.settings.OCSE_URI, strict=strict)

    # unload db
    PyerkEntity.objects.all().delete()
    LanguageSpecifiedString.objects.all().delete()


def create_lss(ent: p.Entity, rel_key: str) -> LanguageSpecifiedString:
    """
    Create a language specified string (see models.LanguageSpecifiedString).
    Note: the object is not yet commited to the database.

    :param ent:
    :param rel_key:
    :return:
    """
    rdf_literal = p.aux.ensure_rdf_str_literal(getattr(ent, rel_key, ""))
    return LanguageSpecifiedString(langtag=rdf_literal.language, content=rdf_literal.value)


def get_sparql_text(code_entity: Union[PyerkEntity, object]) -> str:
    uri = "<" + code_entity.base_uri + "#>"
    prefix = settings.SPARQL_PREFIX_MAPPING[uri]
    key = code_entity.short_key
    desc = code_entity.R1.replace(" ", "_")

    text = prefix + key + "__" + desc

    return text
