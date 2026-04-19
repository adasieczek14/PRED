# -*- coding: utf-8 -*-
"""
Analiza skuteczności historycznej ensemble vs KNN vs XGB
"""
import pandas as pd
import glob
import os

base = os.path.dirname(os.path.abspath(__file__))

def analyze_thresholds(pattern, label):
    files = sorted(glob.glob(os.path.join(base, pattern)))
    # Filtruj pliki >= data startowa
    import re
    files = [f for f in files
             if (m := re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(f))) and m.group(1) >= '2026-03-25']
    all_rows = []
    for f in files:
        df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
        all_rows.append(df)
    if not all_rows:
        print(f"Brak plikow dla: {label}")
        return
    df_all = pd.concat(all_rows, ignore_index=True)
    df_valid = df_all[df_all['Status'].isin(['WYGRANA', 'PRZEGRANA'])].copy()
    
    df_valid['MaxProb'] = df_valid[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
    
    print(f"\n== {label} ==")
    print(f"{'Prog':>8} | {'Mecze':>6} | {'Trafione':>8} | {'Skut%':>6} | {'Profit':>10}")
    print('-' * 52)
    for prog in [50, 60, 65, 70, 75, 80, 85]:
        sub = df_valid[df_valid['MaxProb'] >= prog]
        if len(sub) == 0:
            continue
        w = (sub['Status'] == 'WYGRANA').sum()
        prof = sub['Zysk/Strata (Flat 100)'].sum()
        acc = w / len(sub) * 100
        print(f"{prog:>7}%+ | {len(sub):>6} | {w:>8} | {acc:>5.1f}% | {prof:>+10.0f}")

analyze_thresholds('ZWALIDOWANE_TYPY_2026-*.csv', 'KNN (od 2026-03-25)')
analyze_thresholds('ZWALIDOWANE_TYPY_XGB_2026-*.csv', 'XGBoost (od 2026-03-25)')
analyze_thresholds('ZWALIDOWANE_TYPY_ENSEMBLE_2026-*.csv', 'ENSEMBLE (od 2026-03-25)')

# Bonus: analiza ENSEMBLE po consensus
print("\n== ENSEMBLE - tylko OBA ZGODNE ==")
files = sorted(glob.glob(os.path.join(base, 'ZWALIDOWANE_TYPY_ENSEMBLE_2026-*.csv')))
files = [f for f in files if os.path.basename(f) >= 'ZWALIDOWANE_TYPY_ENSEMBLE_2026-03-25.csv']
all_rows = []
for f in files:
    df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
    all_rows.append(df)
if all_rows:
    df_all = pd.concat(all_rows, ignore_index=True)
    df_valid = df_all[df_all['Status'].isin(['WYGRANA', 'PRZEGRANA'])].copy()
    df_zgodne = df_valid[df_valid['Consensus'].str.contains('OBA ZGODNE', na=False)].copy()
    df_roznica = df_valid[~df_valid['Consensus'].str.contains('OBA ZGODNE', na=False)].copy()
    
    df_zgodne['MaxProb'] = df_zgodne[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
    df_roznica['MaxProb'] = df_roznica[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
    
    print(f"\n{'Prog':>8} | {'Mecze':>6} | {'Trafione':>8} | {'Skut%':>6} | {'Profit':>10}")
    print('-' * 52)
    for prog in [50, 60, 65, 70, 75, 80]:
        sub = df_zgodne[df_zgodne['MaxProb'] >= prog]
        if len(sub) == 0:
            continue
        w = (sub['Status'] == 'WYGRANA').sum()
        prof = sub['Zysk/Strata (Flat 100)'].sum()
        acc = w / len(sub) * 100
        print(f"{prog:>7}%+ | {len(sub):>6} | {w:>8} | {acc:>5.1f}% | {prof:>+10.0f}")
    
    print("\n== ENSEMBLE - tylko ROZNICA MODELI ==")
    print(f"{'Prog':>8} | {'Mecze':>6} | {'Trafione':>8} | {'Skut%':>6} | {'Profit':>10}")
    print('-' * 52)
    for prog in [50, 60, 65, 70, 75]:
        sub = df_roznica[df_roznica['MaxProb'] >= prog]
        if len(sub) == 0:
            continue
        w = (sub['Status'] == 'WYGRANA').sum()
        prof = sub['Zysk/Strata (Flat 100)'].sum()
        acc = w / len(sub) * 100
        print(f"{prog:>7}%+ | {len(sub):>6} | {w:>8} | {acc:>5.1f}% | {prof:>+10.0f}")

print()
