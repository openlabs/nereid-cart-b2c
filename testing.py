# -*- coding: utf-8 -*-
"""
    testing

    Register Testing Helpers

    :copyright: (c) 2011-2012 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
import datetime
from dateutil.relativedelta import relativedelta

from nereid.testing import testing_proxy
from trytond.pool import Pool


@testing_proxy.register()
def create_fiscal_year(obj, date=None, company=None):
    """Creates a fiscal year and requried sequences
    """
    fiscal_year_obj = obj.pool.get('account.fiscalyear')
    sequence_obj = obj.pool.get('ir.sequence')
    sequence_strict_obj = obj.pool.get('ir.sequence.strict')
    company_obj = obj.pool.get('company.company')

    if date is None:
        date = datetime.date.today()

    if company is None:
        company, = company_obj.search([], limit=1)

    invoice_sequence = sequence_strict_obj.create({
        'name': '%s' % date.year,
        'code': 'account.invoice',
        'company': company,
        })
    fiscal_year = fiscal_year_obj.create({
        'name': '%s' % date.year,
        'start_date': date + relativedelta(month=1, day=1),
        'end_date': date + relativedelta(month=12, day=31),
        'company': company,
        'post_move_sequence': sequence_obj.create({
            'name': '%s' % date.year,
            'code': 'account.move',
            'company': company,
            }),
        'out_invoice_sequence': invoice_sequence,
        'in_invoice_sequence': invoice_sequence,
        'out_credit_note_sequence': invoice_sequence,
        'in_credit_note_sequence': invoice_sequence,
        })
    fiscal_year_obj.create_period([fiscal_year])
    return fiscal_year


@testing_proxy.register()
def create_coa_minimal(obj, company=None):
    """Create a minimal chart of accounts
    """
    account_template_obj = obj.pool.get('account.account.template')
    account_obj = obj.pool.get('account.account')
    account_journal_obj = obj.pool.get('account.journal')
    create_chart_account_obj = obj.pool.get(
        'account.create_chart', type="wizard")
    company_obj = obj.pool.get('company.company')

    account_template, = account_template_obj.search(
        [('parent', '=', False)])

    if company is None:
        company, = company_obj.search([], limit=1)

    session_id, start_state, end_state = create_chart_account_obj.create()
    # Stage 1
    create_chart_account_obj.execute(session_id, {}, 'start')
    # Stage 2
    create_chart_account_obj.execute(session_id, {
        start_state: {
            'account_template': account_template,
            'company': company,
            }
        }, 'account')
    # Stage 3
    revenue = account_obj.search([
        ('kind', '=', 'revenue'),
        ('company', '=', company),
        ])
    receivable = account_obj.search([
        ('kind', '=', 'receivable'),
        ('company', '=', company),
        ])
    payable = account_obj.search([
        ('kind', '=', 'payable'),
        ('company', '=', company),
        ])
    create_chart_account_obj.execute(session_id, {
        start_state: {
            'account_receivable': receivable,
            'account_payable': payable,
            'account_revenue': revenue,
            'company': company,
            }
        }, 'properties')


@testing_proxy.register()
def get_account_by_kind(self, kind, company=None, silent=True):
    """Returns an account with given spec

    :param kind: receivable/payable/expense/revenue
    :param silent: dont raise error if account is not found
    """
    account_obj = Pool().get('account.account')
    company_obj = Pool().get('company.company')

    if company is None:
        company, = company_obj.search([], limit=1)

    account_ids = account_obj.search([
        ('kind', '=', kind),
        ('company', '=', company)
        ], limit=1)
    if not account_ids and not silent:
        raise Exception("Account not found")
    return account_ids[0] if account_ids else False


@testing_proxy.register()
def create_payment_term(obj):
    """Create a simple payment term with all advance
    """
    payment_term_obj = obj.pool.get('account.invoice.payment_term')
    return payment_term_obj.create({
        'name': 'Direct',
        'lines': [('create', {'type': 'remainder'})]
        })
