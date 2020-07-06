#!/bin/sh
set -e


if [ "x$DJANGO_MANAGEPY_MIGRATE" = 'xon' ]; then

    # create an empty database
    python manage.py migrate --noinput

    # this is the place where fixtures could be loaded

fi

exec "$@"
