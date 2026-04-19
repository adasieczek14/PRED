# -*- coding: utf-8 -*-
"""
Generator historycznych typów ENSEMBLE
=======================================
Łączy istniejące pliki DZISIEJSZE_TYPY_*.csv (KNN) i DZISIEJSZE_TYPY_XGB_*.csv
w pliki DZISIEJSZE_TYPY_ENSEMBLE_*.csv (ważona średnia), zaczynając od daty 2026-03-25.

Następnie walidator_typow.py może sprawdzić skuteczność tak samo jak dla KNN/XGB.

Użycie:
  python generuj_ensemble_historycznie.py
  python generuj_ensemble_historycznie.py --od 2026-03-25 --waga_xgb 0.60
  python generuj_ensemble_historycznie.py --nadpisz
"""

import argparse
import glob
import os
import sys
from datetime import datetime

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def merge_knn_xgb_to_ensemble(
    df_knn: pd.DataFrame,
    df_xgb: pd.DataFrame,
    w_xgb: float = 0.60,
) -> pd.DataFrame:
    """
    Scala dwa DataFrame'y (KNN i XGB) po kluczu Mecz+Godzina i oblicza ensemble.

    Ważona średnia:
        P_ens(wynik) = w_knn * P_knn(wynik) + w_xgb * P_xgb(wynik)
    """
    w_knn = round(1.0 - w_xgb, 4)

    # Normalizuj nazwy meczów do lowercase dla bezpiecznego merge'a
    df_knn = df_knn.copy()
    df_xgb = df_xgb.copy()
    df_knn['_mecz_key'] = df_knn['Mecz'].str.strip().str.lower()
    df_xgb['_mecz_key'] = df_xgb['Mecz'].str.strip().str.lower()

    # Przemianuj kolumny XGB żeby nie kolidowały
    df_xgb = df_xgb.rename(columns={
        '% Wygranej Gospodarza [1]': '_xgb_1',
        '% Wygranej Goscia [2]':     '_xgb_2',
        '% Remisu [X]':              '_xgb_X',
        'Typ_Modelu':                '_xgb_typ',
    })

    # Merge
    merged = pd.merge(
        df_knn,
        df_xgb[['_mecz_key', '_xgb_1', '_xgb_2', '_xgb_X', '_xgb_typ']],
        on='_mecz_key',
        how='inner',
    )

    if merged.empty:
        print("  [!] Brak wspolnych meczow po merge (rozne nazwy?). Proba fuzzy match...")
        # Fallback: merge po pozycji (zakładamy tę samą kolejność)
        n = min(len(df_knn), len(df_xgb))
        df_knn_trunc = df_knn.iloc[:n].copy().reset_index(drop=True)
        df_xgb_trunc = df_xgb.iloc[:n].copy().reset_index(drop=True)
        merged = df_knn_trunc.copy()
        merged['_xgb_1']   = df_xgb_trunc['_xgb_1'].values
        merged['_xgb_2']   = df_xgb_trunc['_xgb_2'].values
        merged['_xgb_X']   = df_xgb_trunc['_xgb_X'].values
        merged['_xgb_typ'] = df_xgb_trunc['_xgb_typ'].values

    rows = []
    for _, row in merged.iterrows():
        knn_1 = float(row.get('% Wygranej Gospodarza [1]', 0))
        knn_2 = float(row.get('% Wygranej Goscia [2]', 0))
        knn_X = float(row.get('% Remisu [X]', 0))
        xgb_1 = float(row.get('_xgb_1', 0))
        xgb_2 = float(row.get('_xgb_2', 0))
        xgb_X = float(row.get('_xgb_X', 0))

        ens_1 = round(w_knn * knn_1 + w_xgb * xgb_1, 1)
        ens_2 = round(w_knn * knn_2 + w_xgb * xgb_2, 1)
        ens_X = round(w_knn * knn_X + w_xgb * xgb_X, 1)

        # Typ ensemble
        szanse = {'1': ens_1, 'X': ens_X, '2': ens_2}
        typ_ens = max(szanse, key=szanse.get)

        # Typ KNN
        knn_szanse = {'1': knn_1, 'X': knn_X, '2': knn_2}
        typ_knn = max(knn_szanse, key=knn_szanse.get)

        # Typ XGB
        xgb_typ_str = str(row.get('_xgb_typ', typ_ens)).strip()
        typ_xgb = xgb_typ_str if xgb_typ_str in ('1', 'X', '2') else typ_ens

        # Consensus
        if typ_knn == typ_xgb:
            consensus = f"✅ OBA ZGODNE ({typ_knn})"
        else:
            consensus = f"⚠️ RÓŻNICA (KNN:{typ_knn} XGB:{typ_xgb})"

        rows.append({
            'Godzina':                   row.get('Godzina', ''),
            'Mecz':                      row.get('Mecz', ''),
            'Liga':                      row.get('Liga', ''),
            'Kurs [Faworyt]':            row.get('Kurs [Faworyt]', ''),
            '% Wygranej Gospodarza [1]': ens_1,
            '% Wygranej Goscia [2]':     ens_2,
            '% Remisu [X]':              ens_X,
            'Typ_Modelu':                typ_ens,
            'Consensus':                 consensus,
            'KNN_%1':                    round(knn_1, 1),
            'KNN_%X':                    round(knn_X, 1),
            'KNN_%2':                    round(knn_2, 1),
            'XGB_%1':                    round(xgb_1, 1),
            'XGB_%X':                    round(xgb_X, 1),
            'XGB_%2':                    round(xgb_2, 1),
        })

    df_ens = pd.DataFrame(rows)
    if not df_ens.empty:
        df_ens['_max'] = df_ens[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
        df_ens = df_ens.sort_values('_max', ascending=False).drop(columns=['_max'])

    return df_ens.reset_index(drop=True)


def generate_for_date(date_str: str, w_xgb: float, nadpisz: bool) -> bool:
    """Generuje plik ENSEMBLE dla jednej daty. Zwraca True jeśli wygenerował."""
    knn_path = os.path.join(BASE_DIR, f"DZISIEJSZE_TYPY_{date_str}.csv")
    xgb_path = os.path.join(BASE_DIR, f"DZISIEJSZE_TYPY_XGB_{date_str}.csv")
    out_path = os.path.join(BASE_DIR, f"DZISIEJSZE_TYPY_ENSEMBLE_{date_str}.csv")

    if not os.path.exists(knn_path):
        print(f"  [{date_str}] BRAK pliku KNN: {os.path.basename(knn_path)}")
        return False
    if not os.path.exists(xgb_path):
        print(f"  [{date_str}] BRAK pliku XGB: {os.path.basename(xgb_path)}")
        return False
    if os.path.exists(out_path) and not nadpisz:
        print(f"  [{date_str}] Plik ENSEMBLE już istnieje (użyj --nadpisz żeby nadpisać)")
        return False

    df_knn = pd.read_csv(knn_path, sep=';', encoding='utf-8-sig')
    df_xgb = pd.read_csv(xgb_path, sep=';', encoding='utf-8-sig')

    df_ens = merge_knn_xgb_to_ensemble(df_knn, df_xgb, w_xgb=w_xgb)

    if df_ens.empty:
        print(f"  [{date_str}] BLAD: Nie udalo sie wygenerowac ensemble (brak wspolnych meczow).")
        return False

    df_ens.to_csv(out_path, sep=';', index=False, encoding='utf-8-sig')
    n_zgodne = df_ens['Consensus'].str.startswith('[OK]').sum() + df_ens['Consensus'].str.contains('OBA ZGODNE').sum()
    print(f"  [{date_str}] OK {len(df_ens)} mecze | OBA ZGODNE: {n_zgodne} | zapisano: {os.path.basename(out_path)}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generuje historyczne pliki DZISIEJSZE_TYPY_ENSEMBLE_*.csv łącząc KNN i XGB."
    )
    parser.add_argument("--od", default="2026-03-25",
                        help="Data początkowa (włącznie), format YYYY-MM-DD. Domyślnie 2026-03-25.")
    parser.add_argument("--do", default="",
                        help="Data końcowa (włącznie), format YYYY-MM-DD. Domyślnie: wczoraj.")
    parser.add_argument("--waga_xgb", type=float, default=0.60,
                        help="Waga XGBoost [0.0-1.0], domyślnie 0.60.")
    parser.add_argument("--nadpisz", action="store_true",
                        help="Nadpisz istniejące pliki ENSEMBLE.")
    args = parser.parse_args()

    w_xgb = max(0.0, min(1.0, args.waga_xgb))
    w_knn = round(1.0 - w_xgb, 2)

    # Wyznacz zakres dat
    date_od = datetime.strptime(args.od, "%Y-%m-%d").date()
    if args.do:
        date_do = datetime.strptime(args.do, "%Y-%m-%d").date()
    else:
        from datetime import date, timedelta
        date_do = date.today() - timedelta(days=1)  # do wczoraj

    print(f"\n{'='*65}")
    print(f"  GENERATOR HISTORYCZNYCH TYPÓW ENSEMBLE")
    print(f"  Zakres: {date_od} -> {date_do}")
    print(f"  Wagi: KNN={w_knn*100:.0f}% / XGB={w_xgb*100:.0f}%")
    print(f"{'='*65}\n")

    # Zbierz wszystkie daty z plików KNN (jako punkt odniesienia)
    knn_files = sorted(glob.glob(os.path.join(BASE_DIR, "DZISIEJSZE_TYPY_2026-*.csv")))
    all_knn_dates = []
    for f in knn_files:
        fname = os.path.basename(f)
        date_part = fname.replace("DZISIEJSZE_TYPY_", "").replace(".csv", "")
        try:
            d = datetime.strptime(date_part, "%Y-%m-%d").date()
            if date_od <= d <= date_do:
                all_knn_dates.append(date_part)
        except ValueError:
            pass

    if not all_knn_dates:
        print("Nie znaleziono plików KNN w podanym zakresie dat.")
        return

    wygenerowane = 0
    for date_str in all_knn_dates:
        if generate_for_date(date_str, w_xgb=w_xgb, nadpisz=args.nadpisz):
            wygenerowane += 1

    print(f"\n{'='*65}")
    print(f"  GOTOWE — Wygenerowano {wygenerowane} plikow ENSEMBLE.")
    print(f"  Uruchom teraz walidator:")
    print(f"  python walidator_typow.py")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
