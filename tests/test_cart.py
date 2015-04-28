#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''

    Cart test Case

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
import unittest
from decimal import Decimal

from nereid import request
from nereid.globals import session
from trytond.tests.test_tryton import USER, DB_NAME, CONTEXT, POOL
from trytond.transaction import Transaction

from test_product import BaseTestCase


class TestCart(BaseTestCase):
    """Test Cart"""

    def _create_pricelists(self):
        """
        Create the pricelists
        """
        # Setup the pricelists
        self.party_pl_margin = Decimal('1')
        self.guest_pl_margin = Decimal('1')
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

    def setup_defaults(self):
        super(TestCart, self).setup_defaults()
        self.ProductTemplate.write(
            [self.template2], {
                'list_price': Decimal('10')
            }
        )

    def test_0010_cart_wo_login(self):
        """
        Check if cart works without login

         * Add 5 units of item to cart
         * Check that the number of orders in system is 1
         * Check if the lines is 1 for that order
        """
        quantity = 5

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)

                c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id,
                        'quantity': quantity,
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)

            sales = self.Sale.search([])
            self.assertEqual(len(sales), 1)
            sale = sales[0]
            self.assertEqual(len(sale.lines), 1)
            self.assertEqual(
                sale.lines[0].product, self.product1
            )
            self.assertEqual(sale.lines[0].quantity, quantity)

    def test_0020_cart_diff_apps(self):
        """
        Call the cart with two different applications
        and assert they are different but same empty carts
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c1:
                rv1 = c1.get('/cart')
                self.assertEqual(rv1.status_code, 200)
                data1 = rv1.data

            with app.test_client() as c2:
                rv2 = c2.get('/cart')
                self.assertEqual(rv2.status_code, 200)
                data2 = rv2.data

            # Both are empty active records
            self.assertTrue(data1 == data2 == 'Cart:None,0,')

    def test_0025_cart_diff_apps(self):
        """
        Call the cart with two different applications
        and assert they are not equal. They become different
        only when
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c1:
                c1.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id, 'quantity': 5
                    }
                )
                rv1 = c1.get('/cart')
                self.assertEqual(rv1.status_code, 200)
                data1 = rv1.data

            with app.test_client() as c2:
                c2.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id, 'quantity': 5
                    }
                )
                rv2 = c2.get('/cart')
                self.assertEqual(rv2.status_code, 200)
                data2 = rv2.data

            self.assertTrue(data1 != data2)

    def test_0030_add_items_n_login(self):
        """User browses cart, adds items and logs in
        Expected behaviour :  The items in the guest cart is added to the
        registered cart of the user upon login
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)

                c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id, 'quantity': 5
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                cart_data1 = rv.data[6:]

                # Login now and access cart
                self.login(c, 'email@example.com', 'password')
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                cart_data2 = rv.data[6:]

                self.assertEqual(cart_data1, cart_data2)

    def test_0035_add_to_cart(self):
        """
        Test the add and set modes of add_to_cart
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                self.login(c, 'email@example.com', 'password')

                c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id, 'quantity': 7
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,7,70.00')

                c.post('/cart/add', data={
                    'product': self.product1.id, 'quantity': 7
                })
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,7,70.00')

                c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id,
                        'quantity': 7, 'action': 'add'
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,14,140.00')

    def test_0040_user_logout(self):
        """
        When the user logs out his guest cart will always be empty

        * Login
        * Add a product to cart
        * Logout
        * Check the cart, should have 0 quantity and different cart id
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                self.login(c, 'email@example.com', 'password')

                c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id, 'quantity': 7
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,7,70.00')

                response = c.get('/logout')
                self.assertEqual(response.status_code, 302)
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:None,0,')

    def test_0050_same_user_two_session(self):
        """
        Registered user on two different sessions should see the same cart
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                self.login(c, 'email2@example.com', 'password2')

                rv = c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id,
                        'quantity': 6
                    }
                )
                self.assertEqual(rv.status_code, 302)
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,6,60.00')

            with app.test_client() as c:
                self.login(c, 'email2@example.com', 'password2')
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,6,60.00')

    def test_0060_delete_line(self):
        """
        Try deleting a line from the cart
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                self.login(c, 'email2@example.com', 'password2')

                # Add 6 of first product
                rv = c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id,
                        'quantity': 6
                    }
                )
                self.assertEqual(rv.status_code, 302)

                # Add 10 of next product
                rv = c.post(
                    '/cart/add',
                    data={
                        'product': self.template2.products[0].id,
                        'quantity': 10
                    }
                )
                self.assertEqual(rv.status_code, 302)

                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,16,160.00')

                # Find the line with product1 and delete it
                cart = self.Cart(1)
                for line in cart.sale.lines:
                    if line.product.id == self.product1.id:
                        break
                else:
                    self.fail("Order line not found")

            with app.test_client() as c:
                self.login(c, 'email2@example.com', 'password2')
                c.post('/cart/delete/%d' % line.id)
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,10,100.00')

                # Test that ValueError is not raised if someone tries to delete
                # already removed item
                c.post('/cart/delete/%d' % line.id)
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,10,100.00')

    def test_0070_clear_cart(self):
        """
        Clear the cart completely
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                self.login(c, 'email2@example.com', 'password2')

                # Add 6 of first product
                rv = c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id,
                        'quantity': 6
                    }
                )
                self.assertEqual(rv.status_code, 302)

            cart = self.Cart(1)
            sale = cart.sale.id

            with app.test_client() as c:
                self.login(c, 'email2@example.com', 'password2')
                c.post('/cart/clear')
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:None,0,')

            self.assertFalse(self.Sale.search([('id', '=', sale)]))

    def test_0080_reject_negative_quantity(self):
        """
        If a negative quantity is sent to add to cart, then reject it
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                self.login(c, 'email2@example.com', 'password2')
                rv = c.post(
                    '/cart/add',
                    data={
                        'product': self.template2.products[0].id,
                        'quantity': 10
                    }
                )
                self.assertEqual(rv.status_code, 302)
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,10,100.00')

                #: Add a negative quantity and nothing should change
                rv = c.post(
                    '/cart/add',
                    data={
                        'product': self.template2.products[0].id,
                        'quantity': -10
                    }
                )
                self.assertEqual(rv.status_code, 302)
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,10,100.00')

    def test_0090_create_sale_order(self):
        """
        Create a sale order and it should work
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            sale, = self.Sale.create([{
                'party': self.registered_user.party.id,
                'company': self.company.id,
                'currency': self.usd.id,
            }])
            self.assertEqual(sale.party, self.registered_user.party)

    def test_0100_create_draft_sale(self):
        """
        Create draft sale method
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            Cart = POOL.get('nereid.cart')

            with app.test_request_context('/'):
                # Guest cart
                cart, = Cart.create([{
                    'user': None,
                    'sessionid': session.sid,
                }])
                cart.create_draft_sale()

                self.assertEqual(
                    cart.sale.party, request.nereid_website.guest_user.party
                )
                self.assertEqual(
                    cart.sale.nereid_user, request.nereid_website.guest_user
                )

    def test_0110_cart_cache_header(self):
        """
        Ensure that the cart page has a no cache header
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.headers['Cache-Control'], 'max-age=0')

    def test_0120_add_non_salable_product_to_cart(self):
        """
        Try to add a non-salable product to cart.
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            # Make product1 non-salable
            self.assertTrue(self.product1.template.salable)
            self.template1.salable = False
            self.template1.save()

            with app.test_client() as c:
                self.login(c, 'email@example.com', 'password')

                # You are adding a non salable product to cart
                rv = c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id, 'quantity': 7
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,0,0')

                rv = c.get('/')
                self.assert_('This product is not for sale' in rv.data)

    def test_0130_cart_sale_taxes(self):
        """
        Test taxes and sale.refresh_taxes
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()
            self.template1.customer_taxes = [self.sale_tax.id]
            self.template1.save()

            with app.test_client() as c:
                self.login(c, 'email@example.com', 'password')

                c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id, 'quantity': 7
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                # 70 (10 x 7) + 3.5 (5% Tax) = 73.50
                self.assertEqual(rv.data, 'Cart:1,7,73.50')

                c.post('/cart/add', data={
                    'product': self.product1.id, 'quantity': 7
                })
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                # 70 (10 x 7) + 3.5 (5% Tax) = 73.50
                self.assertEqual(rv.data, 'Cart:1,7,73.50')

                sale, = self.Sale.search([])
                sale.refresh_taxes()  # Refresh Taxes
                self.assertEqual(sale.tax_amount, Decimal('3.50'))

    def test_0140_price_change_on_quantity(self):
        """
        Test the add and set modes of add_to_cart
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            price_list, = self.PriceList.create([{
                'name': 'Crazy Pricelist',
                'company': self.company.id,
                'lines': [
                    ('create', [{
                        'product': self.product1.id,
                        'quantity': 2,
                        'formula': 'unit_price - 1',
                    }])
                ],
            }])
            self.assertTrue(price_list)

            app = self.get_app()

            with app.test_client() as c:
                self.login(c, 'email@example.com', 'password')

                c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id, 'quantity': 1
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                self.assertEqual(rv.data, 'Cart:1,1,10.00')

                sale = self.Sale.search([])
                self.assertEqual(len(sale), 1)
                sale[0].price_list = price_list
                sale[0].save()

                self.templates.update({
                    'shopping-cart.jinja':
                        'Cart:{{ cart.id }},{{get_cart_size()|round|int}},'
                        '{{cart.sale.total_amount}},{{get_flashed_messages()}}',
                })
                c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id,
                        'quantity': 1, 'action': 'add'
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                # Cart total must be 18 and not 20 due to price list
                self.assertTrue('Cart:1,2,18.00' in rv.data)
                self.assertTrue('dropped from' in rv.data)

                # Set quantity back to 1
                c.post(
                    '/cart/add',
                    data={
                        'product': self.product1.id,
                        'quantity': 1, 'action': 'set'
                    }
                )
                rv = c.get('/cart')
                self.assertEqual(rv.status_code, 200)
                # Cart total must be 18 and not 20 due to price list
                self.assertTrue('Cart:1,1,10.00' in rv.data)
                self.assertTrue('increased from' in rv.data)


def suite():
    "Cart test suite"
    suite = unittest.TestSuite()
    suite.addTests([
        unittest.TestLoader().loadTestsFromTestCase(TestCart),
    ])
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
