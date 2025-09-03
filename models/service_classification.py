# models/service_classification.py

from odoo import models, fields, api


class ServiceClassification(models.Model):
    _name = 'service.classification'
    _description = 'Service Classification'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    # Icon для UI
    icon = fields.Char(string='Icon Class', default='fa-gear',
                       help='FontAwesome icon class for UI display')

    # Color для группировки в UI
    color = fields.Char(string='Color', default='#1f77b4',
                        help='Color for UI display (hex code)')

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Classification code must be unique!'),
        ('name_unique', 'UNIQUE(name)', 'Classification name must be unique!')
    ]

    @api.model
    def get_selection_list(self):
        """Return list for selection fields - с безопасной обработкой ошибок"""
        try:
            classifications = self.search([('active', '=', True)], order='sequence, name')
            if classifications:
                return [(c.code, c.name) for c in classifications]
        except Exception:
            # Если ORM не работает, пытаемся через SQL
            try:
                self.env.cr.execute(
                    "SELECT code, name FROM service_classification WHERE active = TRUE ORDER BY sequence, name")
                records = self.env.cr.fetchall()
                if records:
                    return records
            except Exception:
                pass

        # Fallback если ничего не работает
        return [
            ('workstation', 'Workstation'),
            ('server', 'Server'),
            ('printer', 'Printer'),
            ('network', 'Network Equipment'),
            ('software', 'Software License'),
            ('user', 'User Support'),
            ('project', 'Project Work'),
            ('consulting', 'Consulting'),
            ('hardware', 'Hardware'),
            ('support', 'Support'),
            ('other', 'Other')
        ]

    @api.model
    def get_classification_mapping(self):
        """Return dict mapping for easy access"""
        classifications = self.search([('active', '=', True)])
        return {c.code: {'name': c.name, 'icon': c.icon, 'color': c.color} for c in classifications}