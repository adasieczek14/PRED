# -*- coding: utf-8 -*-
"""
ULEPSZENIE #4 — Automatyczny Typer ENSEMBLE (KNN + XGBoost)
============================================================
Łączy dwa modele predykcyjne w jeden silniejszy sygnał:
  - KNN   (waga 40%) — szuka 25 historycznie podobnych meczów
  - XGBoost skalibrowany (waga 60%) — drzewa decyzyjne gradient boosting

Efekt końcowy dla każdego meczu:
  - Ważona średnia prawdopodobieństw obu modeli (40/60)
  - Kolumna Consensus: ✅ OBA ZGODNE lub ⚠️ RÓŻNICA MODELI
  - Mecze gdzie oba modele wskazują ten sam wynik → silniejszy sygnał

Kolumna Consensus pozwala filtrować tylko najbardziej pewne typy:
typy gdzie OBA modele są przekonane do tego samego wyniku.

Użycie:
  python automatyczny_typer_ensemble.py
  python automatyczny_typer_ensemble.py --data 2026-04-15
  python automatyczny_typer_ensemble.py --data 2026-04-15 --waga_xgb 0.7
"""

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.calibration import CalibratedClassifierCV

try:
    from xgboost import XGBClassifier
except ImportError:
    print("Zainstaluj XGBoost: pip install xgboost")
    sys.exit(1)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from automatyczny_typer import scrape_unplayed_date
from silnik_predykcji import load_and_prepare_data, find_similar_matches


# ─────────────────────────────────────────────
# TRENING PODMODELI
# ─────────────────────────────────────────────

def train_xgb_calibrated(df, faworyt):
    """
    Trenuje skalibrowany XGBoost (takie same ulepszenie co w automatyczny_typer_xgb.py).
    Zwraca (model_skalibrowany, scaler, label_encoder).
    """
    df_faw = df[df['Faworyt'] == faworyt].copy()
    if df_faw.empty or len(df_faw) < 30:
        return None, None, None
    
    X = df_faw[['Kurs', 'TFI', 'TFI HA']].values
    y = df_faw['Rezultat'].astype(str).values
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    xgb_base = XGBClassifier(eval_metric='mlogloss', random_state=42, n_jobs=-1)
    xgb_cal  = CalibratedClassifierCV(xgb_base, method='isotonic', cv=5)
    xgb_cal.fit(X_scaled, y_encoded)
    
    return xgb_cal, scaler, le


def predict_knn(df_history, mecz_data: dict, k: int = 25) -> dict:
    """
    Uruchamia KNN dla jednego meczu. Zwraca słownik {szansa_1, szansa_X, szansa_2}.
    """
    return find_similar_matches(
        df=df_history,
        current_tfi=mecz_data['TFI'],
        current_tfi_ha=mecz_data['TFI_HA'],
        current_kurs=mecz_data['Kurs'],
        current_faworyt=mecz_data['Faworyt'],
        k_neighbors=k,
        quiet=True
    )


def predict_xgb(xgb_model, scaler, le, mecz_data: dict) -> dict:
    """
    Uruchamia skalibrowany XGBoost dla jednego meczu.
    Zwraca słownik {szansa_1, szansa_X, szansa_2}.
    """
    if xgb_model is None:
        return {'szansa_1': 0.0, 'szansa_X': 0.0, 'szansa_2': 0.0}
    
    X_val = np.array([[mecz_data['Kurs'], mecz_data['TFI'], mecz_data['TFI_HA']]])
    X_val_scaled = scaler.transform(X_val)
    probas = xgb_model.predict_proba(X_val_scaled)[0]
    
    result = {'szansa_1': 0.0, 'szansa_X': 0.0, 'szansa_2': 0.0}
    for i, cls in enumerate(le.classes_):
        if   cls == '1': result['szansa_1'] = probas[i] * 100
        elif cls == 'X': result['szansa_X'] = probas[i] * 100
        elif cls == '2': result['szansa_2'] = probas[i] * 100
    
    return result


