# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np

df = pd.read_csv(
    r'C:\Users\admin\Desktop\PRACA INZYNIERSKA\KOD SCRAPER\ZWALIDOWANE_TYPY_XGB_HISTORYCZNIE.csv',
    sep=';', encoding='utf-8-sig'
)
df = df[df['Status'].isin(['WYGRANA', 'PRZEGRANA'])]

def extract_kurs(s):
    try:
        return float(str(s).split(' ')[0])
    except:
        return None

df['Kurs_val'] = df['Kurs [Faworyt]'].apply(extract_kurs)

sub85 = df[df['MAX_Szansa'] >= 85]
print(f'Prog 85%+: {len(sub85)} meczow')
przegrane = sub85[sub85['Status'] == 'PRZEGRANA']
wygrane = sub85[sub85['Status'] == 'WYGRANA']
print(f'Sredni kurs WYGRANA: {wygrane["Kurs_val"].mean():.2f}')
print(f'Sredni kurs PRZEGRANA: {przegrane["Kurs_val"].mean():.2f}')
print(f'Mediana kursu WYGRANA: {wygrane["Kurs_val"].median():.2f}')
print(f'Mediana kursu PRZEGRANA: {przegrane["Kurs_val"].median():.2f}')
print()

print('=== SEGMENTACJA KURSU (85%+ mecze) ===')
for kmin, kmax, label in [
    (1.0, 1.10, '1.01-1.10'),
    (1.10, 1.20, '1.10-1.20'),
    (1.20, 1.30, '1.20-1.30'),
    (1.30, 1.50, '1.30-1.50'),
    (1.50, 99, '1.50+')
]:
    seg = sub85[(sub85['Kurs_val'] >= kmin) & (sub85['Kurs_val'] < kmax)]
    if len(seg) < 5:
        continue
    w = (seg['Status'] == 'WYGRANA').sum()
    p = (seg['Status'] == 'PRZEGRANA').sum()
    wr = w / (w + p) * 100
    roi = seg['Zysk/Strata (Flat 100)'].sum()
    avg_k = seg['Kurs_val'].mean()
    print(f'Kurs {label}: {len(seg)} meczow | WR: {wr:.1f}% | avg kurs: {avg_k:.2f} | ROI: {roi:.0f}')

print()
print('=== TOP LIGI - NAJWYZSZY ODSETEK PRZEGRAN (85%+) ===')
lg = sub85.groupby('Liga').agg(
    total=('Status', 'count'),
    wins=('Status', lambda x: (x == 'WYGRANA').sum()),
    losses=('Status', lambda x: (x == 'PRZEGRANA').sum()),
    roi=('Zysk/Strata (Flat 100)', 'sum')
).reset_index()
lg['wr'] = lg['wins'] / lg['total'] * 100
lg_min = lg[lg['total'] >= 5].sort_values('wr').head(15)
for _, r in lg_min.iterrows():
    print(f'{r["Liga"][:35]}: {r["total"]} meczow | WR: {r["wr"]:.0f}% | ROI: {r["roi"]:.0f}')

print()
print('=== TOP LIGI - NAJLEPSZY ROI (85%+) ===')
lg_best = lg[lg['total'] >= 5].sort_values('roi', ascending=False).head(15)
for _, r in lg_best.iterrows():
    print(f'{r["Liga"][:35]}: {r["total"]} meczow | WR: {r["wr"]:.0f}% | ROI: {r["roi"]:.0f}')

print()
print('=== ANALIZA PRZEGRAN - JAKIE MECZE NIE WCHODZA (85%+) ===')
przeg = sub85[sub85['Status'] == 'PRZEGRANA'].copy()
print(f'Przegrane mecze: {len(przeg)}')
print(f'Rozklad wyniku: {przeg["Wynik_Rzeczywisty"].value_counts().to_dict()}')
print(f'Kto typował w przegranej: {przeg["Typ_Modelu"].value_counts().to_dict()}')
print(f'Sredni MAX_Szansa przegrana: {przeg["MAX_Szansa"].mean():.1f}%')
print(f'Sredni kurs przegrane: {przeg["Kurs_val"].mean():.2f}')
print()

# Kluczowy insight - kursy vs ROI przy progu 95%+
sub95 = df[df['MAX_Szansa'] >= 95]
print(f'=== SUPER PEWNE (>=95%): {len(sub95)} meczow ===')
w95 = (sub95['Status'] == 'WYGRANA').sum()
p95 = (sub95['Status'] == 'PRZEGRANA').sum()
print(f'WR: {w95/(w95+p95)*100:.1f}% | ROI: {sub95["Zysk/Strata (Flat 100)"].sum():.0f}')
print(f'Sredni kurs: {sub95["Kurs_val"].mean():.2f}  Mediana kursu: {sub95["Kurs_val"].median():.2f}')
print(f'Proc kursow < 1.15: {(sub95["Kurs_val"] < 1.15).mean()*100:.1f}%')

# Wyliczymy ile by zarobily mecze 85%+ jesli by wyloczyc te z kursem < 1.12
print()
print('=== FILTROWANIE - 85%+ I KURS >= 1.15 ===')
sub85_hk = sub85[sub85['Kurs_val'] >= 1.15]
w = (sub85_hk['Status'] == 'WYGRANA').sum()
p = (sub85_hk['Status'] == 'PRZEGRANA').sum()
wr = w / (w + p) * 100
roi = sub85_hk['Zysk/Strata (Flat 100)'].sum()
print(f'{len(sub85_hk)} meczow | WR: {wr:.1f}% | ROI: {roi:.0f}')

print()
print('=== FILTROWANIE - 88%+ I KURS 1.10-1.40 ===')
sub88_mid = df[(df['MAX_Szansa'] >= 88) & (df['Kurs_val'] >= 1.10) & (df['Kurs_val'] <= 1.40)]
w = (sub88_mid['Status'] == 'WYGRANA').sum()
p = (sub88_mid['Status'] == 'PRZEGRANA').sum()
wr = w / (w + p) * 100
roi = sub88_mid['Zysk/Strata (Flat 100)'].sum()
print(f'{len(sub88_mid)} meczow | WR: {wr:.1f}% | ROI: {roi:.0f}')
