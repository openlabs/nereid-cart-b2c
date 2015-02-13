#!/usr/bin/env python
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import re
import os
import ConfigParser
import unittest
from setuptools import setup, Command


class SQLiteTest(Command):
    """
    Run the tests on SQLite
    """
    description = "Run tests on SQLite"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if self.distribution.tests_require:
            self.distribution.fetch_build_eggs(self.distribution.tests_require)

        os.environ['TRYTOND_DATABASE_URI'] = 'sqlite://'
        os.environ['DB_NAME'] = ':memory:'

        from tests import suite
        test_result = unittest.TextTestRunner(verbosity=3).run(suite())

        if test_result.wasSuccessful():
            sys.exit(0)
        sys.exit(-1)


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

config = ConfigParser.ConfigParser()
config.readfp(open('tryton.cfg'))
info = dict(config.items('tryton'))
for key in ('depends', 'extras_depend', 'xml'):
    if key in info:
        info[key] = info[key].strip().splitlines()
major_version, minor_version, _ = info.get('version', '0.0.1').split('.', 2)
major_version = int(major_version)
minor_version = int(minor_version)

requires = [
    'blinker',
]

MODULE2PREFIX = {
    'sale_shop': 'trytonzz',
}

for dep in info.get('depends', []):
    if not re.match(r'(ir|res|webdav)(\W|$)', dep):
        requires.append(
            '%s_%s >= %s.%s, < %s.%s' % (
                MODULE2PREFIX.get(dep, 'trytond'), dep, major_version,
                minor_version, major_version, minor_version + 1
            )
        )
requires.append(
    'trytond >= %s.%s, < %s.%s' % (
        major_version, minor_version, major_version, minor_version + 1
    )
)

setup(
    name='trytond_nereid_cart_b2c',
    version=info.get('version', '0.0.1'),
    description="Nereid Cart B2C",
    author="Openlabs Technologies & consulting (P) Limited",
    author_email='info@openlabs.co.in',
    url='http://www.openlabs.co.in',
    package_dir={'trytond.modules.nereid_cart_b2c': '.'},
    packages=[
        'trytond.modules.nereid_cart_b2c',
        'trytond.modules.nereid_cart_b2c.tests',
    ],
    package_data={
        'trytond.modules.nereid_cart_b2c':
            info.get('xml', [])
            + info.get('translation', [])
            + ['tryton.cfg', 'locale/*.po', 'tests/*.rst']
            + ['i18n/*.pot', 'i18n/pt_BR/LC_MESSAGES/*'],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Plugins',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Tryton',
        'Topic :: Office/Business',
    ],
    license='GPL-3',
    install_requires=requires,
    zip_safe=False,
    entry_points="""
    [trytond.modules]
    nereid_cart_b2c = trytond.modules.nereid_cart_b2c
    """,
    test_suite='tests',
    test_loader='trytond.test_loader:Loader',
    tests_require=['pycountry'],
    cmdclass={
        'test': SQLiteTest,
    },
)
