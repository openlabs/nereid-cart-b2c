# -*- coding: UTF-8 -*-
'''
    nereid_cart.cart

    Cart

    :copyright: (c) 2010-2012 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
from decimal import Decimal
from functools import partial
import warnings

from nereid import jsonify, render_template, flash
from nereid.helpers import login_required, url_for
from nereid.globals import session, request, current_app
from nereid.signals import login
from werkzeug import redirect
from babel import numbers


from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool

from .forms import AddtoCartForm
from .i18n import _


# pylint: disable-msg=E1101
class Cart(ModelSQL):
    """
    Shopping Cart plays the link between a customer's shopping experience
    and the creation of a Sale Order in the backend.

    A Draft Sale Order is maintained through out the process of the existance
    of a cart which is finally converted into a confirmed sale order once
    the process is complete.
    """
    _name = 'nereid.cart'
    _description = 'Shopping Cart'
    _rec_name = 'user'

    user = fields.Many2One('nereid.user', 'Cart owner', select=True)
    sale = fields.Many2One('sale.sale', 'Sale Order', select=True)
    sessionid = fields.Char('Session ID', select=True)
    website = fields.Many2One('nereid.website', 'Website', select=True)

    def cart_size(self):
        "Returns the sum of quantities in the cart"
        cart = self.open_cart()
        return sum([line.quantity for line in cart.sale.lines]) \
            if cart.sale else Decimal('0')

    @login_required
    def _get_addresses(self):
        'Returns a list of tuple of addresses'
        party = request.nereid_user.party
        return [(address.id, address.full_address) \
            for address in party.addresses]

    def view_cart(self):
        """Returns a view of the shopping cart

        This method only handles GET. Unlike previous versions
        the checkout method has been moved to nereid.checkout.x

        For XHTTP/Ajax Requests a JSON object with order and lines information
        which should be sufficient to show order information is returned.
        """
        cart = self.open_cart()

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
            headers=[('Cache-Control', 'max-age=0')])

    def view_cart_esi(self):
        """Returns a view of the shopping cart

        Similar to :meth:view_cart but for ESI
        """
        cart = self.open_cart()
        return current_app.response_class(
            render_template('shopping-cart-esi.jinja', cart=cart),
            headers=[('Cache-Control', 'max-age=0')])

    def _clear_cart(self, cart):
        sale_obj = Pool().get('sale.sale')
        if cart.sale:
            sale_obj.cancel([cart.sale.id])
            sale_obj.delete(cart.sale.id)
        self.delete(cart.id)

    def clear_cart(self):
        """
        Clears the current cart and redirects to shopping cart page
        """
        cart = self.open_cart()
        self._clear_cart(cart)
        flash(_('Your shopping cart has been cleared'))
        return redirect(url_for('nereid.cart.view_cart'))

    def open_cart(self, create_order=False):
        """Logic of this cart functionality is inspired by amazon. Most
        e-commerce systems handle cart in a different way and it is important
        to know how the cart behaves under different circumstances.

        :param create_order: If `True` Create a sale order and attach
            if one does not already exist.
        :return: The browse record for the shopping cart of the user

        The method is guaranteed to return a cart but the cart may not have
        a sale order. For methods like add to cart which definitely need a sale
        order pass :attr: create_order = True so that an order is also assured.
        """
        sale_obj = Pool().get('sale.sale')
        nereid_user_obj = Pool().get('nereid.user')

        # request.nereid_user is not used here this method is used by the 
        # signal handlers immediately after a user logs in (but before being 
        # redirected). This causes the cached property of nereid_user to remain
        # in old value through out the request, which will not  have ended when
        # this method is called.
        user = nereid_user_obj.browse(
            session.get('user', request.nereid_website.guest_user.id)
        )

        # for a registered user there is only one cart, session is immaterial
        if 'user' in session:
            ids = self.search([
                ('sessionid', '=', False),
                ('user', '=', user.id),
                ('website', '=', request.nereid_website.id)
            ])
        else:
            ids = self.search([
                ('sessionid', '=', session.sid),
                ('user', '=', user.id),
                ('website', '=', request.nereid_website.id)
                ], limit=1)

        if not ids:
            # Create a cart since it definitely does not exists
            ids = [self.create({
                'user': user.id,
                'website': request.nereid_website.id,
                'sessionid': session.sid if 'user' not in session else None,
            })]

        cart = self.browse(ids[0])

        if cart.sale:
            self.sanitise_state(cart, user)

        # Check if the order needs to be created
        if create_order and not cart.sale:
            # Try any abandoned carts that may exist if user is registered
            sale_ids = sale_obj.search([
                ('state', '=', 'draft'),
                ('is_cart', '=', True),
                ('website', '=', request.nereid_website.id),
                ('party', '=', user.party.id),
                ('currency', '=', request.nereid_currency.id)
                ], limit=1) if 'user' in session else None
            self.write(cart.id, {
                'sale': sale_ids[0] if sale_ids \
                    else self.create_draft_sale(user)
                })

        return self.browse(ids[0])

    def sanitise_state(self, cart, user):
        """This method verifies that the sale order in the cart is a valid one
        1. for example must not be in any other state than draft
        2. must be of the current currency
        3. must be owned by the given user

        :param cart: browse node of the cart
        :param user: browse record of the user
        """
        if cart.sale:
            if cart.sale.state != 'draft' or \
                cart.sale.currency != request.nereid_currency or \
                cart.sale.party != user.party:
                self.write(cart.id, {'sale': False})

    def check_update_date(self, cart):
        """Check if the sale_date is same as today
        If not then update the sale_date with today's date

        :param cart: browse record of the cart
        """
        date_obj = Pool().get('ir.date')
        sale_obj = Pool().get('sale.sale')
        if cart.sale and cart.sale.sale_date \
                and cart.sale.sale_date < date_obj.today():
            sale_obj.write(cart.sale.id, {'sale_date': date_obj.today()})

    def create_draft_sale(self, user):
        """A helper for the cart which creates a draft order for the given
        user.

        :param user: Browse Record of the user
        """
        sale_obj = Pool().get('sale.sale')
        nereid_user_obj = Pool().get('nereid.user')

        site = request.nereid_website
        guest_user = nereid_user_obj.browse(current_app.guest_user)

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

        sale_values = {
            'party': request.nereid_user.party.id,
            'currency': request.nereid_currency.id,
            'price_list': price_list,
            'company': site.company.id,
            'is_cart': True,
            'state': 'draft',
            'website': site.id,
            'nereid_user': user.id
        }
        return sale_obj.create(sale_values)

    def add_to_cart(self):
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
            cart = self.open_cart(create_order=True)
            action = request.values.get('action', 'set')
            self._add_or_update(
                cart.sale.id, form.product.data, form.quantity.data, action
            )
            if action == 'add':
                flash(_('The product has been added to your cart'), 'info')
            else:
                flash(_('Your cart has been updated with the product'), 'info')
            if request.is_xhr:
                return jsonify(message='OK')

        return redirect(url_for('nereid.cart.view_cart'))

    def _add_or_update(self, sale_id, product_id, quantity, action='set'):
        '''Add item as a line or if a line with item exists
        update it for the quantity

        :param sale: ID of sale
        :param product: ID of the product
        :param quantity: Quantity
        :param action: set - set the quantity to the given quantity
                       add - add quantity to existing quantity
        '''
        sale_line_obj = Pool().get('sale.line')
        sale_obj = Pool().get('sale.sale')

        sale = sale_obj.browse(sale_id)
        ids = sale_line_obj.search([
            ('sale', '=', sale.id), ('product', '=', product_id)])
        if ids:
            order_line = sale_line_obj.browse(ids[0])
            values = {
                'product': product_id,
                '_parent_sale.currency': sale.currency.id,
                '_parent_sale.party': sale.party.id,
                '_parent_sale.price_list': sale.price_list.id,
                'unit': order_line.unit.id,
                'quantity': quantity if action == 'set' \
                        else quantity + order_line.quantity,
                'type': 'line'
                }
            values.update(sale_line_obj.on_change_quantity(values))

            new_values = { }
            for key, value in values.iteritems():
                if '.' not in key:
                    new_values[key] = value

            return sale_line_obj.write(order_line.id, new_values)
        else:
            values = {
                'product': product_id,
                '_parent_sale.currency': sale.currency.id,
                '_parent_sale.party': sale.party.id,
                '_parent_sale.price_list': sale.price_list.id,
                'sale': sale.id,
                'type': 'line',
                'quantity': quantity,
                }
            values.update(sale_line_obj.on_change_product(values))
            values.update(sale_line_obj.on_change_quantity(values))
            new_values = { }
            for key, value in values.iteritems():
                if '.' not in key:
                    new_values[key] = value
            return sale_line_obj.create(new_values)

    def delete_from_cart(self, line):
        """
        Delete a line from the cart. The required argument in POST is:

            line_id : ID of the line

        Response: 'OK' if X-HTTPRequest else redirect to shopping cart
        """
        sale_line_obj = Pool().get('sale.line')

        sale_line = sale_line_obj.browse(line)
        assert sale_line.sale.id == self.open_cart().sale.id
        sale_line_obj.delete(line)
        flash(_('The order item has been successfully removed'))

        if request.is_xhr:
            return jsonify(message='OK')

        return redirect(url_for('nereid.cart.view_cart'))

    def context_processor(self):
        """This function will be called by nereid to update
        the template context. Must return a dictionary that the context
        will be updated with.

        This function is registered with nereid.template.context_processor
        in xml code
        """
        return {
            'get_cart_size': self.cart_size,
            'get_cart': self.open_cart,
            }

Cart()


class Website(ModelSQL, ModelView):
    """Set Currency behaviour change"""
    _name = 'nereid.website'

    def set_currency(self):
        """Sets the currency for current session. A change in the currency
        should reset the cart if the currency of the cart is not the same as
        the one here
        """
        cart_obj = Pool().get('nereid.cart')

        rv = super(Website, self).set_currency()

        # If currency has changed drop the cart
        # This behaviour needs serious improvement. Probably create a new cart
        # with all items in this cart and then drop this one
        cart = cart_obj.open_cart()
        if cart.sale and cart.sale.currency.id != session['currency']:
            cart_obj.clear_cart()

        return rv

    def _user_status(self):
        """Add cart size and amount to the dictionary
        """
        cart_obj = Pool().get('nereid.cart')
        cart = cart_obj.open_cart()

        rv = super(Website, self)._user_status()

        if cart.sale:
            # Build locale based formatters
            currency_format = partial(
                numbers.format_currency, currency=cart.sale.currency.code,
                locale=request.nereid_language.code
            )
            number_format = partial(
                numbers.format_number, locale=request.nereid_language.code
            )

            rv['cart'] = {
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
            }
            rv['cart_total_amount'] = currency_format(
                cart.sale and cart.sale.total_amount or 0
            )

        rv['cart_size'] = '%s' % cart_obj.cart_size()

        return rv

Website()


@login.connect
def login_event_handler(website_obj):
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
        warnings.warn("login_event_handler will not accept arguments from "
            "Version 2.5 +", DeprecationWarning, stacklevel=2)

    try:
        cart_obj = Pool().get('nereid.cart')
    except KeyError:
        # Just return silently. This KeyError is cause if the module is not
        # installed for a specific database but exists in the python path
        # and is loaded by the tryton module loader
        current_app.logger.warning(
            "nereid-cart-b2c module installed but not in database"
        )
        return

    # Find the guest cart
    ids = cart_obj.search([
        ('sessionid', '=', session.sid),
        ('user', '=', current_app.guest_user),
        ('website', '=', request.nereid_website.id)
        ], limit=1)
    if not ids:
        return

    # There is a cart
    guest_cart = cart_obj.browse(ids[0])
    if guest_cart.sale and guest_cart.sale.lines:
        to_cart = cart_obj.open_cart(True)
        # Transfer lines from one cart to another
        for from_line in guest_cart.sale.lines:
            cart_obj._add_or_update(
                to_cart.sale.id, from_line.product.id, from_line.quantity)

    # Clear and delete the old cart
    cart_obj._clear_cart(guest_cart)
