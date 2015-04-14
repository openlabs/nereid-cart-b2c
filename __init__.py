# -*- coding: UTF-8 -*-
'''
    nereid_cart.

    Cart

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
from trytond.pool import Pool

from product import Product
from sale import Sale, SaleLine
from cart import Cart
from website import Website
from channel import SaleChannel


def register():
    Pool.register(
        Product,
        Sale,
        SaleChannel,
        SaleLine,
        Cart,
        Website,
        type_="model", module="nereid_cart_b2c"
    )
