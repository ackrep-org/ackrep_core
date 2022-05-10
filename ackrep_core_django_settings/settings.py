"""
Django settings for the ackrep_core django project.

Generated by 'django-admin startproject' using Django 2.1.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# (the following key is only used for local testing but not for production deployment)
SECRET_KEY = "4(bbovkj6lx0txurbo4uozpr+sk&y%cu-o$8w0kww&cgyp)hww"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "demo.ackrep.org"]


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

    test_db_settings = {"TEST": {"ENGINE": "django.db.backends.sqlite3", "NAME": database_path,}}


DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": database_path, **test_db_settings}}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",},
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = "en-us"

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

# static url of the current ackrep_data branch running on the server (used to show link to source code)
ACKREP_DATA_BASE_URL = "https://github.com/ackrep-org/ackrep_data.git"
ACKREP_DATA_BRANCH = "tree/systemModelsCatalog"

# refresh rate of page when waiting for check to load [ms]
REFRESH_TIMEOUT = 2000

# The following mechanism allows to incorporate custom settings (which are maintained
# outside of the repository, see ackrep_deployment)

try:
    # noinspection PyUnresolvedReferences
    from .custom_settings import *
except ImportError:
    pass
except SyntaxError:
    print("\n" * 2, " !! Warning: Syntax-Error in custom_settings.py !!", "\n\n")
