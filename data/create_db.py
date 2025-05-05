import sqlalchemy as sa

# --- Конфигурация ---
DB_NAME = 'nascar_stats.db'
DB_URL = f'sqlite:///{DB_NAME}'

# --- Создание движка и метаданных ---
engine = sa.create_engine(DB_URL)
metadata = sa.MetaData()

# --- Определение таблиц ---

series_table = sa.Table('Series', metadata,
    sa.Column('series_id', sa.Integer, primary_key=True),
    sa.Column('series_name', sa.String(50), nullable=False, unique=True)
)

tracks_table = sa.Table('Tracks', metadata,
    sa.Column('track_id', sa.Integer, primary_key=True),
    sa.Column('track_name', sa.String(255), nullable=False, unique=True),
    sa.Column('track_length', sa.REAL),
    sa.Column('track_surface', sa.String(50))
)

drivers_table = sa.Table('Drivers', metadata,
    sa.Column('driver_id', sa.Integer, primary_key=True),
    sa.Column('driver_name', sa.String(255), nullable=False, unique=True)
)

teams_table = sa.Table('Teams', metadata,
    sa.Column('team_id', sa.Integer, primary_key=True),
    sa.Column('team_name', sa.String(255), nullable=False, unique=True)
)

manufacturers_table = sa.Table('Manufacturers', metadata,
    sa.Column('manufacturer_id', sa.Integer, primary_key=True),
    sa.Column('manufacturer_name', sa.String(100), nullable=False, unique=True)
)

races_table = sa.Table('Races', metadata,
    sa.Column('race_id', sa.Integer, primary_key=True),
    sa.Column('season', sa.Integer, nullable=False),
    sa.Column('race_num_in_season', sa.Integer, nullable=False),
    sa.Column('race_name', sa.String(255), nullable=False),
    sa.Column('track_id', sa.Integer, sa.ForeignKey('Tracks.track_id'), nullable=False),
    sa.Column('series_id', sa.Integer, sa.ForeignKey('Series.series_id'), nullable=False),
    # Уникальный ключ для гонки в рамках сезона и серии
    sa.UniqueConstraint('season', 'race_num_in_season', 'series_id', name='uq_race')
)

race_entries_table = sa.Table('RaceEntries', metadata,
    sa.Column('entry_id', sa.Integer, primary_key=True),
    sa.Column('race_id', sa.Integer, sa.ForeignKey('Races.race_id'), nullable=False),
    sa.Column('driver_id', sa.Integer, sa.ForeignKey('Drivers.driver_id'), nullable=False),
    sa.Column('team_id', sa.Integer, sa.ForeignKey('Teams.team_id'), nullable=False),
    sa.Column('manufacturer_id', sa.Integer, sa.ForeignKey('Manufacturers.manufacturer_id'), nullable=False),
    sa.Column('car_number', sa.String(10)),
    sa.Column('start_position', sa.Integer),
    sa.Column('finish_position', sa.Integer),
    sa.Column('points', sa.Integer),
    sa.Column('laps_completed', sa.Integer),
    sa.Column('laps_led', sa.Integer),
    sa.Column('status', sa.String(50)),
    sa.Column('segment1_finish', sa.Integer),
    sa.Column('segment2_finish', sa.Integer),
    sa.Column('driver_rating', sa.REAL),
    sa.Column('won_race', sa.Integer, nullable=False), # Используем Integer (0 или 1) для совместимости
    # Потенциальный уникальный ключ для записи (зависит от бизнес-логики)
    # sa.UniqueConstraint('race_id', 'driver_id', 'car_number', name='uq_race_entry')
)

# --- Функция для создания таблиц и заполнения начальных данных ---
def create_database():
    """Создает все таблицы в базе данных и заполняет таблицу Series."""
    print(f"Создание структуры базы данных в файле: {DB_NAME}...")
    metadata.create_all(engine)
    print("Структура базы данных успешно создана.")

    # Заполнение таблицы Series начальными данными
    print("Заполнение таблицы 'Series'...")
    initial_series = [
        {'series_name': 'Cup'},
        {'series_name': 'Xfinity'},
        {'series_name': 'Truck'},
    ]
    try:
        with engine.connect() as connection:
            # Проверяем, пуста ли таблица перед вставкой
            count = connection.execute(sa.select(sa.func.count()).select_from(series_table)).scalar_one()
            if count == 0:
                connection.execute(series_table.insert(), initial_series)
                connection.commit() # Не забываем коммит для SQLite при записи
                print("Таблица 'Series' успешно заполнена.")
            else:
                print("Таблица 'Series' уже содержит данные.")
    except Exception as e:
        print(f"Ошибка при заполнении таблицы 'Series': {e}")

# --- Точка входа ---
if __name__ == "__main__":
    create_database()