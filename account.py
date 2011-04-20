# -*- coding: UTF-8 -*-
'''
    nereid_cart.account

    User Account

    :copyright: (c) 2010-2011 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''

from nereid import render_template, login_required, request
from werkzeug.exceptions import NotFound

from trytond.model import ModelSQL

class Account(ModelSQL):
    "Add elements to account context"
    _name = 'nereid.website'

    def account_context(self):
        "First get existing context and then add"
        sale_obj = self.pool.get('sale.sale')
        invoice_obj = self.pool.get('account.invoice')
        shipment_obj = self.pool.get('stock.shipment.out')

        sales_ids = sale_obj.search(
            [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft')
            ],
            limit=5)
        sales = sale_obj.browse(sales_ids)

        invoice_ids = invoice_obj.search(
            [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft'),
            ],
            limit=5)
        invoices = invoice_obj.browse(invoice_ids)

        shipment_ids = shipment_obj.search(
            [
            ('customer', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft'),
            ],
            limit=5)
        shipments = shipment_obj.browse(shipment_ids)

        context = super(Website, self).account_context()
        context.update({
            'sales': sales,
            'invoices': invoices,
            'shipments': shipments,
            })
        return context

    @login_required
    def sales(self):
        'All sales'
        sale_obj = self.pool.get('sale.sale')
        sales_ids = sale_obj.search(
            [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft')
            ])
        sales = sale_obj.browse(sales_ids)
        return render_template('sales.jinja', sales=sales)

    @login_required
    def sale(self, sale):
        'Individual Sale Order'
        sale_obj = self.pool.get('sale.sale')
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
    def invoices(self):
        'List of Invoices'
        invoice_obj = self.pool.get('account.invoice')
        invoice_ids = invoice_obj.search(
            [
            ('party', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft')
            ])
        invoices = invoice_obj.browse(invoice_ids)
        return render_template('invoices.jinja', invoices=invoices)

    @login_required
    def invoice(self, invoice):
        'individual Invoice'
        invoice_obj = self.pool.get('account.invoice')
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
    def shipments(self):
        'List of Shipments'
        shipment_obj = self.pool.get('stock.shipment.out')
        shipment_ids = shipment_obj.search(
            [
            ('customer', '=', request.nereid_user.party.id),
            ('state', '!=', 'draft'),
            ])
        shipments = shipment_obj.browse(shipment_ids)
        return render_template('shipments.jinja', shipments=shipments)

    @login_required
    def shipment(self, shipment):
        'Shipment'
        shipment_obj = self.pool.get('stock.shipment.out')
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

Account()
