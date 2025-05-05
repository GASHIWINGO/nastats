# ============================================================================
# ВАЖНО: ПЕРЕД ЗАПУСКОМ СКРИПТА В VS CODE
# ============================================================================
# 1. ПЕРЕЗАПУСТИТЕ R ТЕРМИНАЛ: Чтобы гарантировать успешное обновление
#    пакета nascaR.data, обязательно перезапустите R сессию/терминал
#    в VS Code перед запуском этого скрипта. Иначе обновление может
#    быть пропущено с сообщением "package 'nascaR.data' is in use".
#    (В VS Code: Откройте Command Palette (Ctrl+Shift+P) и введите 'R: Restart Session')
# 2. RTOOLS: Вы можете увидеть предупреждение о необходимости Rtools.
#    Для Windows рекомендуется их установить с сайта CRAN для полной
#    совместимости при сборке пакетов из исходников, но скрипт МОЖЕТ
#    отработать и без них, если для nascaR.data доступна бинарная версия.
# 3. ФАЙЛ БД: Убедитесь, что файл 'nascar_stats.db', созданный Python
#    скриптом, находится в ТОЙ ЖЕ ПАПКЕ, что и этот R скрипт.
# ============================================================================

# --- 0. Настройка и Загрузка Пакетов ---
install_and_load <- function(packages) {
  for (pkg in packages) {
    # Проверяем, установлен ли пакет, перед попыткой загрузки
    if (!require(pkg, character.only = TRUE)) {
      print(paste("Установка пакета:", pkg))
      install.packages(pkg, dependencies = TRUE)
      # Повторная попытка загрузки после установки
      if (!require(pkg, character.only = TRUE)) {
        stop(paste("Не удалось загрузить пакет:", pkg, "после установки."))
      }
      print(paste("Пакет", pkg, "успешно установлен и загружен."))
    } else {
      # Пакет уже загружен, сообщаем об этом
      print(paste("Пакет", pkg, "уже загружен."))
    }
  }
}

required_packages <- c("dplyr", "DBI", "RSQLite", "remotes", "lubridate")
print("Проверка и установка основных пакетов...")
suppressPackageStartupMessages(install_and_load(required_packages))
print("Основные пакеты загружены.")

# --- Принудительное обновление и загрузка nascaR.data ---
print("Попытка принудительного обновления пакета nascaR.data с GitHub (ветка weekly)...")
# Напоминание: Перезапустите R сессию, если видите ошибку 'package in use'!
tryCatch({
  remotes::install_github('kyleGrealis/nascaR.data@weekly',
                          quiet = FALSE, # Показываем вывод установки
                          force = TRUE,  # Принудительная попытка
                          upgrade = "never") # Не обновляем зависимости, чтобы ускорить
  # Загружаем пакет после попытки установки/обновления
  library(nascaR.data)
  # Проверяем версию пакета (опционально, для диагностики)
  print(paste("Загружена версия nascaR.data:", packageVersion("nascaR.data")))
  print("nascaR.data успешно загружен (или использована существующая версия, если обновление не удалось).")
}, error = function(e) {
  stop("Не удалось установить или загрузить nascaR.data. Ошибка: ", e$message)
})


# --- 1. Определение Переменных ---
# Файл БД должен быть в той же папке, что и скрипт R
db_name <- "nascar_stats.db"
db_path <- db_name # Указываем имя файла напрямую
print(paste("Путь к базе данных:", db_path))

# Проверка существования файла БД перед подключением
if (!file.exists(db_path)) {
    stop("Файл базы данных '", db_path, "' не найден в текущей директории. ",
         "Убедитесь, что Python скрипт для создания БД был запущен успешно и файл находится рядом с R скриптом.")
}

# --- 2. Подключение к Базе Данных ---
print(paste("Подключение к SQLite базе данных:", db_path))
if (exists("con") && inherits(con, "DBIConnection") && dbIsValid(con)) {
  print("Обнаружено активное соединение с БД. Закрытие...")
  dbDisconnect(con)
}
con <- DBI::dbConnect(RSQLite::SQLite(), dbname = db_path)
print("Соединение с БД установлено.")

