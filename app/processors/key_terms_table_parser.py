"""
Key terms table parser.

Extracts key terms from the "Ключевые термины и обозначения" tables
found at the beginning of each unit in the textbook.

This is the MOST authoritative source for keywords since it's
explicitly provided by the textbook authors.
"""

import re
from typing import List, Dict, Any, Tuple
import fitz


class KeyTermsTableParser:
    """
    Parses key terms tables from textbook units.

    Table format:
    № | Название параграфа | Ключевые термины и обозначения
    1.1.1. | Элементы и множества | ∈ — отношение принадлежности; ∅ — пустое множество
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def find_key_terms_pages(self) -> List[int]:
        """Find all pages containing key terms tables."""
        doc = fitz.open(self.pdf_path)
        pages_with_tables = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if "Ключевые термины и обозначения" in text:
                pages_with_tables.append(page_num)

        doc.close()
        return pages_with_tables

    def parse_key_terms_page(self, page_num: int) -> List[Dict[str, Any]]:
        """
        Parse a single key terms table page.

        Returns:
            List of dicts with section_num, section_title, key_terms
        """
        doc = fitz.open(self.pdf_path)
        page = doc[page_num]
        text = page.get_text("text")
        doc.close()

        # Find the table content after "Ключевые термины и обозначения"
        idx = text.find("Ключевые термины и обозначения")
        if idx == -1:
            return []

        table_text = text[idx + len("Ключевые термины и обозначения"):]

        # Fix hyphenated line breaks BEFORE parsing
        table_text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', table_text)

        # Parse section entries
        entries = []
        lines = table_text.split('\n')

        current_section = None
        current_title = None
        current_terms = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line starts with section number (e.g., "1.1.1.", "8.3.5.*")
            section_match = re.match(r'^(\d+\.\d+(?:\.\d+)?\.?\*?)\s*(.*)', line)

            if section_match:
                # Save previous entry if exists
                if current_section and current_terms:
                    entries.append({
                        'section_num': current_section.rstrip('.*'),
                        'section_title': current_title,
                        'key_terms': current_terms,
                    })

                current_section = section_match.group(1).strip()
                rest = section_match.group(2).strip()

                if rest:
                    current_title = rest
                    current_terms = []
                else:
                    current_title = None
                    current_terms = []
            elif current_section:
                # This line contains key terms or continuation of title
                if not current_title:
                    current_title = line
                else:
                    # Parse key terms from this line
                    terms = self._parse_key_terms_line(line)
                    current_terms.extend(terms)

        # Save last entry
        if current_section and current_terms:
            entries.append({
                'section_num': current_section.rstrip('.*'),
                'section_title': current_title,
                'key_terms': current_terms,
            })

        return entries

    def _parse_key_terms_line(self, line: str) -> List[str]:
        """
        Parse key terms from a line.

        Formats:
        - "∈ — отношение принадлежности; ∅ — пустое множество"
        - "Система различных представителей; совершенное паросочетание"
        - "Латинский прямоугольник; ортогональные латинские квадраты"
        """
        terms = []

        # Split by semicolons
        parts = line.split(';')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Remove symbols and mathematical notation
            # Keep only Russian/English words (4+ chars to avoid fragments)
            words = re.findall(r'[А-Яа-яёЁA-Za-z]{4,}', part)

            if words:
                # Join words that form a single term
                term = ' '.join(words)
                if 4 <= len(term) <= 100:
                    terms.append(term.lower())

        return terms

    def extract_all_key_terms(self) -> Dict[str, List[str]]:
        """
        Extract key terms from all tables in the PDF.

        Returns:
            Dict mapping section_num -> list of key terms
        """
        table_pages = self.find_key_terms_pages()
        print(f"Found {len(table_pages)} pages with key terms tables")

        all_key_terms = {}

        for page_num in table_pages:
            entries = self.parse_key_terms_page(page_num)

            for entry in entries:
                section_num = entry['section_num']
                key_terms = entry['key_terms']

                if section_num and key_terms:
                    # Normalize section number (remove trailing dots and asterisks)
                    section_num = section_num.rstrip('.* ')

                    if section_num and section_num not in all_key_terms:
                        all_key_terms[section_num] = []
                    all_key_terms[section_num].extend(key_terms)

        # Deduplicate terms for each section
        for section_num in all_key_terms:
            all_key_terms[section_num] = sorted(list(set(all_key_terms[section_num])))

        sections_with_terms = sum(1 for v in all_key_terms.values() if v)
        total_terms = sum(len(v) for v in all_key_terms.values())

        print(f"Extracted key terms for {sections_with_terms} sections ({total_terms} total terms)")
        return all_key_terms
