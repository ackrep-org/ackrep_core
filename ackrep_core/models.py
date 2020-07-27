import os
import sys
import inspect

from django.db import models
import django
from django.conf import settings
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from . import core


"""
This module uses the django model engine to specify models.
However, they are used also outside the web application, i.e. for the command line application.  
"""

# The following is necessary to let us use django functionality without accessing via manage.py
try:
    hasattr(settings, "BASE_DIR")
except ImproperlyConfigured:
    settings_configured_flag = False
else:
    settings_configured_flag = True


if not apps.apps_ready:
    settings_configured_flag = False

if not settings_configured_flag:
    mod_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, mod_path)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'ackrep_core_django_settings.settings'
    django.setup()
else:
    pass


# define two type to distinguish charfields which will hold (foreign) entity-keys or a list of entity-keys
# see core.resolve_keys(...) for more info
class EntityKeyField(models.CharField):
    pass


class EntityKeyListField(models.CharField):
    pass


class MergeRequest(models.Model):
    STATUS_OPEN = "STATUS_OPEN"
    STATUS_MERGED = "STATUS_MERGED"

    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=5, null=False, blank=False)
    title = models.CharField(max_length=500, null=False, blank=False)
    repo_url = models.CharField(max_length=500, null=False, blank=False)
    status = ((STATUS_OPEN, "open"), (STATUS_MERGED, "merged"))
    last_update = models.CharField(max_length=500, null=False, blank=False)
    description = models.CharField(max_length=5000, null=False, blank=False)
    fork_commit = models.CharField(max_length=40, null=False, blank=False)
    merge_commit = models.CharField(max_length=40, null=False, blank=False)


class GenericEntity(models.Model):
    """
    This is the base class for all other acrep-entities
    """
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=5, null=False, blank=False, )

    # TODO: Better data type for referencing merge request
    merge_request = models.CharField(max_length=5, null=False, blank=False)

    # TODO: this field should be renamed to `predecessor`
    predecessor_key = EntityKeyField(max_length=5, null=True, blank=False, )
    type = models.CharField(max_length=20, null=False, blank=False,)
    name = models.CharField(max_length=40, null=False, blank=False,)
    short_description = models.CharField(max_length=500, null=True, blank=True,)
    version = models.CharField(max_length=10, null=False, blank=False, default="0.1.0")
    tag_list = models.CharField(max_length=500, null=True, blank=True,)

    creator = models.CharField(max_length=500, null=True, blank=True,)
    editor_list = models.CharField(max_length=500, null=True, blank=True,)
    creation_date = models.CharField(max_length=500, null=True, blank=True,)

    external_references = models.CharField(max_length=500, null=True, blank=True,)
    notes = models.CharField(max_length=5000, null=True, blank=True,)

    # this is automatically filled when importing .yml files into the db
    # should not be specified inside the .yml file
    base_path = models.CharField(max_length=5000, null=True, blank=True,)

    class Meta:
        abstract = True

    @classmethod
    def get_fields(cls):

        # noinspection PyUnresolvedReferences
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

    def __repr__(self):
        return f"<{type(self).__name__} (pk: {self.pk}, key: {self.key})>"

    def __str__(self):
        return repr(self)

    def status(self):
        """Return merge status based on associated merge request"""
        if self.merge_request is None:
            # Manually added to DB
            return MergeRequest.STATUS_MERGED
        
        merge_requests_with_key = list(MergeRequest.objects.filter(key=self.merge_request))
        assert len(merge_requests_with_key) == 1, "Associated merge request is either missing or duplicated"
        mr = merge_requests_with_key[0]
        
        return mr.status


class ProblemSpecification(GenericEntity):
    _type = "problem_specification"
    problemclass_list = EntityKeyListField(max_length=500, null=True, blank=True,)
    problem_file = models.CharField(max_length=500, null=True, blank=True, default="problem.py")

    # TODO: this function is affacted by the necessary model-refactoring (issue #1)
    def available_solutions_list(self):
        all_solutions = ProblemSolution.objects.all()

        available_solutions = []
        for sol in all_solutions:
            core.resolve_keys(sol)
            solved_problem_keys = [prob.key for prob in sol.oc.solved_problem_list]
            if self.key in solved_problem_keys:
                available_solutions.append(sol)

        return available_solutions


class ProblemSolution(GenericEntity):
    _type = "problem_solution"
    solved_problem_list = EntityKeyListField(max_length=500, null=True, blank=True,)
    method_package_list = EntityKeyListField(max_length=500, null=True, blank=True,)
    compatible_environment = EntityKeyField(max_length=500, null=True, blank=True,)
    estimated_runtime = models.CharField(max_length=500, null=True, blank=True,)
    solution_file = models.CharField(max_length=500, null=True, blank=True, default="solution.py")
    postprocessing_file = models.CharField(max_length=500, null=True, blank=True,)


class ProblemClass(GenericEntity):
    _type = "problem_class"


class Comment(GenericEntity):
    referenced_entity_list = EntityKeyField(max_length=500, null=True, blank=True, )
    _type = "comment"


class Documentation(GenericEntity):
    referenced_entity_list = EntityKeyField(max_length=500, null=True, blank=True, )
    _type = "documentation"


class EnvironmentSpecification(GenericEntity):
    _type = "environment_specification"


class MethodPackage(GenericEntity):
    _type = "method_package"
    compatible_environment_list = EntityKeyListField(max_length=500, null=True, blank=True,)


# TODO: rename this to get_entity_types
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
