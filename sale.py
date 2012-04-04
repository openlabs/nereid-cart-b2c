# -*- coding: UTF-8 -*-
'''
    nereid_cart.sale

    Sales modules changes to fit nereid

    :copyright: (c) 2010-2012 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
from trytond.model import ModelView, ModelSQL, fields


class Sale(ModelSQL, ModelView):
    '''Add a boolean to indicate if the order originated from a shopping cart.
    '''
    _name = 'sale.sale'

    is_cart = fields.Boolean(
        'Is Cart Order?', readonly=True, select=1
    )
    website = fields.Many2One(
        'nereid.website', 'Website', readonly=True, select=1
    )
    nereid_user = fields.Many2One('nereid.user', 'Nereid User')

    def default_is_cart(self):
        """Dont make this as a default as this would cause orders being placed
        from backend to be placed under default.
        """
        return False

Sale()
