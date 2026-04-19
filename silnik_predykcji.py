import pandas as pd
import numpy as np
import argparse
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore') # Ukrycie ostrzezen przy transformacjach danych

# Ścieżka do naszego docelowego CSV
CSV_FILE = r"C:\Users\admin\Desktop\PRACA INZYNIERSKA\DANE CSV PO TRANSFOMACJI\fctables_data_tranformacja.csv"

def load_and_prepare_data():
    print("Trwa ładowanie bazy danych, chwileczkę...")
    # Ładowanie z polskim separatorem po modyfikacjach scrapera/excela
    df = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8')
    
    # Podstawowe czyszczenie z braków danych - mecze bez kursu nie wezma udzialu w nauczaniu
    df = df.dropna(subset=['Kurs', 'TFI', 'TFI HA', 'Rezultat'])
    
    # Zamiana tekstowych przecinków z Excela na kropki pythona, aby można było na nich uczyć maszyny (liczyć odległości wektorowe)
    for col in ['Kurs', 'TFI', 'TFI HA']:
        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
        
    # Odfiltrowanie tylko wierszy, gdzie faktycznie faworyt byl znany 1/2
    df = df[df['Faworyt'].isin([1, 2, "1", "2"])]
    df['Faworyt'] = df['Faworyt'].astype(int)
    
    print(f"Baza załadowana! Ilość poprawnych meczów historycznych do treningu: {len(df)}")
    return df

def find_similar_matches(df, current_tfi, current_tfi_ha, current_kurs, current_faworyt, k_neighbors=25, quiet=False):
    """
    Znajduje k-podobnych meczy na podstawie wprowadzonych danych z uzyciem uczenia maszynowego (KNN).
    """
    # 1. Filtrujemy mecze tak, by szukac wlasciwosci na takim samym rynku (gospodarz vs gosc faworyzowany)
    df_filtered = df[df['Faworyt'] == current_faworyt].copy()
    
    if len(df_filtered) < k_neighbors:
        if not quiet:
            print(f"Za mało danych dla układu Faworyt={current_faworyt}. Zmniejszam K do {len(df_filtered)}.")
        k_neighbors = len(df_filtered)
        
    # 2. Definicja Cech ML dla których poszukujemy geometrycznego najbliższego sasiada (szukamy po 3 osiach X,Y,Z)
    features = ['Kurs', 'TFI', 'TFI HA']
    X = df_filtered[features].values
    
    # Skalujemy dane (Ustawiamy kurs, TFI i Handi na jednej skali 0-1, zeby -5 w TFI nie wazylo 100x wiecej od 2.15 w Kursie
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # 3. Definiujemy nasz dzisiejszy wejsciowy rozklad
    wejscie = np.array([[current_kurs, current_tfi, current_tfi_ha]])
    wejscie_scaled = scaler.transform(wejscie)
    
    # 4. Inicjacja silnika Scikit-Learn (Sztuczna Inteligencja) KNN 
    knn = NearestNeighbors(n_neighbors=k_neighbors, metric='euclidean')
    knn.fit(X_scaled)
    
    # Zwraca dokladne odleglosci oraz indeksy "Sąsiadów" z tabeli
    distances, indices = knn.kneighbors(wejscie_scaled)
    
    # 5. Wyciaga z historii tylko te dopasowane wiersze (Sasiadow)
    nearest_matches = df_filtered.iloc[indices[0]].copy()
    
    # Generowanie raportu predykcyjnego
    if not quiet:
        print("\n" + "="*50)
        print(f"--- ANALIZA PODOBIEŃSTW - SCENARIUSZ NA DZIŚ ---")
        print(f"FAWORYT: {current_faworyt} | KURS: {current_kurs} | TFI: {current_tfi} | TFI HA: {current_tfi_ha}")
        print("="*50)
        print(f"Znaleziono {k_neighbors} najbardziej zbliżonych historycznych meczów.\n")
        
    # Podlicz wyniki (ile razy 1, X, 2 z sąsiadów)
    wyniki_count = nearest_matches['Rezultat'].value_counts(normalize=True).dropna() * 100
    powodzenie_faw = nearest_matches['Skutecznosc_Faworyta'].mean() * 100
    
    if not quiet:
        print("--- Prawdopodobieństwo na podstawie historii wg. Skuteczności:")
        print(f"Wygrana Faworyta ({current_faworyt}): {powodzenie_faw:.1f}%")
        
        print("\n--- Rozkład wyników 1X2 w podobnych sytuacjach:")
        szansa_1 = wyniki_count.get('1', 0)
        szansa_X = wyniki_count.get('X', 0)
        szansa_2 = wyniki_count.get('2', 0)
        
        print(f"1 (Gospodarz) : {szansa_1:.1f}%")
        print(f"X (Remis)     : {szansa_X:.1f}%")
        print(f"2 (Gość)      : {szansa_2:.1f}%")
        print("="*50)
        
        # Pokaz 5 najnowszych wierszy na potwiedzenie
        print("\nOstatnie 5 historycznych przykładów tego konkretnego układu sił (sąsiadów):")
        cols_to_show = ['Data', 'Druzyna_Gospodarzy', 'GOLE_Gospodarzy', 'GOLE_Gosci', 'Druzyna_Gosci', 'Kurs', 'TFI', 'TFI HA', 'Rezultat']
        print("="*50 + "\n")
    else:
        szansa_1 = wyniki_count.get('1', 0)
        szansa_X = wyniki_count.get('X', 0)
        szansa_2 = wyniki_count.get('2', 0)
    
    return {
        "szansa_1": szansa_1,
        "szansa_X": szansa_X,
        "szansa_2": szansa_2,
        "skutecznosc_faworyta": powodzenie_faw
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Algorytm Predykcyjny TFI (KNN)")
    parser.add_argument("--faw", type=int, required=True, help="Rynkowy faworyt (1 lub 2)")
    parser.add_argument("--kurs", type=float, required=True, help="Kurs na faworyta (np. 1.85)")
    parser.add_argument("--tfi", type=float, required=True, help="Wskaznik TFI (np. 3.40)")
    parser.add_argument("--tfiha", type=float, required=True, help="Wskaznik TFI HA (np. -1.05)")
    parser.add_argument("--k", type=int, default=20, help="Ilosc wyszukiwanych sasiadow podobnych (np. 20)")
    
    args = parser.parse_args()
    
    df = load_and_prepare_data()
    find_similar_matches(df, current_tfi=args.tfi, current_tfi_ha=args.tfiha, current_kurs=args.kurs, current_faworyt=args.faw, k_neighbors=args.k)
