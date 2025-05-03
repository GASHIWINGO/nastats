import logging
import os
import math
from sqlalchemy import create_engine, select, func, MetaData, desc, asc, text, case, cast, Integer, Float, over
from sqlalchemy.orm import sessionmaker, Session # Импортируем обычную Session
from contextlib import contextmanager

# Определяем путь к корневой папке проекта
# D:/cod/statistics/database/db_sync.py -> D:/cod/statistics/
PROJECT_ROOT = os.path.dirname(__file__)
DB_NAME = 'data/nascar_stats.db'
DB_PATH = os.path.join(PROJECT_ROOT, DB_NAME)
DB_URL = f'sqlite:///{DB_PATH}' # Используем стандартный драйвер sqlite

# --- SQLAlchemy Setup ---
logger = logging.getLogger(__name__) # Логгер для этого модуля
metadata = MetaData()

# Используем синхронный движок
engine = create_engine(DB_URL, echo=False) # echo=True для отладки SQL запросов

# Используем синхронную сессию
sync_session_factory = sessionmaker(engine, class_=Session, expire_on_commit=False)

# --- Переменные для отраженных таблиц (как и раньше) ---
series_table, tracks_table, drivers_table, teams_table, manufacturers_table, races_table, race_entries_table = [None] * 7

# --- Кэш последнего сезона (как и раньше) ---
LATEST_SEASON = None

@contextmanager
def get_db_session() -> Session:
    """Предоставляет сессию БД в менеджере контекста."""
    session = sync_session_factory()
    try:
        yield session
        session.commit() # Коммитим, если все прошло успешно
    except Exception:
        session.rollback() # Откатываем изменения в случае ошибки
        raise
    finally:
        session.close() # Всегда закрываем сессию

def reflect_db_schema():
    """Отражает схему БД синхронно и заполняет переменные таблиц."""
    global series_table, tracks_table, drivers_table, teams_table, manufacturers_table, races_table, race_entries_table, LATEST_SEASON
    logger.info("Начало отражения схемы БД (синхронно)...")
    try:
        # Отражение происходит через движок
        metadata.reflect(bind=engine)
        logger.info("Структура БД успешно отражена.")

        # Заполняем глобальные переменные таблиц
        series_table = metadata.tables.get('Series')
        tracks_table = metadata.tables.get('Tracks')
        drivers_table = metadata.tables.get('Drivers')
        teams_table = metadata.tables.get('Teams')
        manufacturers_table = metadata.tables.get('Manufacturers')
        races_table = metadata.tables.get('Races')
        race_entries_table = metadata.tables.get('RaceEntries')

        missing_tables = [
            name for name, table in zip(
                ['Series', 'Tracks', 'Drivers', 'Teams', 'Manufacturers', 'Races', 'RaceEntries'],
                [series_table, tracks_table, drivers_table, teams_table, manufacturers_table, races_table, race_entries_table]
            ) if table is None
        ]
        if missing_tables:
            logger.error(f"Не найдены следующие таблицы: {', '.join(missing_tables)}")
            raise ValueError("Не удалось отразить одну или несколько таблиц БД.")
        logger.info("Все необходимые таблицы найдены.")

        # Определяем последний сезон после отражения
        LATEST_SEASON = get_latest_season(force_refresh=True) # Вызываем синхронную версию
        if LATEST_SEASON is None:
            logger.warning("Не удалось определить последний сезон после отражения схемы.")
            # Можно установить значение по умолчанию или выбросить ошибку,
            # пока просто оставим None и предупреждение.

    except Exception as e:
        logger.critical(f"Критическая ошибка при отражении схемы БД: {e}")
        raise # Перевыбрасываем ошибку, т.к. без схемы работать нельзя

def get_latest_season(force_refresh: bool = False) -> int | None:
    """Получает и кэширует последний сезон из БД (синхронно)."""
    global LATEST_SEASON
    if LATEST_SEASON is not None and not force_refresh:
        return LATEST_SEASON

    logger.info("Запрашиваем последний сезон из БД (синхронно)...")
    if races_table is None:
        logger.error("Таблица Races не отражена. Невозможно определить последний сезон.")
        return None # Возвращаем None, если таблицы нет

    try:
        with get_db_session() as session: # Используем менеджер контекста
            stmt = select(func.max(races_table.c.season))
            # Выполняем синхронно
            max_season = session.execute(stmt).scalar_one_or_none()
            if max_season:
                LATEST_SEASON = int(max_season)
                logger.info(f"Последний сезон из БД: {LATEST_SEASON}")
            else:
                logger.warning("В таблице Races нет записей. Не удалось определить последний сезон.")
                LATEST_SEASON = None
    except Exception as e:
        logger.error(f"Ошибка при запросе последнего сезона: {e}", exc_info=True)
        LATEST_SEASON = None # Возвращаем None в случае ошибки
    return LATEST_SEASON

# --- Далее будем адаптировать остальные функции ---
# Пример адаптации get_series_id_by_name:

def get_series_id_by_name(session: Session, series_name: str) -> int | None:
    """Получает ID серии по её имени (синхронно)."""
    if series_table is None:
        logger.error("Таблица Series не отражена.")
        return None
    series_stmt = select(series_table.c.series_id).where(series_table.c.series_name == series_name)
    # Используем переданную сессию
    series_id = session.execute(series_stmt).scalar_one_or_none()
    if not series_id:
        logger.warning(f"Серия '{series_name}' не найдена в БД.")
    return series_id

def get_id_by_name(session: Session, table, name_column_name: str, id_column_name: str, entity_name: str) -> int | None:
    """Универсальная функция для поиска ID по имени в таблице (без учета регистра, синхронно)."""
    if table is None:
        logger.error(f"Таблица для поиска ID ({name_column_name}) не отражена.")
        return None
    # Проверяем наличие атрибутов перед использованием
    if not hasattr(table.c, name_column_name):
        logger.error(f"В таблице {table.name} нет столбца {name_column_name}")
        return None
    if not hasattr(table.c, id_column_name):
        logger.error(f"В таблице {table.name} нет столбца {id_column_name}")
        return None

    name_column = getattr(table.c, name_column_name)
    id_column = getattr(table.c, id_column_name)

    stmt = select(id_column).where(func.lower(name_column) == func.lower(entity_name))
    result = session.execute(stmt).scalar_one_or_none() # Выполняем синхронно
    if not result:
        logger.warning(f"Сущность с именем '{entity_name}' не найдена в таблице {table.name}.")
    return result

def get_driver_id_by_name(session: Session, driver_name: str) -> int | None:
    """Получает ID гонщика по имени (без учета регистра, синхронно)."""
    return get_id_by_name(session, drivers_table, "driver_name", "driver_id", driver_name)

