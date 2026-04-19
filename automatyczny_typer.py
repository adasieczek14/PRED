# -*- coding: utf-8 -*-
"""
Automatyczny Generator Typów (Typer)
Czyta nierozegrane mecze na dany dzien ze strony FC Tables ("vs") 
i poddaje je doglebnej weryfikacji przez Silnik Predykcyjny (KNN). 
Zapisuje do sortowanego docelowego pliku CSV.
"""

import argparse
import csv
import os
import sys
from datetime import datetime

from bs4 import BeautifulSoup
import pandas as pd

# Importy z plikow narzedziowych w folderze
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fctables_scraper import setup_driver, accept_cookies, human_sleep, CONFIG
from silnik_predykcji import load_and_prepare_data, find_similar_matches

def scrape_unplayed_date(driver, target_date: str) -> list:
    """Zczytuje wszystkie nierozegrane mecze (zawierajace znacznik "vs" oraz kurs) z fctables na dany dzien"""
    url = f"{CONFIG['BASE_URL']}{target_date}/"
    print(f"Pobieranie tabeli nierozegranych spotkan na dzien: {target_date}...")
    try:
        driver.get(url)
    except Exception as e:
        print(f"Błąd wywoływania przeglądarki URL: {e}")
        return []
        
    accept_cookies(driver)
    
    # Przewijanie w celach wygenerowania leniwych danych JS
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
        print(f"Nie mogłem znaleźć głównej tabeli meczowej na dzień {target_date}.")
        return []
        
    rows = table.find_all("tr")
    if not rows:
        return []
        
    unplayed_matches = []
    
    for row in rows:
        if row.get("class") and "ad-row" in row.get("class"):
            continue
            
        cells = row.find_all(["td", "th"])
        if len(cells) >= 6:
            row_data = [cell.get_text(strip=True, separator=" ") for cell in cells]
            
            godzina = row_data[0] # Kolumna Data/Godzina w FCTables
            raw_mecz = row_data[1]
            liga = row_data[2]
            raw_kurs = row_data[3]
            raw_tfi_ha = row_data[4]
            raw_tfi = row_data[5]
            
            if raw_mecz.lower() == "mecz" and liga.lower() == "liga":
                continue

            # Szukamy spotkań zawierających ' vs ' - co świadczy o nierozegranym meczu a zaplanowanym
            if " vs " in raw_mecz.lower():
                parts = raw_mecz.split(" vs ", 1)
                home_team = parts[0].strip()
                away_team = parts[1].strip() if len(parts) > 1 else ""
                
                # Tylko z kursami podanymi
                if not raw_kurs or "-" in raw_kurs or ":" not in raw_kurs:
                    continue 
                
                try:
                    # Typowanie z formatu FCT np. "2 : 1.40"
                    k_parts = raw_kurs.split(" : ")
                    faworyt = int(k_parts[0].strip())
                    kurs_val = float(k_parts[1].strip().replace(",", "."))
                    tfi_ha = float(raw_tfi_ha.replace(",", "."))
                    tfi = float(raw_tfi.replace(",", "."))
                except ValueError:
                    continue # Pomijamy błędy rzutowania np gdy gra rzuca nam Puste okieneczka
                
                unplayed_matches.append({
                    "Godzina": godzina,
                    "Mecz": f"{home_team} vs {away_team}",
                    "Liga": liga,
                    "Faworyt": faworyt,
                    "Kurs": kurs_val,
                    "TFI": tfi,
                    "TFI_HA": tfi_ha
                })
                
    print(f"Znaleziono {len(unplayed_matches)} nadchodzacych meczow do analizy modelowej.")
    return unplayed_matches

def main():
    parser = argparse.ArgumentParser(description="Automatyczny Typowacz spotkań (Wyszukiwanie Typów ze wzoru ML)")
    parser.add_argument("--data", default=datetime.now().strftime("%Y-%m-%d"), help="Data dzisiejsza (np. 2026-03-11).")
    parser.add_argument("--k", type=int, default=20, help="Punkty odniesienia K - ile sąsiadów z bazy 140k pobrac by liczyc szanse.")
    
    args = parser.parse_args()
    
    # 1. Zescrapuj nierozegrane jeszcze spotkania na wybrany dzien (domyslnie dzisiaj)
    print("\nUruchamiam silnik Google Chrome... Sprawdzam zblizajace sie mecze...")
    driver = setup_driver(headless=True) # Chrome niewidocznie z tylu w pamieci by nie przeszkadzac
    matches_to_analyze = scrape_unplayed_date(driver, args.data)
    driver.quit()
    
    if not matches_to_analyze:
        print("Brak zaplanowanych spotkan u Bukmachera do odczytu / wszystkie zostaly juz rozegrane.")
        return
        
    # 2. Zaladuj baze treningowa tylko raz. Nie obciazac we/wy!
    df_history = load_and_prepare_data()
    
    # 3. Przepuszczamy nowo pobrane wykazania przez Silnik AI
    results = []
    print(f"\nModel AI ocenia szanse dla zaplanowanych {len(matches_to_analyze)} meczów, moment...")
    
    for m in matches_to_analyze:
        pred_data = find_similar_matches(
            df=df_history,
            current_tfi=m['TFI'],
            current_tfi_ha=m['TFI_HA'],
            current_kurs=m['Kurs'],
            current_faworyt=m['Faworyt'],
            k_neighbors=args.k,
            quiet=True # Ważna funkcja by nie wyrzucać tysiące stron tekstu i wulgarnie zapchać wiersza!
        )
        
        # Wyłuskaj zwrotki modelowe na czytelne wartosci do procentów
        szansa_1 = pred_data.get('szansa_1', 0)
        szansa_X = pred_data.get('szansa_X', 0)
        szansa_2 = pred_data.get('szansa_2', 0)
        
        results.append({
            "Godzina": m['Godzina'],
            "Mecz": m['Mecz'],
            "Liga": m['Liga'],
            "Kurs [Faworyt]": f"{m['Kurs']} ({m['Faworyt']})",
            "% Wygranej Gospodarza [1]": round(szansa_1, 1),
            "% Wygranej Goscia [2]": round(szansa_2, 1),
            "% Remisu [X]": round(szansa_X, 1)
        })

    # Zapisz i Posortuj plik na uzytek uzytkownika do obstawiania (najwazniejsze prawdopodobieństwa od Finału Faworyzacji)
    df_results = pd.DataFrame(results)
    
    # Sortuje siec by miec na samej górze spotkania w których AI mowi nam np "tu masz 95% na 1, weź se go doloż"
    df_results['Max_Szansa'] = df_results[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]']].max(axis=1)
    df_results = df_results.sort_values(by="Max_Szansa", ascending=False).drop(columns=['Max_Szansa'])
    
    # 4. Zapis Eksportowy
    file_name = f"DZISIEJSZE_TYPY_{args.data}.csv"
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
    df_results.to_csv(save_path, sep=';', index=False, encoding='utf-8-sig') # utf-8-sig pomaga Excelowi z polskimi znakami
    
    print("\n" + "="*60)
    print(f"ZNALEZIONE ZŁOTA - Twój własny plik ekspertowy '{file_name}' zostal wlasnie wyeksportowany!")
    print("Otwórz go w Excelu od razu widząc % faworyzacji i od samej góry szukaj bezpiecznych wygranych.")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
