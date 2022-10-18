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
from ackrep_core_django_settings import settings

activate_ips_on_exception()

from pyerk.settings import DEFAULT_DATA_LANGUAGE
from pyerk.auxiliary import get_erk_root_dir

ERK_ROOT_DIR = get_erk_root_dir()

# Flag to determine if tests are running
RUNNING_TESTS = False

# TODO: This should be read from a config file
ERK_DATA_PATH = os.path.join(ERK_ROOT_DIR, "erk-data", "control-theory", "control_theory1.py")
ERK_DATA_MOD_NAME = "control_theory1"


if not os.environ.get("ACKREP_ENVIRONMENT_NAME"):
    # this env var is set in Dockerfile of env
    import pyerk as p


class BaseModel(models.Model):
    class Meta:
        abstract = True

    objects = models.Manager()  # make PyCharm happy


class LanguageSpecifiedString(BaseModel):
    id = models.BigAutoField(primary_key=True)
    langtag = models.CharField(max_length=8, default="", null=False)
    content = models.TextField(null=True)

    def __repr__(self):
        return f"<LSS({self.content}@{self.langtag})>"


class Entity(BaseModel):
    id = models.BigAutoField(primary_key=True)

    # TODO: this should be renamed to `short_key` (first step: see property `short_key` below)
    uri = models.TextField(default="(unknown uri)")

    # note: in reality this a one-to-many-relationship which in principle could be modeled by a ForeignKeyField
    # on the other side. However, as we might use the LanguageSpecifiedString model also on other fields (e.g.
    # description) in the future this is not an option
    label = models.ManyToManyField(LanguageSpecifiedString)
    description = models.TextField(default="", null=True)

    def get_label(self, langtag=None) -> str:
        if langtag is None:
            langtag = DEFAULT_DATA_LANGUAGE
        # noinspection PyUnresolvedReferences
        res = self.label.filter(langtag=langtag)
        if len(res) == 0:
            return f"[no label in language {langtag} available]"
        else:
            return res[0].content

    def __str__(self) -> str:
        label_str = self.get_label().replace(" ", "_")
        # TODO introduce prefixes
        return f"{self.uri}__{label_str}"

    # TODO: remove obsolete short_key
    # @property
    # def short_key(self):
    #     return self.uri


def _entity_sort_key(entity) -> Tuple[str, int]:
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
    mod_uri, sk = uri.split(p.settings.URI_SEP)

    if sk[1].isdigit():
        num = int(sk[1:])
        letter = sk[0]
        # return
    else:
        num = int(sk[2:])
        letter = f"x{sk[0]}"

    return letter, num

def render_entity_inline(entity: Union[Entity, p.Entity], **kwargs) -> str:

    # allow both models.Entity (from db) and "code-defined" pyerk.Entity
    if isinstance(entity, p.Entity):
        code_entity = entity
    elif isinstance(entity, Entity):
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
            new_data[new_key] = value.replace(highlight_text, f"<strong>{highlight_text}</strong>")

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

def represent_entity_as_dict(code_entity: Union[Entity, object]) -> dict:

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
            "detail_url": q_reverse("entitypage", uri=code_entity.uri),
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

def q_reverse(pagename, uri, **kwargs):
    """
    Simplifies the hazzle for passing URIs into `reverse` (they must be percent-encoded therefor, aka quoted), and then
    unqoting the result again.


    :param pagename:
    :param uri:
    :param kwargs:
    :return:
    """

    quoted_url = reverse(pagename, kwargs={"uri": urlquote(uri)})

    # noinspection PyUnresolvedReferences
    return quoted_url

def urlquote(txt):
    # noinspection PyUnresolvedReferences
    return urllib.parse.quote(txt, safe="")

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
            ERK_DATA_PATH, prefix="ct", modname=ERK_DATA_MOD_NAME,
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
        Entity.objects.all().delete()
        LanguageSpecifiedString.objects.all().delete()
    except OperationalError:
        # db does not yet exist. The functions is probably called during `manage.py migrate` or similiar.
        return 0

    if RUNNING_TESTS:
        speedup = False

    # repopulate the databse with items and relations (and auxiliary objects)
    _load_entities_to_db(speedup=speedup)

    n = len(Entity.objects.all())
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
        entity = Entity(uri=ent.uri, description=getattr(ent, "R2", None))

        label_list.append(label)
        entity_list.append(entity)

    # print(p.auxiliary.bcyan(f"time1: {time.time() - t0}"))
    Entity.objects.bulk_create(entity_list)
    LanguageSpecifiedString.objects.bulk_create(label_list)

    if speedup:
        transaction.commit()

    assert len(Entity.objects.all()) == len(LanguageSpecifiedString.objects.all()), "Mismatch in Entities and corresponding Labels."
    for entity, label in zip(Entity.objects.all(), LanguageSpecifiedString.objects.all()):
        entity.label.add(label)

    # print(p.auxiliary.bcyan(f"time2: {time.time() - t0}"))


