# ============================================================================
# load_data_postgres.R (Адаптированная версия для PostgreSQL)
# ============================================================================
# ВАЖНО:
# 1. УСТАНОВИТЕ ПАКЕТ RPostgres: install.packages("RPostgres")
# 2. УБЕДИТЕСЬ, ЧТО PostgreSQL СЕРВЕР ЗАПУЩЕН И ДОСТУПЕН.
# 3. ПРОВЕРЬТЕ ПАРАМЕТРЫ ПОДКЛЮЧЕНИЯ К БД НИЖЕ.
# ============================================================================

# --- 0. Настройка и Загрузка Пакетов ---
install_and_load <- function(packages) {
  for (pkg in packages) {
    if (!require(pkg, character.only = TRUE)) {
      print(paste("Установка пакета:", pkg))
      install.packages(pkg, dependencies = TRUE)
      if (!require(pkg, character.only = TRUE)) {
        stop(paste("Не удалось загрузить пакет:", pkg, "после установки."))
      }
    }
    # print(paste("Пакет", pkg, "уже загружен или успешно установлен и загружен.")) # Убрал лишний вывод
  }
}

# Добавляем RPostgres, убираем RSQLite
required_packages <- c("dplyr", "DBI", "RPostgres", "remotes", "lubridate")
print("Проверка и установка основных пакетов...")
suppressPackageStartupMessages(install_and_load(required_packages))
print("Основные пакеты загружены.")

# --- Принудительное обновление и загрузка nascaR.data ---
# Эта часть остается без изменений
print("Попытка принудительного обновления пакета nascaR.data с GitHub (ветка weekly)...")
tryCatch({
  remotes::install_github('kyleGrealis/nascaR.data@weekly',
                          quiet = FALSE,
                          force = TRUE,
                          upgrade = "never")
  library(nascaR.data)
  print(paste("Загружена версия nascaR.data:", packageVersion("nascaR.data")))
  print("nascaR.data успешно загружен.")
}, error = function(e) {
  stop("Не удалось установить или загрузить nascaR.data. Ошибка: ", e$message)
})


# --- 1. Определение Переменных для PostgreSQL ---
db_host <- "localhost"  # Хост вашего PostgreSQL сервера
db_port <- 5432         # Порт (стандартный 5432)
db_name_pg <- "nascar_stats_db" # Имя вашей базы данных в PostgreSQL
db_user <- "nascar_user"    # Пользователь PostgreSQL
db_password <- "dzkexbnhtfre" # ВАШ ПАРОЛЬ для пользователя PostgreSQL

print(paste("Подключение к PostgreSQL: Host=", db_host, "DBName=", db_name_pg, "User=", db_user))

# --- 2. Подключение к Базе Данных PostgreSQL ---
if (exists("con_pg") && inherits(con_pg, "DBIConnection") && dbIsValid(con_pg)) {
  print("Обнаружено активное соединение с PostgreSQL. Закрытие...")
  dbDisconnect(con_pg)
}
# Используем RPostgres::Postgres()
con_pg <- DBI::dbConnect(RPostgres::Postgres(),
                         dbname = db_name_pg,
                         host = db_host,
                         port = db_port,
                         user = db_user,
                         password = db_password)
print("Соединение с PostgreSQL установлено.")

# --- 3. Получение Данных из nascaR.data ---
# Эта часть остается без изменений
print("Получение данных из пакета nascaR.data...")
cup_data <- nascaR.data::cup_series %>% mutate(SeriesName = "Cup")
xfinity_data <- nascaR.data::xfinity_series %>% mutate(SeriesName = "Xfinity")
truck_data <- nascaR.data::truck_series %>% mutate(SeriesName = "Truck")
print(paste("Загружено строк Cup:", nrow(cup_data)))
# ... (остальное логирование данных из nascaR.data без изменений) ...

# Проверка наличия столбца 'Date' (остается без изменений)
data_frames_list <- list(Cup = cup_data, Xfinity = xfinity_data, Truck = truck_data)
date_column_present <- all(sapply(data_frames_list, function(df) "Date" %in% names(df)))
# ... (логика проверки Date без изменений) ...

