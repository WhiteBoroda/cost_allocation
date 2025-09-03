# hooks.py

def pre_init_hook(env):
    """Pre-init hook - вызывается ДО создания/обновления таблиц"""

    # Проверяем, существует ли таблица service_classification
    env.cr.execute("""
                   SELECT EXISTS (SELECT
                                  FROM information_schema.tables
                                  WHERE table_schema = current_schema()
                                    AND table_name = 'service_classification')
                   """)
    table_exists = env.cr.fetchone()[0]

    if not table_exists:
        # Создаем таблицу вручную
        env.cr.execute("""
                       CREATE TABLE service_classification
                       (
                           id          SERIAL PRIMARY KEY,
                           name        VARCHAR NOT NULL,
                           code        VARCHAR NOT NULL UNIQUE,
                           sequence    INTEGER DEFAULT 10,
                           icon        VARCHAR DEFAULT 'fa-gear',
                           color       VARCHAR DEFAULT '#1f77b4',
                           description TEXT,
                           active      BOOLEAN DEFAULT TRUE,
                           create_date TIMESTAMP,
                           write_date  TIMESTAMP,
                           create_uid  INTEGER,
                           write_uid   INTEGER
                       )
                       """)

        # Заполняем базовыми данными
        classifications_data = [
            ('Workstation', 'workstation', 10, 'fa-desktop', '#1f77b4'),
            ('Server', 'server', 20, 'fa-server', '#ff7f0e'),
            ('Printer', 'printer', 30, 'fa-print', '#2ca02c'),
            ('Network Equipment', 'network', 40, 'fa-network-wired', '#d62728'),
            ('Software License', 'software', 50, 'fa-code', '#9467bd'),
            ('User Support', 'user', 60, 'fa-users', '#8c564b'),
            ('Project Work', 'project', 70, 'fa-project-diagram', '#e377c2'),
            ('Consulting', 'consulting', 80, 'fa-lightbulb', '#7f7f7f'),
            ('Hardware', 'hardware', 90, 'fa-microchip', '#bcbd22'),
            ('Support', 'support', 100, 'fa-life-ring', '#17becf'),
            ('Other', 'other', 999, 'fa-question', '#aec7e8'),
        ]

        for name, code, seq, icon, color in classifications_data:
            env.cr.execute("""
                           INSERT INTO service_classification
                               (name, code, sequence, icon, color, active, create_date, write_date)
                           VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                           """, (name, code, seq, icon, color))

        env.cr.commit()
        print("✅ Service classifications table created and populated!")

    else:
        # Таблица существует, проверяем есть ли записи
        env.cr.execute("SELECT COUNT(*) FROM service_classification")
        count = env.cr.fetchone()[0]

        if count == 0:
            # Заполняем пустую таблицу
            classifications_data = [
                ('Workstation', 'workstation', 10, 'fa-desktop', '#1f77b4'),
                ('Server', 'server', 20, 'fa-server', '#ff7f0e'),
                ('Printer', 'printer', 30, 'fa-print', '#2ca02c'),
                ('Network Equipment', 'network', 40, 'fa-network-wired', '#d62728'),
                ('Software License', 'software', 50, 'fa-code', '#9467bd'),
                ('User Support', 'user', 60, 'fa-users', '#8c564b'),
                ('Project Work', 'project', 70, 'fa-project-diagram', '#e377c2'),
                ('Consulting', 'consulting', 80, 'fa-lightbulb', '#7f7f7f'),
                ('Hardware', 'hardware', 90, 'fa-microchip', '#bcbd22'),
                ('Support', 'support', 100, 'fa-life-ring', '#17becf'),
                ('Other', 'other', 999, 'fa-question', '#aec7e8'),
            ]

            for name, code, seq, icon, color in classifications_data:
                env.cr.execute("""
                               INSERT INTO service_classification
                                   (name, code, sequence, icon, color, active, create_date, write_date)
                               VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                               """, (name, code, seq, icon, color))

            env.cr.commit()
            print("✅ Service classifications populated!")


def post_install_hook(env):
    """Post-install hook для финальной настройки"""

    # Убеждаемся что справочник заполнен
    classification_model = env['service.classification']
    count = classification_model.search_count([])

    if count == 0:
        # Резервное заполнение через ORM
        classifications_data = [
            {'name': 'Workstation', 'code': 'workstation', 'sequence': 10, 'icon': 'fa-desktop', 'color': '#1f77b4'},
            {'name': 'Server', 'code': 'server', 'sequence': 20, 'icon': 'fa-server', 'color': '#ff7f0e'},
            {'name': 'Printer', 'code': 'printer', 'sequence': 30, 'icon': 'fa-print', 'color': '#2ca02c'},
            {'name': 'Network Equipment', 'code': 'network', 'sequence': 40, 'icon': 'fa-network-wired',
             'color': '#d62728'},
            {'name': 'Software License', 'code': 'software', 'sequence': 50, 'icon': 'fa-code', 'color': '#9467bd'},
            {'name': 'User Support', 'code': 'user', 'sequence': 60, 'icon': 'fa-users', 'color': '#8c564b'},
            {'name': 'Project Work', 'code': 'project', 'sequence': 70, 'icon': 'fa-project-diagram',
             'color': '#e377c2'},
            {'name': 'Consulting', 'code': 'consulting', 'sequence': 80, 'icon': 'fa-lightbulb', 'color': '#7f7f7f'},
            {'name': 'Hardware', 'code': 'hardware', 'sequence': 90, 'icon': 'fa-microchip', 'color': '#bcbd22'},
            {'name': 'Support', 'code': 'support', 'sequence': 100, 'icon': 'fa-life-ring', 'color': '#17becf'},
            {'name': 'Other', 'code': 'other', 'sequence': 999, 'icon': 'fa-question', 'color': '#aec7e8'},
        ]

        for data in classifications_data:
            classification_model.create(data)

        print("✅ Service classifications created via ORM!")

    print("✅ Post-install completed successfully!")