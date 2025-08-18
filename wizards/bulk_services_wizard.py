from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BulkServicesWizard(models.TransientModel):
    _name = 'bulk.services.wizard'
    _description = 'Bulk Add Services to Clients'

    # Target client(s)
    client_ids = fields.Many2many('res.partner', string='Clients',
                                  domain=[('is_company', '=', True)], required=True)

    # Services to add
    service_line_ids = fields.One2many('bulk.services.wizard.line', 'wizard_id', string='Services to Add')

    # Quick add options
    add_template = fields.Selection([
        ('workstations', 'Workstations Package'),
        ('basic_office', 'Basic Office Package'),
        ('server_room', 'Server Room Package'),
        ('network_infrastructure', 'Network Infrastructure'),
        ('custom', 'Custom Selection')
    ], string='Service Template', default='custom')

    # Workstation template fields
    workstation_count = fields.Integer(string='Number of Workstations', default=10)
    user_count = fields.Integer(string='Number of Users', default=10)
    printer_count = fields.Integer(string='Number of Printers', default=2)

    @api.onchange('add_template')
    def _onchange_add_template(self):
        """Auto-populate services based on template"""
        if self.add_template and self.add_template != 'custom':
            self.service_line_ids = [(5, 0, 0)]  # Clear existing lines

            if self.add_template == 'workstations':
                self._add_workstation_template()
            elif self.add_template == 'basic_office':
                self._add_basic_office_template()
            elif self.add_template == 'server_room':
                self._add_server_room_template()
            elif self.add_template == 'network_infrastructure':
                self._add_network_template()

    def _add_workstation_template(self):
        """Add workstation package"""
        # Find service types
        workstation_service = self.env['service.type'].search([
            '|', ('name', 'ilike', 'workstation'), ('name', 'ilike', 'desktop')
        ], limit=1)

        user_service = self.env['service.type'].search([
            ('name', 'ilike', 'user')
        ], limit=1)

        printer_service = self.env['service.type'].search([
            ('name', 'ilike', 'printer')
        ], limit=1)

        lines = []
        if workstation_service:
            lines.append((0, 0, {
                'service_type_id': workstation_service.id,
                'quantity': self.workstation_count,
                'auto_assign': True
            }))

        if user_service:
            lines.append((0, 0, {
                'service_type_id': user_service.id,
                'quantity': self.user_count,
                'auto_assign': True
            }))

        if printer_service:
            lines.append((0, 0, {
                'service_type_id': printer_service.id,
                'quantity': self.printer_count,
                'auto_assign': True
            }))

        self.service_line_ids = lines

    def _add_basic_office_template(self):
        """Add basic office package"""
        service_names = ['workstation', 'printer', 'user', 'network switch']
        lines = []

        for name in service_names:
            service = self.env['service.type'].search([
                ('name', 'ilike', name)
            ], limit=1)

            if service:
                quantity = 1
                if 'workstation' in name.lower() or 'user' in name.lower():
                    quantity = 5
                elif 'printer' in name.lower():
                    quantity = 1

                lines.append((0, 0, {
                    'service_type_id': service.id,
                    'quantity': quantity,
                    'auto_assign': True
                }))

        self.service_line_ids = lines

    def _add_server_room_template(self):
        """Add server room package"""
        service_names = ['server', 'network switch', 'ups', 'monitoring']
        lines = []

        for name in service_names:
            service = self.env['service.type'].search([
                ('name', 'ilike', name)
            ], limit=1)

            if service:
                lines.append((0, 0, {
                    'service_type_id': service.id,
                    'quantity': 1,
                    'auto_assign': True
                }))

        self.service_line_ids = lines

    def _add_network_template(self):
        """Add network infrastructure"""
        service_names = ['router', 'switch', 'access point', 'firewall']
        lines = []

        for name in service_names:
            service = self.env['service.type'].search([
                ('name', 'ilike', name)
            ], limit=1)

            if service:
                lines.append((0, 0, {
                    'service_type_id': service.id,
                    'quantity': 1,
                    'auto_assign': True
                }))

        self.service_line_ids = lines

    def action_create_services(self):
        """Create services for all selected clients"""
        if not self.service_line_ids:
            raise ValidationError(_("Please add at least one service to create."))

        created_services = []

        for client in self.client_ids:
            for line in self.service_line_ids:
                # Check if service already exists for this client
                existing = self.env['client.service'].search([
                    ('client_id', '=', client.id),
                    ('service_type_id', '=', line.service_type_id.id)
                ])

                if existing and not line.force_create:
                    # Update quantity if service exists
                    existing.quantity += line.quantity
                else:
                    # Create new service
                    service_vals = {
                        'client_id': client.id,
                        'service_type_id': line.service_type_id.id,
                        'name': line.name or line.service_type_id.name,
                        'quantity': line.quantity,
                        'location': line.location,
                        'status': 'active'
                    }

                    # Auto-assign responsible team if requested
                    if line.auto_assign and line.service_type_id.auto_assign_responsible:
                        if line.service_type_id.primary_responsible_id:
                            service_vals['responsible_employee_id'] = line.service_type_id.primary_responsible_id.id
                        if line.service_type_id.default_responsible_ids:
                            service_vals['support_team_ids'] = [
                                (6, 0, line.service_type_id.default_responsible_ids.ids)]

                    service = self.env['client.service'].create(service_vals)
                    created_services.append(service)

        # Show created services
        if created_services:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Created Services'),
                'res_model': 'client.service',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', [s.id for s in created_services])],
                'context': {'search_default_group_client': 1}
            }
        else:
            return {'type': 'ir.actions.act_window_close'}


class BulkServicesWizardLine(models.TransientModel):
    _name = 'bulk.services.wizard.line'
    _description = 'Bulk Services Wizard Line'

    wizard_id = fields.Many2one('bulk.services.wizard', string='Wizard', ondelete='cascade')

    service_type_id = fields.Many2one('service.type', string='Service Type', required=True)
    name = fields.Char(string='Custom Name', help='Leave empty to use service type name')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    location = fields.Char(string='Location')

    auto_assign = fields.Boolean(string='Auto Assign Team', default=True)
    force_create = fields.Boolean(string='Force Create New',
                                  help='Create new service even if already exists for client')

    @api.onchange('service_type_id')
    def _onchange_service_type_id(self):
        if self.service_type_id:
            self.name = self.service_type_id.name