#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import unittest2 as unittest

from trytond.config import CONFIG
CONFIG.options['db_type'] = 'sqlite'
from trytond.modules import register_classes
register_classes()

from nereid.testing import testing_proxy, TestCase
from trytond.transaction import Transaction


class TestProduct(TestCase):
    """
    Test the sale_price method of Product
    """
    @classmethod
    def setUpClass(cls):
        super(TestProduct, cls).setUpClass()
        # Install module
        testing_proxy.install_module('nereid_cart_b2c')

        uom_obj = testing_proxy.pool.get('product.uom')
        country_obj = testing_proxy.pool.get('country.country')
        currency_obj = testing_proxy.pool.get('currency.currency')
        user_obj = testing_proxy.pool.get('nereid.user')
        pricelist_obj = testing_proxy.pool.get('product.price_list')

        with Transaction().start(testing_proxy.db_name, 1, None) as txn:
            # Create company
            company = cls.company = testing_proxy.create_company('Test Co Inc')
            testing_proxy.set_company_for_user(1, cls.company)
            # Create Fiscal Year
            testing_proxy.create_fiscal_year(company=cls.company)
            # Create Chart of Accounts
            testing_proxy.create_coa_minimal(company=cls.company)
            # Create payment term
            testing_proxy.create_payment_term()

            cls.guest_user = testing_proxy.create_guest_user(company=company)
                
            cls.regd_user = testing_proxy.create_user_party(
                'Registered User',
                'email@example.com', 'password', company
            )
            cls.regd_user_2 = testing_proxy.create_user_party(
                'Registered User 2',
                'email2@example.com', 'password2', company
            )
            category_template = testing_proxy.create_template(
                'category-list.jinja', ' ')
            product_template = testing_proxy.create_template(
                'product-list.jinja', ' ')
            cls.available_countries = country_obj.search([], limit=5)
            cls.available_currencies = currency_obj.search(
                    [('code', '=', 'USD')]
            )
            category = testing_proxy.create_product_category(
                'Category', uri='category')
            cls.site = testing_proxy.create_site('testsite.com', 
                category_template = category_template,
                product_template = product_template,
                countries = [('set', cls.available_countries)],
                currencies = [('set', cls.available_currencies)],
                categories = [('set', [category])]
            )

            # Templates
            testing_proxy.create_template('home.jinja', ' Home ', cls.site)
            testing_proxy.create_template(
                'login.jinja', 
                '{{ login_form.errors }} {{get_flashed_messages()}}', cls.site)
            testing_proxy.create_template('shopping-cart.jinja', 
                'Cart:{{ cart.id }},{{get_cart_size()|round|int}},'
                '{{cart.sale.total_amount}}', 
                cls.site)
            product_template = testing_proxy.create_template(
                'product.jinja', 
                '{{ product.sale_price(product.id) }}', cls.site
            )
            category_template = testing_proxy.create_template(
                'category.jinja', ' ', cls.site)


            cls.product = testing_proxy.create_product(
                'product 1', category,
                type = 'stockable',
                salable = True,
                list_price = Decimal('10'),
                cost_price = Decimal('5'),
                account_expense = testing_proxy.get_account_by_kind('expense'),
                account_revenue = testing_proxy.get_account_by_kind('revenue'),
                uri = 'product-1',
                sale_uom = uom_obj.search([('name', '=', 'Unit')], limit=1)[0],
                )
            cls.product2 = testing_proxy.create_product(
                'product 2', category,
                type = 'stockable',
                salable = True,
                list_price = Decimal('15'),
                cost_price = Decimal('5'),
                account_expense = testing_proxy.get_account_by_kind('expense'),
                account_revenue = testing_proxy.get_account_by_kind('revenue'),
                uri = 'product-2',
                sale_uom = uom_obj.search([('name', '=', 'Unit')], limit=1)[0],
                )

            pl_1_margin, pl_2_margin = Decimal('1.10'), Decimal('1.20')

            cls.pricelist_1 = pricelist_obj.create({
                'name': 'PL 1',
                'company': company,
                'lines': [
                    ('create', {'formula': 'unit_price * %s' % pl_1_margin})
                ],
            })
            cls.pricelist_2 = pricelist_obj.create({
                'name': 'PL 2',
                'company': company,
                'lines': [
                    ('create', {'formula': 'unit_price * %s' % pl_2_margin})
                ],
            })

            # Write the pricelist to the party
            user_obj.write(
                cls.regd_user, {'sale_price_list': cls.pricelist_1}
            )
            cls.party_pl_margin = pl_1_margin
            user_obj.write(
                cls.guest_user, {'sale_price_list': cls.pricelist_2}
            )
            cls.guest_pl_margin = pl_2_margin


            txn.cursor.commit()

    def get_app(self, **options):
        options.update({
            'SITE': 'testsite.com',
            'GUEST_USER': self.guest_user,
            'TRYTON_USER': 1,
            })
        return testing_proxy.make_app(**options)

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
        rv = client.post('/en_US/login', data={
            'email': username,
            'password': password,
            })
        if assert_:
            self.assertEqual(rv.status_code, 302)
        return rv

    def test_0010_test_guest_price(self):
        """
        Test the pricelist lookup algorithm
        """
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
        app = self.get_app()

        with app.test_client() as c:
            self.login(c, 'email2@example.com', 'password2')
            rv = c.get('/en_US/product/product-1')
            self.assertEqual(
                Decimal(rv.data), Decimal('10') * self.guest_pl_margin
            )
            rv = c.get('/en_US/product/product-2')
            self.assertEqual(
                Decimal(rv.data), Decimal('15') *  self.guest_pl_margin
            )


def suite():
    "Cart test suite"
    suite = unittest.TestSuite()
    suite.addTests([
        unittest.TestLoader().loadTestsFromTestCase(TestProduct),
        ])
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