# --- 3. Получение Данных из nascaR.data ---
print("Получение данных из пакета nascaR.data...")
cup_data <- nascaR.data::cup_series %>% mutate(SeriesName = "Cup")
xfinity_data <- nascaR.data::xfinity_series %>% mutate(SeriesName = "Xfinity")
truck_data <- nascaR.data::truck_series %>% mutate(SeriesName = "Truck")
print(paste("Загружено строк Cup:", nrow(cup_data)))
print(paste("Загружено строк Xfinity:", nrow(xfinity_data)))
print(paste("Загружено строк Truck:", nrow(truck_data)))

# Проверка наличия столбца 'Date' после загрузки данных (важно!)
data_frames_list <- list(Cup = cup_data, Xfinity = xfinity_data, Truck = truck_data)
date_column_present <- all(sapply(data_frames_list, function(df) "Date" %in% names(df)))

if (!date_column_present) {
    print("ВНИМАНИЕ: Столбец 'Date' отсутствует в данных из пакета nascaR.data.")
    print("Возможно, пакет не обновился или в данных ветки 'weekly' его нет.")
    print("Скрипт продолжит работу, но фильтрация по дате не будет применена.")
    # Если Date критически важен, можно остановить скрипт здесь:
    # stop("Критическая ошибка: Столбец 'Date' отсутствует в исходных данных.")
} else {
    print("Столбец 'Date' присутствует в загруженных данных.")
}


# --- Логирование последней гонки по дивизионам ---
print("--- Логирование последней загруженной гонки по дивизионам ---")
current_season_log <- lubridate::year(lubridate::today())
print(paste("Анализ данных за сезон:", current_season_log))

log_last_race <- function(race_data, series_name) {
  print(paste("--- Проверка данных для серии:", series_name, "---"))
  season_data <- race_data %>%
    filter(Season == current_season_log, !is.na(Race))

  if (nrow(season_data) > 0) {
    last_race_info <- season_data %>%
      slice_max(order_by = Race, n = 1, with_ties = FALSE)

    if (nrow(last_race_info) > 0) {
      date_info <- if ("Date" %in% names(last_race_info) && !is.na(last_race_info$Date)) {
          # Пытаемся отформатировать дату, используем tryCatch на всякий случай
          tryCatch({
              paste0(" (", format(as.Date(last_race_info$Date), "%Y-%m-%d"), ")")
          }, error = function(e) {" (дата ?)"}) # Если ошибка форматирования
      } else { "" }
      msg <- paste0("✅ [", series_name, "] Последняя гонка в данных: #", last_race_info$Race,
                     " - ", last_race_info$Name, " @ ", last_race_info$Track, date_info)
       print(msg)
    } else {
       print(paste("⚠️ [", series_name, "] Не найдено гонок с номером в данных за", current_season_log))
    }
  } else {
    print(paste("ℹ️ [", series_name, "] Нет данных о гонках за", current_season_log, "в загруженных данных."))
  }
}

log_last_race(cup_data, "Cup")
log_last_race(xfinity_data, "Xfinity")
log_last_race(truck_data, "Truck")

print("--- Завершение логирования последних гонок ---")


# --- Объединение ВСЕХ данных для дальнейшей обработки ---
print("Объединение всех исторических данных...")
all_races_raw <- bind_rows(cup_data, xfinity_data, truck_data)
print(paste("Всего строк данных для обработки:", nrow(all_races_raw)))

# --- 4. Предобработка Данных ---
print("Начало предобработки данных...")

# Проверяем наличие ключевых столбцов, которые используются в rename/mutate
# Если их нет, скрипт, скорее всего, упадет дальше - это индикатор проблемы с данными
core_cols <- c("Season", "Race", "Name", "Track", "Finish", "Start", "Car",
               "Driver", "Team", "Make", "Laps", "Led") # Минимальный набор
missing_core_cols <- setdiff(core_cols, names(all_races_raw))
if (length(missing_core_cols) > 0) {
    stop("Отсутствуют КЛЮЧЕВЫЕ столбцы в исходных данных: ", paste(missing_core_cols, collapse=", "),
         ". Проверьте версию пакета nascaR.data или его целостность.")
}

