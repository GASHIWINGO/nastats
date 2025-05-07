# init_postgres_schema.py
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BIGINT # Для telegram_user_id

# --- Конфигурация для ЛОКАЛЬНОЙ PostgreSQL ---
# Замените на ваши данные, если отличаются от стандартных
DB_USER_LOCAL = "nascar_user"  # Или 'postgres'
DB_PASSWORD_LOCAL = "dzkexbnhtfre" # Пароль пользователя БД
DB_HOST_LOCAL = "localhost"
DB_PORT_LOCAL = "5432"
DB_NAME_LOCAL_PG = "nascar_stats_db" # Имя вашей PostgreSQL БД

# Строка подключения для psycopg2 (синхронный драйвер, используется SQLAlchemy create_engine)
DB_URL_LOCAL_PG = f"postgresql+psycopg2://{DB_USER_LOCAL}:{DB_PASSWORD_LOCAL}@{DB_HOST_LOCAL}:{DB_PORT_LOCAL}/{DB_NAME_LOCAL_PG}"

engine = sa.create_engine(DB_URL_LOCAL_PG)
metadata = sa.MetaData()

# --- Определение таблиц ---

series_table = sa.Table('Series', metadata,
    sa.Column('series_id', sa.Integer, primary_key=True, autoincrement=True),
    sa.Column('series_name', sa.String(50), nullable=False, unique=True)
)

tracks_table = sa.Table('Tracks', metadata,
    sa.Column('track_id', sa.Integer, primary_key=True, autoincrement=True),
    sa.Column('track_name', sa.String(255), nullable=False, unique=True),
    sa.Column('track_length', sa.REAL), # В PostgreSQL это будет REAL или DOUBLE PRECISION
    sa.Column('track_surface', sa.String(50))
)

drivers_table = sa.Table('Drivers', metadata,
    sa.Column('driver_id', sa.Integer, primary_key=True, autoincrement=True),
    sa.Column('driver_name', sa.String(255), nullable=False, unique=True)
)

teams_table = sa.Table('Teams', metadata,
    sa.Column('team_id', sa.Integer, primary_key=True, autoincrement=True),
    sa.Column('team_name', sa.String(255), nullable=False, unique=True)
)

manufacturers_table = sa.Table('Manufacturers', metadata,
    sa.Column('manufacturer_id', sa.Integer, primary_key=True, autoincrement=True),
    sa.Column('manufacturer_name', sa.String(100), nullable=False, unique=True)
)

races_table = sa.Table('Races', metadata,
    sa.Column('race_id', sa.Integer, primary_key=True, autoincrement=True),
    sa.Column('season', sa.Integer, nullable=False),
    sa.Column('race_num_in_season', sa.Integer, nullable=False),
    sa.Column('race_name', sa.String(255), nullable=False),
    sa.Column('track_id', sa.Integer, sa.ForeignKey('Tracks.track_id'), nullable=False),
    sa.Column('series_id', sa.Integer, sa.ForeignKey('Series.series_id'), nullable=False),
    sa.UniqueConstraint('season', 'race_num_in_season', 'series_id', name='uq_race')
)

race_entries_table = sa.Table('RaceEntries', metadata,
    sa.Column('entry_id', sa.Integer, primary_key=True, autoincrement=True),
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
    sa.Column('won_race', sa.Integer, nullable=False, default=0), # default=0
    # sa.UniqueConstraint('race_id', 'driver_id', 'car_number', name='uq_race_entry') # Раскомментируйте, если нужно
)

# --- Новые таблицы для пользователей и подписок ---
users_table = sa.Table('Users', metadata,
    sa.Column('user_id', sa.Integer, primary_key=True, autoincrement=True),
    sa.Column('username', sa.String(100), nullable=False, unique=True),
    sa.Column('password_hash', sa.String(255), nullable=False), # Будет хранить хэш пароля
    sa.Column('telegram_user_id', BIGINT, unique=True, nullable=True), # Telegram User ID
    sa.Column('link_code', sa.String(50), nullable=True, index=True), # Код для привязки Telegram
    sa.Column('link_code_expires_at', sa.TIMESTAMP(timezone=True), nullable=True), # Время жизни кода
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()) # Время создания
)

user_subscriptions_table = sa.Table('UserSubscriptions', metadata,
    sa.Column('subscription_id', sa.Integer, primary_key=True, autoincrement=True),
    sa.Column('user_id', sa.Integer, sa.ForeignKey('Users.user_id', ondelete="CASCADE"), nullable=False),
    sa.Column('series_id', sa.Integer, sa.ForeignKey('Series.series_id'), nullable=False),
    sa.Column('notification_type', sa.String(50), nullable=False, default='race_results_update'), # Тип уведомления
    sa.Column('is_active', sa.Boolean, nullable=False, default=True), # Активна ли подписка
    sa.UniqueConstraint('user_id', 'series_id', 'notification_type', name='uq_user_subscription')
)

# --- Функция для создания таблиц и заполнения начальных данных ---
def create_database_structure():
    """Создает все таблицы в базе данных PostgreSQL и заполняет таблицу Series."""
    print(f"Создание структуры таблиц в PostgreSQL базе: {DB_NAME_LOCAL_PG}...")
    try:
        metadata.create_all(engine) # Эта команда создаст все определенные таблицы
        print("Структура таблиц успешно создана в PostgreSQL.")

        # Заполнение таблицы Series начальными данными
        print("Заполнение таблицы 'Series'...")
        initial_series = [
            {'series_name': 'Cup'},
            {'series_name': 'Xfinity'},
            {'series_name': 'Truck'},
        ]
        with engine.connect() as connection:
            # Проверяем, пуста ли таблица перед вставкой
            count_result = connection.execute(sa.select(sa.func.count()).select_from(series_table))
            count = count_result.scalar_one()
            if count == 0:
                connection.execute(series_table.insert(), initial_series)
                connection.commit() # Для PostgreSQL коммит нужен явно после операций записи
                print("Таблица 'Series' успешно заполнена.")
            else:
                print("Таблица 'Series' уже содержит данные.")
    except Exception as e:
        print(f"Ошибка при создании/заполнении таблиц в PostgreSQL: {e}")

# --- Точка входа ---
if __name__ == "__main__":
    create_database_structure()