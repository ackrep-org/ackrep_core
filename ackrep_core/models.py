import os
import sys
import inspect

from django.db import models
import django


"""
This module uses the django model engine to specify models
"""

mod_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, mod_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_settings.settings')
django.setup()


class GenericEntity(models.Model):
    """
    This is the base class for all other acrep-entities
    """
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
    related_dataset_list = models.CharField(max_length=500, null=True, blank=True,)
    external_references = models.CharField(max_length=500, null=True, blank=True,)
    notes = models.CharField(max_length=5000, null=True, blank=True,)

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

        return fields


class ProblemSpecification(GenericEntity):
    problemclass_list = models.CharField(max_length=500, null=True, blank=True,)
    _type = "problem_specification"


class ProblemSolution(GenericEntity):
    _type = "problem_solution"
    problemclass_list = models.CharField(max_length=500, null=True, blank=True,)
    method_list = models.CharField(max_length=500, null=True, blank=True,)
    related_dataset_list = models.CharField(max_length=500, null=True, blank=True,)
    compatible_environment_list = models.CharField(max_length=500, null=True, blank=True,)
    estimated_runtime = models.CharField(max_length=500, null=True, blank=True,)
    solution_file = models.CharField(max_length=500, null=True, blank=True, default="solution.py")
    postprocessing_file = models.CharField(max_length=500, null=True, blank=True,)


def get_entities():
    """
    Return a list of all defined entities

    :return:
    """
    clsmembers = inspect.getmembers(sys.modules[__name__], inspect.isclass)

    res = [c[1] for c in clsmembers if issubclass(c[1], GenericEntity) and not c[1] is GenericEntity]
    return res

