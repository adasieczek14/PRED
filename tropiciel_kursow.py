import os
import sys
import time
import glob
import re
import pandas as pd
import urllib.parse
import urllib.request
from datetime import datetime
import undetected_chromedriver as my_uc
from selenium_stealth import stealth
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try: sys.stdout.reconfigure(encoding='utf-8')
except: pass

def setup_driver():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    browser_path = os.path.join(base_dir, "chrome-win64", "chrome.exe")
    if not os.path.exists(browser_path):
        browser_path = os.path.join(base_dir, "chrome-win64", "chrome-win64", "chrome.exe")
    driver_path = os.path.join(base_dir, "chromedriver-win64", "chromedriver.exe")
    if not os.path.exists(driver_path):
        driver_path = os.path.join(base_dir, "chromedriver-win64", "chromedriver-win64", "chromedriver.exe")
    
    opts = my_uc.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--no-first-run")
    opts.add_argument("--window-size=1920,1080")

    if os.path.exists(browser_path):
        opts.binary_location = browser_path

    kwargs = {"options": opts, "use_subprocess": True}
    if os.path.exists(driver_path):
        kwargs["driver_executable_path"] = driver_path
            
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
    return driver

def find_flashscore_url(query: str) -> str:
    """Szuka URL meczu na Flashscore przez Google (requests, bez przeglądarki)."""
    search_q = urllib.parse.quote(f"site:flashscore.pl/mecz {query}")
    url = f"https://www.google.com/search?q={search_q}&num=5&hl=pl"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept-Language": "pl-PL,pl;q=0.9",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # Flashscore ID meczu to 8-znakowy hash alfanumeryczny (bez myślników) np. 'Kb6aUTS7'
        # Kategorie takie jak 'pilka-nozna' zawierają myślniki - odrzucamy je
        matches = re.findall(r'flashscore\.pl/mecz/([A-Za-z0-9]{6,14})/', html)
        if matches:
            m_id = matches[0]
            return f"https://www.flashscore.pl/mecz/{m_id}/#/zestawienie-kursow/kursy-1x2/koniec-meczu"
    except Exception as e:
        print(f"   Google search error: {e}")
    return None

def parse_dropping_odds(title_attr: str):
    if not title_attr or "»" not in title_attr:
        return None, None, 0.0
    # Czysc whitespace (w tym \n) i bierz tylko pierwszą linię z kursami
    first_line = title_attr.split("\n")[0].strip()
    parts = first_line.split("»")
    try:
        open_odd = float(parts[0].strip().replace(',', '.'))
        curr_odd = float(parts[1].strip().replace(',', '.'))
        return open_odd, curr_odd, round(curr_odd - open_odd, 2)
    except:
        return None, None, 0.0