def get_team_id_by_name(session: Session, team_name: str) -> int | None:
    """Получает ID команды по имени (без учета регистра, синхронно)."""
    return get_id_by_name(session, teams_table, "team_name", "team_id", team_name)

def get_manufacturer_id_by_name(session: Session, manufacturer_name: str) -> int | None:
    """Получает ID производителя по имени (без учета регистра, синхронно)."""
    return get_id_by_name(session, manufacturers_table, "manufacturer_name", "manufacturer_id", manufacturer_name)

def get_races_for_season(season: int, series_name: str = 'Cup', page: int = 1, page_size: int = 7):
    """Получает список гонок (включая ID) для сезона/серии с пагинацией (синхронно)."""
    logger.info(f"Запрос гонок: season={season}, series='{series_name}', page={page}")
    if races_table is None or tracks_table is None or series_table is None: # Добавил проверку series_table
        logger.error("Таблицы Races, Tracks или Series не отражены.")
        return [], 1, 1
    # Используем сессию внутри, т.к. функция самодостаточна
    with get_db_session() as session:
        try:
            # Получаем series_id, используя адаптированную функцию
            series_id = get_series_id_by_name(session, series_name)
            if not series_id: return [], 1, 1 # Если серия не найдена

            count_stmt = select(func.count(races_table.c.race_id)).where(
                (races_table.c.season == season) & (races_table.c.series_id == series_id)
            )
            # Выполняем синхронно
            total_races = session.execute(count_stmt).scalar_one()
            logger.info(f"Найдено всего гонок: {total_races}")
            if total_races == 0: return [], 1, 1

            total_pages = math.ceil(total_races / page_size)
            page = max(1, min(page, total_pages)) # Ограничиваем номер страницы
            offset = (page - 1) * page_size
            logger.info(f"Пагинация: total_pages={total_pages}, current_page={page}, offset={offset}")

            races_stmt = select(
                races_table.c.race_id, races_table.c.race_num_in_season,
                races_table.c.race_name, tracks_table.c.track_name,
                tracks_table.c.track_length, tracks_table.c.track_surface
            ).join(tracks_table, races_table.c.track_id == tracks_table.c.track_id
            ).where(
                (races_table.c.season == season) & (races_table.c.series_id == series_id)
            ).order_by(
                asc(races_table.c.race_num_in_season)
            ).limit(page_size).offset(offset)

            # Выполняем синхронно
            races_list = session.execute(races_stmt).fetchall()
            logger.info(f"Возвращено {len(races_list)} гонок для страницы.")
            return races_list, page, total_pages
        except Exception as e:
            logger.error(f"Ошибка получения гонок (season={season}, page={page}): {e}", exc_info=True)
            return [], 1, 1 # Возвращаем пустой список при ошибке

def get_race_details_and_results(race_id: int):
    """Получает детали гонки и ВСЕ результаты (синхронно)."""
    logger.info(f"Запрос деталей и результатов для race_id={race_id}")
    # Проверяем наличие всех нужных таблиц
    required_tables = [races_table, tracks_table, series_table, race_entries_table, drivers_table, teams_table, manufacturers_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['Races', 'Tracks', 'Series', 'RaceEntries', 'Drivers', 'Teams', 'Manufacturers'], required_tables) if table is None]
        logger.error(f"Одна или несколько таблиц не отражены для get_race_details_and_results: {', '.join(missing)}")
        return None, None

    # Используем сессию внутри
    with get_db_session() as session:
        try:
            details_stmt = select(
                races_table.c.race_name, races_table.c.season,
                tracks_table.c.track_name, tracks_table.c.track_length, tracks_table.c.track_surface,
                series_table.c.series_name
            ).select_from(races_table
            ).join(tracks_table, races_table.c.track_id == tracks_table.c.track_id
            ).join(series_table, races_table.c.series_id == series_table.c.series_id
            ).where(races_table.c.race_id == race_id)
            # Выполняем синхронно
            race_details = session.execute(details_stmt).fetchone()

            if not race_details:
                logger.warning(f"Детали гонки для race_id={race_id} не найдены.")
                return None, None
            logger.info(f"Детали гонки найдены: {race_details.race_name}")

            results_stmt = select(
                race_entries_table.c.finish_position, race_entries_table.c.start_position,
                race_entries_table.c.car_number, race_entries_table.c.laps_completed,
                race_entries_table.c.laps_led, race_entries_table.c.status,
                drivers_table.c.driver_name, teams_table.c.team_name,
                manufacturers_table.c.manufacturer_name
            ).select_from(race_entries_table
            ).join(drivers_table, race_entries_table.c.driver_id == drivers_table.c.driver_id, isouter=True # isouter=True на случай отсутствия гонщика в справочнике
            ).join(teams_table, race_entries_table.c.team_id == teams_table.c.team_id, isouter=True
            ).join(manufacturers_table, race_entries_table.c.manufacturer_id == manufacturers_table.c.manufacturer_id, isouter=True
            ).where(race_entries_table.c.race_id == race_id
            ).order_by(
                asc(race_entries_table.c.finish_position) # Сортируем по финишной позиции
            )

            # Выполняем синхронно
            results = session.execute(results_stmt).fetchall()
            logger.info(f"Найдено результатов гонки: {len(results) if results else 0}")
            return race_details, results
        except Exception as e:
            logger.error(f"Ошибка получения деталей/результатов (race_id={race_id}): {e}", exc_info=True)
            return None, None # Возвращаем None при ошибке

