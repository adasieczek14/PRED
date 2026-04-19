# -*- coding: utf-8 -*-
"""
Fctables TFI Ranking Scraper
Pobiera dane z rankingu TFI (Team Form Index) ze strony fctables.com wstecz do 2019 roku.
"""

import argparse
import csv
import random
import time
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

# ==========================================
# KONFIGURACJA
# ==========================================

CONFIG = {
    "BASE_URL": "https://pl.fctables.com/ranking-tfi/",
    "END_DATE": "2019-01-01",
    "OUTPUT_FILE": "fctables_data.csv",
    "HEADLESS": False,
    "SEL_WAIT": 15,
}

# ==========================================
# LOGGING SETUP
# ==========================================

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==========================================
# WEBDRIVER (UNDETECTED)
# ==========================================

def setup_driver(headless: bool = None):
    """Konfiguruje i zwraca instancję Chrome z undetected_chromedriver."""
    if headless is None:
        headless = CONFIG["HEADLESS"]
        
    logger.info("Konfiguracja undetected_chromedriver...")
    base_dir = os.path.dirname(os.path.abspath(__file__))

    browser_path = os.path.join(base_dir, "chrome-win64", "chrome.exe")
    if not os.path.exists(browser_path):
        browser_path = os.path.join(base_dir, "chrome-win64", "chrome-win64", "chrome.exe")

    driver_path = os.path.join(base_dir, "chromedriver-win64", "chromedriver.exe")
    if not os.path.exists(driver_path):
        driver_path = os.path.join(base_dir, "chromedriver-win64", "chromedriver-win64", "chromedriver.exe")

    opts = uc.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--no-first-run")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument('--no-sandbox')

    if os.path.exists(browser_path):
        logger.info(f"Browser: {browser_path}")
        opts.binary_location = browser_path

    kwargs = {"options": opts, "use_subprocess": True}
    if os.path.exists(driver_path):
        logger.info(f"Driver: {driver_path}")
        kwargs["driver_executable_path"] = driver_path
        if os.path.exists(browser_path):
            kwargs["browser_executable_path"] = browser_path
            
    # Try with explicit version first if using system browser as it might be 145 exactly.
    # Otherwise attempt normal startup
    try:
        driver = uc.Chrome(**kwargs)
    except Exception as e:
        logger.warning(f"Failed standard startup ({e}). Trying with version_main=145")
        kwargs["version_main"] = 145
        try:
            if "browser_executable_path" in kwargs:
                del kwargs["browser_executable_path"]
            driver = uc.Chrome(**kwargs)
        except Exception as e2:
            logger.error(f"Failed startup completely: {e2}")
            raise

    stealth(
        driver,
        languages=["pl-PL", "pl", "en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True
    )
    
    logger.info("Driver gotowy!")
    return driver

# ==========================================
# NAWIGACJA
# ==========================================

def accept_cookies(driver):
    """Akceptuje ciasteczka OneTrust (jeśli widoczne)."""
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        btn.click()
        logger.debug("Zaakceptowano cookies.")
        time.sleep(1)
    except Exception:
        pass # Nie ma przycisku albo już zaakceptowano

def human_sleep(a: float, b: float):
    """Udaje pauzę człowieka by zmylić Cloudflare."""
    time.sleep(random.uniform(a, b))

# ==========================================
# ZARZĄDZANIE DRUŻYNAMI I ID
# ==========================================

TEAM_IDS: Dict[str, int] = {}
NEXT_TEAM_ID: int = 1

def load_team_ids(csv_file: str):
    """Wczytuje istniejace ID druzyn z pliku docelowego, zeby zachowac relacyjnosc."""
    global NEXT_TEAM_ID
    if not os.path.exists(csv_file):
        return

    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                try:
                    home_team = row.get("Druzyna_Gospodarzy", "").strip()
                    home_id = int(row.get("ID_GOSPO", 0))
                    away_team = row.get("Druzyna_Gosci", "").strip()
                    away_id = int(row.get("ID_GOSCI", 0))

                    if home_team and home_id > 0:
                        TEAM_IDS[home_team] = home_id
                    if away_team and away_id > 0:
                        TEAM_IDS[away_team] = away_id
                except ValueError:
                    continue
                    
        if TEAM_IDS:
            NEXT_TEAM_ID = max(TEAM_IDS.values()) + 1
        logger.info(f"Wczytano {len(TEAM_IDS)} unikalnych ID druzyn. Nastepne ID to: {NEXT_TEAM_ID}")
    except Exception as e:
        logger.warning(f"Nie udalo sie wczytac bazy ID: {e}")

def get_or_create_team_id(team_name: str) -> int:
    """Zwraca istniejace ID lub tworzy nowe dla druzyny."""
    global NEXT_TEAM_ID
    
    # Czyszczenie znakow kodowania e.g., 'CĂ«rrik' na 'Cerrik' jak w Excelu (opcjonalnie, tu upraszczam)
    t = team_name.replace("Ă«", "e").replace("Ă@", "a").strip()
    
    if t not in TEAM_IDS:
        TEAM_IDS[t] = NEXT_TEAM_ID
        NEXT_TEAM_ID += 1
    return TEAM_IDS[t]

# ==========================================
# GŁÓWNA LOGIKA
# ==========================================

def get_last_scraped_date(csv_file: str) -> Optional[str]:
    """Odczytuje najwyzsza date z pliku CSV by wznowic poprawne dzialanie od najswiezszego dnia."""
    if not os.path.exists(csv_file):
        return None
        
    last_date = None
    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader, None) # pomiń nagłówki
            # Szukamy pierwszej daty ktora nie jest z roku 2019, albo bierzemy faktycznie ostatnio wprowadzana na gore
            for row in reader:
                if row and len(row) > 0:
                    last_date = row[0]
                    if len(last_date) > 10:
                        last_date = last_date[:10]
                    # Since dates in the old file are descending (newest first), the first data row has the most recent date!
                    break
    except Exception as e:
        logger.warning(f"Nie udało się odczytać ostatniej daty z {csv_file}: {e}")
        
    return last_date

