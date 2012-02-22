# -*- coding: UTF-8 -*-
'''
    nereid_cart.product

    Product Pricelist

    :copyright: (c) 2010-2012 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''

from trytond.model import ModelSQL, ModelView
from trytond.transaction import Transaction
from nereid import request, cache
from nereid.globals import current_app
from nereid.helpers import key_from_list


class Product(ModelSQL, ModelView):
    "Product extension for Nereid"
    _name = "product.product"

    def sale_price(self, product, quantity=0):
        """Return the Sales Price. 
        A wrapper designed to work as a context variable in templating

        The price is calculated from the pricelist associated with the current
        user. The user in the case of guest user is logged in user. In the 
        event that the logged in user does not have a pricelist set against 
        the user, the guest user's pricelist is chosen.

        Finally if neither the guest user, nor the regsitered user has a 
        pricelist set against them then the list price is displayed as the 
        price of the product

        :param product: ID of product
        :param quantity: Quantity
        """
        price_list = request.nereid_user.sale_price_list.id if \
            request.nereid_user.sale_price_list else None

        # If the registered user does not have a pricelist try for
        # the pricelist of guest user
        if not request.is_guest_user and price_list is None:
            user_obj = self.pool.get('nereid.user')
            guest_user = user_obj.browse(current_app.guest_user)
            price_list = guest_user.sale_price_list.id if \
                guest_user.sale_price_list else None

        # Build a Cache key to store in cache
        cache_key = key_from_list([
            Transaction().cursor.dbname,
            Transaction().user,
            request.nereid_user.party.id,
            price_list, product, quantity,
            request.nereid_currency.id,
            'product.product.sale_price',
            ])
        rv = cache.get(cache_key)
        if rv is None:
            # There is a valid pricelist, now get the price
            with Transaction().set_context(
                    customer = request.nereid_user.party.id, 
                    price_list = price_list,
                    currency = request.nereid_currency.id):
                rv = self.get_sale_price([product], quantity)[product]

            # Now convert the price to the session currency
            cache.set(cache_key, rv, 60 * 5)
        return rv

Product()