def get_driver_standings(season: int, series_name: str = 'Cup', page: int = 1, page_size: int = 10):
    """Получает рейтинг гонщиков за сезон с пагинацией (синхронно)."""
    logger.info(f"Запрос рейтинга гонщиков: season={season}, series='{series_name}', page={page}")
    required_tables = [race_entries_table, races_table, drivers_table, series_table] # Добавил series_table
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['RaceEntries', 'Races', 'Drivers', 'Series'], required_tables) if table is None]
        logger.error(f"Одна или несколько таблиц не отражены для get_driver_standings: {', '.join(missing)}")
        return [], 1, 1

    with get_db_session() as session:
        try:
            series_id = get_series_id_by_name(session, series_name)
            if not series_id: return [], 1, 1

            # Подзапрос для агрегации статистики по гонщикам
            subq = select(
                race_entries_table.c.driver_id,
                func.sum(race_entries_table.c.points).label('total_points'),
                func.sum(race_entries_table.c.won_race).label('total_wins'),
                func.count(race_entries_table.c.race_id).label('races_entered') # Считаем количество гонок
            ).join(races_table, race_entries_table.c.race_id == races_table.c.race_id
            ).where(
                (races_table.c.season == season) &
                (races_table.c.series_id == series_id) &
                (race_entries_table.c.points != None) & # Исключаем записи без очков? (можно убрать, если очки могут быть 0)
                (race_entries_table.c.driver_id != None) # Исключаем записи без гонщика
            ).group_by(race_entries_table.c.driver_id
            ).subquery() # Делаем это подзапросом

            # Запрос для подсчета общего количества гонщиков в рейтинге
            count_stmt = select(func.count()).select_from(subq)
            total_drivers = session.execute(count_stmt).scalar_one()
            logger.info(f"Найдено всего гонщиков в рейтинге: {total_drivers}")
            if total_drivers == 0: return [], 1, 1

            total_pages = math.ceil(total_drivers / page_size)
            page = max(1, min(page, total_pages)) # Ограничиваем номер страницы
            offset = (page - 1) * page_size
            logger.info(f"Пагинация: total_pages={total_pages}, current_page={page}, offset={offset}")

            # Основной запрос для получения страницы рейтинга
            standings_stmt = select(
                subq.c.driver_id, drivers_table.c.driver_name,
                subq.c.total_points, subq.c.total_wins, subq.c.races_entered
            ).select_from(subq # Выбираем из подзапроса
            ).join(drivers_table, subq.c.driver_id == drivers_table.c.driver_id # Присоединяем имена гонщиков
            ).order_by(
                desc(subq.c.total_points), # Сортируем по очкам (убыв.)
                desc(subq.c.total_wins),   # Затем по победам (убыв.)
                asc(drivers_table.c.driver_name) # Затем по имени (возр.)
            ).limit(page_size).offset(offset)

            standings_list = session.execute(standings_stmt).fetchall()
            logger.info(f"Возвращено {len(standings_list)} гонщиков для страницы.")
            return standings_list, page, total_pages
        except Exception as e:
            logger.error(f"Ошибка получения рейтинга гонщиков (season={season}, page={page}): {e}", exc_info=True)
            return [], 1, 1 # Возвращаем пустоту при ошибке

def get_driver_season_details(driver_id: int, season: int, series_name: str = 'Cup'):
    """Получает детальную статистику гонщика за сезон (синхронно)."""
    logger.info(f"Запрос деталей гонщика: driver_id={driver_id}, season={season}, series='{series_name}'")
    required_tables = [drivers_table, race_entries_table, races_table, series_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['Drivers', 'RaceEntries', 'Races', 'Series'], required_tables) if table is None]
        logger.error(f"Одна или несколько таблиц не отражены для get_driver_season_details: {', '.join(missing)}")
        return None

    with get_db_session() as session:
        try:
            series_id = get_series_id_by_name(session, series_name)
            if not series_id: return None # Серия не найдена

            # Сначала получаем имя гонщика
            driver_name_stmt = select(drivers_table.c.driver_name).where(drivers_table.c.driver_id == driver_id)
            driver_name = session.execute(driver_name_stmt).scalar_one_or_none()
            if not driver_name:
                logger.warning(f"Гонщик с driver_id={driver_id} не найден.")
                return None
            logger.info(f"Найден гонщик: {driver_name}")

            # Затем получаем агрегированную статистику
            stats_stmt = select(
                func.count(race_entries_table.c.race_id).label('races'),
                func.sum(race_entries_table.c.won_race).label('wins'),
                func.sum(case((race_entries_table.c.finish_position <= 5, 1), else_=0)).label('top5'),
                func.sum(case((race_entries_table.c.finish_position <= 10, 1), else_=0)).label('top10'),
                func.sum(func.coalesce(race_entries_table.c.laps_led, 0)).label('laps_led'), # Используем coalesce для суммы NULLs как 0
                func.sum(func.coalesce(race_entries_table.c.laps_completed, 0)).label('laps_completed'),
                func.avg(cast(race_entries_table.c.start_position, Float)).label('avg_start'),
                func.avg(cast(race_entries_table.c.finish_position, Float)).label('avg_finish'),
                func.sum(func.coalesce(race_entries_table.c.points, 0)).label('points')
            ).select_from(race_entries_table
            ).join(races_table, race_entries_table.c.race_id == races_table.c.race_id
            ).where(
                (race_entries_table.c.driver_id == driver_id) &
                (races_table.c.season == season) &
                (races_table.c.series_id == series_id) &
                (race_entries_table.c.finish_position != None) # Учитываем только финишировавших для средних
                # Добавляем условие для старта, если start_position может быть NULL
                # (race_entries_table.c.start_position != None)
            )

            stats_result = session.execute(stats_stmt).fetchone() # Выполняем синхронно
            logger.info(f"Результат запроса статистики гонщика: {stats_result}")

            # Формируем результат, даже если гонок не было
            details = {'driver_name': driver_name, 'season': season, 'series_name': series_name}
            if stats_result and stats_result.races is not None and stats_result.races > 0:
                 details.update({
                    'races': stats_result.races or 0, 'wins': stats_result.wins or 0,
                    'top5': stats_result.top5 or 0, 'top10': stats_result.top10 or 0,
                    'laps_led': stats_result.laps_led or 0, 'laps_completed': stats_result.laps_completed or 0,
                    'avg_start': round(stats_result.avg_start, 1) if stats_result.avg_start else None,
                    'avg_finish': round(stats_result.avg_finish, 1) if stats_result.avg_finish else None,
                    'points': stats_result.points if stats_result.points is not None else 0
                })
            else:
                # Если гонок нет, заполняем нулями/None
                details.update({
                    'races': 0, 'wins': 0, 'top5': 0, 'top10': 0, 'laps_led': 0,
                    'laps_completed': 0, 'avg_start': None, 'avg_finish': None, 'points': 0
                })
                logger.info(f"Гонки для driver_id={driver_id}, season={season}, series={series_name} не найдены.")

            logger.info(f"Сформирован словарь деталей гонщика: {details}")
            return details
        except Exception as e:
            logger.error(f"Ошибка получения деталей гонщика (driver_id={driver_id}, season={season}): {e}", exc_info=True)
            return None

