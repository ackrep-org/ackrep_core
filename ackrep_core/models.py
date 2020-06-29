import os
import sys
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
    pk = models.CharField(max_length=5, null=False, blank=False,)
    type = models.CharField(max_length=20, null=False, blank=False,)
    name = models.CharField(max_length=40, null=False, blank=False,)
    short_description = models.CharField(max_length=500, null=True, blank=True,)
    version = models.CharField(max_length=10, null=False, blank=False,)
    tags = models.CharField(max_length=500, null=True, blank=True,)

    # !! TODO: review
    creator = models.CharField(max_length=500, null=True, blank=True,)
    editors = models.CharField(max_length=500, null=True, blank=True,)
    creation_date = models.CharField(max_length=500, null=True, blank=True,)
    related_docs = models.CharField(max_length=500, null=True, blank=True,)
    related_datasets = models.CharField(max_length=500, null=True, blank=True,)
    external_references = models.CharField(max_length=500, null=True, blank=True,)
    notes = models.CharField(max_length=500, null=True, blank=True,)

    @classmethod
    def get_fields(cls):
        return cls._meta.fields


class ProblemSpecification(GenericEntity):
    pass










