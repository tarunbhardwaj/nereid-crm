# -*- coding: utf-8 -*-
"""
    __init__

    Nereid CRM test cases

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import unittest

import trytond.tests.test_tryton
from test_opportunity import NereidCRMTestCase


def suite():
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(NereidCRMTestCase)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
