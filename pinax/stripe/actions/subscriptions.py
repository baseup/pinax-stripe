import datetime

from django.db.models import Q
from django.utils import timezone

import stripe

from .. import hooks, models, utils


class Billing_Thresholds:
    def __init__(self, amount_gte=0, reset_billing_cycle_anchor=False):
        self.amount_gte: int = amount_gte
        self.reset_billing_cycle_anchor: boolean = reset_billing_cycle_anchor


def cancel(subscription, at_period_end=True):
    """
    Cancels a subscription

    Args:
        subscription: the subscription to cancel
        at_period_end: True to cancel at the end of the period, otherwise cancels immediately
    """
    sub = stripe.Subscription(
        subscription.stripe_id,
        stripe_account=subscription.stripe_account_stripe_id,
    ).delete(
        at_period_end=at_period_end,
    )
    return sync_subscription_from_stripe_data(subscription.customer, sub)


def create(customer,
           plan,
           quantity=None,
           trial_days=None,
           token=None,
           coupon=None,
           tax_percent=None,
           billing_thresholds: Billing_Thresholds=None):
    """
    Creates a subscription for the given customer

    Args:
        customer: the customer to create the subscription for
        plan: the plan to subscribe to
        quantity: if provided, the number to subscribe to
        trial_days: if provided, the number of days to trial before starting
        token: if provided, a token from Stripe.js that will be used as the
               payment source for the subscription and set as the default
               source for the customer, otherwise the current default source
               will be used
        coupon: if provided, a coupon to apply towards the subscription
        tax_percent: if provided, add percentage as tax

    Returns:
        the pinax.stripe.models.Subscription object (created or updated)
    """
    quantity = hooks.hookset.adjust_subscription_quantity(customer=customer, plan=plan, quantity=quantity)

    subscription_params = {}
    if trial_days:
        subscription_params["trial_end"] = datetime.datetime.utcnow() + datetime.timedelta(days=trial_days)
    if token:
        subscription_params["source"] = token

    subscription_params["stripe_account"] = customer.stripe_account_stripe_id
    subscription_params["customer"] = customer.stripe_id
    subscription_params["plan"] = plan
    if plan.usage_type == 'licensed':
        subscription_params['quantity'] = quantity
    if billing_thresholds is not None:
        subscription_params['billing_thresholds'] = billing_thresholds.__dict__
    subscription_params["coupon"] = coupon
    subscription_params["tax_percent"] = tax_percent
    resp = stripe.Subscription.create(**subscription_params)

    return sync_subscription_from_stripe_data(customer, resp)


def create_usage_record(subscription_item,
                        quantity=1,
                        timestamp=int(timezone.now().timestamp()),
                        action='increment'):

    resp = stripe.SubscriptionItem.create_usage_record(
        subscription_item.stripe_id,
        quantity=quantity,
        timestamp=timestamp,
        action=action
    )

    return sync_usage_record_from_stripe_data(resp)


def sync_usage_record_from_stripe_data(usage_record):
    sub_item = models.SubscriptionItem.objects.get(stripe_id=usage_record['subscription_item'])

    defaults = {
        'quantity': usage_record['quantity'],
        'timestamp': utils.convert_tstamp(usage_record['timestamp']),
        'subscription_item': sub_item,
    }

    obj, created = models.UsageRecord.objects.get_or_create(
        stripe_id=usage_record['id'],
        defaults=defaults
    )

    return utils.update_with_defaults(obj, defaults, created)


def has_active_subscription(customer):
    """
    Checks if the given customer has an active subscription

    Args:
        customer: the customer to check

    Returns:
        True, if there is an active subscription, otherwise False
    """
    return models.Subscription.objects.filter(
        customer=customer
    ).filter(
        Q(ended_at__isnull=True) | Q(ended_at__gt=timezone.now())
    ).exists()


def is_period_current(subscription):
    """
    Tests if the provided subscription object for the current period

    Args:
        subscription: a pinax.stripe.models.Subscription object to test
    """
    return subscription.current_period_end > timezone.now()


def is_status_current(subscription):
    """
    Tests if the provided subscription object has a status that means current

    Args:
        subscription: a pinax.stripe.models.Subscription object to test
    """
    return subscription.status in subscription.STATUS_CURRENT


def is_valid(subscription):
    """
    Tests if the provided subscription object is valid

    Args:
        subscription: a pinax.stripe.models.Subscription object to test
    """
    if not is_status_current(subscription):
        return False

    if subscription.cancel_at_period_end and not is_period_current(subscription):
        return False

    return True


