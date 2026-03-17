import json
import re
from typing import List, Dict, Any
import numpy as np


class SearchResult:
    def __init__(self, section_num: str, title: str, page: int, score: float, keywords: List[str]):
        self.section_num = section_num
        self.title = title
        self.page = page
        self.score = score
        self.keywords = keywords
        self.pages = []


class BM25Search:
    def __init__(self, sections: List[Dict[str, Any]]):
        self.sections = sections
        self.corpus = [f"{s['title']} {' '.join(s.get('keywords', []))}" for s in sections]
        self._build_index()
    
    def _build_index(self):
        from rank_bm25 import BM25Okapi
        
        tokenized_corpus = []
        for doc in self.corpus:
            tokens = re.findall(r'\b\w+\b', doc.lower())
            tokenized_corpus.append(tokens)
        
        self.bm25 = BM25Okapi(tokenized_corpus)
        print("BM25 index built")
    
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        query_tokens = re.findall(r'\b\w+\b', query.lower())
        scores = self.bm25.get_scores(query_tokens)
        
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                s = self.sections[idx]
                result = SearchResult(
                    section_num=s['section_num'],
                    title=s['title'],
                    page=s['page'],
                    score=float(scores[idx]),
                    keywords=s.get('keywords', [])
                )
                result.pages = self._get_page_range(idx)
                results.append(result)
        
        return results
    
    def _get_page_range(self, idx: int, range_size: int = 2) -> List[int]:
        """Get page range: main page in the middle, but return in order: main, then surrounding"""
        current_page = self.sections[idx]['page']
        
        pages = [current_page]
        for i in range(1, range_size + 1):
            pages.append(current_page - i)
            pages.append(current_page + i)
        
        return [p for p in pages if p >= 1]


def load_index(path: str = 'data/sections_index.json') -> List[Dict[str, Any]]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_search_engine(sections: List[Dict[str, Any]] = None) -> BM25Search:
    if sections is None:
        sections = load_index()
    return BM25Search(sections)
