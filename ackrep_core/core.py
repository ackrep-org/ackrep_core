import secrets
import yaml


def gen_random_pk():
    return "".join([c for c in secrets.token_urlsafe(10).upper() if c.isalnum()])[:5]


required_generic_meta_data = {
    "pk": "=5",
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


def get_metadata_from_file(fname, subtype=None):
    """
    Load metadata
    :param fname:
    :param subtype:
    :return:
    """
    with open("metadata.yml") as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    assert set(required_generic_meta_data.keys()).issubset(data.keys())
