# -*- coding: UTF-8 -*-
'''
    nereid_cart.sale

    Sales modules changes to fit nereid

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['Sale']
__metaclass__ = PoolMeta


class Sale:
    '''Add a boolean to indicate if the order originated from a shopping cart.
    '''
    __name__ = 'sale.sale'

    is_cart = fields.Boolean(
        'Is Cart Order?', readonly=True, select=True
    )
    website = fields.Many2One(
        'nereid.website', 'Website', readonly=True, select=True
    )
    nereid_user = fields.Many2One(
        'nereid.user', 'Nereid User', select=True
    )

    @staticmethod
    def default_is_cart():
        """Dont make this as a default as this would cause orders being placed
        from backend to be placed under default.
        """
        return False
