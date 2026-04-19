# -*- coding: utf-8 -*-
"""
FlashScore Superbet Scraper v2.0
Pobiera dane o meczach, kursy bukmacherskie i formy drużyn z FlashScore.
"""

import argparse
import csv
import random
import re
import time
import os
import glob
import logging
from functools import wraps
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any

import pandas as pd

# --- IMPORTY ANTY-DETECTION ---
import undetected_chromedriver as my_uc
from selenium_stealth import stealth

# --- Standardowe importy Selenium ---
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# --- Opcjonalnie tqdm dla progress bar ---
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# ==========================================
# KONFIGURACJA
# ==========================================

CONFIG = {
    "SEL_WAIT": 20,
    "FLASH_FOOTBALL_URL": "https://www.flashscore.pl/pilka-nozna/",
    "MAX_SCROLL_LOOPS": 30,
    "FORM_LIMIT": 6,
    "H2H_LIMIT": 5,
    "HEADLESS": False,
    "OUTPUT_DIR": ".",
    "TEMP_TABLES_DIR": "temp_tables",
    "RETRY_ATTEMPTS": 3,
    "RETRY_DELAY": 2,
}

# Centralizacja selektorów CSS
SELECTORS = {
    # Cookies i overlay
    "cookies_btn": "button[id*='onetrust-accept-btn']",
    "close_buttons": [
        "button[aria-label='Zamknij']",
        "button.close",
        "[id*='ad'] button.close",
        "div[id*='onetrust'] button"
    ],
    
    # Nawigacja datą
    "day_picker": "button[data-testid='wcl-dayPickerButton'], button.wcl-dayPickerButton",
    "next_day": "button[aria-label='Następny dzień'], button[data-day-picker-arrow='next']",
    
    # Mecze
    "match_row": "div.event__match--withRowLink[data-event-row='true'], div.event__match[data-event-row='true']",
    "match_link": "a.eventRowLink",
    "show_matches_btn": "//*[contains(text(), 'pokaż spotkania') or contains(text(), 'show matches')]",
    "show_more_matches": "//a[contains(text(), 'Pokaż więcej meczów')]",
    "collapsed_leagues": "div[class*='--collapsed'] svg, button[title='Rozwiń'], .event__expander--close",
    
    # Szczegóły meczu
    "home_name": ".duelParticipant__home .participant__participantName",
    "away_name": ".duelParticipant__away .participant__participantName",
    "kickoff_time": ".duelParticipant__startTime",
    
    # Liga
    "header_league": "div[data-testid='wcl-headerLeague']",
    "league_category": "span.headerLeague__category",
    "league_title": "a.headerLeague__title",
    
    # Tabela
    "table_btn": "//a[contains(@href,'/tabela')] | //button[contains(translate(.,'TABELA','tabela'),'tabela')]",
    "table_row": ".ui-table__row",
    "table_rank": ".table__cell--rank",
    "table_team": ".tableCellParticipant__name",
    "table_values": ".table__cell--value",
    "table_form": ".table__cell--form",
    
    # H2H
    "h2h_tab": "//button[@data-testid='wcl-tab' and normalize-space()='H2H']",
    "h2h_subtab": "//a[@data-analytics-alias='{alias}']//button[@data-testid='wcl-tab']",
    "h2h_section": "div.h2h div.h2h__section",
    "h2h_section_header": "[data-testid='wcl-headerSection-text']",
    "h2h_row": "a.h2h__row",
    "h2h_event": ".h2h__event",
    "h2h_date": ".h2h__date",
    "h2h_home": ".h2h__homeParticipant .h2h__participantInner",
    "h2h_away": ".h2h__awayParticipant .h2h__participantInner",
    "h2h_result": ".h2h__result span",
    "h2h_show_more": ".//button[contains(@class,'wclButtonLink')][.//span[contains(.,'Pokaż więcej')]]",
    "h2h_badge": "div[class*='wcl-badge'] span[data-testid='wcl-scores-simple-text-01']",
    
    # Superbet
    "odds_tab": "//a[contains(@href, '/kursy/')]",
    "superbet_img": "img",
    "sb_row_xpath": "./ancestor::div[contains(@class, 'ui-table__row')]",
    "odds_cells_xpath": ".//a[contains(@class, 'odd')] | .//span[contains(@class, 'odd')]",
    "superbet_link": "div.bookmaker a.prematchLink[title*='Superbet']",
    "odds_row": "div[@class='odds']",
    "odds_cell": "button[data-testid='wcl-oddsCell']",
    "odds_cell_fallback": "button.wcl-oddsCell, button",
    "odds_value": "[data-testid='wcl-oddsValue']",
    "odds_value_fallback": "span.wcl-oddsValue",
}

# ==========================================
# LOGGING SETUP
# ==========================================