def get_driver_race_results_for_season(driver_id: int, season: int, series_id: int):
    """
    Получает результаты (номер гонки, старт, финиш, ОЧКИ) для гонщика за сезон/серию.
    Возвращает список кортежей (race_num_in_season, start_position, finish_position, points)
    или пустой список.
    """
    logger.info(f"Запрос результатов гонок (с очками) для driver_id={driver_id}, season={season}, series_id={series_id}")
    required_tables = [race_entries_table, races_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['RaceEntries', 'Races'], required_tables) if table is None]
        logger.error(f"Таблицы не отражены для get_driver_race_results_for_season: {', '.join(missing)}")
        return []

    with get_db_session() as session:
        try:
            stmt = select(
                races_table.c.race_num_in_season,
                race_entries_table.c.start_position,
                race_entries_table.c.finish_position,
                race_entries_table.c.points # <--- Добавляем столбец очков
            ).select_from(race_entries_table
            ).join(races_table, race_entries_table.c.race_id == races_table.c.race_id
            ).where(
                (race_entries_table.c.driver_id == driver_id) &
                (races_table.c.season == season) &
                (races_table.c.series_id == series_id)
                # Убираем фильтр по finish_position != None, т.к. очки могут быть и за DNF
            ).order_by(asc(races_table.c.race_num_in_season)) # Сортируем по номеру гонки

            results = session.execute(stmt).fetchall()
            logger.info(f"Найдено {len(results)} результатов гонок (с очками) для графика.")
            # Кортеж теперь содержит 4 элемента
            return results
        except Exception as e:
            logger.error(f"Ошибка получения результатов гонок (с очками) для графика: {e}", exc_info=True)
            return []

def get_team_standings(season: int, series_name: str = 'Cup', page: int = 1, page_size: int = 10):
    """Получает рейтинг команд за сезон с пагинацией (синхронно)."""
    logger.info(f"Запрос рейтинга команд: season={season}, series='{series_name}', page={page}")
    required_tables = [race_entries_table, races_table, teams_table, series_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['RaceEntries', 'Races', 'Teams', 'Series'], required_tables) if table is None]
        logger.error(f"Одна или несколько таблиц не отражены для get_team_standings: {', '.join(missing)}")
        return [], 1, 1

    with get_db_session() as session:
        try:
            series_id = get_series_id_by_name(session, series_name)
            if not series_id: return [], 1, 1

            # Подзапрос для агрегации статистики по командам
            subq = select(
                race_entries_table.c.team_id,
                func.sum(race_entries_table.c.won_race).label('total_wins'),
                # Суммируем очки всех гонщиков команды
                func.sum(func.coalesce(race_entries_table.c.points, 0)).label('total_points'),
                func.sum(case((race_entries_table.c.finish_position <= 5, 1), else_=0)).label('total_top5'),
                func.count(race_entries_table.c.driver_id).label('total_entries') # Считаем участия машин
            ).join(races_table, race_entries_table.c.race_id == races_table.c.race_id
            ).where(
                (races_table.c.season == season) &
                (races_table.c.series_id == series_id) &
                (race_entries_table.c.team_id != None) & # У команды должен быть ID
                (race_entries_table.c.driver_id != None) # У участия должен быть гонщик
            ).group_by(race_entries_table.c.team_id
            ).subquery()

            # Запрос для подсчета общего количества команд
            count_stmt = select(func.count()).select_from(subq)
            total_teams = session.execute(count_stmt).scalar_one()
            logger.info(f"Найдено всего команд в рейтинге: {total_teams}")
            if total_teams == 0: return [], 1, 1

            total_pages = math.ceil(total_teams / page_size)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * page_size
            logger.info(f"Пагинация команд: total_pages={total_pages}, current_page={page}, offset={offset}")

            # Основной запрос для получения страницы рейтинга команд
            standings_stmt = select(
                subq.c.team_id,
                teams_table.c.team_name,
                subq.c.total_wins,
                subq.c.total_points,
                subq.c.total_top5,
                subq.c.total_entries
            ).select_from(subq
            ).join(teams_table, subq.c.team_id == teams_table.c.team_id
            ).order_by(
                # Сортировка может быть разной, например, по победам, потом по очкам
                desc(subq.c.total_wins),
                desc(subq.c.total_points),
                desc(subq.c.total_top5),
                asc(teams_table.c.team_name) # По имени для стабильности
            ).limit(page_size).offset(offset)

            standings_list = session.execute(standings_stmt).fetchall()
            logger.info(f"Возвращено {len(standings_list)} команд для страницы.")
            return standings_list, page, total_pages
        except Exception as e:
            logger.error(f"Ошибка получения рейтинга команд (season={season}, page={page}): {e}", exc_info=True)
            return [], 1, 1

def get_team_season_details(team_id: int, season: int, series_name: str = 'Cup'):
    """Получает детальную статистику команды за сезон (синхронно)."""
    logger.info(f"Запрос деталей команды: team_id={team_id}, season={season}, series='{series_name}'")
    required_tables = [teams_table, race_entries_table, races_table, series_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['Teams', 'RaceEntries', 'Races', 'Series'], required_tables) if table is None]
        logger.error(f"Одна или несколько таблиц не отражены для get_team_season_details: {', '.join(missing)}")
        return None

    with get_db_session() as session:
        try:
            series_id = get_series_id_by_name(session, series_name)
            if not series_id: return None

            team_name_stmt = select(teams_table.c.team_name).where(teams_table.c.team_id == team_id)
            team_name = session.execute(team_name_stmt).scalar_one_or_none()
            if not team_name:
                logger.warning(f"Команда с team_id={team_id} не найдена.")
                return None
            logger.info(f"Найдена команда: {team_name}")

            # Запрос агрегированной статистики для команды
            stats_stmt = select(
                func.count(race_entries_table.c.driver_id).label('entries'), # Считаем участия машин
                func.sum(race_entries_table.c.won_race).label('wins'),
                func.sum(case((race_entries_table.c.finish_position <= 5, 1), else_=0)).label('top5'),
                func.sum(case((race_entries_table.c.finish_position <= 10, 1), else_=0)).label('top10'),
                func.sum(func.coalesce(race_entries_table.c.laps_led, 0)).label('laps_led'),
                func.sum(func.coalesce(race_entries_table.c.laps_completed, 0)).label('laps_completed'),
                # Средние значения по всем машинам команды
                func.avg(cast(race_entries_table.c.start_position, Float)).label('avg_start'),
                func.avg(cast(race_entries_table.c.finish_position, Float)).label('avg_finish'),
                func.sum(func.coalesce(race_entries_table.c.points, 0)).label('points')
            ).select_from(race_entries_table
            ).join(races_table, race_entries_table.c.race_id == races_table.c.race_id
            ).where(
                (race_entries_table.c.team_id == team_id) &
                (races_table.c.season == season) &
                (races_table.c.series_id == series_id) &
                (race_entries_table.c.finish_position != None) & # Для корректного среднего финиша
                (race_entries_table.c.driver_id != None) # Убедимся что есть гонщик
                # Возможно, стоит добавить условие и для start_position != None
            )

            stats_result = session.execute(stats_stmt).fetchone()
            logger.info(f"Результат запроса статистики команды: {stats_result}")

            details = {'team_name': team_name, 'season': season, 'series_name': series_name}
            if stats_result and stats_result.entries is not None and stats_result.entries > 0:
                 details.update({
                    'entries': stats_result.entries or 0, 'wins': stats_result.wins or 0,
                    'top5': stats_result.top5 or 0, 'top10': stats_result.top10 or 0,
                    'laps_led': stats_result.laps_led or 0, 'laps_completed': stats_result.laps_completed or 0,
                    'avg_start': round(stats_result.avg_start, 1) if stats_result.avg_start else None,
                    'avg_finish': round(stats_result.avg_finish, 1) if stats_result.avg_finish else None,
                    'points': stats_result.points if stats_result.points is not None else 0
                })
            else:
                details.update({
                    'entries': 0, 'wins': 0, 'top5': 0, 'top10': 0, 'laps_led': 0,
                    'laps_completed': 0, 'avg_start': None, 'avg_finish': None, 'points': 0
                })
                logger.info(f"Участия для team_id={team_id}, season={season}, series={series_name} не найдены.")

            logger.info(f"Сформирован словарь деталей команды: {details}")
            return details
        except Exception as e:
            logger.error(f"Ошибка получения деталей команды (team_id={team_id}, season={season}): {e}", exc_info=True)
            return None

