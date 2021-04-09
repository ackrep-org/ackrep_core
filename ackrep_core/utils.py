"""
This modules contains some utility functions which should not be placed in .core to prevent circular imports
"""
import os
from ipydex import Container


# path of this module (i.e. the file core.py)
mod_path = os.path.dirname(os.path.abspath(__file__))

# path of this package (i.e. the directory ackrep_core)
core_pkg_path = os.path.dirname(mod_path)

# path of the general project root (expected to contain ackrep_data, ackrep_core, ackrep_deployment, ...)
root_path = os.path.abspath(os.path.join(mod_path, "..", ".."))

# paths for (ackrep_data and its test-related clone)
data_path = os.path.join(root_path, "ackrep_data")
data_test_repo_path = os.path.join(root_path, "ackrep_data_for_unittests")


class ResultContainer(Container):
    """
    @DynamicAttrs
    """

    pass


class ObjectContainer(Container):
    """
    @DynamicAttrs
    """

    pass


class InconsistentMetaDataError(ValueError):
    """Raised when an entity with inconsistent metadata is loaded."""

    pass


class DuplicateKeyError(Exception):
    """Raised when a duplicate key is found in the database."""

    def __init__(self, dup_key):
        super().__init__(f"Duplicate key in database '{dup_key}'")
