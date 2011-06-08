# -*- coding: UTF-8 -*-
'''
    nereid_cart.cart

    Cart

    :copyright: (c) 2010-2011 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
from decimal import Decimal
from nereid import jsonify, render_template, flash
from nereid.helpers import login_required, url_for
from nereid.globals import session, request, current_app
from nereid.signals import login
from werkzeug import redirect

from trytond.model import ModelSQL, ModelView, fields

from .forms import AddtoCartForm


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

    user = fields.Many2One('party.address', 'Cart owner')
    sale = fields.Many2One('sale.sale', 'Sale Order')
    sessionid = fields.Char('Session ID')
    website = fields.Many2One('nereid.website', 'Website')

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
        """
        cart = self.open_cart()
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
        sale_obj = self.pool.get('sale.sale')
        if cart.sale:
            sale_obj.workflow_trigger_validate(cart.sale.id, 'cancel')
            sale_obj.delete(cart.sale.id)
        self.delete(cart.id)

    def clear_cart(self):
        """
        Clears the current cart and redirects to shopping cart page
        """
        cart = self.open_cart()
        self._clear_cart(cart)
        flash('Your shopping cart has been cleared')
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
        # request.nereid_user is not used here this method is used by the 
        # signal handlers immediately after a user logs in (but before being 
        # redirected). This causes the cached property of nereid_user to remain
        # in old value through out the request, which will not  have ended when
        # this method is called.
        user_id = session.get('user', current_app.guest_user)

        # for a registered user there is only one cart, session is immaterial
        if 'user' in session:
            ids = self.search([
                ('sessionid', '=', False),
                ('user', '=', user_id)
            ])
        else:
            ids = self.search([
                ('sessionid', '=', session.sid),
                ('user', '=', user_id)
                ], limit=1)


        if not ids:
            # Create a cart since it definitely does not exists
            ids = [self.create({
                'user': user_id,
                'sessionid': session.sid if 'user' not in session else False,
            })]

        cart = self.browse(ids[0])

        # Check if the order needs to be created
        if create_order and not cart.sale:
            self.write(cart.id, {'sale': self.create_draft_sale(user_id)})

        return self.browse(ids[0])

    def transfer_ownership(self, cart, owner=None):
        """Transfer the ownership of the cart and sale if any to the new owner

        :param cart: Browse Record of the cart
        :param owner: Browse Record of party.address (of current user). If 
            owner is None, ownership is transferred to current user
        """
        sale_obj = self.pool.get('sale.sale')

        assert not request.is_guest_user, "Cannot transfer cart to guest user"
        if owner is None:
            owner = request.nereid_user

        self.write(cart.id, {'user': owner})

        if cart.sale:
            sale_obj.write(cart.sale.id, {'party': owner.party.id})
            # TODO: Evaluate the situation where the party has a different
            # pricelist from the guest pricelist. Then it might be better to 
            # call create_draft_sale to create a new order and then move lines
            # to the new order.

        return True

    def create_draft_sale(self, user_id):
        """A helper for the cart which creates a draft order for the given 
        user.
        """
        sale_obj = self.pool.get('sale.sale')
        party_address_obj = self.pool.get('party.address')

        site = request.nereid_website
        user = party_address_obj.browse(user_id)
        guest_user = party_address_obj.browse(current_app.guest_user)

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
            'website': site.id
                }
        return sale_obj.create(sale_values)

    def add_to_cart(self):
        """
        Adds the given item to the cart if it exists or to a new cart

        The form is expected to have the following data is post

            quantity    : decimal
            product     : integer ID

        Response:
            'OK' if X-HTTPRequest
            Redirect to shopping cart if normal request
        """
        form = AddtoCartForm(request.form)
        if request.method == 'POST' and form.validate():
            cart = self.open_cart(create_order=True)
            self._add_or_update(
                cart.sale, form.product.data, form.quantity.data)
            flash('The order has been successfully updated')
            if request.is_xhr:
                return jsonify(message='OK')

        return redirect(url_for('nereid.cart.view_cart'))

    def _add_or_update(self, sale, product, quantity):
        '''Add item as a line or if a line with item exists
        update it for the quantity

        :param sale: Browse Record of sale
        :param product: ID of the product
        :param quantity: Quantity
        '''
        sale_line_obj = self.pool.get('sale.line')

        ids = sale_line_obj.search([
            ('sale', '=', sale.id), ('product', '=', product)])
        if ids:
            order_line = sale_line_obj.browse(ids[0])
            values = {
                'product': product,
                '_parent_sale.currency': sale.currency.id,
                '_parent_sale.party': sale.party.id,
                '_parent_sale.price_list': sale.price_list.id,
                'unit': order_line.unit.id,
                'quantity': quantity,
                'type': 'line'
                }
            values.update(sale_line_obj.on_change_quantity(values))
            return sale_line_obj.write(order_line.id, values)
        else:
            values = {
                'product': product,
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
        sale_line_obj = self.pool.get('sale.line')

        sale_line = sale_line_obj.browse(line)
        assert sale_line.sale.id == self.open_cart().sale.id
        sale_line_obj.delete(line)
        flash('The order item has been successfully removed')

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
        cart_obj = self.pool.get('nereid.cart')

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
        cart_obj = self.pool.get('nereid.cart')
        cart = cart_obj.open_cart()

        rv = super(Website, self)._user_status()

        rv['cart_size'] = '%s' % cart_obj.cart_size()
        rv['cart_total_amount'] = '%s %.2f' % (
            (cart.sale.currency.symbol, cart.sale.total_amount) if cart.sale \
            else (request.nereid_currency.symbol, Decimal('0.0'))
            )

        return rv

Website()

@login.connect
def login_event_handler(website_obj):
    """This method is triggered when a login event occurs.

    When a user logs in, all items in his guest cart should be added to his
    logged in or registered cart. If there is no such cart, it should be 
    created.
    """
    cart_obj = website_obj.pool.get('nereid.cart')

    # Find the guest cart
    ids = cart_obj.search([
        ('sessionid', '=', session.sid),
        ('user', '=', current_app.guest_user)
        ], limit=1)
    if not ids:
        return

    # There is a cart
    guest_cart = cart_obj.browse(ids[0])
    if not guest_cart.sale:
        return
    if not guest_cart.sale.lines:
        return

    to_cart = cart_obj.open_cart(True)
    # Transfer lines from one cart to another
    for from_line in guest_cart.sale.lines:
        cart_obj._add_or_update(
            to_cart.sale, from_line.product.id, from_line.quantity)

    # Clear and delete the old cart
    cart_obj._clear_cart(guest_cart)