def main():
    print("===================================================")
    print(" [TRACKER] TROPICIEL KURSOW (DROPPING ODDS) - FLASHSCORE ")
    print("===================================================")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = glob.glob(os.path.join(base_dir, "DZISIEJSZE_TYPY_XGB_*.csv"))
    if not csv_files:
        print("Brak jakichkolwiek plików predykcji DZISIEJSZE_TYPY_XGB_*.csv")
        return
        
    csv_file = sorted(csv_files)[-1]
    print(f"Otwieranie najnowszego pliku: {os.path.basename(csv_file)}")
        
    df = pd.read_csv(csv_file, sep=';', encoding='utf-8-sig')
    df['MAX_Szansa'] = df[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
    df_to_check = df[df['MAX_Szansa'] >= 65.0].copy()
    if df_to_check.empty:
        print("Brak spotkań > 65% na dzisiaj.")
        return
        
    if 'Delta_Kursu' not in df.columns:
        df['Kurs_Otwarcia'] = ""
        df['Delta_Kursu'] = ""
        df['Alert_Rynku'] = ""

    print(f"[SZUKAJ] Znaleziono {len(df_to_check)} meczów do prześwietlenia pod kątem wahań rynkowych.")
    
    driver = setup_driver()
    
    for index, row in df_to_check.iterrows():
        safe_query = str(row['Mecz']).encode('ascii', errors='ignore').decode('ascii')
        typ = str(row['Typ_Modelu']).strip()
        print(f" \n--- Skanowanie: {safe_query} ---")
        
        try:
            # 1. Szukaj URL meczu przez Google (requests - szybki, bez Selenium)
            target_url = find_flashscore_url(safe_query)
            
            if not target_url:
                print("   Nie znaleziono meczu w Google. Próba DuckDuckGo...")
                # Fallback: DDG via Selenium - bierzemy href bezposrednio z wynikow
                driver.get("https://lite.duckduckgo.com/lite/")
                time.sleep(1.5)
                try:
                    search_input = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, "q")))
                    search_input.clear()
                    ddg_q = safe_query.replace(' vs ', ' ')
                    search_input.send_keys(f"flashscore.pl/mecz {ddg_q}")
                    search_input.submit()
                    time.sleep(2.5)
                    
                    # Iteruj przez WSZYSTKIE elementy <a> - szukaj href z flashscore.pl/mecz/
                    for a_elem in driver.find_elements(By.TAG_NAME, "a"):
                        href = str(a_elem.get_attribute("href") or "")
                        # Musi byc z flashscore.pl i zawierac /mecz/ (nie /team/, /h2h/ itp.)
                        if "flashscore.pl/mecz/" in href and "h2h" not in href:
                            # Odrzuc linki do strony glownej ligi (bez ?mid= i bez slashow po slug sportu)
                            # Prawidlowy link ma format: /mecz/sport/slug1/slug2/?mid=XXX lub /mecz/sport/slug1/slug2/
                            parts_after_mecz = href.split("/mecz/")[1].rstrip("/").split("?")[0].split("/")
                            # Musi miec przynajmniej 3 segmenty: sport/slug_goscia/slug_gospodarza
                            if len(parts_after_mecz) >= 3:
                                # Zbuduj czysty URL - tylko czesc PRZED ? (bez parametrow query)
                                # format: https://www.flashscore.pl/mecz/sport/slug1/slug2/
                                clean_path = "/".join(parts_after_mecz)
                                base = f"https://www.flashscore.pl/mecz/{clean_path}"
                                target_url = f"{base}/#/zestawienie-kursow/kursy-1x2/koniec-meczu"
                                print(f"   DDG znalazl href: {href}")
                                break
                except Exception as e:
                    print(f"   DDG fallback error: {e}")

            
            if not target_url:
                print("   Nie znaleziono URL meczu Flashscore.")
                continue
                
            print(f"   URL: {target_url}")
            
            # 2. Otwórz stronę meczu
            driver.get(target_url)
            time.sleep(3.5)
            
            # Zamknij nakładki cookies/rodo
            try:
                driver.execute_script("document.querySelectorAll('[class*=\"wcl-overlay\"]').forEach(e => e.remove());")
                driver.execute_script("let btn = document.querySelector('button[id*=\"onetrust-accept-btn\"]'); if (btn) btn.click();")
            except: pass
            
            # 3. Kliknij zakładkę Kursy jeśli nie jest aktywna
            try:
                odds_tab = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/kursy/')]")))
                driver.execute_script("arguments[0].click();", odds_tab)
                time.sleep(2.5)
            except:
                print("   Brak zakładki KURSÓW (niszowa liga).")
                continue
            
            # 4. Pobierz kursy - próbuj sekwencyjnie różne selektory
            SELECTORS = [
                "button[data-testid='wcl-oddsCell']",
                "div[data-testid='wcl-oddsCell']",
                ".oddsCell__odd",
                ".wcl-oddsCell",
                "[class*='oddsCell']",
                "[class*='odds-cell']",
            ]
            odds_cells = []
            used_sel = ""
            for sel in SELECTORS:
                found = driver.find_elements(By.CSS_SELECTOR, sel)
                if len(found) >= 3:
                    odds_cells = found
                    used_sel = sel
                    break
                    
            if len(odds_cells) >= 3:
                cell_idx = 0 if typ == "1" else (2 if typ == "2" else 1)
                cell = odds_cells[cell_idx]
                
                # Pobierz title (JS też dla pewności)
                title_attr = cell.get_attribute("title") or ""
                if "»" not in title_attr:
                    title_attr = driver.execute_script(
                        "return arguments[0].getAttribute('title') || arguments[0].dataset.title || '';", cell
                    ) or ""
                
                open_odd, curr_odd, delta = parse_dropping_odds(title_attr)
                if open_odd is not None:
                    print(f"   [KURS] Otwarcie: {open_odd} → Aktualny: {curr_odd} | Delta: {delta:+.2f}")
                    df.at[index, 'Kurs_Otwarcia'] = open_odd
                    df.at[index, 'Delta_Kursu'] = delta
                    
                    if delta < -0.10:
                        df.at[index, 'Alert_Rynku'] = "GRUBA GRA (Spadek)"
                    elif delta > 0.10:
                        df.at[index, 'Alert_Rynku'] = "OSTRZEZENIE (Rosnie)"
                    else:
                        df.at[index, 'Alert_Rynku'] = "Stabilnie"
                else:
                    curr_text = cell.get_attribute("textContent").strip()
                    print(f"   Brak tooltipa '»' (title='{title_attr}', sel='{used_sel}', text='{curr_text}')")
            else:
                print(f"   Brak kursów - żaden z {len(SELECTORS)} selektorów nie znalazł >=3 elementów.")
                
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                
        except Exception as e:
            err_msg = str(e).split("\n")[0]
            print(f"   Błąd skanowania: {err_msg}")
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

    try:
        driver.quit()
    except: pass
    
    df.drop(columns=['MAX_Szansa'], inplace=True, errors='ignore')
    df.to_csv(csv_file, sep=';', index=False, encoding='utf-8-sig')
    print(f"\n[SUKCES] Operacja zakończona. Plik {os.path.basename(csv_file)} zapisany!")

if __name__ == "__main__":
    main()
