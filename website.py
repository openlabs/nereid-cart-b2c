# -*- coding: UTF-8 -*-
'''
    nereid_cart.website

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
from functools import partial

from babel import numbers
from nereid import render_template, login_required, request
from nereid.contrib.pagination import Pagination
from nereid.globals import session
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


__all__ = ['Website']
__metaclass__ = PoolMeta


class Website:
    """
    Website
    """
    __name__ = 'nereid.website'

    #: The warehouse to be used in the sale order when an order on this site is
    #: created
    warehouse = fields.Many2One(
        'stock.location', 'Warehouse',
        domain=[('type', '=', 'warehouse')], required=True
    )

    #: Stock location to be used when calculating the stock.
    stock_location = fields.Many2One(
        'stock.location', 'Stock Location', required=True,
        depends=['warehouse'],
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', Eval('warehouse'))
        ], help="Stock location to be used to check availability"
    )

    @classmethod
    def __setup__(cls):
        super(Website, cls).__setup__()
        cls.per_page = 10

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
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft')
        ], 1, 5)

        invoices = Pagination(Invoice, [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft'),
        ], 1, 5)

        shipments = Pagination(Shipment, [
            ('customer', '=', request.nereid_user.party.id),
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
    def account(cls):
        'Account Details'
        account_context = cls.account_context()
        sales = account_context.get('sales')
        invoices = account_context.get('invoices')
        shipments = account_context.get('shipments')
        return render_template(
            'account.jinja', sales=sales,
            invoices=invoices, shipments=shipments,
            user=request.nereid_user
        )

    @classmethod
    @login_required
    def sales(cls, page=1):
        'All sales'
        Sale = Pool().get('sale.sale')
        sales = Pagination(Sale, [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft')
        ], page, cls.per_page)
        return render_template('sales.jinja', sales=sales)

    @classmethod
    @login_required
    def invoices(cls, page=1):
        'List of Invoices'
        Invoice = Pool().get('account.invoice')
        invoices = Pagination(Invoice, [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft')
        ], page, cls.per_page)
        return render_template('invoices.jinja', invoices=invoices)

    @classmethod
    @login_required
    def shipments(cls, page=1):
        'List of Shipments'
        Shipment = Pool().get('stock.shipment.out')
        shipments = Pagination(Shipment, [
            ('customer', '=', request.nereid_user.party.id),
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
            number_format = partial(
                numbers.format_number, locale=request.nereid_language.code
            )

            rv['cart'] = {
                'lines': [{
                    'product': line.product.name,
                    'quantity': number_format(line.quantity),
                    'unit': line.unit.symbol,
                    'unit_price': currency_format(line.unit_price),
                    'amount': currency_format(line.amount),
                } for line in cart.sale.lines],
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
