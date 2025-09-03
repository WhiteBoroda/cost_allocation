# models/client_service.py

from odoo import models, fields, api


class ClientService(models.Model):
    _name = 'client.service'
    _description = 'Client IT Services and Equipment'
    _rec_name = 'display_name'
    _inherit = ['sequence.helper']

    code = fields.Char(string='Service Code', readonly=True, copy=False)
    client_id = fields.Many2one('res.partner', string='Client',
                                domain=[('is_company', '=', True)], required=True)

    # ОСНОВНЫЕ связи
    service_type_id = fields.Many2one('service.type', string='Service Type', required=True)
    service_catalog_id = fields.Many2one('service.catalog', string='Service Catalog Item',
                                         domain="[('service_type_id', '=', service_type_id)]")

    # Категория берется из service_type
    category_id = fields.Many2one('service.category', string='Category',
                                  related='service_type_id.category_id', store=True, readonly=True)

    # Equipment/Service details
    name = fields.Char(string='Equipment/Service Name', required=True)
    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)

    # Location and technical data
    location = fields.Char(string='Location')
    brand = fields.Char(string='Brand')
    model = fields.Char(string='Model')
    ip_address = fields.Char(string='IP Address')
    mac_address = fields.Char(string='MAC Address')
    serial_number = fields.Char(string='Serial Number')
    inventory_number = fields.Char(string='Inventory Number')

    # Service lifecycle
    installation_date = fields.Date(string='Installation Date')
    warranty_end = fields.Date(string='Warranty End')
    last_maintenance = fields.Date(string='Last Maintenance')
    next_maintenance = fields.Date(string='Next Maintenance')

    # Status - ИСПРАВЛЕНО: логичные статусы для УСЛУГ
    status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated')
    ], string='Status', default='active', required=True)

    # SLA computed from client support level and service type
    effective_response_time = fields.Float(string='Response Time (hours)',
                                           compute='_compute_effective_sla', store=True)
    effective_resolution_time = fields.Float(string='Resolution Time (hours)',
                                             compute='_compute_effective_sla', store=True)
    effective_workload_factor = fields.Float(string='Effective Workload Factor',
                                             compute='_compute_effective_workload', store=True)

    # Responsible team - specific for this service/equipment
    responsible_employee_id = fields.Many2one('hr.employee', string='Primary Responsible')
    support_team_ids = fields.Many2many('hr.employee',
                                        'client_service_employee_rel',
                                        'service_id', 'employee_id',
                                        string='Support Team')

    # Display and computed fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    @api.depends('name', 'client_id', 'service_type_id', 'quantity')
    def _compute_display_name(self):
        for service in self:
            if service.name and service.client_id:
                service.display_name = f"{service.name} ({service.client_id.name})"
            elif service.service_type_id and service.client_id:
                qty_str = f" x{int(service.quantity)}" if service.quantity > 1 else ""
                service.display_name = f"{service.service_type_id.name}{qty_str} ({service.client_id.name})"
            else:
                service.display_name = service.name or 'New Service'

    @api.depends('client_id.support_level', 'service_type_id.response_time', 'service_type_id.resolution_time')
    def _compute_effective_sla(self):
        for service in self:
            if not service.client_id or not service.service_type_id:
                service.effective_response_time = 0
                service.effective_resolution_time = 0
                continue

            # SLA multipliers based on client support level
            sla_multipliers = {
                'basic': 2.0,  # Longer response times for basic support
                'standard': 1.0,  # Standard times
                'premium': 0.5,  # Faster response for premium
                'enterprise': 0.25  # Fastest for enterprise
            }

            multiplier = sla_multipliers.get(service.client_id.support_level, 1.0)
            service.effective_response_time = service.service_type_id.response_time * multiplier
            service.effective_resolution_time = service.service_type_id.resolution_time * multiplier

    @api.depends('client_id.support_level', 'service_type_id.base_workload_factor')
    def _compute_effective_workload(self):
        for service in self:
            if not service.client_id or not service.service_type_id:
                service.effective_workload_factor = 1.0
                continue

            # Workload factors based on client support level
            workload_factors = {
                'basic': 0.8,  # Less intensive support
                'standard': 1.0,  # Standard workload
                'premium': 1.3,  # More intensive support
                'enterprise': 1.8  # Most intensive support
            }

            base_factor = service.service_type_id.base_workload_factor or 1.0
            level_factor = workload_factors.get(service.client_id.support_level, 1.0)
            service.effective_workload_factor = base_factor * level_factor

    @api.onchange('service_type_id')
    def _onchange_service_type(self):
        """Clear service_catalog_id when service_type changes"""
        if self.service_type_id:
            self.service_catalog_id = False
            # Auto-set responsible from service type defaults
            if self.service_type_id.primary_responsible_id:
                self.responsible_employee_id = self.service_type_id.primary_responsible_id

    @api.onchange('service_catalog_id')
    def _onchange_service_catalog(self):
        """Auto-fill details from catalog selection"""
        if self.service_catalog_id:
            catalog = self.service_catalog_id
            if catalog.vendor:
                self.brand = catalog.vendor
            if catalog.model_version:
                self.model = catalog.model_version

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code('client.service.code')
        return super().create(vals_list)

    def action_activate(self):
        """Activate service"""
        for service in self:
            service.status = 'active'

    def action_suspend(self):
        """Suspend service temporarily"""
        for service in self:
            service.status = 'suspended'

    def action_set_inactive(self):
        """Set service inactive"""
        for service in self:
            service.status = 'inactive'

    def action_terminate(self):
        """Terminate service"""
        for service in self:
            service.status = 'terminated'