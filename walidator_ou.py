# -*- coding: utf-8 -*-
"""
Walidator Typów Over/Under (Backtester)
Wczytuje historyczne pliki DZISIEJSZE_TYPY_OU_*.csv, pobiera rzeczywiste
wyniki (gole) z fctables.com i rozlicza trafność Over 1.5 / Over 2.5 / BTTS.

Wynik zapisuje do: ZWALIDOWANE_TYPY_OU_YYYY-MM-DD.csv
"""

import glob
import os
import sys
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fctables_scraper import setup_driver, accept_cookies, human_sleep, CONFIG


# ──────────────────────────────────────────────────────────────────────────────
# Pobieranie rzeczywistych wyników (gole) z fctables
# ──────────────────────────────────────────────────────────────────────────────

def get_actual_goals(driver, target_date: str) -> dict:
    """
    Zczytuje rzeczywiste wyniki (gole) z fctables na podany dzień.
    Zwraca słownik: {"Home vs Away": (gole_h, gole_a), ...}
    """
    url = f"{CONFIG['BASE_URL']}{target_date}/"
    print(f"Pobieranie RZECZYWISTYCH GOLI dla dnia: {target_date}...")
    try:
        driver.get(url)
    except Exception as e:
        print(f"Błąd otwierania URL: {e}")
        return {}

    accept_cookies(driver)

    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        human_sleep(1.0, 2.0)
    except Exception:
        pass

    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", class_="stage-table")

    if not table:
        print(f"Nie znaleziono tabeli meczów dla dnia {target_date}.")
        return {}

    goals_dict = {}

    for row in table.find_all("tr"):
        if row.get("class") and "ad-row" in row.get("class"):
            continue

        cells = row.find_all(["td", "th"])
        if len(cells) < 6:
            continue

        row_data = [cell.get_text(strip=True, separator=" ") for cell in cells]
        raw_mecz = row_data[1]

        # Rozegrany mecz zawiera " : " z wynikiem
        if " : " not in raw_mecz:
            continue

        parts = raw_mecz.split(" : ")
        if len(parts) < 2:
            continue

        try:
            home_raw = parts[0].rsplit(" ", 1)
            home_team = home_raw[0].strip()
            gole_h = int(home_raw[1].strip())

            away_raw = parts[1].split(" ", 1)
            gole_a = int(away_raw[0].strip())
            away_team = away_raw[1].strip() if len(away_raw) > 1 else ""

            match_key = f"{home_team} vs {away_team}".lower()
            goals_dict[match_key] = (gole_h, gole_a)

        except (ValueError, IndexError):
            pass

    print(f"  Znaleziono wyniki dla {len(goals_dict)} rozegranych meczów.")
    return goals_dict


# ──────────────────────────────────────────────────────────────────────────────
# Walidacja jednego pliku O/U
# ──────────────────────────────────────────────────────────────────────────────

STAWKA = 100.0  # płaska stawka do ROI

# Typowe kursy rynkowe na O/U (uproszczone — fctables nie podaje kursów O/U)
KURS_OVER_15 = 1.25
KURS_OVER_25 = 1.60
KURS_BTTS    = 1.75


