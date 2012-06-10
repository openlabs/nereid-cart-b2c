#!/usr/bin/env python
#This file is part of Tryton and Nereid.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
import unittest2 as unittest

from trytond.config import CONFIG
CONFIG.options['db_type'] = 'sqlite'
from trytond.modules import register_classes
register_classes()

from nereid.testing import testing_proxy, TestCase
from trytond.transaction import Transaction
from trytond.pool import Pool


class TestCart(TestCase):
    """Test Cart"""

    @classmethod
    def setUpClass(cls):
        super(TestCase, cls).setUpClass()
        # Install module
        testing_proxy.install_module('nereid_cart_b2c')

        with Transaction().start(testing_proxy.db_name, 1, None) as txn:
            uom_obj = Pool().get('product.uom')
            country_obj = Pool().get('country.country')
            currency_obj = Pool().get('currency.currency')
            location_obj = Pool().get('stock.location')

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

            testing_proxy.create_template('category-list.jinja', ' ')
            testing_proxy.create_template('product-list.jinja', ' ')
            cls.available_countries = country_obj.search([], limit=5)
            cls.available_currencies = currency_obj.search(
                    [('code', '=', 'USD')]
            )
            location, = location_obj.search([
                ('type', '=', 'storage')
            ], limit=1)
            cls.site = testing_proxy.create_site(
                'localhost',
                countries = [('set', cls.available_countries)],
                currencies = [('set', cls.available_currencies)],
                application_user = 1,
                guest_user = cls.guest_user,
                stock_location = location,
            )

            # Templates
            testing_proxy.create_template('home.jinja', ' Home ', cls.site)
            testing_proxy.create_template(
                'login.jinja',
                '{{ login_form.errors }} {{get_flashed_messages()}}', cls.site)
            testing_proxy.create_template(
                'shopping-cart.jinja',
                'Cart:{{ cart.id }},{{get_cart_size()|round|int}},'
                '{{cart.sale.total_amount}}',
                cls.site)
            product_template = testing_proxy.create_template(
                'product.jinja', ' ', cls.site)
            category_template = testing_proxy.create_template(
                'category.jinja', ' ', cls.site)

            category = testing_proxy.create_product_category(
                'Category', uri='category')
            cls.product = testing_proxy.create_product(
                'product 1', category,
                type = 'goods',
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
                type = 'goods',
                salable = True,
                list_price = Decimal('10'),
                cost_price = Decimal('5'),
                account_expense = testing_proxy.get_account_by_kind('expense'),
                account_revenue = testing_proxy.get_account_by_kind('revenue'),
                uri = 'product-2',
                sale_uom = uom_obj.search([('name', '=', 'Unit')], limit=1)[0],
                )
            txn.cursor.commit()

    def get_app(self, **options):
        options.update({
            'SITE': 'localhost',
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

    def setUp(self):
        self.cart_obj = testing_proxy.pool.get('nereid.cart')
        self.sale_obj = testing_proxy.pool.get('sale.sale')
        self.country_obj = testing_proxy.pool.get('country.country')
        self.address_obj = testing_proxy.pool.get('party.address')

    def test_0010_cart_wo_login(self):
        """
        Check if cart works without login

         * Add 5 units of item to cart
         * Check that the number of orders in system is 1
         * Check if the lines is 1 for that order
        """
        quantity = 5
        app = self.get_app()
        with app.test_client() as c:
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)

            c.post('/en_US/cart/add', data={
                'product': self.product, 'quantity': quantity
                })
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)

        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            sales_ids = self.sale_obj.search([])
            self.assertEqual(len(sales_ids), 1)
            sale = self.sale_obj.browse(sales_ids[0])
            self.assertEqual(len(sale.lines), 1)
            self.assertEqual(sale.lines[0].product.id, self.product)
            self.assertEqual(sale.lines[0].quantity, quantity)
            
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
            self.login(c, 'email@example.com', 'password')
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            cart_data2 = rv.data[6:]
            
            self.assertEqual(cart_data1, cart_data2)
    
    def test_0035_add_to_cart(self):
        """
        Test the add and set modes of add_to_cart
        """
        app = self.get_app()
        with app.test_client() as c:
            self.login(c, 'email@example.com', 'password')

            c.post('/en_US/cart/add', data={
                'product': self.product, 'quantity': 7
                })
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:7,7,70.00')

            c.post('/en_US/cart/add', data={
                'product': self.product, 'quantity': 7
                })
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:7,7,70.00')

            c.post('/en_US/cart/add', data={
                'product': self.product, 'quantity': 7, 'action': 'add'
                })
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:7,14,140.00')


    def test_0040_user_logout(self):
        """
        When the user logs out his guest cart will always be empty

        * Login
        * Add a product to cart
        * Logout
        * Check the cart, should have 0 quantity and different cart id
        """
        app = self.get_app()
        with app.test_client() as c:
            self.login(c, 'email@example.com', 'password')

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
            self.assertEqual(rv.data, 'Cart:8,0,None')
            
    def test_0050_same_user_two_session(self):
        """
        Registered user on two different sessions should see the same cart
        """
        with Transaction().start(testing_proxy.db_name, 
                testing_proxy.user, testing_proxy.context) as txn:
            testing_proxy.create_user_party(
                'Registered User 2', 'email2@example.com', 'password2',
                self.company
            )
            txn.cursor.commit()
            
        app = self.get_app()
        with app.test_client() as c:
            self.login(c, 'email2@example.com', 'password2')

            rv = c.post('/en_US/cart/add', data={
                'product': self.product, 'quantity': 6
                })
            self.assertEqual(rv.status_code, 302)
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:9,6,60.00')
            
        with app.test_client() as c:
            self.login(c, 'email2@example.com', 'password2')
                
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:9,6,60.00')

    def test_0060_delete_line(self):
        """
        Try deleting a line from the cart
        """
        app = self.get_app()
        with app.test_client() as c:
            self.login(c, 'email2@example.com', 'password2')

            rv = c.post('/en_US/cart/add', data={
                'product': self.product2, 'quantity': 10
                })
            self.assertEqual(rv.status_code, 302)
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:9,16,160.00')

        # Find the line with product1 and delete it
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            cart = self.cart_obj.browse(9)
            for line in cart.sale.lines:
                if line.product.id == self.product:
                    break
            else:
                self.fail("Order line not found")

        with app.test_client() as c:
            self.login(c, 'email2@example.com', 'password2')
            c.get('/en_US/cart/delete/%d' % line.id)
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:9,10,100.00')

    def test_0070_clear_cart(self):
        """
        Clear the cart completely
        """
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            cart = self.cart_obj.browse(9)
            sale = cart.sale.id

        app = self.get_app()
        with app.test_client() as c:
            self.login(c, 'email2@example.com', 'password2')
            c.get('/en_US/cart/clear')
            rv = c.get('/en_US/cart')
            self.assertEqual(rv.status_code, 200)
            self.assertEqual(rv.data, 'Cart:10,0,None')

        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            self.assertFalse(self.sale_obj.search([('id', '=', sale)]))
        

def suite():
    "Cart test suite"
    suite = unittest.TestSuite()
    suite.addTests([
        unittest.TestLoader().loadTestsFromTestCase(TestCart),
        ])
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
