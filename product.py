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
from trytond.model import fields
from trytond.pyson import Bool, Eval
from nereid import request, cache, jsonify, abort, current_user, route
from nereid.helpers import key_from_list

__all__ = ['Product']
__metaclass__ = PoolMeta


class Product:
    "Product extension for Nereid"
    __name__ = "product.product"

    display_available_quantity = fields.Boolean(
        "Display Available Quantity On Website?"
    )

    start_displaying_qty_digits = fields.Function(
        fields.Integer('Start Quantity Digits'),
        getter='on_change_with_start_displaying_qty_digits'
    )

    start_displaying_available_quantity = fields.Numeric(
        'Start Quantity', digits=(16, Eval('start_displaying_qty_digits', 2)),
        states={
            'invisible': ~Bool(Eval('display_available_quantity')),
        }, depends=[
            'display_available_quantity', 'start_displaying_qty_digits',
        ],
        help=(
            "Product's available quantity must be less than this to show on"
            " website"
        )
    )

    min_warehouse_quantity = fields.Numeric(
        'Min Warehouse Quantity', digits=(16, 4),
        help="Minimum quantity required in warehouse for orders"
    )
    is_backorder = fields.Function(
        fields.Boolean("Is Backorder"), getter="get_is_backorder"
    )

    def get_is_backorder(self, name):
        if self.min_warehouse_quantity is None or \
                self.min_warehouse_quantity < 0:
            return True
        return False

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()

        cls._error_messages.update({
            'start_displaying_positive': (
                'This quantity should be always be positive'
            ),
        })

    @classmethod
    def validate(cls, records):
        """
        Validation method
        """
        super(Product, cls).validate(records)

        for record in records:
            record.validate_start_display_quantity()

    def validate_start_display_quantity(self):
        """
        This method validates that `start_displaying_available_quantity` is
        always positive.
        """
        if self.start_displaying_available_quantity and \
                self.start_displaying_available_quantity <= 0:
            self.raise_user_error('start_displaying_positive')

    @staticmethod
    def default_min_warehouse_quantity():
        """
        By default, min_warehouse_quantity is minus one. This is to handle the
        normal sale order workflow.
        """
        return -1

    @fields.depends('_parent_template')
    def on_change_with_start_displaying_qty_digits(self, name=None):
        """
        Getter for start_displaying_qty_digits
        """
        return self.template.default_uom.digits or 2

    def can_buy_from_eshop(self):
        """
        This function is used for inventory checking purpose. It returns a
        boolean result on the basis of fields such as min_warehouse_quantity.
        """
        quantity = self.get_availability().get('quantity')

        if self.type != 'goods':
            # If product type is not goods, then inventory need not be checked
            return True

        if self.min_warehouse_quantity < 0 or \
                self.min_warehouse_quantity is None:
            # If min_warehouse_quantity is negative (back order) or not set,
            # product is in stock
            return True
        elif quantity > self.min_warehouse_quantity:
            # If min_warehouse_quantity is less than available quantity, product
            # is in stock
            return True
        else:
            # In all other cases, product is not in stock
            return False

    def inventory_status(self):
        """
        This method returns the inventory status for the given product which can
        have the following messages -:
          * Out Of Stock
          * In Stock
          * X <UOM> left

        It returns a tuple of the form -:
          ('in_stock', 'In Stock')
        whose elements are decided by the fields min_warehouse_quantity,
        start_displaying_available_quantity and the product's current quantity.

        The first element of the tuple can be used in future to decide things
        such as color scheming in template. The second element of the tuple is
        the message to show.
        """
        if self.can_buy_from_eshop():
            status, message = 'in_stock', 'In stock'
        else:
            status, message = 'out_of_stock', 'Out of stock'

        quantity = self.get_availability().get('quantity')

        if status == 'in_stock' and self.display_available_quantity and \
                quantity <= self.start_displaying_available_quantity:
            message = '%s %s left' % (quantity, self.default_uom.name)

        return status, message

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
                'image': (self.default_image.transform_command().thumbnail(
                    150, 150, 'a'
                ).url() if self.default_image else None),
            }
        if hasattr(super(Product, self), 'serialize'):
            return super(Product, self).serialize(purpose)

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
