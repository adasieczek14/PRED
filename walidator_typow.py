# -*- coding: utf-8 -*-
"""
Walidator Skuteczności Typów (Backtester)
Wczytuje historyczne pliki z predykcjami (DZISIEJSZE_TYPY_*.csv), pobiera 
rzeczywiste wyniki rozegranych już spotkań z fctables.com i rozlicza trafność oraz zysk (ROI).
"""

import argparse
import csv
import glob
import os
import sys
import time
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup

# Importy z plikow narzedziowych w folderze
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fctables_scraper import setup_driver, accept_cookies, human_sleep, CONFIG

def get_actual_results(driver, target_date: str) -> dict:
    """
    Zczytuje wyniki rozegranych spotkań z fctables na podany dzień.
    Zwraca słownik: {"Home vs Away": "rezultat", ...} (np. "1", "X", "2")
    """
    url = f"{CONFIG['BASE_URL']}{target_date}/"
    print(f"Pobieranie tabeli RZECZYWISTYCH wynikow na dzien: {target_date}...")
    try:
        driver.get(url)
    except Exception as e:
        print(f"Błąd wywoływania przeglądarki URL: {e}")
        return {}
        
    accept_cookies(driver)
    
    # Przewijanie w celach wygenerowania leniwych danych JS
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        human_sleep(1.0, 2.0)
    except Exception:
        pass

    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", class_="stage-table")
    
    if not table:
        print(f"Nie mogłem znaleźć tabeli meczów dla dnia {target_date}.")
        return {}
        
    rows = table.find_all("tr")
    actual_results = {}
    
    for row in rows:
        if row.get("class") and "ad-row" in row.get("class"):
            continue
            
        cells = row.find_all(["td", "th"])
        if len(cells) >= 6:
            row_data = [cell.get_text(strip=True, separator=" ") for cell in cells]
            raw_mecz = row_data[1]
            
            if " : " not in raw_mecz:
                continue # mecz odwolany, bez wyniku lub 'vs'
                
            parts = raw_mecz.split(" : ")
            if len(parts) >= 2:
                try:
                    home_team_raw = parts[0].rsplit(" ", 1)
                    home_team = home_team_raw[0].strip()
                    gole_gospodarzy = int(home_team_raw[1].strip())
                    
                    away_team_raw = parts[1].split(" ", 1)
                    gole_gosci = int(away_team_raw[0].strip())
                    away_team = away_team_raw[1].strip() if len(away_team_raw) > 1 else ""
                    
                    # Oblicz rezultat (1, X, 2)
                    if gole_gospodarzy > gole_gosci:
                        rezultat = "1"
                    elif gole_gospodarzy == gole_gosci:
                        rezultat = "X"
                    else:
                        rezultat = "2"
                        
                    match_key = f"{home_team} vs {away_team}".lower()
                    actual_results[match_key] = (rezultat, f"{gole_gospodarzy}:{gole_gosci}")
                except (ValueError, IndexError):
                    pass
                    
    return actual_results

