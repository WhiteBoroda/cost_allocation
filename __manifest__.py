{
    'name': 'Розподіл затрат / Cost Allocation',
    'version': '17.0.1.1.3',
    'category': 'Accounting',
    'summary': 'ABC розрахунок собівартості IT послуг / ABC Cost Allocation for IT Services',
    'description': """

                                              Модуль розрахунку собівартості послуг методом ABC (Activity-Based Costing) для сервісних компаній.

                                              🎯 Підходить для різних типів бізнесу:
        • IT Services - технічна підтримка, обслуговування обладнання
        • Legal Services - юридичні послуги, консалтинг  
        • Accounting Services - бухгалтерські послуги, аудит
        • Financial Consulting - фінансове планування, аналіз
        • Construction Services - будівельні послуги, проектування
        • Technical Expertise - технічна експертиза, оцінка

        🚀 Основні можливості:
        • ABC Cost Allocation (Activity-Based Costing)
        • Каталог послуг з автоматичним ціноутворенням
        • Управління підписками з автоматичним виставленням рахунків
        • Interactive Dashboard з KPI та аналітикою
        • Підтримка Дія.City податкових ставок
        • Автоматизація через cron jobs
        • Система безпеки з 3 рівнями доступу

        Activity-Based Costing module for IT service companies.
        Allocates direct and indirect costs to clients based on cost drivers.
        Supports subscription billing and interactive dashboard with KPI analytics.
    """,
    'depends': ['base', 'hr', 'hr_timesheet', 'project', 'account', 'sale'],
    'data': [
        'security/security.xml',
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
        'views/dashboard_views.xml',
        'wizards/wizard_views.xml',
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