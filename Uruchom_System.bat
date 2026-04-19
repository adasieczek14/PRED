@echo off
chcp 65001 >nul
echo ===================================================
echo   SYSTEM TYPOWANIA AI — v3.0 (Ensemble + O/U + Smart Money)
echo   Potok: KNN / XGBoost / ENSEMBLE / OVER-UNDER
echo ===================================================
echo.

echo [1/7] GENEROWANIE TYPOW (KNN)...
python automatyczny_typer.py
if %errorlevel% neq 0 (
    echo [BLAD] automatyczny_typer.py zakonczony z bledem! Kontynuuje...
)
echo.

echo [2/7] GENEROWANIE TYPOW (XGBoost skalibrowany)...
python automatyczny_typer_xgb.py
if %errorlevel% neq 0 (
    echo [BLAD] automatyczny_typer_xgb.py zakonczony z bledem! Kontynuuje...
)
echo.

echo [3/7] GENEROWANIE TYPOW ENSEMBLE (KNN 40%% + XGBoost 60%%)...
python automatyczny_typer_ensemble.py
if %errorlevel% neq 0 (
    echo [BLAD] automatyczny_typer_ensemble.py zakonczony z bledem! Kontynuuje...
)
echo.

echo [4/7] GENEROWANIE TYPOW OVER/UNDER (1.5 / 2.5 / BTTS)...
python automatyczny_typer_over_under.py
if %errorlevel% neq 0 (
    echo [BLAD] automatyczny_typer_over_under.py zakonczony z bledem! Kontynuuje...
)
echo.

echo [5/7] WALIDACJA WCZORAJSZYCH TYPOW (Prawdziwe wyniki)...
echo       (Waliduje pliki: KNN, XGBoost, Ensemble ORAZ Over/Under)
python walidator_typow.py
if %errorlevel% neq 0 (
    echo [BLAD] walidator_typow.py zakonczony z bledem! Kontynuuje...
)
python walidator_ou.py
if %errorlevel% neq 0 (
    echo [BLAD] walidator_ou.py zakonczony z bledem! Kontynuuje...
)
echo.

echo [6/7] SLEDENIE KURSOW (Smart Money / Dropping Odds)...
python tropiciel_kursow.py
if %errorlevel% neq 0 (
    echo [BLAD] tropiciel_kursow.py zakonczony z bledem! Kontynuuje...
)
echo.

echo [OPT] Optymalizacja progu wejscia (raz w tygodniu)...
python optymalizator_progu.py
if %errorlevel% neq 0 (
    echo [BLAD] optymalizator_progu.py zakonczony z bledem! Kontynuuje...
)
echo.

echo [UPD] Aktualizacja bazy treningowej o nowe mecze...
python aktualizuj_baze_treningowa.py
if %errorlevel% neq 0 (
    echo [BLAD] aktualizuj_baze_treningowa.py zakonczony z bledem! Kontynuuje...
)
echo.

echo [7/7] URUCHAMIANIE PANELU STREAMLIT...
echo Prosze czekac - okno przegladarki otworzy sie automatycznie.
echo Nowa zakladka: "Over/Under - Typy Bramkowe" (Over 1.5 / 2.5 / BTTS)
echo Aby zatrzymac panel wcisnij Ctrl+C lub zamknij to okno.
echo.
streamlit run dashboard.py

pause
