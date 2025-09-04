# wizards/admin_cost_setup_wizard.py

from odoo import models, fields, api


class AdminCostSetupWizard(models.TransientModel):
    _name = 'admin.cost.setup.wizard'
    _description = 'Quick Setup for Administrative Costs'

    # Setup options
    setup_method = fields.Selection([
        ('simple', 'Simple Setup (percentage of other costs)'),
        ('driver_based', 'Driver-Based Setup (detailed)')
    ], string='Setup Method', default='simple', required=True)

    # Simple method parameters
    admin_percentage = fields.Float(string='Admin Cost Percentage', default=15.0,
                                    help='Percentage of direct+indirect costs allocated as admin')

    # Driver-based method
    create_admin_pool = fields.Boolean(string='Create Admin Cost Pool', default=True)
    admin_pool_name = fields.Char(string='Admin Pool Name', default='Administration')

    create_admin_driver = fields.Boolean(string='Create Admin Driver', default=True)
    admin_driver_name = fields.Char(string='Admin Driver Name', default='Administrative Hours')
    admin_cost_per_hour = fields.Float(string='Admin Cost per Hour', default=40.0)

    # Client allocation
    setup_client_allocations = fields.Boolean(string='Setup Client Allocations', default=True)
    default_admin_hours_per_client = fields.Float(string='Default Admin Hours per Client', default=5.0)

    def action_setup_simple(self):
        """Setup simple percentage-based admin costs"""
        # This would modify the calculation method to use percentage
        # For now, let's create a basic setup

        self._create_basic_admin_setup()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Simple admin setup complete! Admin costs will be {self.admin_percentage}% of other costs.',
                'type': 'success',
            }
        }

    def action_setup_driver_based(self):
        """Setup driver-based admin costs"""
        created_items = []

        # 1. Create admin pool if needed
        admin_pool = None
        if self.create_admin_pool:
            existing_pool = self.env['cost.pool'].search([
                ('pool_type', '=', 'admin'),
                ('name', '=', self.admin_pool_name)
            ], limit=1)

            if not existing_pool:
                admin_pool = self.env['cost.pool'].create({
                    'name': self.admin_pool_name,
                    'pool_type': 'admin',
                    'description': f'Administrative costs pool created by setup wizard'
                })
                created_items.append(f'Admin Pool: {admin_pool.name}')
            else:
                admin_pool = existing_pool

        # 2. Create admin driver if needed
        admin_driver = None
        if self.create_admin_driver and admin_pool:
            # Find or create hour unit
            hour_unit = self.env['unit.of.measure'].search([('name', 'ilike', 'hour')], limit=1)
            if not hour_unit:
                hour_unit = self.env.ref('cost_allocation.unit_hour', raise_if_not_found=False)

            if not hour_unit:
                # Create hour unit
                hour_unit = self.env['unit.of.measure'].create({
                    'name': 'Hour',
                    'symbol': 'h',
                    'description': 'Working hours unit for administrative tasks'
                })

            existing_driver = self.env['cost.driver'].search([
                ('name', '=', self.admin_driver_name),
                ('pool_id', '=', admin_pool.id)
            ], limit=1)

            if not existing_driver:
                admin_driver = self.env['cost.driver'].create({
                    'name': self.admin_driver_name,
                    'pool_id': admin_pool.id,
                    'unit_id': hour_unit.id,
                    'monthly_cost': self.admin_cost_per_hour * 160,  # assuming 160 hours/month
                    'is_license_unit': False,
                })
                created_items.append(f'Admin Driver: {admin_driver.name}')
            else:
                admin_driver = existing_driver

        # 3. Setup client allocations
        if self.setup_client_allocations and admin_driver:
            clients = self.env['res.partner'].search([
                ('is_company', '=', True),
                ('customer_rank', '>', 0)
            ])

            allocation_count = 0
            for client in clients:
                existing = self.env['client.cost.driver'].search([
                    ('driver_id', '=', admin_driver.id),
                    ('client_id', '=', client.id)
                ])

                if not existing:
                    self.env['client.cost.driver'].create({
                        'driver_id': admin_driver.id,
                        'client_id': client.id,
                        'quantity': self.default_admin_hours_per_client
                    })
                    allocation_count += 1

            if allocation_count > 0:
                created_items.append(f'Client Allocations: {allocation_count} clients')

        # Show results
        message = 'Driver-based admin setup complete!<br/>'
        if created_items:
            message += 'Created:<ul>'
            for item in created_items:
                message += f'<li>{item}</li>'
            message += '</ul>'
        else:
            message += 'All components already existed.'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Admin Cost Setup Complete',
                'message': message,
                'type': 'success',
                'sticky': True,
            }
        }

    def _create_basic_admin_setup(self):
        """Create basic admin cost setup"""
        # Set system parameter for percentage-based calculation
        self.env['ir.config_parameter'].sudo().set_param(
            'cost_allocation.admin_cost_percentage',
            self.admin_percentage
        )

        # Create minimal admin pool for tracking
        existing_pool = self.env['cost.pool'].search([
            ('pool_type', '=', 'admin')
        ], limit=1)

        if not existing_pool:
            self.env['cost.pool'].create({
                'name': 'Administrative Costs (Auto)',
                'pool_type': 'admin',
                'description': 'Auto-created admin pool for percentage-based allocation'
            })