# ─────────────────────────────────────────────
# LOGIKA ENSEMBLE
# ─────────────────────────────────────────────

def ensemble_predict(knn_pred: dict, xgb_pred: dict, w_knn: float, w_xgb: float) -> dict:
    """
    Łączy predykcje KNN i XGB przez ważoną średnią.
    
    Wzór: P_ens(wynik) = w_knn * P_knn(wynik) + w_xgb * P_xgb(wynik)
    
    Przykład (wagi 40/60):
      KNN:  1=79%, X=13%, 2=8%
      XGB:  1=84%, X=9%,  2=7%
      ENS:  1=0.4*79+0.6*84=82%, X=11%, 2=7%
    """
    ens_1 = w_knn * knn_pred['szansa_1'] + w_xgb * xgb_pred['szansa_1']
    ens_X = w_knn * knn_pred['szansa_X'] + w_xgb * xgb_pred['szansa_X']
    ens_2 = w_knn * knn_pred['szansa_2'] + w_xgb * xgb_pred['szansa_2']
    
    # Typ modelu na podstawie ensemble
    szanse = {'1': ens_1, 'X': ens_X, '2': ens_2}
    typ_ens = max(szanse, key=szanse.get)
    
    # Typ KNN i XGB osobno (dla kolumny Consensus)
    knn_szanse = {'1': knn_pred['szansa_1'], 'X': knn_pred['szansa_X'], '2': knn_pred['szansa_2']}
    xgb_szanse = {'1': xgb_pred['szansa_1'], 'X': xgb_pred['szansa_X'], '2': xgb_pred['szansa_2']}
    typ_knn = max(knn_szanse, key=knn_szanse.get)
    typ_xgb = max(xgb_szanse, key=xgb_szanse.get)
    
    if typ_knn == typ_xgb:
        consensus = f"✅ OBA ZGODNE ({typ_knn})"
    else:
        consensus = f"⚠️ RÓŻNICA (KNN:{typ_knn} XGB:{typ_xgb})"
    
    return {
        'szansa_1_ens':  round(ens_1, 1),
        'szansa_X_ens':  round(ens_X, 1),
        'szansa_2_ens':  round(ens_2, 1),
        'typ_ens':       typ_ens,
        'szansa_1_knn':  round(knn_pred['szansa_1'], 1),
        'szansa_X_knn':  round(knn_pred['szansa_X'], 1),
        'szansa_2_knn':  round(knn_pred['szansa_2'], 1),
        'szansa_1_xgb':  round(xgb_pred['szansa_1'], 1),
        'szansa_X_xgb':  round(xgb_pred['szansa_X'], 1),
        'szansa_2_xgb':  round(xgb_pred['szansa_2'], 1),
        'typ_knn':        typ_knn,
        'typ_xgb':        typ_xgb,
        'Consensus':      consensus,
    }


