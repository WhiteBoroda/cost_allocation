# hooks.py - СТВОРИТИ В КОРЕНІ МОДУЛЯ cost_allocation/

import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def pre_init_hook(cr):
    """
    Хук для підготовки даних перед оновленням модуля
    Заповнює NULL значення unit_id дефолтними значеннями
    """
    _logger.info("=== MIGRATION HOOK: Fixing unit_id NULL values ===")

    try:
        # Перевіряємо чи існують таблиці
        cr.execute("""
                   SELECT table_name
                   FROM information_schema.tables
                   WHERE table_name IN ('cost_driver', 'service_type')
                     AND table_schema = current_schema()
                   """)
        existing_tables = [row[0] for row in cr.fetchall()]

        if 'cost_driver' in existing_tables:
            # Знаходимо або створюємо дефолтну одиницю вимірювання
            cr.execute("""
                       SELECT id
                       FROM unit_of_measure
                       WHERE name = 'Unit'
                       LIMIT 1
                       """)
            result = cr.fetchone()

            if result:
                default_unit_id = result[0]
                _logger.info(f"Found default unit ID: {default_unit_id}")
            else:
                # Створюємо дефолтну категорію якщо не існує
                cr.execute("""
                           INSERT INTO unit_measure_category (name, sequence, create_date, write_date, create_uid, write_uid)
                           SELECT 'General', 1, NOW(), NOW(), 1, 1
                           WHERE NOT EXISTS (SELECT 1
                                             FROM unit_measure_category
                                             WHERE name = 'General')
                           RETURNING id
                           """)

                # Отримуємо ID категорії
                cr.execute("SELECT id FROM unit_measure_category WHERE name = 'General' LIMIT 1")
                category_id = cr.fetchone()[0]

                # Створюємо дефолтну одиницю вимірювання
                cr.execute("""
                           INSERT INTO unit_of_measure (name, symbol, category_id, ratio, create_date, write_date,
                                                        create_uid, write_uid)
                           VALUES ('Unit', 'Unit', %s, 1.0, NOW(), NOW(), 1, 1)
                           RETURNING id
                           """, (category_id,))
                default_unit_id = cr.fetchone()[0]
                _logger.info(f"Created default unit ID: {default_unit_id}")

            # Оновлюємо NULL значення в cost_driver
            cr.execute("""
                       UPDATE cost_driver
                       SET unit_id = %s
                       WHERE unit_id IS NULL
                       """, (default_unit_id,))

            updated_drivers = cr.rowcount
            _logger.info(f"Updated {updated_drivers} cost_driver records with NULL unit_id")

        if 'service_type' in existing_tables:
            # Аналогічно для service_type
            cr.execute("""
                       SELECT id
                       FROM unit_of_measure
                       WHERE name = 'Unit'
                       LIMIT 1
                       """)
            default_unit_id = cr.fetchone()[0]

            cr.execute("""
                       UPDATE service_type
                       SET unit_id = %s
                       WHERE unit_id IS NULL
                       """, (default_unit_id,))

            updated_services = cr.rowcount
            _logger.info(f"Updated {updated_services} service_type records with NULL unit_id")

    except Exception as e:
        _logger.error(f"Migration hook failed: {str(e)}")
        # Не викидаємо помилку, щоб не зламати встановлення
        pass

    _logger.info("=== MIGRATION HOOK: Completed ===")


def post_init_hook(cr, registry):
    """
    Хук після встановлення модуля - перевіряємо чи все ОК
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Перевіряємо чи залишились NULL значення
    null_drivers = env['cost.driver'].search([('unit_id', '=', False)])
    null_services = env['service.type'].search([('unit_id', '=', False)])

    if null_drivers:
        _logger.warning(f"Found {len(null_drivers)} cost_driver records with NULL unit_id after migration")

    if null_services:
        _logger.warning(f"Found {len(null_services)} service_type records with NULL unit_id after migration")

    _logger.info("Post-init hook completed successfully")