# --- 0. Настройка и Загрузка Пакетов ---
install_and_load <- function(packages) {
  for (pkg in packages) {
    if (!require(pkg, character.only = TRUE)) {
      print(paste("Установка пакета:", pkg))
      install.packages(pkg, dependencies = TRUE)
      library(pkg, character.only = TRUE)
    }
  }
}
required_packages <- c("dplyr", "DBI", "RSQLite", "remotes")
print("Проверка и установка основных пакетов...")
install_and_load(required_packages)
print("Основные пакеты загружены.")
print("Принудительное обновление пакета nascaR.data с GitHub...")
tryCatch({
  remotes::install_github('kyleGrealis/nascaR.data@weekly', quiet = TRUE, force = TRUE)
  library(nascaR.data)
  print("nascaR.data успешно обновлен и загружен.")
}, error = function(e) {
  stop("Не удалось установить или загрузить nascaR.data. Ошибка: ", e$message)
})


# --- 1. Определение Переменных ---
db_path <- "nascar_stats.db"
if (!file.exists(db_path)) {
  stop("Файл базы данных '", db_path, "' не найден.")
}

# --- 2. Подключение к Базе Данных ---
print(paste("Подключение к SQLite базе данных:", db_path))
if (exists("con") && inherits(con, "DBIConnection") && dbIsValid(con)) {
  dbDisconnect(con)
}
con <- DBI::dbConnect(RSQLite::SQLite(), dbname = db_path)

# --- 3. Получение и Объединение Данных ---
print("Получение данных из nascaR.data...")
cup_data <- nascaR.data::cup_series %>% mutate(SeriesName = "Cup")
xfinity_data <- nascaR.data::xfinity_series %>% mutate(SeriesName = "Xfinity")
truck_data <- nascaR.data::truck_series %>% mutate(SeriesName = "Truck")

print("Получение данных из nascaR.data...")
cup_data <- nascaR.data::cup_series %>% mutate(SeriesName = "Cup")

# --- Логирование гонок Cup Series за 2025 ---
cup_2025 <- cup_data %>% filter(Season == 2025)
if (nrow(cup_2025) == 0) {
  print("⚠️ Нет данных о гонках Cup Series за 2025 год.")
} else {
  print(paste("📋 Cup Series гонки за 2025 год:", nrow(cup_2025)))
  for (i in seq_len(nrow(cup_2025))) {
    row <- cup_2025[i, ]
    msg <- paste0("🏁 Гонка #", row$Race, " - ", row$Name,
                  " @ ", row$Track, " (", row$Date, ")")
    print(msg)
  }
}

xfinity_data <- nascaR.data::xfinity_series %>% mutate(SeriesName = "Xfinity")
truck_data <- nascaR.data::truck_series %>% mutate(SeriesName = "Truck")


all_races_raw <- bind_rows(cup_data, xfinity_data, truck_data)
print(paste("Загружено строк данных:", nrow(all_races_raw)))

# --- 4. Предобработка Данных ---
all_races <- all_races_raw %>%
  rename(
    RaceNumInSeason = Race, TrackName = Track, RaceName = Name,
    TrackLength = Length, TrackSurface = Surface, FinishPosition = Finish,
    StartPosition = Start, CarNumber = Car, DriverName = Driver,
    TeamName = Team, ManufacturerName = Make, Points = Pts,
    LapsCompleted = Laps, LapsLed = Led, Status = Status,
    Segment1Finish = S1, Segment2Finish = S2, DriverRating = Rating,
    WonRace = Win
  ) %>%
  mutate(
    WonRace = as.integer(WonRace), Season = as.integer(Season),
    RaceNumInSeason = as.integer(RaceNumInSeason), StartPosition = as.integer(StartPosition),
    FinishPosition = as.integer(FinishPosition), Points = as.integer(Points),
    LapsCompleted = as.integer(LapsCompleted), LapsLed = as.integer(LapsLed),
    Segment1Finish = as.integer(Segment1Finish), Segment2Finish = as.integer(Segment2Finish),
    DriverRating = as.numeric(DriverRating), TrackLength = as.numeric(TrackLength),
    DriverName = trimws(DriverName), TeamName = trimws(TeamName),
    ManufacturerName = trimws(ManufacturerName), TrackName = trimws(TrackName),
    RaceName = trimws(RaceName), CarNumber = trimws(CarNumber),
    Status = trimws(Status), TrackSurface = trimws(TrackSurface)
  ) %>%
  filter(!is.na(DriverName) & DriverName != "", !is.na(TeamName) & TeamName != "",
         !is.na(ManufacturerName) & ManufacturerName != "", !is.na(TrackName) & TrackName != "",
         !is.na(SeriesName) & SeriesName != "", !is.na(Season), !is.na(RaceNumInSeason))
