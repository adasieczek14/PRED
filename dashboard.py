# -*- coding: utf-8 -*-
"""
Aplikacja Webowa: Panel Dashboard Typów (Streamlit)
Interaktywny panel prezentujący dzisiejsze typy AI oraz historię skuteczności (Backtest) w oparciu o zwalidowane wyniki.
Idealne środowisko graficzne pod obronę pracy.
"""

import streamlit as st
import pandas as pd
import glob
import os
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# ==========================================
# KONFIGURACJA STRONY (Zawsze na samej górze)
# ==========================================
st.set_page_config(
    page_title="AI Predykcje Wyników - Panel",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================
# GOOGLE ANALYTICS 4
# ==========================================
# Inject GA tag into the main Streamlit page <head> (covers root URL /)
st.markdown("""
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-M6GPSMNMK2"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-M6GPSMNMK2', {
    'page_title': 'AI Predykcje Wyników - Panel',
    'page_location': 'https://x6vskskmsh93n9r8qzxikhyv.streamlit.app/'
  });
</script>
""", unsafe_allow_html=True)

# Also fire a pageview from within the iframe (covers /~/+/) using postMessage to parent
components.html("""
<script>
  (function() {
    // Fire gtag directly inside iframe context
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-M6GPSMNMK2', {
      'page_title': 'AI Predykcje Wyników - Panel',
      'page_location': 'https://x6vskskmsh93n9r8qzxikhyv.streamlit.app/'
    });
    // Notify parent frame to also fire GA (belt-and-suspenders)
    try {
      window.parent.postMessage({type: 'GA_PAGEVIEW', gtmId: 'G-M6GPSMNMK2'}, '*');
    } catch(e) {}
  })();
</script>
""", height=0)


# ==========================================
# GŁÓWNA LOGIKA DANYCH
# ==========================================
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

@st.cache_data
def load_today_predictions(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    file_path = os.path.join(DATA_DIR, f"DZISIEJSZE_TYPY_{date_str}.csv")
    if os.path.exists(file_path):
        return pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
    return pd.DataFrame()

@st.cache_data
def load_today_predictions_xgb(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    file_path = os.path.join(DATA_DIR, f"DZISIEJSZE_TYPY_XGB_{date_str}.csv")
    if os.path.exists(file_path):
        return pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
    return pd.DataFrame()

@st.cache_data
def load_today_predictions_ensemble(date_str=None):
    """Ładuje dzisiejsze typy Ensemble (KNN+XGB) dla podanej daty."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    file_path = os.path.join(DATA_DIR, f"DZISIEJSZE_TYPY_ENSEMBLE_{date_str}.csv")
    if os.path.exists(file_path):
        return pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
    return pd.DataFrame()

@st.cache_data
def load_today_predictions_ou(date_str=None):
    """Ładuje dzisiejsze typy Over/Under dla podanej daty."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(DATA_DIR, f"DZISIEJSZE_TYPY_OU_{date_str}.csv")
    if os.path.exists(file_path):
        return pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
    return pd.DataFrame()

@st.cache_data
def load_ou_base_stats():
    """Wylicza statystyki Over/Under z całej bazy fctables_data.csv (cached)."""
    csv_path = os.path.join(DATA_DIR, "fctables_data.csv")
    if not os.path.exists(csv_path):
        return {}
    try:
        df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
        df['GOLE_Gospodarzy'] = pd.to_numeric(df['GOLE_Gospodarzy'], errors='coerce')
        df['GOLE_Gosci']      = pd.to_numeric(df['GOLE_Gosci'],      errors='coerce')
        df = df.dropna(subset=['GOLE_Gospodarzy', 'GOLE_Gosci'])
        df['Total'] = df['GOLE_Gospodarzy'] + df['GOLE_Gosci']
        n = len(df)
        return {
            'total_mecze': n,
            'over_05': round((df['Total'] >= 1).sum() / n * 100, 1),
            'over_15': round((df['Total'] >= 2).sum() / n * 100, 1),
            'over_25': round((df['Total'] >= 3).sum() / n * 100, 1),
            'over_35': round((df['Total'] >= 4).sum() / n * 100, 1),
            'btts':    round(((df['GOLE_Gospodarzy'] >= 1) & (df['GOLE_Gosci'] >= 1)).sum() / n * 100, 1),
            'srednia_goli': round(df['Total'].mean(), 2),
            'dist': df['Total'].value_counts().sort_index(),
        }
    except Exception:
        return {}

@st.cache_data
def load_league_stats_ou_db():
    """Wyciąga statystyki O/U i BTTS dla każdej ligi z fctables_data.csv."""
    csv_path = os.path.join(DATA_DIR, "fctables_data.csv")
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
        df['GOLE_Gospodarzy'] = pd.to_numeric(df['GOLE_Gospodarzy'], errors='coerce')
        df['GOLE_Gosci']      = pd.to_numeric(df['GOLE_Gosci'],      errors='coerce')
        df = df.dropna(subset=['GOLE_Gospodarzy', 'GOLE_Gosci', 'Liga'])
        df['Total'] = df['GOLE_Gospodarzy'] + df['GOLE_Gosci']
        df['Over 1.5'] = (df['Total'] >= 2).astype(int)
        df['Over 2.5'] = (df['Total'] >= 3).astype(int)
        df['BTTS'] = ((df['GOLE_Gospodarzy'] >= 1) & (df['GOLE_Gosci'] >= 1)).astype(int)
        
        ls = df.groupby('Liga').agg(
            Mecze=('Liga', 'count'),
            O15=('Over 1.5', 'sum'),
            O25=('Over 2.5', 'sum'),
            B=('BTTS', 'sum'),
            Sr_Goli=('Total', 'mean')
        ).reset_index()
        
        ls['% Over 1.5'] = (ls['O15'] / ls['Mecze'] * 100).round(1)
        ls['% Over 2.5'] = (ls['O25'] / ls['Mecze'] * 100).round(1)
        ls['% BTTS'] = (ls['B'] / ls['Mecze'] * 100).round(1)
        ls['Śr. Goli'] = ls['Sr_Goli'].round(2)
        
        return ls[['Liga', 'Mecze', '% Over 1.5', '% Over 2.5', '% BTTS', 'Śr. Goli']]
    except Exception:
        return pd.DataFrame()

@st.cache_data
def load_validation_history_ensemble():
    """Ładuje całą historię zwalidowanych typów Ensemble (ZWALIDOWANE_TYPY_ENSEMBLE_*.csv)."""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "ZWALIDOWANE_TYPY_ENSEMBLE_2026-*.csv")))
    if not files:
        return pd.DataFrame()
        
    df_list = []
    for f in files:
        basename = os.path.basename(f)
        date_part = basename.replace("ZWALIDOWANE_TYPY_ENSEMBLE_", "").replace(".csv", "")
        try:
            temp_df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
            temp_df['Data_Rozegrania'] = date_part
            df_list.append(temp_df)
        except Exception as e:
            st.error(f"Błąd ładowania {f}: {e}")
            
    if df_list:
        return pd.concat(df_list, ignore_index=True)
    return pd.DataFrame()

@st.cache_data
def load_validation_history():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "ZWALIDOWANE_TYPY_*.csv")))
    files = [f for f in files if "XGB" not in os.path.basename(f) and "ENSEMBLE" not in os.path.basename(f) and "OU" not in os.path.basename(f) and "BTTS" not in os.path.basename(f)]
    if not files:
        return pd.DataFrame()
        
    df_list = []
    for f in files:
        # Wyciagnij date z nazwy pliku ZWALIDOWANE_TYPY_YYYY-MM-DD.csv
        basename = os.path.basename(f)
        date_part = basename.replace("ZWALIDOWANE_TYPY_", "").replace(".csv", "")
        
        try:
            temp_df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
            temp_df['Data_Rozegrania'] = date_part
            df_list.append(temp_df)
        except Exception as e:
            st.error(f"Błąd ładowania {f}: {e}")
            
    if df_list:
        combined = pd.concat(df_list, ignore_index=True)
        return combined
    return pd.DataFrame()

@st.cache_data
def load_validation_history_xgb():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "ZWALIDOWANE_TYPY_XGB_*.csv")))
    files = [f for f in files if "HISTORYCZNIE" not in os.path.basename(f)]
    if not files:
        return pd.DataFrame()
        
    df_list = []
    for f in files:
        basename = os.path.basename(f)
        date_part = basename.replace("ZWALIDOWANE_TYPY_XGB_", "").replace(".csv", "")
        
        try:
            temp_df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
            temp_df['Data_Rozegrania'] = date_part
            df_list.append(temp_df)
        except Exception as e:
            st.error(f"Błąd ładowania {f}: {e}")
            
    if df_list:
        combined = pd.concat(df_list, ignore_index=True)
        return combined
    return pd.DataFrame()

@st.cache_data
def load_ou_validation_history():
    """Ładuje całą historię zwalidowanych typów O/U (ZWALIDOWANE_TYPY_OU_*.csv)."""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "ZWALIDOWANE_TYPY_OU_*.csv")))
    if not files:
        return pd.DataFrame()
    parts = []
    for f in files:
        bn = os.path.basename(f)
        date_part = bn.replace("ZWALIDOWANE_TYPY_OU_", "").replace(".csv", "")
        try:
            tmp = pd.read_csv(f, sep=';', encoding='utf-8-sig')
            tmp['Data_Rozegrania'] = date_part
            parts.append(tmp)
        except Exception:
            pass
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

# ==========================================
# INTERFEJS UŻYTKOWNIKA (UI)
# ==========================================

st.sidebar.title("⚽ Opcje Panelu")
menu = st.sidebar.radio("Nawigacja", [
    "🤖 Dzisiejsze Typy (Live)",
    "🤖 Dzisiejsze Typy XGBoost (Live)",
    "🧬 Dzisiejsze Typy Ensemble (KNN+XGB)",
    "⚽ Over/Under — Typy Bramkowe (Live)",
    "📊 Skuteczność (Historia)",
    "📊 Skuteczność XGBoost (Historia)",
    "📊 Skuteczność Ensemble (Historia)",
    "📊 Skuteczność Over/Under (Historia)",
    "🏆 Ślepy Test XGBoost (Eksperymentalne)"
])
st.sidebar.markdown("---")
st.sidebar.info("Panel Inżynierski — Predykcje AI: KNN, XGBoost (skalibrowany) i Ensemble KNN+XGB.")

