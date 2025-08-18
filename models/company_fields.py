from odoo import models, fields, api


class CostPool(models.Model):
    _inherit = 'cost.pool'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)


class CostDriver(models.Model):
    _inherit = 'cost.driver'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)


class ClientCostAllocation(models.Model):
    _inherit = 'client.cost.allocation'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)


class ServiceCategory(models.Model):
    _inherit = 'service.category'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)


class ServiceCatalog(models.Model):
    _inherit = 'service.catalog'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)


class ServiceType(models.Model):
    _inherit = 'service.type'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)


class ClientService(models.Model):
    _inherit = 'client.service'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)


class ClientServiceSubscription(models.Model):
    _inherit = 'client.service.subscription'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)