all_races <- all_races_raw %>%
  # Шаг 1: Переименование столбцов
  rename(
    RaceNumInSeason = Race, TrackName = Track, RaceName = Name,
    # Используем .data[[ ]] для необязательных столбцов, если они могут отсутствовать
    # Но проще проверить их наличие до этого шага
    TrackLength = Length, TrackSurface = Surface, FinishPosition = Finish,
    StartPosition = Start, CarNumber = Car, DriverName = Driver,
    TeamName = Team, ManufacturerName = Make, Points = Pts,
    LapsCompleted = Laps, LapsLed = Led, Status = Status,
    Segment1Finish = S1, Segment2Finish = S2, DriverRating = Rating
  ) %>%
  # Шаг 2: Преобразование типов и создание новых столбцов
  mutate(
    # Преобразуем дату, если она есть
    Date = if ("Date" %in% names(.)) as.Date(Date) else as.Date(NA),

    # Числовые преобразования с подавлением предупреждений (станут NA при ошибке)
    FinishPosition = suppressWarnings(as.integer(FinishPosition)),
    won_race = as.integer(FinishPosition == 1 & !is.na(FinishPosition)),
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

    # Очистка текстовых полей (безопасно, если столбец есть)
    DriverName = trimws(DriverName), TeamName = trimws(TeamName),
    ManufacturerName = trimws(ManufacturerName), TrackName = trimws(TrackName),
    RaceName = trimws(RaceName), CarNumber = trimws(CarNumber),
    Status = if ("Status" %in% names(.)) trimws(Status) else NA_character_, # Проверка необязательных
    TrackSurface = if ("TrackSurface" %in% names(.)) trimws(TrackSurface) else NA_character_,
    SeriesName = trimws(SeriesName) # Должен быть всегда из mutate выше
  ) %>%
  # Шаг 3: Фильтрация строк
  # Убрали фильтр !is.na(Date), т.к. он вызывал проблемы
  filter(
    !is.na(DriverName) & DriverName != "",
    !is.na(TeamName) & TeamName != "",
    !is.na(ManufacturerName) & ManufacturerName != "",
    !is.na(TrackName) & TrackName != "",
    !is.na(SeriesName) & SeriesName != "",
    !is.na(Season),
    !is.na(RaceNumInSeason),
    !is.na(FinishPosition) # Важно оставить только финишировавших
  )

# Проверяем, остались ли строки после фильтрации
if(nrow(all_races) == 0) {
    print("ВНИМАНИЕ: После предобработки и фильтрации не осталось строк данных.")
    print("Возможные причины: проблемы с исходными данными или слишком строгие фильтры.")
    # Можно остановить скрипт, если это критично
    # stop("Обработка остановлена: нет данных после фильтрации.")
} else {
    print(paste("Строк после предобработки и фильтрации:", nrow(all_races)))
}


# --- 5. Операции с Базой Данных (в транзакции) ---
print("Начало транзакции для обновления базы данных...")
# Проверка соединения перед началом транзакции
if (!exists("con") || !inherits(con, "DBIConnection") || !dbIsValid(con)) {
    stop("Ошибка: Соединение с базой данных не установлено или невалидно перед началом транзакции.")
}
dbBegin(con)

