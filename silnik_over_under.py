# -*- coding: utf-8 -*-
"""
Silnik Predykcji Over/Under Goli (XGBoost)
Trenuje modele binarne dla rynków:
  - Over 1.5 (padną >= 2 gole)
  - Over 2.5 (padną >= 3 gole)
  - BTTS     (obie drużyny strzelą >= 1 gol)

Używa tych samych cech co główny silnik (Kurs, TFI, TFI HA) i tej samej bazy
fctables_data.csv, ale jako etykietę przyjmuje sumę goli zamiast 1/X/2.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV

warnings.filterwarnings('ignore')

try:
    from xgboost import XGBClassifier
except ImportError:
    print("Zainstaluj XGBoost: pip install xgboost")
    sys.exit(1)

# Ścieżka do tej samej bazy co silnik 1X2
CSV_FILE = r"C:\Users\admin\Desktop\PRACA INZYNIERSKA\KOD SCRAPER\fctables_data.csv"

# ──────────────────────────────────────────────────────────────────────────────
# Ładowanie i przygotowanie danych
# ──────────────────────────────────────────────────────────────────────────────

def load_and_prepare_data_ou():
    """
    Ładuje bazę meczów i wylicza kolumny pomocnicze:
      - Total_Goli:  suma goli w meczu
      - Over_05:     int(Total_Goli >= 1)
      - Over_15:     int(Total_Goli >= 2)
      - Over_25:     int(Total_Goli >= 3)
      - BTTS:        int(Gole_H >= 1 AND Gole_A >= 1)
    Zwraca DataFrame gotowy do trenowania.
    """
    print("Ładowanie bazy O/U z fctables_data.csv...")
    df = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8')

    # Zamiana przecinków na kropki dla kolumn numerycznych
    for col in ['Kurs', 'TFI', 'TFI HA']:
        df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Konwersja goli
    df['GOLE_Gospodarzy'] = pd.to_numeric(df['GOLE_Gospodarzy'], errors='coerce')
    df['GOLE_Gosci']      = pd.to_numeric(df['GOLE_Gosci'],      errors='coerce')

    # Odrzuć rekordy bez kursów lub bez wyników
    df = df.dropna(subset=['Kurs', 'TFI', 'TFI HA', 'GOLE_Gospodarzy', 'GOLE_Gosci'])

    # Skonstruuj zmienne docelowe
    df['Total_Goli'] = df['GOLE_Gospodarzy'] + df['GOLE_Gosci']
    df['Over_05']    = (df['Total_Goli'] >= 1).astype(int)
    df['Over_15']    = (df['Total_Goli'] >= 2).astype(int)
    df['Over_25']    = (df['Total_Goli'] >= 3).astype(int)
    df['BTTS']       = ((df['GOLE_Gospodarzy'] >= 1) & (df['GOLE_Gosci'] >= 1)).astype(int)

    print(f"Baza O/U załadowana — {len(df):,} meczów z wynikami gotowych do treningu.")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Trenowanie modelu
# ──────────────────────────────────────────────────────────────────────────────

MARKET_TARGETS = {
    'over_05': 'Over_05',
    'over_15': 'Over_15',
    'over_25': 'Over_25',
    'btts':    'BTTS',
}

FEATURES = ['Kurs', 'TFI', 'TFI HA']


def train_ou_model(df: pd.DataFrame, market: str = 'over_25'):
    """
    Trenuje skalibrowany model XGBoost dla wybranego rynku O/U.

    Parametry
    ---------
    df     : DataFrame z load_and_prepare_data_ou()
    market : klucz z MARKET_TARGETS ('over_05', 'over_15', 'over_25', 'btts')

    Zwraca
    ------
    model   : CalibratedClassifierCV (skalibrowany XGBoost)
    scaler  : StandardScaler dopasowany do danych treningowych
    base_rate: float — historyczna częstość zdarzenia (% Over w bazie)
    """
    if market not in MARKET_TARGETS:
        raise ValueError(f"Nieznany rynek: {market}. Dostępne: {list(MARKET_TARGETS.keys())}")

    target_col = MARKET_TARGETS[market]
    df_clean = df.dropna(subset=FEATURES + [target_col]).copy()

    X = df_clean[FEATURES].values
    y = df_clean[target_col].values

    scaler  = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    base_rate = float(y.mean() * 100)

    xgb_base = XGBClassifier(
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1,
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
    )
    # Kalibracja izotoniczna — bardziej wiarygodne prawdopodobieństwa
    model = CalibratedClassifierCV(xgb_base, method='isotonic', cv=3)
    model.fit(X_scaled, y)

    return model, scaler, base_rate


# ──────────────────────────────────────────────────────────────────────────────
# Predykcja dla jednego meczu
# ──────────────────────────────────────────────────────────────────────────────

def predict_ou(model, scaler, kurs: float, tfi: float, tfi_ha: float) -> float:
    """
    Zwraca prawdopodobieństwo (%) zdarzenia Over dla podanych cech meczu.
    """
    X = np.array([[kurs, tfi, tfi_ha]])
    X_scaled = scaler.transform(X)
    proba = model.predict_proba(X_scaled)[0]
    # klasa 1 = Over zachodzi
    idx_over = list(model.classes_).index(1) if hasattr(model, 'classes_') else 1
    return round(float(proba[idx_over]) * 100, 1)


# ──────────────────────────────────────────────────────────────────────────────
# Szybki test z linii poleceń
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Silnik Over/Under — pojedyncza predykcja')
    parser.add_argument('--kurs',   type=float, required=True, help='Kurs na faworyta (np. 1.85)')
    parser.add_argument('--tfi',    type=float, required=True, help='Indeks TFI (np. 3.40)')
    parser.add_argument('--tfiha',  type=float, required=True, help='Indeks TFI HA (np. -1.05)')
    parser.add_argument('--rynek',  type=str,   default='over_25',
                        choices=list(MARKET_TARGETS.keys()),
                        help='Rynek do predykcji (domyślnie: over_25)')
    args = parser.parse_args()

    df = load_and_prepare_data_ou()
    model, scaler, base_rate = train_ou_model(df, market=args.rynek)

    prob = predict_ou(model, scaler, args.kurs, args.tfi, args.tfiha)
    label = args.rynek.replace('_', ' ').upper()

    print(f"\n{'='*50}")
    print(f"  Predykcja O/U — {label}")
    print(f"  Kurs={args.kurs}  TFI={args.tfi}  TFI HA={args.tfiha}")
    print(f"{'='*50}")
    print(f"  Prawdopodobieństwo {label}: {prob:.1f}%")
    print(f"  Bazowa częstość w historii:  {base_rate:.1f}%")
    print(f"{'='*50}\n")