print(paste("Строк после базовой очистки:", nrow(all_races)))

# --- 5. Операции с Базой Данных (в транзакции) ---
print("Начало транзакции...")
dbBegin(con)

tryCatch({
  print("Очистка таблиц RaceEntries и Races...")
  dbExecute(con, "DELETE FROM RaceEntries;")
  dbExecute(con, "DELETE FROM Races;")
  print("Таблицы очищены.")

  series_lookup <- dbGetQuery(con, "SELECT series_id, series_name FROM Series;")
  print("Получены ID серий.")

  # --- 5c. Заполнение Справочников ---

  # --- ИЗМЕНЕНИЕ ЗДЕСЬ: Специальная обработка для Tracks ---
  print("Обработка таблицы: Tracks")
  # 1. Получаем уникальные данные трасс, выбирая первое не-NA значение для length/surface
  unique_tracks_data <- all_races %>%
    filter(!is.na(TrackName) & TrackName != "") %>%
    group_by(TrackName) %>%
    summarise(
      # Берем первое не-NA значение, если оно есть
      TrackLength = first(na.omit(TrackLength)),
      TrackSurface = first(na.omit(TrackSurface)),
      .groups = 'drop' # Убираем группировку
    )
  print(paste("Найдено уникальных трасс для обработки:", nrow(unique_tracks_data)))

  # 2. Вставляем или игнорируем только имена
  track_names_df <- unique_tracks_data %>% select(TrackName)
  insert_track_name_query <- "INSERT OR IGNORE INTO Tracks (track_name) VALUES (?);"
  # Используем dbExecute с data.frame для параметризации (если поддерживается RSQLite)
  # dbExecute(con, insert_track_name_query, params = track_names_df)
  # Безопаснее в цикле:
  for(t_name in unique_tracks_data$TrackName) {
     dbExecute(con, insert_track_name_query, params = list(t_name))
  }
  print("Имена трасс вставлены (или проигнорированы существующие).")

  # 3. Обновляем длину и покрытие для всех (включая только что вставленные)
  update_track_details_query <- "UPDATE Tracks SET track_length = ?, track_surface = ? WHERE track_name = ?;"
  # Обновляем в цикле
  for(i in 1:nrow(unique_tracks_data)) {
      row <- unique_tracks_data[i, ]
      # Проверяем на NA перед передачей в запрос (SQLite может не любить NA)
      len <- ifelse(is.na(row$TrackLength), NA_real_, row$TrackLength)
      surf <- ifelse(is.na(row$TrackSurface), NA_character_, row$TrackSurface)
      dbExecute(con, update_track_details_query, params = list(len, surf, row$TrackName))
  }
  print("Детали трасс (длина, покрытие) обновлены.")

  # 4. Получаем итоговый lookup для трасс
  tracks_lookup <- dbGetQuery(con, "SELECT track_id, track_name FROM Tracks")
  print("Получены актуальные ID из таблицы: Tracks")
  # --- КОНЕЦ ИЗМЕНЕНИЯ ДЛЯ TRACKS ---

  # Общая функция для остальных справочников (Drivers, Teams, Manufacturers)
  upsert_and_get_ids <- function(con_trans, table_name, id_col, name_col, data_vector) {
    print(paste("Обработка таблицы:", table_name))
    unique_names <- unique(data_vector[!is.na(data_vector) & data_vector != ""])
    if(length(unique_names) == 0) {
        print(paste("Нет данных для обработки в", table_name))
        return(data.frame(id=integer(), name=character(), stringsAsFactors=FALSE) %>% setNames(c(id_col, name_col)))
    }
    query <- paste0("INSERT OR IGNORE INTO ", table_name, " (", name_col, ") VALUES (?);")
    # Вставляем в цикле
    for(name in unique_names) {
       dbExecute(con_trans, query, params = list(name))
    }
    print(paste("Попытка вставки новых записей в", table_name, "завершена."))
    lookup_query <- paste("SELECT", id_col, ",", name_col, "FROM", table_name)
    lookup_table <- dbGetQuery(con_trans, lookup_query)
    print(paste("Получены актуальные ID из таблицы:", table_name))
    return(lookup_table)
  }

  drivers_lookup <- upsert_and_get_ids(con, "Drivers", "driver_id", "driver_name", all_races$DriverName)
  teams_lookup <- upsert_and_get_ids(con, "Teams", "team_id", "team_name", all_races$TeamName)
  manufacturers_lookup <- upsert_and_get_ids(con, "Manufacturers", "manufacturer_id", "manufacturer_name", all_races$ManufacturerName)

  # --- 5d. Подготовка и Вставка Данных о Гонках (Races) ---
  print("Подготовка данных для таблицы Races...")
  races_to_insert <- all_races %>%
    select(Season, RaceNumInSeason, RaceName, TrackName, SeriesName) %>%
    distinct() %>%
    left_join(tracks_lookup, by = c("TrackName" = "track_name")) %>%
    left_join(series_lookup, by = c("SeriesName" = "series_name")) %>%
    mutate(RaceName = ifelse(is.na(RaceName), paste("Unknown Race", Season, RaceNumInSeason, SeriesName), RaceName)) %>%
    rename(season = Season, race_num_in_season = RaceNumInSeason, race_name = RaceName) %>%
    select(season, race_num_in_season, race_name, track_id, series_id) %>%
    filter(!is.na(track_id) & !is.na(series_id))
  print(paste("Записей для вставки в Races:", nrow(races_to_insert)))
  if(nrow(races_to_insert) > 0) {
      dbWriteTable(con, "Races", races_to_insert, append = TRUE, row.names = FALSE)
      print("Данные вставлены в таблицу Races.")
  } else {
      print("Нет данных для вставки в Races.")
  }

  # --- 5e. Получение ID созданных гонок ---
  races_lookup <- dbGetQuery(con, "SELECT race_id, season, race_num_in_season, series_id FROM Races;")
  print(paste("Получены ID гонок из таблицы Races:", nrow(races_lookup)))

  # --- 5f. Подготовка и Вставка Данных о Результатах (RaceEntries) ---
  print("Подготовка данных для таблицы RaceEntries...")
  series_lookup_join <- series_lookup %>% rename(SeriesName = series_name)
  drivers_lookup_join <- drivers_lookup %>% select(driver_id, driver_name) %>% rename(DriverName = driver_name)
  teams_lookup_join <- teams_lookup %>% select(team_id, team_name) %>% rename(TeamName = team_name)
  manufacturers_lookup_join <- manufacturers_lookup %>% select(manufacturer_id, manufacturer_name) %>% rename(ManufacturerName = manufacturer_name)
  races_lookup_join <- races_lookup

  race_entries_to_insert <- all_races %>%
    left_join(series_lookup_join, by = "SeriesName") %>%
    left_join(drivers_lookup_join, by = "DriverName") %>%
    left_join(teams_lookup_join, by = "TeamName") %>%
    left_join(manufacturers_lookup_join, by = "ManufacturerName") %>%
    left_join(races_lookup_join, by = c("Season" = "season", "RaceNumInSeason" = "race_num_in_season", "series_id" = "series_id")) %>%
    rename(
        car_number = CarNumber, start_position = StartPosition, finish_position = FinishPosition,
        points = Points, laps_completed = LapsCompleted, laps_led = LapsLed, status = Status,
        segment1_finish = Segment1Finish, segment2_finish = Segment2Finish,
        driver_rating = DriverRating, won_race = WonRace
    ) %>%
    mutate(won_race = ifelse(is.na(won_race), 0L, won_race)) %>%
    select(
      race_id, driver_id, team_id, manufacturer_id, car_number, start_position,
      finish_position, points, laps_completed, laps_led, status,
      segment1_finish, segment2_finish, driver_rating, won_race
    ) %>%
    filter(!is.na(race_id) & !is.na(driver_id) & !is.na(team_id) & !is.na(manufacturer_id))
  print(paste("Записей для вставки в RaceEntries:", nrow(race_entries_to_insert)))
  if(nrow(race_entries_to_insert) > 0) {
      dbWriteTable(con, "RaceEntries", race_entries_to_insert, append = TRUE, row.names = FALSE)
      print("Данные вставлены в таблицу RaceEntries.")
  } else {
      print("Нет данных для вставки в RaceEntries.")
  }

  # --- 5g. Коммит транзакции ---
  dbCommit(con)
  print("Транзакция успешно завершена (Commit).")

}, error = function(e) {
  # --- 5h. Откат транзакции в случае ошибки ---
  print(paste("Произошла ошибка:", e$message))
  print("Откат транзакции (Rollback)...")
  dbRollback(con)
  stop("Загрузка данных не удалась. Изменения отменены.")
})

# --- 6. Отключение от Базы Данных ---
print("Отключение от базы данных.")
dbDisconnect(con)

print("Скрипт успешно завершил работу.")