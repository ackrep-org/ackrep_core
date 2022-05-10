from celery import Celery

app = Celery('ackrep_core',
             broker='amqp://',
             backend='rpc://',
             include=['ackrep_core.core'])
app.config_from_object('ackrep_web.celeryconfig')

# Optional configuration, see the application user guide.
app.conf.update(
    result_expires=3600,
)

if __name__ == '__main__':
    app.start()