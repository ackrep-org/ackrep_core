import os
# default for cmd run, env var for docker run
broker_url = os.environ.get("CELERY_BROKER_URL") if os.environ.get("CELERY_BROKER_URL") else 'pyamqp://guest@localhost//'
result_backend = os.environ.get("CELERY_RESULT_BACKEND") if os.environ.get("CELERY_RESULT_BACKEND") else 'rpc://'
# print("Using Celery broker", broker_url)
# print("Using result backend", result_backend)
task_serializer = 'pickle'
result_serializer = 'pickle'
accept_content = ['pickle']
timezone = 'Europe/Berlin'
enable_utc = True