#!/usr/bin/env python3
"""
Build keywords and questions from PDF.

Extracts sections, keywords from multiple sources, and generates template-based questions.
Runs completely offline - no LLM required!

Usage:
    python build_keywords.py --pdf books/DM2024.pdf
    python build_keywords.py --pdf books/DM2024.pdf --output data/sections_index.json
    python build_keywords.py --pdf books/DM2024.pdf --skip-questions
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import fitz

from app.processors.pdf_keyword_extractor import RedTextKeywordExtractor, SubjectIndexParser, KeywordMerger
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

                section_title = self._clean_title(raw_title)
                if not section_title:
                    continue

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
        if not title:
            return None

        title = re.sub(r'\s*\(\d+/\d*\s*$', '', title)
        title = re.sub(r'\s*\(\d+/\d+\)\s*', '', title)
        title = title.rstrip('.!?;:')
        title = re.sub(r'-\s*$', '', title)

        if ':' in title:
            parts = title.split(':')
            if len(parts[0].strip()) > 3 and len(parts[0].strip()) < 100:
                title = parts[0].strip()

        if ',' in title and len(title) > 60:
            parts = title.split(',')
            if len(parts[0].strip()) > 3:
                title = parts[0].strip()

        title = ' '.join(title.split())

        if not (title[0].isupper() or title[0].isdigit()):
            return None

        if len(title) < 3 or len(title) > 100:
            return None

        bad_patterns = [r'^и\s+\w', r'^для\s+\w', r'^при\s+\w', r'^в\s+\w', r'^на\s+\w', r'^что\s+\w', r'^как\s+\w']
        for pattern in bad_patterns:
            if re.search(pattern, title):
                return None

        return title[:100]


def build_keywords(pdf_path: str, output_path: str):
    """
    Build complete index with keywords from all sources and template-based questions.

    Keyword priority:
    1. Key terms tables (авторские ключевые термины)
    2. Subject index (предметный указатель)
    3. Red text keywords
    4. Frequency-based fallback
    
    Questions are always generated with reference answers from section content.
    """
    print("=" * 70)
    print("KEYWORD AND QUESTION EXTRACTION")
    print("=" * 70)

    # Step 1: Extract sections
    print("\n[1/5] Extracting sections...")
    section_extractor = SectionExtractor(pdf_path)
    sections = section_extractor.extract_sections()

    # Step 2: Key terms tables (HIGHEST PRIORITY)
    print("\n[2/5] Parsing key terms tables...")
    table_parser = KeyTermsTableParser(pdf_path)
    key_terms = table_parser.extract_all_key_terms()

    # Step 3: Red text keywords
    print("\n[3/5] Extracting red text keywords...")
    red_extractor = RedTextKeywordExtractor(pdf_path)
    red_keywords = red_extractor.extract_all_red_keywords()
    print(f"  Found on {len(red_keywords)} pages")

    # Step 4: Subject index
    print("\n[4/5] Parsing subject index...")
    subject_parser = SubjectIndexParser(pdf_path)
    subject_index = subject_parser.extract_subject_index()

    # Step 5: Frequency fallback
    print("\n[5/5] Building frequency keywords...")
    doc = fitz.open(pdf_path)
    freq_keywords = {}
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text:
            freq_keywords[page_num + 1] = extract_keywords_from_text(text, top_k=15)
    doc.close()

    # Merge all sources
    print("\nMerging keywords...")
    sections = KeywordMerger.merge_keywords_with_tables(
        key_terms=key_terms,
        subject_index=subject_index,
        red_keywords=red_keywords,
        frequency_keywords=freq_keywords,
        sections=sections,
    )

    # Generate template-based questions with reference answers
    print("\nGenerating template-based questions with reference answers...")
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
        section["quiz_questions"] = questions
        total_questions += len(questions)
        
        if (idx + 1) % 100 == 0:
            print(f"  Generated questions for {idx + 1}/{len(sections)} sections")
    
    doc.close()
    print(f"  ✅ Generated {total_questions} questions for {len(sections)} sections")

    # Save
    print(f"\nSaving to {output_path}...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)

    # Stats
    with_key_terms = sum(1 for s in sections if s.get('keywords_by_source', {}).get('key_terms', 0) > 0)
    with_subject = sum(1 for s in sections if s.get('keywords_by_source', {}).get('subject_index', 0) > 0)
    with_red = sum(1 for s in sections if s.get('keywords_by_source', {}).get('red', 0) > 0)
    only_freq = sum(1 for s in sections if s.get('keywords_by_source', {}).get('key_terms', 0) == 0
                   and s.get('keywords_by_source', {}).get('subject_index', 0) == 0
                   and s.get('keywords_by_source', {}).get('red', 0) == 0)
    total_questions = sum(len(s.get('quiz_questions', [])) for s in sections)

    print("\n" + "=" * 70)
    print("✅ KEYWORD AND QUESTION EXTRACTION COMPLETE!")
    print(f"   Sections: {len(sections)}")
    print(f"   Keywords sources:")
    print(f"     - Key terms tables: {with_key_terms}/{len(sections)} sections")
    print(f"     - Subject index: {with_subject}/{len(sections)} sections")
    print(f"     - Red text: {with_red}/{len(sections)} sections")
    print(f"     - Frequency only: {only_freq}/{len(sections)} sections")
    print(f"   Quiz questions: {total_questions}")
    print(f"   File: {output_path}")
    print("=" * 70)

    return sections


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build keywords and questions from PDF")
    parser.add_argument("--pdf", default="books/DM2024.pdf")
    parser.add_argument("--output", default="data/sections_index.json")

    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"❌ PDF not found: {args.pdf}")
        sys.exit(1)

    build_keywords(args.pdf, args.output)
