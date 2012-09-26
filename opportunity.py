# -*- coding: utf-8 -*-
"""
    opportunnity

    Mini CRM based on Nereid and Sale Opprotunity

    :copyright: (c) 2012 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
import logging
from nereid import (request, abort, render_template, login_required, url_for,
    redirect, flash, jsonify, permissions_required)
from nereid.contrib.pagination import Pagination
from trytond.model import ModelView, ModelSQL, ModelSingleton, Workflow, fields
from trytond.pool import Pool
from trytond.pyson import Eval

geoip = None
try:
    from pygeoip import GeoIP
except ImportError:
    logging.error("pygeoip is not installed")
else:
    try:
        # Usual location in Ubuntu
        geoip = GeoIP('/usr/share/GeoIP/GeoIP.dat')
    except IOError:
        try:
            # this is where brew installs it
            geoip = GeoIP(
                '/usr/local/Cellar/geoip/1.4.8/share/GeoIP/GeoIP.dat'
            )
        except IOError:
            pass



class Configuration(ModelSingleton, ModelSQL, ModelView):
    "Sale Opportunity configuration"
    _name = 'sale.configuration'

    website_employee = fields.Property(
        fields.Many2One('company.employee', 'Website Employee')
    )

Configuration()


class SaleOpportunity(Workflow, ModelSQL, ModelView):
    "Sale Opportunity"
    _name = "sale.opportunity"

    ip_address = fields.Char('IP Address')
    reviews = fields.One2Many(
        'nereid.review',
        'lead', 'Reviews'
    )

    def new_opportunity(self):
        """Create a new sale opportunity
        """
        contact_form = request.form

        if request.method == 'POST':
            address_obj = Pool().get('party.address')
            contact_mech_obj = Pool().get('party.contact_mechanism')
            party_obj = Pool().get('party.party')
            config_obj = Pool().get('sale.configuration')
            company_obj = Pool().get('company.company')
            country_obj = Pool().get('country.country')

            config = config_obj.browse(1)

            # Create Party
            company = request.nereid_website.company.id

            country_ids = [False]
            if not contact_form.get('country', None) and geoip:
                country_code = geoip.country_code_by_addr(request.remote_addr)
                if country_code:
                    country_ids = country_obj.search(
                        [('code', '=', country_code)], limit=1
                    )
            party_id = party_obj.create({
                'name': contact_form.get('company') or \
                    contact_form['name'],
                'addresses': [
                    ('create', {
                        'name': contact_form['name'],
                        'country': country_ids[0],
                        })],
                })
            party = party_obj.browse(party_id)

            if contact_form.get('website'):
                # Create website as contact mech
                contact_mech_id = contact_mech_obj.create({
                        'type': 'website',
                        'party': party.id,
                        'website': contact_form['website'],
                    })

            if contact_form.get('phone'):
                # Create phone as contact mech and assign as phone
                contact_mech_id = contact_mech_obj.create({
                        'type': 'phone',
                        'party': party.id,
                        'other_value': contact_form['phone'],
                    })
                address_obj.write(party.addresses[0].id,
                    {'phone': contact_form['phone']})

            # Create email as contact mech and assign as email
            contact_mech_id = contact_mech_obj.create({
                    'type': 'email',
                    'party': party.id,
                    'email': contact_form['email'],
                })
            address_obj.write(party.addresses[0].id,
                {'email': contact_form['email']})

            # Create sale opportunity
            employee = request.nereid_user.employee.id \
                if request.nereid_user.employee else config.website_employee.id
            lead_id = self.create({
                    'party': party_id,
                    'company': company,
                    'employee': employee,
                    'address': party.addresses[0].id,
                    'description': 'New lead from website',
                    'comment': contact_form['comment'],
                    'ip_address': request.remote_addr
                })

            return redirect(request.args.get('next',
                url_for('sale.opportunity.admin_lead', id=lead_id)))
        return render_template('crm/sale_form.jinja')

    def new_opportunity_thanks(self):
        "A thanks template rendered"
        return render_template('crm/thanks.jinja')

    @login_required
    @permissions_required(['sales.admin'])
    def sales_home(self):
        """
        Shows a home page for the sale opportunities
        """
        return render_template('crm/home.jinja')

    @login_required
    @permissions_required(['sales.admin'])
    def all_leads(self, page=1):
        """
        All leads captured
        """
        filter_domain = []

        company = request.args.get('company', None)
        if company:
            filter_domain.append(('party.name', 'ilike', '%%%s%%' % company))

        name = request.args.get('name', None)
        if name:
            filter_domain.append(
                ('address.name', 'ilike', '%%%s%%' % name)
            )

        email = request.args.get('email', None)
        if email:
            filter_domain.append(
                ('address.email', 'ilike', '%%%s%%' % email)
            )

        state = request.args.get('state', None)
        if state:
            filter_domain.append(
                ('state', '=', '%s' % state)
            )

        leads = Pagination(self, filter_domain, page, 10)
        return render_template(
            'crm/leads.jinja', leads=leads
        )

    @login_required
    @permissions_required(['sales.admin'])
    def admin_lead(self, id):
        """
        Lead
        """
        lead = self.browse(id)
        return render_template(
            'crm/admin-lead.jinja', lead=lead
        )

    @login_required
    @permissions_required(['sales.admin'])
    def add_review(self):
        """Add a review for the lead
        """
        review_obj = Pool().get('nereid.review')
        lead_id = request.form.get('lead', type=int)

        lead = self.browse(lead_id)

        review_obj.create({
            'lead': lead.id,
            'title': request.form.get('title'),
            'comment': request.form.get('comment'),
            'nereid_user': request.nereid_user.id,
            'party': lead.party.id,
        })
        if request.is_xhr:
            return jsonify({
                'success': True,
                'message': 'The review has been added.'
            })
        return redirect(request.referrer + '#review')

SaleOpportunity()


class Company(ModelSQL, ModelView):
    "Company"
    _name = 'company.company'

    sales_team = fields.Many2Many(
        'company.company-company.employee', 'company', 'employee', 'Sales Team'
    )

Company()


class CompanySalesTeam(ModelSQL):
    "Sales Team"
    _name = 'company.company-company.employee'
    _table = 'company_sales_team_rel'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', ondelete='CASCADE',
        required=True, select=True
    )
    employee = fields.Many2One('company.employee', 'Employee',
        ondelete='CASCADE', required=True, select=True,
        domain=[
            ('company', '=', Eval('company')),
        ],
        depends=['company']
    )

CompanySalesTeam()


class NereidReview(ModelSQL, ModelView):
    """
    Nereid Review
    """
    _name = "nereid.review"

    lead = fields.Many2One(
        'sale.opportunity', 'Sale Opportunity Lead'
    )

NereidReview()

