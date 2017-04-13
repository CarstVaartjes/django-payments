from __future__ import unicode_literals

import stripe
from django import forms
from django.utils.translation import ugettext as _

from .. import PaymentStatus

class StripeFormMixin(object):

    source = None

    def clean(self):
        data = self.cleaned_data

        if not self.errors:
            if not self.payment.transaction_id:
                stripe.api_key = self.provider.secret_key
                try:
                    self.source = stripe.Source.create(
                        capture=False,
                        amount=int(self.payment.total * 100),
                        currency=self.payment.currency,
                        type='ideal',
                        metadata={self.payment.id},
                        description='%s %s' % (
                            self.payment.billing_last_name,
                            self.payment.billing_first_name),
                        redirect={
                            'return_url': self.payment.get_success_url()
                        },
                    )
                except stripe.CardError as e:
                    # Making sure we retrieve the charge
                    charge_id = e.json_body['error']['charge']
                    self.charge = stripe.Charge.retrieve(charge_id)
                    # Checking if the charge was fraudulent
                    self._handle_potentially_fraudulent_charge(
                        self.charge, commit=False)
                    # The card has been declined
                    self._errors['__all__'] = self.error_class([str(e)])
                    self.payment.change_status(PaymentStatus.ERROR, str(e))
            else:
                msg = _('This payment has already been processed.')
                self._errors['__all__'] = self.error_class([msg])

        return data

    def save(self):
        self.payment.transaction_id = self.source.id
        self.payment.attrs.source = stripe.util.json.dumps(self.source)
        self.payment.change_status(PaymentStatus.PREAUTH)

