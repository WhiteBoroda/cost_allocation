# wizards/add_multiple_services_wizard.py

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AddMultipleServicesWizard(models.TransientModel):
    _name = 'add.multiple.services.wizard'
    _description = 'Add Multiple Services to Subscription'

    subscription_id = fields.Many2one('client.service.subscription', string='Subscription', required=True)
    service_ids = fields.Many2many('service.catalog', string='Services to Add', required=True)

    # Default values for all selected services
    default_quantity = fields.Float(string='Default Quantity', default=1.0)
    default_unit_price = fields.Float(string='Default Unit Price', default=0.0)

    def action_add_services(self):
        """Add selected services to subscription"""
        self.ensure_one()

        if not self.service_ids:
            raise ValidationError(_('Please select at least one service to add.'))

        # Create subscription lines for each selected service
        lines_created = 0
        for service in self.service_ids:
            # Check if service already exists in subscription
            existing_line = self.subscription_id.service_line_ids.filtered(
                lambda l: l.service_id.id == service.id  # ИСПРАВЛЕНО: правильное поле
            )

            if existing_line:
                # Update quantity instead of creating duplicate
                existing_line.quantity += self.default_quantity
            else:
                # Create new subscription line
                # ИСПРАВЛЕНО: используем base_cost вместо sales_price
                unit_price = self.default_unit_price or service.base_cost or 0.0

                vals = {
                    'subscription_id': self.subscription_id.id,
                    'service_id': service.id,  # ИСПРАВЛЕНО: правильное поле
                    'name': service.name,
                    'quantity': self.default_quantity,
                    'unit_price': unit_price,
                }

                self.env['client.service.subscription.line'].create(vals)
                lines_created += 1

        # Show notification
        message = _('Successfully added %d services to subscription.') % lines_created
        if lines_created != len(self.service_ids):
            existing_count = len(self.service_ids) - lines_created
            message += _(' %d services were already in subscription (quantity updated).') % existing_count

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Services Added'),
                'message': message,
                'sticky': False,
                'type': 'success'
            }
        }