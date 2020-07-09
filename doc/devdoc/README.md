# Unittests

As the software is still an early prototype and defining the concrete feature set is subject to ongoing research, only a fraction of the functionality is already covered by tests. However this fraction will increase in the future. The unittest depend on data which is maintained outside of this repo: It is assumed that there is a copy of the `acrep_data` repository named `acrep_data_for_unittests` next to it (see [directory layout](https://github.com/cknoll/ackrep_deployment#directory-layout)) and that its HEAD points to a defined commit (see `ackrep_core.core.test.test_core.default_repo_head_hash`).


There are several options to run the tests. The following is recommended (`--rednose` is optional):

- `python3 manage.py test --nocapture --rednose` (all tests)
- `python3 manage.py test --nocapture --rednose ackrep_core.test.test_core` (tests for _core only)
- `python3 manage.py test --nocapture --rednose ackrep_core.test.test_web` (tests for _web only)
- `python3 manage.py test --nocapture --rednose ackrep_core.test.test_core:TestCases1` (all tests of one class)
- `python3 manage.py test --nocapture --rednose ackrep_core.test.test_core:TestCases1.test_00` (one specific test)


Usual test execution with  `python -m unittest <path>` will not work because django is needed to create an empty test-database etc.

At the current stage frontend testing does not happen. However the backend introduces some *unit_tests_comments* (`utc_...`) to the served html sources, such that the tests cases can roughly check if the expected content is shown.
