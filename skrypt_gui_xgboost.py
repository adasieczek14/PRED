import pandas as pd
import numpy as np
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from xgboost import XGBClassifier
import warnings
warnings.filterwarnings('ignore')

CSV_FILE = r"C:\Users\admin\Desktop\PRACA INZYNIERSKA\DANE CSV PO TRANSFOMACJI\fctables_data_tranformacja.csv"

def main():
    print("Generowanie ślepej próby historycznej XGBoost dla GUI...")
    df = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8')
    df = df.dropna(subset=['Kurs', 'TFI', 'TFI HA', 'Rezultat'])
    
    for col in ['Kurs', 'TFI', 'TFI HA']:
        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
        
    df = df[df['Faworyt'].isin([1, 2, "1", "2"])]
    df['Faworyt'] = df['Faworyt'].astype(int)
    
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    
    X_train = train_df[['Kurs', 'TFI', 'TFI HA']].values
    y_train_raw = train_df['Rezultat'].astype(str).values
    
    X_test = test_df[['Kurs', 'TFI', 'TFI HA']].values
    y_test_raw = test_df['Rezultat'].astype(str).values
    
    le = LabelEncoder()
    y_train = le.fit_transform(y_train_raw)
    y_test = le.transform(y_test_raw)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    xgb = XGBClassifier(eval_metric='mlogloss', random_state=42, n_jobs=-1)
    xgb.fit(X_train_scaled, y_train)
    
    probas = xgb.predict_proba(X_test_scaled)
    max_probs = np.max(probas, axis=1)
    preds_idx = np.argmax(probas, axis=1)
    preds = le.inverse_transform(preds_idx)
    
    test_df = test_df.copy()
    test_df['Typ_Modelu'] = preds
    test_df['MAX_Szansa'] = max_probs * 100
    
    df_pewniaki = test_df[test_df['MAX_Szansa'] >= 80.0].copy()
    
    out_rows = []
    
    for _, row in df_pewniaki.iterrows():
        wynik_rzecz = row['Rezultat']
        typ = row['Typ_Modelu']
        faw = row['Faworyt']
        kurs = row['Kurs']
        
        status = "WYGRANA" if str(typ) == str(wynik_rzecz) else "PRZEGRANA"
        
        zysk = 0.0
        if status == "WYGRANA":
            if str(faw) == str(typ):
                zysk = (100 * kurs) - 100
            else:
                zysk = 0.0
        else:
            zysk = -100.0
            
        mecz = f"{row['Druzyna_Gospodarzy']} vs {row['Druzyna_Gosci']}"
        gole = f"{row['GOLE_Gospodarzy']}:{row['GOLE_Gosci']}"
        
        out_rows.append({
            "Data_Rozegrania": row['Data'],
            "Mecz": mecz,
            "Liga": row.get('Liga', 'Inne'),
            "Typ_Modelu": typ,
            "Wynik_Rzeczywisty": wynik_rzecz,
            "Gole": gole,
            "Status": status,
            "Kurs [Faworyt]": f"{kurs} ({faw})",
            "MAX_Szansa": round(row['MAX_Szansa'], 2),
            "Zysk/Strata (Flat 100)": round(zysk, 2)
        })
        
    res_df = pd.DataFrame(out_rows)
    res_df = res_df.sort_values(by='Data_Rozegrania')
    
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZWALIDOWANE_TYPY_XGB_HISTORYCZNIE.csv")
    res_df.to_csv(save_path, sep=';', index=False, encoding='utf-8-sig')
    print(f"Wygenerowano {len(res_df)} historycznych spotkań do pliku CSV dla GUI!")

if __name__ == "__main__":
    main()
