"""
Django settings for the ackrep_core django project.

Generated by 'django-admin startproject' using Django 2.1.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
import sys
import deploymentutils as du


# DEVMODE should be False by default.
# Exceptions:
#   - server program is started by `manage.py runserver` command
#   - DEVMODE explicitly activated by ENV-Variable DJANGO_DEVMODE
# Also, for  some management commands (on the production server) we want to explicitly switch off DEVMODE

# export DJANGO_DEVMODE=True; py3 manage.py <some_command>
env_devmode = os.getenv("DJANGO_DEVMODE")
if env_devmode is None:
    DEVMODE = "runserver" in sys.argv
else:
    DEVMODE = env_devmode.lower() == "true"

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
# this is the repo root (where manage.py lives)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT_DIR = os.path.dirname(BASE_DIR)

# Note: catching a FileNotFoundException here leads to strange error.
# ("RuntimeError: Script manage.py does not exist.") -> use if-based sanity check
cfgpath = os.path.join(PARENT_DIR, "config.ini")
if os.path.isfile(cfgpath):
    config = du.get_nearest_config(cfgpath, devmode=DEVMODE)
else:
    config = du.get_nearest_config(os.path.join(BASE_DIR, "config-example.ini"), devmode=DEVMODE)
    if not DEVMODE:

        class UnsafeConfiguration(BaseException):
            pass

        msg = f"Using the example config is not allowed outside development mode.{DEVMODE} " + str(sys.argv)
        # raise UnsafeConfiguration(msg)

        # TODO:
        # This security issue is only relevant for the ackrep-server, not for the command line interface (cli).
        # Cli should work directly after installing. However, we prevent to accidentally run the production
        # webserver with the example config

# this serves to check the path via the debugging page
CONFIG_PATH = config.path

# TODO: save the config path and DEVMODE to logfile

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# (the following key is only used for local testing but not for production deployment)
SECRET_KEY = config("SECRET_KEY")
SECRET_CIRCLECI_WEBHOOK_KEY = config("SECRET_CIRCLECI_WEBHOOK_KEY")
SECRET_CIRCLECI_API_KEY = config("SECRET_CIRCLECI_API_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
# note this might be influenced by DEVMODE
DEBUG = config("DEBUG", cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=config.Csv())


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_bleach",
    "django_nose",
    "ackrep_core",
    "ackrep_web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "ackrep_web.middleware.statuscodewriter.StatusCodeWriterMiddleware",
]

X_FRAME_OPTIONS = "SAMEORIGIN"

# "settings" is the name of the django-projects settings
ROOT_URLCONF = "ackrep_core_django_settings.urls"
WSGI_APPLICATION = "ackrep_core_django_settings.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

# allow for separate databases, e.g. to handle unittests that make cli calls to `ackrep`
database_path = os.environ.get("ACKREP_DATABASE_PATH")
if not (database_path):
    # use default db name
    database_path = os.path.join(BASE_DIR, "db.sqlite3")

    test_db_settings = {
        "TEST": {
            "ENGINE": "django.db.backends.sqlite3",
            # TODO: ensure that this is consistent with test_core.py
            "NAME": os.path.join(BASE_DIR, "db_for_unittests.sqlite3"),
        }
    }
else:
    # use the provided path also as path for the test db

    test_db_settings = {
        "TEST": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": database_path,
        }
    }


DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": database_path, **test_db_settings}}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = "en-us"

# TODO: consider using config("TIME_ZONE") (which is currently "Europe/Berlin")
TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = "/static/"

# The absolute path to the directory where collectstatic will collect static files for deployment.
STATIC_ROOT = os.path.join(BASE_DIR, "static")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# path where db-backups are dumped to
BACKUP_PATH = os.path.join(BASE_DIR, "db_backups")

TEST_RUNNER = "django_nose.NoseTestSuiteRunner"

ACKREP_DATA_BASE_URL = config("ACKREP_DATA_BASE_URL")
ACKREP_DATA_BRANCH = config("ACKREP_DATA_BRANCH")

DEFAULT_ENVIRONMENT_KEY = "CDAMA"  # "YJBOX"

ENTITY_TIMEOUT = 3 * 60  # s

try:
    with open(os.path.join(BASE_DIR, "deployment_date.txt")) as txtfile:
        LAST_DEPLOYMENT = txtfile.read().strip()
except FileNotFoundError:
    LAST_DEPLOYMENT = "<not available>"
