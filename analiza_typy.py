# -*- coding: utf-8 -*-
import pandas as pd, numpy as np, glob, os, sys

# Wymuszenie UTF-8 w konsoli Windows
sys.stdout.reconfigure(encoding='utf-8')

base_dir = r'C:\Users\admin\Desktop\PRACA INZYNIERSKA\KOD SCRAPER'

def load_xgb(files):
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
            date_str = os.path.basename(f).replace('ZWALIDOWANE_TYPY_XGB_','').replace('.csv','').strip()
            df['Data_pliku'] = date_str
            dfs.append(df)
        except:
            pass
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def load_knn(files):
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
            date_str = os.path.basename(f).replace('ZWALIDOWANE_TYPY_','').replace('.csv','').strip()
            df['Data_pliku'] = date_str
            dfs.append(df)
        except:
            pass
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

xgb_files = sorted(glob.glob(os.path.join(base_dir, 'ZWALIDOWANE_TYPY_XGB_2026-*.csv')))
knn_files = sorted(glob.glob(os.path.join(base_dir, 'ZWALIDOWANE_TYPY_2026-*.csv')))
xgb = load_xgb(xgb_files)
knn = load_knn(knn_files)

def get_max(row):
    p1 = pd.to_numeric(row.get('% Wygranej Gospodarza [1]',0), errors='coerce') or 0
    p2 = pd.to_numeric(row.get('% Wygranej Goscia [2]',0), errors='coerce') or 0
    pX = pd.to_numeric(row.get('% Remisu [X]',0), errors='coerce') or 0
    return max(p1, p2, pX)

def exk(s):
    try:
        return float(str(s).split(' ')[0])
    except:
        return None

for label, data in [('XGBoost', xgb), ('KNN', knn)]:
    data['MAX_Szansa'] = data.apply(get_max, axis=1)
    data['Kurs_val'] = data['Kurs [Faworyt]'].apply(exk)
    dv = data[data['Status'].isin(['WYGRANA','PRZEGRANA'])].copy()
    dv['Zysk'] = pd.to_numeric(dv['Zysk/Strata (Flat 100)'], errors='coerce').fillna(0)

    print(f"\n{'='*55}")
    print(f"  MODEL: {label}")
    print(f"{'='*55}")
    w = (dv['Status']=='WYGRANA').sum()
    p = (dv['Status']=='PRZEGRANA').sum()
    print(f"Ogolnie: {len(dv)} | WR: {w/(w+p)*100:.1f}% | ROI: {dv['Zysk'].sum():.0f} zl")

    print("\n--- Skutecznosc wg progu ---")
    for prog in [75,80,82,85,88,90,93]:
        sub = dv[dv['MAX_Szansa']>=prog]
        if len(sub)<2: continue
        sw = (sub['Status']=='WYGRANA').sum()
        sp = (sub['Status']=='PRZEGRANA').sum()
        roi_p = sub['Zysk'].sum()
        print(f"  {prog}%+: {len(sub):3d} mecz | WR: {sw/(sw+sp)*100:.1f}% | ROI: {roi_p:+.0f}")

    sub80 = dv[dv['MAX_Szansa']>=80]
    print(f"\n--- Segmentacja kursu (80%+): {len(sub80)} meczow ---")
    for kmin,kmax,lbl in [(1.0,1.10,'1.01-1.10'),(1.10,1.20,'1.10-1.20'),(1.20,1.30,'1.20-1.30'),(1.30,1.50,'1.30-1.50'),(1.50,99,'1.50+')]:
        seg = sub80[(sub80['Kurs_val']>=kmin) & (sub80['Kurs_val']<kmax)]
        if len(seg)<2: continue
        sw = (seg['Status']=='WYGRANA').sum()
        sp = (seg['Status']=='PRZEGRANA').sum()
        print(f"  Kurs {lbl}: {len(seg):3d} mecz | WR: {sw/(sw+sp)*100:.1f}% | ROI: {seg['Zysk'].sum():+.0f}")

    sub80_p = sub80[sub80['Status']=='PRZEGRANA']
    print(f"\n--- Przegrane (80%+): {len(sub80_p)} meczow ---")
    if len(sub80_p) > 0:
        print(f"  Typy: {sub80_p['Wynik_Rzeczywisty'].value_counts().to_dict()}")
        print(f"  Avg pewnosc: {sub80_p['MAX_Szansa'].mean():.1f}%")
        print(f"  Avg kurs: {sub80_p['Kurs_val'].mean():.2f}")
        pct_remis = (sub80_p['Wynik_Rzeczywisty']=='X').sum()/len(sub80_p)*100
        print(f"  Procent REMIS: {pct_remis:.0f}%")

    print(f"\n--- LISTA PRZEGRANYCH MECZOW (80%+) ---")
    for _,r in sub80_p.iterrows():
        mecz = str(r['Mecz'])[:38]
        print(f"  {r['Data_pliku']} | {mecz} | K:{r['Kurs_val']} | {r['MAX_Szansa']:.0f}% | Wynik:{r['Wynik_Rzeczywisty']} (typ:{r['Typ_Modelu']})")

    print(f"\n--- Wyniki dzien po dniu (80%+) ---")
    days = sub80.groupby('Data_pliku').agg(
        total=('Status','count'),
        wins=('Status', lambda x: (x=='WYGRANA').sum()),
        roi=('Zysk','sum')
    ).reset_index()
    days['wr'] = days['wins']/days['total']*100
    for _,r in days.iterrows():
        stat = 'ZYSK' if r['roi'] >= 0 else 'STRATA'
        print(f"  {r['Data_pliku']}: {int(r['total'])} mecz | WR: {r['wr']:.0f}% | ROI: {r['roi']:+.0f} ({stat})")