def generate_date_range(start_date: str, end_date: str) -> List[str]:
    """Generuje listę dat (YYYY-MM-DD) od start_date (najnowsza) w tył do end_date."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    dates = []
    current = start
    while current >= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current -= timedelta(days=1)
        
    return dates

def scrape_date(driver, target_date: str) -> List[List[str]]:
    """Pobiera dane z tabeli dla podanej daty."""
    url = f"{CONFIG['BASE_URL']}{target_date}/"
    logger.info(f"Pobieranie danych dla: {target_date} ({url})")
    
    try:
        driver.get(url)
    except Exception as e:
        logger.error(f"Błąd nawigacji do URL: {e}")
        return []
        
    accept_cookies(driver)
    
    # Przewinięcie w celu leniwego ładowania
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        human_sleep(1.0, 2.0)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight*2/3);")
        human_sleep(1.0, 2.0)
    except Exception:
        pass

    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", class_="stage-table")
    
    if not table:
        logger.warning(f"Brak tabeli <table class='stage-table'> dla daty {target_date}.")
        return []
        
    rows = table.find_all("tr")
    if not rows:
        return []
        
    data = []
    for row in rows:
        # Pomiń wiersze z reklamami
        if row.get("class") and "ad-row" in row.get("class"):
            continue
            
        cells = row.find_all(["td", "th"])
        if len(cells) >= 6:
            row_data = [cell.get_text(strip=True, separator=" ") for cell in cells]
            
            raw_mecz = row_data[1]
            liga = row_data[2]
            raw_kurs = row_data[3]
            tfi_ha = row_data[4].replace(".", ",")
            tfi = row_data[5].replace(".", ",")
            
            if raw_mecz.lower() == "mecz" and liga.lower() == "liga":
                continue

            # --- PARSOWANIE MECZU I WYNIKU ---
            # Szukamy " : " aby wydzielić zespoły i wynik
            if " : " not in raw_mecz:
                continue # pomijamy mecze bez wyniku (np. "vs")

            parts = raw_mecz.split(" : ")
            if len(parts) >= 2:
                # Ostatnie slowo przed pierwszym dwukropkiem to gole gospodarzy
                try:
                    home_team_raw = parts[0].rsplit(" ", 1)
                    home_team = home_team_raw[0].strip()
                    gole_gospodarzy = int(home_team_raw[1].strip())
                    
                    # Pierwsze slowo po drugim (lub jedynym) dwukropku to gole gosci
                    away_team_raw = parts[1].split(" ", 1)
                    gole_gosci = int(away_team_raw[0].strip())
                    away_team = away_team_raw[1].strip() if len(away_team_raw) > 1 else ""
                except (ValueError, IndexError):
                    logger.debug(f"Pominieto problematyczny wynik w: {raw_mecz}")
                    continue
            else:
                continue

            # --- ID DRUZYN ---
            id_gospo = get_or_create_team_id(home_team)
            id_gosci = get_or_create_team_id(away_team)

            # --- KURS I FAWORYT ---
            faworyt = ""
            kurs_val = ""
            if " : " in raw_kurs:
                k_parts = raw_kurs.split(" : ")
                faworyt = k_parts[0].strip()
                kurs_val = k_parts[1].strip().replace(".", ",") # format liczbowy PL
            elif "-" in raw_kurs:
                k_parts = raw_kurs.split("-")
                faworyt = k_parts[0].strip()
                kurs_val = ""

            # --- REZULTAT ---
            if gole_gospodarzy > gole_gosci:
                rezultat = "1"
            elif gole_gospodarzy == gole_gosci:
                rezultat = "X"
            else:
                rezultat = "2"
                
            remis = 1 if rezultat == "X" else 0

            # --- SKUTECZNOSC FAWORYTA ---
            skutecznosc_faworyta = 0
            if (faworyt == "1" and rezultat == "1") or (faworyt == "2" and rezultat == "2"):
                skutecznosc_faworyta = 1
                
            # Date conversion back to DD.MM.YYYY
            dt_formatted = datetime.strptime(target_date, "%Y-%m-%d").strftime("%d.%m.%Y")

            data.append([
                dt_formatted, home_team, gole_gospodarzy, gole_gosci, away_team,
                liga, faworyt, kurs_val, tfi_ha, tfi,
                id_gospo, id_gosci, skutecznosc_faworyta, remis, rezultat
            ])
            
    logger.info(f"Pobrano i sformatowano {len(data)} rekordow dla {target_date}.")
    return data

def main():
    parser = argparse.ArgumentParser(description="Fctables TFI Ranking Scraper")
    parser.add_argument("--start-date", help="Data początkowa (np. 2024-03-01). Domyślnie: dzisiaj", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--end-date", help="Data końcowa (np. 2019-01-01).", default=CONFIG["END_DATE"])
    parser.add_argument("--force-dates", action="store_true", help="Ignoruj plik CSV i wymus bezwzlglednie pobieranie miedzy zadanymi datami")
    parser.add_argument("--headless", action="store_true", help="Uruchom w tle (headless)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Pokaż logi debugowania")
    args = parser.parse_args()
    
    global logger
    logger = setup_logging(args.verbose)
    
    csv_file = CONFIG["OUTPUT_FILE"]
    
    # Laduj istniejace ID
    load_team_ids(csv_file)
    
    start_date = args.start_date
    
    # Wznów od miejsca, gdzie skończono
    last_date = get_last_scraped_date(csv_file)
    
    if args.force_dates:
        logger.info(f"Wymuszenie uruchomienia manualnego przedzialu od {start_date} do {args.end_date}.")
    elif last_date:
        # Konwersja DD.MM.YYYY na YYYY-MM-DD bazy skryptowej jezeli byla nowa
        try:
            last_dt = datetime.strptime(last_date[:10], "%d.%m.%Y")
        except ValueError:
            last_dt = datetime.strptime(last_date[:10], "%Y-%m-%d")

        logger.info(f"Znaleziono poprzednie dane. Wznawianie od dnia przed: {last_dt.strftime('%d.%m.%Y')}")
        start_date = (last_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Create new file and write headers
        with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow([
                "Data", "Druzyna_Gospodarzy", "GOLE_Gospodarzy", "GOLE_Gosci", "Druzyna_Gosci", 
                "Liga", "Faworyt", "Kurs", "TFI HA", "TFI", "ID_GOSPO", "ID_GOSCI", 
                "Skutecznosc_Faworyta", "REMIS", "Rezultat"
            ])
            
    dates_to_scrape = generate_date_range(start_date, args.end_date)
    if not dates_to_scrape:
        logger.info("Wszystkie daty do podanego limitu zostały już wyodrębnione. Koniec pracy.")
        return
        
    logger.info(f"Do pobrania: {len(dates_to_scrape)} dni (od {dates_to_scrape[0]} wstecz do {args.end_date}).")
    
    driver = None
    try:
        driver = setup_driver(headless=args.headless)
        
        for date_str in dates_to_scrape:
            daily_data = scrape_date(driver, date_str)
            
            # Zapisz w locie
            if daily_data:
                with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, delimiter=';')
                    writer.writerows(daily_data)
            
            # Odstęp by uniknąć bana
            human_sleep(2.0, 4.0)
            
    except KeyboardInterrupt:
        logger.info("Zatrzymano skrypt ręcznie.")
    except Exception as e:
        logger.error(f"Krytyczny błąd: {e}", exc_info=True)
    finally:
        if driver:
            driver.quit()
        logger.info("Zakończono pracę scrapera fctables.")

if __name__ == "__main__":
    main()
