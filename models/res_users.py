from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Service statistics
    service_count = fields.Integer(string='Active Services', compute='_compute_service_stats', store=True)
    subscription_count = fields.Integer(string='Active Subscriptions', compute='_compute_service_stats', store=True)

    # Cost driver quantities
    workstation_count = fields.Integer(string='Workstations', default=0)
    user_count = fields.Integer(string='User Count', default=0)  # ИСПРАВЛЕНО: уникальный label
    server_count = fields.Integer(string='Servers', default=0)
    phone_count = fields.Integer(string='IP Phones', default=0)
    printer_count = fields.Integer(string='Printers', default=0)

    # Relations
    client_service_ids = fields.One2many('client.service', 'client_id', string='Services')
    subscription_ids = fields.One2many('client.service.subscription', 'client_id', string='User Subscriptions')  # ИСПРАВЛЕНО: уникальный label

    @api.depends('client_service_ids.status', 'subscription_ids.state')
    def _compute_service_stats(self):
        for user in self:
            user.service_count = len(user.client_service_ids.filtered(lambda s: s.status == 'active'))
            user.subscription_count = len(user.subscription_ids.filtered(lambda s: s.state == 'active'))
