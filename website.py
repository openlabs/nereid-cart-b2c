# -*- coding: UTF-8 -*-
'''
    nereid_cart.website

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
from functools import partial

from babel import numbers
from nereid import render_template, login_required, request, current_user, \
    route
from nereid.contrib.pagination import Pagination
from nereid.globals import session
from trytond import backend
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


__all__ = ['Website']
__metaclass__ = PoolMeta


class Website:
    """
    Website
    """
    __name__ = 'nereid.website'

    #: The channel in which the sales will be registered. It is recommended
    #: to create a different channel for each website. The channel's price_list,
    #: warehouse and sale order sequences are respected by nereid cart
    #:
    #: .. versionadded::3.2.1.0
    #:
    channel = fields.Many2One(
        'sale.channel', 'Channel', required=True,
        domain=[
            ('create_users', '=', Eval('application_user')),
            ('source', '=', 'webshop'),
        ],
        depends=['application_user']
    )

    #: The warehouse to be used in the sale order when an order on this site is
    #: created
    #:
    #: .. versionchanged::3.2.1.0
    #:
    #:     This information is now fetched from channel
    warehouse = fields.Function(
        fields.Many2One('stock.location', 'Warehouse'),
        'get_fields_from_channel'
    )

    #: Stock location to be used when calculating the stock.
    #:
    #: .. versionchanged::3.2.1.0
    #:
    #:     This information is now fetched from channel
    stock_location = fields.Function(
        fields.Many2One('stock.location', 'Stock Location'),
        'get_fields_from_channel'
    )

    #: Guest user to identify guest carts
    guest_user = fields.Many2One(
        'nereid.user', 'Guest user', required=True
    )

    #: Payment term used for cart sale
    #:
    #: .. versionchanged::3.2.1.0
    #:
    #:     This information is now fetched from channel
    payment_term = fields.Function(
        fields.Many2One('account.invoice.payment_term', 'Payment Term'),
        'get_fields_from_channel'
    )

    @classmethod
    def __setup__(cls):
        super(Website, cls).__setup__()
        cls.per_page = 10

    @classmethod
    def __register__(cls, module_name):
        super(Website, cls).__register__(module_name)

        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        table = TableHandler(cursor, cls, module_name)

        table.not_null_action('warehouse', action='remove')
        table.not_null_action('stock_location', action='remove')
        table.not_null_action('payment_term', action='remove')

    def get_fields_from_channel(self, name):
        """
        Return the information from the channel assigned to the website.
        """
        if name == 'stock_location':
            return self.channel.warehouse.storage_location.id

        return getattr(self.channel, name).id

    @classmethod
    def account_context(cls):
        """
        When the account page is displayed it may be required to display a
        lot of information, and this depends from site to site. So rather than
        rewriting the render page everytime it is optimal to have a context
        being rebuilt by subclassing.

        This basic context builder builds sales, invoices and shipments,
        (only last 5) of the customer.

        To add more items to the context, subclass the method and call super
        to get the result of this method and then add your content to it.

        :return: A dictionary of items to render a context
        """
        Sale = Pool().get('sale.sale')
        Invoice = Pool().get('account.invoice')
        Shipment = Pool().get('stock.shipment.out')

        sales = Pagination(Sale, [
            ('party', '=', current_user.party.id),
            ('state', '!=', 'draft')
        ], 1, 5)

        invoices = Pagination(Invoice, [
            ('party', '=', current_user.party.id),
            ('state', '!=', 'draft'),
        ], 1, 5)

        shipments = Pagination(Shipment, [
            ('customer', '=', current_user.party.id),
            ('state', '!=', 'draft'),
        ], 1, 5)

        context = super(Website, cls).account_context()
        context.update({
            'sales': sales,
            'invoices': invoices,
            'shipments': shipments,
        })
        return context

    @classmethod
    @login_required
    @route('/account')
    def account(cls):
        'Account Details'
        account_context = cls.account_context()
        sales = account_context.get('sales')
        invoices = account_context.get('invoices')
        shipments = account_context.get('shipments')
        return render_template(
            'account.jinja', sales=sales,
            invoices=invoices, shipments=shipments,
            user=current_user
        )

    @classmethod
    @login_required
    @route('/sales')
    def sales(cls, page=1):
        'All sales'
        Sale = Pool().get('sale.sale')
        sales = Pagination(Sale, [
            ('party', '=', current_user.party.id),
            ('state', '!=', 'draft')
        ], page, cls.per_page)
        return render_template('sales.jinja', sales=sales)

    @classmethod
    @login_required
    @route('/invoices')
    def invoices(cls, page=1):
        'List of Invoices'
        Invoice = Pool().get('account.invoice')
        invoices = Pagination(Invoice, [
            ('party', '=', current_user.party.id),
            ('state', '!=', 'draft')
        ], page, cls.per_page)
        return render_template('invoices.jinja', invoices=invoices)

    @classmethod
    @login_required
    @route('/shipments')
    def shipments(cls, page=1):
        'List of Shipments'
        Shipment = Pool().get('stock.shipment.out')
        shipments = Pagination(Shipment, [
            ('customer', '=', current_user.party.id),
            ('state', '!=', 'draft'),
        ], page, cls.per_page)
        return render_template('shipments.jinja', shipments=shipments)

    @classmethod
    def set_currency(cls):
        """Sets the currency for current session. A change in the currency
        should reset the cart if the currency of the cart is not the same as
        the one here
        """
        Cart = Pool().get('nereid.cart')

        rv = super(Website, cls).set_currency()

        # TODO: If currency has changed drop the cart
        # This behaviour needs serious improvement. Probably create a new cart
        # with all items in this cart and then drop this one
        cart = Cart.open_cart()
        if cart.sale and cart.sale.currency.id != session['currency']:
            Cart.clear_cart()

        return rv

    @classmethod
    def _user_status(cls):
        """Add cart size and amount to the dictionary
        """
        Cart = Pool().get('nereid.cart')
        cart = Cart.open_cart()

        rv = super(Website, cls)._user_status()

        if cart.sale:
            # Build locale based formatters
            currency_format = partial(
                numbers.format_currency, currency=cart.sale.currency.code,
                locale=request.nereid_language.code
            )

            rv['cart'] = {
                'lines': [
                    line.serialize(purpose='cart')
                    for line in cart.sale.lines
                ],
                'empty': len(cart.sale.lines) > 0,
                'total_amount': currency_format(cart.sale.total_amount),
                'tax_amount': currency_format(cart.sale.tax_amount),
                'untaxed_amount': currency_format(cart.sale.untaxed_amount),
            }
            rv['cart_total_amount'] = currency_format(
                cart.sale and cart.sale.total_amount or 0
            )

        rv['cart_size'] = '%s' % Cart.cart_size()

        return rv
