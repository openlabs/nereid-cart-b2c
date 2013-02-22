# -*- coding: UTF-8 -*-
'''
    nereid_cart.

    Cart

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
from trytond.pool import Pool

from .product import *
from .sale import *
from .cart import *
from .website import *


def register():
    Pool.register(
        Product,
        Sale,
        Cart,
        Website,
        type_="model", module="nereid_cart_b2c"
    )
