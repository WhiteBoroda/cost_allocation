# __manifest__.py
{
    'name': 'Розподіл витрат / Service Cost Allocation',
    'version': '17.0.1.6.0',  # ВЕРСИЯ ПОВЫШЕНА после реструктуризации
    'category': 'Accounting',
    'summary': 'ABC Cost Allocation for Service Companies',
    'description': """

                                                                 Activity-Based Costing module for service companies.
                                                                 Allocates direct and indirect costs to clients based on cost drivers.
                                                                 Supports subscription billing and interactive dashboard with KPI analytics.

                                                                 v1.6.0 MAJOR RESTRUCTURING:
                                                                 - Complete file structure reorganization
                                                                 - Separated models into logical files: service_category.py, service_type.py, 
                                                                   service_catalog.py, client_service.py, employee_workload.py
                                                                 - Fixed view duplications and conflicts
                                                                 - Clean architecture with proper model separation
                                                                 - Corrected service status logic (no more "maintenance" status for services)
                                                                 - Standardized unit_of_measure usage across all models

                                                                 v1.4.2 UNIT OF MEASURE STANDARDIZATION:
                                                                 - Replaced scattered unit_name Char fields with standardized Unit of Measure model
                                                                 - Added Unit Categories (Time, Quantity, Storage, Users, Hardware)
                                                                 - Pre-defined units: Hour, User, Workstation, Server, GB, TB, License, etc.
                                                                 - Cost Drivers and Service Types now use Many2one to unit.of.measure
                                                                 - Backward compatibility with legacy unit_of_measure Selection fields
                                                                 - Centralized unit management with proper categorization
                                                                 """,
    'depends': ['base', 'hr', 'hr_timesheet', 'project', 'account', 'sale', 'resource'],
    'data': [
        # Security
        'security/security.xml',
        'security/security_rules.xml',
        'security/ir.model.access.csv',

        # Data files
        'data/sequence_data.xml',
        'data/config_data.xml',
        'data/working_hours_cron.xml',
        'data/unit_measure_data.xml',
        'data/service_data.xml',
        'data/service_catalog_data.xml',
        'data/service_templates_data.xml',
        'data/driver_categories_data.xml',
        'data/cron_data.xml',

        # Base views
        'views/actions.xml',
        'views/unit_measure_views.xml',

        # Core cost allocation views
        'views/billing_views.xml',
        'views/cost_pool_views.xml',
        'views/cost_driver_views.xml',
        'views/employee_cost_views.xml',
        'views/client_allocation_views.xml',

        # Service catalog views (ПРАВИЛЬНЫЙ ПОРЯДОК!)
        'views/service_category_views.xml',      # ServiceCategory
        'views/service_type_views.xml',          # ServiceType
        'views/service_catalog_views.xml',       # ServiceCatalog
        'views/client_service_views.xml',        # ClientService
        'views/employee_workload_views.xml',     # EmployeeWorkload

        # Partner and company views
        'views/res_partner_views.xml',
        'views/company_views.xml',

        # Analysis and reporting
        'views/dashboard_views.xml',
        'views/service_costing_views.xml',
        'views/overhead_costs_views.xml',

        # Configuration views
        'views/sequence_config_views.xml',
        'views/cost_settings_views.xml',
        'views/cost_driver_category_views.xml',

        # Subscription and billing
        'views/subscription_views.xml',
        'views/add_multiple_services_wizard_views.xml',

        # Wizards
        'wizards/setup_wizard_views.xml',
        'wizards/wizard_views.xml',
        'wizards/bulk_services_wizard_views.xml',
        'wizards/client_services_wizard_views.xml',

        # Holding structure (inherit views - должно быть после базовых)
        'views/holding_structure_views.xml',

        # Menu (последний!)
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'cost_allocation/static/src/css/dashboard.css',
            'cost_allocation/static/src/js/dashboard.js',
        ],
    },

    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'AGPL-3',
    'author': 'HD DS LLC',
    'website': 'https://github.com/WhiteBoroda/cost_allocation.git',
    'support': 'y.varaksin@hlibodar.com.ua',
}