# -*- coding: UTF-8 -*-
'''
    nereid_cart.cart

    Cart

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
from decimal import Decimal
from functools import partial
import warnings

from nereid import jsonify, render_template, flash, request, login_required, \
    url_for
from nereid.globals import session, current_app
from nereid.signals import login
from werkzeug import redirect
from babel import numbers


from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta

from .forms import AddtoCartForm
from .i18n import _

__all__ = ['Cart']
__metaclass__ = PoolMeta

# pylint: disable-msg=E1101


class Cart(ModelSQL):
    """
    Shopping Cart plays the link between a customer's shopping experience
    and the creation of a Sale Order in the backend.

    A Draft Sale Order is maintained through out the process of the existance
    of a cart which is finally converted into a confirmed sale order once
    the process is complete.
    """
    __name__ = 'nereid.cart'
    _rec_name = 'sessionid'

    user = fields.Many2One('nereid.user', 'Cart owner', select=True)
    sale = fields.Many2One('sale.sale', 'Sale Order', select=True)
    sessionid = fields.Char('Session ID', select=True)
    website = fields.Many2One('nereid.website', 'Website', select=True)

    @classmethod
    def cart_size(cls):
        "Returns the sum of quantities in the cart"
        cart = cls.open_cart()
        return sum([line.quantity for line in cart.sale.lines]) \
            if cart.sale else Decimal('0')

    @classmethod
    @login_required
    def _get_addresses(cls):
        'Returns a list of tuple of addresses'
        party = request.nereid_user.party
        return [
            (address.id, address.full_address) for address in party.addresses
        ]

    @classmethod
    def view_cart(cls):
        """Returns a view of the shopping cart

        This method only handles GET. Unlike previous versions
        the checkout method has been moved to nereid.checkout.x

        For XHTTP/Ajax Requests a JSON object with order and lines information
        which should be sufficient to show order information is returned.
        """
        cart = cls.open_cart()

        if request.is_xhr:
            if not cart.sale:
                # Dont try to build further if the cart is empty
                return jsonify({'empty': True})

            # Build locale formatters
            currency_format = partial(
                numbers.format_currency, currency=cart.sale.currency.code,
                locale=request.nereid_language.code
            )
            number_format = partial(
                numbers.format_number, locale=request.nereid_language.code
            )
            return jsonify(cart={
                'lines': [{
                    'product': l.product.name,
                    'quantity': number_format(l.quantity),
                    'unit': l.unit.symbol,
                    'unit_price': currency_format(l.unit_price),
                    'amount': currency_format(l.amount),
                } for l in cart.sale.lines],
                'empty': len(cart.sale.lines) > 0,
                'total_amount': currency_format(cart.sale.total_amount),
                'tax_amount': currency_format(cart.sale.tax_amount),
                'untaxed_amount': currency_format(cart.sale.untaxed_amount),
            })

        return current_app.response_class(
            render_template('shopping-cart.jinja', cart=cart),
            headers=[('Cache-Control', 'max-age=0')]
        )

    @classmethod
    def view_cart_esi(cls):
        """Returns a view of the shopping cart

        Similar to :meth:view_cart but for ESI
        """
        cart = cls.open_cart()
        return current_app.response_class(
            render_template('shopping-cart-esi.jinja', cart=cart),
            headers=[('Cache-Control', 'max-age=0')]
        )

    def _clear_cart(self):
        """
        Clear the shopping cart by deleting both the sale associated
        with it and the cart itself.
        """
        Sale = Pool().get('sale.sale')

        if self.sale:
            Sale.cancel([self.sale])
            Sale.delete([self.sale])
        self.__class__.delete([self])

    @classmethod
    def clear_cart(cls):
        """
        Clears the current cart and redirects to shopping cart page
        """
        cart = cls.open_cart()
        cart._clear_cart()
        flash(_('Your shopping cart has been cleared'))
        return redirect(url_for('nereid.cart.view_cart'))

    @classmethod
    def open_cart(cls, create_order=False):
        """Logic of this cart functionality is inspired by amazon. Most
        e-commerce systems handle cart in a different way and it is important
        to know how the cart behaves under different circumstances.

        :param create_order: If `True` Create a sale order and attach
            if one does not already exist.
        :return: The Active record for the shopping cart of the user

        The method is guaranteed to return a cart but the cart may not have
        a sale order. For methods like add to cart which definitely need a sale
        order pass :attr: create_order = True so that an order is also assured.
        """
        Sale = Pool().get('sale.sale')
        NereidUser = Pool().get('nereid.user')

        # request.nereid_user is not used here this method is used by the
        # signal handlers immediately after a user logs in (but before being
        # redirected). This causes the cached property of nereid_user to remain
        # in old value through out the request, which will not  have ended when
        # this method is called.
        user = NereidUser(
            session.get('user', request.nereid_website.guest_user.id)
        )

        # for a registered user there is only one cart, session is immaterial
        if 'user' in session:
            carts = cls.search([
                ('sessionid', '=', None),
                ('user', '=', user.id),
                ('website', '=', request.nereid_website.id)
            ])
        else:
            carts = cls.search([
                ('sessionid', '=', session.sid),
                ('user', '=', user.id),
                ('website', '=', request.nereid_website.id)
            ], limit=1)

        if not carts:
            # Create a cart since it definitely does not exists
            carts = cls.create([{
                'user': user.id,
                'website': request.nereid_website.id,
                'sessionid': session.sid if 'user' not in session else None,
            }])

        cart, = carts

        if cart.sale:
            cart.sanitise_state(user)

        # Check if the order needs to be created
        if create_order and not cart.sale:
            # Try any abandoned carts that may exist if user is registered
            sale_orders = Sale.search([
                ('state', '=', 'draft'),
                ('is_cart', '=', True),
                ('website', '=', request.nereid_website.id),
                ('party', '=', user.party.id),
                ('currency', '=', request.nereid_currency.id)
            ], limit=1) if 'user' in session else None
            cls.write(
                [cart], {
                    'sale': sale_orders[0].id if sale_orders
                            else cls.create_draft_sale(user).id
                }
            )

        return cls(cart.id)

    def sanitise_state(self, user):
        """This method verifies that the sale order in the cart is a valid one
        1. for example must not be in any other state than draft
        2. must be of the current currency
        3. must be owned by the given user

        :param user: Active record of the user
        """
        if self.sale:
            if self.sale.state != 'draft' or \
                    self.sale.currency != request.nereid_currency or \
                    self.sale.party != user.party:
                self.write([self], {'sale': None})

    def check_update_date(self):
        """Check if the sale_date is same as today
        If not then update the sale_date with today's date
        """
        Date = Pool().get('ir.date')
        Sale = Pool().get('sale.sale')

        if self.sale and self.sale.sale_date \
                and self.sale.sale_date < Date.today():
            Sale.write([self.sale], {'sale_date': Date.today()})

    @classmethod
    def create_draft_sale(cls, user):
        """A helper for the cart which creates a draft order for the given
        user.

        :param user: ActiveRecord of the user
        """
        Sale = Pool().get('sale.sale')

        site = request.nereid_website
        guest_user = request.nereid_website.guest_user

        # Get the pricelist of active user, may be regd or guest
        price_list = user.party.sale_price_list.id \
            if user.party.sale_price_list else None

        # If the regsitered user does not have a pricelist try for
        # the pricelist of guest user
        if (guest_user != user) and price_list is None:
            price_list = guest_user.party.sale_price_list.id \
                if guest_user.party.sale_price_list else None

        # TODO: Evaluate if an error needs to be raised if the pricelist
        # is still not there.
        if not price_list:
            raise Exception("There is no pricelist")

        sale_values = {
            'party': request.nereid_user.party.id,
            'currency': request.nereid_currency.id,
            'price_list': price_list,
            'company': site.company.id,
            'is_cart': True,
            'state': 'draft',
            'website': site.id,
            'nereid_user': user.id,
            'warehouse': request.nereid_website.warehouse.id,
        }
        return Sale.create([sale_values])[0]

    @classmethod
    def add_to_cart(cls):
        """
        Adds the given item to the cart if it exists or to a new cart

        The form is expected to have the following data is post

            quantity    : decimal
            product     : integer ID
            action      : set (default), add

        Response:
            'OK' if X-HTTPRequest
            Redirect to shopping cart if normal request
        """
        form = AddtoCartForm(request.form)
        if request.method == 'POST' and form.validate():
            cart = cls.open_cart(create_order=True)
            action = request.values.get('action', 'set')
            if form.quantity.data <= 0:
                flash(
                    _('Be sensible! You can only add real quantities to cart')
                )
                return redirect(url_for('nereid.cart.view_cart'))
            cls._add_or_update(
                cart.sale.id, form.product.data, form.quantity.data, action
            )
            if action == 'add':
                flash(_('The product has been added to your cart'), 'info')
            else:
                flash(_('Your cart has been updated with the product'), 'info')
            if request.is_xhr:
                return jsonify(message='OK')

        return redirect(url_for('nereid.cart.view_cart'))

    @classmethod
    def _add_or_update(cls, sale_id, product_id, quantity, action='set'):
        '''Add item as a line or if a line with item exists
        update it for the quantity

        :param sale: ID of sale
        :param product: ID of the product
        :param quantity: Quantity
        :param action: set - set the quantity to the given quantity
                       add - add quantity to existing quantity
        '''
        SaleLine = Pool().get('sale.line')
        Sale = Pool().get('sale.sale')

        sale = Sale(sale_id)
        lines = SaleLine.search([
            ('sale', '=', sale.id), ('product', '=', product_id)])
        if lines:
            order_line = lines[0]
            values = {
                'product': product_id,
                '_parent_sale.currency': sale.currency.id,
                '_parent_sale.party': sale.party.id,
                '_parent_sale.price_list': sale.price_list.id,
                'unit': order_line.unit.id,
                'quantity': quantity if action == 'set'
                    else quantity + order_line.quantity,
                'type': 'line',
            }
            values.update(SaleLine(**values).on_change_quantity())

            new_values = {}
            for key, value in values.iteritems():
                if '.' not in key:
                    new_values[key] = value
                if key == 'taxes' and value:
                    new_values[key] = [('set', value)]
            SaleLine.write([order_line], new_values)
            return order_line
        else:
            values = {
                'product': product_id,
                '_parent_sale.currency': sale.currency.id,
                '_parent_sale.party': sale.party.id,
                '_parent_sale.price_list': sale.price_list.id,
                'sale': sale.id,
                'type': 'line',
                'quantity': quantity,
                'unit': None,
                'description': None,
            }
            values.update(SaleLine(**values).on_change_product())
            values.update(SaleLine(**values).on_change_quantity())
            new_values = {}
            for key, value in values.iteritems():
                if '.' not in key:
                    new_values[key] = value
                if key == 'taxes' and value:
                    new_values[key] = [('set', value)]
            return SaleLine.create([new_values])[0]

    @classmethod
    def delete_from_cart(cls, line):
        """
        Delete a line from the cart. The required argument in POST is:

            line_id : ID of the line

        Response: 'OK' if X-HTTPRequest else redirect to shopping cart
        """
        SaleLine = Pool().get('sale.line')

        sale_line = SaleLine(line)
        assert sale_line.sale.id == cls.open_cart().sale.id
        SaleLine.delete([sale_line])
        flash(_('The order item has been successfully removed'))

        if request.is_xhr:
            return jsonify(message='OK')

        return redirect(url_for('nereid.cart.view_cart'))

    @classmethod
    def context_processor(cls):
        """This function will be called by nereid to update
        the template context. Must return a dictionary that the context
        will be updated with.

        This function is registered with nereid.template.context_processor
        in xml code
        """
        return {
            'get_cart_size': cls.cart_size,
            'get_cart': cls.open_cart,
        }


@login.connect
def login_event_handler(website_obj=None):
    """This method is triggered when a login event occurs.

    When a user logs in, all items in his guest cart should be added to his
    logged in or registered cart. If there is no such cart, it should be
    created.

    .. versionchanged:: 2.4.0.1
        website_obj was previously a mandatory argument because the pool
        object in the class was required to load other objects from the pool.
        Since pool object is a singleton, this object is not required.
    """

    if website_obj is not None:
        warnings.warn(
            "login_event_handler will not accept arguments from "
            "Version 2.5 +", DeprecationWarning, stacklevel=2
        )

    try:
        Cart = Pool().get('nereid.cart')
    except KeyError:
        # Just return silently. This KeyError is cause if the module is not
        # installed for a specific database but exists in the python path
        # and is loaded by the tryton module loader
        current_app.logger.warning(
            "nereid-cart-b2c module installed but not in database"
        )
        return

    # Find the guest cart
    try:
        guest_cart, = Cart.search([
            ('sessionid', '=', session.sid),
            ('user', '=', request.nereid_website.guest_user.id),
            ('website', '=', request.nereid_website.id)
        ], limit=1)
    except ValueError:
        return

    # There is a cart
    if guest_cart.sale and guest_cart.sale.lines:
        to_cart = Cart.open_cart(True)
        # Transfer lines from one cart to another
        for from_line in guest_cart.sale.lines:
            Cart._add_or_update(
                to_cart.sale.id, from_line.product.id, from_line.quantity
            )

    # Clear and delete the old cart
    guest_cart._clear_cart()
