from odoo import models, fields, api


class ServiceCostingSetupWizard(models.TransientModel):
    _name = 'service.costing.setup.wizard'
    _description = 'Service Costing Setup Wizard'

    company_type = fields.Selection([
        ('it', 'IT Services'),
        ('legal', 'Legal Services'),
        ('accounting', 'Accounting Services'),
        ('financial', 'Financial Consulting'),
        ('construction', 'Construction Services'),
        ('expertise', 'Technical Expertise'),
        ('consulting', 'General Consulting'),
        ('custom', 'Custom Setup')
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

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Setup Complete',
                'message': f'{dict(self._fields["company_type"].selection)[self.company_type]} costing setup completed successfully!',
                'type': 'success',
                'sticky': False,
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
        """Setup cost pools based on company type"""
        pools_data = self._get_pools_data()

        for pool_data in pools_data:
            existing = self.env['cost.pool'].search([('name', '=', pool_data['name'])])
            if not existing:
                self.env['cost.pool'].create(pool_data)

    def _setup_cost_drivers(self):
        """Setup cost drivers based on company type"""
        drivers_data = self._get_drivers_data()

        for driver_data in drivers_data:
            existing = self.env['cost.driver'].search([('name', '=', driver_data['name'])])
            if not existing:
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
        """Get cost pools data based on company type"""
        pools_mapping = {
            'it': [
                {'name': 'Hardware Support', 'description': 'Computer equipment and hardware support'},
                {'name': 'Software Support', 'description': 'Software and SaaS support'},
                {'name': 'Infrastructure', 'description': 'Network and server infrastructure'},
                {'name': 'User Support', 'description': 'End-user technical support'},
                {'name': 'Administration', 'description': 'Administrative and management costs'},
            ],
            'legal': [
                {'name': 'Corporate Law', 'description': 'Corporate legal services'},
                {'name': 'Contract Law', 'description': 'Contract drafting and review'},
                {'name': 'Litigation', 'description': 'Court proceedings and disputes'},
                {'name': 'Compliance', 'description': 'Legal compliance services'},
                {'name': 'Administration', 'description': 'Administrative and management costs'},
            ],
            'accounting': [
                {'name': 'Bookkeeping', 'description': 'Daily bookkeeping and accounting'},
                {'name': 'Tax Services', 'description': 'Tax preparation and planning'},
                {'name': 'Audit', 'description': 'Audit and assurance services'},
                {'name': 'Advisory', 'description': 'Financial advisory services'},
                {'name': 'Administration', 'description': 'Administrative and management costs'},
            ],
            'financial': [
                {'name': 'Planning', 'description': 'Financial planning and strategy'},
                {'name': 'Analysis', 'description': 'Financial analysis and modeling'},
                {'name': 'Investment', 'description': 'Investment advisory services'},
                {'name': 'Risk Management', 'description': 'Risk assessment and management'},
                {'name': 'Administration', 'description': 'Administrative and management costs'},
            ],
            'construction': [
                {'name': 'Design', 'description': 'Architectural and engineering design'},
                {'name': 'Project Management', 'description': 'Construction project management'},
                {'name': 'Execution', 'description': 'Construction and building work'},
                {'name': 'Quality Control', 'description': 'Quality assurance and control'},
                {'name': 'Administration', 'description': 'Administrative and management costs'},
            ],
            'expertise': [
                {'name': 'Technical Assessment', 'description': 'Technical evaluations and assessments'},
                {'name': 'Expert Testimony', 'description': 'Expert witness and testimony'},
                {'name': 'Research', 'description': 'Technical research and analysis'},
                {'name': 'Consulting', 'description': 'Technical consulting services'},
                {'name': 'Administration', 'description': 'Administrative and management costs'},
            ],
        }

        return pools_mapping.get(self.company_type, pools_mapping['consulting'])

    def _get_drivers_data(self):
        """Get cost drivers data based on company type"""
        drivers_mapping = {
            'it': [
                {'name': 'Workstations', 'description': 'Number of workstations'},
                {'name': 'Users', 'description': 'Number of users'},
                {'name': 'Servers', 'description': 'Number of servers'},
                {'name': 'Applications', 'description': 'Number of applications'},
            ],
            'legal': [
                {'name': 'Cases', 'description': 'Number of legal cases'},
                {'name': 'Contracts', 'description': 'Number of contracts'},
                {'name': 'Hours', 'description': 'Legal hours'},
                {'name': 'Documents', 'description': 'Number of documents'},
            ],
            'accounting': [
                {'name': 'Transactions', 'description': 'Number of transactions'},
                {'name': 'Accounts', 'description': 'Number of accounts'},
                {'name': 'Reports', 'description': 'Number of reports'},
                {'name': 'Entities', 'description': 'Number of legal entities'},
            ],
            'financial': [
                {'name': 'Portfolios', 'description': 'Number of portfolios'},
                {'name': 'Assets', 'description': 'Assets under management'},
                {'name': 'Reports', 'description': 'Number of reports'},
                {'name': 'Clients', 'description': 'Number of clients'},
            ],
            'construction': [
                {'name': 'Projects', 'description': 'Number of projects'},
                {'name': 'Square Meters', 'description': 'Construction area'},
                {'name': 'Workers', 'description': 'Number of workers'},
                {'name': 'Equipment', 'description': 'Construction equipment'},
            ],
            'expertise': [
                {'name': 'Assessments', 'description': 'Number of assessments'},
                {'name': 'Reports', 'description': 'Number of expert reports'},
                {'name': 'Hours', 'description': 'Expert hours'},
                {'name': 'Cases', 'description': 'Number of cases'},
            ],
        }

        return drivers_mapping.get(self.company_type, drivers_mapping.get('consulting', []))

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