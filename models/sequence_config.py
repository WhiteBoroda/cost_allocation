from odoo import models, fields, api


class SequenceConfig(models.TransientModel):
    _name = 'sequence.config'
    _description = 'Sequence Configuration'

    # Service Category
    service_category_prefix = fields.Char(
        string='Service Category Prefix',
        default='CAT-',
        help='Prefix for service category codes'
    )

    # Service Catalog
    service_catalog_prefix = fields.Char(
        string='Service Catalog Prefix',
        default='SRV-',
        help='Prefix for service catalog codes'
    )

    # Service Type
    service_type_prefix = fields.Char(
        string='Service Type Prefix',
        default='ST-',
        help='Prefix for service type codes'
    )

    # Client Service
    client_service_prefix = fields.Char(
        string='Client Service Prefix',
        default='CS-',
        help='Prefix for client service codes'
    )

    # Subscription
    subscription_prefix = fields.Char(
        string='Subscription Prefix',
        default='SUB-',
        help='Prefix for subscription codes'
    )

    # Cost Pool
    cost_pool_prefix = fields.Char(
        string='Cost Pool Prefix',
        default='CP-',
        help='Prefix for cost pool codes'
    )

    # Cost Driver
    cost_driver_prefix = fields.Char(
        string='Cost Driver Prefix',
        default='CD-',
        help='Prefix for cost driver codes'
    )

    # Cost Allocation
    cost_allocation_prefix = fields.Char(
        string='Cost Allocation Prefix',
        default='CA-',
        help='Prefix for cost allocation codes'
    )

    # Employee Cost
    employee_cost_prefix = fields.Char(
        string='Employee Cost Prefix',
        default='EC-',
        help='Prefix for employee cost codes'
    )

    @api.model
    def default_get(self, fields_list):
        """Load current values from system parameters"""
        values = super().default_get(fields_list)

        config_params = self.env['ir.config_parameter'].sudo()

        values.update({
            'service_category_prefix': config_params.get_param('cost_allocation.sequence.service_category.prefix',
                                                               'CAT-'),
            'service_catalog_prefix': config_params.get_param('cost_allocation.sequence.service_catalog.prefix',
                                                              'SRV-'),
            'service_type_prefix': config_params.get_param('cost_allocation.sequence.service_type.prefix', 'ST-'),
            'client_service_prefix': config_params.get_param('cost_allocation.sequence.client_service.prefix', 'CS-'),
            'subscription_prefix': config_params.get_param('cost_allocation.sequence.subscription.prefix', 'SUB-'),
            'cost_pool_prefix': config_params.get_param('cost_allocation.sequence.cost_pool.prefix', 'CP-'),
            'cost_driver_prefix': config_params.get_param('cost_allocation.sequence.cost_driver.prefix', 'CD-'),
            'cost_allocation_prefix': config_params.get_param('cost_allocation.sequence.cost_allocation.prefix', 'CA-'),
            'employee_cost_prefix': config_params.get_param('cost_allocation.sequence.employee_cost.prefix', 'EC-'),
        })

        return values

    def action_save_config(self):
        """Save configuration to system parameters and update sequences"""
        self.ensure_one()

        config_params = self.env['ir.config_parameter'].sudo()

        # Save to system parameters
        config_params.set_param('cost_allocation.sequence.service_category.prefix', self.service_category_prefix)
        config_params.set_param('cost_allocation.sequence.service_catalog.prefix', self.service_catalog_prefix)
        config_params.set_param('cost_allocation.sequence.service_type.prefix', self.service_type_prefix)
        config_params.set_param('cost_allocation.sequence.client_service.prefix', self.client_service_prefix)
        config_params.set_param('cost_allocation.sequence.subscription.prefix', self.subscription_prefix)
        config_params.set_param('cost_allocation.sequence.cost_pool.prefix', self.cost_pool_prefix)
        config_params.set_param('cost_allocation.sequence.cost_driver.prefix', self.cost_driver_prefix)
        config_params.set_param('cost_allocation.sequence.cost_allocation.prefix', self.cost_allocation_prefix)
        config_params.set_param('cost_allocation.sequence.employee_cost.prefix', self.employee_cost_prefix)

        # Update actual sequences
        self._update_sequences()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Settings Saved',
                'message': 'Sequence prefixes have been updated successfully.',
                'sticky': False,
                'type': 'success'
            }
        }

    def _update_sequences(self):
        """Update sequence prefixes"""
        sequence_mappings = {
            'service.category.code': self.service_category_prefix,
            'service.catalog.code': self.service_catalog_prefix,
            'service.type.code': self.service_type_prefix,
            'client.service.code': self.client_service_prefix,
            'client.service.subscription.code': self.subscription_prefix,
            'cost.pool.code': self.cost_pool_prefix,
            'cost.driver.code': self.cost_driver_prefix,
            'client.cost.allocation.code': self.cost_allocation_prefix,
            'cost.employee.code': self.employee_cost_prefix,
        }

        for sequence_code, prefix in sequence_mappings.items():
            sequence = self.env['ir.sequence'].search([('code', '=', sequence_code)], limit=1)
            if sequence:
                sequence.write({'prefix': prefix})

    def action_reset_defaults(self):
        """Reset to default prefixes"""
        self.write({
            'service_category_prefix': 'CAT-',
            'service_catalog_prefix': 'SRV-',
            'service_type_prefix': 'ST-',
            'client_service_prefix': 'CS-',
            'subscription_prefix': 'SUB-',
            'cost_pool_prefix': 'CP-',
            'cost_driver_prefix': 'CD-',
            'cost_allocation_prefix': 'CA-',
            'employee_cost_prefix': 'EC-',
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reset to Defaults',
                'message': 'All prefixes have been reset to default values.',
                'sticky': False,
                'type': 'info'
            }
        }


class SequenceHelper(models.AbstractModel):
    """Helper mixin for automatic code generation"""
    _name = 'sequence.helper'
    _description = 'Sequence Helper Mixin'

    @api.model
    def _generate_code(self, sequence_code):
        """Generate next code from sequence"""
        return self.env['ir.sequence'].next_by_code(sequence_code) or 'NEW'

    @api.model
    def _get_sequence_prefix(self, param_key, default_prefix):
        """Get sequence prefix from system parameters"""
        return self.env['ir.config_parameter'].sudo().get_param(param_key, default_prefix)