# ─────────────────────────────────────────────
# GŁÓWNA LOGIKA
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Automatyczny Typowacz Ensemble (KNN + XGBoost skalibrowany)")
    parser.add_argument("--data",      default=datetime.now().strftime("%Y-%m-%d"),
                        help="Data do predykcji (np. 2026-04-15). Domyślnie: dzisiaj.")
    parser.add_argument("--k",         type=int,   default=25,
                        help="Liczba sąsiadów KNN (domyślnie 25).")
    parser.add_argument("--waga_xgb",  type=float, default=0.60,
                        help="Waga XGBoost w ensemble [0.0-1.0] (domyślnie 0.60).")
    args = parser.parse_args()
    
    w_xgb = max(0.0, min(1.0, args.waga_xgb))
    w_knn  = round(1.0 - w_xgb, 2)
    
    print(f"\n{'='*65}")
    print(f"  ENSEMBLE TYPER: KNN({w_knn*100:.0f}%) + XGBoost_skalibrowany({w_xgb*100:.0f}%)")
    print(f"  Data predykcji: {args.data}")
    print(f"{'='*65}")
    
    # 1. Scraping nierozegranych meczów
    try:
        from fctables_scraper import setup_driver
    except Exception as e:
        print(f"Błąd ładowania drivera FCTables: {e}")
        return
    
    print("\nUruchamiam Chrome... Pobieram nierozegrane mecze...")
    driver = setup_driver(headless=True)
    matches_to_analyze = scrape_unplayed_date(driver, args.data)
    driver.quit()
    
    if not matches_to_analyze:
        print("Brak zaplanowanych meczów do analizy.")
        return
    
    # 2. Ładowanie bazy i trening
    print(f"\nŁadowanie bazy historycznej i trenowanie modeli (KNN+XGB)...")
    df_history = load_and_prepare_data()
    
    # Trenuj XGB osobno dla Faworyta=1 i Faworyta=2
    print("  ⚙️  Trenuję XGBoost (Faworyt=1)...")
    xgb_1, scaler_1, le_1 = train_xgb_calibrated(df_history, 1)
    print("  ⚙️  Trenuję XGBoost (Faworyt=2)...")
    xgb_2, scaler_2, le_2 = train_xgb_calibrated(df_history, 2)
    print("  ✅ Modele gotowe.\n")
    
    # 3. Przepuszczamy mecze przez ensemble
    results = []
    print(f"Ensemble analizuje {len(matches_to_analyze)} meczów...")
    
    for m in matches_to_analyze:
        faw = m['Faworyt']
        
        # KNN predykcja
        knn_pred = predict_knn(df_history, m, k=args.k)
        
        # XGB predykcja
        xgb_model  = xgb_1  if faw == 1 else xgb_2
        xgb_scaler = scaler_1 if faw == 1 else scaler_2
        xgb_le     = le_1   if faw == 1 else le_2
        xgb_pred   = predict_xgb(xgb_model, xgb_scaler, xgb_le, m)
        
        # Połącz przez ważoną średnią
        ens = ensemble_predict(knn_pred, xgb_pred, w_knn=w_knn, w_xgb=w_xgb)
        
        results.append({
            "Godzina":                    m['Godzina'],
            "Mecz":                       m['Mecz'],
            "Liga":                       m['Liga'],
            "Kurs [Faworyt]":             f"{m['Kurs']} ({m['Faworyt']})",
            "% Wygranej Gospodarza [1]":  ens['szansa_1_ens'],
            "% Wygranej Goscia [2]":      ens['szansa_2_ens'],
            "% Remisu [X]":               ens['szansa_X_ens'],
            "Typ_Modelu":                 ens['typ_ens'],
            "Consensus":                  ens['Consensus'],
            "KNN_%1":                     ens['szansa_1_knn'],
            "KNN_%X":                     ens['szansa_X_knn'],
            "KNN_%2":                     ens['szansa_2_knn'],
            "XGB_%1":                     ens['szansa_1_xgb'],
            "XGB_%X":                     ens['szansa_X_xgb'],
            "XGB_%2":                     ens['szansa_2_xgb'],
        })
    
    # 4. Sortowanie i zapis
    df_results = pd.DataFrame(results)
    df_results['_Max'] = df_results[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
    df_results = df_results.sort_values(by='_Max', ascending=False).drop(columns=['_Max'])
    
    file_name = f"DZISIEJSZE_TYPY_ENSEMBLE_{args.data}.csv"
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
    df_results.to_csv(save_path, sep=';', index=False, encoding='utf-8-sig')
    
    # Podsumowanie w konsoli
    zgodne = df_results['Consensus'].str.startswith('✅').sum()
    print(f"\n{'='*65}")
    print(f"  SUKCES — Plik ensemble zapisany: {file_name}")
    print(f"  Łącznie meczów: {len(df_results)}")
    print(f"  ✅ OBA MODELE ZGODNE:   {zgodne} meczów")
    print(f"  ⚠️  ROZBIEŻNOŚĆ MODELI: {len(df_results) - zgodne} meczów")
    print(f"  Wagi: KNN={w_knn*100:.0f}% / XGB={w_xgb*100:.0f}%")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
