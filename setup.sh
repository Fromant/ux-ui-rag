#!/bin/bash

echo "=== RAG System Setup ==="

# Check if PDF exists
if [ ! -f "books/DM2024.pdf" ]; then
    echo "ERROR: books/DM2024.pdf not found!"
    echo "Please place your textbook PDF in books/DM2024.pdf"
    exit 1
fi

echo ""
echo "Step 1: Creating directories..."
mkdir -p data/pages

echo ""
echo "Step 2: Building index with keyword extraction and question generation..."
python3 build_keywords.py --pdf books/DM2024.pdf --output data/sections_index.json

echo ""
echo "=== Setup complete! ==="
echo "Generated data is available in ./data folder"
echo ""
echo "To start the application:"
echo "  docker compose up -d"
