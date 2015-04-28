# -*- coding: UTF-8 -*-
'''
    nereid_cart.sale

    Sales modules changes to fit nereid

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
from functools import partial
from babel import numbers
from decimal import Decimal

from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from trytond.transaction import Transaction
from nereid import current_user, url_for, request, redirect, flash, abort
from nereid.contrib.locale import make_lazy_gettext
from nereid.ctx import has_request_context
_ = make_lazy_gettext('nereid_cart_b2c')

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
        the user, the channel's pricelist is chosen.

        :param user: active record of the nereid user
        """
        User = Pool().get('res.user')
        user = User(Transaction().user)
        channel_price_list = user.current_channel.price_list.id if \
            user.current_channel else None

        if not has_request_context():
            # Not a nereid request
            return channel_price_list

        # If control reaches here, then this is a nereid request. Lets try
        # and personalise the pricelist of the user logged in.
        if current_user.is_anonymous():
            # Sorry anonymous users, you get the shop price
            return channel_price_list

        if current_user.party.sale_price_list:
            # There is a sale pricelist for the specific user's party.
            return current_user.party.sale_price_list.id

        return channel_price_list

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
        Product = Pool().get('product.product')

        order_line = self.find_existing_line(product_id)
        product = Product(product_id)

        values = {
            'product': product_id,
            '_parent_sale.currency': self.currency.id,
            '_parent_sale.party': self.party.id,
            '_parent_sale.price_list': (
                self.price_list.id if self.price_list else None
            ),
            'type': 'line',
        }

        old_price = Decimal('0.0')
        if order_line:
            old_price = order_line.unit_price
            values.update({
                'unit': order_line.unit.id,
                'quantity': quantity if action == 'set'
                    else quantity + order_line.quantity,
            })
        else:
            order_line = SaleLine()
            values.update({
                'sale': self.id,
                'sequence': 10,
                'quantity': quantity,
                'unit': None,
                'description': None,
            })
            values.update(SaleLine(**values).on_change_product())

        values.update(SaleLine(**values).on_change_quantity())

        if old_price and old_price != values['unit_price']:
            vals = (
                product.name, self.currency.symbol, old_price,
                self.currency.symbol, values['unit_price']
            )
            if old_price < values['unit_price']:
                message = _(
                    "The unit price of product %s increased from %s%d to "
                    "%s%d." % vals
                )
            else:
                message = _(
                    "The unit price of product %s dropped from %s%d "
                    "to %s%d." % vals
                )
            flash(message)

        for key, value in values.iteritems():
            if '.' not in key:
                setattr(order_line, key, value)
        return order_line


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
        if purpose == 'cart':
            currency_format = partial(
                numbers.format_currency, currency=self.sale.currency.code,
                locale=request.nereid_language.code
            )
            number_format = partial(
                numbers.format_number, locale=request.nereid_language.code
            )
            res.update({
                'id': self.id,
                'display_name': (
                    self.product and self.product.name or self.description
                ),
                'url': self.product.get_absolute_url(_external=True),
                'image': (
                    self.product.default_image.transform_command().thumbnail(
                        150, 150, 'a'
                    ).url() if self.product.default_image else None
                ),
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

    def add_to(self, sale):
        """
        Copy sale_line to new sale.

        Downstream modules can override this method to add change this behaviour
        of copying.

        :param sale: Sale active record.

        :return: Newly created sale_line
        """
        return sale._add_or_update(self.product.id, self.quantity)

    def validate_for_product_inventory(self):
        """
        This method validates the sale line against the product's inventory
        attributes. This method requires request context.
        """
        if has_request_context() and not self.product.can_buy_from_eshop():
            flash(_('This product is no longer available'))
            abort(redirect(request.referrer))