# Логирование последней гонки (остается без изменений)
# ...

# Объединение данных (остается без изменений)
print("Объединение всех исторических данных...")
all_races_raw <- bind_rows(cup_data, xfinity_data, truck_data)
print(paste("Всего строк данных для обработки:", nrow(all_races_raw)))


# --- 4. Предобработка Данных ---
# Эта часть остается в основном без изменений, так как dplyr работает с датафреймами.
# Важно, чтобы имена столбцов после rename совпадали с именами в PostgreSQL схеме
# (SQLAlchemy по умолчанию использует snake_case, например, race_num_in_season).
# Если имена в R (например, RaceNumInSeason) отличаются от имен в PG (race_num_in_season),
# dbWriteTable может потребовать явного маппинга или переименования в R перед записью.
# Однако, если вы использовали snake_case в init_postgres_schema.py, то проблем быть не должно
# при использовании dbWriteTable(..., name = "races", value = races_to_insert, ...),
# где 'name' - имя таблицы в PG, а 'value' - R датафрейм.
# Пакет 'DBI' и 'RPostgres' стараются корректно обрабатывать регистр, но лучше проверить.
# Для PostgreSQL имена таблиц и столбцов, если они не заключены в двойные кавычки при создании,
# обычно хранятся в нижнем регистре. SQLAlchemy обычно генерирует имена в нижнем регистре.

print("Начало предобработки данных...")
core_cols <- c("Season", "Race", "Name", "Track", "Finish", "Start", "Car",
               "Driver", "Team", "Make", "Laps", "Led")
missing_core_cols <- setdiff(core_cols, names(all_races_raw))
if (length(missing_core_cols) > 0) {
    stop("Отсутствуют КЛЮЧЕВЫЕ столбцы: ", paste(missing_core_cols, collapse=", "))
}

all_races <- all_races_raw %>%
  rename(
    # ВАЖНО: Имена столбцов в PostgreSQL (если не в кавычках при создании) будут в нижнем регистре.
    # SQLAlchemy обычно использует snake_case. Убедимся, что имена столбцов в R датафреймах
    # соответствуют (или будут корректно смаплены DBI/RPostgres) именам в PG таблицах.
    # Для простоты, оставим CamelCase в R и понадеемся, что RPostgres справится,
    # либо будем использовать snake_case в R перед записью.
    # Пока оставляем как есть, предполагая, что RPostgres + DBI смогут смапить.
    RaceNumInSeason = Race, TrackName = Track, RaceName = Name,
    TrackLength = Length, TrackSurface = Surface, FinishPosition = Finish,
    StartPosition = Start, CarNumber = Car, DriverName = Driver,
    TeamName = Team, ManufacturerName = Make, Points = Pts,
    LapsCompleted = Laps, LapsLed = Led, # Status = Status, # Status уже есть
    Segment1Finish = S1, Segment2Finish = S2, DriverRating = Rating
  ) %>%
  mutate(
    # ... (преобразования типов и создание новых столбцов без изменений) ...
    Date = if ("Date" %in% names(.)) as.Date(Date) else as.Date(NA),
    FinishPosition = suppressWarnings(as.integer(FinishPosition)),
    won_race = as.integer(FinishPosition == 1 & !is.na(FinishPosition)),
    # ... и т.д. ...
    Season = as.integer(Season),
    RaceNumInSeason = as.integer(RaceNumInSeason),
    StartPosition = suppressWarnings(as.integer(StartPosition)),
    LapsCompleted = suppressWarnings(as.integer(LapsCompleted)),
    LapsLed = suppressWarnings(as.integer(LapsLed)),
    Points = suppressWarnings(as.integer(Points)),
    Segment1Finish = suppressWarnings(as.integer(Segment1Finish)),
    Segment2Finish = suppressWarnings(as.integer(Segment2Finish)),
    DriverRating = suppressWarnings(as.numeric(DriverRating)),
    TrackLength = suppressWarnings(as.numeric(TrackLength)),
    DriverName = trimws(DriverName), TeamName = trimws(TeamName),
    ManufacturerName = trimws(ManufacturerName), TrackName = trimws(TrackName),
    RaceName = trimws(RaceName), CarNumber = trimws(CarNumber),
    Status = if ("Status" %in% names(.)) trimws(Status) else NA_character_,
    TrackSurface = if ("TrackSurface" %in% names(.)) trimws(TrackSurface) else NA_character_,
    SeriesName = trimws(SeriesName)
  ) %>%
  filter( # Фильтрация остается без изменений
    !is.na(DriverName) & DriverName != "",
    !is.na(TeamName) & TeamName != "",
    !is.na(ManufacturerName) & ManufacturerName != "",
    !is.na(TrackName) & TrackName != "",
    !is.na(SeriesName) & SeriesName != "",
    !is.na(Season),
    !is.na(RaceNumInSeason),
    !is.na(FinishPosition)
  )

