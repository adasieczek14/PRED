# -*- coding: utf-8 -*-
"""
ULEPSZENIE #6 — Aktualizacja Bazy Treningowej o Zwalidowane Mecze
==================================================================
Problem: Model uczy się wyłącznie ze statycznej bazy fctables_data_tranformacja.csv
(dane historyczne do pewnego momentu). Natomiast mecze które system codziennie
wytypował i zwalidował (ZWALIDOWANE_TYPY_XGB_HISTORYCZNIE.csv) NIE trafiają
z powrotem do treningu — model nie "uczy się na błędach z 2026 roku".

Rozwiązanie: Ten skrypt mapuje kolumny z pliku zwalidowanych historycznych typów
na format bazy treningowej i dokleja je, eliminując duplikaty.

OGRANICZENIE: Pliki ZWALIDOWANE nie zawierają kolumn TFI i TFI HA (nie były
zapisywane podczas scrapowania). Wiersze bez TFI zostaną dodane do bazy ale
odpadną przy dropna() podczas treningu KNN/XGB (potrzebują TFI do predykcji).
Są przydatne jako pełna ewidencja meczów.

Użycie:
  python aktualizuj_baze_treningowa.py
  python aktualizuj_baze_treningowa.py --dry-run   (tylko podgląd, bez zapisu)
"""

import argparse
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
HIST_XGB_FILE = os.path.join(BASE_DIR, "ZWALIDOWANE_TYPY_XGB_HISTORYCZNIE.csv")
TRAINING_FILE = r"C:\Users\admin\Desktop\PRACA INZYNIERSKA\DANE CSV PO TRANSFOMACJI\fctables_data_tranformacja.csv"


def extract_kurs_faworyt(s: str):
    """Parsuje '1.35 (1)' → (1.35, 1). Zwraca (None, None) przy błędzie."""
    try:
        parts = str(s).split('(')
        kurs = float(parts[0].strip().replace(',', '.'))
        faw  = int(parts[1].replace(')', '').strip())
        return kurs, faw
    except Exception:
        return None, None


def split_mecz(s: str):
    """Parsuje 'Chelsea vs Arsenal' → ('Chelsea', 'Arsenal')."""
    if ' vs ' in str(s):
        parts = str(s).split(' vs ', 1)
        return parts[0].strip(), parts[1].strip()
    return str(s).strip(), ''


def split_gole(s: str):
    """Parsuje '2:1' → (2, 1). Zwraca (None, None) przy błędzie."""
    try:
        parts = str(s).split(':')
        return int(parts[0].strip()), int(parts[1].strip())
    except Exception:
        return None, None


def map_wynik_do_skutecznosc(wynik: str, faworyt: int) -> int:
    """Zwraca 1 jeśli faworyt wygrał, 0 jeśli nie."""
    try:
        wynik_int = int(wynik) if wynik in ('1', '2') else None
        return 1 if wynik_int == faworyt else 0
    except Exception:
        return 0


