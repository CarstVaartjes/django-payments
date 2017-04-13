from __future__ import unicode_literals
from decimal import Decimal

import stripe

from .forms import StripeFormMixin
from .. import RedirectNeeded, PaymentError, PaymentStatus
from ..core import BasicProvider


class StripeSourcesProvider(BasicProvider):

    form_class = StripeFormMixin

    def __init__(self, public_key, secret_key, image='', name='', **kwargs):
        stripe.api_key = secret_key
        self.secret_key = secret_key
        self.public_key = public_key
        self.image = image
        self.name = name
        super(StripeSourcesProvider, self).__init__(**kwargs)

    def get_form(self, payment, data=None):
        if payment.status == PaymentStatus.WAITING:
            payment.change_status(PaymentStatus.INPUT)

        form = self.form_class(
            data=data, payment=payment, provider=self)

        if form.is_valid():
            form.save()
            if form.source.flow == 'redirect':
                raise RedirectNeeded(form.source.redirect.url)
            else:
                raise RedirectNeeded(payment.get_success_url())
        return form

    def charge(self, payment, amount=None):
        amount = int((amount or payment.total) * 100)
        charge = stripe.Charge.create(
            amount=amount,
            currency=payment.currency,
            source=payment.transaction_id,
        )
        payment.attrs.charge = stripe.util.json.dumps(charge)
        if charge.status == 'succeeded':
            payment.change_status(PaymentStatus.CONFIRMED)
        return Decimal(amount) / 100

    def capture(self, payment, amount=None):
        amount = int((amount or payment.total) * 100)
        charge = stripe.Charge.retrieve(payment.attrs.charge['id'])
        try:
            charge.capture(amount=amount)
        except stripe.InvalidRequestError as e:
            payment.change_status(PaymentStatus.REFUNDED)
            raise PaymentError('Payment already refunded')
        payment.attrs.capture = stripe.util.json.dumps(charge)
        return Decimal(amount) / 100

    def release(self, payment):
        charge = stripe.Charge.retrieve(payment.transaction_id)
        charge.refund()
        payment.attrs.release = stripe.util.json.dumps(charge)

    def refund(self, payment, amount=None):
        amount = int((amount or payment.total) * 100)
        charge = stripe.Charge.retrieve(payment.transaction_id)
        charge.refund(amount=amount)
        payment.attrs.refund = stripe.util.json.dumps(charge)
        return Decimal(amount) / 100


class StripeCardProvider(StripeSourcesProvider):
    pass

