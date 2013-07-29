# -*- coding: utf-8 -*-
"""
    opportunnity

    Mini CRM based on Nereid and Sale Opprotunity

    :copyright: (c) 2012 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
from decimal import Decimal
import logging
from wtforms import (Form, IntegerField, TextField, SelectField, TextAreaField, 
    validators)
from wtfrecaptcha.fields import RecaptchaField

from nereid import (request, abort, render_template, login_required, url_for,
    redirect, flash, jsonify, permissions_required, render_email)
from nereid.contrib.pagination import Pagination
from trytond.model import ModelView, ModelSQL, ModelSingleton, Workflow, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.config import CONFIG
from trytond.tools import get_smtp_server

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


class ContactUsForm(Form):
    "Simple Contact Us form"
    name = TextField('Name', [validators.Required(),])
    company = TextField('Company')
    country = SelectField('Country', [validators.Required(),], coerce=int)
    email = TextField('e-mail', [validators.Required(), validators.Email()])
    if 're_captcha_public' in CONFIG.options:
        captcha = RecaptchaField(
            public_key=CONFIG.options['re_captcha_public'],
            private_key=CONFIG.options['re_captcha_private'], secure=True)
    website = TextField('Website')
    phone = TextField('Phone')
    comment = TextAreaField('Comment', [validators.Required(),])


class SaleOpportunity(Workflow, ModelSQL, ModelView):
    "Sale Opportunity"
    _name = "sale.opportunity"

    ip_address = fields.Char('IP Address')
    reviews = fields.One2Many(
        'nereid.review',
        'lead', 'Reviews'
    )
    detected_country = fields.Char('Detected Country')

    contactus_form = ContactUsForm

    def new_opportunity(self):
        """Create a new sale opportunity
        """
        country_obj = Pool().get('country.country')

        if 're_captcha_public' in CONFIG.options:
            contact_form = self.contactus_form(
                request.form,
                captcha={'ip_address': request.remote_addr}
            )
        else:
            contact_form = self.contactus_form(request.form)

        country_ids = country_obj.search([])
        countries = country_obj.browse(country_ids)

        contact_form.country.choices = [
            (c.id, c.name) for c in countries
        ]

        if request.method == 'POST' and contact_form.validate():
            address_obj = Pool().get('party.address')
            contact_mech_obj = Pool().get('party.contact_mechanism')
            party_obj = Pool().get('party.party')
            config_obj = Pool().get('sale.configuration')
            company_obj = Pool().get('company.company')
            country_obj = Pool().get('country.country')

            config = config_obj.browse(1)

            contact_data = contact_form.data

            # Create Party
            company = request.nereid_website.company.id

            if not contact_data.get('country', None) and geoip:
                detected_country = geoip.country_name_by_addr(
                    request.remote_addr
                )
            else:
                detected_country = ''

            party_id = party_obj.create({
                'name': contact_data.get('company') or \
                    contact_data['name'],
                'addresses': [
                    ('create', {
                        'name': contact_data['name'],
                        'country': contact_data['country'],
                        })],
                })
            party = party_obj.browse(party_id)

            if contact_data.get('website'):
                # Create website as contact mech
                contact_mech_id = contact_mech_obj.create({
                        'type': 'website',
                        'party': party.id,
                        'website': contact_data['website'],
                    })

            if contact_data.get('phone'):
                # Create phone as contact mech and assign as phone
                contact_mech_id = contact_mech_obj.create({
                        'type': 'phone',
                        'party': party.id,
                        'other_value': contact_data['phone'],
                    })
                address_obj.write(party.addresses[0].id,
                    {'phone': contact_data['phone']})

            # Create email as contact mech and assign as email
            contact_mech_id = contact_mech_obj.create({
                    'type': 'email',
                    'party': party.id,
                    'email': contact_data['email'],
                })
            address_obj.write(party.addresses[0].id,
                {'email': contact_data['email']})

            # Create sale opportunity
            if request.nereid_user.employee:
                employee = request.nereid_user.employee.id
                description = 'Created by %s' % \
                    request.nereid_user.display_name
            else:
                employee = config.website_employee.id
                description =  'Created from website'
            employee = request.nereid_user.employee.id \
                if request.nereid_user.employee else config.website_employee.id
            lead_id = self.create({
                    'party': party_id,
                    'company': company,
                    'employee': employee,
                    'address': party.addresses[0].id,
                    'description': description,
                    'comment': contact_data['comment'],
                    'ip_address': request.remote_addr,
                    'detected_country': detected_country,
                })
            self.send_notification_mail(lead_id)

            return redirect(request.args.get('next',
                url_for('sale.opportunity.admin_lead', id=lead_id)))
        return render_template('crm/sale_form.jinja', form=contact_form)

    def send_notification_mail(self, lead_id):
        """Send a notification mail to sales department whenever there is query
        for new lead.

        :param lead_id: ID of lead.
        """
        lead = self.browse(lead_id)

        # Prepare the content for email.
        subject = "[Openlabs CRM] New lead created by %s" % (lead.party.name)

        receivers = [member.email for member in lead.company.sales_team
                     if member.email]
        if not receivers:
            return

        message = render_email(
            from_email=CONFIG['smtp_from'],
            to=', '.join(receivers),
            subject=subject,
            text_template='crm/emails/notification_text.jinja',
            lead=lead
        )

        # Send mail.
        server = get_smtp_server()
        server.sendmail(
            CONFIG['smtp_from'], receivers, message.as_string()
        )
        server.quit()

    def new_opportunity_thanks(self):
        "A thanks template rendered"
        return render_template('crm/thanks.jinja')

    @login_required
    @permissions_required(['sales.admin'])
    def revenue_opportunity(self, lead_id):
        """Set the Conversion Probability and estimated revenue amount
        """
        nereid_user_obj = Pool().get('nereid.user')
        lead  = self.browse(lead_id)

        nereid_user_id = nereid_user_obj.search(
            [('employee', '=', lead.employee.id)], limit=1
        )
        if nereid_user_id:
            employee = nereid_user_obj.browse(nereid_user_id[0])
        else:
            employee = None

        if request.method == 'POST':
            self.write(lead.id, {
                'probability': request.form['probability'],
                'amount': Decimal(request.form.get('amount'))
            })
            flash('Lead has been updated.')
            return redirect(url_for(
                'sale.opportunity.admin_lead', id=lead.id) + "#tab-revenue"
            )
        return render_template(
            'crm/admin-lead.jinja', lead=lead, employee=employee,
        )

    @login_required
    @permissions_required(['sales.admin'])
    def sales_home(self):
        """
        Shows a home page for the sale opportunities
        """
        country_obj = Pool().get('country.country')

        country_ids = country_obj.search([])
        countries = country_obj.browse(country_ids)

        counter = {}
        for state in ('lead', 'opportunity', 'converted', 'cancelled', 'lost'):
            counter[state] = self.search([('state', '=', state)], count=True)
        return render_template(
            'crm/home.jinja', counter=counter, countries=countries
        )

    @login_required
    @permissions_required(['sales.admin'])
    def assign_lead(self, lead_id):
        "Change the employee on lead"
        lead = self.browse(lead_id)
        nereid_user_obj = Pool().get('nereid.user')

        new_assignee = nereid_user_obj.browse(int(request.form['user']))

        if lead.employee.id == new_assignee.id:
            flash("Lead already assigned to %s" % new_assignee.name)
            return redirect(request.referrer)

        self.write(lead.id, {
            'employee': new_assignee.employee.id
        })

        flash("Lead assigned to %s" % new_assignee.name)
        return redirect(request.referrer)

    @login_required
    @permissions_required(['sales.admin'])
    def all_leads(self, page=1):
        """
        All leads captured
        """
        country_obj = Pool().get('country.country')

        country_ids = country_obj.search([])
        countries = country_obj.browse(country_ids)

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
            'crm/leads.jinja', leads=leads, countries=countries
        )

    @login_required
    @permissions_required(['sales.admin'])
    def admin_lead(self, id):
        """
        Lead
        """
        nereid_user_obj = Pool().get('nereid.user')
        country_obj = Pool().get('country.country')

        country_ids = country_obj.search([])
        countries = country_obj.browse(country_ids)

        lead = self.browse(id)
        nereid_user_id = nereid_user_obj.search(
            [('employee', '=', lead.employee.id)], limit=1
        )
        if nereid_user_id:
            employee = nereid_user_obj.browse(nereid_user_id[0])
        else:
            employee = None
        return render_template(
            'crm/admin-lead.jinja', lead=lead, employee=employee,
            countries=countries
        )

    @login_required
    @permissions_required(['sales.admin'])
    def add_comment(self):
        """Add a comment for the lead
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
                'message': 'The comment has been added.'
            })
        return redirect(request.referrer + '#tab-comment')

    @login_required
    @permissions_required(['sales.admin'])
    def mark_opportunity(self, lead_id):
        """Convert the lead to opportunity
        """
        self.opportunity([lead_id])
        if request.is_xhr:
            return jsonify({
                'success': True,
                'message': 'Good Work! This lead is an opportunity now.'
            })
        return redirect(request.referrer)

    @login_required
    @permissions_required(['sales.admin'])
    def mark_lost(self, lead_id):
        """Convert the lead to lost
        """
        self.lost([lead_id])
        if request.is_xhr:
            return jsonify({
                'success': True,
                'message': 'The lead is marked as lost.'
            })
        return redirect(request.referrer)

    @login_required
    @permissions_required(['sales.admin'])
    def mark_lead(self, lead_id):
        """Convert the opportunity to lead
        """
        self.lead([lead_id])
        if request.is_xhr:
            return jsonify({
                'success': True,
                'message': 'The lead is marked back to open.'
            })
        return redirect(request.referrer)

    @login_required
    @permissions_required(['sales.admin'])
    def mark_converted(self, lead_id):
        """Convert the opportunity
        """
        self.convert([lead_id])
        if request.is_xhr:
            return jsonify({
                'success': True,
                'message': 'Awesome! The Opportunity is converted.'
            })
        return redirect(request.referrer)

    @login_required
    @permissions_required(['sales.admin'])
    def mark_cancelled(self, lead_id):
        """Convert the lead as cancelled
        """
        self.cancel([lead_id])
        if request.is_xhr:
            return jsonify({
                'success': True,
                'message': 'The lead is cancelled.'
            })
        return redirect(request.referrer)

SaleOpportunity()


class Company(ModelSQL, ModelView):
    "Company"
    _name = 'company.company'

    sales_team = fields.Many2Many(
        'company.company-nereid.user-sales',
        'company', 'nereid_user', 'Sales Team'
    )

Company()


class CompanySalesTeam(ModelSQL):
    "Sales Team"
    _name = 'company.company-nereid.user-sales'
    _table = 'company_nereid_sales_team_rel'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', ondelete='CASCADE',
        required=True, select=True
    )
    nereid_user = fields.Many2One('nereid.user', 'Nereid User',
        ondelete='CASCADE', required=True, select=True,
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