def retrieve(customer, sub_id):
    """
    Retrieve a subscription object from Stripe's API

    Args:
        customer: a legacy argument, we check that the given
            subscription belongs to the given customer
        sub_id: the Stripe ID of the subscription you are fetching

    Returns:
        the data for a subscription object from the Stripe API
    """
    if not sub_id:
        return
    subscription = stripe.Subscription.retrieve(sub_id, stripe_account=customer.stripe_account_stripe_id)
    if subscription and subscription.customer != customer.stripe_id:
        return
    return subscription


def sync_subscription_from_stripe_data(customer, subscription):
    """
    Synchronizes data from the Stripe API for a subscription

    Args:
        customer: the customer who's subscription you are syncronizing
        subscription: data from the Stripe API representing a subscription

    Returns:
        the pinax.stripe.models.Subscription object (created or updated)
    """
    defaults = dict(
        customer=customer,
        application_fee_percent=subscription["application_fee_percent"],
        cancel_at_period_end=subscription["cancel_at_period_end"],
        canceled_at=utils.convert_tstamp(subscription["canceled_at"]),
        current_period_start=utils.convert_tstamp(subscription["current_period_start"]),
        current_period_end=utils.convert_tstamp(subscription["current_period_end"]),
        ended_at=utils.convert_tstamp(subscription["ended_at"]),
        start=utils.convert_tstamp(subscription["start"]),
        status=subscription["status"],
        trial_start=utils.convert_tstamp(subscription["trial_start"]) if subscription["trial_start"] else None,
        trial_end=utils.convert_tstamp(subscription["trial_end"]) if subscription["trial_end"] else None
    )

    if 'items' in subscription and len(subscription['items']['data']) > 1:
        defaults['plan'] = models.Plan.objects.get(
            stripe_id=subscription['items']['data'][0]['plan']['id'])
        defaults['quantity'] = subscription['items']['data'][0]['quantity']
    else:
        defaults['plan'] = models.Plan.objects.get(
            stripe_id=subscription['plan']['id'])
        defaults['quantity'] = subscription['quantity']

    sub, created = models.Subscription.objects.get_or_create(
        stripe_id=subscription["id"],
        defaults=defaults
    )
    sub = utils.update_with_defaults(sub, defaults, created)

    items_to_keep = []

    if 'items' in subscription and len(subscription['items']['data']) > 0:
        for item in subscription['items']['data']:
            defaults = dict(
                created=utils.convert_tstamp(item['created']),
                metadata=item['metadata'],
                plan=models.Plan.objects.get(stripe_id=item['plan']['id']),
                subscription=sub
            )

            if item['plan']['usage_type'] == 'licensed':
                defaults.update({'quantity': item['quantity']})

            sub_item, created = models.SubscriptionItem.objects.get_or_create(
                stripe_id=item['id'],
                defaults=defaults
            )
            utils.update_with_defaults(sub_item, defaults, created)

            items_to_keep.append(item['id'])

    models.SubscriptionItem.objects.filter(
        subscription=sub
    ).exclude(
        stripe_id__in=items_to_keep
    ).delete()

    return sub


def update(subscription,
           plan=None,
           quantity=None,
           prorate=True,
           coupon=None,
           charge_immediately=False,
           billing_thresholds=None):
    """
    Updates a subscription

    Args:
        subscription: the subscription to update
        plan: optionally, the plan to change the subscription to
        quantity: optionally, the quantity of the subscription to change
        prorate: optionally, if the subscription should be prorated or not
        coupon: optionally, a coupon to apply to the subscription
        charge_immediately: optionally, whether or not to charge immediately
    """
    stripe_subscription = subscription.stripe_subscription
    if plan:
        stripe_subscription.plan = plan
    if quantity:
        if plan.usage_type == 'licensed':
            stripe_subscription.quantity = quantity
        else:
            delattr(stripe_subscription, 'quantity')
    if billing_thresholds is not None:
        stripe.subscription.billing_thresholds = billing_thresholds
    if not prorate:
        stripe_subscription.prorate = False
    if coupon:
        stripe_subscription.coupon = coupon
    if charge_immediately:
        if stripe_subscription.trial_end is not None and utils.convert_tstamp(stripe_subscription.trial_end) > timezone.now():
            stripe_subscription.trial_end = "now"
    sub = stripe_subscription.save()
    customer = models.Customer.objects.get(pk=subscription.customer.pk)
    return sync_subscription_from_stripe_data(customer, sub)
