# -*- coding: utf-8 -*-
"""
ULEPSZENIE #2 — Automatyczny Optymalizator Progu Wejścia
=========================================================
Analizuje wszystkie zwalidowane historyczne pliki CSV (ZWALIDOWANE_TYPY_*) 
i dla każdego możliwego progu pewności (70%-97%) oblicza:
  - liczbę meczów
  - Win Rate (%)
  - łączny ROI (zysk/strata)

Na tej podstawie wychwytuje OPTYMALNY PRÓG — ten który historycznie dawał
najwyższy zysk łączny. Uruchamiaj raz w tygodniu by dostosować strategię.

Użycie:
  python optymalizator_progu.py              (analizuje oba modele)
  python optymalizator_progu.py --model XGB  (tylko XGBoost)
  python optymalizator_progu.py --model KNN  (tylko KNN)
  python optymalizator_progu.py --model ENS  (tylko Ensemble)
"""

import argparse
import glob
import os
import sys

import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_validated_files(pattern: str, exclude: list = None) -> pd.DataFrame:
    """Ładuje i łączy wszystkie pasujące pliki zwalidowane."""
    files = sorted(glob.glob(os.path.join(BASE_DIR, pattern)))
    if exclude:
        files = [f for f in files if not any(ex in os.path.basename(f) for ex in exclude)]
    
    if not files:
        return pd.DataFrame()
    
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
            date_str = os.path.basename(f)
            for prefix in ['ZWALIDOWANE_TYPY_XGB_', 'ZWALIDOWANE_TYPY_ENSEMBLE_', 'ZWALIDOWANE_TYPY_']:
                date_str = date_str.replace(prefix, '')
            date_str = date_str.replace('.csv', '').strip()
            df['Data_pliku'] = date_str
            dfs.append(df)
        except Exception:
            pass
    
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def get_max_szansa(df: pd.DataFrame) -> pd.Series:
    """Wyciąga MAX_Szansa — z kolumny lub na bieżąco z %."""
    if 'MAX_Szansa' in df.columns:
        return pd.to_numeric(df['MAX_Szansa'], errors='coerce')
    
    cols = ['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']
    existing = [c for c in cols if c in df.columns]
    if existing:
        return df[existing].apply(pd.to_numeric, errors='coerce').max(axis=1)
    
    return pd.Series([np.nan] * len(df))


def analyze_model(label: str, df: pd.DataFrame) -> int:
    """
    Analizuje jeden model i wypisuje tabelę progów.
    Zwraca optymalny próg (maks. ROI).
    """
    df = df[df['Status'].isin(['WYGRANA', 'PRZEGRANA'])].copy()
    if df.empty:
        print(f"\n[{label}] Brak zwalidowanych danych.\n")
        return -1
    
    df['_MAX'] = get_max_szansa(df)
    df['_Zysk'] = pd.to_numeric(df['Zysk/Strata (Flat 100)'], errors='coerce').fillna(0)
    
    n_pliki = df['Data_pliku'].nunique() if 'Data_pliku' in df.columns else '?'
    d_min = df['Data_pliku'].min() if 'Data_pliku' in df.columns else '?'
    d_max = df['Data_pliku'].max() if 'Data_pliku' in df.columns else '?'
    
    print(f"\n{'='*65}")
    print(f"  OPTYMALIZATOR PROGU — Model: {label}")
    print(f"  Dane z {n_pliki} plików zwalidowanych  ({d_min} → {d_max})")
    print(f"{'='*65}")
    print(f"  {'Próg':>4} | {'Mecze':>6} | {'Win%':>6} | {'ROI':>10} | Ocena")
    print(f"  {'-'*54}")
    
    best_roi = -999999
    best_prog = 70
    
    for prog in range(70, 98):
        sub = df[df['_MAX'] >= prog]
        if len(sub) < 5:
            break
        
        w = (sub['Status'] == 'WYGRANA').sum()
        p = (sub['Status'] == 'PRZEGRANA').sum()
        total = w + p
        if total == 0:
            continue
        
        wr = w / total * 100
        roi = sub['_Zysk'].sum()
        
        # Ocena wizualna
        if roi > best_roi:
            best_roi = roi
            best_prog = prog
        
        if roi > 0:
            arrows = '▲' * min(int(roi / 500) + 1, 5)
        else:
            arrows = '▼'
        
        star = ' ★' if prog == best_prog else ''
        print(f"  {prog:>3}%+ | {len(sub):>6} | {wr:>5.1f}% | {roi:>+9.0f}zł | {arrows}{star}")
    
    print(f"  {'-'*54}")
    print(f"\n  ★  OPTYMALNY PRÓG: {best_prog}%  →  Maks. ROI: {best_roi:+.0f} zł")
    print(f"  Rekomendacja: Obstaw mecze z pewnością ≥ {best_prog}%\n")
    
    return best_prog


def main():
    parser = argparse.ArgumentParser(description="Optymalizator Progu Wejścia — analiza historycznego ROI")
    parser.add_argument(
        "--model",
        choices=["XGB", "KNN", "ENS", "ALL"],
        default="ALL",
        help="Model do analizy: XGB, KNN, ENS (Ensemble) lub ALL (domyślnie)"
    )
    args = parser.parse_args()
    
    wyniki = {}
    
    if args.model in ("XGB", "ALL"):
        df_xgb = load_validated_files("ZWALIDOWANE_TYPY_XGB_2026-*.csv", exclude=["HISTORYCZNIE"])
        if not df_xgb.empty:
            wyniki['XGBoost'] = analyze_model("XGBoost (skalibrowany)", df_xgb)
    
    if args.model in ("KNN", "ALL"):
        df_knn = load_validated_files("ZWALIDOWANE_TYPY_2026-*.csv", exclude=["XGB", "ENSEMBLE"])
        if not df_knn.empty:
            wyniki['KNN'] = analyze_model("KNN", df_knn)
    
    if args.model in ("ENS", "ALL"):
        df_ens = load_validated_files("ZWALIDOWANE_TYPY_ENSEMBLE_2026-*.csv")
        if not df_ens.empty:
            wyniki['Ensemble'] = analyze_model("Ensemble KNN+XGB", df_ens)
        else:
            print("\n[Ensemble] Brak plików zwalidowanych — uruchom najpierw automatyczny_typer_ensemble.py\n")
    
    if len(wyniki) > 1:
        print(f"\n{'='*65}")
        print("  PODSUMOWANIE OPTYMALNYCH PROGÓW")
        print(f"{'='*65}")
        for model_name, prog in wyniki.items():
            if prog > 0:
                print(f"  {model_name:30s}: ≥ {prog}%")
        print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
