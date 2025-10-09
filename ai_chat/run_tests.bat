@echo off
REM Test runner script for AI Chat Service (Windows)

echo ==================================
echo AI Chat Service - Test Runner
echo ==================================
echo.

REM Check if pytest is available
where pytest >nul 2>&1
if %errorlevel% neq 0 (
    echo pytest not found. Installing dependencies...
    pip install -r requirements.txt
    echo.
)

echo Running tests...
echo.

REM Run tests with coverage
pytest tests\ -v --cov=ai_chat --cov-report=term-missing --cov-report=html

echo.
echo ==================================
echo Tests completed!
echo ==================================
echo.
echo Coverage report saved to: htmlcov\index.html
echo Open it in your browser to view detailed coverage

