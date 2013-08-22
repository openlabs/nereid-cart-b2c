#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''

    Test product features

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
import json
import unittest
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta

import pycountry
from nereid.testing import NereidTestCase
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from trytond.transaction import Transaction


class BaseTestCase(NereidTestCase):
    """
    Test the sale_price method of Product
    """
    def setUp(self):

        # Install the company module and create a company first
        # to avoid a catch 22 situation where the payable and receivable
        # accounts are required once the nereid_cart_b2c modules are
        # installed.
        trytond.tests.test_tryton.install_module('company')

        self.currency_obj = POOL.get('currency.currency')
        self.company_obj = POOL.get('company.company')

        with Transaction().start(DB_NAME, USER, CONTEXT) as txn:
            if not self.company_obj.search([]):
                self.usd = self.currency_obj.create({
                    'name': 'US Dollar',
                    'code': 'USD',
                    'symbol': '$',
                })
                self.company = self.company_obj.create({
                    'name': 'Openlabs',
                    'currency': self.usd
                })
                txn.cursor.commit()
            else:
                self.usd, = self.currency_obj.search([])
                self.company, = self.company_obj.search([])

        # Now install the cart module to be tested
        trytond.tests.test_tryton.install_module('nereid_cart_b2c')

        self.site_obj = POOL.get('nereid.website')
        self.sale_obj = POOL.get('sale.sale')
        self.cart_obj = POOL.get('nereid.cart')
        self.product_obj = POOL.get('product.product')
        self.url_map_obj = POOL.get('nereid.url_map')
        self.language_obj = POOL.get('ir.lang')
        self.nereid_website_obj = POOL.get('nereid.website')
        self.uom_obj = POOL.get('product.uom')
        self.country_obj = POOL.get('country.country')
        self.subdivision_obj = POOL.get('country.subdivision')
        self.currency_obj = POOL.get('currency.currency')
        self.nereid_user_obj = POOL.get('nereid.user')
        self.user_obj = POOL.get('res.user')
        self.pricelist_obj = POOL.get('product.price_list')
        self.location_obj = POOL.get('stock.location')

        self.templates = {
            'localhost/home.jinja': ' Home ',
            'localhost/login.jinja':
                '{{ login_form.errors }} {{get_flashed_messages()}}',
            'localhost/shopping-cart.jinja':
                'Cart:{{ cart.id }},{{get_cart_size()|round|int}},'
                '{{cart.sale.total_amount}}',
            'localhost/product.jinja':
                '{{ product.sale_price(product.id) }}',
            'localhost/category.jinja': ' ',
        }

    def _create_product_category(self, name, **values):
        """
        Creates a product category

        Name is mandatory while other value may be provided as keyword
        arguments

        :param name: Name of the product category
        """
        category_obj = POOL.get('product.category')

        values['name'] = name
        return category_obj.create(values)

    def _create_product(self, name, uom=u'Unit', **values):
        """
        Create a product and return its ID

        Additional arguments may be provided as keyword arguments

        :param name: Name of the product
        :param uom: Note it is the name of UOM (not symbol or code)
        """
        product_obj = POOL.get('product.product')
        uom_obj = POOL.get('product.uom')

        values['name'] = name
        values['default_uom'] = uom_obj.search(
            [('name', '=', uom)], limit=1
        )[0].id

        return product_obj.create(values)

    def _create_fiscal_year(self, date=None, company=None):
        """Creates a fiscal year and requried sequences
        """
        fiscal_year_obj = POOL.get('account.fiscalyear')
        sequence_obj = POOL.get('ir.sequence')
        sequence_strict_obj = POOL.get('ir.sequence.strict')
        company_obj = POOL.get('company.company')

        if date is None:
            date = datetime.date.today()

        if company is None:
            company, = company_obj.search([], limit=1)

        invoice_sequence = sequence_strict_obj.create({
            'name': '%s' % date.year,
            'code': 'account.invoice',
            'company': company,
        })
        fiscal_year = fiscal_year_obj.create({
            'name': '%s' % date.year,
            'start_date': date + relativedelta(month=1, day=1),
            'end_date': date + relativedelta(month=12, day=31),
            'company': company,
            'post_move_sequence': sequence_obj.create({
                'name': '%s' % date.year,
                'code': 'account.move',
                'company': company,
            }),
            'out_invoice_sequence': invoice_sequence,
            'in_invoice_sequence': invoice_sequence,
            'out_credit_note_sequence': invoice_sequence,
            'in_credit_note_sequence': invoice_sequence,
        })
        fiscal_year_obj.create_period([fiscal_year])
        return fiscal_year

    def _create_coa_minimal(self, company):
        """Create a minimal chart of accounts
        """
        account_template_obj = POOL.get('account.account.template')
        account_obj = POOL.get('account.account')
        account_create_chart = POOL.get(
            'account.create_chart', type="wizard")

        account_template, = account_template_obj.search(
            [('parent', '=', None)]
        )

        session_id, _, _ = account_create_chart.create()
        create_chart = account_create_chart(session_id)
        create_chart.account.account_template = account_template
        create_chart.account.company = company
        create_chart.transition_create_account()

        receivable, = account_obj.search([
            ('kind', '=', 'receivable'),
            ('company', '=', company),
        ])
        payable, = account_obj.search([
            ('kind', '=', 'payable'),
            ('company', '=', company),
        ])
        create_chart.properties.company = company
        create_chart.properties.account_receivable = receivable
        create_chart.properties.account_payable = payable
        create_chart.transition_create_properties()

    def _get_account_by_kind(self, kind, company=None, silent=True):
        """Returns an account with given spec

        :param kind: receivable/payable/expense/revenue
        :param silent: dont raise error if account is not found
        """
        account_obj = POOL.get('account.account')
        company_obj = POOL.get('company.company')

        if company is None:
            company, = company_obj.search([], limit=1)

        account_ids = account_obj.search([
            ('kind', '=', kind),
            ('company', '=', company)
        ], limit=1)
        if not account_ids and not silent:
            raise Exception("Account not found")
        return account_ids[0] if account_ids else False

    def _create_payment_term(self):
        """Create a simple payment term with all advance
        """
        payment_term_obj = POOL.get('account.invoice.payment_term')
        return payment_term_obj.create({
            'name': 'Direct',
            'lines': [('create', {'type': 'remainder'})]
        })

    def _create_countries(self, count=5):
        """
        Create some sample countries and subdivisions
        """
        for country in list(pycountry.countries)[0:count]:
            country_id = self.country_obj.create({
                'name': country.name,
                'code': country.alpha2,
            })
            try:
                divisions = pycountry.subdivisions.get(
                    country_code=country.alpha2
                )
            except KeyError:
                pass
            else:
                for subdivision in list(divisions)[0:count]:
                    self.subdivision_obj.create({
                        'country': country_id,
                        'name': subdivision.name,
                        'code': subdivision.code,
                        'type': subdivision.type.lower(),
                    })

    def _create_pricelists(self):
        """
        Create the pricelists
        """
        # Setup the pricelists
        self.party_pl_margin = Decimal('1.10')
        self.guest_pl_margin = Decimal('1.20')
        user_price_list = self.pricelist_obj.create({
            'name': 'PL 1',
            'company': self.company.id,
            'lines': [
                ('create', {
                    'formula': 'unit_price * %s' % self.party_pl_margin
                })
            ],
        })
        guest_price_list = self.pricelist_obj.create({
            'name': 'PL 2',
            'company': self.company.id,
            'lines': [
                ('create', {
                    'formula': 'unit_price * %s' % self.guest_pl_margin
                })
            ],
        })
        return guest_price_list.id, user_price_list.id

    def setup_defaults(self):
        """
        Setup the defaults
        """

        self.user_obj.write(
            [self.user_obj(USER)], {
                'main_company': self.company.id,
                'company': self.company.id,
            }
        )
        CONTEXT.update(self.user_obj.get_preferences(context_only=True))

        # Create Fiscal Year
        self._create_fiscal_year(company=self.company.id)
        # Create Chart of Accounts
        self._create_coa_minimal(company=self.company.id)
        # Create a payment term
        self._create_payment_term()

        guest_price_list, user_price_list = self._create_pricelists()

        # Create users and assign the pricelists to them
        guest_user = self.nereid_user_obj.create({
            'name': 'Guest User',
            'display_name': 'Guest User',
            'email': 'guest@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
            'sale_price_list': guest_price_list,
        })
        self.registered_user_id = self.nereid_user_obj.create({
            'name': 'Registered User',
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': self.company.id,
            'sale_price_list': user_price_list,
        })
        self.registered_user_id2 = self.nereid_user_obj.create({
            'name': 'Registered User 2',
            'display_name': 'Registered User 2',
            'email': 'email2@example.com',
            'password': 'password2',
            'company': self.company.id,
        })

        self._create_countries()
        self.available_countries = self.country_obj.search([], limit=5)

        category = self._create_product_category(
            'Category', uri='category'
        )
        warehouse, = self.location_obj.search([
            ('type', '=', 'warehouse')
        ], limit=1)
        location, = self.location_obj.search([
            ('type', '=', 'storage')
        ], limit=1)
        url_map_id, = self.url_map_obj.search([], limit=1)
        en_us, = self.language_obj.search([('code', '=', 'en_US')])
        self.nereid_website_obj.create({
            'name': 'localhost',
            'url_map': url_map_id,
            'company': self.company.id,
            'application_user': USER,
            'default_language': en_us,
            'guest_user': guest_user,
            'countries': [('set', self.available_countries)],
            'warehouse': warehouse,
            'stock_location': location,
            'categories': [('set', [category])],
            'currencies': [('set', [self.usd])],
        })

        self.product = self._create_product(
            'product 1',
            category=category.id,
            type='goods',
            salable=True,
            list_price=Decimal('10'),
            cost_price=Decimal('5'),
            account_expense=self._get_account_by_kind('expense').id,
            account_revenue=self._get_account_by_kind('revenue').id,
            uri='product-1',
            sale_uom=self.uom_obj.search(
                [('name', '=', 'Unit')], limit=1
            )[0].id,
        )
        self.product2 = self._create_product(
            'product 2',
            category=category.id,
            type='goods',
            salable=True,
            list_price=Decimal('15'),
            cost_price=Decimal('5'),
            account_expense=self._get_account_by_kind('expense').id,
            account_revenue=self._get_account_by_kind('revenue').id,
            uri='product-2',
            sale_uom=self.uom_obj.search(
                [('name', '=', 'Unit')], limit=1
            )[0].id,
        )

    def get_template_source(self, name):
        """
        Return templates
        """
        return self.templates.get(name)

    def login(self, client, username, password, assert_=True):
        """
        Tries to login.

        .. note::
            This method MUST be called within a context

        :param client: Instance of the test client
        :param username: The username, usually email
        :param password: The password to login
        :param assert_: Boolean value to indicate if the login has to be
                        ensured. If the login failed an assertion error would
                        be raised
        """
        rv = client.post(
            '/en_US/login', data={
                'email': username,
                'password': password,
            }
        )
        if assert_:
            self.assertEqual(rv.status_code, 302)
        return rv


