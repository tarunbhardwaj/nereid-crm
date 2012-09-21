#This file is part of Nereid.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Nereid CRM',
    'version': '2.4.0.1dev',
    'author': 'Openlabs Technologies & Consulting (P) Ltd.',
    'email': 'info@openlabs.co.in',
    'website': 'http://www.openlabs.co.in/',
    'description': '''
        Extend Sale opportunity to a basic CRM with nereid
     ''',
    'depends': [
        "nereid",
        "sale_opportunity",
        ],
    'xml': [
        'urls.xml',
        'opportunity.xml',
        ],
    'translation': [
        ],
}
