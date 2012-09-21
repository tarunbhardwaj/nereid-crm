# -*- coding: utf-8 -*-
"""
    opportunnity

    Mini CRM based on Nereid and Sale Opprotunity

    :copyright: (c) 2012 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
from nereid import (request, abort, render_template, login_required, url_for,
    redirect, flash, jsonify)
from trytond.model import ModelView, ModelSQL, ModelSingleton, Workflow, fields
from trytond.pool import Pool
from trytond.pyson import Eval


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

            config = config_obj.browse(1)

            # Create Party
            company = request.nereid_website.company.id
            party_id = party_obj.create({
                'name': contact_form.get('company') or \
                    contact_form['name'],
                'addresses': [
                    ('create', {
                        'name': contact_form['name'],
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
            self.create({
                    'party': party_id,
                    'company': company,
                    'employee': config.website_employee.id,
                    'address': party.addresses[0].id,
                    'description': 'New lead from website',
                    'comment': contact_form['comment'],
                })

            flash('Thank you for contacting us. We will revert soon.')
            return redirect(request.args.get('next',
                url_for('nereid.website.home')))
        return render_template('crm/sale_form.jinja')

    def new_opportunity_thanks(self):
        "A thanks template rendered"
        return render_template('crm/thanks.jinja')

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
