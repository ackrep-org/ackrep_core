import secrets
import yaml


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


def gen_random_key():
    return "".join([c for c in secrets.token_urlsafe(10).upper() if c.isalnum()])[:5]


def get_metadata_from_file(fname, subtype=None):
    """
    Load metadata
    :param fname:
    :param subtype:
    :return:
    """
    with open(fname) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    # TODO: this check is outdated -> temporarily deactivated
    if 0 and not set(required_generic_meta_data.keys()).issubset(data.keys()):
        msg = f"In the provided file `{fname}` at least one required key is missing."
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

