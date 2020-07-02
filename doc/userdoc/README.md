This document briefly summarizes the important commands.


- `cd $ACKREP_CORE_DIR; rm -f db.sqlite3; python manage.py migrate --run-syncdb`
    - delete database file (if it exists) and create a new and empty database
- `cd $ACKREP_DATA_DIR; ackrep --load-repo-to-db ./`
    - crawl the current directory for `metadata.yml`-files and populate the database with the respective entities
- `cd $ACKREP_DATA_DIR; ackrep --check-solution demo_problem/metadata.yml`
    - check the solution against the respective problem specifications
- `ackrep --help`
    - print information about available commands
