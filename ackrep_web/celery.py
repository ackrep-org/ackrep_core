from celery import Celery

app = Celery(
    "ackrep_core",
    include=["ackrep_core.core"],
)
app.config_from_object("ackrep_web.celeryconfig")

if __name__ == "__main__":
    app.start()

"""
starting the worker from cli:

cd ackrep_core
celery -A ackrep_web worker -c 2 --loglevel=INFO
"""