def main():
    parser = argparse.ArgumentParser(description="Aktualizator Bazy Treningowej — dołącza zwalidowane mecze")
    parser.add_argument("--dry-run", action="store_true",
                        help="Tylko podgląd — nie zapisuje zmian do pliku")
    args = parser.parse_args()
    
    print("=" * 60)
    print("  AKTUALIZACJA BAZY TRENINGOWEJ (Ulepszenie #6)")
    print("=" * 60)
    
    # 1. Sprawdź czy pliki istnieją
    if not os.path.exists(HIST_XGB_FILE):
        print(f"\n❌ Brak pliku: {HIST_XGB_FILE}")
        print("   Uruchom najpierw walidator_typow.py by wygenerować historię XGB.")
        sys.exit(1)
    
    if not os.path.exists(TRAINING_FILE):
        print(f"\n❌ Brak pliku treningowego: {TRAINING_FILE}")
        sys.exit(1)
    
    # 2. Załaduj zwalidowane mecze
    print(f"\nCzytam: {os.path.basename(HIST_XGB_FILE)}")
    df_hist = pd.read_csv(HIST_XGB_FILE, sep=';', encoding='utf-8-sig')
    df_hist = df_hist[df_hist['Status'].isin(['WYGRANA', 'PRZEGRANA'])].copy()
    print(f"Znaleziono {len(df_hist)} zwalidowanych meczów (WYGRANA/PRZEGRANA).")
    
    # 3. Załaduj bazę treningową
    print(f"\nCzytam bazę treningową ({os.path.basename(TRAINING_FILE)})...")
    df_base = pd.read_csv(TRAINING_FILE, sep=';', encoding='utf-8')
    print(f"Baza przed aktualizacją: {len(df_base):,} wierszy.")
    
    # 4. Stwórz klucz duplikatów na podstawie istniejącej bazy (Data + Drużyny)
    existing_keys = set()
    for _, row in df_base.iterrows():
        key = f"{str(row.get('Data',''))}__{str(row.get('Druzyna_Gospodarzy',''))}_{str(row.get('Druzyna_Gosci',''))}"
        existing_keys.add(key.lower().strip())
    
    # 5. Mapuj kolumny z pliku historycznego na format bazy treningowej
    nowe_wiersze = []
    pominięte_duplikaty = 0
    błędne_wiersze = 0
    
    for _, row in df_hist.iterrows():
        kurs, faworyt = extract_kurs_faworyt(row.get('Kurs [Faworyt]', ''))
        if kurs is None or faworyt is None:
            błędne_wiersze += 1
            continue
        
        druzyna_gosp, druzyna_gosci = split_mecz(row.get('Mecz', ''))
        gole_gosp, gole_gosci = split_gole(row.get('Gole', ''))
        wynik_rzecz = str(row.get('Wynik_Rzeczywisty', ''))
        data_val = str(row.get('Data_Rozegrania', ''))
        
        # Unormowana data dla klucza duplikatów
        key = f"{data_val}__{druzyna_gosp}_{druzyna_gosci}".lower().strip()
        if key in existing_keys:
            pominięte_duplikaty += 1
            continue
        
        existing_keys.add(key)
        
        nowy = {
            'Data':               data_val,
            'Druzyna_Gospodarzy': druzyna_gosp,
            'GOLE_Gospodarzy':    gole_gosp,
            'GOLE_Gosci':         gole_gosci,
            'Druzyna_Gosci':      druzyna_gosci,
            'Liga':               str(row.get('Liga', '')),
            'Faworyt':            faworyt,
            'Kurs':               kurs,
            'TFI HA':             None,   # Niedostępne w pliku historycznym
            'TFI':                None,   # Niedostępne w pliku historycznym
            'ID_GOSPO':           None,
            'ID_GOSCI':           None,
            'Skutecznosc_Faworyta': map_wynik_do_skutecznosc(wynik_rzecz, faworyt),
            'REMIS':              1 if wynik_rzecz == 'X' else 0,
            'Rezultat':           wynik_rzecz,
        }
        nowe_wiersze.append(nowy)
    
    # 6. Raport
    print(f"\n--- Wyniki mapowania ---")
    print(f"  Nowe unikalne mecze do dodania: {len(nowe_wiersze)}")
    print(f"  Pominięte (duplikaty):          {pominięte_duplikaty}")
    print(f"  Pominięte (błąd parsowania):    {błędne_wiersze}")
    print(f"\n  ℹ️  TFI i TFI HA ustawione na NULL — te mecze nie wpłyną na trening")
    print(f"     modeli KNN/XGB (zostaną odfiltrowane przez dropna()), ale są")
    print(f"     zapisane jako pełna ewidencja rozegranych spotkań.")
    
    if not nowe_wiersze:
        print("\n✅ Baza jest już aktualna — brak nowych meczów do dodania.")
        return
    
    # 7. Dołącz nowe wiersze
    df_nowe = pd.DataFrame(nowe_wiersze)
    df_polaczone = pd.concat([df_base, df_nowe], ignore_index=True)
    
    print(f"\n  Baza po aktualizacji: {len(df_polaczone):,} wierszy  (+{len(nowe_wiersze)})")
    
    if args.dry_run:
        print("\n  [DRY-RUN] Zmiany NIE zostały zapisane (flaga --dry-run).")
        print("  Usuń flagę --dry-run aby zapisać.")
    else:
        df_polaczone.to_csv(TRAINING_FILE, sep=';', index=False, encoding='utf-8')
        print(f"\n✅ Zapisano zaktualizowaną bazę: {TRAINING_FILE}")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
