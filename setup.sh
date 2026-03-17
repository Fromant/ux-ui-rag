#!/bin/bash

echo "=== RAG System Setup ==="

# Check if PDF exists
if [ ! -f "books/DM2024.pdf" ]; then
    echo "ERROR: books/DM2024.pdf not found!"
    echo "Please place your textbook PDF in books/DM2024.pdf"
    exit 1
fi

echo "Step 1: Creating directories..."
mkdir -p data/pages

echo "Step 2: Converting PDF to images (this may take a few minutes)..."
python3 -c "
import sys
sys.path.insert(0, '.')
from app.processors.pdf_to_images import convert_pdf_to_images
convert_pdf_to_images('books/DM2024.pdf', 'data/pages', dpi=150)
print('PDF conversion complete!')
"

echo "Step 3: Building search index..."
python3 -c "
import sys
sys.path.insert(0, '.')
from app.search.pdf_indexer import PDFIndexer
indexer = PDFIndexer('books/DM2024.pdf')
sections = indexer.extract_sections()
indexer.save('data/sections_index.json')
print(f'Index created with {len(sections)} sections')
"

echo ""
echo "=== Setup complete! ==="
echo "Now run: docker build -t pestr-rag . && docker run -p 8000:8000 pestr-rag"
