from django import template
from ackrep_core.release import __version__
from django.conf import settings

register = template.Library()


@register.filter
def get_version(_):
    return __version__


@register.filter
def get_last_deployment(_):

    last_deployment = getattr(settings, "LAST_DEPLOYMENT", "<not available>")
    return last_deployment