def get_manufacturer_season_stats(season: int, series_name: str = 'Cup'):
    """Получает агрегированную статистику по производителям за сезон (синхронно)."""
    logger.info(f"Запрос статистики производителей: season={season}, series='{series_name}'")
    required_tables = [race_entries_table, races_table, manufacturers_table, series_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['RaceEntries', 'Races', 'Manufacturers', 'Series'], required_tables) if table is None]
        logger.error(f"Одна или несколько таблиц не отражены для get_manufacturer_season_stats: {', '.join(missing)}")
        return []

    with get_db_session() as session:
        try:
            series_id = get_series_id_by_name(session, series_name)
            if not series_id:
                return []

            # Запрос агрегированной статистики
            stats_stmt = select(
                manufacturers_table.c.manufacturer_id,  # ✅ Добавлено
                manufacturers_table.c.manufacturer_name,
                func.sum(race_entries_table.c.won_race).label('wins'),
                func.sum(case((race_entries_table.c.finish_position <= 5, 1), else_=0)).label('top5'),
                func.sum(case((race_entries_table.c.finish_position <= 10, 1), else_=0)).label('top10'),
                func.sum(func.coalesce(race_entries_table.c.laps_led, 0)).label('laps_led'),
                func.count(race_entries_table.c.driver_id).label('entries')
            ).select_from(
                race_entries_table
            ).join(
                races_table, race_entries_table.c.race_id == races_table.c.race_id
            ).join(
                manufacturers_table, race_entries_table.c.manufacturer_id == manufacturers_table.c.manufacturer_id
            ).where(
                (races_table.c.season == season) &
                (races_table.c.series_id == series_id) &
                (race_entries_table.c.manufacturer_id != None) &
                (race_entries_table.c.driver_id != None)
            ).group_by(
                manufacturers_table.c.manufacturer_id,
                manufacturers_table.c.manufacturer_name
            ).order_by(
                desc('wins'),
                desc('top5'),
                asc(manufacturers_table.c.manufacturer_name)
            )

            results = session.execute(stats_stmt).mappings().all()
            logger.info(f"Найдена статистика для {len(results)} производителей.")
            return results

        except Exception as e:
            logger.error(f"Ошибка при получении статистики производителей (season={season}): {e}", exc_info=True)
            return []

# --- Функции для общей статистики (Адаптированные) ---
def get_overall_driver_stats(driver_id: int):
    """Получает общую статистику гонщика за все время (синхронно)."""
    logger.info(f"Запрос общей статистики для driver_id={driver_id}")
    required_tables = [drivers_table, race_entries_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['Drivers', 'RaceEntries'], required_tables) if table is None]
        logger.error(f"Одна или несколько таблиц не отражены для get_overall_driver_stats: {', '.join(missing)}")
        return None

    with get_db_session() as session:
        try:
            driver_name_stmt = select(drivers_table.c.driver_name).where(drivers_table.c.driver_id == driver_id)
            driver_name = session.execute(driver_name_stmt).scalar_one_or_none()
            if not driver_name:
                 logger.warning(f"Гонщик с driver_id={driver_id} не найден для общей статистики.")
                 return None

            stats_stmt = select(
                func.count(race_entries_table.c.race_id).label('races'),
                func.sum(race_entries_table.c.won_race).label('wins'),
                func.sum(case((race_entries_table.c.finish_position <= 5, 1), else_=0)).label('top5'),
                func.sum(case((race_entries_table.c.finish_position <= 10, 1), else_=0)).label('top10'),
                func.sum(func.coalesce(race_entries_table.c.laps_led, 0)).label('laps_led'),
                func.sum(func.coalesce(race_entries_table.c.laps_completed, 0)).label('laps_completed'),
                func.avg(cast(race_entries_table.c.start_position, Float)).label('avg_start'),
                func.avg(cast(race_entries_table.c.finish_position, Float)).label('avg_finish'),
                func.sum(func.coalesce(race_entries_table.c.points, 0)).label('points')
            ).select_from(race_entries_table
            ).where(
                (race_entries_table.c.driver_id == driver_id) &
                (race_entries_table.c.finish_position != None) # Учитываем только финишировавших
            )
            stats_result = session.execute(stats_stmt).fetchone()

            details = {'driver_name': driver_name, 'type': 'driver'} # Добавляем тип для возможного использования в GUI
            if stats_result and stats_result.races is not None and stats_result.races > 0:
                details.update({
                    'races': stats_result.races or 0, 'wins': stats_result.wins or 0,
                    'top5': stats_result.top5 or 0, 'top10': stats_result.top10 or 0,
                    'laps_led': stats_result.laps_led or 0, 'laps_completed': stats_result.laps_completed or 0,
                    'avg_start': round(stats_result.avg_start, 1) if stats_result.avg_start else None,
                    'avg_finish': round(stats_result.avg_finish, 1) if stats_result.avg_finish else None,
                    'points': stats_result.points if stats_result.points is not None else 0
                })
            else:
                 details.update({
                    'races': 0, 'wins': 0, 'top5': 0, 'top10': 0, 'laps_led': 0,
                    'laps_completed': 0, 'avg_start': None, 'avg_finish': None, 'points': 0
                 })
            return details
        except Exception as e:
            logger.error(f"Ошибка получения общей статистики гонщика (driver_id={driver_id}): {e}", exc_info=True)
            return None

