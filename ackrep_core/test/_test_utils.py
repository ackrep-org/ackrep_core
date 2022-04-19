import os
from git import Repo, InvalidGitRepositoryError

from ackrep_core import core

# globally accessible variable to save whether the database has yet been initialized
test_metadata = core.Container(db_initialized=False)

# this function must not have "test" inside its name for not beeing interpreted as test case
def load_repo_to_db_for_tests(repo_path:str) -> None:
    """
    Call core.load_repo_to_db(...) depending on some environment variable.

    :param repo_path:   path to the repository which is to be loaded into the db

    Background: Some unittest interact with the (test) database read only, orhters
    perform write-access. For efficient development (test speed) it is useful to control
    when the database is regenerated (from the repo) by setUp methods:
    - mode "1" for every single test (default)
    - mode "2" only once per test-suite-call
    - mode "3" never

    Note, that some tests explicitly regenerate the database in their actual test code
    (i.e. not in setUp). This is not affected.

    usage example.: `export ACKREP_TEST_DB_REGENERATION_MODE=3`
    python3 manage.py test --keepdb --nocapture --rednose --ips ackrep_core.test.test_core:TestCases2.test_get_metadata_path_from_key
    """

    db_regeneration_mode = os.environ.get("ACKREP_TEST_DB_REGENERATION_MODE", "1")


    valid_values = ("1", "2", "3")
    if db_regeneration_mode not in valid_values:
        raise ValueError(
            "Unexpected value for environment variable: "
            f"`ACKREP_TEST_DB_REGENERATION_MODE`. Must be one of {valid_values}."
        )

    if db_regeneration_mode == "1":
            # called by setUp-methods
            core.load_repo_to_db(repo_path)

    elif db_regeneration_mode == "2" and not test_metadata.db_initialized:
            # only run if db has not yet been regenerated
            core.load_repo_to_db(repo_path)
            test_metadata.db_initialized = True

    else:
        # do nothing
        pass

def reset_repo(repo_path):
    """
    Some tests change the state of the working directory of the test repository.
    This function resets it to the last commit.
    """

    repo = Repo(repo_path)
    repo.head.reset(index=True, working_tree=True)
