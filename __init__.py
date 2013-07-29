# -*- coding: utf-8 -*-
"""
    __init__

    Nereid Frontend of Sale Opportunity as CRM

    :copyright: (c) 2012-2013 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.pool import Pool

from opportunity import *


def register():
    """
    This method will register trytond module nereid_crm
    """
    Pool.register(
        NereidUser,
        Configuration,
        NereidReview,
        CompanySalesTeam,
        SaleOpportunity,
        Company,
        module='nereid_crm', type_='model',
    )
