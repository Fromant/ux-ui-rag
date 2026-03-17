import re
import json
import os
from pathlib import Path
from typing import List, Dict, Any
import fitz


class PDFIndexer:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.sections: List[Dict[str, Any]] = []
        
    def extract_sections(self):
        print("Extracting sections from PDF...")
        doc = fitz.open(self.pdf_path)
        print(f"PDF has {len(doc)} pages")
        
        section_pattern = re.compile(
            r'(\d+\.\d+(?:\.\d+)?)\.?\s*([А-Яа-яёЁA-Z][^\n]{2,120})',
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
                section_title = match.group(2).strip()[:100]
                
                if len(section_title) < 3:
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
        
        print(f"Found {len(self.sections)} sections")
        return self.sections
    
    def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r'\b[А-Яа-яёЁA-Za-z]{3,}\b', text)
        word_freq = {}
        stop_words = {
            'это', 'такой', 'который', 'является', 'имеет', 'может', 'для', 'при', 'что',
            'также', 'где', 'когда', 'этом', 'этой', 'другой', 'только', 'было', 'будет',
            'the', 'and', 'for', 'are', 'from', 'that', 'with', 'this', 'have', 'has'
        }
        for word in words:
            word_lower = word.lower()
            if word_lower not in stop_words:
                word_freq[word_lower] = word_freq.get(word_lower, 0) + 1
        
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:10]]
    
    def save(self, output_path: str):
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.sections, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(self.sections)} sections to {output_path}")


def main():
    indexer = PDFIndexer('books/DM2024.pdf')
    sections = indexer.extract_sections()
    indexer.save('data/sections_index.json')


if __name__ == '__main__':
    main()