def get_overall_team_stats(team_id: int):
    """Получает общую статистику команды за все время (синхронно)."""
    logger.info(f"Запрос общей статистики для team_id={team_id}")
    required_tables = [teams_table, race_entries_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['Teams', 'RaceEntries'], required_tables) if table is None]
        logger.error(f"Одна или несколько таблиц не отражены для get_overall_team_stats: {', '.join(missing)}")
        return None

    with get_db_session() as session:
        try:
            team_name_stmt = select(teams_table.c.team_name).where(teams_table.c.team_id == team_id)
            team_name = session.execute(team_name_stmt).scalar_one_or_none()
            if not team_name:
                logger.warning(f"Команда с team_id={team_id} не найдена для общей статистики.")
                return None

            stats_stmt = select(
                func.count(race_entries_table.c.driver_id).label('entries'),
                func.sum(race_entries_table.c.won_race).label('wins'),
                func.sum(case((race_entries_table.c.finish_position <= 5, 1), else_=0)).label('top5'),
                func.sum(case((race_entries_table.c.finish_position <= 10, 1), else_=0)).label('top10'),
                func.sum(func.coalesce(race_entries_table.c.laps_led, 0)).label('laps_led'),
                func.sum(func.coalesce(race_entries_table.c.laps_completed, 0)).label('laps_completed'),
                func.avg(cast(race_entries_table.c.start_position, Float)).label('avg_start'),
                func.avg(cast(race_entries_table.c.finish_position, Float)).label('avg_finish'),
                func.sum(func.coalesce(race_entries_table.c.points, 0)).label('points')
            ).select_from(race_entries_table
            ).where(
                (race_entries_table.c.team_id == team_id) &
                (race_entries_table.c.finish_position != None) &
                (race_entries_table.c.driver_id != None)
            )
            stats_result = session.execute(stats_stmt).fetchone()

            details = {'team_name': team_name, 'type': 'team'}
            if stats_result and stats_result.entries is not None and stats_result.entries > 0:
                details.update({
                    'entries': stats_result.entries or 0, 'wins': stats_result.wins or 0,
                    'top5': stats_result.top5 or 0, 'top10': stats_result.top10 or 0,
                    'laps_led': stats_result.laps_led or 0, 'laps_completed': stats_result.laps_completed or 0,
                    'avg_start': round(stats_result.avg_start, 1) if stats_result.avg_start else None,
                    'avg_finish': round(stats_result.avg_finish, 1) if stats_result.avg_finish else None,
                    'points': stats_result.points if stats_result.points is not None else 0
                })
            else:
                 details.update({
                    'entries': 0, 'wins': 0, 'top5': 0, 'top10': 0, 'laps_led': 0,
                    'laps_completed': 0, 'avg_start': None, 'avg_finish': None, 'points': 0
                 })
            return details
        except Exception as e:
            logger.error(f"Ошибка получения общей статистики команды (team_id={team_id}): {e}", exc_info=True)
            return None

def get_overall_manufacturer_stats(manufacturer_id: int):
    """Получает общую статистику производителя за все время (синхронно)."""
    logger.info(f"Запрос общей статистики для manufacturer_id={manufacturer_id}")
    required_tables = [manufacturers_table, race_entries_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['Manufacturers', 'RaceEntries'], required_tables) if table is None]
        logger.error(f"Одна или несколько таблиц не отражены для get_overall_manufacturer_stats: {', '.join(missing)}")
        return None

    with get_db_session() as session:
        try:
            manufacturer_name_stmt = select(manufacturers_table.c.manufacturer_name).where(manufacturers_table.c.manufacturer_id == manufacturer_id)
            manufacturer_name = session.execute(manufacturer_name_stmt).scalar_one_or_none()
            if not manufacturer_name:
                logger.warning(f"Производитель с manufacturer_id={manufacturer_id} не найден для общей статистики.")
                return None

            stats_stmt = select(
                func.count(race_entries_table.c.driver_id).label('entries'),
                func.sum(race_entries_table.c.won_race).label('wins'),
                func.sum(case((race_entries_table.c.finish_position <= 5, 1), else_=0)).label('top5'),
                func.sum(case((race_entries_table.c.finish_position <= 10, 1), else_=0)).label('top10'),
                func.sum(func.coalesce(race_entries_table.c.laps_led, 0)).label('laps_led')
            ).select_from(race_entries_table
            ).where(
                (race_entries_table.c.manufacturer_id == manufacturer_id) &
                (race_entries_table.c.driver_id != None)
            )
            stats_result = session.execute(stats_stmt).fetchone()

            details = {'manufacturer_name': manufacturer_name, 'type': 'manufacturer'}
            if stats_result and stats_result.entries is not None and stats_result.entries > 0:
                 details.update({
                    'entries': stats_result.entries or 0, 'wins': stats_result.wins or 0,
                    'top5': stats_result.top5 or 0, 'top10': stats_result.top10 or 0,
                    'laps_led': stats_result.laps_led or 0
                })
            else:
                 details.update({'entries': 0, 'wins': 0, 'top5': 0, 'top10': 0, 'laps_led': 0})
            return details
        except Exception as e:
            logger.error(f"Ошибка получения общей статистики производителя (manufacturer_id={manufacturer_id}): {e}", exc_info=True)
            return None

def get_driver_standings_progression(driver_id: int, season: int, series_id: int):
    """
    Получает прогресс набора очков гонщиком за сезон/серию.
    Возвращает список кортежей (race_num_in_season, cumulative_points) или пустой список.
    """
    logger.info(f"Запрос прогресса очков для driver_id={driver_id}, season={season}, series_id={series_id}")
    required_tables = [race_entries_table, races_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['RaceEntries', 'Races'], required_tables) if table is None]
        logger.error(f"Таблицы не отражены для get_driver_standings_progression: {', '.join(missing)}")
        return []

    with get_db_session() as session:
        try:
            # Определяем оконную функцию для кумулятивной суммы очков
            cumulative_points_window = over(
                func.sum(func.coalesce(race_entries_table.c.points, 0)),
                order_by=asc(races_table.c.race_num_in_season)
            )

            stmt = select(
                races_table.c.race_num_in_season,
                cumulative_points_window.label('cumulative_points') # Применяем оконную функцию
            ).select_from(race_entries_table
            ).join(races_table, race_entries_table.c.race_id == races_table.c.race_id
            ).where(
                (race_entries_table.c.driver_id == driver_id) &
                (races_table.c.season == season) &
                (races_table.c.series_id == series_id)
                # Не фильтруем по finish_position != None, т.к. даже за DNF могут дать очки
            ).order_by(asc(races_table.c.race_num_in_season)) # Сортируем для правильной кумуляции

            results = session.execute(stmt).fetchall()
            logger.info(f"Найдено {len(results)} точек прогресса очков для графика.")
            # Результат: [(1, 35), (2, 70), (3, 95), ...]
            return results
        except Exception as e:
            logger.error(f"Ошибка получения прогресса очков для графика: {e}", exc_info=True)
            return []

