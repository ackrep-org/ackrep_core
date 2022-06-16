import os
from ackrep_core_django_settings import settings

# default for cmd run, env var for docker run
if os.environ.get("USE_CELERY_BROKER_URL") == "True":
    broker_url = settings.CELERY_BROKER_URL
else:
    broker_url = "pyamqp://guest@localhost//"
# print(broker_url)
if os.environ.get("USE_CELERY_RESULT_BACKEND") == "True":
    result_backend = settings.CELERY_RESULT_BACKEND
else:
    result_backend = "rpc://"

# print("ci", os.environ.get("CI"))
# if os.environ.get("CI") == "true":
#     # broker_url = 'redis://localhost:6379/0'
#     # broker_url = 'redis://172.17.0.1:6379/0'
#     # broker_url = 'amqp://myuser:mypassword@localhost:5672/myvhost'
#     broker_url = "pyamqp://guest@localhost//"
#     result_backend = "rpc://"
# print(broker_url)

# result serializer has to be pickle to pass CompletedProcess Objects
task_serializer = "pickle"
result_serializer = "pickle"
accept_content = ["pickle"]
timezone = "Europe/Berlin"
enable_utc = True
result_expires = settings.RESULT_EXPIRATION_TIME
