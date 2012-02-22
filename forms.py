# -*- coding: UTF-8 -*-
'''
    nereid_cart.forms

    Forms used in the cart

    :copyright: (c) 2010-2012 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
    '''
from wtforms import Form, validators
from wtforms import IntegerField, FloatField

from .i18n import _

_VDTR = [validators.Required(message=_("This field is required"))]


class AddtoCartForm(Form):
    """
    A simple add to cart form
    """
    quantity = FloatField(_('Quantity'), default=1.0, validators=_VDTR)
    product = IntegerField(_('Product'), validators=_VDTR)
