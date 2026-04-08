"""
PDF text extraction and cleaning for LLM context.

Extracts clean, meaningful text from PDF pages to use as context
for question and answer generation. Handles common PDF artifacts.
"""

import re
from typing import List, Optional


def extract_page_text(doc, page_num: int) -> str:
    """
    Extract clean text from a single page.

    Args:
        doc: PyMuPDF document
        page_num: Page number (0-based)

    Returns:
        Cleaned text
    """
    if page_num < 0 or page_num >= len(doc):
        return ""

    page = doc[page_num]
    return clean_pdf_text(page.get_text("text"))


def extract_section_context(doc, page_num: int, context_pages: int = 2) -> str:
    """
    Extract context text for a section (page + surrounding pages).

    Args:
        doc: PyMuPDF document
        page_num: Main page number (0-based)
        context_pages: Number of additional pages to include

    Returns:
        Combined cleaned text
    """
    texts = []
    start = max(0, page_num)
    end = min(len(doc), page_num + context_pages)

    for p in range(start, end):
        text = extract_page_text(doc, p)
        if text and len(text) > 50:  # Skip nearly empty pages
            texts.append(text)

    return "\n\n".join(texts)


def clean_pdf_text(raw_text: str) -> str:
    """
    Clean text extracted from PDF.

    Handles:
    - Hyphenated line breaks: "множе-\nство" -> "множество"
    - Repeated headers/footers
    - Excessive whitespace
    - Page number artifacts
    - Math formula fragments
    """
    if not raw_text:
        return ""

    # Fix hyphenated line breaks
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', raw_text)

    # Remove page numbers (standalone digits at line boundaries)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

    # Remove common PDF artifacts
    # "2/2", "1/1" part indicators
    text = re.sub(r'\s*\(\d+/\d+\)\s*', ' ', text)

    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'  +', ' ', text)

    # Remove lines that are just symbols/math
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip lines that are mostly math symbols
        alpha_chars = re.findall(r'[А-Яа-яёЁA-Za-z]', line)
        if len(alpha_chars) < len(line) * 0.3 and len(line) > 5:
            # Less than 30% letters - likely math formula
            continue
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines).strip()


def extract_text_blocks(doc, page_num: int, min_length: int = 100) -> List[str]:
    """
    Extract meaningful text blocks from a page.

    Returns blocks that are long enough to be actual content,
    filtering out headers, footers, and short fragments.

    Args:
        doc: PyMuPDF document
        page_num: Page number (0-based)
        min_length: Minimum block length

    Returns:
        List of text blocks
    """
    if page_num < 0 or page_num >= len(doc):
        return []

    page = doc[page_num]
    text = page.get_text("text")

    # Split by double newlines (natural paragraph breaks)
    blocks = re.split(r'\n\n+', text)

    # Filter and clean
    result = []
    for block in blocks:
        cleaned = clean_pdf_text(block)
        if len(cleaned) >= min_length:
            result.append(cleaned)

    return result


def get_section_text_for_llm(doc, section: dict) -> str:
    """
    Get clean text context for a section, optimized for LLM prompts.

    Extracts and cleans text from the section's pages, removing
    artifacts and keeping only meaningful content.

    Args:
        doc: PyMuPDF document
        section: Section dict with 'page' field (1-based)

    Returns:
        Clean text suitable for LLM context
    """
    page_num = section.get('page', 1) - 1  # Convert to 0-based

    # Get context from main page + next 2 pages
    context = extract_section_context(doc, page_num, context_pages=2)

    # If too little text, expand to more pages
    if len(context) < 200:
        context = extract_section_context(doc, max(0, page_num - 1), context_pages=3)

    # Truncate if too long (LLM context limit)
    if len(context) > 2000:
        # Keep the beginning which usually has the most relevant content
        context = context[:2000]
        # Try to cut at a sentence boundary
        last_period = context.rfind('. ')
        if last_period > 1500:
            context = context[:last_period + 1]

    return context
