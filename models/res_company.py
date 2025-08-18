from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Dія.City status for the company
    is_diia_city_resident = fields.Boolean(
        string='Dія.City Resident Company',
        default=False,
        help='Company operates under Dія.City special tax regime: 5% income + 5% military + 22% ESV from minimum wage'
    )

    # Company business type for cost allocation
    business_type = fields.Selection([
        ('it', 'IT Services'),
        ('legal', 'Legal Services'),
        ('accounting', 'Accounting Services'),
        ('financial', 'Financial Consulting'),
        ('construction', 'Construction Services'),
        ('expertise', 'Technical Expertise'),
        ('production', 'Production Company'),
        ('other', 'Other')
    ], string='Business Type', default='other',
        help='Type of business for cost allocation templates')