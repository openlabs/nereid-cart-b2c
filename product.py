# -*- coding: UTF-8 -*-
'''
    nereid_cart.product

    Product Pricelist

    :copyright: (c) 2010-2012 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
from datetime import date
from dateutil.relativedelta import relativedelta

from trytond.model import ModelSQL, ModelView
from trytond.transaction import Transaction
from trytond.pool import Pool
from nereid import request, cache, jsonify, abort
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
            user_obj = Pool().get('nereid.user')
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

    def get_availability(self, product):
        """
        This method could be subclassed to implement your custom availability
        behavior.

        By default the forecasted quantity is a 7 day forecast. In future this
        feature may be replaced with a configuration value on the website to
        specify the number of days to forecast.

        .. warning::
            `quantity` is mandatory information which needs to be returned, no
            matter what your logic for computing that is

        :param product: ID of the product
        :return: A dictionary with `quantity` and `forecast_quantity`
        """
        context = {
            'locations': [request.nereid_website.stock_location.id],
            'stock_date_end': date.today() + relativedelta(days=7)
        }
        with Transaction().set_context(**context):
            return {
                'quantity': self.get_quantity(
                    [product], 'quantity')[product],
                'forecast_quantity': self.get_quantity(
                    [product], 'forecast_quantity')[product],
            }

    def availability(self, uri):
        """
        Returns the following information for a product:

        +-------------------+-----------------------------------------------+
        | quantity          | Available readily to buy                      |
        +-------------------+-----------------------------------------------+
        | forecast_quantity | Forecasted quantity, if the site needs it     |
        +-------------------+-----------------------------------------------+

        .. note::
            To modify the availability, or to send any additional information,
            it is recommended to subclass the :py:meth:`~get_availability` and
            implement your custom logic. For example, you might want to check
            stock with your vendor for back orders or send a message like
            `Only 5 pieces left`

        :param product: ID of the product
        :return: JSON object
        """
        allowed_categories = request.nereid_website.get_categories() + [None]
        product_ids = self.search([
            ('displayed_on_eshop', '=', True),
            ('uri', '=', uri),
            ('category', 'in', allowed_categories),
            ]
        )
        if not product_ids:
            return abort(404)

        # Location of stock for the website
        location = request.nereid_website.stock_location.id
        return jsonify(self.get_availability(product_ids[0]))

Product()
