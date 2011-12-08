#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from ast import literal_eval
from decimal import Decimal
import unittest2 as unittest

from trytond.config import CONFIG
CONFIG.options['db_type'] = 'sqlite'
from trytond.modules import register_classes
register_classes()

from nereid.testing import testing_proxy
from trytond.transaction import Transaction

class TestCart(unittest.TestCase):
    """Test Cart"""

    @classmethod
    def setUpClass(cls):
        # Install module
        testing_proxy.install_module('nereid_cart_b2c')

        uom_obj = testing_proxy.pool.get('product.uom')
        journal_obj = testing_proxy.pool.get('account.journal')
        country_obj = testing_proxy.pool.get('country.country')
        currency_obj = testing_proxy.pool.get('currency.currency')

        with Transaction().start(testing_proxy.db_name, 1, None) as txn:
            # Create company
            cls.company = testing_proxy.create_company('Test Company')
            testing_proxy.set_company_for_user(1, cls.company)
            # Create Fiscal Year
            fiscal_year = testing_proxy.create_fiscal_year(company=cls.company)
            # Create Chart of Accounts
            testing_proxy.create_coa_minimal(company=cls.company)
            # Create payment term
            testing_proxy.create_payment_term()

            cls.guest_user = testing_proxy.create_guest_user(company=cls.company)
                
            cls.regd_user = testing_proxy.create_user_party('Registered User', 
                'email@example.com', 'password', company=cls.company)

            category_template = testing_proxy.create_template(
                'category-list.jinja', ' ')
            product_template = testing_proxy.create_template(
                'product-list.jinja', ' ')
            cls.available_countries = country_obj.search([], limit=5)
            cls.available_currencies = currency_obj.search([('code', '=', 'USD')])
            cls.site = testing_proxy.create_site('testsite.com', 
                category_template = category_template,
                product_template = product_template,
                countries = [('set', cls.available_countries)],
                currencies = [('set', cls.available_currencies)])

            testing_proxy.create_template('home.jinja', ' Home ', cls.site)
            testing_proxy.create_template(
                'login.jinja', 
                '{{ login_form.errors }} {{get_flashed_messages()}}', cls.site)
            testing_proxy.create_template('shopping-cart.jinja', 
                'Cart:{{ cart.id }},{{get_cart_size()|round|int}},{{cart.sale.total_amount}}', 
                cls.site)
            product_template = testing_proxy.create_template(
                'product.jinja', ' ', cls.site)
            category_template = testing_proxy.create_template(
                'category.jinja', ' ', cls.site)

            category = testing_proxy.create_product_category(
                'Category', uri='category')
            stock_journal = journal_obj.search([('code', '=', 'STO')])[0]
            cls.product = testing_proxy.create_product(
                'product 1', category,
                type = 'stockable',
                # purchasable = True,
                salable = True,
                list_price = Decimal('10'),
                cost_price = Decimal('5'),
                account_expense = testing_proxy.get_account_by_kind('expense'),
                account_revenue = testing_proxy.get_account_by_kind('revenue'),
                uri = 'product-1',
                sale_uom = uom_obj.search([('name', '=', 'Unit')], limit=1)[0],
                #account_journal_stock_input = stock_journal,
                #account_journal_stock_output = stock_journal,
                )

            txn.cursor.commit()

    def get_app(self, **options):
        options.update({
            'SITE': 'testsite.com',
            'GUEST_USER': self.guest_user,
            'TRYTON_USER': 1,
            })
        return testing_proxy.make_app(**options)

    def setUp(self):
        self.sale_obj = testing_proxy.pool.get('sale.sale')
        self.country_obj = testing_proxy.pool.get('country.country')
        self.address_obj = testing_proxy.pool.get('party.address')

    def test_0010_cart_wo_login(self):
        """Check if cart works without login"""
        app = self.get_app()
        with app.test_client() as c:
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)

            c.post('/en_US/cart/add', data={
                'product': self.product, 'quantity': 5
                })
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)

        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            sales_ids = self.sale_obj.search([])
            self.assertEqual(len(sales_ids), 1)
            sale = self.sale_obj.browse(sales_ids[0])
            self.assertEqual(len(sale.lines), 1)
            self.assertEqual(sale.lines[0].product.id, self.product)
            
    def test_0020_cart_diff_apps(self):
        """Call the cart with two different applications 
        and assert they are not equal"""
        app = self.get_app()
        with app.test_client() as c1:
            rv1 = c1.get('/en_US/cart')
            self.assertEqual(rv1.status_code, 200)
        with app.test_client() as c2:
            rv2 = c2.get('/en_US/cart')
            self.assertEqual(rv2.status_code, 200)
        
        self.assertTrue(rv1.data != rv2.data)
        
    def test_0030_add_items_n_login(self):
        """User browses cart, adds items and logs in
        Expected behaviour :  The items in the guest cart is added to the 
        registered cart of the user upon login
        """
        app = self.get_app()
        with app.test_client() as c:
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)

            c.post('/en_US/cart/add', data={
                'product': self.product, 'quantity': 5
                })
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            cart_data1 = rv.data[6:]
            
            #Login now and access cart
            c.post('/en_US/login', data={
                'email': 'email@example.com',
                'password': 'password',
                })
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            cart_data2 = rv.data[6:]
            
            self.assertEqual(cart_data1, cart_data2)
            
    def test_0040_user_logout(self):
        """When the user logs out his guest cart will always be empty
        """
        app = self.get_app()
        with app.test_client() as c:
            c.post('/en_US/login', data={
                'email': 'email@example.com',
                'password': 'password',
                })

            c.post('/en_US/cart/add', data={
                'product': self.product, 'quantity': 7
                })
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:7,7,70.00')

            response = c.get('/en_US/logout')
            self.assertEqual(response.status_code, 302)
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:8,0,False')
            
    def test_0500_same_user_two_session(self):
        """Registered user on two different sessions should see the same cart
        """
        with Transaction().start(testing_proxy.db_name, 
                testing_proxy.user, testing_proxy.context) as txn:
            regd_user2_id = testing_proxy.create_user_party('Registered User 2', 
                'email2@example.com', 'password2', company=self.company)
            txn.cursor.commit()
            
        app = self.get_app()
        with app.test_client() as c:
            c.post('/en_US/login', data={
                'email': 'email2@example.com',
                'password': 'password2',
                })

            c.post('/en_US/cart/add', data={
                'product': self.product, 'quantity': 6
                })
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:9,6,60.00')
            
        with app.test_client() as c:
            c.post('/en_US/login', data={
                'email': 'email2@example.com',
                'password': 'password2',
                })
                
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:9,6,60.00')

def suite():
    "Cart test suite"
    suite = unittest.TestSuite()
    suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestCart)
        )
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
