# -*- coding: UTF-8 -*-
'''
    nereid_cart.sale

    Sales modules changes to fit nereid

    :copyright: (c) 2010-2011 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
'''
from trytond.model import ModelView, ModelSQL, fields

class Sale(ModelSQL, ModelView):
    '''Sale Order in the current way requires
    partner_id and addresses to create a draft order. This
    cannot fit an ecommerce system where the customer will 
    fill up the address only at the checkout (Order confirmation)
    or even the partner might be a guest ?

    Making a new model for cart will severely hamper the capabilities
    like sale promotions which have been designed for sale.sale. Hence
    the objective is to create a pre-draft stage now called cart where
    there are no required fields. However, the partner field always needs
    to be filled up as the price computation it is critical to price
    computation. B2C shops must extend to fill up the partner with a
    guest user.
    '''
    _name = 'sale.sale'

    is_cart = fields.Boolean('Is Cart ?')

    def default_state(self):
        return 'cart'
        
    def default_is_cart(self):
        return False

    def __init__(self):
        super(Sale, self).__init__()
        if ('cart', 'Cart') not in self.state.selection:
            self.state.selection.insert(0, ('cart', 'Cart'))

Sale()
