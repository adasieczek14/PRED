import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
try:
    from xgboost import XGBClassifier
except ImportError:
    print("Brak biblioteki xgboost. Zainstaluj ja przez: pip install xgboost")
    exit(1)
import warnings
warnings.filterwarnings('ignore')

CSV_FILE = r"C:\Users\admin\Desktop\PRACA INZYNIERSKA\DANE CSV PO TRANSFOMACJI\fctables_data_tranformacja.csv"

def evaluate_model(model_name, y_true, y_pred, y_proba, classes):
    # Ogolny accuracy
    acc = np.mean(y_true == y_pred) * 100
    
    # "Pewniaki" - sprawdzamy tylko te mecze, w ktorych model przewidzial ktoras z opcji pow. 80% (0.80)
    max_probs = np.max(y_proba, axis=1)
    high_conf_idx = max_probs >= 0.80
    
    y_true_high = y_true[high_conf_idx]
    y_pred_high = y_pred[high_conf_idx]
    
    if len(y_true_high) > 0:
        acc_high = np.mean(y_true_high == y_pred_high) * 100
        count_high = len(y_true_high)
    else:
        acc_high = 0.0
        count_high = 0
        
    print(f"--- Model: {model_name} ---")
    print(f"Ogólna Skuteczność (Wszystkie 1X2): {acc:.1f}%")
    print(f"Skuteczność 'Pewniaków' (>80%): {acc_high:.1f}% (Znaleziono {count_high} meczów)")
    print("-" * 40)

def main():
    print("Ładowanie historycznej bazy danych (fctables_data_tranformacja.csv)...")
    try:
        df = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8')
    except Exception as e:
        print(f"Błąd ładowania docelowego pliku CSV: {e}")
        return
        
    df = df.dropna(subset=['Kurs', 'TFI', 'TFI HA', 'Rezultat'])
    
    # Poprawa separatorów
    for col in ['Kurs', 'TFI', 'TFI HA']:
        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
        
    df = df[df['Faworyt'].isin([1, 2, "1", "2"])]
    df['Faworyt'] = df['Faworyt'].astype(int)
    
    # Nasze wymiary cech (Feature Matrix) 
    X = df[['Kurs', 'TFI', 'TFI HA']].values
    y = df['Rezultat'].astype(str).values
    
    # Kodowanie Zmiennej celu z [1, X, 2] do id [0, 1, 2] by mozna bylo podac to do matematyki XGBoost'a
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    # Rozbiórka na dane Treningowe i w pelni odizolowane Testowe ("zwalidowane w ciemno") -> 80% / 20%
    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42)
    
    # Wspólne skalowanie dla wszystkich by ułatwić zadanie klasyfikatorom (tak jak robil to Twoj silnik KNN)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    # Zauwaz, testowe transformujemy gotowym skalerem - algorytm ml nie moze podgladac danych testowych srednich!
    X_test_scaled = scaler.transform(X_test) 
    
    print(f"Baza gotowa. Zbiór Treningowy: {len(X_train)} meczów, Zbiór Do Weryfikacji: {len(X_test)} meczów.\n")
    print("Trenowanie modeli... To zajmie dosłownie chwilę.\n")
    
    # 1. Klasyczny KNN (Nasz Obecny Benchmark)
    knn = KNeighborsClassifier(n_neighbors=25, metric='euclidean', n_jobs=-1)
    knn.fit(X_train_scaled, y_train)
    evaluate_model("KNN (Obecny Algorytm Projektu)", y_test, knn.predict(X_test_scaled), knn.predict_proba(X_test_scaled), le.classes_)
    
    # 2. Las Losowy (Random Forest) - Składa się ze 100 drzew decyzyjnych i głosuje na najlepszy wynik
    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train_scaled, y_train)
    evaluate_model("Random Forest (Las Losowy)", y_test, rf.predict(X_test_scaled), rf.predict_proba(X_test_scaled), le.classes_)
    
    # 3. XGBoost - Potezny model podbijajania slabiutkich drzew (Gradient Boosting)
    xgb = XGBClassifier(eval_metric='mlogloss', random_state=42, n_jobs=-1)
    xgb.fit(X_train_scaled, y_train)
    evaluate_model("XGBoost", y_test, xgb.predict(X_test_scaled), xgb.predict_proba(X_test_scaled), le.classes_)

if __name__ == "__main__":
    main()
