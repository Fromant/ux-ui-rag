"""
Template-based question generator for quiz sections.

Generates diverse questions from section titles and keywords using predefined templates.
Also generates reference answers from section content.
No LLM required - runs at build time alongside keyword extraction.
"""

import random
from typing import Dict, Any, List


class QuestionTemplateGenerator:
    """Generates quiz questions using templates based on section type."""

    # Question templates by category
    DEFINITION_TEMPLATES = [
        "Что такое \"{title}\"?",
        "Дайте определение: {title}.",
        "Что понимается под термином \"{title}\"?",
        "Сформулируйте определение понятия \"{title}\".",
    ]

    UNDERSTANDING_TEMPLATES = [
        "Объясните понятие \"{title}\".",
        "Расскажите о \"{title}\".",
        "В чём суть \"{title}\"?",
        "Что вы знаете о \"{title}\"?",
        "Опишите, что такое \"{title}\".",
    ]

    KEYWORD_TEMPLATES = [
        "Как связано \"{title}\" с понятием \"{keyword}\"?",
        "Какую роль играет \"{keyword}\" в контексте \"{title}\"?",
        "Объясните связь между \"{title}\" и \"{keyword}\".",
    ]

    THEOREM_TEMPLATES = [
        "Сформулируйте: {title}.",
        "Что утверждает {title_lower}?",
        "Объясните: {title}.",
        "В чём заключается {title_lower}?",
    ]

    ALGORITHM_TEMPLATES = [
        "Опишите алгоритм: {title}.",
        "В чём суть метода \"{title}\"?",
        "Как работает {title_lower}?",
        "Опишите шаги алгоритма \"{title}\".",
    ]

    PROPERTY_TEMPLATES = [
        "Какие свойства имеет \"{title}\"?",
        "Перечислите основные свойства \"{title}\".",
        "Что характерно для \"{title}\"?",
    ]

    EXAMPLE_TEMPLATES = [
        "Приведите пример \"{title}\".",
        "Где применяется \"{title}\"?",
        "Как используется \"{title}\" на практике?",
    ]

    # Keywords that indicate section type
    THEOREM_KEYWORDS = ['теорема', 'лемма', 'утверждение', 'критерий', 'признак']
    ALGORITHM_KEYWORDS = ['алгоритм', 'метод', 'способ', 'процедура', 'правило']
    PROPERTY_KEYWORDS = ['свойство', 'свойства', 'признак']
    DEFINITION_KEYWORDS = ['определение', 'понятие', 'термин']

    def generate_questions(
        self,
        section: Dict[str, Any],
        section_text: str = "",
        num_questions: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Generate template-based questions for a section.

        Args:
            section: Section dict with 'title', 'keywords', 'section_num'
            section_text: Section content text for generating reference answers
            num_questions: Number of questions to generate (default 3)

        Returns:
            List of question dicts with 'question', 'answer', 'type', 'difficulty'
        """
        title = section.get('title', '')
        keywords = section.get('keywords', [])[:8]

        # Determine section type from title and keywords
        section_type = self._detect_section_type(title, keywords)

        # Generate diverse questions
        questions = []
        question_types_used = set()

        # Always generate at least one definition/understanding question
        questions.append(self._generate_type_question(
            title, keywords, section_text, 'definition', 'easy'
        ))
        question_types_used.add('definition')

        # Add understanding question if we need more
        if num_questions > 1:
            questions.append(self._generate_type_question(
                title, keywords, section_text, 'understanding', 'medium'
            ))
            question_types_used.add('understanding')

        # Add type-specific question
        if num_questions > 2:
            if section_type == 'theorem':
                questions.append(self._generate_type_question(
                    title, keywords, section_text, 'theorem', 'medium'
                ))
                question_types_used.add('theorem')
            elif section_type == 'algorithm':
                questions.append(self._generate_type_question(
                    title, keywords, section_text, 'algorithm', 'medium'
                ))
                question_types_used.add('algorithm')
            elif section_type == 'property':
                questions.append(self._generate_type_question(
                    title, keywords, section_text, 'property', 'medium'
                ))
                question_types_used.add('property')
            else:
                # Generic keyword-based question
                questions.append(self._generate_type_question(
                    title, keywords, section_text, 'keyword', 'medium'
                ))
                question_types_used.add('keyword')

        # Add example/application question if needed
        if num_questions > 3:
            questions.append(self._generate_type_question(
                title, keywords, section_text, 'example', 'hard'
            ))

        return questions[:num_questions]

    def _detect_section_type(self, title: str, keywords: List[str]) -> str:
        """Detect section type from title and keywords."""
        title_lower = title.lower()
        all_text = f"{title_lower} {' '.join(keywords).lower()}"

        if any(kw in all_text for kw in self.THEOREM_KEYWORDS):
            return 'theorem'
        if any(kw in all_text for kw in self.ALGORITHM_KEYWORDS):
            return 'algorithm'
        if any(kw in all_text for kw in self.PROPERTY_KEYWORDS):
            return 'property'
        if any(kw in all_text for kw in self.DEFINITION_KEYWORDS):
            return 'definition'

        return 'general'

    def _generate_type_question(
        self,
        title: str,
        keywords: List[str],
        section_text: str,
        question_type: str,
        difficulty: str,
    ) -> Dict[str, Any]:
        """Generate a question of specific type with reference answer."""
        title_lower = title.lower()

        if question_type == 'definition':
            template = random.choice(self.DEFINITION_TEMPLATES)
            question = template.format(title=title, title_lower=title_lower)
            answer = self._generate_definition_answer(title, keywords, section_text)
            return {
                "question": question,
                "answer": answer,
                "type": "definition",
                "difficulty": difficulty,
            }

        elif question_type == 'understanding':
            template = random.choice(self.UNDERSTANDING_TEMPLATES)
            question = template.format(title=title, title_lower=title_lower)
            answer = self._generate_understanding_answer(title, keywords, section_text)
            return {
                "question": question,
                "answer": answer,
                "type": "understanding",
                "difficulty": difficulty,
            }

        elif question_type == 'theorem':
            template = random.choice(self.THEOREM_TEMPLATES)
            question = template.format(title=title, title_lower=title_lower)
            answer = self._generate_theorem_answer(title, keywords, section_text)
            return {
                "question": question,
                "answer": answer,
                "type": "theorem",
                "difficulty": difficulty,
            }

        elif question_type == 'algorithm':
            template = random.choice(self.ALGORITHM_TEMPLATES)
            question = template.format(title=title, title_lower=title_lower)
            answer = self._generate_algorithm_answer(title, keywords, section_text)
            return {
                "question": question,
                "answer": answer,
                "type": "algorithm",
                "difficulty": difficulty,
            }

        elif question_type == 'property':
            template = random.choice(self.PROPERTY_TEMPLATES)
            question = template.format(title=title, title_lower=title_lower)
            answer = self._generate_property_answer(title, keywords, section_text)
            return {
                "question": question,
                "answer": answer,
                "type": "property",
                "difficulty": difficulty,
            }

        elif question_type == 'keyword' and keywords:
            # Generate question using a keyword
            keyword = random.choice(keywords[:5])
            template = random.choice(self.KEYWORD_TEMPLATES)
            question = template.format(title=title, keyword=keyword)
            answer = self._generate_keyword_answer(title, keyword, keywords, section_text)
            return {
                "question": question,
                "answer": answer,
                "type": "understanding",
                "difficulty": difficulty,
            }

        elif question_type == 'example':
            template = random.choice(self.EXAMPLE_TEMPLATES)
            question = template.format(title=title, title_lower=title_lower)
            answer = self._generate_example_answer(title, keywords, section_text)
            return {
                "question": question,
                "answer": answer,
                "type": "example",
                "difficulty": difficulty,
            }

        # Fallback
        return {
            "question": f"Что вы знаете о \"{title}\"?",
            "answer": self._generate_fallback_answer(title, keywords, section_text),
            "type": "understanding",
            "difficulty": "medium",
        }

    # ==================== ANSWER GENERATION METHODS ====================

    def _generate_definition_answer(self, title: str, keywords: List[str], section_text: str) -> str:
        """Generate reference answer for definition-type questions."""
        answer_parts = [f"{title} - "]
        
        # Extract first meaningful sentence from section text if available
        if section_text:
            sentences = section_text.split('. ')
            for sentence in sentences[:3]:
                sentence = sentence.strip()
                if len(sentence) > 20 and title.lower() in sentence.lower():
                    answer_parts.append(sentence)
                    break
        
        # Add keywords as context
        if keywords:
            answer_parts.append(
                f"Ключевые понятия: {', '.join(keywords[:5])}."
            )
        
        return '. '.join(answer_parts)

    def _generate_understanding_answer(self, title: str, keywords: List[str], section_text: str) -> str:
        """Generate reference answer for understanding-type questions."""
        answer_parts = []
        
        # Try to extract context from section text
        if section_text and len(section_text) > 100:
            # Take first 2-3 sentences as overview
            sentences = section_text.split('. ')
            overview = '. '.join(sentences[:3])
            if len(overview) > 50:
                answer_parts.append(overview)
        
        # Fallback to title + keywords
        if not answer_parts:
            answer_parts.append(f"Раздел \"{title}\" описывает ключевые понятия:")
            if keywords:
                answer_parts.append(', '.join(keywords[:8]))
        
        return '. '.join(answer_parts)

    def _generate_theorem_answer(self, title: str, keywords: List[str], section_text: str) -> str:
        """Generate reference answer for theorem-type questions."""
        answer_parts = []
        
        # Start with theorem name
        answer_parts.append(f"{title} утверждает, что...")
        
        # Try to extract theorem statement
        if section_text:
            # Look for sentences with "если", "то", "тогда"
            sentences = section_text.split('. ')
            for sentence in sentences[:5]:
                sentence = sentence.strip()
                if any(word in sentence.lower() for word in ['если', 'то', 'тогда', 'следует']):
                    answer_parts.append(sentence)
                    break
        
        # Add conditions/context
        if keywords:
            answer_parts.append(
                f"Связанные понятия: {', '.join(keywords[:5])}."
            )
        
        return '. '.join(answer_parts)

    def _generate_algorithm_answer(self, title: str, keywords: List[str], section_text: str) -> str:
        """Generate reference answer for algorithm-type questions."""
        answer_parts = []
        
        # Start with algorithm description
        answer_parts.append(f"{title} - это алгоритм, который")
        
        # Try to extract steps or description
        if section_text:
            # Look for numbered steps or "шаг" mentions
            lines = section_text.split('\n')
            steps = [line.strip() for line in lines if line.strip() and len(line) > 20][:3]
            if steps:
                answer_parts.append(':')
                answer_parts.extend(steps[:3])
        
        # Add keywords
        if keywords:
            answer_parts.append(
                f"Использует понятия: {', '.join(keywords[:5])}."
            )
        
        return '. '.join(answer_parts)

    def _generate_property_answer(self, title: str, keywords: List[str], section_text: str) -> str:
        """Generate reference answer for property-type questions."""
        answer_parts = []
        
        # Start with property introduction
        answer_parts.append(f"{title} имеет следующие характеристики:")
        
        # Try to extract property descriptions
        if section_text:
            sentences = section_text.split('. ')
            for sentence in sentences[:4]:
                sentence = sentence.strip()
                if len(sentence) > 30:
                    answer_parts.append(sentence)
        
        # Add keywords
        if keywords:
            answer_parts.append(
                f"Связанные свойства: {', '.join(keywords[:5])}."
            )
        
        return '. '.join(answer_parts)

    def _generate_keyword_answer(self, title: str, keyword: str, keywords: List[str], section_text: str) -> str:
        """Generate reference answer for keyword relationship questions."""
        answer_parts = []
        
        # Explain relationship
        answer_parts.append(f"\"{title}\" связано с \"{keyword}\" следующим образом:")
        
        # Try to find context in section text
        if section_text:
            sentences = section_text.split('. ')
            for sentence in sentences[:5]:
                sentence = sentence.strip()
                if keyword.lower() in sentence.lower() and len(sentence) > 30:
                    answer_parts.append(sentence)
                    break
        
        # Add context with other keywords
        other_keywords = [kw for kw in keywords[:5] if kw.lower() != keyword.lower()]
        if other_keywords:
            answer_parts.append(
                f"Также связаны с: {', '.join(other_keywords)}."
            )
        
        return '. '.join(answer_parts)

    def _generate_example_answer(self, title: str, keywords: List[str], section_text: str) -> str:
        """Generate reference answer for example-type questions."""
        answer_parts = []
        
        # Start with example introduction
        answer_parts.append(f"Примеры применения \"{title}\":")
        
        # Try to extract examples from section text
        if section_text:
            # Look for sentences with "например", "пример"
            sentences = section_text.split('. ')
            for sentence in sentences:
                sentence = sentence.strip()
                if any(word in sentence.lower() for word in ['например', 'пример', 'допустим']):
                    answer_parts.append(sentence)
                    if len(answer_parts) >= 3:
                        break
        
        # Fallback to keywords
        if len(answer_parts) < 2 and keywords:
            answer_parts.append(
                f"Используется с понятиями: {', '.join(keywords[:6])}."
            )
        
        return '. '.join(answer_parts)

    def _generate_fallback_answer(self, title: str, keywords: List[str], section_text: str) -> str:
        """Generate fallback reference answer when specific type is unknown."""
        answer_parts = []
        
        # Start with title
        answer_parts.append(f"{title}.")
        
        # Add section text summary if available
        if section_text and len(section_text) > 100:
            sentences = section_text.split('. ')
            summary = '. '.join(sentences[:2])
            if len(summary) > 50:
                answer_parts.append(summary)
        
        # Add keywords
        if keywords:
            answer_parts.append(
                f"Ключевые понятия: {', '.join(keywords[:8])}."
            )
        
        return '. '.join(answer_parts)
