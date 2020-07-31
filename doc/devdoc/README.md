# Developer Documentation

## Unittests

As the software is still an early prototype and defining the concrete feature set is subject to ongoing research, only a fraction of the functionality is already covered by tests. However this fraction will increase in the future. The unittest depend on data which is maintained outside of this repo: It is assumed that there is a copy of the `acrep_data` repository named `acrep_data_for_unittests` next to it (see [directory layout](https://github.com/cknoll/ackrep_deployment#directory-layout)) and that its HEAD points to a defined commit (see `ackrep_core.core.test.test_core.default_repo_head_hash`).


There are several options to run the tests. The following is recommended (`--rednose` is optional):

- `python3 manage.py test --nocapture --rednose` (all tests)
- `python3 manage.py test --nocapture --rednose ackrep_core.test.test_core` (tests for _core only)
- `python3 manage.py test --nocapture --rednose ackrep_core.test.test_web` (tests for _web only)
- `python3 manage.py test --nocapture --rednose ackrep_core.test.test_core:TestCases1` (all tests of one class)
- `python3 manage.py test --nocapture --rednose ackrep_core.test.test_core:TestCases1.test_00` (one specific test)

Slow tests are skipped by default. Enable them with `python3 manage.py test --include-slow ...`.


Usual test execution with  `python -m unittest <path>` will not work because django is needed to create an empty test-database etc.

At the current stage frontend testing does not happen. However the backend introduces some *unit_tests_comments* (`utc_...`) to the served html sources, such that the tests cases can roughly check if the expected content is shown.

## Terminology

#### Entity Key
To each entity there is an associated entity-key (matching regex: `[A-Z0-9]{5}`). This key identifies an entity in the repository. This is **not** the primary key for the database. 

## Windows

When running ackrep_web under Windows, several small issues may occur.

#### Symbolic links

Symbolic links are used to make images generated at runtime available as static files. Windows does support symbolic links, but only under the following circumstances:
- Running the webserver with administrator privileges
- Starting from Windows 10 Creators Update, creating symbolic links is possible as an unprivileged user after enabling [Developer Mode](https://blogs.windows.com/windowsdeveloper/2016/12/02/symlinks-windows-10/). To use this feature from Python, a Python version >= 3.8 is required.

#### Removal of Git-directories

The "merge request" feature automatically clones Git repositories into local directories.
These are supposed to be automatically removed, e.g. when deleting the merge request.
This may fail silently because the GitPython module locks some files.
If this happens you can always remove the directory manually.