def unload_data(strict=False):

    # unload modules
    # p.unload_mod(p.ackrep_parser.__URI__, strict=strict)
    p.unload_mod(p.settings.OCSE_URI, strict=strict)

    # unload db
    Entity.objects.all().delete()
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

def render_entity_relations(db_entity: Entity) -> str:

    # omit information which is already displayed by render_entity (label, description)
    black_listed_keys = ["R1", "R2"]
    uri = db_entity.uri

    # #########################################################################
    # frist: handle direct relations (where `db_entity` is subject)
    # #########################################################################

    # dict like {"R1": [<RelationEdge 1234>, ...], "R2": [...]}
    relation_edges0 = p.ds.relation_edges[uri]

    # create a flat list of template-friendly dicts
    re_dict_2tuples = []
    for rel_key, re_list in relation_edges0.items():
        if rel_key in black_listed_keys:
            continue
        for re in re_list:
            # index 0 is the subject entity which is db_entity and thus not relevant here
            d1 = represent_entity_as_dict(re.relation_tuple[1])
            d2 = represent_entity_as_dict(re.relation_tuple[2])
            re_dict_2tuples.append((d1, d2))

    # #########################################################################
    # second: handle inverse relations (where `db_entity` is object)
    # #########################################################################

    # dict like {"R4": [<RelationEdge 1234>, ...], "R8": [...]}
    inv_relation_edges0 = p.ds.inv_relation_edges[uri]

    # create a flat list of template-friendly dicts
    inv_re_dict_2tuples = []
    for rel_key, inv_re_list in inv_relation_edges0.items():
        if rel_key in black_listed_keys:
            continue
        for re in inv_re_list:
            # index 2 is the object entity of the inverse relations which is db_entity and thus not relevant here
            d0 = represent_entity_as_dict(re.relation_tuple[0])
            d1 = represent_entity_as_dict(re.relation_tuple[1])
            inv_re_dict_2tuples.append((d0, d1))

    # #########################################################################
    # third: render the two lists and return
    # #########################################################################

    ctx = {
        "main_entity": {"special_class": "highlight", **represent_entity_as_dict(p.ds.get_entity_by_uri(uri))},
        "re_dict_2tuples": re_dict_2tuples,
        "inv_re_dict_2tuples": inv_re_dict_2tuples,
    }
    template = get_template("mainapp/widget-entity-relations.html")
    render_result = template.render(context=ctx)

    return render_result

def render_entity_scopes(db_entity: Entity) -> str:
    code_entity = p.ds.get_entity_by_uri(db_entity.uri)
    # noinspection PyProtectedMember

    scopes = p.get_scopes(code_entity)

    scope_contents = []
    for scope in scopes:

        # #### first: handle "variables" (locally relevant items) defined in this scope

        items = p.get_items_defined_in_scope(scope)
        re: p.RelationEdge
        # currently we only use `R4__instance_of` as "defining relation"
        # relation_edges = [re for key, re_list in relation_edges0.items() if key not in black_listed_keys for re in re_list]
        defining_relation_triples = []
        for item in items:
            for re in p.ds.relation_edges[item.short_key]["R4"]:
                defining_relation_triples.append(list(map(represent_entity_as_dict, re.relation_tuple)))

        # #### second: handle further relation triples in this scope

        statement_relations = []
        re: p.RelationEdge
        for re in p.ds.scope_relation_edges[scope.short_key]:
            dict_tup = tuple(represent_entity_as_dict(elt) for elt in re.relation_tuple)
            statement_relations.append(dict_tup)

        scope_contents.append(
            {
                "name": scope.R1,
                "defining_relations": defining_relation_triples,
                "statement_relations": statement_relations,
            }
        )

    ctx = {"scopes": scope_contents}

    template = get_template("mainapp/widget-entity-scopes.html")
    render_result = template.render(context=ctx)
    # IPS()
    return render_result

def get_sparql_text(code_entity: Union[Entity, object]) -> str:
    uri = "<" + code_entity.base_uri + "#>"
    prefix = settings.SPARQL_PREFIX_MAPPING[uri]
    key = code_entity.short_key
    desc = code_entity.R1.replace(" ", "_")
    text = prefix + key + "__" + desc

    return text
