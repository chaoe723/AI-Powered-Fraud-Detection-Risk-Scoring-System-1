@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "LOG=tuned_pipeline.log"
set "LIMIT="
set "MODE=%~1"
set "ARG2=%~2"
if "%MODE%"=="" set "MODE=full"

if /i "%MODE%"=="help" goto help
if /i "%MODE%"=="setup" goto setup
if /i "%MODE%"=="quick" (set "LIMIT=--max-rows 5000"& goto quick)
if /i "%MODE%"=="full" goto full
if /i "%MODE%"=="resume" goto resume
if /i "%MODE%"=="train" goto train
if /i "%MODE%"=="evaluate" goto evaluate_only
if /i "%MODE%"=="benchmark" goto benchmark
if /i "%MODE%"=="serve" goto serve
set "ROWS=%MODE%"
call :validate_rows
if errorlevel 1 goto failed_args
set "LIMIT=--max-rows %ROWS%"
goto standard

:banner
echo ================================================================
echo   TUNED FRAUD PIPELINE v5
echo   temporal split ^| stateful history ^| visible progress
echo ================================================================
exit /b 0

:setup
call :banner
call :start_log "SETUP"
call :run_step "1/1" "Installing requirements" "python -m pip install -r requirements.txt"
if errorlevel 1 goto failed
goto completed

:quick
call :banner
echo Mode: quick validation ^(5,000 rows; no install, no benchmark, no API^)
call :start_log "QUICK"
call :check_dependencies
if errorlevel 1 goto failed_dependencies
if exist "backend\artifacts\fraud_model.joblib" (
  echo [1/4] Reusing existing model for quick validation.
) else (
  call :run_step "1/4" "Training a quick model" "python -u scripts\train_model.py %LIMIT%"
  if errorlevel 1 goto failed
)
call :run_step "2/4" "Evaluating classification metrics" "python -u scripts\evaluate_model.py %LIMIT%"
if errorlevel 1 goto failed
call :run_step "3/4" "Running tests" "python -m pytest -q"
if errorlevel 1 goto failed
call :run_step "4/4" "Displaying model report" "python -u scripts\show_report.py"
if errorlevel 1 goto failed
goto completed

:full
call :banner
echo Mode: full training and full holdout evaluation.
echo Benchmark is separate: .\run_tuned.bat benchmark 500000
call :start_log "FULL"
call :run_step "1/6" "Installing requirements" "python -m pip install -r requirements.txt"
if errorlevel 1 goto failed
goto standard_after_setup

:standard
call :banner
echo Mode: train and evaluate %ROWS% rows ^(no benchmark^)
call :start_log "ROWS=%ROWS%"
call :check_dependencies
if errorlevel 1 goto failed_dependencies

:standard_after_setup
call :run_step "2/6" "Training tuned model" "python -u scripts\train_model.py %LIMIT%"
if errorlevel 1 goto failed
call :check_artifact "backend\artifacts\fraud_model.joblib"
if errorlevel 1 goto failed
call :run_step "3/6" "Evaluating classification metrics" "python -u scripts\evaluate_model.py %LIMIT%"
if errorlevel 1 goto failed
call :run_step "4/6" "Running tests" "python -m pytest -q"
if errorlevel 1 goto failed
call :run_step "5/6" "Displaying full model report" "python -u scripts\show_report.py"
if errorlevel 1 goto failed
goto serve_step

:resume
if not exist "backend\artifacts\fraud_model.joblib" goto failed_no_model
if "%ARG2%"=="" goto resume_args_ready
set "ROWS=%ARG2%"
call :validate_rows
if errorlevel 1 goto failed_args
set "LIMIT=--max-rows %ROWS%"
:resume_args_ready
call :banner
echo Mode: reuse model; evaluate %ROWS% rows. Benchmark is skipped.
call :start_log "RESUME"
call :check_dependencies
if errorlevel 1 goto failed_dependencies
call :run_step "1/4" "Evaluating classification metrics" "python -u scripts\evaluate_model.py %LIMIT%"
if errorlevel 1 goto failed
call :run_step "2/4" "Running tests" "python -m pytest -q"
if errorlevel 1 goto failed
call :run_step "3/4" "Displaying full model report" "python -u scripts\show_report.py"
if errorlevel 1 goto failed
goto serve_step

:train
set "ROWS=%ARG2%"
if "%ROWS%"=="" goto train_limit_ready
call :validate_rows
if errorlevel 1 goto failed_args
set "LIMIT=--max-rows %ROWS%"
:train_limit_ready
call :banner
echo Mode: training only
call :start_log "TRAIN"
call :check_dependencies
if errorlevel 1 goto failed_dependencies
call :run_step "1/1" "Training tuned model" "python -u scripts\train_model.py %LIMIT%"
if errorlevel 1 goto failed
goto completed

