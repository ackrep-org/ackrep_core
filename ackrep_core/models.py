import os
import sys
import inspect

from django.db import models
import django
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


"""
This module uses the django model engine to specify models.
However, they are used also outside the web application, i.e. for the command line application.  
"""


# from ipydex import IPS, activate_ips_on_exception
# IPS()
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_settings.settings')

# if 1 and not os.environ.get('DJANGO_SETTINGS_MODULE'):

try:
    hasattr(settings, "BASE_DIR")
except ImproperlyConfigured:
    settings_configured_flag = False
else:
    settings_configured_flag = True

if not settings_configured_flag:
    mod_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, mod_path)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'ackrep_core_django_settings.settings'
    django.setup()
else:
    pass


class GenericEntity(models.Model):
    """
    This is the base class for all other acrep-entities
    """
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=5, null=False, blank=False,)
    predecessor_key = models.CharField(max_length=5, null=True, blank=False,)
    type = models.CharField(max_length=20, null=False, blank=False,)
    name = models.CharField(max_length=40, null=False, blank=False,)
    short_description = models.CharField(max_length=500, null=True, blank=True,)
    version = models.CharField(max_length=10, null=False, blank=False, default="0.1.0")
    tag_list = models.CharField(max_length=500, null=True, blank=True,)

    # !! TODO: review
    creator = models.CharField(max_length=500, null=True, blank=True,)
    editor_list = models.CharField(max_length=500, null=True, blank=True,)
    creation_date = models.CharField(max_length=500, null=True, blank=True,)
    related_doc_list = models.CharField(max_length=500, null=True, blank=True,)
    external_references = models.CharField(max_length=500, null=True, blank=True,)
    notes = models.CharField(max_length=5000, null=True, blank=True,)

    # this is automatically filled when importing .yml files into the db
    # should not be specified inside the .yml file
    base_path = models.CharField(max_length=5000, null=True, blank=True,)

    class Meta:
        abstract = True

    @classmethod
    def get_fields(cls):
        fields = list(cls._meta.fields)

        # remove the first and the last field (they where added automatically)
        f0 = fields.pop(0)
        assert "AutoField" in repr(f0)

        if fields[-1].name == "genericentity_ptr":
            fields.pop()

        # ensure that base_path is not exported. (only meant for internal usage)
        final_fields = []
        for f in fields:
            if f.name != "base_path":
                final_fields.append(f)

        return final_fields


class ProblemSpecification(GenericEntity):
    problemclass_list = models.CharField(max_length=500, null=True, blank=True,)
    problem_file = models.CharField(max_length=500, null=True, blank=True, default="problem.py")
    _type = "problem_specification"


class ProblemSolution(GenericEntity):
    _type = "problem_solution"
    solved_problem_list = models.CharField(max_length=500, null=True, blank=True,)
    method_package_list = models.CharField(max_length=500, null=True, blank=True,)
    compatible_environment = models.CharField(max_length=500, null=True, blank=True,)
    estimated_runtime = models.CharField(max_length=500, null=True, blank=True,)
    solution_file = models.CharField(max_length=500, null=True, blank=True, default="solution.py")
    postprocessing_file = models.CharField(max_length=500, null=True, blank=True,)


class ProblemClass(GenericEntity):
    _type = "problem_class"


class Comment(GenericEntity):
    _type = "comment"


class Documentation(GenericEntity):
    _type = "documentation"


class EnvironmentSpecification(GenericEntity):
    _type = "environment_specification"


class MethodPackage(GenericEntity):
    _type = "method_package"
    compatible_environment_list = models.CharField(max_length=500, null=True, blank=True,)


def get_entities():
    """
    Return a list of all defined entities

    :return:
    """
    clsmembers = inspect.getmembers(sys.modules[__name__], inspect.isclass)

    res = [c[1] for c in clsmembers if issubclass(c[1], GenericEntity) and not c[1] is GenericEntity]
    return res


all_entities = get_entities()
# noinspection PyProtectedMember
entity_mapping = dict([(e._type, e) for e in all_entities])


def create_entity_from_metadata(md):
    """
    :param md:  dict (from yml-file)
    :return:
    """

    entity = entity_mapping[md["type"]](**md)
    return entity
