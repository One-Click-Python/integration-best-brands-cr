#!/bin/bash

# RMS-Shopify Integration Dashboard Launcher
# This script launches the Streamlit dashboard

echo "🛍️ Starting RMS-Shopify Integration Dashboard..."

# Check if streamlit is installed
if ! poetry run python -c "import streamlit" 2>/dev/null; then
    echo "❌ Streamlit not found. Installing dependencies..."
    poetry install
fi

# Set default API URL if not set
export DASHBOARD_API_URL=${DASHBOARD_API_URL:-"http://localhost:8080"}

echo "📡 API URL: $DASHBOARD_API_URL"
echo "🌐 Dashboard will be available at: http://localhost:8501"
echo ""

# Run Streamlit
poetry run streamlit run dashboard/main.py --server.port 8501 --server.address 0.0.0.0