def get_team_race_results_for_season(team_id: int, season: int, series_id: int):
    """
    Получает средние результаты (старт/финиш) для команды за сезон/серию по гонкам.
    Возвращает список кортежей (race_num_in_season, avg_start_position, avg_finish_position) или пустой список.
    """
    logger.info(f"Запрос средних результатов гонок для team_id={team_id}, season={season}, series_id={series_id}")
    required_tables = [race_entries_table, races_table]
    if any(table is None for table in required_tables):
        missing = [name for name, table in zip(['RaceEntries', 'Races'], required_tables) if table is None]
        logger.error(f"Таблицы не отражены для get_team_race_results_for_season: {', '.join(missing)}")
        return []

    with get_db_session() as session:
        try:
            # Группируем по гонке и считаем средние значения
            stmt = select(
                races_table.c.race_num_in_season,
                func.avg(cast(race_entries_table.c.start_position, Float)).label('avg_start'),
                func.avg(cast(race_entries_table.c.finish_position, Float)).label('avg_finish')
            ).select_from(race_entries_table
            ).join(races_table, race_entries_table.c.race_id == races_table.c.race_id
            ).where(
                (race_entries_table.c.team_id == team_id) &
                (races_table.c.season == season) &
                (races_table.c.series_id == series_id) &
                (race_entries_table.c.finish_position != None) & # Учитываем только финишировавших
                (race_entries_table.c.start_position != None) # И тех, у кого есть стартовая позиция
            ).group_by(
                races_table.c.race_id, # Группируем по ID гонки
                races_table.c.race_num_in_season # И по номеру гонки в сезоне
            ).order_by(asc(races_table.c.race_num_in_season)) # Сортируем по номеру гонки

            results = session.execute(stmt).fetchall()
            logger.info(f"Найдено {len(results)} средних результатов по гонкам для команды.")
            # Результат: [(1, 15.5, 12.0), (2, 10.0, 8.5), ...]
            return results
        except Exception as e:
            logger.error(f"Ошибка получения средних результатов гонок команды для графика: {e}", exc_info=True)
            return []
        
def get_manufacturer_wins_by_season(manufacturer_id: int):
    """Возвращает количество побед производителя по каждому сезону."""
    if race_entries_table is None or races_table is None:
        logger.error("Таблицы race_entries или races не отражены.")
        return []

    with get_db_session() as session:
        try:
            stmt = select(
                races_table.c.season,
                func.count().label("wins")
            ).join_from(
                race_entries_table, races_table,
                race_entries_table.c.race_id == races_table.c.race_id
            ).where(
                (race_entries_table.c.manufacturer_id == manufacturer_id) &
                (race_entries_table.c.won_race == 1)
            ).group_by(
                races_table.c.season
            ).order_by(
                races_table.c.season
            )

            results = session.execute(stmt).all()
            return results

        except Exception as e:
            logger.error(f"Ошибка при получении побед производителя по сезонам: {e}", exc_info=True)
            return []

def get_all_drivers_list():
    """Получает список всех гонщиков (ID, Имя) для использования в UI."""
    logger.info("Запрос списка всех гонщиков...")
    if drivers_table is None:
        logger.error("Таблица Drivers не отражена.")
        return []
    with get_db_session() as session:
        try:
            stmt = select(
                drivers_table.c.driver_id,
                drivers_table.c.driver_name
            ).order_by(asc(drivers_table.c.driver_name))
            results = session.execute(stmt).fetchall()
            logger.info(f"Найдено {len(results)} гонщиков.")
            # Возвращаем список кортежей (id, name)
            return results
        except Exception as e:
            logger.error(f"Ошибка получения списка всех гонщиков: {e}", exc_info=True)
            return []

# --- Конец адаптации функций ---

