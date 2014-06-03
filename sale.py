# -*- coding: UTF-8 -*-
'''
    nereid_cart.sale

    Sales modules changes to fit nereid

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from nereid import request, current_user
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
    def default_price_list(user=None):
        """Get the pricelist of active user. In the
        event that the logged in user does not have a pricelist set against
        the user, the guest user's pricelist is chosen.

        :param user: active record of the nereid user
        """
        if not has_request_context():
            # Not a nereid request
            return None

        if user is not None and user.party.sale_price_list:
            # If a user was provided and the user has a pricelist, use
            # that
            return user.party.sale_price_list.id

        if not current_user.is_anonymous() and \
                current_user.party.sale_price_list:
            # If the currently logged in user has a pricelist defined, use
            # that
            return current_user.party.sale_price_list.id

        # Since there is no pricelist for the user, use the guest user's
        # pricelist if one is defined.
        guest_user = request.nereid_website.guest_user
        if guest_user.party.sale_price_list:
            return guest_user.party.sale_price_list.id

        return None

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
                if key == 'taxes' and value:
                    new_values[key] = [('set', value)]
            SaleLine.write([order_line], new_values)
            return order_line
        else:
            values = {
                'product': product_id,
                '_parent_sale.currency': self.currency.id,
                '_parent_sale.party': self.party.id,
                'sale': self.id,
                'type': 'line',
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
                    new_values[key] = [('set', value)]
            return SaleLine.create([new_values])[0]


class SaleLine:
    __name__ = 'sale.line'

    def refresh_taxes(self):
        "Refresh taxes of sale line"
        SaleLine = Pool().get('sale.line')

        values = self.on_change_product()
        if 'taxes' in values:
            SaleLine.write([self], {
                'taxes': [('set', values['taxes'])]
            })
