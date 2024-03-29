import inspect
import yaml
from . import models
from .util import ObjectContainer, InconsistentMetaDataError, DuplicateKeyError

# noinspection PyUnresolvedReferences
from ipydex import IPS  # only for debugging


def get_entity_types():
    """
    Return a list of all defined entities

    :return:
    """
    clsmembers = inspect.getmembers(models, inspect.isclass)

    res = [c[1] for c in clsmembers if issubclass(c[1], models.GenericEntity) and not c[1] is models.GenericEntity]
    return res


def create_entity_from_metadata(md):
    """
    :param md:  dict (from yml-file)
    :return:
    """

    entity = entity_mapping()[md["type"]](**md)
    return entity


def get_entity_dict_from_db(only_merged=True):
    """
    get all entities which are currently in the database
    :return:
    """
    entity_type_list = get_entity_types()

    entity_dict = {}

    for et in entity_type_list:
        if only_merged:
            object_list = list(e for e in et.objects.all() if e.status() == models.MergeRequest.STATUS_MERGED)
        else:
            object_list = list(et.objects.all())

        entity_dict[et.__name__] = object_list

    return entity_dict


def get_entity(key, raise_error_on_empty=True):
    """get entity with key from database
    can be abused to check for multiple keys in db

    Args:
        key (str): entity key
        raise_error_on_empty (bool, optional): set to False if db is in the process of initializing. Defaults to True.

    Raises:
        KeyError: if key not found in db (and raise_error_on_empty==True)
        DuplicateKeyError: if multiple entites with key have been found

    Returns:
        GenericEntity: entity
    """
    results = []
    for entity_type in get_entity_types():
        res = entity_type.objects.filter(key=key)
        results.extend(res)

    if raise_error_on_empty and len(results) == 0:
        msg = f"No entity with key '{key}' could be found. Make sure that the database is in sync with repo."
        # TODO: this should be a 404 Error in the future
        raise KeyError(msg)
    elif len(results) > 1:
        msg = f"There have been multiple entities with key '{key}'. "
        raise DuplicateKeyError(msg)

    if len(results) > 0:
        entity = results[0]
    else:
        entity = None

    return entity


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

    entity.oc = ObjectContainer()

    for field in fields:
        if isinstance(field, models.EntityKeyField):

            # example: get the content of entity.predecessor_key
            refkey = getattr(entity, field.name)
            if refkey:
                try:
                    ref_entity = get_entity(refkey)
                except ValueError as ve:
                    msg = (
                        f"Bad refkey detected when processing field {field.name} of {entity}. "
                        f"Original error: {ve.args[0]}"
                    )
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

            refkeylist = yaml.load(refkeylist_str, Loader=yaml.SafeLoader)
            if refkeylist in (None, [], [""]):
                refkeylist = []

            try:
                entity_list = [get_entity(refkey) for refkey in refkeylist]
            except ValueError as ve:
                msg = (
                    f"Bad refkey detected when processing field {field.name} of {entity}. "
                    f"Original error: {ve.args[0]}"
                )
                raise InconsistentMetaDataError(msg)
            setattr(entity.oc, field.name, entity_list)


list_of_all_entities = []
entity_mapping_dict = {}


def all_entities():
    """
    Encapsulate the access to that list to prevent circular import issues
    :return:
    """
    if not list_of_all_entities:
        entity_type_list = get_entity_types()
        for et in entity_type_list:
            list_of_all_entities.extend(et.objects.all())
    return list_of_all_entities


def entity_mapping():
    """
    Encapsulate the access to that dict to prevent circular import issues
    :return:
    """
    if not entity_mapping_dict:
        # noinspection PyProtectedMember
        tmp = dict([(e._type, e) for e in get_entity_types()])
        entity_mapping_dict.update(tmp)
    return entity_mapping_dict