if __name__ == '__main__':
    # Пример использования и проверки
    logging.basicConfig(level=logging.INFO) # Настроим логирование для теста
    first_race_id_cache = None
    # Определим переменные для ID в основной области видимости теста
    target_driver_id = None
    target_team_id = None
    target_driver_name = "William Byron" # Имя для поиска
    target_team_name = "Hendrick Motorsports" # Имя для поиска

    try:
        print("Запуск отражения схемы...")
        reflect_db_schema()
        print(f"Схема отражена. Последний сезон: {LATEST_SEASON}")

        if LATEST_SEASON:
            # --- Сначала получим нужные ID в одной сессии ---
            print(f"\nПолучение ID для тестов ({target_driver_name}, {target_team_name})...")
            with get_db_session() as id_session:
                target_driver_id = get_driver_id_by_name(id_session, target_driver_name)
                print(f"Найден ID для '{target_driver_name}': {target_driver_id}")
                target_team_id = get_team_id_by_name(id_session, target_team_name)
                print(f"Найден ID для '{target_team_name}': {target_team_id}")
            # --- ID получены, сессия закрыта ---

            # ... (Тесты get_races_for_season - можно оставить как есть) ...
            print(f"\nПроверка получения гонок для сезона {LATEST_SEASON}, Cup Series, стр. 1:")
            races, current_page, total_pages = get_races_for_season(LATEST_SEASON, 'Cup', page=1)
            print(f"Найдено гонок на стр {current_page}/{total_pages}: {len(races)}")
            if races:
                 first_race_id_cache = races[0].race_id
                 print(f"Первая гонка (ID={first_race_id_cache}): {races[0].race_name} на треке {races[0].track_name}")

            # ... (Тест get_race_details_and_results - можно оставить как есть) ...
            if first_race_id_cache:
                print(f"\nПроверка деталей и результатов для первой гонки (ID={first_race_id_cache}):")
                details, results = get_race_details_and_results(first_race_id_cache)
                if details and results:
                    print(f"Детали: {details.race_name}, Сезон: {details.season}, Трек: {details.track_name}")
                    print(f"Найдено результатов: {len(results)}")
                    print(f"Результат 1: Поз={results[0].finish_position}, Ст={results[0].start_position}, Имя={results[0].driver_name}")
                # ... (остальной вывод деталей)
                else:
                     print("Не удалось получить детали/результаты гонки.")


            # ... (Тест get_driver_standings - можно оставить как есть) ...
            print(f"\nПроверка рейтинга гонщиков для сезона {LATEST_SEASON}, Cup Series, стр. 1:")
            standings, current_page_s, total_pages_s = get_driver_standings(LATEST_SEASON, 'Cup', page=1)
            print(f"Найдено гонщиков на стр {current_page_s}/{total_pages_s}: {len(standings)}")
            # ... (вывод топ-2)

            # --- Исправленный тест для get_driver_season_details ---
            print(f"\nПроверка деталей сезона для гонщика '{target_driver_name}' (ID={target_driver_id}):")
            if target_driver_id:
                 driver_details = get_driver_season_details(target_driver_id, LATEST_SEASON, 'Cup')
                 if driver_details:
                     print(f"Имя: {driver_details.get('driver_name')}, Гонки: {driver_details.get('races')}, Победы: {driver_details.get('wins')}, Очки: {driver_details.get('points')}")
                     print(f"Топ5: {driver_details.get('top5')}, Топ10: {driver_details.get('top10')}, Ср.Старт: {driver_details.get('avg_start')}, Ср.Финиш: {driver_details.get('avg_finish')}")
                 else:
                     print(f"Не удалось получить детали сезона для гонщика ID={target_driver_id}.")
            else:
                 print(f"ID для '{target_driver_name}' не был найден, пропускаем тест деталей сезона.")

            # ... (Тест get_team_standings - можно оставить как есть) ...
            print(f"\nПроверка рейтинга команд для сезона {LATEST_SEASON}, Cup Series, стр. 1:")
            team_standings, current_page_t, total_pages_t = get_team_standings(LATEST_SEASON, 'Cup', page=1)
            print(f"Найдено команд на стр {current_page_t}/{total_pages_t}: {len(team_standings)}")
            # ... (вывод топ-2)

            # --- Исправленный тест для get_team_season_details ---
            print(f"\nПроверка деталей сезона для команды '{target_team_name}' (ID={target_team_id}):")
            if target_team_id:
                 team_details = get_team_season_details(target_team_id, LATEST_SEASON, 'Cup')
                 if team_details:
                     print(f"Имя: {team_details.get('team_name')}, Участия: {team_details.get('entries')}, Победы: {team_details.get('wins')}, Очки: {team_details.get('points')}")
                     print(f"Топ5: {team_details.get('top5')}, Топ10: {team_details.get('top10')}, Ср.Старт: {team_details.get('avg_start')}, Ср.Финиш: {team_details.get('avg_finish')}")
                 else:
                      print(f"Не удалось получить детали сезона для команды ID={target_team_id}.")
            else:
                 print(f"ID для '{target_team_name}' не был найден, пропускаем тест деталей сезона.")

            # ... (Тест get_manufacturer_season_stats - можно оставить как есть) ...
            print(f"\nПроверка статистики производителей для сезона {LATEST_SEASON}, Cup Series:")
            manu_stats = get_manufacturer_season_stats(LATEST_SEASON, 'Cup')
            print(f"Найдено производителей: {len(manu_stats)}")
            # ... (вывод топ-3)

        else:
             print("Не удалось определить последний сезон для тестов.")

    except Exception as e:
        print(f"Ошибка во время тестового запуска: {e}")

    # --- Добавляем тесты для overall функций ---
    print("\n--- Тесты общей статистики ---")
    target_driver_overall_name = "Kyle Busch" # Гонщик с долгой карьерой
    target_team_overall_name = "Joe Gibbs Racing"
    target_manu_overall_name = "Toyota"

    target_driver_overall_id = None
    target_team_overall_id = None
    target_manu_overall_id = None

    print(f"\nПолучение ID для тестов overall ({target_driver_overall_name}, {target_team_overall_name}, {target_manu_overall_name})...")
    with get_db_session() as id_session:
        target_driver_overall_id = get_driver_id_by_name(id_session, target_driver_overall_name)
        print(f"Найден ID для '{target_driver_overall_name}': {target_driver_overall_id}")
        target_team_overall_id = get_team_id_by_name(id_session, target_team_overall_name)
        print(f"Найден ID для '{target_team_overall_name}': {target_team_overall_id}")
        target_manu_overall_id = get_manufacturer_id_by_name(id_session, target_manu_overall_name)
        print(f"Найден ID для '{target_manu_overall_name}': {target_manu_overall_id}")

    if target_driver_overall_id:
        print(f"\nПроверка общей статистики для '{target_driver_overall_name}' (ID={target_driver_overall_id}):")
        overall_driver_stats = get_overall_driver_stats(target_driver_overall_id)
        if overall_driver_stats:
            print(f"Гонки: {overall_driver_stats.get('races')}, Победы: {overall_driver_stats.get('wins')}, Топ5: {overall_driver_stats.get('top5')}, Топ10: {overall_driver_stats.get('top10')}")
        else:
            print("Не удалось получить общую статистику.")
    else:
        print(f"ID для '{target_driver_overall_name}' не найден, пропускаем тест.")

    if target_team_overall_id:
        print(f"\nПроверка общей статистики для '{target_team_overall_name}' (ID={target_team_overall_id}):")
        overall_team_stats = get_overall_team_stats(target_team_overall_id)
        if overall_team_stats:
             print(f"Участия: {overall_team_stats.get('entries')}, Победы: {overall_team_stats.get('wins')}, Топ5: {overall_team_stats.get('top5')}, Топ10: {overall_team_stats.get('top10')}")
        else:
             print("Не удалось получить общую статистику.")
    else:
        print(f"ID для '{target_team_overall_name}' не найден, пропускаем тест.")

    if target_manu_overall_id:
        print(f"\nПроверка общей статистики для '{target_manu_overall_name}' (ID={target_manu_overall_id}):")
        overall_manu_stats = get_overall_manufacturer_stats(target_manu_overall_id)
        if overall_manu_stats:
             print(f"Участия: {overall_manu_stats.get('entries')}, Победы: {overall_manu_stats.get('wins')}, Топ5: {overall_manu_stats.get('top5')}, Топ10: {overall_manu_stats.get('top10')}")
        else:
             print("Не удалось получить общую статистику.")
    else:
        print(f"ID для '{target_manu_overall_name}' не найден, пропускаем тест.")

    print("\n--- Тест получения списка гонщиков ---")
    all_drivers = get_all_drivers_list()
    print(f"Получено гонщиков: {len(all_drivers)}")
    if len(all_drivers) > 5:
        print("Первые 5 гонщиков:")
        for driver_id, driver_name in all_drivers[:5]:
            print(f"  ID: {driver_id}, Имя: {driver_name}")
    elif all_drivers:
        print("Гонщики:")
        for driver_id, driver_name in all_drivers:
            print(f"  ID: {driver_id}, Имя: {driver_name}")
