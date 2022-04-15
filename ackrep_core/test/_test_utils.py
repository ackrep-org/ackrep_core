import os

from ackrep_core import core

def load_repo_to_db_for_tests(repo_path:str, initial: bool = False) -> None:
    """
    Call core.load_repo_to_db(...) depending on some environment variable.

    :param repo_path:   path to the repository which is to be loaded into the db
    :param initial:     inidicate if this is the initial call to this function

    Background: Some unittest interact with the (test) database read only, orhters
    perform write-access. For efficient development (test speed) it is useful to control
    when the database is regenerated (from the repo):
    - mode "1" for every single test (default)
    - mode "2" only once per test-suite-call
    - mode "3" never


    usage example.: `export ACKREP_TEST_DB_REGENERATION_MODE=3`
    python3 manage.py test --nocapture --rednose --ips ackrep_core.test.test_core:TestCases2.test_get_metadata_path_from_key
    """

    db_regeneration_mode = os.environ.get("ACKREP_TEST_DB_REGENERATION_MODE", "1")


    valid_values = ("1", "2", "3")
    if db_regeneration_mode not in valid_values:
        raise ValueError(
            "Unexpected value for environment variable: "
            f"`ACKREP_TEST_DB_REGENERATION_MODE`. Must be one of {valid_values}."
        )

    if db_regeneration_mode == "1" and not initial:
            # called by set_up-methods
            core.load_repo_to_db(repo_path)

    elif db_regeneration_mode == "2" and initial:
            # called at the beginning of the test_core module

            core.load_repo_to_db(repo_path)

    else:
        # do nothing
        pass
