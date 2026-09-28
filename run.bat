@echo off
REM Launcher for the Autonomous Trailer Director.
REM   run.bat                 -> CLI passthrough
REM   run.bat ui              -> launch the Streamlit web UI
REM   run.bat test            -> run the test suite
REM
REM Only ROOT goes on PYTHONPATH. Adding src\ would shadow the stdlib
REM `logging` module with src\logging\, breaking every interpreter that
REM imports logging (streamlit, pytest). run.py / streamlit_app.py each
REM set up their own paths.
set "ROOT=%~dp0"
set "PYTHONPATH=%ROOT%"

if /I "%~1"=="ui" goto :ui
if /I "%~1"=="test" goto :test

python "%ROOT%run.py" %*
goto :eof

:ui
python -m streamlit run "%ROOT%streamlit_app.py" %2 %3 %4
goto :eof

:test
REM tests/test_invariants.py needs the optional `hypothesis` package. Skip it
REM cleanly when that extra is not installed rather than failing collection.
python -c "import hypothesis" 2>nul
if errorlevel 1 (
  echo Skipping tests\test_invariants.py - optional dependency 'hypothesis' not installed.
  python -m pytest tests/ -q --ignore=tests/test_invariants.py
) else (
  python -m pytest tests/ -q
)
goto :eof