if menu == "🤖 Dzisiejsze Typy (Live)":
    st.title("Nadchodzące spotkania (Predykcje AI)")
    
    # Wybór daty do predykcji (dzisiaj lub historia)
    wybrana_data = st.date_input("Wybierz dzień z predykcjami:", datetime.now())
    date_str = wybrana_data.strftime("%Y-%m-%d")
    
    df_today = load_today_predictions(date_str)
    
    if df_today.empty:
        st.warning(f"Brak wygenerowanych predykcji na dzień {date_str}. Uruchom skrypt automatyczny_typer.py dla tej daty.")
    else:
        st.success(f"Załadowano {len(df_today)} przewidzianych spotkań na dzień {date_str}.")
        
        # Filtrowanie pewniaków
        min_szansa = st.slider("Pokaż tylko pewne typy (Filtruj wg najwyższej % szansy):", min_value=33, max_value=100, value=65)
        
        # Oblicz "MAX Szansa" kolumnę sztuczną do filtru
        df_today['Najwyzszy_Procent'] = df_today[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
        filtered_df = df_today[df_today['Najwyzszy_Procent'] >= min_szansa].copy()
        
        def highlight_max(row):
            """Funkcja kolorująca wiersz na zielono jeśli Prawdopodobienstwo np >= 80%"""
            val = max(
                row.get('% Wygranej Gospodarza [1]', 0), 
                row.get('% Remisu [X]', 0), 
                row.get('% Wygranej Goscia [2]', 0)
            )
            if val >= 80:
                return ['background-color: rgba(46, 204, 113, 0.2)'] * len(row)
            elif val >= 65:
                return ['background-color: rgba(241, 196, 15, 0.1)'] * len(row)
            return [''] * len(row)
            
        # Wyświetlanie tabeli ładnie ostylowanej
        display_df = filtered_df.drop(columns=['Najwyzszy_Procent']).copy()
        
        WARNING_LEAGUES = {
            'Brazil 1': '⚠️ (Zalecana ostrożność: 40% błędów)',
            'Australia 2': '⚠️ (35% błędów)',
            'Germany 4': '⚠️ (34% błędów)',
            'Sweden 4': '⚠️ (32% błędów)',
            'Saudi Arabia 1': '⚠️ (31% błędów)',
            'Bolivia 1': '🔥 (Złota Liga: 100%)',
            'Scotland 1': '🔥 (Złota Liga: 100%)',
            'Faroe Islands 1': '🔥 (100%)',
            'England 6': '🔥 (100%)',
            'Portugal 1': '⭐ (Elita: 94%)',
            'China 1': '⭐ (Elita: 93%)',
            'Singapore 1': '⭐ (Elita: 93%)'
        }
        display_df['Liga'] = display_df['Liga'].apply(lambda x: f"{x} {WARNING_LEAGUES[x]}" if x in WARNING_LEAGUES else x)
        
        st.dataframe(
            display_df.style.apply(highlight_max, axis=1), 
            use_container_width=True,
            height=600
        )

elif menu == "🤖 Dzisiejsze Typy XGBoost (Live)":
    st.title("Nadchodzące spotkania (Predykcje XGBoost)")
    
    wybrana_data_xgb = st.date_input("Wybierz dzień z predykcjami:", datetime.now(), key="xgb_date")
    date_str_xgb = wybrana_data_xgb.strftime("%Y-%m-%d")
    
    df_today_xgb = load_today_predictions_xgb(date_str_xgb)
    
    if df_today_xgb.empty:
        st.warning(f"Brak wygenerowanych predykcji XGBoost na dzień {date_str_xgb}. Uruchom najpierw skrypt 'automatyczny_typer_xgb.py' dla tej daty.")
    else:
        st.success(f"Załadowano {len(df_today_xgb)} przewidzianych przez XGBoost spotkań na dzień {date_str_xgb}.")
        
        min_szansa_xgb = st.slider("Pokaż tylko pewne typy (Filtruj wg najwyższej % szansy):", min_value=33, max_value=100, value=65, key="xgb_slider")
        
        df_today_xgb['Najwyzszy_Procent'] = df_today_xgb[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
        filtered_df_xgb = df_today_xgb[df_today_xgb['Najwyzszy_Procent'] >= min_szansa_xgb].copy()
        
        def highlight_max_xgb(row):
            val = max(
                row.get('% Wygranej Gospodarza [1]', 0), 
                row.get('% Remisu [X]', 0), 
                row.get('% Wygranej Goscia [2]', 0)
            )
            
            # Weryfikacja opadającego kursu
            delta = row.get('Delta_Kursu', 0)
            try:
                # Zamiana na float, ignorując puste stringi
                delta_val = float(str(delta).strip().replace(',', '.')) if str(delta).strip() else 0.0
            except:
                delta_val = 0.0
                
            # Jeśli rynek wgrywa mnóstwo kasy (duży spadek kursów na faworyta) -> Fioletowy kolor
            if delta_val < -0.10:
                return ['background-color: rgba(155, 89, 182, 0.5); font-weight: bold;'] * len(row)
                
            # Lekko czerwony odcień odpowiadający wykresowi XGBoost
            if val >= 80:
                # Jeśli kurs rośnie niepokojąco przeciwko nam
                if delta_val > 0.10:
                    return ['background-color: rgba(0, 0, 0, 0.8); color: red;'] * len(row) # Blacklist
                return ['background-color: rgba(231, 76, 60, 0.2)'] * len(row) 
            elif val >= 65:
                if delta_val > 0.10:
                    return ['background-color: rgba(0, 0, 0, 0.8); color: red;'] * len(row) # Blacklist
                return ['background-color: rgba(241, 196, 15, 0.1)'] * len(row)
            return [''] * len(row)
        display_df_xgb = filtered_df_xgb.drop(columns=['Najwyzszy_Procent']).copy()
        
        WARNING_LEAGUES = {
            'Brazil 1': '⚠️ (Zalecana ostrożność: 40% błędów)',
            'Australia 2': '⚠️ (35% błędów)',
            'Germany 4': '⚠️ (34% błędów)',
            'Sweden 4': '⚠️ (32% błędów)',
            'Saudi Arabia 1': '⚠️ (31% błędów)',
            'Bolivia 1': '🔥 (Złota Liga: 100%)',
            'Scotland 1': '🔥 (Złota Liga: 100%)',
            'Faroe Islands 1': '🔥 (100%)',
            'England 6': '🔥 (100%)',
            'Portugal 1': '⭐ (Elita: 94%)',
            'China 1': '⭐ (Elita: 93%)',
            'Singapore 1': '⭐ (Elita: 93%)'
        }
        display_df_xgb['Liga'] = display_df_xgb['Liga'].apply(lambda x: f"{x} {WARNING_LEAGUES[x]}" if x in WARNING_LEAGUES else x)
        
        st.dataframe(
            display_df_xgb.style.apply(highlight_max_xgb, axis=1), 
            use_container_width=True,
            height=600
        )
        
        with st.expander("🏆 Zobacz pełną historyczną przewidywalność wszystkich lig (Eksplorator)"):
            st.markdown("""
            Na przeliczeniu **1296 meczów** ze Ślepego Testu (gdzie model dawał >80% szans faworytowi), zbudowaliśmy interaktywne zestawienie. Sprawdź, jak algorytm historycznie radzi sobie z Twoimi ulubionymi ligami!
            """)
            
            hist_file_xgb = os.path.join(DATA_DIR, "ZWALIDOWANE_TYPY_XGB_HISTORYCZNIE.csv")
            if os.path.exists(hist_file_xgb):
                df_hist_xgb_exp = pd.read_csv(hist_file_xgb, sep=';', encoding='utf-8-sig')
                
                try:
                    df_hist_xgb_exp['Data_DT'] = pd.to_datetime(df_hist_xgb_exp['Data_Rozegrania'], dayfirst=True).dt.date
                    min_d = df_hist_xgb_exp['Data_DT'].min()
                    max_d = df_hist_xgb_exp['Data_DT'].max()
                except Exception:
                    min_d = datetime.now().date()
                    max_d = datetime.now().date()
                    df_hist_xgb_exp['Data_DT'] = max_d
                    
                col_a, col_b, col_c = st.columns([1, 1, 2])
                with col_a:
                    zakres_dat = st.date_input("Zakres dat:", value=(min_d, max_d), min_value=min_d, max_value=max_d, key="xgb_exp_date")
                    
                if isinstance(zakres_dat, tuple) and len(zakres_dat) == 2:
                    df_hist_xgb_exp = df_hist_xgb_exp[(df_hist_xgb_exp['Data_DT'] >= zakres_dat[0]) & (df_hist_xgb_exp['Data_DT'] <= zakres_dat[1])]

                ls_exp = df_hist_xgb_exp.groupby('Liga').agg(
                    Rozegrane=('Status', 'count'),
                    Wygrane=('Status', lambda x: (x == 'WYGRANA').sum())
                ).reset_index()
                
                if not ls_exp.empty:
                    ls_exp['Skuteczność (%)'] = (ls_exp['Wygrane'] / ls_exp['Rozegrane']) * 100
                else:
                    ls_exp['Skuteczność (%)'] = pd.Series(dtype=float)
                    
                with col_b:
                    min_roz = st.number_input("Od ilu rozegranych pokazywać:", min_value=1, value=5, step=1, key="xgb_min_rozegrane")
                with col_c:
                    all_leagues = sorted(df_hist_xgb_exp['Liga'].dropna().unique())
                    wyb_ligi = st.multiselect("Wyszukaj konkretne ligi:", options=all_leagues, default=[], key="xgb_szukaj_lig")
                
                if not ls_exp.empty:
                    if wyb_ligi:
                        ls_exp = ls_exp[ls_exp['Liga'].isin(wyb_ligi)]
                    else:
                        ls_exp = ls_exp[ls_exp['Rozegrane'] >= min_roz]
                        
                    ls_exp = ls_exp.sort_values(by=['Skuteczność (%)', 'Rozegrane'], ascending=[False, False])
                
                def style_winrate(val):
                    if val >= 85: return 'background-color: rgba(46, 204, 113, 0.3)'
                    elif val >= 70: return 'background-color: rgba(241, 196, 15, 0.2)'
                    else: return 'background-color: rgba(231, 76, 60, 0.3)'

                try:
                    styled_df = ls_exp.style.format({'Skuteczność (%)': '{:.2f}'}).map(style_winrate, subset=['Skuteczność (%)'])
                except AttributeError:
                    # Kompatybilność ze starszymi wersjami pandas
                    styled_df = ls_exp.style.format({'Skuteczność (%)': '{:.2f}'}).applymap(style_winrate, subset=['Skuteczność (%)'])

                st.dataframe(styled_df, use_container_width=True, height=400)
                
                st.markdown("---")
                st.markdown("#### 🔍 Podgląd wchodzących w skład meczów")
                st.caption(f"Tabela pokazuje ułożone chronologicznie wszystkie mecze dla {len(ls_exp)} wyselekcjonowanych wyżej lig zgodnych z Twoim zakresem dat.")
                
                if not ls_exp.empty:
                    widoczne_ligi = ls_exp['Liga'].tolist()
                    df_raw_filtered = df_hist_xgb_exp[df_hist_xgb_exp['Liga'].isin(widoczne_ligi)].copy()
                    df_raw_filtered = df_raw_filtered.sort_values(by='Data_DT', ascending=False)
                    
                    cols_to_show = ['Data_Rozegrania', 'Mecz', 'Liga', 'Typ_Modelu', 'Wynik_Rzeczywisty', 'Gole', 'Status', 'Kurs [Faworyt]', 'MAX_Szansa']
                    # Sprawdzenie brakujących jeśli df_hist się nie domknął
                    cols_to_show = [c for c in cols_to_show if c in df_raw_filtered.columns]
                    
                    def highlight_raw_matches(row):
                        if row.get('Status') == 'WYGRANA': return ['background-color: rgba(46, 204, 113, 0.2)'] * len(row)
                        elif row.get('Status') == 'PRZEGRANA': return ['background-color: rgba(231, 76, 60, 0.2)'] * len(row)
                        return [''] * len(row)
                        
                    st.dataframe(df_raw_filtered[cols_to_show].style.apply(highlight_raw_matches, axis=1), use_container_width=True, height=350)
                else:
                    st.info("Brak meczów spełniających powyższe kryteria.")
                    
                st.markdown("*💡 Wskazówka: Emotikony ostrzeżeń (⚠️) lub pochwał (🔥) przypinane w tabelach live używają tych twardych danych jako źródła.*")
            else:
                st.info("Brak pliku z historią XGBoost do wykonania w locie analizy.")

elif menu == "📊 Skuteczność (Historia)":
    st.title("Analiza Skuteczności Modelu (Walidacja)")
    
    df_hist = load_validation_history()
    
    if df_hist.empty:
        st.warning("Brak zwalidowanej historii meczów. Uruchom 'walidator_typow.py' aby przeprocesować archiwalne predykcje z rzeczywistymi wynikami.")
    else:
        # Konwersja daty dla filtra
        df_hist['Data_Rozegrania_DT'] = pd.to_datetime(df_hist['Data_Rozegrania']).dt.date
        min_date_val = df_hist['Data_Rozegrania_DT'].min()
        max_date_val = df_hist['Data_Rozegrania_DT'].max()
        
        # Obliczenie dnia poprzedniego (wczoraj)
        wczoraj = (datetime.now() - timedelta(days=1)).date()
        
        # Ustalamy domyślną datę końcową na "wczoraj", ew. ograniczone przez max_date_val
        default_end_date = wczoraj if wczoraj < max_date_val else max_date_val
        if default_end_date < min_date_val:
            default_end_date = min_date_val
            
        st.markdown("### 📅 Filtr Daty")
        date_range = st.date_input(
            "Wybierz zakres dat do analizy (widoczna historia - przedwczoraj/wczoraj):",
            value=(min_date_val, default_end_date),
            min_value=min_date_val,
            max_value=max_date_val
        )
        
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        elif isinstance(date_range, tuple) and len(date_range) == 1:
            start_date = end_date = date_range[0]
        else:
            start_date = end_date = date_range
            
        # Filtrowanie historii
        df_hist_filtered = df_hist[(df_hist['Data_Rozegrania_DT'] >= start_date) & (df_hist['Data_Rozegrania_DT'] <= end_date)].copy()
        
        # Filtruj 'Odwolany' / 'Brak' na przefiltrowanym widoku
        df_valid = df_hist_filtered[df_hist_filtered['Status'].isin(["WYGRANA", "PRZEGRANA"])].copy()
        
        if df_valid.empty:
            st.warning("Brak rozliczonych zakładów w historii (Są same odwołane).")
        else:
            # Metryki Główne (Kafelki u góry)
            total_matches = len(df_valid)
            wygrane = len(df_valid[df_valid['Status'] == 'WYGRANA'])
            win_rate = (wygrane / total_matches) * 100
            
            # Profit / Strata
            total_profit = df_valid['Zysk/Strata (Flat 100)'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Rozegrane/Zwalidowane Typy", total_matches)
            col2.metric("Win Rate (%)", f"{win_rate:.1f}%")
            col3.metric("Zysk / Strata (Flat 100j)", f"{total_profit:.2f} j")
            
            st.markdown("---")
            # --- DODATEK: Porównanie dla pewniaków (Interaktywny Filtr) ---
            st.subheader("🎯 Skuteczność dla wybranych progów pewności")
            
            df_valid['MAX_Szansa'] = df_valid[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
            
            wybrany_zakres = st.slider("Wybierz zakres pewności algorytmu (%):", min_value=75, max_value=100, value=(80, 100), step=1)
            prog_min, prog_max = wybrany_zakres
            
            df_pewniaki = df_valid[(df_valid['MAX_Szansa'] >= prog_min) & (df_valid['MAX_Szansa'] <= prog_max)].copy()
            
            if not df_pewniaki.empty:
                pew_total = len(df_pewniaki)
                pew_wygrane = len(df_pewniaki[df_pewniaki['Status'] == 'WYGRANA'])
                pew_winrate = (pew_wygrane / pew_total) * 100 if pew_total > 0 else 0
                pew_profit = df_pewniaki['Zysk/Strata (Flat 100)'].sum()
                
                c1, c2, c3 = st.columns(3)
                c1.metric(f"Liczba typów ({prog_min}%-{prog_max}%)", pew_total)
                c2.metric(f"Win Rate ({prog_min}%-{prog_max}%)", f"{pew_winrate:.1f}%", delta=f"{(pew_winrate - win_rate):.1f}% vs Ogół")
                c3.metric(f"Zysk / Strata ({prog_min}%-{prog_max}%)", f"{pew_profit:.2f} j")
                
                # Wykres kapitału
                df_pewniaki = df_pewniaki.sort_values(by='Data_Rozegrania').reset_index(drop=True)
                df_pewniaki['Krzywa_Kapitalu_Pewniaki'] = df_pewniaki['Zysk/Strata (Flat 100)'].cumsum()
                
                fig_pew_roi = px.line(df_pewniaki, x=df_pewniaki.index, y='Krzywa_Kapitalu_Pewniaki', 
                                  hover_data=['Data_Rozegrania', 'Mecz', 'Zysk/Strata (Flat 100)', 'MAX_Szansa'],
                                  labels={"index": f"Zagrany typ {prog_min}%-{prog_max}% (#)", "Krzywa_Kapitalu_Pewniaki": "Kapitał (j)"},
                                  template="plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white")
                fig_pew_roi.update_traces(line_color='#2ecc71')
                fig_pew_roi.add_hline(y=0, line_dash="dash", line_color="gray")
                st.plotly_chart(fig_pew_roi, use_container_width=True)
                
                st.markdown(f"#### 🌍 Skuteczność wg Lig w wybranym progu ({prog_min}%-{prog_max}%)")
                league_stats_pew = df_pewniaki.groupby('Liga').agg(
                    Rozegrane=('Status', 'count'),
                    Trafione=('Status', lambda x: (x == 'WYGRANA').sum()),
                    Zysk=('Zysk/Strata (Flat 100)', 'sum')
                ).reset_index()
                league_stats_pew['Win Rate'] = (league_stats_pew['Trafione'] / league_stats_pew['Rozegrane']) * 100
                league_stats_pew = league_stats_pew.sort_values(by='Rozegrane', ascending=False)
                
                wszystkie_ligi = sorted(league_stats_pew['Liga'].dropna().unique().tolist())
                wybrane_ligi = st.multiselect(
                    "Wybierz konkretne ligi do zestawienia (pozostaw puste, aby widzieć ogólne Top 20 pod względem częstotliwości):",
                    options=wszystkie_ligi,
                    default=[],
                    key="knn_league_select"
                )
                
                if wybrane_ligi:
                    league_stats_pew = league_stats_pew[league_stats_pew['Liga'].isin(wybrane_ligi)]
                else:
                    league_stats_pew = league_stats_pew.head(20)
                
                fig_league_pew = px.bar(
                    league_stats_pew, 
                    x='Liga', 
                    y='Rozegrane', 
                    color='Win Rate',
                    color_continuous_scale=px.colors.diverging.RdYlGn,
                    hover_data=['Trafione', 'Win Rate', 'Zysk'],
                    labels={'Rozegrane': 'Liczba Typów', 'Win Rate': 'Skuteczność (%)'}
                )
                fig_league_pew.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_league_pew, use_container_width=True)
                
                # Tabela zagranych meczów w tym progu
                st.markdown(f"**Rozegrane mecze w tym progu ({prog_min}%-{prog_max}%)**")
                display_cols = ['Data_Rozegrania', 'Mecz', 'Liga', 'Typ_Modelu', 'Wynik_Rzeczywisty', 'Gole', 'Status', 'Kurs [Faworyt]', 'MAX_Szansa', 'Zysk/Strata (Flat 100)']
                if 'Gole' not in df_pewniaki.columns:
                    display_cols.remove('Gole')
                    
                def highlight_status(row):
                    if row.get('Status') == 'WYGRANA':
                        return ['background-color: rgba(46, 204, 113, 0.2)'] * len(row)
                    elif row.get('Status') == 'PRZEGRANA':
                        return ['background-color: rgba(231, 76, 60, 0.2)'] * len(row)
                    return [''] * len(row)
                    
                st.dataframe(df_pewniaki[display_cols].style.apply(highlight_status, axis=1), use_container_width=True)
            else:
                st.info(f"Brak w historii meczów o pewności w zakresie od {prog_min}% do {prog_max}%.")
            
            st.markdown("---")
            
            # WYKRES 2: Win Rate wg Miesięcy / Dni (Słupkowy)
            st.subheader("📅 Skuteczność Dziennie")
            daily_stats = df_valid.groupby('Data_Rozegrania').agg(
                Dzienny_Zysk=('Zysk/Strata (Flat 100)', 'sum'),
                Liczba_Typow=('Zysk/Strata (Flat 100)', 'count'),
                Trafione=('Status', lambda x: (x == 'WYGRANA').sum())
            ).reset_index()
            daily_stats['Win Rate'] = (daily_stats['Trafione'] / daily_stats['Liczba_Typow']) * 100
            
            fig_bar = px.bar(daily_stats, x='Data_Rozegrania', y='Dzienny_Zysk', 
                             color='Dzienny_Zysk', 
                             color_continuous_scale=px.colors.diverging.RdYlGn,
                             labels={'Dzienny_Zysk': 'Zysk/Strata', 'Data_Rozegrania': 'Data'},
                             hover_data=['Win Rate', 'Liczba_Typow', 'Trafione'])
            st.plotly_chart(fig_bar, use_container_width=True)
            
            # Podgląd Surowych Danych
            with st.expander("🔎 Pokaż surowe dane walidacyjne"):
                st.dataframe(df_valid)


elif menu == "📊 Skuteczność XGBoost (Historia)":
    st.title("Analiza Skuteczności XGBoost (Zwalidowana)")
    
    df_hist_xgb = load_validation_history_xgb()
    
    if df_hist_xgb.empty:
        st.warning("Brak zwalidowanej historii meczów XGBoost. Uruchom 'walidator_typow.py' po wygenerowaniu plików typów XGBoost.")
    else:
        df_hist_xgb['Data_Rozegrania_DT'] = pd.to_datetime(df_hist_xgb['Data_Rozegrania']).dt.date
        min_date_val_xgb = df_hist_xgb['Data_Rozegrania_DT'].min()
        max_date_val_xgb = df_hist_xgb['Data_Rozegrania_DT'].max()
        
        wczoraj_xgb = (datetime.now() - timedelta(days=1)).date()
        
        default_end_date_xgb = wczoraj_xgb if wczoraj_xgb < max_date_val_xgb else max_date_val_xgb
        if default_end_date_xgb < min_date_val_xgb:
            default_end_date_xgb = min_date_val_xgb
            
        st.markdown("### 📅 Filtr Daty (XGBoost)")
        date_range_xgb = st.date_input(
            "Wybierz zakres dat do analizy XGBoost:",
            value=(min_date_val_xgb, default_end_date_xgb),
            min_value=min_date_val_xgb,
            max_value=max_date_val_xgb,
            key="date_range_xgb"
        )
        
        if isinstance(date_range_xgb, tuple) and len(date_range_xgb) == 2:
            start_date_xgb, end_date_xgb = date_range_xgb
        elif isinstance(date_range_xgb, tuple) and len(date_range_xgb) == 1:
            start_date_xgb = end_date_xgb = date_range_xgb[0]
        else:
            start_date_xgb = end_date_xgb = date_range_xgb
            
        df_hist_filtered_xgb = df_hist_xgb[(df_hist_xgb['Data_Rozegrania_DT'] >= start_date_xgb) & (df_hist_xgb['Data_Rozegrania_DT'] <= end_date_xgb)].copy()
        df_valid_xgb = df_hist_filtered_xgb[df_hist_filtered_xgb['Status'].isin(["WYGRANA", "PRZEGRANA"])].copy()
        
        if df_valid_xgb.empty:
            st.warning("Brak rozliczonych zakładów XGBoost w historii dla tego zakresu dat.")
        else:
            total_matches_xgb = len(df_valid_xgb)
            wygrane_xgb = len(df_valid_xgb[df_valid_xgb['Status'] == 'WYGRANA'])
            win_rate_xgb = (wygrane_xgb / total_matches_xgb) * 100
            total_profit_xgb = df_valid_xgb['Zysk/Strata (Flat 100)'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Rozegrane/Zwalidowane Typy XGB", total_matches_xgb)
            col2.metric("Win Rate (%) XGB", f"{win_rate_xgb:.1f}%")
            col3.metric("Zysk / Strata (Flat 100j) XGB", f"{total_profit_xgb:.2f} j")
            
            st.markdown("---")
            st.subheader("🎯 Skuteczność dla wybranych progów pewności (XGBoost)")
            
            df_valid_xgb['MAX_Szansa'] = df_valid_xgb[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
            
            wybrany_zakres_xgb = st.slider("Wybierz zakres pewności algorytmu XGBoost (%):", min_value=65, max_value=100, value=(65, 100), step=1, key="xgb_slider_hist")
            prog_min_xgb, prog_max_xgb = wybrany_zakres_xgb
            
            df_pewniaki_xgb = df_valid_xgb[(df_valid_xgb['MAX_Szansa'] >= prog_min_xgb) & (df_valid_xgb['MAX_Szansa'] <= prog_max_xgb)].copy()
            
            if not df_pewniaki_xgb.empty:
                pew_total_xgb = len(df_pewniaki_xgb)
                pew_wygrane_xgb = len(df_pewniaki_xgb[df_pewniaki_xgb['Status'] == 'WYGRANA'])
                pew_winrate_xgb = (pew_wygrane_xgb / pew_total_xgb) * 100 if pew_total_xgb > 0 else 0
                pew_profit_xgb = df_pewniaki_xgb['Zysk/Strata (Flat 100)'].sum()
                
                c1, c2, c3 = st.columns(3)
                c1.metric(f"Liczba typów ({prog_min_xgb}%-{prog_max_xgb}%)", pew_total_xgb)
                c2.metric(f"Win Rate ({prog_min_xgb}%-{prog_max_xgb}%)", f"{pew_winrate_xgb:.1f}%", delta=f"{(pew_winrate_xgb - win_rate_xgb):.1f}% vs Ogół")
                c3.metric(f"Zysk / Strata ({prog_min_xgb}%-{prog_max_xgb}%)", f"{pew_profit_xgb:.2f} j")
                
                df_pewniaki_xgb = df_pewniaki_xgb.sort_values(by='Data_Rozegrania').reset_index(drop=True)
                df_pewniaki_xgb['Krzywa_Kapitalu_Pewniaki'] = df_pewniaki_xgb['Zysk/Strata (Flat 100)'].cumsum()
                
                fig_pew_roi_xgb = px.line(df_pewniaki_xgb, x=df_pewniaki_xgb.index, y='Krzywa_Kapitalu_Pewniaki', 
                                  hover_data=['Data_Rozegrania', 'Mecz', 'Zysk/Strata (Flat 100)', 'MAX_Szansa'],
                                  labels={"index": f"Zagrany typ XGB {prog_min_xgb}%-{prog_max_xgb}% (#)", "Krzywa_Kapitalu_Pewniaki": "Kapitał (j)"},
                                  template="plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white")
                fig_pew_roi_xgb.update_traces(line_color='#e74c3c')
                fig_pew_roi_xgb.add_hline(y=0, line_dash="dash", line_color="gray")
                st.plotly_chart(fig_pew_roi_xgb, use_container_width=True)
                
                st.markdown(f"#### 🌍 Skuteczność wg Lig (XGBoost: {prog_min_xgb}%-{prog_max_xgb}%)")
                league_stats_pew_xgb = df_pewniaki_xgb.groupby('Liga').agg(
                    Rozegrane=('Status', 'count'),
                    Trafione=('Status', lambda x: (x == 'WYGRANA').sum()),
                    Zysk=('Zysk/Strata (Flat 100)', 'sum')
                ).reset_index()
                league_stats_pew_xgb['Win Rate'] = (league_stats_pew_xgb['Trafione'] / league_stats_pew_xgb['Rozegrane']) * 100
                league_stats_pew_xgb = league_stats_pew_xgb.sort_values(by='Rozegrane', ascending=False)
                
                wszystkie_ligi_xgb = sorted(league_stats_pew_xgb['Liga'].dropna().unique().tolist())
                wybrane_ligi_xgb = st.multiselect(
                    "Wybierz konkretne ligi do zestawienia (pozostaw puste, aby widzieć ogólne Top 20 pod względem częstotliwości):",
                    options=wszystkie_ligi_xgb,
                    default=[],
                    key="xgb_league_select"
                )
                
                if wybrane_ligi_xgb:
                    league_stats_pew_xgb = league_stats_pew_xgb[league_stats_pew_xgb['Liga'].isin(wybrane_ligi_xgb)]
                else:
                    league_stats_pew_xgb = league_stats_pew_xgb.head(20)
                
                fig_league_pew_xgb = px.bar(
                    league_stats_pew_xgb, 
                    x='Liga', 
                    y='Rozegrane', 
                    color='Win Rate',
                    color_continuous_scale=px.colors.diverging.RdYlGn,
                    hover_data=['Trafione', 'Win Rate', 'Zysk'],
                    labels={'Rozegrane': 'Liczba Typów', 'Win Rate': 'Skuteczność (%)'}
                )
                fig_league_pew_xgb.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_league_pew_xgb, use_container_width=True)
                
                st.markdown(f"**Rozegrane mecze w tym progu ({prog_min_xgb}%-{prog_max_xgb}%)**")
                display_cols_xgb = ['Data_Rozegrania', 'Mecz', 'Liga', 'Typ_Modelu', 'Wynik_Rzeczywisty', 'Gole', 'Status', 'Kurs [Faworyt]', 'MAX_Szansa', 'Zysk/Strata (Flat 100)']
                if 'Gole' not in df_pewniaki_xgb.columns:
                    display_cols_xgb.remove('Gole')
                    
                def highlight_status_xgb(row):
                    if row.get('Status') == 'WYGRANA': return ['background-color: rgba(46, 204, 113, 0.2)'] * len(row)
                    elif row.get('Status') == 'PRZEGRANA': return ['background-color: rgba(231, 76, 60, 0.2)'] * len(row)
                    return [''] * len(row)
                    
                st.dataframe(df_pewniaki_xgb[display_cols_xgb].style.apply(highlight_status_xgb, axis=1), use_container_width=True)
            else:
                st.info(f"Brak w historii meczów o pewności w zakresie od {prog_min_xgb}% do {prog_max_xgb}%.")
            
            st.markdown("---")
            st.subheader("📅 Skuteczność Dziennie (XGBoost)")
            daily_stats_xgb = df_valid_xgb.groupby('Data_Rozegrania').agg(
                Dzienny_Zysk=('Zysk/Strata (Flat 100)', 'sum'),
                Liczba_Typow=('Zysk/Strata (Flat 100)', 'count'),
                Trafione=('Status', lambda x: (x == 'WYGRANA').sum())
            ).reset_index()
            daily_stats_xgb['Win Rate'] = (daily_stats_xgb['Trafione'] / daily_stats_xgb['Liczba_Typow']) * 100
            
            fig_bar_xgb = px.bar(daily_stats_xgb, x='Data_Rozegrania', y='Dzienny_Zysk', 
                             color='Dzienny_Zysk', 
                             color_continuous_scale=px.colors.diverging.RdYlGn,
                             labels={'Dzienny_Zysk': 'Zysk/Strata', 'Data_Rozegrania': 'Data'},
                             hover_data=['Win Rate', 'Liczba_Typow', 'Trafione'])
            st.plotly_chart(fig_bar_xgb, use_container_width=True)
            
            with st.expander("🔎 Pokaż surowe dane walidacyjne XGBoost"):
                st.dataframe(df_valid_xgb)


elif menu == "🧬 Dzisiejsze Typy Ensemble (KNN+XGB)":
    st.title("Nadchodzące spotkania — Predykcje Ensemble (KNN + XGBoost)")
    st.markdown("""
    > **Ensemble** łączy dwa modele: **KNN** (40% wagi) i **XGBoost skalibrowany** (60% wagi).  
    > Kolumna **Consensus** pokazuje czy oba modele zgadzają się co do wyniku — ✅ = silniejszy sygnał.
    """)

    wybrana_data_ens = st.date_input("Wybierz dzień z predykcjami:", datetime.now(), key="ens_date")
    date_str_ens = wybrana_data_ens.strftime("%Y-%m-%d")

    df_ens = load_today_predictions_ensemble(date_str_ens)

    if df_ens.empty:
        st.warning(
            f"Brak predykcji Ensemble na dzień {date_str_ens}.  \n"
            f"Uruchom: `python automatyczny_typer_ensemble.py --data {date_str_ens}`"
        )
    else:
        st.success(f"Załadowano {len(df_ens)} predykcji Ensemble na dzień {date_str_ens}.")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            min_szansa_ens = st.slider("Minimalna pewność Ensemble (%):", 33, 100, 65, key="ens_slider")
        with col_f2:
            tylko_zgodne = st.checkbox("Pokaż tylko mecze gdzie OBA modele są zgodne (✅)", value=False, key="ens_consensus")

        df_ens['_Max'] = df_ens[['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']].max(axis=1)
        df_ens_f = df_ens[df_ens['_Max'] >= min_szansa_ens].copy()
        if tylko_zgodne and 'Consensus' in df_ens_f.columns:
            df_ens_f = df_ens_f[df_ens_f['Consensus'].str.startswith('✅')]

        if df_ens_f.empty:
            st.info("Brak meczów spełniających wybrane kryteria.")
        else:
            # Metryki poglądowe
            count_zgodne   = df_ens_f['Consensus'].str.startswith('✅').sum() if 'Consensus' in df_ens_f.columns else 0
            count_rozbiezne = len(df_ens_f) - count_zgodne
            c1, c2, c3 = st.columns(3)
            c1.metric("Łącznie meczów", len(df_ens_f))
            c2.metric("✅ Oba zgodne", count_zgodne)
            c3.metric("⚠️ Rozbieżność", count_rozbiezne)

            def highlight_ensemble(row):
                consensus = str(row.get('Consensus', ''))
                val = max(
                    row.get('% Wygranej Gospodarza [1]', 0),
                    row.get('% Remisu [X]', 0),
                    row.get('% Wygranej Goscia [2]', 0)
                )
                # Fioletowy dla pełnej zgody + wysoka pewność
                if consensus.startswith('✅') and val >= 80:
                    return ['background-color: rgba(155, 89, 182, 0.35); font-weight:bold;'] * len(row)
                # Zielony dla zgodnych o niższej pewności
                if consensus.startswith('✅'):
                    return ['background-color: rgba(46, 204, 113, 0.2)'] * len(row)
                # Żółty dla rozbieżnych
                if val >= 65:
                    return ['background-color: rgba(241, 196, 15, 0.15)'] * len(row)
                return [''] * len(row)

            WARNING_LEAGUES_ENS = {
                'Brazil 1':     '⚠️ (Zalecana ostrożność)',
                'Australia 2':  '⚠️ (35% błędów)',
                'Germany 4':    '⚠️ (34% błędów)',
                'Bolivia 1':    '🔥 (Złota Liga: 100%)',
                'Scotland 1':   '🔥 (Złota Liga: 100%)',
                'Portugal 1':   '⭐ (Elita: 94%)',
                'China 1':      '⭐ (Elita: 93%)',
            }
            # Kolumny do wyświetlenia — bez wewnętrznych pomocniczych
            display_cols_ens = [c for c in df_ens_f.columns if c != '_Max']
            df_display_ens = df_ens_f[display_cols_ens].copy()
            if 'Liga' in df_display_ens.columns:
                df_display_ens['Liga'] = df_display_ens['Liga'].apply(
                    lambda x: f"{x} {WARNING_LEAGUES_ENS[x]}" if x in WARNING_LEAGUES_ENS else x
                )

            st.dataframe(
                df_display_ens.style.apply(highlight_ensemble, axis=1),
                use_container_width=True,
                height=600
            )

            with st.expander("📊 Szczegółowe predykcje per model (KNN vs XGB)"):
                st.markdown("Poniżej surowe prawdopodobieństwa każdego z modeli przed połączeniem w Ensemble:")
                detail_cols = ['Mecz', 'Liga', 'Kurs [Faworyt]',
                               'KNN_%1', 'KNN_%X', 'KNN_%2',
                               'XGB_%1', 'XGB_%X', 'XGB_%2',
                               'Consensus']
                detail_cols = [c for c in detail_cols if c in df_ens_f.columns]
                st.dataframe(df_ens_f[detail_cols], use_container_width=True)

elif menu == "📊 Skuteczność Ensemble (Historia)":
    st.title("Analiza Skuteczności Ensemble KNN+XGB (Zwalidowana)")
    st.markdown("""
    Sekcja analizuje historyczne wyniki predykcji modelu Ensemble.  
    Dane są dostępne po uruchomieniu `walidator_typow.py` dla plików `DZISIEJSZE_TYPY_ENSEMBLE_*.csv`.
    """)

    df_hist_ens = load_validation_history_ensemble()

    if df_hist_ens.empty:
        st.warning(
            "Brak zwalidowanej historii Ensemble.  \n"
            "Uruchom `walidator_typow.py` po wygenerowaniu plików `DZISIEJSZE_TYPY_ENSEMBLE_*.csv`."
        )
    else:
        df_hist_ens['Data_Rozegrania_DT'] = pd.to_datetime(df_hist_ens['Data_Rozegrania']).dt.date
        min_d_ens = df_hist_ens['Data_Rozegrania_DT'].min()
        max_d_ens = df_hist_ens['Data_Rozegrania_DT'].max()
        wczoraj_ens = (datetime.now() - timedelta(days=1)).date()
        default_end_ens = wczoraj_ens if wczoraj_ens < max_d_ens else max_d_ens
        if default_end_ens < min_d_ens:
            default_end_ens = min_d_ens

        st.markdown("### 📅 Filtr Daty (Ensemble)")
        date_range_ens = st.date_input(
            "Wybierz zakres dat:",
            value=(min_d_ens, default_end_ens),
            min_value=min_d_ens,
            max_value=max_d_ens,
            key="date_range_ens"
        )
        if isinstance(date_range_ens, tuple) and len(date_range_ens) == 2:
            s_ens, e_ens = date_range_ens
        else:
            s_ens = e_ens = date_range_ens if not isinstance(date_range_ens, tuple) else date_range_ens[0]

        df_hf_ens = df_hist_ens[
            (df_hist_ens['Data_Rozegrania_DT'] >= s_ens) &
            (df_hist_ens['Data_Rozegrania_DT'] <= e_ens)
        ].copy()
        df_v_ens = df_hf_ens[df_hf_ens['Status'].isin(['WYGRANA', 'PRZEGRANA'])].copy()

        if df_v_ens.empty:
            st.warning("Brak rozliczonych zakładów Ensemble w wybranym zakresie dat.")
        else:
            total_ens  = len(df_v_ens)
            wygr_ens   = (df_v_ens['Status'] == 'WYGRANA').sum()
            wr_ens     = wygr_ens / total_ens * 100
            profit_ens = df_v_ens['Zysk/Strata (Flat 100)'].sum()

            c1, c2, c3 = st.columns(3)
            c1.metric("Rozegrane typy Ensemble", total_ens)
            c2.metric("Win Rate Ensemble", f"{wr_ens:.1f}%")
            c3.metric("Zysk / Strata (Flat 100j)", f"{profit_ens:.2f} j")

            # Consensus split
            if 'Consensus' in df_v_ens.columns:
                st.markdown("---")
                st.subheader("🤝 Wyniki wg Consensus")
                c_zgod  = df_v_ens[df_v_ens['Consensus'].str.startswith('✅', na=False)]
                c_rozbz = df_v_ens[~df_v_ens['Consensus'].str.startswith('✅', na=False)]
                ca, cb = st.columns(2)
                with ca:
                    st.markdown("**✅ OBA MODELE ZGODNE**")
                    if len(c_zgod) > 0:
                        wr_zgod = (c_zgod['Status'] == 'WYGRANA').sum() / len(c_zgod) * 100
                        roi_zgod = c_zgod['Zysk/Strata (Flat 100)'].sum()
                        st.metric("Mecze", len(c_zgod))
                        st.metric("Win Rate", f"{wr_zgod:.1f}%", delta=f"{wr_zgod-wr_ens:+.1f}% vs ogół")
                        st.metric("ROI", f"{roi_zgod:.0f} j")
                    else:
                        st.info("Brak meczów z consensusem.")
                with cb:
                    st.markdown("**⚠️ RÓŻNICA MODELI**")
                    if len(c_rozbz) > 0:
                        wr_rozbz  = (c_rozbz['Status'] == 'WYGRANA').sum() / len(c_rozbz) * 100
                        roi_rozbz = c_rozbz['Zysk/Strata (Flat 100)'].sum()
                        st.metric("Mecze", len(c_rozbz))
                        st.metric("Win Rate", f"{wr_rozbz:.1f}%", delta=f"{wr_rozbz-wr_ens:+.1f}% vs ogół")
                        st.metric("ROI", f"{roi_rozbz:.0f} j")
                    else:
                        st.info("Brak meczów z rozbieżnością.")

            st.markdown("---")
            st.subheader("🎯 Skuteczność wg progu pewności (Ensemble)")
            df_v_ens['MAX_Szansa'] = df_v_ens[[
                '% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]'
            ]].max(axis=1)
            zakres_ens = st.slider(
                "Zakres pewności Ensemble (%):",
                min_value=50, max_value=100, value=(65, 100), step=1,
                key="ens_slider_hist"
            )
            p_min_ens, p_max_ens = zakres_ens
            df_pew_ens = df_v_ens[
                (df_v_ens['MAX_Szansa'] >= p_min_ens) &
                (df_v_ens['MAX_Szansa'] <= p_max_ens)
            ].copy()

            if not df_pew_ens.empty:
                pe_total  = len(df_pew_ens)
                pe_wygr   = (df_pew_ens['Status'] == 'WYGRANA').sum()
                pe_wr     = pe_wygr / pe_total * 100
                pe_profit = df_pew_ens['Zysk/Strata (Flat 100)'].sum()

                c1, c2, c3 = st.columns(3)
                c1.metric(f"Typów ({p_min_ens}%-{p_max_ens}%)", pe_total)
                c2.metric("Win Rate", f"{pe_wr:.1f}%", delta=f"{pe_wr - wr_ens:+.1f}% vs ogół")
                c3.metric("ROI", f"{pe_profit:.2f} j")

                df_pew_ens = df_pew_ens.sort_values('Data_Rozegrania').reset_index(drop=True)
                df_pew_ens['Krzywa_Kapitalu'] = df_pew_ens['Zysk/Strata (Flat 100)'].cumsum()

                fig_ens = px.line(
                    df_pew_ens, x=df_pew_ens.index, y='Krzywa_Kapitalu',
                    hover_data=['Data_Rozegrania', 'Mecz', 'Zysk/Strata (Flat 100)', 'MAX_Szansa'],
                    labels={"index": f"Typ ENS {p_min_ens}%-{p_max_ens}% (#)", "Krzywa_Kapitalu": "Kapitał (j)"},
                    template="plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white"
                )
                fig_ens.update_traces(line_color='#9b59b6')
                fig_ens.add_hline(y=0, line_dash="dash", line_color="gray")
                st.plotly_chart(fig_ens, use_container_width=True)

                # Tabela meczów
                st.markdown(f"**Mecze Ensemble w tym progu ({p_min_ens}%-{p_max_ens}%)**")
                dcols_ens = ['Data_Rozegrania', 'Mecz', 'Liga', 'Typ_Modelu', 'Consensus',
                             'Wynik_Rzeczywisty', 'Gole', 'Status',
                             'Kurs [Faworyt]', 'MAX_Szansa', 'Zysk/Strata (Flat 100)']
                dcols_ens = [c for c in dcols_ens if c in df_pew_ens.columns]

                def hl_ens_hist(row):
                    if row.get('Status') == 'WYGRANA':   return ['background-color: rgba(46, 204, 113, 0.2)'] * len(row)
                    elif row.get('Status') == 'PRZEGRANA': return ['background-color: rgba(231, 76, 60, 0.2)'] * len(row)
                    return [''] * len(row)

                st.dataframe(
                    df_pew_ens[dcols_ens].style.apply(hl_ens_hist, axis=1),
                    use_container_width=True
                )
            else:
                st.info(f"Brak meczów Ensemble w zakresie {p_min_ens}%-{p_max_ens}%.")

            st.markdown("---")
            st.subheader("📅 Skuteczność Dziennie (Ensemble)")
            daily_ens = df_v_ens.groupby('Data_Rozegrania').agg(
                Dzienny_Zysk=('Zysk/Strata (Flat 100)', 'sum'),
                Liczba_Typow=('Status', 'count'),
                Trafione=('Status', lambda x: (x == 'WYGRANA').sum())
            ).reset_index()
            daily_ens['Win Rate'] = daily_ens['Trafione'] / daily_ens['Liczba_Typow'] * 100

            fig_bar_ens = px.bar(
                daily_ens, x='Data_Rozegrania', y='Dzienny_Zysk',
                color='Dzienny_Zysk',
                color_continuous_scale=px.colors.diverging.RdYlGn,
                labels={'Dzienny_Zysk': 'Zysk/Strata', 'Data_Rozegrania': 'Data'},
                hover_data=['Win Rate', 'Liczba_Typow', 'Trafione']
            )
            st.plotly_chart(fig_bar_ens, use_container_width=True)

            with st.expander("🔎 Surowe dane walidacyjne Ensemble"):
                st.dataframe(df_v_ens)

            # ─────────────────────────────────────────────────────────────────
            # NOWE: Porównanie 3 modeli + tabela progów
            # ─────────────────────────────────────────────────────────────────
            st.markdown("---")
            st.subheader("⚖️ Porównanie KNN vs XGBoost vs Ensemble (od 2026-03-25)")

            import re as _re

            _s_str = s_ens.strftime('%Y-%m-%d')
            _e_str = e_ens.strftime('%Y-%m-%d')

            def _load_model_data(glob_pattern, excl_keyword=None):
                """Ładuje i scala pliki CSV dla danego modelu w zakresie dat z filtra."""
                files = sorted(glob.glob(os.path.join(DATA_DIR, glob_pattern)))
                result = []
                for f in files:
                    bn = os.path.basename(f)
                    if excl_keyword and excl_keyword in bn:
                        continue
                    m = _re.search(r'(\d{4}-\d{2}-\d{2})', bn)
                    if not m:
                        continue
                    d_str = m.group(1)
                    if not (_s_str <= d_str <= _e_str):
                        continue
                    result.append(f)
                if not result:
                    return pd.DataFrame()
                parts = []
                for f in result:
                    try:
                        d = pd.read_csv(f, sep=';', encoding='utf-8-sig')
                        d['Data_Rozegrania'] = _re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(f)).group(1)
                        parts.append(d)
                    except Exception:
                        pass
                return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

            df_knn_all = _load_model_data("ZWALIDOWANE_TYPY_2026-*.csv", excl_keyword="XGB")
            df_xgb_all = _load_model_data("ZWALIDOWANE_TYPY_XGB_2026-*.csv", excl_keyword="HISTORYCZNIE")
            df_ens_all = _load_model_data("ZWALIDOWANE_TYPY_ENSEMBLE_2026-*.csv")

            PROB_COLS = ['% Wygranej Gospodarza [1]', '% Wygranej Goscia [2]', '% Remisu [X]']

            def _build_threshold_row(df, label, prog):
                if df.empty:
                    return None
                df = df[df['Status'].isin(['WYGRANA', 'PRZEGRANA'])].copy()
                df['_max'] = df[PROB_COLS].max(axis=1)
                sub = df[df['_max'] >= prog]
                if len(sub) == 0:
                    return None
                w = (sub['Status'] == 'WYGRANA').sum()
                return {
                    'Model': label,
                    'Próg': f"{prog}%+",
                    'Mecze': len(sub),
                    'Trafione': int(w),
                    'Skuteczność (%)': round(w / len(sub) * 100, 1),
                    'Profit (flat 100)': round(sub['Zysk/Strata (Flat 100)'].sum(), 0),
                }

            progi = [50, 60, 65, 70, 75, 80, 85]
            modele = [
                (df_knn_all, "🟩 KNN"),
                (df_xgb_all, "🟥 XGBoost"),
                (df_ens_all, "🟣 Ensemble"),
            ]

            rows_comp = []
            for prog in progi:
                for df_m, lbl in modele:
                    r = _build_threshold_row(df_m, lbl, prog)
                    if r:
                        rows_comp.append(r)

            if rows_comp:
                df_comp = pd.DataFrame(rows_comp)

                # Pivot na wykres liniowy Skuteczność vs próg
                df_pivot = df_comp.pivot_table(
                    index='Próg', columns='Model', values='Skuteczność (%)', aggfunc='mean'
                ).reset_index()
                # Zachowaj kolejność progów
                prog_order = [f"{p}%+" for p in progi]
                df_pivot['_ord'] = df_pivot['Próg'].map({p: i for i, p in enumerate(prog_order)})
                df_pivot = df_pivot.sort_values('_ord').drop(columns=['_ord'])

                fig_comp = go.Figure()
                colors_map = {
                    '🟩 KNN': '#2ecc71',
                    '🟥 XGBoost': '#e74c3c',
                    '🟣 Ensemble': '#9b59b6',
                }
                for col in df_pivot.columns:
                    if col == 'Próg':
                        continue
                    fig_comp.add_trace(go.Scatter(
                        x=df_pivot['Próg'],
                        y=df_pivot[col],
                        mode='lines+markers',
                        name=col,
                        line=dict(color=colors_map.get(col, '#aaa'), width=3),
                        marker=dict(size=9),
                    ))
                fig_comp.add_hline(y=50, line_dash="dot", line_color="gray",
                                   annotation_text="50% (losowy)", annotation_position="bottom right")
                fig_comp.update_layout(
                    xaxis_title="Minimalny próg pewności modelu",
                    yaxis_title="Skuteczność (%)",
                    yaxis_range=[40, 100],
                    legend_title="Model",
                    height=420,
                    margin=dict(t=30),
                )
                st.plotly_chart(fig_comp, use_container_width=True)

                # Profit bar chart
                df_pivot_profit = df_comp.pivot_table(
                    index='Próg', columns='Model', values='Profit (flat 100)', aggfunc='sum'
                ).reset_index()
                df_pivot_profit['_ord'] = df_pivot_profit['Próg'].map({p: i for i, p in enumerate(prog_order)})
                df_pivot_profit = df_pivot_profit.sort_values('_ord').drop(columns=['_ord'])

                fig_profit = go.Figure()
                for col in df_pivot_profit.columns:
                    if col == 'Próg':
                        continue
                    fig_profit.add_trace(go.Bar(
                        x=df_pivot_profit['Próg'],
                        y=df_pivot_profit[col],
                        name=col,
                        marker_color=colors_map.get(col, '#aaa'),
                        opacity=0.85,
                    ))
                fig_profit.add_hline(y=0, line_dash="dash", line_color="white")
                fig_profit.update_layout(
                    barmode='group',
                    xaxis_title="Minimalny próg pewności",
                    yaxis_title="Profit skumulowany (flat 100j)",
                    legend_title="Model",
                    height=380,
                    margin=dict(t=30),
                )
                st.plotly_chart(fig_profit, use_container_width=True)

                # Tabela z pełnym zestawieniem
                st.markdown("#### 📋 Pełna tabela skuteczności wg progów")

                def _style_wr(val):
                    try:
                        v = float(val)
                    except Exception:
                        return ''
                    if v >= 80:
                        return 'background-color: rgba(46,204,113,0.35); font-weight:bold'
                    elif v >= 65:
                        return 'background-color: rgba(241,196,15,0.25)'
                    else:
                        return 'background-color: rgba(231,76,60,0.25)'

                def _style_profit(val):
                    try:
                        v = float(val)
                    except Exception:
                        return ''
                    return 'color: #2ecc71; font-weight:bold' if v > 0 else 'color: #e74c3c'

                styled_comp = (
                    df_comp.style
                    .map(_style_wr, subset=['Skuteczność (%)'])
                    .map(_style_profit, subset=['Profit (flat 100)'])
                    .format({'Skuteczność (%)': '{:.1f}%', 'Profit (flat 100)': '{:+.0f} j'})
                )
                st.dataframe(styled_comp, use_container_width=True, height=420)

                # Ensemble Consensus breakdown przy wybranym progu
                if not df_ens_all.empty and 'Consensus' in df_ens_all.columns:
                    st.markdown("---")
                    st.subheader("🤝 Ensemble — rozbicie wg Consensus i progu")
                    df_ens_v = df_ens_all[df_ens_all['Status'].isin(['WYGRANA', 'PRZEGRANA'])].copy()
                    df_ens_v['_max'] = df_ens_v[PROB_COLS].max(axis=1)
                    df_ens_v['_zgoda'] = df_ens_v['Consensus'].str.contains('OBA ZGODNE', na=False)

                    con_rows = []
                    for prog in progi:
                        for zgodne_val, lbl_c in [(True, "✅ OBA ZGODNE"), (False, "⚠️ RÓŻNICA")]:
                            sub = df_ens_v[(df_ens_v['_max'] >= prog) & (df_ens_v['_zgoda'] == zgodne_val)]
                            if len(sub) == 0:
                                continue
                            w = (sub['Status'] == 'WYGRANA').sum()
                            con_rows.append({
                                'Consensus': lbl_c,
                                'Próg': f"{prog}%+",
                                'Mecze': len(sub),
                                'Trafione': int(w),
                                'Skuteczność (%)': round(w / len(sub) * 100, 1),
                                'Profit': round(sub['Zysk/Strata (Flat 100)'].sum(), 0),
                            })

                    if con_rows:
                        df_con = pd.DataFrame(con_rows)
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown("**✅ OBA MODELE ZGODNE**")
                            sub_z = df_con[df_con['Consensus'] == '✅ OBA ZGODNE']
                            st.dataframe(
                                sub_z.drop(columns='Consensus').style
                                .map(_style_wr, subset=['Skuteczność (%)'])
                                .map(_style_profit, subset=['Profit'])
                                .format({'Skuteczność (%)': '{:.1f}%', 'Profit': '{:+.0f} j'}),
                                use_container_width=True, hide_index=True
                            )
                        with col_b:
                            st.markdown("**⚠️ RÓŻNICA MODELI**")
                            sub_r = df_con[df_con['Consensus'] == '⚠️ RÓŻNICA']
                            if not sub_r.empty:
                                st.dataframe(
                                    sub_r.drop(columns='Consensus').style
                                    .map(_style_wr, subset=['Skuteczność (%)'])
                                    .map(_style_profit, subset=['Profit'])
                                    .format({'Skuteczność (%)': '{:.1f}%', 'Profit': '{:+.0f} j'}),
                                    use_container_width=True, hide_index=True
                                )
                            else:
                                st.info("Brak meczów z rozbieżnością w zakresie.")
            else:
                st.info("Brak danych do porównania modeli w wybranym zakresie dat.")


elif menu == "⚽ Over/Under — Typy Bramkowe (Live)":
    st.title("⚽ Predykcje Over/Under — Rynki Bramkowe")
    st.markdown("""
    > Prognozy modelu XGBoost dla rynków **Over 1.5**, **Over 2.5** i **BTTS** (obie strzelą).  
    > Model uczony jest na tej samej bazie ~143k meczów co predyktor 1X2.  
    > Przed użyciem uruchom: `python automatyczny_typer_over_under.py`
    """)

    # ── Wybór daty ─────────────────────────────────────────────────────────
    wybrana_data_ou = st.date_input("Wybierz dzień z predykcjami O/U:", datetime.now(), key="ou_date")
    date_str_ou = wybrana_data_ou.strftime("%Y-%m-%d")

    df_ou = load_today_predictions_ou(date_str_ou)

    st.markdown("---")

    # ── Statystyki bazowe z całej historii ─────────────────────────────────
    with st.expander("📊 Statystyki historyczne bazy (~143k meczów) — kliknij aby rozwinąć", expanded=True):
        base_stats = load_ou_base_stats()
        if base_stats:
            bs1, bs2, bs3, bs4, bs5, bs6 = st.columns(6)
            bs1.metric("Mecze w bazie", f"{base_stats.get('total_mecze', 0):,}")
            bs2.metric("Over 0.5", f"{base_stats.get('over_05', 0)}%")
            bs3.metric("Over 1.5", f"{base_stats.get('over_15', 0)}%")
            bs4.metric("Over 2.5", f"{base_stats.get('over_25', 0)}%")
            bs5.metric("BTTS Obie strzelą", f"{base_stats.get('btts', 0)}%")
            bs6.metric("Śr. goli/mecz", f"{base_stats.get('srednia_goli', 0)}")

            # Wykres rozkładu sumy goli
            dist = base_stats.get('dist')
            if dist is not None and len(dist) > 0:
                dist_df = dist.reset_index()
                dist_df.columns = ['Suma goli', 'Liczba meczów']
                dist_df = dist_df[dist_df['Suma goli'] <= 10]  # ogranicz do 0-10
                dist_df['% meczów'] = (dist_df['Liczba meczów'] / dist_df['Liczba meczów'].sum() * 100).round(1)
                fig_dist = px.bar(
                    dist_df, x='Suma goli', y='Liczba meczów',
                    text='% meczów',
                    color='Suma goli',
                    color_continuous_scale='Blues',
                    labels={'Suma goli': 'Łączna liczba goli w meczu', 'Liczba meczów': 'Liczba meczów'},
                    title='Rozkład sumy goli w meczu (baza historyczna)'
                )
                fig_dist.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_dist.update_layout(showlegend=False, height=350, margin=dict(t=40, b=20))
                # Linie progów
                for threshold, color, label in [(1.5, 'orange', 'Over 1.5'), (2.5, 'red', 'Over 2.5')]:
                    fig_dist.add_vline(x=threshold, line_dash="dash", line_color=color,
                                      annotation_text=label, annotation_position="top right")
                st.plotly_chart(fig_dist, use_container_width=True)
        else:
            st.info("Nie można załadować statystyk bazowych. Sprawdź ścieżkę do fctables_data.csv.")

    st.markdown("---")

    # ── Predykcje dnia ────────────────────────────────────────────────────
    if df_ou.empty:
        st.warning(
            f"Brak predykcji Over/Under na dzień **{date_str_ou}**.  \n"
            f"Uruchom: `python automatyczny_typer_over_under.py --data {date_str_ou}`"
        )
    else:
        st.success(f"Załadowano {len(df_ou)} predykcji O/U na dzień **{date_str_ou}**.")

        # Filtry
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            prog_o15 = st.slider("Min. % Over 1.5:", 40, 95, 60, key="ou_o15")
        with col_f2:
            prog_o25 = st.slider("Min. % Over 2.5:", 40, 95, 55, key="ou_o25")
        with col_f3:
            prog_btts = st.slider("Min. % BTTS:", 40, 95, 55, key="ou_btts")

        # Filtry progowe — opcjonalne (AND)
        filtruj = st.checkbox("Filtruj — pokaż tylko mecze przekraczające KTÓRYKOLWIEK próg", value=True, key="ou_filtr")

        df_display_ou = df_ou.copy()
        if filtruj:
            mask = (
                (df_display_ou['% Over 1.5'] >= prog_o15) |
                (df_display_ou['% Over 2.5'] >= prog_o25) |
                (df_display_ou['% BTTS']     >= prog_btts)
            )
            df_display_ou = df_display_ou[mask].copy()

        # Metryki podsumowujące
        if not df_display_ou.empty:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Meczów spełniających kryteria", len(df_display_ou))
            m2.metric("Śr. szansa Over 1.5", f"{df_display_ou['% Over 1.5'].mean():.1f}%")
            m3.metric("Śr. szansa Over 2.5", f"{df_display_ou['% Over 2.5'].mean():.1f}%")
            m4.metric("Śr. szansa BTTS",     f"{df_display_ou['% BTTS'].mean():.1f}%")

        st.markdown("---")

        # Kolorowanie tabeli
        def highlight_ou(row):
            o15  = row.get('% Over 1.5', 0)
            o25  = row.get('% Over 2.5', 0)
            btts = row.get('% BTTS', 0)
            max_val = max(o15, o25, btts)
            if max_val >= 80:
                return ['background-color: rgba(46, 204, 113, 0.35); font-weight:bold;'] * len(row)
            elif max_val >= 65:
                return ['background-color: rgba(241, 196, 15, 0.2)'] * len(row)
            return [''] * len(row)

        if df_display_ou.empty:
            st.info("Brak meczów spełniających wybrane progi. Obniż suwaki.")
        else:
            st.subheader(f"🎯 Typy Over/Under — {date_str_ou}")
            st.dataframe(
                df_display_ou.style.apply(highlight_ou, axis=1),
                use_container_width=True,
                height=550
            )

        # Sekcja BTTS osobno
        st.markdown("---")
        st.subheader("🔵 Analiza BTTS (Obie Strzelą)")
        col_b1, col_b2 = st.columns(2)

        df_btts_high = df_ou[df_ou['% BTTS'] >= 65].sort_values('% BTTS', ascending=False) if not df_ou.empty else pd.DataFrame()
        df_ou25_high = df_ou[df_ou['% Over 2.5'] >= 65].sort_values('% Over 2.5', ascending=False) if not df_ou.empty else pd.DataFrame()

        with col_b1:
            st.markdown(f"**BTTS ≥ 65% ({len(df_btts_high)} meczów)**")
            if not df_btts_high.empty:
                st.dataframe(
                    df_btts_high[['Mecz', 'Liga', '% BTTS', '% Over 1.5', '% Over 2.5']],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Brak meczów BTTS ≥ 65%.")

        with col_b2:
            st.markdown(f"**Over 2.5 ≥ 65% ({len(df_ou25_high)} meczów)**")
            if not df_ou25_high.empty:
                st.dataframe(
                    df_ou25_high[['Mecz', 'Liga', '% Over 2.5', '% Over 1.5', '% BTTS']],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Brak meczów Over 2.5 ≥ 65%.")

        # Scatter plot — Over 1.5 vs Over 2.5
        if not df_ou.empty and len(df_ou) > 1:
            st.markdown("---")
            st.subheader("📈 Mapa prawdopodobieństw (Over 1.5 vs Over 2.5)")
            fig_scatter = px.scatter(
                df_ou,
                x='% Over 1.5',
                y='% Over 2.5',
                color='% BTTS',
                size='% BTTS',
                hover_data=['Mecz', 'Liga', 'Kurs [Faworyt]', 'Sugestia_OU'],
                color_continuous_scale='RdYlGn',
                labels={
                    '% Over 1.5': 'Szansa Over 1.5 (%)',
                    '% Over 2.5': 'Szansa Over 2.5 (%)',
                    '% BTTS': 'BTTS (%)',
                },
                title='Rozkład predykcji Over/Under (rozmiar = szansa BTTS)'
            )
            fig_scatter.add_hline(y=60, line_dash="dash", line_color="gray",
                                  annotation_text="60% próg Over 2.5")
            fig_scatter.add_vline(x=70, line_dash="dash", line_color="lightgray",
                                  annotation_text="70% próg Over 1.5")
            fig_scatter.update_layout(height=450, margin=dict(t=50))
            st.plotly_chart(fig_scatter, use_container_width=True)

elif menu == "📊 Skuteczność Over/Under (Historia)":
    st.title("Analiza Skuteczności Over/Under (Zwalidowana)")
    st.markdown("""
    Sekcja analizuje historyczne wyniki predykcji rynków Over 1.5, Over 2.5 oraz BTTS.  
    Dane wynikają z walidacji faktycznych wyników i kursów orientacyjnych wyliczonych w `walidator_ou.py`.
    """)

    df_hist_ou = load_ou_validation_history()

    if df_hist_ou.empty:
        st.warning(
            "Brak zwalidowanej historii O/U.  \n"
            "Uruchom skrypt systemu, aby wczytać wczorajsze/stare wyniki do `ZWALIDOWANE_TYPY_OU_*.csv`."
        )
    else:
        df_hist_ou['Data_Rozegrania_DT'] = pd.to_datetime(df_hist_ou['Data_Rozegrania']).dt.date
        min_d_ou = df_hist_ou['Data_Rozegrania_DT'].min()
        max_d_ou = df_hist_ou['Data_Rozegrania_DT'].max()
        wczoraj_ou = (datetime.now() - timedelta(days=1)).date()
        default_end_ou = wczoraj_ou if wczoraj_ou < max_d_ou else max_d_ou
        if default_end_ou < min_d_ou:
            default_end_ou = min_d_ou

        st.markdown("### 📅 Filtr Daty (Over/Under)")
        date_range_ou = st.date_input(
            "Wybierz zakres dat:",
            value=(min_d_ou, default_end_ou),
            min_value=min_d_ou,
            max_value=max_d_ou,
            key="date_range_ou"
        )
        if isinstance(date_range_ou, tuple) and len(date_range_ou) == 2:
            s_ou, e_ou = date_range_ou
        else:
            s_ou = e_ou = date_range_ou if not isinstance(date_range_ou, tuple) else date_range_ou[0]

        df_v_ou = df_hist_ou[
            (df_hist_ou['Data_Rozegrania_DT'] >= s_ou) &
            (df_hist_ou['Data_Rozegrania_DT'] <= e_ou)
        ].copy()

        if df_v_ou.empty:
            st.warning("Brak zwalidowanych meczów O/U w wybranym zakresie dat.")
        else:
            rynek_ou = st.radio("Wybierz rynek do analizy:", ["Over 1.5", "Over 2.5", "BTTS"], horizontal=True)

            if rynek_ou == "Over 1.5":
                col_status = 'Status_Over_15'
                col_profit = 'Zysk_Over_15'
                col_prob = '% Over 1.5'
            elif rynek_ou == "Over 2.5":
                col_status = 'Status_Over_25'
                col_profit = 'Zysk_Over_25'
                col_prob = '% Over 2.5'
            else:
                col_status = 'Status_BTTS'
                col_profit = 'Zysk_BTTS'
                col_prob = '% BTTS'

            # Bierzemy tylko te mecze, w których algorytm zdecydował się "zagrać" (np. probability >= 50) i znamy wynik
            # W walidatorze takie mecze mają status "WYGRANA" lub "PRZEGRANA"
            df_rynek = df_v_ou[df_v_ou[col_status].isin(['WYGRANA', 'PRZEGRANA'])].copy()

            if df_rynek.empty:
                st.info(f"Brak zrealizowanych zakładów dla rynku {rynek_ou} w tym czasie.")
            else:
                total_ou = len(df_rynek)
                wygr_ou  = (df_rynek[col_status] == 'WYGRANA').sum()
                wr_ou    = (wygr_ou / total_ou) * 100
                profit_ou= df_rynek[col_profit].sum()

                c1, c2, c3 = st.columns(3)
                c1.metric(f"Mecze zagrane (Model ≥50%)", total_ou)
                c2.metric(f"Win Rate dla {rynek_ou}", f"{wr_ou:.1f}%")
                c3.metric(f"Profit (flat 100j)", f"{profit_ou:+.1f} j")

                st.markdown("---")
                st.subheader(f"🎯 Symulacja wyższego progu wejścia ({rynek_ou})")
                prog_min_ou = st.slider(f"Zagraj mecz TYLKO jeśli pewność predykcji {rynek_ou} wynosi minimum (%):", 50, 100, 60, step=1, key="prog_hist_ou")
                
                df_pew_ou = df_rynek[df_rynek[col_prob] >= prog_min_ou].copy()

                if not df_pew_ou.empty:
                    p_tot = len(df_pew_ou)
                    p_win = (df_pew_ou[col_status] == 'WYGRANA').sum()
                    p_wr  = (p_win / p_tot) * 100
                    p_prof= df_pew_ou[col_profit].sum()

                    pc1, pc2, pc3 = st.columns(3)
                    pc1.metric(f"Mecze po filtrze ({prog_min_ou}%+)", p_tot)
                    pc2.metric("Zoptymalizowany Win Rate", f"{p_wr:.1f}%", delta=f"{p_wr - wr_ou:+.1f}% vs bazowy (50%)")
                    pc3.metric("Zoptymalizowany Profit", f"{p_prof:+.1f} j")

                    # Wykres kapitału
                    df_pew_ou = df_pew_ou.sort_values(by='Data_Rozegrania').reset_index(drop=True)
                    df_pew_ou['Krzywa'] = df_pew_ou[col_profit].cumsum()
                    
                    fig_ou = px.line(
                        df_pew_ou, x=df_pew_ou.index, y='Krzywa',
                        hover_data=['Data_Rozegrania', 'Mecz', col_profit, col_prob, 'Wynik_Gole'],
                        labels={"index": f"Zagrany typ ({prog_min_ou}%+) #", "Krzywa": "Kapitał (j)"},
                        template="plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white"
                    )
                    
                    color_marker = '#f39c12' if rynek_ou == 'Over 1.5' else ('#e74c3c' if rynek_ou == 'Over 2.5' else '#3498db')
                    fig_ou.update_traces(line_color=color_marker)
                    fig_ou.add_hline(y=0, line_dash="dash", line_color="gray")
                    st.plotly_chart(fig_ou, use_container_width=True)
                    
                    with st.expander(f"🔎 Surowa lista zagranych meczów na {rynek_ou}"):
                        cols_to_disp = ['Data_Rozegrania', 'Mecz', 'Liga', col_prob, 'Wynik_Gole', col_status, col_profit]
                        
                        def hl_rynek(row):
                            if row.get(col_status) == 'WYGRANA':
                                return ['background-color: rgba(46, 204, 113, 0.2)'] * len(row)
                            elif row.get(col_status) == 'PRZEGRANA':
                                return ['background-color: rgba(231, 76, 60, 0.2)'] * len(row)
                            return [''] * len(row)
                            
                        st.dataframe(df_pew_ou[cols_to_disp].style.apply(hl_rynek, axis=1), use_container_width=True)
                else:
                    st.info(f"Brak meczów z {rynek_ou} o pewności >= {prog_min_ou}%.")

        # --- DODANA SEKCJA: ZESTAWIENIE LIG Z BAZY HISTORYCZNEJ ---
        st.markdown("---")
        st.subheader("📚 Zestawienie Lig z Potężnej Bazy Historycznej (Over 1.5)")
        st.markdown("Statystyki wygenerowane na podstawie rzeczywistych wyników ze wszystkich przypisanych meczów zgromadzonych w bazowym archiwum (`fctables_data.csv`).")
        
        df_lig_ou = load_league_stats_ou_db()
        
        if df_lig_ou.empty:
            st.info("Brak danych lub plik bazy fctables_data.csv nie istnieje.")
        else:
            lc1, lc2, lc3 = st.columns(3)
            with lc1:
                min_meczy = st.slider("Minimalna liczba rozegranych meczów na ligę:", min_value=10, max_value=2000, value=100, step=10, key="ou_lig_min_meczy")
            with lc2:
                min_o15 = st.slider("Szukaj lig z % Over 1.5 większym lub równym:", min_value=40, max_value=100, value=75, step=1, key="ou_lig_min_o15")
            with lc3:
                all_leagues_ou = sorted(df_lig_ou['Liga'].unique())
                wyb_ligi_ou = st.multiselect("Wyszukaj / filtruj konkretne ligi:", options=all_leagues_ou, default=[], key="ou_lig_szukaj")
                
            df_lig_filtered = df_lig_ou[df_lig_ou['Mecze'] >= min_meczy].copy()
            df_lig_filtered = df_lig_filtered[df_lig_filtered['% Over 1.5'] >= min_o15]
            
            if wyb_ligi_ou:
                df_lig_filtered = df_lig_filtered[df_lig_filtered['Liga'].isin(wyb_ligi_ou)]
                
            df_lig_filtered = df_lig_filtered.sort_values(by='% Over 1.5', ascending=False).reset_index(drop=True)
            
            st.markdown(f"Znaleziono **{len(df_lig_filtered)}** lig spełniających kryteria.")
            
            def style_o15(val):
                try:
                    if val >= 80: return 'background-color: rgba(46, 204, 113, 0.3)'
                    elif val >= 70: return 'background-color: rgba(241, 196, 15, 0.2)'
                    else: return 'background-color: rgba(231, 76, 60, 0.3)'
                except: return ''
                
            st.dataframe(
                df_lig_filtered.style.map(style_o15, subset=['% Over 1.5', '% Over 2.5', '% BTTS']),
                use_container_width=True, height=400
            )
            
            if not df_lig_filtered.empty:
                fig_lig_ou = px.bar(
                    df_lig_filtered.head(30), 
                    x='Liga', y='% Over 1.5', 
                    color='% Over 1.5', 
                    color_continuous_scale='RdYlGn',
                    hover_data=['Mecze', '% Over 2.5', '% BTTS', 'Śr. Goli'],
                    title="Top Ligi pod względem % Over 1.5 (max 30 na wykresie)"
                )
                fig_lig_ou.update_layout(xaxis_tickangle=-45)
                fig_lig_ou.add_hline(y=70, line_dash="dash", line_color="gray", annotation_text="Próg 70%")
                st.plotly_chart(fig_lig_ou, use_container_width=True)

elif menu == "🏆 Ślepy Test XGBoost (Eksperymentalne)":
    st.title("Wyniki ślepego testu modelu XGBoost na historii")
    
    file_path = os.path.join(DATA_DIR, "ZWALIDOWANE_TYPY_XGB_HISTORYCZNIE.csv")
    if not os.path.exists(file_path):
        st.warning("Brak pliku z historią XGBoost. Należy uruchomić skrypt 'skrypt_gui_xgboost.py' generujący plik w tle.")
    else:
        df_xgb = pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
        st.success(f"Załadowano {len(df_xgb)} historycznych meczów, o których XGBoost nie miał pojęcia w trakcie uczenia, a przypisał im >80% pewności.")
        
        total = len(df_xgb)
        wygrane = len(df_xgb[df_xgb['Status'] == 'WYGRANA'])
        win_rate = (wygrane / total) * 100 if total > 0 else 0
        profit = df_xgb['Zysk/Strata (Flat 100)'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Liczba pewniaków", total)
        c2.metric("Skuteczność (Win Rate)", f"{win_rate:.1f}%")
        c3.metric("Zysk / Strata (Flat 100)", f"{profit:.2f} j")
        
        df_xgb['Krzywa'] = df_xgb['Zysk/Strata (Flat 100)'].cumsum()
        fig_xgb = px.line(df_xgb, x=df_xgb.index, y='Krzywa', hover_data=['Data_Rozegrania', 'Mecz', 'Zysk/Strata (Flat 100)', 'MAX_Szansa'],
                          labels={"index": "Kolejny wytypowany mecz z historii (#)", "Krzywa": "Zysk skumulowany (j)"},
                          template="plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white")
        fig_xgb.update_traces(line_color='#e74c3c')
        fig_xgb.add_hline(y=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_xgb, use_container_width=True)
        
        st.markdown("**Pełny wykaz 1296 meczów wyłapanych przez XGBoost:**")
        
        display_cols = ['Data_Rozegrania', 'Mecz', 'Liga', 'Typ_Modelu', 'Wynik_Rzeczywisty', 'Gole', 'Status', 'Kurs [Faworyt]', 'MAX_Szansa', 'Zysk/Strata (Flat 100)']
        
        try:
            df_xgb['Data_Rozegrania_Format'] = pd.to_datetime(df_xgb['Data_Rozegrania'], dayfirst=True)
            df_xgb = df_xgb.sort_values(by='Data_Rozegrania_Format', ascending=False)
        except Exception:
            pass
            
        def highlight_bg(row):
            if row.get('Status') == 'WYGRANA': return ['background-color: rgba(46, 204, 113, 0.2)'] * len(row)
            elif row.get('Status') == 'PRZEGRANA': return ['background-color: rgba(231, 76, 60, 0.2)'] * len(row)
            return [''] * len(row)
                
        st.dataframe(df_xgb[display_cols].style.apply(highlight_bg, axis=1), use_container_width=True, height=600)
