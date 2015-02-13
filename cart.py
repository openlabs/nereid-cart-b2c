# -*- coding: UTF-8 -*-
'''
    nereid_cart.cart

    Cart

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
import warnings
from decimal import Decimal
from functools import partial

from nereid import jsonify, render_template, flash, request, login_required, \
    url_for, current_user, route, context_processor, abort
from nereid.contrib.locale import make_lazy_gettext
from nereid.globals import session, current_app
from flask.ext.login import user_logged_in
from werkzeug import redirect
from babel import numbers


from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta

from .forms import AddtoCartForm
_ = make_lazy_gettext('nereid_cart_b2c')

__all__ = ['Cart']
__metaclass__ = PoolMeta


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

    @staticmethod
    def default_user():
        if not current_user.is_anonymous():
            return current_user.id

    @staticmethod
    def default_session():
        return session.sid

    @staticmethod
    def default_website():
        return request.nereid_website.id

    @classmethod
    @context_processor('get_cart_size')
    def cart_size(cls):
        "Returns the sum of quantities in the cart"
        cart = cls.open_cart()
        return sum([line.quantity for line in cart.sale.lines]) \
            if cart.sale else Decimal('0')

    @classmethod
    @login_required
    def _get_addresses(cls):
        'Returns a list of tuple of addresses'
        return [
            (address.id, address.full_address)
            for address in current_user.party.addresses
        ]

    @classmethod
    @route('/cart', readonly=False)
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
                    'product': l.product and l.product.name or None,
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

        response = render_template('shopping-cart.jinja', cart=cart)
        response.headers['Cache-Control'] = 'max-age=0'
        return response

    @classmethod
    @route('/esi/cart')
    def view_cart_esi(cls):
        """Returns a view of the shopping cart

        Similar to :meth:view_cart but for ESI
        """
        cart = cls.open_cart()
        response = render_template('shopping-cart-esi.jinja', cart=cart)
        response.headers['Cache-Control'] = 'max-age=0'
        return response

    def _clear_cart(self):
        """
        Clear the shopping cart by deleting both the sale associated
        with it and the cart itself.
        """
        Sale = Pool().get('sale.sale')

        if self.sale:
            Sale.cancel([self.sale])
            Sale.delete([self.sale])
        if self.id is not None:
            # An unsaved active record ?
            self.__class__.delete([self])

    @classmethod
    @route('/cart/clear', methods=['POST'])
    def clear_cart(cls):
        """
        Clears the current cart and redirects to shopping cart page
        """
        cart = cls.open_cart()
        cart._clear_cart()
        flash(_('Your shopping cart has been cleared'))
        return redirect(url_for('nereid.cart.view_cart'))

    @classmethod
    def find_cart(cls, user=None):
        """
        Return the cart for the user if one exists. The user is None a guest
        cart for the session is found.

        :param user: ID of the user
        :return: Active record of cart or None
        """
        domain = [
            ('website', '=', request.nereid_website.id),
            ('user', '=', user),
        ]
        if not user:
            domain.append(('sessionid', '=', session.sid))
        carts = cls.search(domain, limit=1)
        return carts[0] if carts else None

    @classmethod
    def create_cart(cls, user=None):
        """
        Create and return an acive record of the cart. If a user is provided,
        a cart for that user is created. Else a cart is created for the
        session.

        :param user: ID of the nereid.user
        """
        values = {}
        if user:
            values['user'] = user
        else:
            values['sessionid'] = session.sid
        return cls.create([values])[0]

    @classmethod
    @context_processor('get_cart')
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
        user_id = current_user.id

        cart = cls.find_cart(user_id)

        if cart:
            cart.sanitise_state(user_id)
        elif create_order:
            cart = cls.create_cart(user_id)
        else:
            # Return an instance of the unsaved active record to keep the api
            # simple and sweet.
            return cls(user=user_id, sale=None)

        # Check if the order needs to be created
        if create_order and not cart.sale:
            existing_sale_orders = None
            if user_id:
                # Try any abandoned carts that may exist if user is registered
                user = NereidUser(user_id)
                existing_sale_orders = Sale.search([
                    ('state', '=', 'draft'),
                    ('is_cart', '=', True),
                    ('website', '=', request.nereid_website.id),
                    ('party', '=', user.party.id),
                    ('currency', '=', request.nereid_currency.id)
                ], limit=1)
            if existing_sale_orders:
                cart.sale = existing_sale_orders[0]
                cart.save()
            else:
                cart.create_draft_sale()

        return cls(cart.id)

    def sanitise_state(self, user_id):
        """This method verifies that the sale order in the cart is a valid one
        1. for example must not be in any other state than draft
        2. must be of the current currency
        3. must be owned by the given user

        :param user_id: ID of the user
        """
        NereidUser = Pool().get('nereid.user')

        if not self.sale:
            return
        if self.sale.state != 'draft':
            current_app.logger.debug('Sale state is not draft')
            self.sale = None
        elif self.sale.currency != request.nereid_currency:
            current_app.logger.debug('Sale currency differs from request')
            self.sale = None
        elif user_id and (self.sale.party.id != NereidUser(user_id).party.id):
            current_app.logger.debug("Order party differs from user's party")
            self.sale = None
        return self.save()

    def check_update_date(self):
        """Check if the sale_date is same as today
        If not then update the sale_date with today's date
        """
        Date = Pool().get('ir.date')
        Sale = Pool().get('sale.sale')

        if self.sale and self.sale.sale_date \
                and self.sale.sale_date < Date.today():
            Sale.write([self.sale], {'sale_date': Date.today()})

    def create_draft_sale(self, user=None, party=None):
        """A helper for the cart which creates a draft order for the given
        user.

        :param user: ActiveRecord of the user If not provided, uses the
                     user of the cart. If the user is not mentioned in the cart
                     (guest cart), the user is guest user of the website.
        :param party: PArty who has to own the sale
        """
        Sale = Pool().get('sale.sale')

        if user is None:
            user = self.user or request.nereid_website.guest_user
        if party is None:
            party = user.party

        sale_values = {
            'party': party.id,
            'currency': request.nereid_currency.id,
            'company': request.nereid_website.company.id,
            'is_cart': True,
            'state': 'draft',
            'website': request.nereid_website.id,
            'nereid_user': user.id,
            'warehouse': request.nereid_website.warehouse.id,
            'payment_term': request.nereid_website.payment_term,
        }
        self.sale = Sale.create([sale_values])[0]
        self.save()

    @classmethod
    @route('/cart/add', methods=['POST'])
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
        Product = Pool().get('product.product')

        form = AddtoCartForm()
        if form.validate_on_submit():
            cart = cls.open_cart(create_order=True)
            action = request.values.get('action', 'set')
            if form.quantity.data <= 0:
                flash(
                    _('Be sensible! You can only add real quantities to cart')
                )
                return redirect(url_for('nereid.cart.view_cart'))

            if not Product(form.product.data).template.salable:
                if request.is_xhr:
                    return jsonify(message="This product is not for sale"), 400
                flash(_("This product is not for sale"))
                return redirect(request.referrer)

            sale_line = cart.sale._add_or_update(
                form.product.data, form.quantity.data, action
            )
            sale_line.save()

            if action == 'add':
                flash(_('The product has been added to your cart'), 'info')
            else:
                flash(_('Your cart has been updated with the product'), 'info')
            if request.is_xhr:
                return jsonify(message='OK')

        return redirect(url_for('nereid.cart.view_cart'))

    def _add_or_update(self, product_id, quantity, action='set'):
        '''Add item as a line or if a line with item exists
        update it for the quantity

        :param product: ID of the product
        :param quantity: Quantity
        :param action: set - set the quantity to the given quantity
                       add - add quantity to existing quantity
        '''
        warnings.warn(
            "cart._add_or_update will be deprecated. "
            "Use cart.sale._add_or_update instead",
            DeprecationWarning, stacklevel=2
        )
        return self.sale._add_or_update(product_id, quantity, action)

    @classmethod
    @route('/cart/delete/<int:line>', methods=['DELETE', 'POST'])
    def delete_from_cart(cls, line):
        """
        Delete a line from the cart. The required argument in POST is:

            line_id : ID of the line

        Response: 'OK' if X-HTTPRequest else redirect to shopping cart
        """
        SaleLine = Pool().get('sale.line')

        cart = cls.open_cart()
        if not cart.sale:
            abort(404)

        try:
            sale_line, = SaleLine.search([
                ('id', '=', line),
                ('sale', '=', cart.sale.id),
            ])
        except ValueError:
            message = 'Looks like the item is already deleted.'
        else:
            SaleLine.delete([sale_line])
            message = 'The order item has been successfully removed.'

        flash(_(message))

        if request.is_xhr:
            return jsonify(message=message)

        return redirect(url_for('nereid.cart.view_cart'))

    @staticmethod
    @user_logged_in.connect
    def login_event_handler(sender, user):
        '''
        This method itself does not do anything required by the login handler.
        All the hard work is done by the :meth:`_login_event_handler`. This is
        to ensure that downstream modules have the ability to modify the
        default behavior.

        .. note::

            It is possible that the cart module is available in the site
            packages and Tryton loads it, but the mdoule may not be installed
            in the specific database. To avoid false triggers, the code
            ensures that the model is in pool

        '''
        try:
            Cart = Pool().get('nereid.cart')
        except KeyError:
            current_app.logger.warning(
                "nereid-cart-b2c module installed but not in database"
            )
        else:
            Cart._login_event_handler(user)

    @classmethod
    def _login_event_handler(cls, user=None):
        """This method is triggered when a login event occurs.

        When a user logs in, all items in his guest cart should be added to his
        logged in or registered cart. If there is no such cart, it should be
        created.
        """
        # Find the guest cart in current session
        guest_cart = cls.find_cart(None)

        if not guest_cart:
            return

        # There is a cart
        if guest_cart.sale and guest_cart.sale.lines:
            to_cart = cls.open_cart(True)
            # Transfer lines from one cart to another
            for from_line in guest_cart.sale.lines:
                sale_line = from_line.add_to(to_cart.sale)
                sale_line.save()

        # Clear and delete the old cart
        guest_cart._clear_cart()
