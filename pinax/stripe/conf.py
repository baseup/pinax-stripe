import importlib

from django.conf import settings  # noqa
from django.core.exceptions import ImproperlyConfigured

from appconf import AppConf


def load_path_attr(path):
    i = path.rfind(".")
    module, attr = path[:i], path[i + 1:]
    try:
        mod = importlib.import_module(module)
    except ImportError as e:
        raise ImproperlyConfigured(
            "Error importing {0}: '{1}'".format(module, e)
        )
    try:
        attr = getattr(mod, attr)
    except AttributeError:
        raise ImproperlyConfigured(
            "Module '{0}' does not define a '{1}'".format(module, attr)
        )
    return attr


class PinaxStripeAppConf(AppConf):

    PUBLIC_KEY = None
    SECRET_KEY = None
    API_VERSION = "2012-11-07"
    INVOICE_FROM_EMAIL = "billing@example.com"
    PLANS = {}
    DEFAULT_PLAN = None
    HOOKSET = "pinax.stripe.hooks.DefaultHookSet"
    SEND_EMAIL_RECEIPTS = True
    SUBSCRIPTION_REQUIRED_EXCEPTION_URLS = []
    SUBSCRIPTION_REQUIRED_REDIRECT = None

    class Meta:
        prefix = "pinax_stripe"
        required = ["PUBLIC_KEY", "SECRET_KEY", "API_VERSION"]

    def configure_hookset(self, value):
        return load_path_attr(value)()