# -*- coding: UTF-8 -*-
'''
    nereid_cart.forms

    Forms used in the cart

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
from flask_wtf import Form
from wtforms import validators, IntegerField, FloatField
from nereid.contrib.locale import make_lazy_gettext

_ = make_lazy_gettext('nereid_cart_b2c')
_VDTR = [validators.Required(message=_("This field is required"))]


class AddtoCartForm(Form):
    """
    A simple add to cart form
    """
    quantity = FloatField(_('Quantity'), default=1.0, validators=_VDTR)
    product = IntegerField(_('Product'), validators=_VDTR)
