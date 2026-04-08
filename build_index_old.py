#!/usr/bin/env python3
"""
Build-time index generator with smart keyword extraction and template-based question generation.

Uses multiple strategies for high-quality index building:
1. Red text detection - keywords are often marked red in the textbook
2. Subject index (предметный указатель) parsing - authoritative keyword source
3. Template-based question generation - diverse quiz questions without LLM

The app itself runs 100% offline - questions are generated at build time!

Usage:
    python build_index_old.py --pdf books/DM2024.pdf
    python build_index_old.py --pdf books/DM2024.pdf --skip-questions
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import fitz

# Import processors
from app.processors.pdf_keyword_extractor import (
    RedTextKeywordExtractor,
    SubjectIndexParser,
    KeywordMerger,
)
from app.processors.key_terms_table_parser import KeyTermsTableParser
from app.processors.text_cleaner import extract_keywords_from_text
from app.processors.question_template_generator import QuestionTemplateGenerator


class SectionExtractor:
    """Extracts sections from PDF using pattern matching."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract_sections(self) -> List[Dict[str, Any]]:
        """Extract all sections from PDF."""
        print("Extracting sections from PDF...")
        doc = fitz.open(self.pdf_path)
        print(f"PDF has {len(doc)} pages")

        # Pattern: section number followed by title
        section_pattern = re.compile(
            r'(\d+\.\d+(?:\.\d+)?)\.?\s+([А-Яа-яёЁA-Z][^\n\r]{2,200})',
            re.MULTILINE
        )

        sections = []
        for page_num in range(len(doc)):
            if page_num % 100 == 0:
                print(f"Processing page {page_num + 1}/{len(doc)}")

            page = doc[page_num]
            text = page.get_text("text")

            if not text:
                continue

            matches = list(section_pattern.finditer(text))

            for match in matches:
                section_num = match.group(1)
                raw_title = match.group(2).strip()

                # Clean and validate the title
                section_title = self._clean_title(raw_title)

                if not section_title:
                    continue

                # Validate section number format
                sec_parts = section_num.split('.')
                if not all(p.isdigit() and 1 <= int(p) <= 999 for p in sec_parts):
                    continue
                if sec_parts[0] == '0':
                    continue

                sections.append({
                    'section_num': section_num,
                    'title': section_title,
                    'page': page_num + 1,
                    'keywords': [],
                    'quiz_questions': [],
                })

        doc.close()

        # Deduplicate (keep last occurrence for each section number)
        seen = {}
        for s in sections:
            seen[s['section_num']] = s

        sections = list(seen.values())
        sections.sort(key=lambda x: (
            int(x['section_num'].split('.')[0]),
            x['section_num']
        ))

        print(f"Extracted {len(sections)} unique sections")
        return sections

    def _clean_title(self, title: str) -> Optional[str]:
        """Clean and validate section title."""
        if not title:
            return None

        # Remove part indicators like (2/2), (3/3), etc.
        title = re.sub(r'\s*\(\d+/\d*\s*$', '', title)
        title = re.sub(r'\s*\(\d+/\d+\)\s*', '', title)

        # Remove trailing punctuation
        title = title.rstrip('.!?;:')

        # Remove trailing hyphenation
        title = re.sub(r'-\s*$', '', title)

        # Remove content after colon if it looks like a subtitle
        if ':' in title:
            parts = title.split(':')
            if len(parts[0].strip()) > 3 and len(parts[0].strip()) < 100:
                title = parts[0].strip()

        # Remove content after comma if title is already long enough
        if ',' in title and len(title) > 60:
            parts = title.split(',')
            if len(parts[0].strip()) > 3:
                title = parts[0].strip()

        # Normalize spaces
        title = ' '.join(title.split())

        # Must start with uppercase letter or digit
        if not (title[0].isupper() or title[0].isdigit()):
            return None

        # Filter bad titles
        if len(title) < 3 or len(title) > 100:
            return None

        # Check for common bad patterns
        bad_patterns = [
            r'^и\s+\w', r'^для\s+\w', r'^при\s+\w', r'^в\s+\w',
            r'^на\s+\w', r'^что\s+\w', r'^как\s+\w',
        ]
        for pattern in bad_patterns:
            if re.search(pattern, title):
                return None

        return title[:100]


