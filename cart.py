# -*- coding: UTF-8 -*-
'''
    nereid_cart.cart

    Cart

    :copyright: (c) 2010-2011 by Openlabs Technologies & Consulting (P) LTD
    :license: GPLv3, see LICENSE for more details
'''
from nereid import jsonify, render_template, flash
from nereid.helpers import login_required, url_for
from nereid.globals import session, request
from werkzeug import redirect

from trytond.model import ModelSQL, ModelView, fields
from trytond.transaction import Transaction

from .forms import AddtoCartForm


# pylint: disable-msg=E1101
class Cart(ModelSQL, ModelView):
    """
    Shopping Cart plays the link between a customer's shopping experience
    and the creation of a Sale Order in the backend.

    A Draft Sale Order is maintained through out the process of the existance
    of a cart which is finally converted into a confirmed sale order once 
    the process is complete. As the ideal design would be a B2B env
    where the payment could also be made on credit and the Sale Order 
    process itself is more aligned to the B2B model, the payment will be made
    as a payment line in a given journal.

    """
    _name = 'nereid.cart'
    _description = 'Shopping Cart'
    _rec_name = 'user'

    user = fields.Many2One('party.address', 'Cart owner')
    sale = fields.Many2One('sale.sale', 'Sale Order')
    sessionid = fields.Char('Session ID')

    def cart_size(self):
        "Returns the sum of quantities in the cart"
        cart = self.open_cart()
        return sum([line.quantity for line in cart.sale.lines])

    #@property
    #def current_user_pricelist(self):
    #    'DEPRECIATED: Return the pricelist of the current session'
    #    import warnings
    #    warnings.warn("""This method will be depreciated in upcoming release, 
    #    Use the method current_user_pricelist in product.product
    #        """, DeprecationWarning)
    #
    #    product_obj = self.pool.get('product.product')
    #    return product_obj.current_user_pricelist

    @login_required
    def _get_addresses(self):
        'Returns a list of tuple of addresses'
        party = request.nereid_user.party
        address_obj = self.pool.get('party.address')
        return address_obj.name_get_([a.id for a in partner.address])

    def view_cart(self):
        """Returns a view of the shopping cart

        This method only handles GET. Unlike previous versions
        the checkout method has been moved to nereid.checkout.x
        """ 
        cart = self.open_cart()
        return render_template('shopping-cart.jinja', cart=cart)

    def clear_cart(self):
        """
        Clears the current cart and redirects to shopping cart page
        """
        sale_obj = self.pool.get('sale.sale')

        cart = self.open_cart()
        if cart.sale:
            sale_obj.workflow_trigger_validate(cart.sale.id, 'cancel')
            sale_obj.delete(cart.sale.id)
        self.delete(cart.id)
        flash('Your shopping cart has been cleared')
        return redirect(url_for('nereid.cart.view_cart'))
        
    def open_cart(self):
        """
        Returns the browse record for the shopping cart of the user
        Creates one if it doesn't exist
        The method is guaranteed to return a cart
        """
        if request.is_guest_user:
            ids = self.search([('sessionid', '=', session.sid)], limit=1)
        else:
            ids = self.search([('user', '=', session['user'])], limit=1)

        if ids:
            cart = self.browse(ids[0])
            # Check if a sale order is still attached
            if (not cart.sale) or (not cart.sale.state in ['draft', 'cart']):
                self.delete(cart.id)
                ids = None

        if not ids:
            sale_obj = self.pool.get('sale.sale')
            site = request.nereid_website
            sale_values = {
                'party': request.nereid_user.party.id,
                'currency': session.get('currency', site.company.currency.id),
                'company': site.company.id,
                }
            cart_id = self.create({
                'user': session['user'] if 'user' in session else False,
                'sessionid': session.sid,
                'sale': sale_obj.create(sale_values)
                })
            cart = self.browse(cart_id)
        return cart

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
            cart = self.open_cart()
            self._add_or_update(cart, form.product.data, form.quantity.data)
            flash('The order has been successfully updated')
            if request.is_xhr:
                return jsonify(message='OK')

        return redirect(url_for('nereid.cart.view_cart'))

    def _add_or_update(self, cart, product, quantity):
        '''Add item as a line or if a line with item exists
        update it for the quantity

        :param cart: Browse Record
        :param product: ID of the product
        :param quantity: Quantity
        '''
        sale_line_obj = self.pool.get('sale.line')

        ids = sale_line_obj.search([
            ('sale', '=', cart.sale.id), ('product', '=', product)])
        if ids:
            order_line = sale_line_obj.browse(ids[0])
            values = {
                'product': product,
                '_parent_sale.currency': cart.sale.currency.id,
                '_parent_sale.party': cart.sale.party.id,
                'unit': order_line.unit.id,
                'quantity': quantity
                }
            values.update(sale_line_obj.on_change_quantity(values))
            return sale_line_obj.write(order_line.id, values)
        else:
            values = {
                'product': product,
                '_parent_sale.currency': cart.sale.currency.id,
                '_parent_sale.party': cart.sale.party.id,
                'sale': cart.sale.id,
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
        return {'get_cart_size': self.cart_size}

Cart()

