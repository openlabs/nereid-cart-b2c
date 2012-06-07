# -*- coding: UTF-8 -*-
'''
    nereid_cart.website

    :copyright: (c) 2010-2012 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
import warnings

from werkzeug.exceptions import NotFound
from nereid import render_template, login_required, request
from nereid.contrib.pagination import Pagination
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool


class Website(ModelSQL, ModelView):
    """
    Website
    """
    _name = 'nereid.website'

    #: Stock location to be used when calculating the stock.
    #:
    #: ..versionadded: 2.4.0.4
    stock_location = fields.Many2One(
        'stock.location', 'Stock Location', required=True,
        domain=[('type', '=', 'storage')],
        help="Stock location to be used to check availability"
    )

    def __init__(self):
        super(Website, self).__init__()
        self.per_page = 10

    def account_context(self):
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
        sale_obj = Pool().get('sale.sale')
        invoice_obj = Pool().get('account.invoice')
        shipment_obj = Pool().get('stock.shipment.out')

        sales = Pagination(sale_obj, [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft')
            ], 1, 5)

        invoices = Pagination(invoice_obj, [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft'),
            ], 1, 5)

        shipments = Pagination(shipment_obj, [
            ('customer', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft'),
            ], 1, 5)

        context = super(Website, self).account_context()
        context.update({
            'sales': sales,
            'invoices': invoices,
            'shipments': shipments,
            })
        return context

    @login_required
    def account(self):
        'Account Details'
        account_context = self.account_context()
        sales = account_context.get('sales')
        invoices = account_context.get('invoices')
        shipments = account_context.get('shipments')
        return render_template(
            'account.jinja', sales = sales,
            invoices = invoices, shipments = shipments, 
            user = request.nereid_user)

    @login_required
    def sales(self, page=1):
        'All sales'
        sale_obj = Pool().get('sale.sale')
        sales = Pagination(sale_obj, [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft')
            ], page, self.per_page)
        return render_template('sales.jinja', sales=sales)

    @login_required
    def sale(self, sale):
        'Individual Sale Order'
        warnings.warn(
            "This method call will be deprecated in future."
            "Use `sale.sale.render` instead", 
            DeprecationWarning
            )
        sale_obj = Pool().get('sale.sale')
        sales_ids = sale_obj.search(
            [
            ('party', '=', request.nereid_user.party.id),
            ('id', '=', sale), ('state', '!=', 'draft')
            ])
        if not sales_ids:
            return NotFound()
        sale = sale_obj.browse(sales_ids[0])
        return render_template('sale.jinja', sale=sale)

    @login_required
    def invoices(self, page=1):
        'List of Invoices'
        invoice_obj = Pool().get('account.invoice')
        invoices = Pagination(invoice_obj, [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft')
            ], page, self.per_page)
        return render_template('invoices.jinja', invoices=invoices)

    @login_required
    def invoice(self, invoice):
        'individual Invoice'
        invoice_obj = Pool().get('account.invoice')
        invoice_ids = invoice_obj.search(
            [
            ('party', '=', request.nereid_user.party.id),
            ('id', '=', invoice),
            ('state', '!=', 'draft')
            ])
        if not invoice_ids:
            return NotFound()
        invoice = invoice_obj.browse(invoice_ids[0])
        return render_template('invoice.jinja', invoice=invoice)

    @login_required
    def shipments(self, page=1):
        'List of Shipments'
        shipment_obj = Pool().get('stock.shipment.out')
        shipments = Pagination(shipment_obj, [
            ('customer', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft'),
            ], page, self.per_page)
        return render_template('shipments.jinja', shipments=shipments)

    @login_required
    def shipment(self, shipment):
        'Shipment'
        shipment_obj = Pool().get('stock.shipment.out')
        shipment_ids = shipment_obj.search(
            [
            ('customer', '=', request.nereid_user.party.id),
            ('id', '=', shipment),
            ('state', '!=', 'draft'),
            ])
        if not shipment_ids:
            return NotFound()
        shipment = shipment_obj.browse(shipment_ids[0])
        return render_template('shipment.jinja', shipment=shipment)

Website()