:evaluate_only
set "ROWS=%ARG2%"
if "%ROWS%"=="" goto evaluate_limit_ready
call :validate_rows
if errorlevel 1 goto failed_args
set "LIMIT=--max-rows %ROWS%"
:evaluate_limit_ready
if not exist "backend\artifacts\fraud_model.joblib" goto failed_no_model
call :banner
echo Mode: evaluation only ^(classification path; anomaly scoring skipped^)
call :start_log "EVALUATE"
call :check_dependencies
if errorlevel 1 goto failed_dependencies
call :run_step "1/2" "Evaluating classification metrics" "python -u scripts\evaluate_model.py %LIMIT%"
if errorlevel 1 goto failed
call :run_step "2/2" "Displaying full model report" "python -u scripts\show_report.py"
if errorlevel 1 goto failed
goto completed

:benchmark
set "ROWS=%ARG2%"
if "%ROWS%"=="" set "ROWS=500000"
call :validate_rows
if errorlevel 1 goto failed_args
call :banner
echo Mode: model comparison benchmark on %ROWS% rows
call :start_log "BENCHMARK"
call :check_dependencies
if errorlevel 1 goto failed_dependencies
call :run_step "1/2" "Benchmarking candidate models" "python -u scripts\benchmark_models.py --max-rows %ROWS%"
if errorlevel 1 goto failed
call :run_step "2/2" "Displaying full model report" "python -u scripts\show_report.py"
if errorlevel 1 goto failed
goto completed

:serve
call :banner
call :start_log "SERVE"
goto serve_step

:serve_step
echo.
echo [6/6] Starting API...
echo Docs: http://localhost:8000/docs
curl --fail --silent http://localhost:8000/health >nul 2>&1
if not errorlevel 1 (
  echo [OK] Existing API is already running on port 8000; reusing it.
) else (
  start "Tuned Fraud API" /b cmd /c "python -u -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 >> tuned_pipeline.log 2>&1"
  timeout /t 3 /nobreak >nul
  curl --fail --silent http://localhost:8000/health >nul 2>&1
  if errorlevel 1 echo [WARNING] API health check pending. See tuned_pipeline.log.
  if not errorlevel 1 echo [OK] API health check passed.
)
goto completed

:check_dependencies
python -c "import joblib, numpy, pandas, sklearn, fastapi, uvicorn" >nul 2>&1
if errorlevel 1 exit /b 1
echo [OK] Python requirements already available; installation skipped.
exit /b 0

:start_log
echo [%date% %time%] %~1 > "%LOG%"
exit /b 0

:run_step
echo.
echo [%~1] %~2
echo Command: %~3
echo [%date% %time%] START %~1 %~2 >> "%LOG%"
set "STEP_STARTED=%time%"
set "STEP_COMMAND=%~3"
rem Run through a child cmd, not CALL.  CALL reparses quoted command strings
rem and could restart the batch file after a successful Python process.
cmd /d /c %STEP_COMMAND%
if errorlevel 1 (
  echo [ERROR] %~2 failed. See %LOG%.
  exit /b 1
)
echo [%date% %time%] DONE  %~1 %~2 >> "%LOG%"
echo [OK] %~2 completed. Started %STEP_STARTED%, finished %time%.
exit /b 0

:check_artifact
if not exist "%~1" (echo [ERROR] Missing artifact: %~1& exit /b 1)
echo [OK] Found: %~1
exit /b 0

:validate_rows
echo(%ROWS%| findstr /r /x "[0-9][0-9]*" >nul
if errorlevel 1 exit /b 1
if "%ROWS%"=="0" exit /b 1
exit /b 0

:failed_no_model
echo [ERROR] Existing model artifact not found. Run .\run_tuned.bat train first.
goto failed
:failed_dependencies
echo [ERROR] Requirements missing. Run .\run_tuned.bat setup once.
goto failed
:failed_args
echo [ERROR] Valid examples: .\run_tuned.bat full ^| quick ^| resume 500000 ^| evaluate 50000 ^| benchmark 500000
goto failed
:failed
echo ================================================================
echo PIPELINE FAILED - review %cd%\%LOG%
pause
exit /b 1
:completed
echo.
echo COMPLETED - metrics: backend\artifacts\evaluation_metrics.json
echo Report: backend\artifacts\metrics.json
echo Log: %LOG%
endlocal
exit /b 0
:help
echo Usage:
echo   .\run_tuned.bat setup                 Install dependencies once
echo   .\run_tuned.bat quick                 5k validation, no benchmark/API
echo   .\run_tuned.bat full                  Train + full evaluation + test + report + API
echo   .\run_tuned.bat 50000                 Same flow with a row limit
echo   .\run_tuned.bat resume [rows]         Re-evaluate existing model; no retraining/benchmark
echo   .\run_tuned.bat train [rows]          Train only
echo   .\run_tuned.bat evaluate [rows]       Metrics/report only
echo   .\run_tuned.bat benchmark [rows]      Explicit model comparison (default 500000)
echo   .\run_tuned.bat serve                 Start/reuse API only
endlocal
exit /b 0
