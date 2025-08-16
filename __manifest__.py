{
    'name': 'Cost Allocation',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'ABC Cost Allocation for IT Services',
    'description': """
        Activity-Based Costing module for IT service companies.
        Allocates direct and indirect costs to clients based on cost drivers.
    """,
    'depends': ['base', 'hr', 'hr_timesheet', 'project', 'account', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/service_data.xml',
        'data/service_catalog_data.xml',
        'data/cron_data.xml',
        'views/actions.xml',
        'views/service_views.xml',
        'views/billing_views.xml',
        'views/cost_pool_views.xml',
        'views/cost_driver_views.xml',
        'views/employee_cost_views.xml',
        'views/client_allocation_views.xml',
        'views/service_catalog_views.xml',
        'views/subscription_views.xml',
        'views/partner_views.xml',
        'wizards/wizard_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}