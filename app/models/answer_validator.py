"""
Answer validator using semantic similarity and keyword matching.

Validates student answers against:
1. Reference answer (from LLM-generated questions)
2. Section keywords (from subject index + red text)
3. Section title

Combines multiple scoring strategies for robust validation.
"""

from typing import List, Tuple, Dict, Optional
from sentence_transformers import SentenceTransformer, util
import torch
import re


class AnswerValidator:
    """
    Validates student answers using semantic similarity + keyword matching.
    Uses multilingual sentence transformers for Russian language support.
    """

    MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, model_name: str = MODEL_NAME, device: Optional[str] = None):
        self.model = None
        self.model_name = model_name

        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = device

    def load_model(self):
        """Load the sentence transformer model."""
        if self.model is None:
            print(f"Loading sentence transformer model: {self.model_name} on {self.device}...")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            print("Model loaded successfully!")

    def validate_answer(
        self,
        student_answer: str,
        question: str,
        reference_answer: str,
        section_title: str,
        keywords: List[str] = None,
    ) -> Tuple[bool, float, Dict]:
        """
        Validate a student's answer.

        Uses multiple strategies:
        1. Semantic similarity between student answer and reference answer
        2. Keyword overlap (does student answer contain key terms?)
        3. Question relevance (does answer address the question?)

        Args:
            student_answer: Student's answer text
            question: The question that was asked
            reference_answer: Correct reference answer
            section_title: Title of the section
            keywords: Keywords from the section

        Returns:
            Tuple of (is_correct, similarity_score, details_dict)
        """
        if self.model is None:
            self.load_model()

        # Strategy 1: Semantic similarity (student vs reference)
        semantic_score = self._semantic_similarity(
            student_answer, reference_answer
        )

        # Strategy 2: Keyword matching
        keyword_score = self._keyword_overlap(
            student_answer, keywords or []
        )

        # Strategy 3: Question relevance
        relevance_score = self._question_relevance(
            student_answer, question
        )

        # Combined score (weighted)
        # Semantic: 50%, Keywords: 30%, Relevance: 20%
        combined_score = (
            semantic_score * 0.5 +
            keyword_score * 0.3 +
            relevance_score * 0.2
        )

        # Determine correctness
        is_correct = combined_score >= 0.35

        # Additional checks
        answer_length = len(student_answer.strip())
        too_short = answer_length < 10

        # If answer is too short, require higher score
        if too_short:
            is_correct = combined_score >= 0.5

        # Find matched keywords for feedback
        matched_keywords = self._get_matched_keywords(
            student_answer, keywords or []
        )

        details = {
            "combined_score": round(combined_score, 4),
            "semantic_score": round(semantic_score, 4),
            "keyword_score": round(keyword_score, 4),
            "relevance_score": round(relevance_score, 4),
            "confidence": self._get_confidence_level(combined_score),
            "matched_keywords": matched_keywords,
            "answer_length": answer_length,
            "too_short": too_short,
        }

        return is_correct, combined_score, details

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts."""
        if not text1 or not text2:
            return 0.0

        with torch.no_grad():
            embedding1 = self.model.encode(
                text1, convert_to_tensor=True, show_progress_bar=False
            )
            embedding2 = self.model.encode(
                text2, convert_to_tensor=True, show_progress_bar=False
            )

        return util.cos_sim(embedding1, embedding2).item()

    def _keyword_overlap(
        self, student_answer: str, keywords: List[str]
    ) -> float:
        """
        Calculate keyword overlap score.

        Returns fraction of keywords found in student answer.
        """
        if not keywords:
            return 0.5  # Neutral if no keywords

        answer_lower = student_answer.lower()
        matched = sum(
            1 for kw in keywords
            if kw.lower() in answer_lower or self._word_stem(kw).lower() in answer_lower
        )

        # Score based on coverage
        coverage = matched / len(keywords)

        # Scale: 0 keywords = 0, 30% = 0.3, 60%+ = 1.0
        return min(1.0, coverage * 1.5)

    def _question_relevance(self, student_answer: str, question: str) -> float:
        """Check if student answer is relevant to the question."""
        if not question or not student_answer:
            return 0.0

        # Extract key terms from question
        question_terms = re.findall(r'[А-Яа-яёЁA-Za-z]{4,}', question)

        # Check if answer contains question terms
        answer_lower = student_answer.lower()
        matched_terms = sum(
            1 for term in question_terms
            if term.lower() in answer_lower
        )

        if question_terms:
            return matched_terms / len(question_terms)
        return 0.5

    def _word_stem(self, word: str) -> str:
        """Simple word stemming (removes common Russian endings)."""
        endings = ['ия', 'ие', 'ый', 'ой', 'ая', 'ое', 'ые',
                   'ого', 'ему', 'ыми', 'ими', 'ться', 'ется']

        word_lower = word.lower()
        for ending in endings:
            if word_lower.endswith(ending) and len(word_lower) > len(ending) + 2:
                return word_lower[:-len(ending)]

        return word_lower

    def _get_matched_keywords(
        self, student_answer: str, keywords: List[str]
    ) -> List[str]:
        """Get list of keywords found in student answer."""
        answer_lower = student_answer.lower()
        matched = []

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in answer_lower or self._word_stem(kw).lower() in answer_lower:
                matched.append(kw)

        return matched

    def _get_confidence_level(self, score: float) -> str:
        """Get confidence level based on combined score."""
        if score >= 0.6:
            return "high"
        elif score >= 0.45:
            return "medium"
        elif score >= 0.35:
            return "low"
        else:
            return "very_low"


def initialize_validator():
    """Initialize the validator (call during app startup)."""
    validator = AnswerValidator()
    validator.load_model()
    return validator