class TestProduct(BaseTestCase):
    "Test Product"

    def test_0010_test_guest_price(self):
        """
        Test the pricelist lookup algorithm
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                rv = c.get('/en_US/product/product-1')
                self.assertEqual(
                    Decimal(rv.data), Decimal('10') * self.guest_pl_margin
                )
                rv = c.get('/en_US/product/product-2')
                self.assertEqual(
                    Decimal(rv.data), Decimal('15') * self.guest_pl_margin
                )

    def test_0020_test_partner_price(self):
        """
        Test the pricelist lookup algorithm when a price is defined on party
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                # Use the partner
                self.login(c, 'email@example.com', 'password')
                rv = c.get('/en_US/product/product-1')
                self.assertEqual(
                    Decimal(rv.data), Decimal('10') * self.party_pl_margin
                )
                rv = c.get('/en_US/product/product-2')
                self.assertEqual(
                    Decimal(rv.data), Decimal('15') * self.party_pl_margin
                )

    def test_0030_test_guest_price_fallback(self):
        """
        Test the pricelist lookup algorithm if it falls back to guest pricing
        if a price is NOT specified for a partner.
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                self.login(c, 'email2@example.com', 'password2')
                rv = c.get('/en_US/product/product-1')
                self.assertEqual(
                    Decimal(rv.data), Decimal('10') * self.guest_pl_margin
                )
                rv = c.get('/en_US/product/product-2')
                self.assertEqual(
                    Decimal(rv.data), Decimal('15') * self.guest_pl_margin
                )

    def test_0040_availability(self):
        """
        Test the availability returned for the products
        """
        stock_move_obj = POOL.get('stock.move')
        website_obj = POOL.get('nereid.website')
        location_obj = POOL.get('stock.location')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                rv = c.get('/en_US/product-availability/product-1')
                availability = json.loads(rv.data)
                self.assertEqual(availability['quantity'], 0.00)
                self.assertEqual(availability['forecast_quantity'], 0.00)

            website, = website_obj.search([])
            supplier_id, = location_obj.search([('code', '=', 'SUP')])
            stock_move_obj.create({
                'product': self.product.id,
                'uom': self.product.sale_uom.id,
                'quantity': 10,
                'from_location': supplier_id,
                'to_location': website.stock_location.id,
                'company': website.company.id,
                'unit_price': Decimal('1'),
                'currency': website.currencies[0].id,
                'state': 'done'
            })
            stock_move_obj.create({
                'product': self.product.id,
                'uom': self.product.sale_uom.id,
                'quantity': 10,
                'from_location': supplier_id,
                'to_location': website.stock_location.id,
                'company': website.company.id,
                'unit_price': Decimal('1'),
                'currency': website.currencies[0].id,
                'planned_date': datetime.date.today() + relativedelta(days=1),
                'state': 'draft'
            })

            with app.test_client() as c:
                rv = c.get('/en_US/product-availability/product-1')
                availability = json.loads(rv.data)
                self.assertEqual(availability['forecast_quantity'], 20.00)
                self.assertEqual(availability['quantity'], 10.00)


def suite():
    "Cart test suite"
    suite = unittest.TestSuite()
    suite.addTests([
        unittest.TestLoader().loadTestsFromTestCase(TestProduct),
    ])
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
