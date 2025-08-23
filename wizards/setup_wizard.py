from odoo import models, fields, api, _


class ServiceCostingSetupWizard(models.TransientModel):
    _name = 'service.costing.setup.wizard'
    _description = 'Service Costing Setup Wizard'

    company_type = fields.Selection([
        ('it', _('IT Services')),
        ('legal', _('Legal Services')),
        ('accounting', _('Accounting Services')),
        ('financial', _('Financial Consulting')),
        ('construction', _('Construction Services')),
        ('expertise', _('Technical Expertise')),
        ('consulting', _('General Consulting')),
        ('custom', _('Custom Setup'))
    ], string='Business Type', required=True, default='it')

    setup_employees = fields.Boolean(string='Setup Employee Costs', default=True)
    setup_pools = fields.Boolean(string='Setup Cost Pools', default=True)
    setup_drivers = fields.Boolean(string='Setup Cost Drivers', default=True)
    setup_services = fields.Boolean(string='Setup Service Catalog', default=True)

    def action_setup_company(self):
        """Setup the company based on selected type"""
        self.ensure_one()

        if self.setup_employees:
            self._setup_employees()

        if self.setup_pools:
            self._setup_cost_pools()

        if self.setup_drivers:
            self._setup_cost_drivers()

        if self.setup_services:
            self._setup_service_categories()

        # Show success message and redirect to cost pools
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Setup Complete!'),
                'message': _('Basic configuration for %s created. You can edit cost pools and drivers in Configuration menu.') % dict(self._fields["company_type"].selection)[self.company_type],
                'type': 'success',
                'sticky': True,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Cost Pools'),
                    'res_model': 'cost.pool',
                    'view_mode': 'tree,form',
                }
            }
        }

    def _setup_employees(self):
        """Create employee cost records for all employees"""
        employees = self.env['hr.employee'].search([])
        for employee in employees:
            existing = self.env['cost.employee'].search([('employee_id', '=', employee.id)])
            if not existing:
                self.env['cost.employee'].create({
                    'employee_id': employee.id,
                    'monthly_hours': 168.0,
                })

    def _setup_cost_pools(self):
        """Setup cost pools based on company type - EDITABLE"""
        pools_data = self._get_pools_data()

        for pool_data in pools_data:
            existing = self.env['cost.pool'].search([('name', '=', pool_data['name'])])
            if not existing:
                # Create pool with description that it can be edited
                pool_data['description'] = f"{pool_data.get('description', '')} ({_('Created by wizard - can be edited')})"
                self.env['cost.pool'].create(pool_data)

    def _setup_cost_drivers(self):
        """Setup cost drivers based on company type - EDITABLE"""
        drivers_data = self._get_drivers_data()

        # Get created pools to link drivers
        pools = self.env['cost.pool'].search([])
        pool_mapping = {pool.name: pool.id for pool in pools}

        for driver_data in drivers_data:
            existing = self.env['cost.driver'].search([('name', '=', driver_data['name'])])
            if not existing:
                # Try to find matching pool
                pool_name = self._get_driver_pool_mapping().get(driver_data['name'])
                if pool_name and pool_name in pool_mapping:
                    driver_data['pool_id'] = pool_mapping[pool_name]
                    driver_data['description'] = f"{driver_data.get('description', '')} ({_('Created by wizard - can be edited')})"
                    self.env['cost.driver'].create(driver_data)

    def _setup_service_categories(self):
        """Activate relevant service categories based on company type"""
        # Get categories to activate
        category_refs = self._get_category_refs()

        # Deactivate all categories first
        all_categories = self.env['service.category'].search([])
        all_categories.write({'active': False})

        # Activate selected categories
        for ref in category_refs:
            try:
                category = self.env.ref(f'cost_allocation.{ref}')
                category.active = True
            except:
                pass  # Category doesn't exist

    def _get_pools_data(self):
        """Get cost pools data based on company type - TEMPLATE DATA"""
        pools_mapping = {
            'it': [
                {'name': _('Hardware Support'), 'description': _('Computer equipment and hardware support'), 'pool_type': 'indirect'},
                {'name': _('Software Support'), 'description': _('Software and SaaS support'), 'pool_type': 'indirect'},
                {'name': _('Infrastructure'), 'description': _('Network and server infrastructure'), 'pool_type': 'indirect'},
                {'name': _('User Support'), 'description': _('End user technical support'), 'pool_type': 'indirect'},
                {'name': _('Administration'), 'description': _('Administrative and management costs'), 'pool_type': 'admin'},
            ],
            'legal': [
                {'name': _('Corporate Law'), 'description': _('Corporate legal services'), 'pool_type': 'indirect'},
                {'name': _('Contract Law'), 'description': _('Contract drafting and review'), 'pool_type': 'indirect'},
                {'name': _('Litigation'), 'description': _('Court proceedings and disputes'), 'pool_type': 'indirect'},
                {'name': _('Compliance'), 'description': _('Legal compliance'), 'pool_type': 'indirect'},
                {'name': _('Administration'), 'description': _('Administrative and management costs'), 'pool_type': 'admin'},
            ],
            'accounting': [
                {'name': _('Bookkeeping'), 'description': _('Daily accounting and bookkeeping'), 'pool_type': 'indirect'},
                {'name': _('Tax Services'), 'description': _('Tax preparation and planning'), 'pool_type': 'indirect'},
                {'name': _('Audit'), 'description': _('Audit and assurance services'), 'pool_type': 'indirect'},
                {'name': _('Consulting'), 'description': _('Financial consulting services'), 'pool_type': 'indirect'},
                {'name': _('Administration'), 'description': _('Administrative and management costs'), 'pool_type': 'admin'},
            ],
        }

        return pools_mapping.get(self.company_type, [
            {'name': _('Main Services'), 'description': _('Main operational services'), 'pool_type': 'indirect'},
            {'name': _('Administration'), 'description': _('Administrative costs'), 'pool_type': 'admin'},
        ])

    def _get_drivers_data(self):
        """Get cost drivers data based on company type"""
        drivers_mapping = {
            'it': [
                {'name': _('Workstations'), 'code': 'WORKSTATIONS', 'driver_category': 'Hardware', 'unit_name': _('PC')},
                {'name': _('Users'), 'code': 'USERS', 'driver_category': 'Users', 'unit_name': _('User')},
                {'name': _('Servers'), 'code': 'SERVERS', 'driver_category': 'Infrastructure', 'unit_name': _('Server')},
                {'name': _('Applications'), 'code': 'APPS', 'driver_category': 'Software', 'unit_name': _('Application')},
            ],
            'legal': [
                {'name': _('Cases'), 'code': 'CASES', 'driver_category': 'Legal', 'unit_name': _('Case')},
                {'name': _('Contracts'), 'code': 'CONTRACTS', 'driver_category': 'Legal', 'unit_name': _('Contract')},
                {'name': _('Work Hours'), 'code': 'HOURS', 'driver_category': 'Time', 'unit_name': _('Hour')},
                {'name': _('Documents'), 'code': 'DOCS', 'driver_category': 'Legal', 'unit_name': _('Document')},
            ],
            'accounting': [
                {'name': _('Transactions'), 'code': 'TRANSACTIONS', 'driver_category': 'Accounting', 'unit_name': _('Transaction')},
                {'name': _('Accounts'), 'code': 'ACCOUNTS', 'driver_category': 'Accounting', 'unit_name': _('Account')},
                {'name': _('Reports'), 'code': 'REPORTS', 'driver_category': 'Accounting', 'unit_name': _('Report')},
                {'name': _('Legal Entities'), 'code': 'ENTITIES', 'driver_category': 'Accounting', 'unit_name': _('Entity')},
            ],
        }

        return drivers_mapping.get(self.company_type, [
            {'name': _('Main Driver'), 'code': 'MAIN', 'driver_category': 'General', 'unit_name': _('Unit')},
        ])

    def _get_driver_pool_mapping(self):
        """Map drivers to pools for linking"""
        mapping = {
            _('Workstations'): _('Hardware Support'),
            _('Users'): _('User Support'),
            _('Servers'): _('Infrastructure'),
            _('Applications'): _('Software Support'),
            _('Cases'): _('Corporate Law'),
            _('Contracts'): _('Contract Law'),
            _('Work Hours'): _('Litigation'),
            _('Documents'): _('Compliance'),
            _('Transactions'): _('Bookkeeping'),
            _('Accounts'): _('Bookkeeping'),
            _('Reports'): _('Audit'),
            _('Legal Entities'): _('Consulting'),
        }
        return mapping

    def _get_category_refs(self):
        """Get service category references to activate"""
        category_mapping = {
            'it': ['category_it_hardware', 'category_it_software', 'category_it_infrastructure', 'category_it_support'],
            'legal': ['category_legal_corporate', 'category_legal_contracts', 'category_legal_litigation'],
            'accounting': ['category_accounting_bookkeeping', 'category_accounting_tax', 'category_accounting_audit'],
            'financial': ['category_financial_consulting', 'category_financial_analysis'],
            'construction': ['category_construction_design', 'category_construction_execution'],
            'expertise': ['category_expertise_technical'],
        }

        return category_mapping.get(self.company_type, [])