def validate_predictions(file_path: str, driver) -> bool:
    """Sprawdza plik z typami i przypisuje im rzeczywiste wyniki z netu. Zwraca True jesli zwalidowano nowosci."""
    filename = os.path.basename(file_path)
    # Usuwamy wszystkie znane prefiksy (kolejność ważna: ENSEMBLE przed XGB przed zwykłym)
    date_str = (filename
                .replace("DZISIEJSZE_TYPY_ENSEMBLE_", "")
                .replace("DZISIEJSZE_TYPY_XGB_", "")
                .replace("DZISIEJSZE_TYPY_", "")
                .replace(".csv", ""))
    
    # Upewnij sie, ze minął już ten dzień. (Nie walidujemy dzisiejszych przed 23:59!)
    file_dt = datetime.strptime(date_str, "%Y-%m-%d")
    today_dt = datetime.now()
    if file_dt.date() >= today_dt.date():
        print(f"Pominieto {filename} - mecze z tego dnia jeszcze trwaja/nie zostaly rozegrane.")
        return False
        
    out_file = file_path.replace("DZISIEJSZE_TYPY_", "ZWALIDOWANE_TYPY_")
    if os.path.exists(out_file):
        print(f"Plik {filename} juz zwalidowany ({os.path.basename(out_file)}). Pomijam.")
        return False
        
    df = pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
    if df.empty:
        return False
        
    actual_results = get_actual_results(driver, date_str)
    if not actual_results:
        print(f"Brak pobranych wynikow dla daty {date_str}. Byc moze to off-season.")
        return False
        
    # Walidacja i doklejanie kolumn
    wyniki_rzeczywiste = []
    dokladny_wynik = []
    statusy = []
    zyski = []
    typy_modelu = []
    
    stawka = 100.0 # stala płaska stawka np. 100 zl 
    
    for idx, row in df.iterrows():
        mecz = str(row['Mecz']).lower().strip()
        wynik_data = actual_results.get(mecz, ("Brak/Odwolany", "-"))
        rozegrany_wynik = wynik_data[0]
        gole_mecz = wynik_data[1]
        
        # Jaki typ model obstawil? (Najwyższe prawdopodobieństwo)
        p_1 = float(row.get('% Wygranej Gospodarza [1]', 0))
        p_X = float(row.get('% Remisu [X]', 0))
        p_2 = float(row.get('% Wygranej Goscia [2]', 0))
        
        max_p = max(p_1, p_X, p_2)
        typ_modelu = ""
        if max_p == p_1: typ_modelu = "1"
        elif max_p == p_2: typ_modelu = "2"
        else: typ_modelu = "X"
            
        typy_modelu.append(typ_modelu)
        wyniki_rzeczywiste.append(rozegrany_wynik)
        
        # Parsowanie Kursu na faworyta (np. "1.45 (1)")
        kurs_faw_str = str(row.get('Kurs [Faworyt]', '0.0 (X)'))
        kurs_w_liczbie = 0.0
        faworyt_kto = ""
        if "(" in kurs_faw_str:
            k_part = kurs_faw_str.split("(")
            try:
                kurs_w_liczbie = float(k_part[0].strip())
                faworyt_kto = k_part[1].replace(")", "").strip()
            except ValueError:
                pass
        
        status = "Odwolany"
        zysk = 0.0
        
        if rozegrany_wynik in ["1", "X", "2"]:
            # Sprawdzenie czy model trafil!
            if typ_modelu == rozegrany_wynik:
                status = "WYGRANA"
                # Czy mozemy policzyc zysk? Fctables daje nam kursy tylko na Faworytow
                if typ_modelu == faworyt_kto and kurs_w_liczbie > 0:
                    zysk = (stawka * kurs_w_liczbie) - stawka
                else:
                    # Trafilismy, ale brak kursu w fctables na wygrana underdoga/remis, dla bezpieczenstwa zysk=0 
                    zysk = 0.0
            else:
                status = "PRZEGRANA"
                # Jesli gramy, to zawsze tracimy cala stawke 100zl (jesli to my wytypowalismy i to nie siadlo)
                zysk = -stawka
                
        statusy.append(status)
        zyski.append(zysk)
        dokladny_wynik.append(gole_mecz)
        
    df['Typ_Modelu'] = typy_modelu
    df['Wynik_Rzeczywisty'] = wyniki_rzeczywiste
    df['Gole'] = dokladny_wynik
    df['Status'] = statusy
    df['Zysk/Strata (Flat 100)'] = zyski
    
    # Statystyki do pokazania konsoli
    wygrane = statusy.count("WYGRANA")
    przegrane = statusy.count("PRZEGRANA")
    suma_profitu = sum(zyski)
    
    print(f"--- Walidacja Dnia: {date_str} ---")
    print(f"Trafione: {wygrane}, Pudła: {przegrane}")
    print(f"Profit/Strata (stawka 100): {round(suma_profitu, 2)}")
    
    # Save validation
    df.to_csv(out_file, sep=';', index=False, encoding='utf-8-sig')
    print(f"Zapisano zweryfikowany plik: {out_file}\n")
    return True

def main():
    parser = argparse.ArgumentParser(description="Walidator Typow AI - Oblicza ROI w oparciu o prawdziwe wyniki z przeszłości")
    parser.add_argument("--date", type=str, default="", help="Konkretna data do walidacji (np. 2026-03-12). Puste = Sprawdza wszystkie niezwalidowane.")
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if args.date:
        files = [
            os.path.join(base_dir, f"DZISIEJSZE_TYPY_{args.date}.csv"),
            os.path.join(base_dir, f"DZISIEJSZE_TYPY_XGB_{args.date}.csv")
        ]
        pliki_do_sprawdzenia = [f for f in files if os.path.exists(f)]
    else:
        pliki_do_sprawdzenia = sorted(glob.glob(os.path.join(base_dir, "DZISIEJSZE_TYPY_*.csv")))
        
    if not pliki_do_sprawdzenia:
        print("Nie znaleziono starych plików CSV z predykcjami do zwalidowania.")
        return
        
    print("Uruchamiam silnik weryfikacyjny (Chrome Headless)...")
    driver = setup_driver(headless=True)
    
    validated_any = False
    try:
        for file_path in pliki_do_sprawdzenia:
            res = validate_predictions(file_path, driver)
            if res:
                validated_any = True
                human_sleep(2, 4)
    finally:
        driver.quit()
        
    if not validated_any:
        print("Wszystkie dostepne pliki z przeszlosci zostaly juz wczesniej zwalidowane! Panel oczekuje na nastepny dzien.")

if __name__ == "__main__":
    main()
