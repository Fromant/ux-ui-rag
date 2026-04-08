import re
import json
from typing import List, Dict, Any, Optional
import fitz


class PDFIndexer:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.sections: List[Dict[str, Any]] = []

    def clean_title(self, title: str) -> Optional[str]:
        """Clean and validate section title."""
        if not title:
            return None

        # Remove part indicators like (2/2), (3/3), etc. (including incomplete ones)
        title = re.sub(r'\s*\(\d+/\d*\s*$', '', title)
        title = re.sub(r'\s*\(\d+/\d+\)\s*', '', title)

        # Remove trailing punctuation that indicates sentence, not title
        title = title.rstrip('.!?;:')

        # Remove trailing hyphenation (incomplete words)
        title = re.sub(r'-\s*$', '', title)
        title = re.sub(r'-\s*\n', ' ', title)  # Join hyphenated line breaks

        # Remove content after colon if it looks like a subtitle or explanation
        if ':' in title:
            parts = title.split(':')
            if len(parts[0].strip()) > 3 and len(parts[0].strip()) < 100:
                title = parts[0].strip()

        # Remove content after comma if title is already long enough
        if ',' in title and len(title) > 60:
            parts = title.split(',')
            if len(parts[0].strip()) > 3:
                title = parts[0].strip()

        # Remove leading/trailing whitespace and normalize internal spaces
        title = ' '.join(title.split())

        # Must start with uppercase letter or digit (for numbered sections)
        if not (title[0].isupper() or title[0].isdigit()):
            return None

        # Filter out bad titles
        # 1. Too short after cleaning
        if len(title) < 3:
            return None

        # 2. Too long (likely captured too much text)
        if len(title) > 100:
            return None

        # 2b. Check for truncated words - Russian words ending mid-stem
        # Common Russian word stems - if title ends with these, it's likely truncated
        truncated_patterns = [
            r'определе$', r'отноше$', r'вычисле$', r'множе$', r'граф$',
            r'алгоритм$', r'свойств$', r'функц$', r'матриц$', r'вероятност$',
            r'дерев$', r'разбиен$', r'покрыт$', r'композ$', r'бин$',
        ]
        for pattern in truncated_patterns:
            if re.search(pattern, title.lower()):
                return None

        # General check: if title ends with 2-3 Cyrillic chars, might be truncated
        if re.search(r'[а-яё]{2,3}$', title.lower()):
            words = title.split()
            if words and len(words[-1]) < 8:
                # Check if it's a common short word or looks truncated
                last_word = words[-1].lower()
                # Short complete words are ok, but not truncated stems
                if len(last_word) <= 4 and not any(last_word.endswith(s) for s in ['ия', 'ие', 'ый', 'ой', 'ая', 'ое']):
                    return None

        # 3. Ends with common sentence fragments
        bad_endings = [
            'и далее', 'и т.д', 'и т.п', 'см.', 'см также',
            'и следствия', 'по первому', 'по второму', 'если нужно',
            'указываются', 'требуется', 'приведённом', 'данной', 'этой',
            'этом', 'другой', 'только', 'было', 'будет', 'является',
            'есть биекция', 'значит', 'значит,', 'и значит',
            'равно c', 'равно с', 'не имеет значения', 'симметрично',
        ]
        title_lower = title.lower()
        for bad in bad_endings:
            if title_lower.endswith(bad):
                return None

        # 3b. Starts with sentence-like patterns
        bad_starts = [
            'в приведённом', 'в данном', 'в этом', 'на самом деле',
            'следует отметить', 'отметим что', 'заметим что',
            'рассмотрим', 'покажем что', 'докажем что',
            'требуется ', 'следует ', 'значит ', 'поэтому ',
        ]
        for bad in bad_starts:
            if title_lower.startswith(bad):
                return None

        # 3c. Contains verb patterns that indicate sentence not title
        sentence_patterns = [
            r'требуется больше', r'не имеет значения', r'является',
            r'следует что', r'следует, что', r'значит,',
        ]
        for pattern in sentence_patterns:
            if re.search(pattern, title_lower):
                return None

        # 4. Contains obvious non-title patterns
        bad_patterns = [
            r'^и\s+\w',  # Starts with "и "
            r'^для\s+\w',  # Starts with "для "
            r'^при\s+\w',  # Starts with "при "
            r'^в\s+\w',  # Starts with "в "
            r'^на\s+\w',  # Starts with "на "
            r'^с\s+\w',  # Starts with "с " (but not specific cases)
            r'^что\s+\w',  # Starts with "что "
            r'^как\s+\w',  # Starts with "как "
            r'^[A-Z]\d\s*⊂',  # Math expressions like "R2 ⊂R"
            r'^[A-Z]\d\s*[=<>]',  # Math expressions with =, <, >
            r'⊂',  # Contains subset symbol
            r'◦',  # Contains composition symbol
            r'\(\d{4}',  # Contains year like (1826
            r'[A-Z][a-z]+ [A-Z][a-z]+ [A-Z]',  # Western name pattern "Georg Friedrich B"
        ]
        for pattern in bad_patterns:
            if re.search(pattern, title):
                return None

        # 5. Has incomplete words (ending with hyphen mid-word or truncated)
        if re.search(r'\w-\s*$', title):
            return None

        # 6. Is just a name without context (likely a random capture)
        # Single word titles that are all caps or surname pattern
        if ' ' not in title:
            # Check if it's all uppercase (like "РИМАН", "ФЛОЙД")
            if title.isupper() and len(title) < 15:
                return None

            # Check if it matches surname pattern
            if re.match(r'^[А-ЯЁ][а-яё]+$', title):
                surnames = ['риман', 'галуа', 'бине', 'капрекар', 'флойд', 'дейкстра',
                           'карно', 'хейкен', 'варшалл', 'эйлер', 'бернсайд', 'кэли',
                           'пуанкаре', 'шредер', 'кантор', 'дедекинд', 'хаусдорф']
                if title.lower() in surnames:
                    return None

        # 6b. Single generic word titles (too vague)
        generic_single = ['вычисление', 'определение', 'понятие', 'раздел', 'часть', 'тема',
                         'пример', 'следствие', 'замечание', 'утверждение', 'предложение']
        if title.lower() in generic_single and ' ' not in title:
            return None

        # 7. Contains newline artifacts
        if '\n' in title or '\r' in title:
            return None

        return title[:100]

    def extract_sections(self):
        print("Extracting sections from PDF...")
        doc = fitz.open(self.pdf_path)
        print(f"PDF has {len(doc)} pages")

        # Pattern: section number followed by title
        # Title starts with capital letter, stops at newline
        # More permissive to capture full titles
        section_pattern = re.compile(
            r'(\d+\.\d+(?:\.\d+)?)\.?\s+([А-Яа-яёЁA-Z][^\n\r]{2,200})',
            re.MULTILINE
        )

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
                section_title = self.clean_title(raw_title)
                
                if not section_title:
                    continue

                # Validate section number format - should be like 1.2, 1.2.3, etc.
                # Reject numbers with too many digits or weird formats
                sec_parts = section_num.split('.')
                if not all(p.isdigit() and 1 <= int(p) <= 999 for p in sec_parts):
                    continue
                # Reject if first part is 0 (like 0.57722)
                if sec_parts[0] == '0':
                    continue

                keywords = self._extract_keywords(text[:2000])

                self.sections.append({
                    'section_num': section_num,
                    'title': section_title,
                    'page': page_num + 1,
                    'keywords': keywords
                })

        doc.close()

        self.sections.sort(key=lambda x: (int(x['section_num'].split('.')[0]) if x['section_num'].split('.')[0].isdigit() else 0, x['section_num']))

        self._filter_toc()

        print(f"Found {len(self.sections)} sections")
        return self.sections
    
    def _filter_toc(self):
        """Filter out table of contents - keep only last occurrence of each section"""
        filtered = {}
        
        for section in self.sections:
            sec_num = section['section_num']
            filtered[sec_num] = section
        
        self.sections = list(filtered.values())
        self.sections.sort(key=lambda x: (
            int(x['section_num'].split('.')[0]) if x['section_num'].split('.')[0].isdigit() else 0, 
            x['section_num']
        ))
    
    def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r'\b[А-Яа-яёЁA-Za-z]{3,}\b', text)
        word_freq = {}
        stop_words = {
            'это', 'такой', 'который', 'является', 'имеет', 'может', 'для', 'при', 'что',
            'также', 'где', 'когда', 'этом', 'этой', 'другой', 'только', 'было', 'будет',
            'the', 'and', 'for', 'are', 'from', 'that', 'with', 'this', 'have', 'has'
        }
        # Filter out programming code artifacts
        code_keywords = {
            'def', 'yield', 'end', 'while', 'if', 'else', 'elif', 'return', 'import',
            'from', 'class', 'func', 'let', 'var', 'const', 'function', 'then', 'do',
            'loop', 'for', 'switch', 'case', 'break', 'continue', 'try', 'catch',
            'except', 'finally', 'throw', 'new', 'delete', 'print', 'input', 'open'
        }
        
        for word in words:
            word_lower = word.lower()
            if word_lower not in stop_words and word_lower not in code_keywords:
                word_freq[word_lower] = word_freq.get(word_lower, 0) + 1

        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:10]]
    
    def save(self, output_path: str):
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.sections, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(self.sections)} sections to {output_path}")
