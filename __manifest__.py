{
    'name': 'Розподіл витрат / Service Cost Allocation',
    'version': '17.0.1.4.2',
    'category': 'Accounting',
    'summary': 'ABC Cost Allocation for Service Companies',
    'description': """
                           Activity-Based Costing module for service companies.
                           Allocates direct and indirect costs to clients based on cost drivers.
                           Supports subscription billing and interactive dashboard with KPI analytics.

                           v1.4.0 DYNAMIC WORKING DAYS CALCULATION:
                           - Implemented dynamic working days/hours calculation based on company calendars
                           - Removed hardcoded working days per month (22.0) and hours (168.0/176.0)
                           - Added WorkingDaysUtil for calendar-based calculations with caching
                           - Employee costs now use actual working hours for each month
                           - Automatic monthly updates via cron jobs
                           - Configurable utilization rates and calculation methods
                           - Support for employee-specific working calendars
                           - Accounts for weekends, holidays, and company-specific schedules

                           v1.2.1 AUTOMATIC CODE GENERATION + MULTIPLE SERVICES SELECTION:
                           - Added automatic code generation for all entities
                           - Created configurable sequence prefixes (CAT-, SRV-, ST-, CS-, SUB-, CP-, CD-, CA-, EC-, OH-)
                           - Added sequence configuration interface for easy prefix management
                           - All new records get automatic codes: Service Category, Service Catalog, Service Type, Client Service, Subscriptions, Cost Pools, Cost Drivers, Cost Allocations
                           - New: Добавлен множественный выбор сервисов в подписках 
                           - Backward compatible: existing records keep their current codes
                           - Fixed subscription views and currency display issues    

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
        'security/security.xml',
        'data/sequence_data.xml',
        'data/config_data.xml',
        'data/working_hours_cron.xml',
        'data/unit_measure_data.xml',
        'data/service_data.xml',
        'data/service_catalog_data.xml',
        'data/service_templates_data.xml',
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'views/actions.xml',
        'views/unit_measure_views.xml',
        'views/billing_views.xml',
        'views/cost_pool_views.xml',
        'views/cost_driver_views.xml',
        'views/employee_cost_views.xml',
        'views/client_allocation_views.xml',
        'views/service_catalog_views.xml',
        'views/service_management_views.xml',
        'views/res_partner_views.xml',
        'views/company_views.xml',
        'views/dashboard_views.xml',
        'views/sequence_config_views.xml',
        'views/cost_settings_views.xml',
        'views/add_multiple_services_wizard_views.xml',
        'views/subscription_views.xml',
        'views/overhead_costs_views.xml',
        'views/service_costing_views.xml',
        'wizards/setup_wizard_views.xml',
        'wizards/wizard_views.xml',
        'wizards/bulk_services_wizard_views.xml',
        'views/service_views.xml',
        'views/holding_structure_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'cost_allocation/static/src/css/dashboard.css',
            'cost_allocation/static/src/js/dashboard.js',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'AGPL-3',
    'author': 'HD DS LLC',
    'website': 'https://github.com/WhiteBoroda/cost_allocation.git',
    'support': 'y.varaksin@hlibodar.com.ua',
}