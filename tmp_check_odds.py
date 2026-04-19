import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from xgboost import XGBClassifier

CSV_FILE = r"C:\Users\admin\Desktop\PRACA INZYNIERSKA\DANE CSV PO TRANSFOMACJI\fctables_data_tranformacja.csv"

def main():
    df = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8')
    df = df.dropna(subset=['Kurs', 'TFI', 'TFI HA', 'Rezultat'])
    for col in ['Kurs', 'TFI', 'TFI HA']:
        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
        
    df = df[df['Faworyt'].isin([1, 2, "1", "2"])]
    df['Faworyt'] = df['Faworyt'].astype(int)
    
    X = df[['Kurs', 'TFI', 'TFI HA']].values
    y = df['Rezultat'].astype(str).values
    
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=0.2, random_state=42)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    xgb = XGBClassifier(eval_metric='mlogloss', random_state=42, n_jobs=-1)
    xgb.fit(X_train_scaled, y_train)
    
    xgb_probas = xgb.predict_proba(X_test_scaled)
    max_probs = np.max(xgb_probas, axis=1)
    high_conf_idx = max_probs >= 0.80
    
    kursy_pewniakow = X_test[high_conf_idx, 0] # Z index 0 wyciagamy Kurs
    
    print(f"Liczba meczów XGBoost >80%: {len(kursy_pewniakow)}")
    print(f"Sredni kurs: {np.mean(kursy_pewniakow):.2f}")
    print(f"Mediana kursu: {np.median(kursy_pewniakow):.2f}")
    print(f"Minimalny kurs: {np.min(kursy_pewniakow):.2f}")
    print(f"Maksymalny kurs: {np.max(kursy_pewniakow):.2f}")
    print("-" * 30)
    
    # Przedziały
    ranges = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 5.0]
    for i in range(len(ranges)-1):
        low, high = ranges[i], ranges[i+1]
        count = np.sum((kursy_pewniakow >= low) & (kursy_pewniakow < high))
        print(f"Kursy pomiedzy {low:.2f} a {high:.2f} : {count} meczow ({count/len(kursy_pewniakow)*100:.1f}%)")

if __name__ == "__main__":
    main()
