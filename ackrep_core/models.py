import os
import sys

from django.db import models
import django
from django.conf import settings
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

import git

from . import util
from . import model_utils

if not os.environ.get("ACKREP_ENVIRONMENT_NAME"):
    from pyerk.settings import DEFAULT_DATA_LANGUAGE

# noinspection PyUnresolvedReferences
from ipydex import IPS  # only for debugging


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
    os.environ["DJANGO_SETTINGS_MODULE"] = "ackrep_core_django_settings.settings"
    django.setup()
else:
    pass


# define two type to distinguish char-fields which will hold (foreign) entity-keys or a list of entity-keys
# see core.resolve_keys(...) for more info
class EntityKeyField(models.CharField):
    pass


class EntityKeyListField(models.CharField):
    pass


class BaseModel(models.Model):
    """
    prevent PyCharm from complaining on .objects-attribute
    source: https://stackoverflow.com/a/56845199/333403
    """

    objects = models.Manager()

    class Meta:
        abstract = True


class MergeRequest(BaseModel):
    STATUS_OPEN = "STATUS_OPEN"
    STATUS_MERGED = "STATUS_MERGED"

    STATUS_CHOICES = ((STATUS_OPEN, "open"), (STATUS_MERGED, "merged"))

    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=5, null=False, blank=False)
    title = models.CharField(max_length=500, null=False, blank=False)
    repo_url = models.CharField(max_length=500, null=False, blank=False)
    status = models.CharField(max_length=13, choices=STATUS_CHOICES, default=STATUS_OPEN)
    last_update = models.CharField(max_length=500, null=False, blank=False)
    description = models.CharField(max_length=5000, null=False, blank=False)
    fork_commit = models.CharField(max_length=40, null=False, blank=False)
    merge_commit = models.CharField(max_length=40, null=False, blank=False)

    def entity_list(self):
        entity_dict = model_utils.get_entity_dict_from_db(only_merged=False)
        entity_list = []
        for _, val in entity_dict.items():
            entity_list += [e for e in val if e.merge_request == self.key]

        return entity_list

    def repo_dir(self):
        return os.path.join(util.root_path, "external_repos", str(self.key))

    def repo(self):
        return git.Repo(self.repo_dir())


class GenericEntity(BaseModel):
    """
    This is the base class for all other ackrep-entities
    """

    id = models.AutoField(primary_key=True)
    key = models.CharField(
        max_length=5,
        null=False,
        blank=False,
    )

    # TODO: Better data type for referencing merge request
    merge_request = models.CharField(max_length=5, null=True, blank=False)

    # TODO: this field should be renamed to `predecessor`
    predecessor_key = EntityKeyField(
        max_length=5,
        null=True,
        blank=False,
    )
    type = models.CharField(
        max_length=20,
        null=False,
        blank=False,
    )
    name = models.CharField(
        max_length=40,
        null=False,
        blank=False,
    )
    short_description = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    version = models.CharField(max_length=10, null=False, blank=False, default="0.1.0")
    tag_list = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    creator = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    editor_list = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    creation_date = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    external_references = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    notes = models.CharField(
        max_length=5000,
        null=True,
        blank=True,
    )

    # this is automatically filled when importing .yml files into the db
    # should not be specified inside the .yml file
    base_path = models.CharField(
        max_length=5000,
        null=True,
        blank=True,
    )

    oc = util.ObjectContainer()

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
        if not self.merge_request:
            # Manually added to DB
            return MergeRequest.STATUS_MERGED

        merge_requests_with_key = list(MergeRequest.objects.filter(key=self.merge_request))
        assert len(merge_requests_with_key) == 1, "Associated merge request is either missing or duplicated"
        mr = merge_requests_with_key[0]

        return mr.status


class SystemModel(GenericEntity):
    _type = "system_model"
    estimated_runtime = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    compatible_environment = EntityKeyField(
        max_length=500,
        null=True,
        blank=True,
    )
    erk_data = models.CharField(max_length=100000, blank=True)
    system_model_file = models.CharField(max_length=500, null=True, blank=True, default="system_model.py")
    simulation_file = models.CharField(max_length=500, null=True, blank=True, default="simulation.py")

    def related_problems_list(self):
        all_problems = ProblemSpecification.objects.all()

        related_problems = []
        for problem in all_problems:
            model_utils.resolve_keys(problem)
            related_problem_keys = [model.key for model in problem.oc.related_system_models_list]
            if self.key in related_problem_keys:
                related_problems.append(problem)

        return related_problems


class ProblemSpecification(GenericEntity):
    _type = "problem_specification"
    problemclass_list = EntityKeyListField(
        max_length=500,
        null=True,
        blank=True,
    )
    related_system_models_list = EntityKeyListField(
        max_length=500,
        null=True,
        blank=True,
    )
    problem_file = models.CharField(max_length=500, null=True, blank=True, default="problem.py")

    # TODO: this function is affected by the necessary model-refactoring (issue #1)
    def available_solutions_list(self):
        all_solutions = ProblemSolution.objects.all()

        available_solutions = []
        for sol in all_solutions:
            model_utils.resolve_keys(sol)
            solved_problem_keys = [prob.key for prob in sol.oc.solved_problem_list]
            if self.key in solved_problem_keys:
                available_solutions.append(sol)

        return available_solutions


class ProblemSolution(GenericEntity):
    _type = "problem_solution"
    solved_problem_list = EntityKeyListField(
        max_length=500,
        null=True,
        blank=True,
    )
    method_package_list = EntityKeyListField(
        max_length=500,
        null=True,
        blank=True,
    )
    compatible_environment = EntityKeyField(
        max_length=500,
        null=True,
        blank=True,
    )
    estimated_runtime = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    solution_file = models.CharField(max_length=500, null=True, blank=True, default="solution.py")
    postprocessing_file = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )


class Notebook(GenericEntity):
    _type = "notebook"
    estimated_runtime = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    compatible_environment = EntityKeyField(
        max_length=500,
        null=True,
        blank=True,
    )
    notebook_file = models.CharField(max_length=500, null=True, blank=True, default="notebook.ipynb")


class ProblemClass(GenericEntity):
    _type = "problem_class"


class Comment(GenericEntity):
    referenced_entity_list = EntityKeyField(
        max_length=500,
        null=True,
        blank=True,
    )
    _type = "comment"


class Documentation(GenericEntity):
    referenced_entity_list = EntityKeyField(
        max_length=500,
        null=True,
        blank=True,
    )
    _type = "documentation"


class EnvironmentSpecification(GenericEntity):
    _type = "environment_specification"


class MethodPackage(GenericEntity):
    _type = "method_package"
    compatible_environment_list = EntityKeyListField(
        max_length=500,
        null=True,
        blank=True,
    )


class LanguageSpecifiedString(BaseModel):
    id = models.BigAutoField(primary_key=True)
    langtag = models.CharField(max_length=8, default="", null=False)
    content = models.TextField(null=True)

    def __repr__(self):
        return f"<LSS({self.content}@{self.langtag})>"


class PyerkEntity(BaseModel):
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
