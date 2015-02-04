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
from trytond.pool import PoolMeta, Pool
from nereid import request, cache, jsonify, abort, current_user, route
from nereid.helpers import key_from_list

__all__ = ['Product']
__metaclass__ = PoolMeta


class Product:
    "Product extension for Nereid"
    __name__ = "product.product"

    def serialize(self, purpose=None):
        """
        Serialize product data
        """
        if purpose == 'cart':
            return {
                'id': self.id,
                'code': self.code,
                'name': self.name,
                'category': self.category and self.category.name or None,
                'image': (
                    self.default_image.transform_command().thumbnail(
                        150, 150, 'a'
                    ).url() if self.default_image else None
                ),
            }

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
        Sale = Pool().get('sale.sale')

        price_list = Sale.default_price_list()

        if current_user.is_anonymous():
            customer = request.nereid_website.guest_user.party
        else:
            customer = current_user.party

        # Build a Cache key to store in cache
        cache_key = key_from_list([
            Transaction().cursor.dbname,
            Transaction().user,
            customer.id,
            price_list, self.id, quantity,
            request.nereid_currency.id,
            'product.product.sale_price',
        ])
        price = cache.get(cache_key)
        if price is None:
            # There is a valid pricelist, now get the price
            with Transaction().set_context(
                customer=customer.id,
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
    @route('/product-availability/<uri>')
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
        try:
            product, = cls.search([
                ('displayed_on_eshop', '=', True),
                ('uri', '=', uri),
            ])
        except ValueError:
            return abort(404)

        return jsonify(product.get_availability())