def setup_logging(verbose: bool = False):
    """Konfiguruje system logowania."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==========================================
# DEKORATORY I HELPERY
# ==========================================

def retry(max_attempts: int = None, delay: float = None):
    """Dekorator do automatycznego ponawiania funkcji przy błędach."""
    max_attempts = max_attempts or CONFIG["RETRY_ATTEMPTS"]
    delay = delay or CONFIG["RETRY_DELAY"]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"[{func.__name__}] Próba {attempt+1}/{max_attempts} nieudana: {e}. Ponawiam za {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"[{func.__name__}] Wszystkie {max_attempts} prób nieudane.")
            raise last_exception
        return wrapper
    return decorator


def human_sleep(a: float, b: float):
    """Symuluje ludzkie opóźnienie."""
    time.sleep(random.uniform(a, b))


def human_move_mouse(driver):
    """Symuluje ruch myszą."""
    try:
        driver.execute_script("""
        const e = document.createEvent('MouseEvents');
        e.initMouseEvent('mousemove', true, true, window);
        document.body.dispatchEvent(e);
        """)
    except Exception as e:
        logger.debug(f"human_move_mouse: {e}")


def human_scroll(driver):
    """Symuluje ludzkie scrollowanie."""
    try:
        driver.execute_script("window.scrollBy(0, arguments[0]);", random.randint(200, 600))
    except Exception as e:
        logger.debug(f"human_scroll: {e}")


def sanitize_filename(name: str) -> str:
    """Czyści string do użycia jako nazwa pliku."""
    if not name:
        return "unknown"
    return re.sub(r"[^a-zA-Z0-9]", "_", name).strip("_")


def _count_form_letters(s: str) -> Tuple[int, int, int]:
    """Liczy litery W, R, P w stringu formy."""
    if not s:
        return 0, 0, 0
    return s.count("W"), s.count("R"), s.count("P")


def _sanitize_odd(txt: str) -> Optional[float]:
    """Parsuje i waliduje kurs bukmacherski."""
    if not txt:
        return None
    t = txt.strip().replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if 1.01 <= v < 100 else None


def calculate_form_metrics(form_string: str) -> Dict[str, Any]:
    """Oblicza zaawansowane metryki formy."""
    if not form_string:
        return {"win_rate": 0, "ppg": 0, "unbeaten": 0, "trend": "unknown"}
    
    W, R, P = _count_form_letters(form_string)
    total = W + R + P
    
    if total == 0:
        return {"win_rate": 0, "ppg": 0, "unbeaten": 0, "trend": "unknown"}
    
    # Oblicz passę bez porażki
    unbeaten = 0
    for c in form_string:
        if c in ('W', 'R'):
            unbeaten += 1
        else:
            break
    
    # Trend na podstawie ostatnich 2 meczów
    recent = form_string[:2] if len(form_string) >= 2 else form_string
    if recent.count('W') >= 1:
        trend = "up"
    elif recent.count('P') >= 1:
        trend = "down"
    else:
        trend = "stable"
    
    return {
        "win_rate": round(W / total, 2),
        "ppg": round((W * 3 + R) / total, 2),
        "unbeaten": unbeaten,
        "trend": trend
    }


# ==========================================
# FILTRY
# ==========================================

def _is_friendly_competition(name: str) -> bool:
    """Sprawdza czy rozgrywki są towarzyskie."""
    if not name:
        return False
    base = re.sub(r"\([^)]*\)", "", name).strip().lower()
    return any(k in base for k in ["towarzysk", "friendly", "friendlies", "club friendly"])


def _is_friendly_kind(kind: str) -> bool:
    """Sprawdza czy rodzaj meczu jest towarzyski."""
    if not kind:
        return False
    return _is_friendly_competition(kind.rsplit(":", 1)[-1].strip())


def _is_friendly_h2h_row(row) -> bool:
    """Sprawdza czy wiersz H2H dotyczy meczu towarzyskiego."""
    try:
        ev = row.find_element(By.CSS_SELECTOR, SELECTORS["h2h_event"])
        return _is_friendly_competition((ev.get_attribute("title") or ev.text).strip())
    except Exception:
        return False


def _normalize_competition_for_matching(name: str) -> Tuple[str, str]:
    """Normalizuje nazwę rozgrywek do porównywania."""
    if not name:
        return "", ""
    base = re.sub(r"\([^)]*\)", "", name).strip().lower()
    kind = "league"
    if any(x in base for x in ["puchar", "cup", "copa", "trophy"]):
        kind = "cup"
    core = base.split(" - ")[0].strip()
    return kind, core


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

    opts = my_uc.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--no-first-run")

    if os.path.exists(browser_path):
        logger.info(f"Browser: {browser_path}")
        opts.binary_location = browser_path

    kwargs = {"options": opts, "use_subprocess": True}
    if os.path.exists(driver_path):
        logger.info(f"Driver: {driver_path}")
        kwargs["driver_executable_path"] = driver_path
        if os.path.exists(browser_path):
            kwargs["browser_executable_path"] = browser_path

    try:
        driver = my_uc.Chrome(**kwargs)
    except TypeError:
        if "browser_executable_path" in kwargs:
            del kwargs["browser_executable_path"]
        driver = my_uc.Chrome(**kwargs)

    stealth(
        driver,
        languages=["pl-PL", "pl"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True
    )
    
    logger.info("Driver gotowy!")
    return driver


# ==========================================
# NAWIGACJA I DATA
# ==========================================

def accept_cookies_banner(driver):
    """Akceptuje baner cookies."""
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTORS["cookies_btn"]))
        ).click()
        logger.debug("Cookies zaakceptowane")
    except TimeoutException:
        logger.debug("Brak baneru cookies")
    except Exception as e:
        logger.debug(f"accept_cookies_banner: {e}")


def close_overlays_if_any(driver):
    """Zamyka wszelkie overlay/popup."""
    for sel in SELECTORS["close_buttons"]:
        try:
            for e in driver.find_elements(By.CSS_SELECTOR, sel):
                if e.is_displayed():
                    driver.execute_script("arguments[0].click();", e)
                    time.sleep(0.3)
        except Exception as e:
            logger.debug(f"close_overlays_if_any ({sel}): {e}")
    
    try:
        driver.execute_script("document.dispatchEvent(new KeyboardEvent('keydown',{'key':'Escape'}));")
    except Exception as e:
        logger.debug(f"Escape key: {e}")


@retry()
def goto_next_day_once(driver) -> str:
    """Przechodzi do następnego dnia i zwraca datę."""
    wait = WebDriverWait(driver, CONFIG["SEL_WAIT"])
    
    date_btn = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, SELECTORS["day_picker"])
    ))
    before_label = date_btn.text.strip()
    
    nxt = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, SELECTORS["next_day"])
    ))
    driver.execute_script("arguments[0].click();", nxt)
    
    WebDriverWait(driver, CONFIG["SEL_WAIT"]).until(
        lambda d: d.find_element(By.CSS_SELECTOR, SELECTORS["day_picker"]).text.strip() != before_label
    )
    
    try:
        return driver.find_element(By.CSS_SELECTOR, SELECTORS["day_picker"]).get_attribute("data-date") or ""
    except Exception:
        pass
    
    return (datetime.now().date() + timedelta(days=1)).strftime("%Y-%m-%d")


def open_tomorrow_via_arrow(driver) -> str:
    """Otwiera stronę FlashScore i przechodzi do jutra."""
    logger.info(f"Otwieram {CONFIG['FLASH_FOOTBALL_URL']}")
    driver.get(CONFIG["FLASH_FOOTBALL_URL"])
    human_sleep(1.0, 2.0)
    accept_cookies_banner(driver)
    close_overlays_if_any(driver)
    human_scroll(driver)
    human_move_mouse(driver)
    return goto_next_day_once(driver)


# ==========================================
# ROZWIJANIE I ŁADOWANIE MECZÓW
# ==========================================

def expand_show_matches(driver):
    """Rozwija ukryte mecze."""
    try:
        btns = driver.find_elements(By.XPATH, SELECTORS["show_matches_btn"])
        for b in btns:
            try:
                if b.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", b)
                    driver.execute_script("arguments[0].click();", b)
                    human_sleep(0.3, 0.6)
            except Exception as e:
                logger.debug(f"expand_show_matches (btn): {e}")
    except Exception as e:
        logger.debug(f"expand_show_matches: {e}")


def expand_closed_leagues(driver):
    """Rozwija zwinięte ligi."""
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR, SELECTORS["collapsed_leagues"])
        for btn in buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                driver.execute_script("arguments[0].click();", btn)
                human_sleep(0.2, 0.5)
            except Exception as e:
                logger.debug(f"expand_closed_leagues (btn): {e}")
    except Exception as e:
        logger.debug(f"expand_closed_leagues: {e}")


def auto_scroll_load_all(driver, max_loops: int = None):
    """Automatycznie scrolluje i ładuje wszystkie mecze."""
    if max_loops is None:
        max_loops = CONFIG["MAX_SCROLL_LOOPS"]
    
    logger.info("Ładowanie wszystkich meczów...")
    last_count = -1
    same_count_hits = 0
    
    for loop in range(max_loops):
        expand_show_matches(driver)
        expand_closed_leagues(driver)
        
        try:
            mb = driver.find_elements(By.XPATH, SELECTORS["show_more_matches"])
            if mb:
                driver.execute_script("arguments[0].click();", mb[0])
                human_sleep(1.0, 2.0)
        except Exception as e:
            logger.debug(f"show_more_matches: {e}")

        rows = driver.find_elements(By.CSS_SELECTOR, SELECTORS["match_row"])
        cnt = len(rows)
        
        if cnt == last_count:
            same_count_hits += 1
        else:
            same_count_hits = 0
        last_count = cnt
        
        if same_count_hits >= 3:
            break

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        human_sleep(0.8, 1.4)
        
        if (loop + 1) % 5 == 0:
            logger.debug(f"Scroll {loop+1}/{max_loops}, znaleziono {cnt} meczów")
    
    logger.info(f"Załadowano {last_count} meczów")


# ==========================================
# ZBIERANIE URLI I TABELI
# ==========================================

def collect_matches_from_list(driver) -> List[Dict]:
    """Zbiera linki do meczów z listy."""
    matches = []
    curr = ""
    
    try:
        root = driver.find_element(By.ID, "live-table")
    except NoSuchElementException:
        root = driver
    
    blocks = root.find_elements(By.XPATH,
        ".//div[@data-testid='wcl-headerLeague' or (contains(@class,'event__match') and @data-event-row='true')]"
    )
    
    for b in blocks:
        tid = b.get_attribute("data-testid") or ""
        
        if tid == "wcl-headerLeague":
            try:
                c = b.find_element(By.CSS_SELECTOR, SELECTORS["league_category"]).text.strip()
                t = b.find_element(By.CSS_SELECTOR, SELECTORS["league_title"]).text.strip()
                curr = f"{c}: {t}"
            except Exception as e:
                logger.debug(f"collect_matches_from_list (header): {e}")
        
        elif "event__match" in (b.get_attribute("class") or ""):
            try:
                href = b.find_element(By.CSS_SELECTOR, SELECTORS["match_link"]).get_attribute("href")
                if href and "/mecz/" in href:
                    matches.append({"url": href, "Rodzaj": curr})
            except Exception as e:
                logger.debug(f"collect_matches_from_list (match): {e}")
    
    return matches


def get_league_table_data(driver) -> List[Dict]:
    """Pobiera dane z tabeli ligowej."""
    data = []
    try:
        xpath = SELECTORS["table_btn"]
        btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].click();", btn)
        human_sleep(2.0, 3.0)
        
        rows = driver.find_elements(By.CSS_SELECTOR, SELECTORS["table_row"])
        for r in rows:
            try:
                d = {}
                d["Poz"] = r.find_element(By.CSS_SELECTOR, SELECTORS["table_rank"]).text.replace(".", "").strip()
                d["Druzyna"] = r.find_element(By.CSS_SELECTOR, SELECTORS["table_team"]).text.strip()
                
                vals = r.find_elements(By.CSS_SELECTOR, SELECTORS["table_values"])
                if len(vals) >= 7:
                    d["M"] = vals[0].text
                    d["Z"] = vals[1].text
                    d["R"] = vals[2].text
                    d["P"] = vals[3].text
                    d["B"] = vals[4].text
                    d["RB"] = vals[5].text
                    d["Pkt"] = vals[6].text
                
                try:
                    badges = r.find_element(By.CSS_SELECTOR, SELECTORS["table_form"]).text.replace("\n", "")
                    d["Forma"] = badges[-5:]
                except Exception:
                    d["Forma"] = ""
                
                data.append(d)
            except Exception as e:
                logger.debug(f"get_league_table_data (row): {e}")
                continue
    except TimeoutException:
        logger.debug("Brak tabeli ligowej")
    except Exception as e:
        logger.debug(f"get_league_table_data: {e}")
    
    return data


# ==========================================
# H2H - POMOCNIKI I PARSERY
# ==========================================

def click_h2h_tab(driver):
    """Klika zakładkę H2H."""
    try:
        btn = WebDriverWait(driver, CONFIG["SEL_WAIT"]).until(
            EC.element_to_be_clickable((By.XPATH, SELECTORS["h2h_tab"]))
        )
        driver.execute_script("arguments[0].click();", btn)
        human_sleep(0.7, 1.4)
        logger.debug("Kliknięto H2H tab")
    except TimeoutException:
        logger.warning("Nie znaleziono zakładki H2H")
    except Exception as e:
        logger.debug(f"click_h2h_tab: {e}")


def click_h2h_subtab_alias(driver, alias: str):
    """Klika podzakładkę H2H o podanym aliasie."""
    try:
        xpath = SELECTORS["h2h_subtab"].format(alias=alias)
        btn = WebDriverWait(driver, CONFIG["SEL_WAIT"]).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].click();", btn)
        human_sleep(0.6, 1.2)
    except Exception as e:
        logger.debug(f"click_h2h_subtab_alias ({alias}): {e}")


def click_show_more_matches_if_present(driver):
    """Klika 'Pokaż więcej' jeśli jest dostępne."""
    try:
        btn = driver.find_element(By.XPATH,
            "//div[contains(@class,'h2h')]//button[contains(@class,'wclButtonLink')][.//span[contains(.,'Pokaż więcej')]]"
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        driver.execute_script("arguments[0].click();", btn)
        human_sleep(0.6, 1.2)
    except Exception as e:
        logger.debug(f"click_show_more_matches_if_present: {e}")


def _extract_row_result_letter(row) -> Optional[str]:
    """Wyciąga literę wyniku z wiersza."""
    try:
        l = row.find_element(By.CSS_SELECTOR, SELECTORS["h2h_badge"]).text.strip().upper()
        if l in ("Z", "W"):
            return "W"
        if l in ("P", "L"):
            return "P"
        if l in ("R", "D"):
            return "R"
    except Exception:
        pass
    return None


def _extract_section_rows(section) -> List:
    """Wyciąga wiersze z sekcji H2H."""
    try:
        return section.find_elements(By.CSS_SELECTOR, SELECTORS["h2h_row"])
    except Exception:
        return []


def _find_section_for_team(driver, team_name: str):
    """Znajduje sekcję H2H dla danej drużyny."""
    name_low = team_name.lower()
    secs = driver.find_elements(By.CSS_SELECTOR, SELECTORS["h2h_section"])
    
    for s in secs:
        try:
            h = s.find_element(By.CSS_SELECTOR, SELECTORS["h2h_section_header"]).text.strip()
        except Exception:
            h = s.text.strip()
        
        if name_low in h.lower():
            return s
    
    return None


def _result_for_team_in_row(row, team_name: str) -> Optional[str]:
    """Określa wynik dla drużyny w wierszu H2H."""
    try:
        h = row.find_element(By.CSS_SELECTOR, SELECTORS["h2h_home"]).text.strip().lower()
        a = row.find_element(By.CSS_SELECTOR, SELECTORS["h2h_away"]).text.strip().lower()
        s = row.find_elements(By.CSS_SELECTOR, SELECTORS["h2h_result"])
        hg, ag = int(s[0].text), int(s[1].text)
        tn = team_name.lower()
        
        if tn in h:
            return "W" if hg > ag else ("P" if hg < ag else "R")
        elif tn in a:
            return "W" if ag > hg else ("P" if ag < hg else "R")
    except Exception:
        pass
    return None


def _read_direct_h2h(driver, h_name: str, a_name: str, limit: int = None) -> Tuple[str, str]:
    """Czyta bezpośrednie starcia H2H."""
    if limit is None:
        limit = CONFIG["H2H_LIMIT"]
    
    sec = None
    secs = driver.find_elements(By.CSS_SELECTOR, SELECTORS["h2h_section"])
    
    for s in secs:
        if "bezpośrednie" in s.text.lower():
            sec = s
            break
    
    if not sec and secs:
        sec = secs[-1]
    
    if not sec:
        return "", ""
    
    rows = sec.find_elements(By.CSS_SELECTOR, SELECTORS["h2h_row"])
    hr, ar = [], []
    
    for r in rows:
        if _is_friendly_h2h_row(r):
            continue
        rh = _result_for_team_in_row(r, h_name)
        ra = _result_for_team_in_row(r, a_name)
        if rh and ra:
            hr.append(rh)
            ar.append(ra)
        if len(hr) >= limit:
            break
    
    return "".join(hr), "".join(ar)


def _parse_h2h_row_detailed(row, team_name: str) -> Optional[Dict]:
    """Parsuje szczegółowe dane z wiersza H2H."""
    if _is_friendly_h2h_row(row):
        return None
    
    try:
        try:
            ev_el = row.find_element(By.CSS_SELECTOR, SELECTORS["h2h_event"])
            comp = (ev_el.get_attribute("title") or ev_el.text).strip()
        except Exception:
            comp = "Unknown"

        if _is_friendly_competition(comp):
            return None

        date = row.find_element(By.CSS_SELECTOR, SELECTORS["h2h_date"]).text.strip()
        ht = row.find_element(By.CSS_SELECTOR, SELECTORS["h2h_home"]).text.strip()
        at = row.find_element(By.CSS_SELECTOR, SELECTORS["h2h_away"]).text.strip()
        sp = row.find_elements(By.CSS_SELECTOR, SELECTORS["h2h_result"])
        hg, ag = int(sp[0].text), int(sp[1].text)

        tn = team_name.lower()
        hn = ht.lower()
        an = at.lower()
        is_home = tn in hn
        is_away = tn in an
        
        if not (is_home or is_away):
            return None

        if is_home:
            opp, gf, ga, role = at, hg, ag, "HOME"
        else:
            opp, gf, ga, role = ht, ag, hg, "AWAY"
        
        gd = gf - ga
        if gd > 0:
            pts, res = 3, "W"
        elif gd == 0:
            pts, res = 1, "R"
        else:
            pts, res = 0, "P"

        return {
            "date": date,
            "opponent": opp,
            "score": f"{hg}:{ag}",
            "gd": gd,
            "points": pts,
            "result": res,
            "role": role,
            "competition": comp
        }
    except Exception as e:
        logger.debug(f"_parse_h2h_row_detailed: {e}")
        return None


def _get_comp_form_for_team_with_details(driver, team_name: str, comp_key: str, limit: int = None) -> Tuple[str, List[Dict]]:
    """
    Pobiera formę drużyny z filtrowaniem po lidze.
    Działa na aktualnie wybranej zakładce (Overall, Home, Away).
    """
    if limit is None:
        limit = CONFIG["FORM_LIMIT"]
    
    comp_key = (comp_key or "").strip()
    mk, mc = _normalize_competition_for_matching(comp_key)

    found_str = []
    found_det = []
    clicks = 0

    while True:
        sec = _find_section_for_team(driver, team_name)
        if not sec:
            return "".join(found_str), found_det

        rows = _extract_section_rows(sec)
        current_batch_str = []
        current_batch_det = []

        for r in rows:
            try:
                ev = r.find_element(By.CSS_SELECTOR, SELECTORS["h2h_event"])
                ev_text = (ev.get_attribute("title") or ev.text).strip()
            except Exception:
                ev_text = ""
            
            rk, rc = _normalize_competition_for_matching(ev_text)

            # Filtrowanie ligi
            if mk and rk and mk != rk:
                continue
            if mc and not (mc in rc or rc in mc):
                continue

            det = _parse_h2h_row_detailed(r, team_name)
            if det:
                current_batch_det.append(det)
                current_batch_str.append(det['result'])

        if len(current_batch_str) >= limit:
            return "".join(current_batch_str[:limit]), current_batch_det[:limit]

        if clicks >= 5:
            return "".join(current_batch_str), current_batch_det

        try:
            btn = sec.find_element(By.XPATH, SELECTORS["h2h_show_more"])
            driver.execute_script("arguments[0].click();", btn)
            human_sleep(0.5, 1.0)
            clicks += 1
        except Exception:
            return "".join(current_batch_str), current_batch_det


# ==========================================
# GŁÓWNY READER FORM
# ==========================================

def read_match_forms(driver, h_name: str, a_name: str, comp_hint: str = "") -> Dict:
    """Czyta formy obu drużyn."""
    forms = {
        "home_form_overall": "", "away_form_overall": "",
        "home_form_home": "", "away_form_away": "",
        "home_form_h2h": "", "away_form_h2h": "",
        "detailed_history": {}
    }

    comp_key = comp_hint.rsplit(":", 1)[-1].strip() if comp_hint else ""

    # 1. Overall (z filtrem ligi)
    click_h2h_tab(driver)
    click_h2h_subtab_alias(driver, "head-2-head_0_h2h")

    hs, hd = _get_comp_form_for_team_with_details(driver, h_name, comp_key, CONFIG["FORM_LIMIT"])
    forms["home_form_overall"] = hs
    forms["detailed_history"]["home_overall"] = hd

    as_, ad = _get_comp_form_for_team_with_details(driver, a_name, comp_key, CONFIG["FORM_LIMIT"])
    forms["away_form_overall"] = as_
    forms["detailed_history"]["away_overall"] = ad

    # 2. Home@Home (z filtrem ligi)
    click_h2h_subtab_alias(driver, "head-2-head_1_h2h")
    click_show_more_matches_if_present(driver)
    hs_h, hd_h = _get_comp_form_for_team_with_details(driver, h_name, comp_key, CONFIG["FORM_LIMIT"])
    forms["home_form_home"] = hs_h
    forms["detailed_history"]["home_home"] = hd_h

    # 3. Away@Away (z filtrem ligi)
    click_h2h_subtab_alias(driver, "head-2-head_2_h2h")
    click_show_more_matches_if_present(driver)
    as_a, ad_a = _get_comp_form_for_team_with_details(driver, a_name, comp_key, CONFIG["FORM_LIMIT"])
    forms["away_form_away"] = as_a
    forms["detailed_history"]["away_away"] = ad_a

    # 4. Direct H2H (bez filtrowania ligi)
    click_h2h_subtab_alias(driver, "head-2-head_0_h2h")
    human_sleep(0.4, 0.8)
    hh, ah = _read_direct_h2h(driver, h_name, a_name)
    forms["home_form_h2h"] = hh
    forms["away_form_h2h"] = ah

    return forms


# ==========================================
# KURSY SUPERBET
# ==========================================

def _find_superbet_row_fallback(driver):
    """Fallback do szukania wiersza Superbet."""
    try:
        els = driver.find_elements(By.XPATH, "//*[contains(translate(., 'SUPERBET', 'superbet'),'superbet')]")
        for el in els:
            node = el
            for _ in range(10):
                if "wclOddsRow" in (node.get_attribute("class") or ""):
                    return node
                node = node.find_element(By.XPATH, "..")
    except Exception as e:
        logger.debug(f"_find_superbet_row_fallback: {e}")
    return None


@retry()
def read_superbet_odds_on_match(driver, url: str, comp_hint: str = "") -> Dict:
    """Czyta kursy Superbet dla meczu."""
    if driver.current_url != url:
        driver.get(url)
        human_sleep(1.5, 3.0)
        close_overlays_if_any(driver)

    odds = {
        "home": "", "draw": "", "away": "",
        "home_name": "", "away_name": "", "kickoff_time": ""
    }
    
    try:
        odds["home_name"] = driver.find_element(By.CSS_SELECTOR, SELECTORS["home_name"]).text.strip()
    except Exception as e:
        logger.debug(f"home_name: {e}")
    
    try:
        odds["away_name"] = driver.find_element(By.CSS_SELECTOR, SELECTORS["away_name"]).text.strip()
    except Exception as e:
        logger.debug(f"away_name: {e}")
    
    try:
        odds["kickoff_time"] = driver.find_element(By.CSS_SELECTOR, SELECTORS["kickoff_time"]).text.strip()
    except Exception as e:
        logger.debug(f"kickoff_time: {e}")

    try:
        btn_odds = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, SELECTORS["odds_tab"])))
        driver.execute_script("arguments[0].click();", btn_odds)
        human_sleep(1.0, 2.0)
    except Exception as e:
        logger.debug(f"brak mozliwosci klikniecia odds tab: {e}")

    row = None
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, SELECTORS["superbet_img"])
        sb_img = None
        for img in imgs:
            alt = img.get_attribute("alt") or ""
            title = img.get_attribute("title") or ""
            if "superbet" in alt.lower() or "superbet" in title.lower():
                sb_img = img
                break
                
        if sb_img:
            row = sb_img.find_element(By.XPATH, SELECTORS["sb_row_xpath"])
    except Exception as e:
        row = _find_superbet_row_fallback(driver)

    if row:
        vals = []
        cells = row.find_elements(By.XPATH, SELECTORS["odds_cells_xpath"])
        
        for c in cells[:3]:
            vals.append(_sanitize_odd(c.text))
        
        if len(vals) >= 3 and all(v is not None for v in vals[:3]):
            odds["home"], odds["draw"], odds["away"] = [f"{x:.2f}".replace(".", ",") for x in vals[:3]]

    if odds["home"] and odds["away"] and odds["home_name"]:
        try:
            f = read_match_forms(driver, odds["home_name"], odds["away_name"], comp_hint)
            odds.update(f)
        except Exception as e:
            logger.warning(f"read_match_forms error: {e}")

    return odds


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():
    ap = argparse.ArgumentParser(description="FlashScore Superbet Scraper v2.0")
    ap.add_argument("--out", default="flashscore_superbet.csv", help="Plik wyjściowy CSV z meczami")
    ap.add_argument("--hist-out", default="flashscore_history.csv", help="Plik wyjściowy CSV z historią")
    ap.add_argument("--final-excel", default="flashscore_complete.xlsx", help="Plik Excel z wszystkimi danymi")
    ap.add_argument("--limit", type=int, default=0, help="Limit meczów (0 = wszystkie)")
    ap.add_argument("--headless", action="store_true", help="Tryb headless (bez okna)")
    ap.add_argument("--verbose", "-v", action="store_true", help="Tryb verbose (więcej logów)")
    args = ap.parse_args()

    if args.verbose:
        global logger
        logger = setup_logging(verbose=True)

    driver = setup_driver(headless=args.headless)
    
    temp_dir = CONFIG["TEMP_TABLES_DIR"]
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    processed_leagues = set()

    try:
        logger.info("Pobieranie listy meczów...")
        target_day = open_tomorrow_via_arrow(driver)
        auto_scroll_load_all(driver)
        matches = collect_matches_from_list(driver)
        
        if args.limit > 0:
            matches = matches[:args.limit]
        
        logger.info(f"Znaleziono {len(matches)} meczów na {target_day}")

        # Przygotowanie plików CSV
        f_main = open(args.out, "w", newline="", encoding="utf-8-sig")
        fieldnames = [
            "Rodzaj", "Data", "Gospodarz", "Gosc", "Kurs_1", "Kurs_X", "Kurs_2", "Match_ID", "URL",
            "home_form_overall", "away_form_overall", "home_form_home", "away_form_away",
            "home_form_h2h", "away_form_h2h",
            "home_form_overall_W", "home_form_overall_R", "home_form_overall_P",
            "away_form_overall_W", "away_form_overall_R", "away_form_overall_P",
            "home_form_home_W", "home_form_home_R", "home_form_home_P",
            "away_form_away_W", "away_form_away_R", "away_form_away_P",
            "home_form_h2h_W", "home_form_h2h_R", "home_form_h2h_P",
            "away_form_h2h_W", "away_form_h2h_R", "away_form_h2h_P"
        ]
        w_main = csv.DictWriter(f_main, fieldnames=fieldnames, extrasaction='ignore', delimiter=';')
        w_main.writeheader()

        f_hist = open(args.hist_out, "w", newline="", encoding="utf-8-sig")
        hist_fields = [
            "Match_ID", "Team_Name", "Type", "Date", "Opponent", "Score",
            "GD", "Points", "Result", "Role", "Competition"
        ]
        w_hist = csv.DictWriter(f_hist, fieldnames=hist_fields, delimiter=';')
        w_hist.writeheader()

        # Iteracja po meczach
        iterator = enumerate(matches, 1)
        if HAS_TQDM:
            iterator = tqdm(list(iterator), desc="Przetwarzanie", unit="mecz")
        
        skipped = 0
        saved = 0
        
        for item in iterator:
            if HAS_TQDM:
                i, m = item
            else:
                i, m = item
            
            kind = m.get("Rodzaj", "")
            url = m["url"]

            if _is_friendly_kind(kind):
                logger.debug(f"[{i}] Skip (towarzyski): {kind}")
                skipped += 1
                continue

            try:
                odds = read_superbet_odds_on_match(driver, url, kind)
            except Exception as e:
                logger.warning(f"[{i}] Błąd pobierania: {e}")
                skipped += 1
                continue

            if not (odds.get("home") and odds.get("away")):
                logger.debug(f"[{i}] Skip (brak kursów) -> {odds.get('home_name', '?')}")
                skipped += 1
                continue

            # Pobierz tabelę ligową (raz na ligę)
            if kind not in processed_leagues:
                logger.info(f"Pobieram tabelę: {kind}")
                tbl = get_league_table_data(driver)
                processed_leagues.add(kind)
                if tbl:
                    tbl_file = os.path.join(temp_dir, f"{sanitize_filename(kind)}.csv")
                    pd.DataFrame(tbl).to_csv(tbl_file, index=False, sep=';', encoding="utf-8-sig")

            match_id = f"M_{i}_{sanitize_filename(odds.get('home_name', ''))}_vs_{sanitize_filename(odds.get('away_name', ''))}"

            # Oblicz statystyki formy
            for k in ["home_form_overall", "away_form_overall", "home_form_home", 
                      "away_form_away", "home_form_h2h", "away_form_h2h"]:
                W, R, P = _count_form_letters(odds.get(k, ""))
                odds[f"{k}_W"] = W
                odds[f"{k}_R"] = R
                odds[f"{k}_P"] = P

            row = {
                "Rodzaj": kind,
                "Data": f"{target_day} {odds.get('kickoff_time', '')}".strip(),
                "Gospodarz": odds.get("home_name"),
                "Gosc": odds.get("away_name"),
                "Kurs_1": odds.get("home"),
                "Kurs_X": odds.get("draw"),
                "Kurs_2": odds.get("away"),
                "Match_ID": match_id,
                "URL": url,
                **odds
            }
            w_main.writerow(row)
            f_main.flush()

            # Zapisz szczegółową historię
            det = odds.get("detailed_history", {})
            for cat_name, entries in det.items():
                for e in entries:
                    tn = odds["home_name"] if "home" in cat_name else odds["away_name"]
                    w_hist.writerow({
                        "Match_ID": match_id,
                        "Team_Name": tn,
                        "Type": cat_name,
                        "Date": e["date"],
                        "Opponent": e["opponent"],
                        "Score": e["score"],
                        "GD": e["gd"],
                        "Points": e["points"],
                        "Result": e["result"],
                        "Role": e["role"],
                        "Competition": e.get("competition", "")
                    })
            f_hist.flush()
            
            saved += 1
            if not HAS_TQDM:
                logger.info(f"[{i}/{len(matches)}] Zapisano: {odds.get('home_name')} vs {odds.get('away_name')}")

        f_main.close()
        f_hist.close()
        
        logger.info(f"Zapisano {saved} meczów, pominięto {skipped}")

        # Tworzenie Excela
        logger.info("Tworzenie pliku Excel...")
        try:
            with pd.ExcelWriter(args.final_excel, engine='openpyxl') as writer:
                if os.path.exists(args.out):
                    pd.read_csv(args.out, sep=';').to_excel(writer, sheet_name="Mecze", index=False)
                if os.path.exists(args.hist_out):
                    pd.read_csv(args.hist_out, sep=';').to_excel(writer, sheet_name="Historia", index=False)
                for tf in glob.glob(os.path.join(temp_dir, "*.csv")):
                    sheet_name = os.path.basename(tf).replace(".csv", "")[:31]
                    pd.read_csv(tf, sep=';').to_excel(writer, sheet_name=sheet_name, index=False)
            logger.info(f"Excel zapisany: {args.final_excel}")
        except Exception as e:
            logger.error(f"Błąd tworzenia Excela: {e}")

    except KeyboardInterrupt:
        logger.warning("Przerwano przez użytkownika (Ctrl+C)")
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd: {e}")
        raise
    finally:
        driver.quit()
        logger.info("Zakończono.")


if __name__ == "__main__":
    main()
