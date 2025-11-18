#!/bin/bash
# Quick start script for stock-research-agent

set -e

echo "🏦 Stock Research Agent - Quick Start"
echo "======================================"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed."
    echo "📦 Install it with:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    exit 1
fi

echo "✅ uv is installed"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found"
    if [ -f .env.example ]; then
        echo "📋 Copying .env.example to .env"
        cp .env.example .env
        echo "⚙️  Please edit .env and add your ANTHROPIC_API_KEY"
        echo "   Get your API key at: https://console.anthropic.com/settings/keys"
        echo ""
        read -p "Press Enter after you've added your API key..."
    else
        echo "❌ .env.example not found"
        exit 1
    fi
else
    echo "✅ .env file found"
fi

# Check if API key is set
if ! grep -q "ANTHROPIC_API_KEY=sk-" .env 2>/dev/null; then
    echo "⚠️  ANTHROPIC_API_KEY not set in .env"
    echo "   Please add your API key to .env file"
    exit 1
fi

echo "✅ API key configured"
echo ""

# Install dependencies
echo "📦 Installing dependencies with uv..."
uv sync
echo "✅ Dependencies installed"
echo ""

# Run the agent
echo "🚀 Starting Stock Research Agent..."
echo "======================================"
echo ""
uv run python main.py
