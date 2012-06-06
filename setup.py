#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from setuptools import setup
import re

info = eval(open('__tryton__.py').read())
major_version, minor_version, _ = info.get('version', '0.0.1').split('.', 2)
major_version = int(major_version)
minor_version = int(minor_version)

requires = ['blinker']
for dep in info.get('depends', []):
    if not re.match(r'(ir|res|workflow|webdav|nereid)(\W|$)', dep):
        requires.append('trytond_%s >= %s.%s, < %s.%s' %
                (dep, major_version, minor_version, major_version,
                    minor_version + 1))
requires.append('trytond >= %s.%s, < %s.%s' %
        (major_version, minor_version, major_version, minor_version + 1))

setup(name='trytond_nereid_cart_b2c',
    version=info.get('version', '0.0.1'),
    description=info.get('description', ''),
    author=info.get('author', ''),
    author_email=info.get('email', ''),
    url=info.get('website', ''),
    download_url="http://downloads.openlabs.co.in/" + \
            info.get('version', '0.0.1').rsplit('.', 1)[0] + '/',
    package_dir={'trytond.modules.nereid_cart_b2c': '.'},
    packages=[
        'trytond.modules.nereid_cart_b2c',
        'trytond.modules.nereid_cart_b2c.tests',
    ],
    package_data={
        'trytond.modules.nereid_cart_b2c': info.get('xml', []) \
                + info.get('translation', []) \
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
)
