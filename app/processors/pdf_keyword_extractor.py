"""
Smart keyword extractor from PDF.

Uses PyMuPDF's text dictionary format to detect:
1. Red-colored text (keywords are often highlighted in red in textbooks)
2. Subject index (предметный указатель) at the end of PDF
3. Combined keyword merging from multiple sources
"""

import re
from typing import List, Dict, Any, Tuple
import fitz

from app.processors.text_cleaner import extract_keywords_from_text, is_valid_keyword


class RedTextKeywordExtractor:
    """Extracts keywords from PDF by detecting red-colored text."""

    # PyMuPDF uses 24-bit integer colors (0-16777215)
    # Format: 0xRRGGBB
    # Common colors:
    # - Red: 0xFF0000 = 16711680
    # - Blue: 0x0000FF = 255
    # - Black: 0x000000 = 0
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def _is_red_color(self, color: Any) -> bool:
        """
        Check if a color value represents red text.
        
        PyMuPDF returns colors as 24-bit integers: 0xRRGGBB
        Red = 0xFF0000 = 16711680
        """
        if color is None:
            return False
        
        # Convert to RGB components
        if isinstance(color, int):
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            
            # Check if it's red-ish (high R, low G and B)
            # Allow some tolerance
            return r >= 200 and g <= 80 and b <= 80
        
        # Handle tuple/list RGB (0.0-1.0 range)
        if isinstance(color, (list, tuple)):
            if len(color) == 3:  # RGB
                r, g, b = color
                # If values are 0.0-1.0
                if all(isinstance(v, float) for v in [r, g, b]):
                    return r >= 0.8 and g <= 0.3 and b <= 0.3
                # If values are 0-255
                else:
                    return r >= 200 and g <= 80 and b <= 80
            elif len(color) == 4:  # CMYK
                c, m, y, k = color
                # Red in CMYK: low cyan, high magenta, high yellow
                return m >= 0.8 and y >= 0.8 and c <= 0.3
        
        return False

    def extract_red_keywords_from_page(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """
        Extract all red text from a page.

        Returns list of dicts with:
        - text: the red text content
        - page: page number (1-based)
        - position: bounding box coordinates
        """
        keywords = []

        # Get text as dict with formatting info
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Skip non-text blocks
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    color = span.get("color")

                    if text and len(text) >= 3 and self._is_red_color(color):
                        # Split text into individual words and validate each
                        words = re.findall(r'\b[А-Яа-яёЁA-Za-z]{3,}\b', text)
                        for word in words:
                            if is_valid_keyword(word):
                                keywords.append({
                                    "text": word.lower(),
                                    "page": page.number + 1,
                                })

        return keywords

    def extract_all_red_keywords(self, page_range: Tuple[int, int] = None) -> Dict[str, List[str]]:
        """
        Extract red keywords from all pages in range.

        Args:
            page_range: Optional tuple (start_page, end_page), 1-based

        Returns:
            Dict mapping page_number -> list of red keywords
        """
        doc = fitz.open(self.pdf_path)
        keywords_by_page = {}

        start_page = 0
        end_page = len(doc)

        if page_range:
            start_page = max(0, page_range[0] - 1)
            end_page = min(len(doc), page_range[1])

        for page_num in range(start_page, end_page):
            page = doc[page_num]
            red_keywords = self.extract_red_keywords_from_page(page)

            if red_keywords:
                page_key = page_num + 1
                # Deduplicate keywords on this page
                seen = set()
                unique_keywords = []
                for kw in red_keywords:
                    if kw["text"] not in seen:
                        seen.add(kw["text"])
                        unique_keywords.append(kw["text"])
                
                keywords_by_page[page_key] = unique_keywords

        doc.close()
        return keywords_by_page


class SubjectIndexParser:
    """
    Parses the предметный указатель (subject index) from the end of the PDF.

    This is the authoritative source for keywords and their page references.
    Format is typically: "Keyword, page_number" or "Keyword, page_numbers"
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def _find_subject_index_pages(self) -> List[int]:
        """
        Find pages containing the предметный указатель.

        Strategy 1: Look for header "Предметный указатель" or similar.
        Strategy 2: Detect by format - pages with "Term (translation), number" pattern.
        """
        doc = fitz.open(self.pdf_path)
        index_pages = []

        # Check last 50 pages (or all pages if less)
        search_pages = range(max(0, len(doc) - 50), len(doc))

        # Pattern that matches subject index format
        index_pattern = re.compile(r'[А-Яа-яёЁ]{3,}\s*\([^)]+\)\s*,\s*\d+', re.MULTILINE)

        for page_num in search_pages:
            page = doc[page_num]
            text = page.get_text("text")

            # Strategy 1: Look for header
            text_lower = text.lower()
            index_headers = [
                "предметный указатель",
                "предметный",
                "указатель",
                "алфавитный указатель",
                "индекс",
            ]

            has_header = any(h in text_lower for h in index_headers)

            # Strategy 2: Detect by format (multiple entries matching pattern)
            format_matches = len(index_pattern.findall(text))

            # If has header OR strong format match (5+ index entries)
            if has_header or format_matches >= 5:
                index_pages.append(page_num)

        doc.close()

        # If we found consecutive pages, keep them all
        if len(index_pages) > 0:
            # Fill in gaps - if we have pages 1715, 1716, 1720, fill 1717-1719
            min_page = min(index_pages)
            max_page = max(index_pages)
            index_pages = list(range(min_page, max_page + 1))

        return index_pages

    def _parse_index_page(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """
        Parse a single subject index page.

        Handles multiline entries like:
        "Расстояние (distance), 1103, 1192\nманхэттенское (Manhatten), 1409"
        "Реализация (implementation)\nалгоритма (of algorithm), 776"
        """
        keywords = []
        text = page.get_text("text")

        # Join lines that are continuations (don't end with page number)
        lines = text.split('\n')
        joined_lines = []
        current_line = ""

        for line in lines:
            line = line.strip()
            if not line:
                if current_line:
                    joined_lines.append(current_line)
                    current_line = ""
                continue

            # Check if line ends with page number pattern
            if re.search(r',\s*\d+\s*$', line):
                # This line has page numbers - complete entry
                if current_line:
                    current_line += " " + line
                    joined_lines.append(current_line)
                    current_line = ""
                else:
                    joined_lines.append(line)
            else:
                # Continuation or start of new entry
                if current_line:
                    current_line += " " + line
                else:
                    current_line = line

        if current_line:
            joined_lines.append(current_line)

        # Now parse each joined line
        # Pattern: "Термин (translation), 123" or "Термин (trans)\nподтермин (subtrans), 123"
        pattern = r'([А-Яа-яёЁA-Za-z][А-Яа-яёЁA-Za-z\s\-\']+?)(?:\s*\([^)]*\))?(?:\s*\n\s*[А-Яа-яёЁA-Za-z][А-Яа-яёЁA-Za-z\s\-\']*\s*\([^)]*\))?\s*,\s*(\d+(?:\s*,\s*\d+)*)'

        for full_line in joined_lines:
            if not full_line or len(full_line) < 5:
                continue

            # Skip lines that are clearly not index entries
            if any(skip in full_line.lower() for skip in ['содержание', 'оглавление', 'введение']):
                continue

            matches = re.finditer(pattern, full_line)
            for match in matches:
                keyword = match.group(1).strip()
                pages_str = match.group(2)

                # Parse page numbers
                try:
                    pages = [int(p.strip()) for p in pages_str.split(',')]
                except ValueError:
                    continue

                # Validate
                if len(keyword) >= 2 and all(1 <= p <= 3000 for p in pages):
                    # Clean up keyword (remove trailing artifacts, normalize spaces)
                    keyword = re.sub(r'\s+', ' ', keyword).rstrip('-\n').strip()
                    if len(keyword) >= 2 and is_valid_keyword(keyword):
                        keywords.append({
                            "keyword": keyword.lower(),
                            "pages": pages,
                        })

        return keywords

    def extract_subject_index(self) -> Dict[str, List[int]]:
        """
        Extract the complete subject index.

        Returns:
            Dict mapping keyword -> list of page numbers
        """
        index_pages = self._find_subject_index_pages()

        if not index_pages:
            print("⚠️  Subject index (предметный указатель) not found")
            return {}

        print(f"Found subject index on {len(index_pages)} pages")

        doc = fitz.open(self.pdf_path)
        all_keywords = {}

        for page_num in index_pages:
            page = doc[page_num]
            keywords = self._parse_index_page(page)

            for kw in keywords:
                keyword = kw["keyword"]
                if keyword not in all_keywords:
                    all_keywords[keyword] = []
                all_keywords[keyword].extend(kw["pages"])

        doc.close()

        # Deduplicate and sort page numbers
        for keyword in all_keywords:
            all_keywords[keyword] = sorted(list(set(all_keywords[keyword])))

        print(f"Extracted {len(all_keywords)} keywords from subject index")
        return all_keywords


class KeywordMerger:
    """Merges keywords from multiple sources with priority."""

    @staticmethod
    def _get_page_range_keywords(page: int, keyword_dict: Dict[str, List[int]], tolerance: int = 2) -> List[str]:
        """
        Get keywords for a page with tolerance for page number mismatches.

        If exact page not found, check nearby pages (±tolerance).
        """
        # Direct match
        if page in keyword_dict:
            return keyword_dict[page]

        # Fuzzy match with tolerance
        nearby_keywords = []
        for offset in range(1, tolerance + 1):
            for nearby_page in [page - offset, page + offset]:
                if nearby_page in keyword_dict:
                    nearby_keywords.extend(keyword_dict[nearby_page])

        return nearby_keywords

    @staticmethod
    def merge_keywords(
        subject_index: Dict[str, List[int]],
        red_keywords: Dict[int, List[str]],
        frequency_keywords: Dict[int, List[str]],
        sections: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge keywords from multiple sources into sections.

        Priority: subject_index > red_keywords > frequency_keywords

        Args:
            subject_index: keyword -> [page_nums] from предметный указатель
            red_keywords: page_num -> [keywords] from red text
            frequency_keywords: page_num -> [keywords] from frequency analysis
            sections: list of section dicts to update

        Returns:
            Updated sections list
        """
        # Build page -> keywords mapping from all sources
        page_keywords = {}

        # From subject index (highest priority)
        for keyword, pages in subject_index.items():
            for page in pages:
                if page not in page_keywords:
                    page_keywords[page] = {"subject_index": [], "red": [], "frequency": []}
                page_keywords[page]["subject_index"].append(keyword)

        # From red keywords
        for page, keywords in red_keywords.items():
            if page not in page_keywords:
                page_keywords[page] = {"subject_index": [], "red": [], "frequency": []}
            page_keywords[page]["red"].extend(keywords)

        # From frequency keywords
        for page, keywords in frequency_keywords.items():
            if page not in page_keywords:
                page_keywords[page] = {"subject_index": [], "red": [], "frequency": []}
            page_keywords[page]["frequency"].extend(keywords)

        # Update sections with merged keywords
        for section in sections:
            page = section["page"]

            if page in page_keywords:
                sources = page_keywords[page]

                # Merge with priority: subject_index > red > frequency
                merged = []
                seen = set()

                for keyword in sources["subject_index"]:
                    kw_lower = keyword.lower()
                    if kw_lower not in seen:
                        merged.append(keyword)
                        seen.add(kw_lower)

                for keyword in sources["red"]:
                    kw_lower = keyword.lower()
                    if kw_lower not in seen:
                        merged.append(keyword)
                        seen.add(kw_lower)

                for keyword in sources["frequency"]:
                    kw_lower = keyword.lower()
                    if kw_lower not in seen:
                        merged.append(keyword)
                        seen.add(kw_lower)

                # Keep top 15 keywords
                section["keywords"] = merged[:15]
                section["keywords_by_source"] = {
                    "subject_index": len(sources["subject_index"]),
                    "red": len(sources["red"]),
                    "frequency": len(sources["frequency"]),
                }
            else:
                # Keep existing keywords if no better source found
                if "keywords" not in section:
                    section["keywords"] = []

        return sections

    @staticmethod
    def merge_keywords_with_tables(
        key_terms: Dict[str, List[str]],
        subject_index: Dict[str, List[int]],
        red_keywords: Dict[int, List[str]],
        frequency_keywords: Dict[int, List[str]],
        sections: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge keywords with key terms tables as highest priority.

        Priority: key_terms > subject_index > red_keywords > frequency

        Args:
            key_terms: section_num -> [keywords] from tables
            subject_index: keyword -> [page_nums]
            red_keywords: page_num -> [keywords]
            frequency_keywords: page_num -> [keywords]
            sections: list of section dicts

        Returns:
            Updated sections list
        """
        # Build subject_index page mapping
        subject_index_by_page = {}
        for keyword, pages in subject_index.items():
            for page in pages:
                if page not in subject_index_by_page:
                    subject_index_by_page[page] = []
                subject_index_by_page[page].append(keyword)

        for section in sections:
            section_num = section["section_num"]
            page = section["page"]

            # Get keywords from all sources
            table_kw = key_terms.get(section_num, [])
            subject_kw = subject_index_by_page.get(page, [])
            red_kw = red_keywords.get(page, [])
            freq_kw = frequency_keywords.get(page, [])

            # Merge with priority: key_terms > subject_index > red > frequency
            merged = []
            seen = set()

            for keyword in table_kw:
                if keyword not in seen and is_valid_keyword(keyword):
                    merged.append(keyword)
                    seen.add(keyword)

            for keyword in subject_kw:
                if keyword not in seen and is_valid_keyword(keyword):
                    merged.append(keyword)
                    seen.add(keyword)

            for keyword in red_kw:
                if keyword not in seen and is_valid_keyword(keyword):
                    merged.append(keyword)
                    seen.add(keyword)

            for keyword in freq_kw:
                if keyword not in seen and is_valid_keyword(keyword):
                    merged.append(keyword)
                    seen.add(keyword)

            # Keep top 15 keywords
            section["keywords"] = merged[:15]
            section["keywords_by_source"] = {
                "key_terms": len(table_kw),
                "subject_index": len(subject_kw),
                "red": len(red_kw),
                "frequency": len(freq_kw),
            }

        return sections
