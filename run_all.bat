@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "LOG=pipeline.log"
set "START_TIME=%time%"

echo ================================================================
echo   AI FRAUD DETECTION - TRAIN ^> EVALUATE ^> TEST ^> API
echo ================================================================
echo Start time: %START_TIME%
echo Log file:   %cd%\%LOG%
echo.
echo [%date% %time%] START > "%LOG%"

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found in PATH.
  goto :failed
)

if /i "%~1"=="resume" (
  if not "%~2"=="" (
    set "RESUME_LIMIT=--max-rows %~2"
    echo Mode: resume existing model, evaluate %~2 rows
  ) else (
    set "RESUME_LIMIT="
    echo Mode: resume existing model, evaluate full test dataset
  )
  echo.
  call :check_file "backend\artifacts\fraud_model.joblib"
  if errorlevel 1 goto :failed
  call :check_file "backend\artifacts\feature_schema.json"
  if errorlevel 1 goto :failed
  call :step "3/5" "Evaluating existing model" "python -u scripts\evaluate_model.py %RESUME_LIMIT%"
  if errorlevel 1 goto :failed
  call :step "4/5" "Running automated tests" "python -m pytest -q"
  if errorlevel 1 goto :failed
  call :step "5/6" "Benchmarking models" "python -u scripts\benchmark_models.py %RESUME_LIMIT%"
  if errorlevel 1 goto :failed
  goto :start_api
)

if not "%~1"=="" (
  for /f "delims=0123456789" %%A in ("%~1") do set "INVALID=%%A"
  if defined INVALID (
    echo [ERROR] Row limit must be a positive integer, for example: run_all.bat 50000
    goto :failed
  )
  if "%~1"=="0" (
    echo [ERROR] Row limit must be greater than zero.
    goto :failed
  )
  set "LIMIT=--max-rows %~1"
  echo Mode: sample with %~1 rows from each Kaggle CSV
) else (
  set "LIMIT="
  echo Mode: full Kaggle dataset
)
echo.

call :step "1/5" "Installing Python requirements" "python -m pip install -r requirements.txt"
if errorlevel 1 goto :failed

call :step "2/5" "Training model" "python scripts\train_model.py %LIMIT%"
if errorlevel 1 goto :failed
call :check_file "backend\artifacts\fraud_model.joblib"
if errorlevel 1 goto :failed
call :check_file "backend\artifacts\feature_schema.json"
if errorlevel 1 goto :failed
call :check_file "backend\artifacts\thresholds.json"
if errorlevel 1 goto :failed

call :step "3/5" "Evaluating model" "python -u scripts\evaluate_model.py %LIMIT%"
if errorlevel 1 goto :failed

call :step "4/5" "Running automated tests" "python -m pytest -q"
if errorlevel 1 goto :failed

call :step "5/6" "Benchmarking models" "python -u scripts\benchmark_models.py %LIMIT%"
if errorlevel 1 goto :failed

:start_api
echo.
echo [6/6] Starting FastAPI server...
echo API docs: http://localhost:8000/docs
echo Health:   http://localhost:8000/health
start "Fraud Detection API" /b cmd /c "python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 >> pipeline.log 2>&1"
timeout /t 3 /nobreak >nul
curl --fail --silent http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
  echo [WARNING] API did not answer yet. Check pipeline.log.
) else (
  echo [OK] API is running and health check passed.
)

echo.
echo ================================================================
echo   COMPLETED
echo   Finished: %date% %time%
echo   Reports:  backend\artifacts\metrics.json
echo   Log:      %cd%\%LOG%
echo ================================================================
goto :end

:step
echo.
echo [%~1] %~2
echo Command: %~3
echo [%date% %time%] %~1 %~2 >> "%LOG%"
call %~3
if errorlevel 1 (
  echo [ERROR] %~2 failed. See pipeline.log.
  exit /b 1
)
echo [OK] %~2 completed.
exit /b 0

:check_file
if not exist "%~1" (
  echo [ERROR] Required artifact missing: %~1
  exit /b 1
)
echo [OK] Artifact found: %~1
exit /b 0

:failed
echo.
echo ================================================================
echo   PIPELINE FAILED
echo   Review: %cd%\%LOG%
echo ================================================================
pause
exit /b 1

:end
endlocal