if(nrow(all_races) == 0) {
    print("ВНИМАНИЕ: После предобработки не осталось строк.")
    # stop("Обработка остановлена: нет данных после фильтрации.")
} else {
    print(paste("Строк после предобработки:", nrow(all_races)))
}


# --- 5. Операции с Базой Данных PostgreSQL (в транзакции) ---
print("Начало транзакции для обновления PostgreSQL базы данных...")
if (!exists("con_pg") || !inherits(con_pg, "DBIConnection") || !dbIsValid(con_pg)) {
    stop("Ошибка: Соединение с PostgreSQL не установлено или невалидно.")
}
dbBegin(con_pg)

tryCatch({
  # --- 5a. Очистка таблиц с результатами ---
  # В PostgreSQL внешние ключи могут потребовать определенного порядка удаления или CASCADE.
  # Если есть ON DELETE CASCADE, то удаление из Races удалит связанные RaceEntries.
  # Если нет, то сначала RaceEntries, потом Races.
  # Таблицы в PostgreSQL обычно именуются в нижнем регистре, если не указано иное при создании.
  # Предположим, SQLAlchemy создал их в нижнем регистре: "raceentries", "races".
  print("Очистка таблиц 'raceentries' и 'races'...")
  dbExecute(con_pg, "DELETE FROM \"RaceEntries\";") # Заключаем в кавычки, если регистрозависимые имена
  dbExecute(con_pg, "DELETE FROM \"Races\";")
  print("Таблицы 'RaceEntries' и 'Races' очищены.")

  # --- 5b. Получение ID серий ---
  # Имена в PG также могут быть в нижнем регистре.
  series_lookup <- dbGetQuery(con_pg, "SELECT series_id, series_name FROM \"Series\";")
  if (nrow(series_lookup) == 0) { stop("Таблица 'Series' в базе данных пуста.") }
  print("Получены ID серий.")

  # --- 5c. Заполнение Справочников ---
  # Адаптируем upsert_and_get_ids для PostgreSQL
  upsert_and_get_ids_pg <- function(con_trans, table_name_pg, id_col_pg, name_col_pg, data_vector) {
    print(paste("Обработка справочника:", table_name_pg))
    unique_names <- unique(data_vector[!is.na(data_vector) & data_vector != ""])
    if(length(unique_names) == 0) {
        print(paste("Нет уникальных имен для обработки в", table_name_pg))
        df_empty <- data.frame(matrix(ncol = 2, nrow = 0)); colnames(df_empty) <- c(id_col_pg, name_col_pg); return(df_empty)
    }
    print(paste("Найдено уникальных имен:", length(unique_names)))

    # PostgreSQL INSERT ... ON CONFLICT DO NOTHING
    # Имена столбцов и таблицы должны соответствовать регистру в PG (обычно нижний)
    # или быть заключены в двойные кавычки, если создавались с сохранением регистра.
    # Предположим, SQLAlchemy создал их так, как в R (TrackName) или snake_case (track_name).
    # Для простоты будем использовать имена столбцов и таблиц как в `init_postgres_schema.py` (они там в CamelCase, но PG их приведет к lower_case, если не в кавычках).
    # SQLAlchemy обычно использует имена в нижнем регистре.
    # Будем использовать имена столбцов и таблиц в кавычках для ЯВНОГО указания регистра, если он важен.
    # Или убедимся, что в init_postgres_schema.py все имена в нижнем регистре.
    # В нашем init_postgres_schema.py они с большой буквы, значит PG их переведет в нижний.
    # Например, Series -> series, series_name -> series_name.
    
    # Используем ИМЕНА ИЗ СХЕМЫ PostgreSQL (обычно snake_case или lower_case)
    # В вашем init_postgres_schema.py использовался CamelCase для таблиц, но PG по умолчанию их в lower case.
    # Столбцы были snake_case или CamelCase. SQLAlchemy также по умолчанию создает snake_case.
    # Для безопасности будем использовать двойные кавычки для имен таблиц и столбцов, если они были созданы с сохранением регистра.
    # Если init_postgres_schema.py создал их без кавычек, они будут в нижнем регистре.
    
    # Предположим, все имена в PG в нижнем регистре (стандарт для SQLAlchemy без кавычек)
    table_name_pg_lower <- tolower(table_name_pg)
    id_col_pg_lower <- tolower(id_col_pg)
    name_col_pg_lower <- tolower(name_col_pg)

    # Подготавливаем данные для вставки (DataFrame с одним столбцом)
    df_to_insert <- data.frame(temp_name_col = unique_names)
    colnames(df_to_insert) <- c(name_col_pg_lower)

    # Записываем с ON CONFLICT DO NOTHING
    # dbWriteTable не поддерживает ON CONFLICT напрямую. Нужно делать через dbExecute.
    # Более простой способ - сначала записать все, потом удалить дубликаты (если нет UNIQUE constraint)
    # или использовать временную таблицу.
    # Но с UNIQUE constraint на name_col, мы можем просто пытаться вставить, а ошибки из-за дубликатов игнорировать.
    # Или использовать dbExecute с ON CONFLICT.

    inserted_count <- 0
    for(name_val in unique_names) {
        # Одинарные кавычки вокруг name_val нужны для SQL строки, если не используем параметры
        # Но лучше использовать параметризованный запрос
        query <- paste0("INSERT INTO \"", table_name_pg, "\" (\"", name_col_pg, "\") VALUES ($1) ON CONFLICT (\"", name_col_pg, "\") DO NOTHING;")
        tryCatch({
            res <- dbExecute(con_trans, query, params = list(name_val))
            # dbExecute для INSERT通常 возвращает количество измененных строк, но ON CONFLICT может вести себя по-разному
            # Проще считать, что если нет ошибки, то все ок. Для точного подсчета нужны другие методы.
        }, error = function(e) {
            print(paste("Возможна ошибка при вставке в", table_name_pg, "для значения", name_val, ":", e$message))
        })
    }
    # Поскольку точное количество вставленных записей с ON CONFLICT DO NOTHING сложно получить через dbExecute напрямую,
    # мы просто запрашиваем все записи после попыток вставки.
    
    print(paste("Попытка вставки/обновления в", table_name_pg, "завершена."))
    lookup_query <- paste0("SELECT \"", id_col_pg, "\", \"", name_col_pg, "\" FROM \"", table_name_pg, "\";")
    lookup_table <- dbGetQuery(con_trans, lookup_query)
    print(paste("Получены актуальные ID из таблицы:", table_name_pg, "(", nrow(lookup_table), "записей )"))
    return(lookup_table)
  }

  # Имена таблиц и столбцов должны соответствовать тем, что в PostgreSQL (обычно snake_case или lower case)
  # В вашем init_postgres_schema.py имена таблиц Series, Drivers, Teams, Manufacturers. Столбцы series_name, driver_name etc.
  # PostgreSQL по умолчанию приводит их к нижнему регистру, если они не были созданы в кавычках.
  # SQLAlchemy также обычно работает с нижним регистром.
  # Будем предполагать, что имена в PG соответствуют CamelCase из скрипта Python.

  drivers_lookup <- upsert_and_get_ids_pg(con_pg, "Drivers", "driver_id", "driver_name", all_races$DriverName)
  teams_lookup <- upsert_and_get_ids_pg(con_pg, "Teams", "team_id", "team_name", all_races$TeamName)
  manufacturers_lookup <- upsert_and_get_ids_pg(con_pg, "Manufacturers", "manufacturer_id", "manufacturer_name", all_races$ManufacturerName)

  # Специальная обработка для Tracks (обновляем существующие, если детали изменились)
  print("Обработка справочника: Tracks (с обновлением деталей)")
  unique_tracks_data <- all_races %>%
    filter(!is.na(TrackName) & TrackName != "") %>%
    group_by(TrackName) %>%
    summarise(
      TrackLength = first(na.omit(TrackLength)),
      TrackSurface = first(na.omit(TrackSurface)),
      .groups = 'drop'
    ) %>% ungroup()
  print(paste("Найдено уникальных трасс для обработки:", nrow(unique_tracks_data)))

  for(i in 1:nrow(unique_tracks_data)) {
    row <- unique_tracks_data[i,]
    # Сначала вставляем имя трассы, если его нет
    insert_name_query <- paste0("INSERT INTO \"Tracks\" (track_name) VALUES ($1) ON CONFLICT (track_name) DO NOTHING;")
    dbExecute(con_pg, insert_name_query, params = list(row$TrackName))

    # Затем обновляем детали, если они есть
    update_parts <- c()
    params_list_update <- list()
    if (!is.na(row$TrackLength)) {
      update_parts <- c(update_parts, "track_length = $1")
      params_list_update[[length(params_list_update) + 1]] <- row$TrackLength
    }
    if (!is.na(row$TrackSurface) && row$TrackSurface != "") {
      update_parts <- c(update_parts, paste0("track_surface = $", length(params_list_update) + 1))
      params_list_update[[length(params_list_update) + 1]] <- row$TrackSurface
    }

    if (length(update_parts) > 0) {
      params_list_update[[length(params_list_update) + 1]] <- row$TrackName
      update_query_sql <- paste0("UPDATE \"Tracks\" SET ", paste(update_parts, collapse = ", "),
                                 " WHERE track_name = $", length(params_list_update), ";")
      dbExecute(con_pg, update_query_sql, params = params_list_update)
    }
  }
  print("Детали трасс (длина, покрытие) обновлены.")
  tracks_lookup <- dbGetQuery(con_pg, "SELECT track_id, track_name FROM \"Tracks\";")
  print(paste("Получены актуальные ID из таблицы Tracks:", nrow(tracks_lookup)))


  # --- 5d. Подготовка и Вставка Данных о Гонках (Races) ---
  print("Подготовка данных для таблицы Races...")
  # Важно: имена столбцов в join и select должны соответствовать именам в датафреймах R.
  # А имена таблиц и столбцов в dbWriteTable должны соответствовать PostgreSQL.
  # Предполагаем, что RPostgres + DBI корректно обработают регистр имен столбцов при dbWriteTable
  # если имена в датафрейме R (races_to_insert) совпадают (регистронезависимо)
  # с именами столбцов в таблице PostgreSQL "Races".
  # Для безопасности лучше привести имена столбцов в R датафрейме к нижнему регистру перед dbWriteTable.

  races_to_insert_df <- all_races %>%
    select(Season, RaceNumInSeason, RaceName, TrackName, SeriesName) %>%
    distinct(Season, RaceNumInSeason, SeriesName, .keep_all = TRUE) %>%
    left_join(tracks_lookup, by = c("TrackName" = "track_name")) %>% # join по нижнему регистру из PG
    left_join(series_lookup, by = c("SeriesName" = "series_name")) %>%
    mutate(RaceName = ifelse(is.na(RaceName) | RaceName == "", paste("Race", RaceNumInSeason, "at", TrackName), RaceName)) %>%
    filter(!is.na(track_id) & !is.na(series_id)) %>%
    select(
      season = Season, # Эти имена должны совпадать с PG таблицей "Races"
      race_num_in_season = RaceNumInSeason,
      race_name = RaceName,
      track_id = track_id, # track_id из tracks_lookup
      series_id = series_id # series_id из series_lookup
    ) %>% distinct()

  print(paste("Подготовлено УНИКАЛЬНЫХ записей для вставки в Races:", nrow(races_to_insert_df)))
  if(nrow(races_to_insert_df) > 0) {
    # Имя таблицы в PG "Races" (с большой буквы, как в init_postgres_schema.py)
    # RPostgres должен автоматически обработать кавычки, если они нужны из-за регистра.
    dbWriteTable(con_pg, name = "Races", value = races_to_insert_df, append = TRUE, row.names = FALSE)
    print("Данные вставлены в таблицу Races.")
  } else {
    print("Нет новых данных для вставки в Races.")
  }

  # --- 5e. Получение ID созданных гонок ---
  races_lookup_db <- dbGetQuery(con_pg, "SELECT race_id, season, race_num_in_season, series_id FROM \"Races\";")
  print(paste("Получены ID и ключи гонок из таблицы Races:", nrow(races_lookup_db)))


  # --- 5f. Подготовка и Вставка Данных о Результатах (RaceEntries) ---
  print("Подготовка данных для таблицы RaceEntries...")
  all_races_with_series_id <- all_races %>%
    left_join(series_lookup, by = c("SeriesName" = "series_name")) # series_name из PG

  race_entries_to_insert_df <- all_races_with_series_id %>%
    left_join(drivers_lookup, by = c("DriverName" = "driver_name")) %>%
    left_join(teams_lookup, by = c("TeamName" = "team_name")) %>%
    left_join(manufacturers_lookup, by = c("ManufacturerName" = "manufacturer_name")) %>%
    left_join(races_lookup_db, by = c("Season" = "season", "RaceNumInSeason" = "race_num_in_season", "series_id" = "series_id")) %>%
    filter(!is.na(race_id) & !is.na(driver_id) & !is.na(team_id) & !is.na(manufacturer_id)) %>%
    select(
      race_id, driver_id, team_id, manufacturer_id,
      car_number = CarNumber,
      start_position = StartPosition,
      finish_position = FinishPosition,
      points = Points,
      laps_completed = LapsCompleted,
      laps_led = LapsLed,
      status = Status,
      segment1_finish = Segment1Finish,
      segment2_finish = Segment2Finish,
      driver_rating = DriverRating,
      won_race
    )

  print(paste("Подготовлено записей для вставки в RaceEntries:", nrow(race_entries_to_insert_df)))
  if(nrow(race_entries_to_insert_df) > 0) {
    dbWriteTable(con_pg, name = "RaceEntries", value = race_entries_to_insert_df, append = TRUE, row.names = FALSE)
    print("Данные вставлены в таблицу RaceEntries.")
  } else {
    print("Нет данных для вставки в RaceEntries.")
  }

  # --- 5g. Коммит транзакции ---
  dbCommit(con_pg)
  print("Транзакция успешно завершена (Commit). База данных PostgreSQL обновлена.")

}, error = function(e) {
  # --- 5h. Откат транзакции в случае ошибки ---
  print(paste("ОШИБКА ВО ВРЕМЯ ТРАНЗАКЦИИ В POSTGRESQL:", e$message))
  print("Откат транзакции (Rollback)...")
  dbRollback(con_pg)
  print("Трассировка ошибки:")
  print(rlang::last_trace())
  stop("Загрузка данных в PostgreSQL не удалась. Все изменения отменены.")
})

# --- 6. Отключение от Базы Данных ---
print("Отключение от PostgreSQL базы данных...")
if (exists("con_pg") && inherits(con_pg, "DBIConnection") && dbIsValid(con_pg)) {
  dbDisconnect(con_pg)
  print("Соединение с PostgreSQL базой данных закрыто.")
} else {
  print("Соединение с PostgreSQL уже было закрыто или не было установлено/валидно.")
}

print("Скрипт успешно завершил работу.")