def build_index_pipeline(
    pdf_path: str,
    output_path: str,
    sample_size: Optional[int] = None,
    chapters: Optional[str] = None,
):
    """
    Complete index building pipeline with smart keyword extraction and question generation.

    Keyword sources (in priority order):
    1. Key terms table (авторские ключевые термины из таблиц учебника)
    2. Subject index (предметный указатель)
    3. Red text keywords
    4. Frequency-based fallback
    
    Questions are always generated with reference answers from section content.
    """
    print("=" * 70)
    print("SMART PDF INDEX BUILDER")
    print("Pipeline: Sections → Keywords (Tables + Subject + Red + Freq) → Questions")
    print("=" * 70)

    # Step 1: Extract sections
    print("\n[1/6] Extracting sections from PDF...")
    section_extractor = SectionExtractor(pdf_path)
    sections = section_extractor.extract_sections()

    # Step 2: Parse key terms tables (HIGHEST PRIORITY)
    print("\n[2/6] Parsing key terms tables...")
    table_parser = KeyTermsTableParser(pdf_path)
    key_terms = table_parser.extract_all_key_terms()

    # Step 3: Extract red text keywords
    print("\n[3/6] Extracting red text keywords...")
    red_extractor = RedTextKeywordExtractor(pdf_path)
    red_keywords = red_extractor.extract_all_red_keywords()
    print(f"  Found red keywords on {len(red_keywords)} pages")

    # Step 4: Parse subject index
    print("\n[4/6] Parsing subject index (предметный указатель)...")
    subject_parser = SubjectIndexParser(pdf_path)
    subject_index = subject_parser.extract_subject_index()

    # Step 5: Build frequency-based keywords as fallback
    print("\n[5/6] Building frequency-based keyword fallback...")
    doc = fitz.open(pdf_path)
    freq_keywords = {}
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text:
            # Use the proper text cleaner
            freq_keywords[page_num + 1] = extract_keywords_from_text(text, top_k=15)
    doc.close()

    # Step 6: Merge keywords (key_terms has highest priority)
    print("\n[6/6] Merging keywords from all sources...")
    sections = KeywordMerger.merge_keywords_with_tables(
        key_terms=key_terms,
        subject_index=subject_index,
        red_keywords=red_keywords,
        frequency_keywords=freq_keywords,
        sections=sections,
    )

    # Generate questions with reference answers from section content
    print("\n[EXTRA] Generating template-based quiz questions with reference answers...")
    question_gen = QuestionTemplateGenerator()
    
    doc = fitz.open(pdf_path)
    total_questions = 0
    
    for idx, section in enumerate(sections):
        # Get section text for generating reference answers
        page_num = section['page'] - 1  # Convert to 0-based
        section_text = ""
        if 0 <= page_num < len(doc):
            # Get text from main page + next 2 pages
            texts = []
            for p in range(page_num, min(page_num + 3, len(doc))):
                text = doc[p].get_text("text")
                if text and len(text) > 50:
                    texts.append(text)
            section_text = '\n\n'.join(texts)[:2000]  # Limit context
        
        questions = question_gen.generate_questions(section, section_text=section_text, num_questions=3)
        section['quiz_questions'] = questions
        total_questions += len(questions)
        
        if (idx + 1) % 100 == 0:
            print(f"  Generated questions for {idx + 1}/{len(sections)} sections")
    
    doc.close()
    print(f"  ✅ Generated {total_questions} questions for {len(sections)} sections")

    # Save index
    print(f"\nSaving index to {output_path}...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)

    # Print statistics
    with_key_terms = sum(1 for s in sections if s.get('keywords_by_source', {}).get('key_terms', 0) > 0)
    with_subject_index = sum(1 for s in sections if s.get('keywords_by_source', {}).get('subject_index', 0) > 0)
    with_red = sum(1 for s in sections if s.get('keywords_by_source', {}).get('red', 0) > 0)
    only_freq = sum(1 for s in sections if s.get('keywords_by_source', {}).get('key_terms', 0) == 0
                   and s.get('keywords_by_source', {}).get('subject_index', 0) == 0
                   and s.get('keywords_by_source', {}).get('red', 0) == 0)
    total_questions = sum(len(s.get('quiz_questions', [])) for s in sections)

    print("\n" + "=" * 70)
    print("✅ INDEX BUILD COMPLETE!")
    print(f"   Sections: {len(sections)}")
    print(f"   Keywords sources:")
    print(f"     - Key terms tables: {with_key_terms}/{len(sections)} sections")
    print(f"     - Subject index: {with_subject_index}/{len(sections)} sections")
    print(f"     - Red text: {with_red}/{len(sections)} sections")
    print(f"     - Frequency only: {only_freq}/{len(sections)} sections")
    print(f"   Quiz questions: {total_questions}")
    print(f"   File: {output_path}")
    print("=" * 70)

    return sections


def convert_pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 150):
    """Convert PDF pages to PNG images."""
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"Converting {total_pages} pages to images...")

    for page_num in range(total_pages):
        if page_num % 100 == 0:
            print(f"  Page {page_num + 1}/{total_pages}")

        page = doc.load_page(page_num)
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        img_path = os.path.join(output_dir, f"page_{page_num + 1:04d}.png")
        pix.save(img_path)

    doc.close()
    print(f"✅ Saved {total_pages} images")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build RAG index with smart keyword extraction and question generation"
    )
    parser.add_argument("--pdf", default="books/DM2024.pdf")
    parser.add_argument("--output", default="data/sections_index.json")
    parser.add_argument("--pages-dir", default="data/pages")
    parser.add_argument("--skip-images", action="store_true")
    parser.add_argument("--sample-size", type=int, default=None,
                        help="Process only first N sections (for testing)")
    parser.add_argument("--chapters", type=str, default=None,
                        help="Process only specific chapters (e.g., '7' or '7,8')")

    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"❌ PDF not found: {args.pdf}")
        sys.exit(1)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    if not args.skip_images:
        os.makedirs(args.pages_dir, exist_ok=True)

    # Build index with new pipeline
    sections = build_index_pipeline(
        pdf_path=args.pdf,
        output_path=args.output,
        sample_size=args.sample_size,
        chapters=args.chapters,
    )

    # Generate images
    if not args.skip_images:
        print("\nGenerating page images...")
        convert_pdf_to_images(args.pdf, args.pages_dir)

    print("\n🎉 Build complete!")