tryCatch({
  # --- 5a. Очистка таблиц с результатами ---
  print("Очистка таблиц RaceEntries и Races...")
  dbExecute(con, "DELETE FROM RaceEntries;")
  dbExecute(con, "DELETE FROM Races;")
  print("Таблицы RaceEntries и Races очищены.")

  # --- 5b. Получение ID серий ---
  series_lookup <- dbGetQuery(con, "SELECT series_id, series_name FROM Series;")
  if (nrow(series_lookup) == 0) { stop("Таблица 'Series' в базе данных пуста.") }
  print("Получены ID серий.")

  # --- 5c. Заполнение Справочников (INSERT OR IGNORE) ---
  upsert_and_get_ids <- function(con_trans, table_name, id_col, name_col, data_vector) {
    # ... (код функции без изменений) ...
     print(paste("Обработка справочника:", table_name))
    unique_names <- unique(data_vector[!is.na(data_vector) & data_vector != ""])
    if(length(unique_names) == 0) {
        print(paste("Нет уникальных имен для обработки в", table_name))
        df_empty <- data.frame(matrix(ncol = 2, nrow = 0)); colnames(df_empty) <- c(id_col, name_col); return(df_empty)
    }
    print(paste("Найдено уникальных имен:", length(unique_names)))
    query <- paste0("INSERT OR IGNORE INTO ", table_name, " (", name_col, ") VALUES (?);")
    inserted_count <- 0
    for(name in unique_names) {
      tryCatch({ res <- dbExecute(con_trans, query, params = list(name)); inserted_count <- inserted_count + res }, error = function(e) {})
    }
    print(paste("Добавлено новых записей в", table_name, ":", inserted_count))
    lookup_query <- paste("SELECT", id_col, ",", name_col, "FROM", table_name)
    lookup_table <- dbGetQuery(con_trans, lookup_query)
    print(paste("Получены актуальные ID из таблицы:", table_name, "(", nrow(lookup_table), "записей )"))
    return(lookup_table)
  }
  drivers_lookup <- upsert_and_get_ids(con, "Drivers", "driver_id", "driver_name", all_races$DriverName)
  teams_lookup <- upsert_and_get_ids(con, "Teams", "team_id", "team_name", all_races$TeamName)
  manufacturers_lookup <- upsert_and_get_ids(con, "Manufacturers", "manufacturer_id", "manufacturer_name", all_races$ManufacturerName)

  # --- Специальная обработка для Tracks ---
  print("Обработка справочника: Tracks (с обновлением деталей)")
  # ... (код обработки Tracks без изменений) ...
   unique_tracks_data <- all_races %>%
    filter(!is.na(TrackName) & TrackName != "") %>% group_by(TrackName) %>%
    summarise( TrackLength = first(na.omit(TrackLength)), TrackSurface = first(na.omit(TrackSurface)), .groups = 'drop' ) %>% ungroup()
  print(paste("Найдено уникальных трасс для обработки:", nrow(unique_tracks_data)))
  track_names_to_insert <- unique_tracks_data %>% distinct(TrackName)
  insert_track_name_query <- "INSERT OR IGNORE INTO Tracks (track_name) VALUES (?);"
  inserted_track_count <- 0
  for(t_name in track_names_to_insert$TrackName) { res <- dbExecute(con, insert_track_name_query, params = list(t_name)); inserted_track_count <- inserted_track_count + res }
  print(paste("Добавлено новых имен трасс:", inserted_track_count))
  update_track_details_query <- "UPDATE Tracks SET track_length = ?, track_surface = ? WHERE track_name = ?;"
  for(i in 1:nrow(unique_tracks_data)) {
    row <- unique_tracks_data[i, ]; params_list <- list(); update_clause <- c()
    if (!is.na(row$TrackLength)) { update_clause <- c(update_clause, "track_length = ?"); params_list <- c(params_list, row$TrackLength) }
    if (!is.na(row$TrackSurface) & row$TrackSurface != "") { update_clause <- c(update_clause, "track_surface = ?"); params_list <- c(params_list, row$TrackSurface) }
    if (length(update_clause) > 0) {
      params_list <- c(params_list, row$TrackName); query_sql <- paste("UPDATE Tracks SET", paste(update_clause, collapse=", "), "WHERE track_name = ?")
      res <- dbExecute(con, query_sql, params = params_list)
    }
  }
  print("Детали трасс (длина, покрытие) обновлены.")
  tracks_lookup <- dbGetQuery(con, "SELECT track_id, track_name FROM Tracks"); print(paste("Получены актуальные ID из таблицы Tracks:", nrow(tracks_lookup)))

  # --- 5d. Подготовка и Вставка Данных о Гонках (Races) ---
  print("Подготовка данных для таблицы Races...")
  # ... (код подготовки Races без изменений - Date не используется) ...
  tracks_lookup_join <- tracks_lookup %>% rename(TrackName = track_name)
  series_lookup_join <- series_lookup %>% rename(SeriesName = series_name)
  races_to_insert <- all_races %>%
    select(Season, RaceNumInSeason, RaceName, TrackName, SeriesName) %>%
    distinct(Season, RaceNumInSeason, SeriesName, .keep_all = TRUE) %>%
    left_join(tracks_lookup_join, by = "TrackName") %>%
    left_join(series_lookup_join, by = "SeriesName") %>%
    mutate(RaceName = ifelse(is.na(RaceName) | RaceName == "", paste("Race", RaceNumInSeason, "at", TrackName), RaceName)) %>%
    rename(season = Season, race_num_in_season = RaceNumInSeason, race_name = RaceName) %>%
    select(season, race_num_in_season, race_name, track_id, series_id) %>%
    filter(!is.na(track_id) & !is.na(series_id)) %>% distinct()
  print(paste("Подготовлено УНИКАЛЬНЫХ записей для вставки в Races:", nrow(races_to_insert)))
  if(nrow(races_to_insert) > 0) { dbWriteTable(con, "Races", races_to_insert, append = TRUE, row.names = FALSE); print("Данные вставлены в таблицу Races.") } else { print("Нет новых данных для вставки в Races.") }


  # --- 5e. Получение ID созданных гонок ---
  races_lookup_db <- dbGetQuery(con, "SELECT race_id, season, race_num_in_season, series_id FROM Races;")
  print(paste("Получены ID и ключи гонок из таблицы Races:", nrow(races_lookup_db)))
  # Убрали проверку на 0 строк здесь, т.к. могут быть запуски без новых гонок
  # if (nrow(races_lookup_db) == 0 && nrow(all_races) > 0) { stop("Не удалось получить ID гонок из базы данных после вставки.") }

  # --- 5f. Подготовка и Вставка Данных о Результатах (RaceEntries) ---
  print("Подготовка данных для таблицы RaceEntries...")
  # ... (код подготовки RaceEntries без изменений - Date не используется для join) ...
   drivers_lookup_join <- drivers_lookup %>% rename(DriverName = driver_name)
  teams_lookup_join <- teams_lookup %>% rename(TeamName = team_name)
  manufacturers_lookup_join <- manufacturers_lookup %>% rename(ManufacturerName = manufacturer_name)
  all_races_with_series_id <- all_races %>% left_join(series_lookup_join, by = "SeriesName")
  race_entries_to_insert <- all_races_with_series_id %>%
    left_join(drivers_lookup_join, by = "DriverName") %>%
    left_join(teams_lookup_join, by = "TeamName") %>%
    left_join(manufacturers_lookup_join, by = "ManufacturerName") %>%
    # Join по ключу гонки
    left_join(races_lookup_db, by = c("Season" = "season", "RaceNumInSeason" = "race_num_in_season", "series_id" = "series_id")) %>%
    rename( car_number = CarNumber, start_position = StartPosition, finish_position = FinishPosition, points = Points, laps_completed = LapsCompleted, laps_led = LapsLed, status = Status, segment1_finish = Segment1Finish, segment2_finish = Segment2Finish, driver_rating = DriverRating ) %>%
    select( race_id, driver_id, team_id, manufacturer_id, car_number, start_position, finish_position, points, laps_completed, laps_led, status, segment1_finish, segment2_finish, driver_rating, won_race ) %>%
    # Фильтруем строки, где не удалось найти внешние ключи (особенно race_id)
    filter(!is.na(race_id) & !is.na(driver_id) & !is.na(team_id) & !is.na(manufacturer_id))

  print(paste("Подготовлено записей для вставки в RaceEntries:", nrow(race_entries_to_insert)))
  if(nrow(race_entries_to_insert) > 0) { dbWriteTable(con, "RaceEntries", race_entries_to_insert, append = TRUE, row.names = FALSE); print("Данные вставлены в таблицу RaceEntries.") } else { print("Нет данных для вставки в RaceEntries.") }


  # --- 5g. Коммит транзакции ---
  dbCommit(con)
  print("Транзакция успешно завершена (Commit). База данных обновлена.")

}, error = function(e) {
  # --- 5h. Откат транзакции в случае ошибки ---
  print(paste("ОШИБКА ВО ВРЕМЯ ТРАНЗАКЦИИ:", e$message))
  print("Откат транзакции (Rollback)...")
  dbRollback(con)
  print("Трассировка ошибки:")
  print(rlang::last_trace())
  stop("Загрузка данных в БД не удалась. Все изменения отменены.")
})

# --- 6. Отключение от Базы Данных ---
print("Отключение от базы данных...")
if (exists("con") && inherits(con, "DBIConnection") && dbIsValid(con)) {
  dbDisconnect(con)
  print("Соединение с базой данных закрыто.")
} else {
  print("Соединение с базой данных уже было закрыто или не было установлено/валидно.")
}

print("Скрипт успешно завершил работу.")