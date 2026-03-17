import json
import random
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class Question:
    id: str
    text: str
    section_num: str
    title: str
    page: int
    pages: List[int]
    keywords: List[str]


class QuestionGenerator:
    def __init__(self, sections: List[Dict[str, Any]]):
        self.sections = sections
        self.questions: List[Question] = []
    
    def generate(self, questions_per_section: int = 1) -> List[Question]:
        self.questions = []
        question_id = 0
        
        templates = [
            "Что вы знаете о {topic}?",
            "Расскажите о {topic}",
            "Дайте определение {topic}",
            "Какие свойства имеет {topic}?",
            "Объясните {topic}",
        ]
        
        for section in self.sections:
            if not section.get('title'):
                continue
            
            topic = section['title']
            page = section['page']
            
            for _ in range(questions_per_section):
                template = random.choice(templates)
                question_text = template.format(topic=topic)
                
                pages = self._get_page_range(page)
                
                self.questions.append(Question(
                    id=f"q_{question_id}",
                    text=question_text,
                    section_num=section['section_num'],
                    title=section['title'],
                    page=page,
                    pages=pages,
                    keywords=section.get('keywords', [])
                ))
                question_id += 1
        
        random.shuffle(self.questions)
        return self.questions
    
    def _get_page_range(self, page: int, range_size: int = 2) -> List[int]:
        min_page = max(1, page - range_size)
        max_page = page + range_size
        return list(range(min_page, max_page + 1))
    
    def get_by_id(self, question_id: str) -> Question:
        for q in self.questions:
            if q.id == question_id:
                return q
        return None
    
    def save(self, path: str):
        data = [
            {
                'id': q.id,
                'text': q.text,
                'section_num': q.section_num,
                'title': q.title,
                'page': q.page,
                'pages': q.pages,
                'keywords': q.keywords
            }
            for q in self.questions
        ]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.questions = [
            Question(
                id=d['id'],
                text=d['text'],
                section_num=d['section_num'],
                title=d['title'],
                page=d['page'],
                pages=d['pages'],
                keywords=d['keywords']
            )
            for d in data
        ]


def load_questions(path: str = 'data/questions_simple.json') -> List[Question]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [
            Question(
                id=d['id'],
                text=d['text'],
                section_num=d['section_num'],
                title=d['title'],
                page=d['page'],
                pages=d['pages'],
                keywords=d['keywords']
            )
            for d in data
        ]
    except:
        return []
