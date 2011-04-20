#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Nereid : Shopping Cart B2C',
    'version': '1.8.0.1',
    'author': 'Open Labs Business Solutions',
    'email': 'info@openlabs.co.in',
    'website': 'http://www.openlabs.co.in/',
    'description': '''
    - B2C Shopping Cart.
    - Hooks for Gateways    
    ''',
    'depends': [
                "product",
                "nereid_catalog",
                "sale",
                "sale_price_list",
        ],
    'xml': [
        'cart.xml',
        'urls.xml',
        'sale.xml',
        ],
    'translation': [
        ],
}
