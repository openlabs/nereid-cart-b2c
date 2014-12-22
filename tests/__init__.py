#!/usr/bin/env python
# This file is part of Tryton and Nereid. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from test_cart import TestCart
from test_product import TestProduct
from test_website import TestWebsite


def suite():
    "Cart test suite"
    suite = unittest.TestSuite()
    suite.addTests([
        unittest.TestLoader().loadTestsFromTestCase(TestCart),
        unittest.TestLoader().loadTestsFromTestCase(TestProduct),
        unittest.TestLoader().loadTestsFromTestCase(TestWebsite),
    ])
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
