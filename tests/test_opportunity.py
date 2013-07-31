# -*- coding: utf-8 -*-
"""
    test_opportunity

    Test suite for crm

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import sys
import os
import datetime
import simplejson as json
from dateutil.relativedelta import relativedelta
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.tests.test_tryton import test_view, test_depends
from nereid.testing import NereidTestCase


class NereidCRMTestCase(NereidTestCase):
    '''
    Test Nereid CRM module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('nereid_crm')

        self.nereid_website_obj = POOL.get('nereid.website')
        self.nereid_permission_obj = POOL.get('nereid.permission')
        self.nereid_user_obj = POOL.get('nereid.user')
        self.url_map_obj = POOL.get('nereid.url_map')
        self.company_obj = POOL.get('company.company')
        self.employee_obj = POOL.get('company.employee')
        self.currency_obj = POOL.get('currency.currency')
        self.country_obj = POOL.get('country.country')
        self.language_obj = POOL.get('ir.lang')
        self.party_obj = POOL.get('party.party')
        self.sale_opp_obj = POOL.get('sale.opportunity')
        self.user_obj = POOL.get('res.user')
        self.Config = POOL.get('sale.configuration')
        self.xhr_header = [
            ('X-Requested-With', 'XMLHttpRequest'),
        ]

    def _create_fiscal_year(self, date=None, company=None):
        """Creates a fiscal year and requried sequences
        """
        fiscal_year_obj = POOL.get('account.fiscalyear')
        sequence_obj = POOL.get('ir.sequence')
        sequence_strict_obj = POOL.get('ir.sequence.strict')
        company_obj = POOL.get('company.company')

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

    def _create_coa_minimal(self, company):
        """Create a minimal chart of accounts
        """
        account_template_obj = POOL.get('account.account.template')
        account_obj = POOL.get('account.account')
        account_create_chart = POOL.get(
            'account.create_chart', type="wizard")

        account_template, = account_template_obj.search(
            [('parent', '=', None)])

        session_id, _, _ = account_create_chart.create()
        create_chart = account_create_chart(session_id)
        create_chart.account.account_template = account_template
        create_chart.account.company = company
        create_chart.transition_create_account()

        receivable, = account_obj.search([
            ('kind', '=', 'receivable'),
            ('company', '=', company),
            ])
        payable, = account_obj.search([
            ('kind', '=', 'payable'),
            ('company', '=', company),
            ])
        create_chart.properties.company = company
        create_chart.properties.account_receivable = receivable
        create_chart.properties.account_payable = payable
        create_chart.transition_create_properties()

    def _get_account_by_kind(self, kind, company=None, silent=True):
        """Returns an account with given spec

        :param kind: receivable/payable/expense/revenue
        :param silent: dont raise error if account is not found
        """
        account_obj = POOL.get('account.account')
        company_obj = POOL.get('company.company')

        if company is None:
            company, = company_obj.search([], limit=1)

        account_ids = account_obj.search([
            ('kind', '=', kind),
            ('company', '=', company)
            ], limit=1)
        if not account_ids and not silent:
            raise Exception("Account not found")
        return account_ids[0] if account_ids else False


    def setup_defaults(self):
        '''
        Setup defaults for test
        '''
        usd = self.currency_obj.create({
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        })
        self.country_obj.create({
            'name': 'India',
            'code': 'IN',
        })
        self.country, = self.country_obj.search([])

        with Transaction().set_context(company=None):
            self.company = self.company_obj.create({
                'name': 'Openlabs',
                'currency': usd,
            })

        self.user_obj.write([self.user_obj(USER)], {
            'company': self.company,
            'main_company': self.company,
        })
        CONTEXT.update(self.user_obj.get_preferences(context_only=True))

        self._create_fiscal_year(company=self.company.id)
        self._create_coa_minimal(company=self.company.id)

        self.guest_user = self.nereid_user_obj.create({
            'name': 'Guest User',
            'display_name': 'Guest User',
            'email': 'guest@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
        })
        self.crm_admin = self.nereid_user_obj.create({
            'name': 'Crm Admin',
            'display_name': 'Crm Admin',
            'email': 'admin@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
        })
        employee = self.employee_obj.create({
            'company': self.company.id,
            'party': self.crm_admin.party.id,
        })

        self.Config.write([self.Config(1)], {'website_employee': employee.id})

        self.nereid_user_obj.write([self.crm_admin], {
            'employee': employee.id,
        })

        self.crm_admin2 = self.nereid_user_obj.create({
            'name': 'Crm Admin2',
            'display_name': 'Crm Admin2',
            'email': 'admin2@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
        })
        employee = self.employee_obj.create({
            'company': self.company.id,
            'party': self.crm_admin2.party.id,
        })
        self.nereid_user_obj.write([self.crm_admin2], {
            'employee': employee.id,
        })

        url_map, = self.url_map_obj.search([], limit=1)
        en_us, = self.language_obj.search([('code', '=', 'en_US')])
        self.nereid_website_obj.create({
            'name': 'localhost',
            'url_map': url_map,
            'company': self.company,
            'application_user': USER,
            'default_language': en_us,
            'guest_user': self.guest_user,
        })
        self.templates = {
            'localhost/home.jinja': '{{get_flashed_messages()}}',
            'localhost/login.jinja':
                    '{{ login_form.errors }} {{get_flashed_messages()}}',
            'localhost/crm/sale_form.jinja': ' ',
            'localhost/crm/leads.jinja': '{{leads|length}}',
        }
        perm_admin, = self.nereid_permission_obj.search([
            ('value', '=', 'sales.admin'),
        ])
        self.nereid_user_obj.write(
            [self.crm_admin], {'permissions': [('set', [perm_admin])]}
        )

    def create_test_lead(self):
        '''
        Setup test sale
        '''
        self.setup_defaults()
        Address = POOL.get('party.address')
        ContactMech = POOL.get('party.contact_mechanism')
        Party = POOL.get('party.party')
        Company = POOL.get('company.company')
        Country = POOL.get('country.country')

        # Create Party
        party = Party.create({
            'name': "abc",
            'addresses': [
                ('create', {
                    'name': 'abc',
                    'country': self.country,
                })
            ],
        })

        # Create email as contact mech and assign as email
        contact_mech = ContactMech.create({
            'type': 'email',
            'party': party.id,
            'email': 'client@example.com',
        })
        Address.write(
            [party.addresses[0]], {'email': 'client@example.com'}
        )

        # Create sale opportunity
        description = 'Created by %s' % self.crm_admin.display_name
        self.lead = self.sale_opp_obj.create({
            'party': party.id,
            'company': self.company,
            'employee': self.crm_admin.employee.id,
            'address': party.addresses[0].id,
            'description': description,
            'comment': 'comment',
            'ip_address': '127.0.0.1',
            'detected_country': '',
        })

    def get_template_source(self, name):
        """
        Return templates
        """
        return self.templates.get(name)

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('nereid_crm')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test_0010_new_opportunity(self):
        """
        Test new_opportunity web handler
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                response = c.post(
                    '/en_US/sales/opportunity/-new',
                    data={
                        'company': 'ABC',
                        'name': 'Tarun',
                        'email': 'demo@example.com',
                        'comment': 'comment',
                    },
                    headers=self.xhr_header,
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(json.loads(response.data)['success'])

    def test_0020_revenue_opportunity(self):
        '''
        Test revenue_opportunity web handler
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.create_test_lead()
            app = self.get_app()

            with app.test_client() as c:
                response = c.post(
                    '/en_US/login',
                    data={
                        'email': 'admin@openlabs.co.in',
                        'password': 'password',
                    }
                )
                self.assertEqual(response.status_code, 302)
                response = c.post(
                    '/en_US/sales/opportunity/lead-revenue/%d' % self.lead.id,
                    data={
                        'probability': 1,
                        'amount': 100,
                    }
                )
                self.assertEqual(response.status_code, 302)

    def test_0030_assign_lead(self):
        '''
        Test assign_lead
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.create_test_lead()
            app = self.get_app()

            with app.test_client() as c:
                response = c.post(
                    '/en_US/login',
                    data={
                        'email': 'admin@openlabs.co.in',
                        'password': 'password',
                    }
                )
                self.assertEqual(response.status_code, 302)
                response = c.post(
                    '/en_US/lead-%d/-assign' % self.lead.id,
                    data={
                        'user': self.crm_admin.id,
                    }
                )
                self.assertEqual(response.status_code, 302)
                response = c.get('/en_US/login')
                self.assertTrue(
                    "Lead already assigned to %s" % self.crm_admin.name
                    in response.data
                )
                response = c.post(
                    '/en_US/lead-%d/-assign' % self.lead.id,
                    data={
                        'user': self.crm_admin2.id,
                    }
                )
                self.assertEqual(response.status_code, 302)
                response = c.get('/en_US/login')
                self.assertTrue(
                    "Lead assigned to %s" % self.crm_admin2.name
                    in response.data
                )

    def test_0040_all_leads(self):
        '''
        Test all_leads
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.create_test_lead()
            app = self.get_app()

            with app.test_client() as c:
                response = c.post(
                    '/en_US/login',
                    data={
                        'email': 'admin@openlabs.co.in',
                        'password': 'password',
                    }
                )
                self.assertEqual(response.status_code, 302)
                response = c.get(
                    '/en_US/sales/opportunity/leads',
                )
                self.assertEqual(
                    response.data, u'1'
                )


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            NereidCRMTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
