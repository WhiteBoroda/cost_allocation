# models/__init__.py

# Base configurations
from . import sequence_config
from . import cost_settings
from . import working_days_util
from . import unit_measure

# Core cost allocation models
from . import employee_cost
from . import cost_pool
from . import cost_driver
from . import client_allocation

# ДОБАВЛЕНО: справочник классификации сервисов (должен быть первым)
from . import service_classification

# Service catalog hierarchy (ПРАВИЛЬНЫЙ ПОРЯДОК!)
from . import service_category      # ServiceCategory (ссылается на classification)
from . import service_type          # ServiceType (ссылается на category + classification)
from . import service_catalog       # ServiceCatalog (ссылается на type)
from . import client_service        # ClientService (ссылается на type + catalog)

# Workload analysis
from . import employee_workload     # EmployeeWorkload + EmployeePoolWorkload

# Billing and automation
from . import billing_automation
from . import subscription

# Partner and company extensions
from . import res_partner
from . import res_company
from . import company_fields

# Account integration
from . import account_move

# Additional modules
from . import overhead_costs
from . import service_costing
from . import res_users
from . import cost_driver_category