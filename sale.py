# -*- coding: UTF-8 -*-
'''
    nereid_cart.sale

    Sales modules changes to fit nereid

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
from functools import partial
from babel import numbers

from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from trytond.transaction import Transaction
from nereid import current_user, url_for, request
from nereid.ctx import has_request_context

__all__ = ['Sale', 'SaleLine']
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

    @staticmethod
    def default_price_list():
        """Get the pricelist of active user. In the
        event that the logged in user does not have a pricelist set against
        the user, the shop's pricelist is chosen.

        :param user: active record of the nereid user
        """
        User = Pool().get('res.user')
        user = User(Transaction().user)
        shop_price_list = user.shop.price_list.id if user.shop else None

        if not has_request_context():
            # Not a nereid request
            return shop_price_list

        # If control reaches here, then this is a nereid request. Lets try
        # and personalise the pricelist of the user logged in.
        if current_user.is_anonymous():
            # Sorry anonymous users, you get the shop price
            return shop_price_list

        if current_user.party.sale_price_list:
            # There is a sale pricelist for the specific user's party.
            return current_user.party.sale_price_list.id

        return shop_price_list

    def refresh_taxes(self):
        '''
        Reload taxes of all sale lines
        '''
        for line in self.lines:
            line.refresh_taxes()

    def find_existing_line(self, product_id):
        """Return existing sale line for given product"""
        SaleLine = Pool().get('sale.line')

        lines = SaleLine.search([
            ('sale', '=', self.id),
            ('product', '=', product_id),
        ])
        return lines[0] if lines else None

    def _add_or_update(self, product_id, quantity, action='set'):
        '''Add item as a line or if a line with item exists
        update it for the quantity

        :param product: ID of the product
        :param quantity: Quantity
        :param action: set - set the quantity to the given quantity
                       add - add quantity to existing quantity
        '''
        SaleLine = Pool().get('sale.line')

        order_line = self.find_existing_line(product_id)
        if order_line:
            values = {
                'product': product_id,
                '_parent_sale.currency': self.currency.id,
                '_parent_sale.party': self.party.id,
                '_parent_sale.price_list': (
                    self.price_list.id if self.price_list else None
                ),
                'unit': order_line.unit.id,
                'quantity': quantity if action == 'set'
                    else quantity + order_line.quantity,
                'type': 'line',
            }
            values.update(SaleLine(**values).on_change_quantity())

            new_values = {}
            for key, value in values.iteritems():
                if '.' not in key:
                    new_values[key] = value
            SaleLine.write([order_line], new_values)
            return order_line
        else:
            values = {
                'product': product_id,
                '_parent_sale.currency': self.currency.id,
                '_parent_sale.party': self.party.id,
                'sale': self.id,
                'type': 'line',
                'sequence': 10,
                'quantity': quantity,
                'unit': None,
                'description': None,
            }
            if self.price_list:
                values['_parent_sale.price_list'] = self.price_list.id
            values.update(SaleLine(**values).on_change_product())
            values.update(SaleLine(**values).on_change_quantity())
            new_values = {}
            for key, value in values.iteritems():
                if '.' not in key:
                    new_values[key] = value
                if key == 'taxes' and value:
                    new_values[key] = [('add', value)]
            return SaleLine.create([new_values])[0]


class SaleLine:
    __name__ = 'sale.line'

    def refresh_taxes(self):
        "Refresh taxes of sale line"
        SaleLine = Pool().get('sale.line')

        values = SaleLine(self.id).on_change_product()
        if 'taxes' in values:
            self.taxes = values['taxes']
            self.save()

    def serialize(self, purpose=None):
        """
        Serialize SaleLine data
        """
        res = {}
        currency_format = partial(
            numbers.format_currency, currency=self.sale.currency.code,
            locale=request.nereid_language.code
        )
        number_format = partial(
            numbers.format_number, locale=request.nereid_language.code
        )
        if purpose == 'cart':
            res.update({
                'id': self.id,
                'product': self.product.serialize(purpose),
                'quantity': number_format(self.quantity),
                'unit': self.unit.symbol,
                'unit_price': currency_format(self.unit_price),
                'amount': currency_format(self.amount),
                'remove_url': url_for(
                    'nereid.cart.delete_from_cart', line=self.id
                ),
            })
        return res
