@echo off
cd /d "%~dp0"
title AlumnusCare - Generador de Solicitudes
echo ============================================================
echo    AlumnusCare - Generador de Solicitudes
echo ------------------------------------------------------------
echo    Se abrira solo en tu navegador en unos segundos.
echo    NO cierres esta ventana negra mientras uses la app.
echo    Para apagar el programa, cierra esta ventana.
echo ============================================================
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless=false
pause
