#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''

    Test product features

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
import json
import unittest
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta

import pycountry
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from nereid.testing import NereidTestCase
from trytond.transaction import Transaction


class BaseTestCase(NereidTestCase):
    """
    Test the sale_price method of Product
    """
    def setUp(self):
        trytond.tests.test_tryton.install_module('nereid_cart_b2c')

        self.Currency = POOL.get('currency.currency')
        self.Company = POOL.get('company.company')
        self.Party = POOL.get('party.party')
        self.Sale = POOL.get('sale.sale')
        self.Cart = POOL.get('nereid.cart')
        self.Product = POOL.get('product.product')
        self.ProductTemplate = POOL.get('product.template')
        self.Language = POOL.get('ir.lang')
        self.NereidWebsite = POOL.get('nereid.website')
        self.SaleShop = POOL.get('sale.shop')
        self.Uom = POOL.get('product.uom')
        self.Country = POOL.get('country.country')
        self.Subdivision = POOL.get('country.subdivision')
        self.Currency = POOL.get('currency.currency')
        self.NereidUser = POOL.get('nereid.user')
        self.User = POOL.get('res.user')
        self.PriceList = POOL.get('product.price_list')
        self.Location = POOL.get('stock.location')
        self.Party = POOL.get('party.party')
        self.Locale = POOL.get('nereid.website.locale')
        self.Tax = POOL.get('account.tax')

        self.templates = {
            'home.jinja': '{{get_flashed_messages()}}',
            'login.jinja':
                '{{ login_form.errors }} {{get_flashed_messages()}}',
            'shopping-cart.jinja':
                'Cart:{{ cart.id }},{{get_cart_size()|round|int}},'
                '{{cart.sale.total_amount}}',
            'product.jinja':
                '{{ product.sale_price(product.id) }}',
        }

    def _create_product_template(self, name, vlist, uri, uom=u'Unit'):
        """
        Create a product template with products and return its ID

        :param name: Name of the product
        :param vlist: List of dictionaries of values to create
        :param uri: uri of product template
        :param uom: Note it is the name of UOM (not symbol or code)
        """
        ProductTemplate = POOL.get('product.template')
        Uom = POOL.get('product.uom')

        for values in vlist:
            values['name'] = name
            values['default_uom'], = Uom.search([('name', '=', uom)], limit=1)
            values['sale_uom'], = Uom.search([('name', '=', uom)], limit=1)
            values['products'] = [
                ('create', [{
                    'uri': uri,
                    'displayed_on_eshop': True
                }])
            ]
        return ProductTemplate.create(vlist)

    def _create_fiscal_year(self, date=None, company=None):
        """
        Creates a fiscal year and requried sequences
        """
        FiscalYear = POOL.get('account.fiscalyear')
        Sequence = POOL.get('ir.sequence')
        SequenceStrict = POOL.get('ir.sequence.strict')
        Company = POOL.get('company.company')

        if date is None:
            date = datetime.date.today()

        if company is None:
            company, = Company.search([], limit=1)

        invoice_sequence, = SequenceStrict.create([{
            'name': '%s' % date.year,
            'code': 'account.invoice',
            'company': company,
        }])
        fiscal_year, = FiscalYear.create([{
            'name': '%s' % date.year,
            'start_date': date + relativedelta(month=1, day=1),
            'end_date': date + relativedelta(month=12, day=31),
            'company': company,
            'post_move_sequence': Sequence.create([{
                'name': '%s' % date.year,
                'code': 'account.move',
                'company': company,
            }])[0],
            'out_invoice_sequence': invoice_sequence,
            'in_invoice_sequence': invoice_sequence,
            'out_credit_note_sequence': invoice_sequence,
            'in_credit_note_sequence': invoice_sequence,
        }])
        FiscalYear.create_period([fiscal_year])
        return fiscal_year

    def _create_coa_minimal(self, company):
        """Create a minimal chart of accounts
        """
        AccountTemplate = POOL.get('account.account.template')
        Account = POOL.get('account.account')

        account_create_chart = POOL.get(
            'account.create_chart', type="wizard")

        account_template, = AccountTemplate.search(
            [('parent', '=', None)]
        )

        session_id, _, _ = account_create_chart.create()
        create_chart = account_create_chart(session_id)
        create_chart.account.account_template = account_template
        create_chart.account.company = company
        create_chart.transition_create_account()

        receivable, = Account.search([
            ('kind', '=', 'receivable'),
            ('company', '=', company),
        ])
        payable, = Account.search([
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
        Account = POOL.get('account.account')
        Company = POOL.get('company.company')

        if company is None:
            company, = Company.search([], limit=1)

        accounts = Account.search([
            ('kind', '=', kind),
            ('company', '=', company)
        ], limit=1)
        if not accounts and not silent:
            raise Exception("Account not found")
        return accounts[0] if accounts else False

    def _create_payment_term(self):
        """Create a simple payment term with all advance
        """
        PaymentTerm = POOL.get('account.invoice.payment_term')

        return PaymentTerm.create([{
            'name': 'Direct',
            'lines': [('create', [{'type': 'remainder'}])]
        }])

    def _create_countries(self, count=5):
        """
        Create some sample countries and subdivisions
        """
        for country in list(pycountry.countries)[0:count]:
            countries = self.Country.create([{
                'name': country.name,
                'code': country.alpha2,
            }])
            try:
                divisions = pycountry.subdivisions.get(
                    country_code=country.alpha2
                )
            except KeyError:
                pass
            else:
                for subdivision in list(divisions)[0:count]:
                    self.Subdivision.create([{
                        'country': countries[0].id,
                        'name': subdivision.name,
                        'code': subdivision.code,
                        'type': subdivision.type.lower(),
                    }])

    def _create_pricelists(self):
        """
        Create the pricelists
        """
        # Setup the pricelists
        self.party_pl_margin = Decimal('1.10')
        self.guest_pl_margin = Decimal('1.20')
        user_price_list, = self.PriceList.create([{
            'name': 'PL 1',
            'company': self.company.id,
            'lines': [
                ('create', [{
                    'formula': 'unit_price * %s' % self.party_pl_margin
                }])
            ],
        }])
        guest_price_list, = self.PriceList.create([{
            'name': 'PL 2',
            'company': self.company.id,
            'lines': [
                ('create', [{
                    'formula': 'unit_price * %s' % self.guest_pl_margin
                }])
            ],
        }])
        return guest_price_list.id, user_price_list.id

    def create_website(self):
        """
        Creates a website. Since the fields required to make this could
        change depending on modules installed and this is a base test case
        the creation is separated to another method
        """
        return self.NereidWebsite.create([{
            'name': 'localhost',
            'shop': self.shop,
            'company': self.company.id,
            'application_user': USER,
            'default_locale': self.locale_en_us.id,
            'guest_user': self.guest_user,
            'countries': [('add', self.available_countries)],
            'currencies': [('add', [self.usd.id])],
        }])

    def setup_defaults(self):
        """
        Setup the defaults
        """
        with Transaction().set_context(company=None):
            self.usd, = self.Currency.create([{
                'name': 'US Dollar',
                'code': 'USD',
                'symbol': '$',
            }])
            self.party, = self.Party.create([{
                'name': 'Openlabs',
            }])
            self.company, = self.Company.create([{
                'party': self.party.id,
                'currency': self.usd
            }])

        self.User.write(
            [self.User(USER)], {
                'main_company': self.company.id,
                'company': self.company.id,
            }
        )
        CONTEXT.update(self.User.get_preferences(context_only=True))

        # Create Fiscal Year
        self._create_fiscal_year(company=self.company.id)
        # Create Chart of Accounts
        self._create_coa_minimal(company=self.company.id)
        # Create a payment term
        payment_term, = self._create_payment_term()

        shop_price_list, user_price_list = self._create_pricelists()

        party1, = self.Party.create([{
            'name': 'Guest User',
        }])

        party2, = self.Party.create([{
            'name': 'Registered User',
            'sale_price_list': user_price_list,
        }])

        party3, = self.Party.create([{
            'name': 'Registered User 2',
        }])

        # Create users and assign the pricelists to them
        self.guest_user, = self.NereidUser.create([{
            'party': party1.id,
            'display_name': 'Guest User',
            'email': 'guest@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
        }])
        self.registered_user, = self.NereidUser.create([{
            'party': party2.id,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': self.company.id,
        }])
        self.registered_user2, = self.NereidUser.create([{
            'party': party3.id,
            'display_name': 'Registered User 2',
            'email': 'email2@example.com',
            'password': 'password2',
            'company': self.company.id,
        }])

        self._create_countries()
        self.available_countries = self.Country.search([], limit=5)

        warehouse, = self.Location.search([
            ('type', '=', 'warehouse')
        ], limit=1)
        location, = self.Location.search([
            ('type', '=', 'storage')
        ], limit=1)
        en_us, = self.Language.search([('code', '=', 'en_US')])

        self.locale_en_us, = self.Locale.create([{
            'code': 'en_US',
            'language': en_us.id,
            'currency': self.usd.id,
        }])

        self.sale_tax, = self.Tax.create([{
            'name': 'Sales Tax',
            'description': 'Sales Tax',
            'type': 'percentage',
            'rate': Decimal('0.05'),  # Rate 5%
            'company': self.company.id,
            'invoice_account': self._get_account_by_kind('other').id,
            'credit_note_account': self._get_account_by_kind('other').id,
        }])

        with Transaction().set_context(company=self.company.id):
            self.shop, = self.SaleShop.create([{
                'name': 'Default Shop',
                'price_list': shop_price_list,
                'warehouse': warehouse,
                'payment_term': payment_term,
                'company': self.company.id,
                'users': [('add', [USER])]
            }])
        self.User.set_preferences({'shop': self.shop})

        self.create_website()

        # Create product templates with products
        self.template1, = self._create_product_template(
            'product-1',
            [{
                'type': 'goods',
                'salable': True,
                'list_price': Decimal('10'),
                'cost_price': Decimal('5'),
                'account_expense': self._get_account_by_kind('expense').id,
                'account_revenue': self._get_account_by_kind('revenue').id,
            }],
            uri='product-1',
        )
        self.template2, = self._create_product_template(
            'product-2',
            [{
                'type': 'goods',
                'salable': True,
                'list_price': Decimal('15'),
                'cost_price': Decimal('5'),
                'account_expense': self._get_account_by_kind('expense').id,
                'account_revenue': self._get_account_by_kind('revenue').id,
            }],
            uri='product-2',
        )
        self.product1 = self.template1.products[0]
        self.product2 = self.template2.products[0]

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
            '/login', data={
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
                rv = c.get('/product/product-1')
                self.assertEqual(
                    Decimal(rv.data), Decimal('10') * self.guest_pl_margin
                )
                rv = c.get('/product/product-2')
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
                rv = c.get('/product/product-1')
                self.assertEqual(
                    Decimal(rv.data), Decimal('10') * self.party_pl_margin
                )
                rv = c.get('/product/product-2')
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
                rv = c.get('/product/product-1')
                self.assertEqual(
                    Decimal(rv.data), Decimal('10') * self.guest_pl_margin
                )
                rv = c.get('/product/product-2')
                self.assertEqual(
                    Decimal(rv.data), Decimal('15') * self.guest_pl_margin
                )

    def test_0040_availability(self):
        """
        Test the availability returned for the products
        """
        StockMove = POOL.get('stock.move')
        Website = POOL.get('nereid.website')
        Location = POOL.get('stock.location')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                rv = c.get('/product-availability/product-1')
                availability = json.loads(rv.data)
                self.assertEqual(availability['quantity'], 0.00)
                self.assertEqual(availability['forecast_quantity'], 0.00)

            website, = Website.search([])
            supplier, = Location.search([('code', '=', 'SUP')])
            stock1, = StockMove.create([{
                'product': self.product1.id,
                'uom': self.template1.sale_uom.id,
                'quantity': 10,
                'from_location': supplier,
                'to_location': website.stock_location.id,
                'company': website.company.id,
                'unit_price': Decimal('1'),
                'currency': website.currencies[0].id,
                'planned_date': datetime.date.today(),
                'effective_date': datetime.date.today(),
                'state': 'draft',
            }])
            stock2, = StockMove.create([{
                'product': self.product1.id,
                'uom': self.template1.sale_uom.id,
                'quantity': 10,
                'from_location': supplier,
                'to_location': website.stock_location.id,
                'company': website.company.id,
                'unit_price': Decimal('1'),
                'currency': website.currencies[0].id,
                'planned_date': datetime.date.today() + relativedelta(days=1),
                'effective_date': datetime.date.today() + relativedelta(days=1),
                'state': 'draft'
            }])
            StockMove.write([stock1], {
                'state': 'done'
            })

            locations = Location.search([('type', '=', 'storage')])

            with app.test_client() as c:
                with Transaction().set_context(
                        {'locations': map(int, locations)}):
                    rv = c.get('/product-availability/product-1')
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
