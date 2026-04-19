# -*- coding: utf-8 -*-
"""
Automatyczny Typer (XGBOOST EDITION)
Dodatkowe narzedzie opierajace sie na docelowym i najnowszym silniku XGBoost zamiast KNN.
Pozwala na codzienne typowanie nadchodzących meczow z wieksza o kilka % celnascia.

ULEPSZENIE #1 — Kalibracja Prawdopodobieństw (CalibratedClassifierCV):
  Surowy XGBoost zawyża pewność własnych predykcji (np. podaje 95% gdy realna
  skuteczność wynosi 78%). CalibratedClassifierCV metodą 'isotonic' mapuje
  wyjściowe prawdopodobieństwa modelu na realne historyczne rozkłady wyników,
  dzięki czemu "85%" w pliku CSV jest naprawdę bliskie 85% trafień.
"""

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.calibration import CalibratedClassifierCV  # ULEPSZENIE #1

# Upewniamy się, że XGBoost jest zaimportowany w bloku głównym.
try:
    from xgboost import XGBClassifier
except ImportError:
    print("Zainstaluj XGBoost: pip install xgboost")
    sys.exit(1)

# Importy scrapera starych narzedzi (by nie duplikowac logiki przegladarki Chrome / FCTables)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from automatyczny_typer import scrape_unplayed_date 
from silnik_predykcji import load_and_prepare_data

def train_xgb_submodel(df, faworyt):
    """
    Trenuje skalibrowany silnik XGBoost dla danego układu faworyta.
    
    ULEPSZENIE #1 — Kalibracja:
    Zamiast zwracać surowy XGBoost, owijamy go w CalibratedClassifierCV
    metodą 'isotonic'. Kalibracja działa przez cross-validation (cv=5):
    dane dzielone na 5 części → model uczy się na 4, kalibruje na 1.
    Efekt: prawdopodobieństwa wyjściowe są skalibrowane do realnych rozkładów.
    """
    df_faw = df[df['Faworyt'] == faworyt].copy()
    if df_faw.empty:
        return None, None, None
        
    X = df_faw[['Kurs', 'TFI', 'TFI HA']].values
    y = df_faw['Rezultat'].astype(str).values
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    # ULEPSZENIE #1: Kalibracja prawdopodobieństw
    # cv=5 = 5-krotna walidacja krzyżowa podczas kalibracji
    # method='isotonic' = dokładniejsza kalibracja (wymaga min ~1000 próbek, mamy 140k+)
    xgb_base = XGBClassifier(eval_metric='mlogloss', random_state=42, n_jobs=-1)
    xgb_cal = CalibratedClassifierCV(xgb_base, method='isotonic', cv=5)
    xgb_cal.fit(X_scaled, y_encoded)
    
    return xgb_cal, scaler, le


def main():
    parser = argparse.ArgumentParser(description="Automatyczny Typowacz spotkań (Eksperymentalny XGBoost)")
    parser.add_argument("--data", default=datetime.now().strftime("%Y-%m-%d"), help="Data dzisiejsza lub zbliżająca się do predykcji xgboost (np. 2026-03-26).")
    
    args = parser.parse_args()
    
    # 1. Zescrapuj nierozegrane spotkania
    try:
        from fctables_scraper import setup_driver
    except Exception as e:
        print(f"Blad ladowania drivera: {e}")
        return
        
    print(f"\nUruchamiam silnik Chrome... Sprawdzam zbliżające się mecze (Zasilane przez XGBoost) dla daty: {args.data}...")
    driver = setup_driver(headless=True)
    matches_to_analyze = scrape_unplayed_date(driver, args.data)
    driver.quit()
    
    if not matches_to_analyze:
        print("Brak zaplanowanych spotkan do odczytu / wszystkie zostaly juz rozegrane.")
        return
        
    # 2. Ladowanie bazy do treningu
    print("\nŁadowanie całej bazy i trenowanie dwóch nowoczesnych silników XGBoost w tle... (zajmie ułamek sekundy)")
    df_history = load_and_prepare_data()
    
    # XGBoost trenujemy na dwoch roznych rynkach (faworyzowany Gospodarz, ew. Gosc)
    xgb_1, scaler_1, le_1 = train_xgb_submodel(df_history, 1)
    xgb_2, scaler_2, le_2 = train_xgb_submodel(df_history, 2)
    
    # 3. Przepuszczamy nowe spotkania przez model
    results = []
    print(f"Sztuczna Inteligencja XGBoost ocenia prawdopodobieństwa dla {len(matches_to_analyze)} zaplanowanych meczów...")
    
    for m in matches_to_analyze:
        faw = m['Faworyt']
        
        xgb_model = xgb_1 if faw == 1 else xgb_2
        scaler = scaler_1 if faw == 1 else scaler_2
        le = le_1 if faw == 1 else le_2
        
        if not xgb_model:
            continue
            
        X_val = np.array([[m['Kurs'], m['TFI'], m['TFI_HA']]])
        X_val_scaled = scaler.transform(X_val)
        
        probas = xgb_model.predict_proba(X_val_scaled)[0]
        classes = le.classes_
        
        szansa_1, szansa_X, szansa_2 = 0.0, 0.0, 0.0
        
        for i, c in enumerate(classes):
            if c == '1': szansa_1 = probas[i] * 100
            elif c == 'X': szansa_X = probas[i] * 100
            elif c == '2': szansa_2 = probas[i] * 100
            
        results.append({
            "Godzina": m['Godzina'],
            "Mecz": m['Mecz'],
            "Liga": m['Liga'],
            "Kurs [Faworyt]": f"{m['Kurs']} ({m['Faworyt']})",
            "% Wygranej Gospodarza [1]": round(szansa_1, 1),
            "% Wygranej Goscia [2]": round(szansa_2, 1),
            "% Remisu [X]": round(szansa_X, 1),
            "Typ_Modelu": "1" if szansa_1 > szansa_2 and szansa_1 > szansa_X else ("2" if szansa_2 > szansa_1 and szansa_2 > szansa_X else "X")
        })

    # Sortowanie predykcji XGBoosta
    df_results = pd.DataFrame(results)
    df_results['Max_Szansa'] = df_results[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
    df_results = df_results.sort_values(by="Max_Szansa", ascending=False).drop(columns=['Max_Szansa'])
    
    # 4. Zapis do nowego pliku
    file_name = f"DZISIEJSZE_TYPY_XGB_{args.data}.csv"
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
    df_results.to_csv(save_path, sep=';', index=False, encoding='utf-8-sig')
    
    print("\n" + "="*60)
    print(f"SUKCES - Zapisano wytypowane mecze w technologii ML XGBoost do pliku:")
    print(f"--> {file_name}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
