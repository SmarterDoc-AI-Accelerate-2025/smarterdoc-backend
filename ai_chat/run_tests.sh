#!/bin/bash
# Test runner script for AI Chat Service

set -e

echo "=================================="
echo "AI Chat Service - Test Runner"
echo "=================================="
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Warning: Virtual environment not activated"
    echo "   Please activate it first:"
    echo "   source venv/bin/activate  # Linux/Mac"
    echo "   .\\venv\\Scripts\\Activate.ps1  # Windows"
    echo ""
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing dependencies..."
    pip install -r requirements.txt
    echo ""
fi

echo "Running tests..."
echo ""

# Run tests with coverage
pytest tests/ -v --cov=ai_chat --cov-report=term-missing --cov-report=html

echo ""
echo "=================================="
echo "✅ Tests completed!"
echo "=================================="
echo ""
echo "Coverage report saved to: htmlcov/index.html"
echo "Open it in your browser to view detailed coverage"

