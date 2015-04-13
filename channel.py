# -*- coding: utf-8 -*-
"""
    channel.py

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = ['SaleChannel']


class SaleChannel:
    """
    Sale Channel
    """
    __name__ = 'sale.channel'

    @classmethod
    def get_source(cls):
        """
        Override the get_source method to add 'Webshop' as a source in channel
        """
        sources = super(SaleChannel, cls).get_source()
        sources.append(('webshop', 'Webshop'))

        return sources
