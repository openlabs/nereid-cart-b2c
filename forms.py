# -*- coding: UTF-8 -*-
'''
    nereid_cart.forms

    Forms used in the cart

    :copyright: (c) 2010-2011 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
    '''
from wtforms import Form, validators
from wtforms import IntegerField, FloatField


_VDTR = [validators.Required()]


class AddtoCartForm(Form):
    """
    A simple add to cart form
    """
    quantity = FloatField('Quantity', default=1.0, validators=_VDTR)
    product = IntegerField('Product', validators=_VDTR)