def validate_ou_file(file_path: str, driver) -> bool:
    """
    Waliduje jeden plik DZISIEJSZE_TYPY_OU_*.csv.
    Zwraca True jeśli plik został zwalidowany (był nowy).
    """
    filename = os.path.basename(file_path)
    date_str = filename.replace("DZISIEJSZE_TYPY_OU_", "").replace(".csv", "")

    # Nie waliduj dzisiejszych — wyniki jeszcze trwają
    try:
        file_dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"Pominięto {filename} — nie można odczytać daty.")
        return False

    if file_dt.date() >= datetime.now().date():
        print(f"Pominięto {filename} — mecze jeszcze nie rozegrane.")
        return False

    out_file = os.path.join(
        os.path.dirname(file_path),
        f"ZWALIDOWANE_TYPY_OU_{date_str}.csv"
    )
    if os.path.exists(out_file):
        print(f"Już zwalidowany: {os.path.basename(out_file)} — pomijam.")
        return False

    df = pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
    if df.empty:
        print(f"Plik {filename} jest pusty.")
        return False

    goals = get_actual_goals(driver, date_str)
    if not goals:
        print(f"Brak wyników dla {date_str}.")
        return False

    # Kolumny wynikowe
    col_gole      = []
    col_over05    = []
    col_over15    = []
    col_over25    = []
    col_btts      = []
    col_status_15 = []
    col_status_25 = []
    col_status_btts = []
    col_zysk_15   = []
    col_zysk_25   = []
    col_zysk_btts = []

    for _, row in df.iterrows():
        mecz_key = str(row['Mecz']).lower().strip()
        wynik = goals.get(mecz_key)

        if wynik is None:
            # Mecz nierozegrany / brak danych
            col_gole.append("-")
            col_over05.append("-")
            col_over15.append("-")
            col_over25.append("-")
            col_btts.append("-")
            col_status_15.append("Brak")
            col_status_25.append("Brak")
            col_status_btts.append("Brak")
            col_zysk_15.append(0.0)
            col_zysk_25.append(0.0)
            col_zysk_btts.append(0.0)
            continue

        gh, ga = wynik
        total = gh + ga

        # Faktyczne zrealizowanie rynku
        fact_over05 = int(total >= 1)
        fact_over15 = int(total >= 2)
        fact_over25 = int(total >= 3)
        fact_btts   = int(gh >= 1 and ga >= 1)

        col_gole.append(f"{gh}:{ga}")
        col_over05.append("TAK" if fact_over05 else "NIE")
        col_over15.append("TAK" if fact_over15 else "NIE")
        col_over25.append("TAK" if fact_over25 else "NIE")
        col_btts.append("TAK" if fact_btts else "NIE")

        # Próg modelu — kiedy "typujemy" Over
        prog_o15 = float(row.get('% Over 1.5', 0))
        prog_o25 = float(row.get('% Over 2.5', 0))
        prog_btts = float(row.get('% BTTS', 0))

        # Status Over 1.5 (typujemy jeśli model ≥ 50%)
        if prog_o15 >= 50:
            if fact_over15:
                col_status_15.append("WYGRANA")
                col_zysk_15.append(round((STAWKA * KURS_OVER_15) - STAWKA, 2))
            else:
                col_status_15.append("PRZEGRANA")
                col_zysk_15.append(-STAWKA)
        else:
            col_status_15.append("Nie typowano")
            col_zysk_15.append(0.0)

        # Status Over 2.5
        if prog_o25 >= 50:
            if fact_over25:
                col_status_25.append("WYGRANA")
                col_zysk_25.append(round((STAWKA * KURS_OVER_25) - STAWKA, 2))
            else:
                col_status_25.append("PRZEGRANA")
                col_zysk_25.append(-STAWKA)
        else:
            col_status_25.append("Nie typowano")
            col_zysk_25.append(0.0)

        # Status BTTS
        if prog_btts >= 50:
            if fact_btts:
                col_status_btts.append("WYGRANA")
                col_zysk_btts.append(round((STAWKA * KURS_BTTS) - STAWKA, 2))
            else:
                col_status_btts.append("PRZEGRANA")
                col_zysk_btts.append(-STAWKA)
        else:
            col_status_btts.append("Nie typowano")
            col_zysk_btts.append(0.0)

    # Doklejenie wyników do DataFrame
    df['Wynik_Gole']        = col_gole
    df['Over_05_Real']      = col_over05
    df['Over_15_Real']      = col_over15
    df['Over_25_Real']      = col_over25
    df['BTTS_Real']         = col_btts
    df['Status_Over_15']    = col_status_15
    df['Status_Over_25']    = col_status_25
    df['Status_BTTS']       = col_status_btts
    df['Zysk_Over_15']      = col_zysk_15
    df['Zysk_Over_25']      = col_zysk_25
    df['Zysk_BTTS']         = col_zysk_btts

    # Statystyki do konsoli
    w15  = col_status_15.count("WYGRANA")
    p15  = col_status_15.count("PRZEGRANA")
    w25  = col_status_25.count("WYGRANA")
    p25  = col_status_25.count("PRZEGRANA")
    wbtts= col_status_btts.count("WYGRANA")
    pbtts= col_status_btts.count("PRZEGRANA")

    wr15  = w15  / (w15  + p15)  * 100 if (w15  + p15)  > 0 else 0
    wr25  = w25  / (w25  + p25)  * 100 if (w25  + p25)  > 0 else 0
    wrbtts= wbtts/ (wbtts+ pbtts)* 100 if (wbtts+ pbtts)> 0 else 0

    print(f"\n--- Walidacja O/U: {date_str} ---")
    print(f"  Over 1.5 : {w15}W / {p15}P  | Win Rate: {wr15:.0f}%  | Profit: {sum(col_zysk_15):+.0f}j")
    print(f"  Over 2.5 : {w25}W / {p25}P  | Win Rate: {wr25:.0f}%  | Profit: {sum(col_zysk_25):+.0f}j")
    print(f"  BTTS     : {wbtts}W / {pbtts}P  | Win Rate: {wrbtts:.0f}%  | Profit: {sum(col_zysk_btts):+.0f}j")

    df.to_csv(out_file, sep=';', index=False, encoding='utf-8-sig')
    print(f"Zapisano: {os.path.basename(out_file)}\n")
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Walidator Over/Under — sprawdza faktyczne gole i liczy ROI")
    parser.add_argument(
        "--date", type=str, default="",
        help="Konkretna data do walidacji (np. 2026-04-13). Puste = wszystkie niezwalidowane."
    )
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))

    if args.date:
        files = [os.path.join(base_dir, f"DZISIEJSZE_TYPY_OU_{args.date}.csv")]
        pliki = [f for f in files if os.path.exists(f)]
    else:
        pliki = sorted(glob.glob(os.path.join(base_dir, "DZISIEJSZE_TYPY_OU_*.csv")))

    if not pliki:
        print("Brak plików O/U do zwalidowania (DZISIEJSZE_TYPY_OU_*.csv).")
        return

    print(f"Znaleziono {len(pliki)} pliku(ów) O/U do sprawdzenia.")
    print("Uruchamiam Chrome Headless...")
    driver = setup_driver(headless=True)

    try:
        for f in pliki:
            validate_ou_file(f, driver)
            human_sleep(2, 3)
    finally:
        driver.quit()

    print("Walidacja O/U zakończona.")


if __name__ == "__main__":
    main()
