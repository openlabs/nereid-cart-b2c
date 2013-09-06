# -*- coding: UTF-8 -*-
'''
    nereid_cart.product

    Product Pricelist

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
from datetime import date
from dateutil.relativedelta import relativedelta

from trytond.transaction import Transaction
from trytond.pool import PoolMeta
from nereid import request, cache, jsonify, abort
from nereid.helpers import key_from_list

__all__ = ['Product']
__metaclass__ = PoolMeta


class Product:
    "Product extension for Nereid"
    __name__ = "product.product"

    def sale_price(self, quantity=0):
        """Return the Sales Price.
        A wrapper designed to work as a context variable in templating

        The price is calculated from the pricelist associated with the current
        user. The user in the case of guest user is logged in user. In the
        event that the logged in user does not have a pricelist set against
        the user, the guest user's pricelist is chosen.

        Finally if neither the guest user, nor the regsitered user has a
        pricelist set against them then the list price is displayed as the
        list price of the product

        :param quantity: Quantity
        """
        price_list = request.nereid_user.party.sale_price_list.id if \
            request.nereid_user.party.sale_price_list else None

        # If the registered user does not have a pricelist try for
        # the pricelist of guest user
        if not request.is_guest_user and price_list is None:
            guest_user = request.nereid_website.guest_user
            price_list = guest_user.party.sale_price_list.id if \
                guest_user.party.sale_price_list else None

        # Build a Cache key to store in cache
        cache_key = key_from_list([
            Transaction().cursor.dbname,
            Transaction().user,
            request.nereid_user.party.id,
            price_list, self.id, quantity,
            request.nereid_currency.id,
            'product.product.sale_price',
        ])
        price = cache.get(cache_key)
        if price is None:
            # There is a valid pricelist, now get the price
            with Transaction().set_context(
                customer=request.nereid_user.party.id,
                price_list=price_list,
                currency=request.nereid_currency.id
            ):
                price = self.get_sale_price([self], quantity)[self.id]

            # Now convert the price to the session currency
            cache.set(cache_key, price, 60 * 5)
        return price

    def get_availability(self):
        """
        This method could be subclassed to implement your custom availability
        behavior.

        By default the forecasted quantity is a 7 day forecast. In future this
        feature may be replaced with a configuration value on the website to
        specify the number of days to forecast.

        .. warning::
            `quantity` is mandatory information which needs to be returned, no
            matter what your logic for computing that is

        :return: A dictionary with `quantity` and `forecast_quantity`
        """
        context = {
            'locations': [request.nereid_website.stock_location.id],
            'stock_date_end': date.today() + relativedelta(days=7)
        }
        with Transaction().set_context(**context):
            return {
                'quantity': self.get_quantity([self], 'quantity')[self.id],
                'forecast_quantity': self.get_quantity(
                    [self], 'forecast_quantity'
                )[self.id],
            }

    @classmethod
    def availability(cls, uri):
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

        :param uri: URI of the product for which the availability needs to
                    be found
        :return: JSON object
        """
        allowed_categories = request.nereid_website.get_categories() + [None]

        try:
            product, = cls.search([
                ('displayed_on_eshop', '=', True),
                ('uri', '=', uri),
                ('category', 'in', allowed_categories),
            ])
        except ValueError:
            return abort(404)

        return jsonify(product.get_availability())
