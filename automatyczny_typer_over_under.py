# -*- coding: utf-8 -*-
"""
Automatyczny Typer Over/Under (XGBoost)
Scrape nadchodzących meczów + predykcja rynków bramkowych:
  - Over 1.5 (padną >= 2 gole)
  - Over 2.5 (padną >= 3 gole)
  - BTTS     (obie drużyny strzelą)

Wynik zapisywany do: DZISIEJSZE_TYPY_OU_YYYY-MM-DD.csv
"""

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from automatyczny_typer import scrape_unplayed_date      # reużywa scrapera
from silnik_over_under import (                           # nowy silnik O/U
    load_and_prepare_data_ou,
    train_ou_model,
    predict_ou,
)


def main():
    parser = argparse.ArgumentParser(description='Automatyczny Typer Over/Under (XGBoost)')
    parser.add_argument(
        '--data',
        default=datetime.now().strftime('%Y-%m-%d'),
        help='Data dzisiejsza lub docelowa (np. 2026-04-14)'
    )
    args = parser.parse_args()

    # ── 1. Scrapuj nierozegrane mecze ──────────────────────────────────────
    try:
        from fctables_scraper import setup_driver
    except Exception as e:
        print(f'Błąd ładowania drivera: {e}')
        return

    print(f'\nUruchamiam Chrome — pobieranie meczów na: {args.data} (Over/Under)...')
    driver = setup_driver(headless=True)
    matches = scrape_unplayed_date(driver, args.data)
    driver.quit()

    if not matches:
        print('Brak nierozegranych meczów do analizy O/U.')
        return

    # ── 2. Trenowanie modeli ────────────────────────────────────────────────
    print('\nŁadowanie bazy i trenowanie modeli Over/Under... (może chwilę potrwać)')
    df_history = load_and_prepare_data_ou()

    models = {}
    base_rates = {}
    for market in ('over_15', 'over_25', 'btts'):
        print(f'  Trenowanie modelu: {market.upper()}...')
        model, scaler, base_rate = train_ou_model(df_history, market=market)
        models[market] = (model, scaler)
        base_rates[market] = base_rate
    print('Modele gotowe!\n')

    # ── 3. Predykcja dla każdego meczu ─────────────────────────────────────
    results = []
    print(f'Oceniam {len(matches)} meczów pod kątem Over/Under...')

    for m in matches:
        kurs   = m['Kurs']
        tfi    = m['TFI']
        tfi_ha = m['TFI_HA']

        probs = {}
        for market, (model, scaler) in models.items():
            probs[market] = predict_ou(model, scaler, kurs, tfi, tfi_ha)

        # Sugestia typera — najwyższe prawdopodobieństwo wśród rynków > 60%
        sugestia_parts = []
        if probs['over_15'] >= 60:
            sugestia_parts.append(f"Over 1.5 ({probs['over_15']:.0f}%)")
        if probs['over_25'] >= 60:
            sugestia_parts.append(f"Over 2.5 ({probs['over_25']:.0f}%)")
        if probs['btts'] >= 60:
            sugestia_parts.append(f"BTTS ({probs['btts']:.0f}%)")
        sugestia = ' | '.join(sugestia_parts) if sugestia_parts else '—'

        results.append({
            'Godzina':          m['Godzina'],
            'Mecz':             m['Mecz'],
            'Liga':             m['Liga'],
            'Kurs [Faworyt]':   f"{kurs} ({m['Faworyt']})",
            '% Over 1.5':       probs['over_15'],
            '% Over 2.5':       probs['over_25'],
            '% BTTS':           probs['btts'],
            'Sugestia_OU':      sugestia,
        })

    # ── 4. Sortowanie i zapis ───────────────────────────────────────────────
    df_out = pd.DataFrame(results)
    # Sortuj po Over 2.5 (najciekawszy rynek bukmacherski)
    df_out = df_out.sort_values(by='% Over 2.5', ascending=False).reset_index(drop=True)

    file_name = f'DZISIEJSZE_TYPY_OU_{args.data}.csv'
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
    df_out.to_csv(save_path, sep=';', index=False, encoding='utf-8-sig')

    print('\n' + '=' * 60)
    print(f'Statystyki historyczne bazy (baseline):')
    for market, rate in base_rates.items():
        print(f'  {market.upper()}: {rate:.1f}% meczów w historii')
    print('=' * 60)
    print(f'SUKCES — Typy Over/Under zapisano do: {file_name}')
    print('=' * 60 + '\n')


if __name__ == '__main__':
    main()
