from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer, util
import torch


class AnswerValidator:
    """
    Validates student answers using semantic similarity.
    Uses multilingual sentence transformers to compare answers with reference content.
    """
    
    # Model that supports Russian and other languages
    MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
    
    def __init__(self, model_name: str = MODEL_NAME, device: Optional[str] = None):
        """
        Initialize the answer validator with a sentence transformer model.
        
        Args:
            model_name: Name of the sentence transformer model to use
            device: Device to run model on ('cpu', 'cuda', etc.)
        """
        self.model = None
        self.model_name = model_name
        
        # Auto-detect device
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
        reference_text: str,
        section_title: str,
        keywords: List[str] = None
    ) -> Tuple[bool, float, dict]:
        """
        Validate a student's answer against reference content.
        
        Args:
            student_answer: The student's answer text
            reference_text: Reference text from the textbook section
            section_title: Title of the section (used as additional context)
            keywords: Optional list of keywords from the section
            
        Returns:
            Tuple of (is_correct, similarity_score, details_dict)
        """
        if self.model is None:
            self.load_model()
        
        # Build reference text: combine title, keywords, and reference content
        reference_parts = [section_title]
        if keywords:
            reference_parts.extend(keywords[:5])  # Top 5 keywords
        reference_parts.append(reference_text)
        full_reference = " ".join(reference_parts)
        
        # Encode both texts
        with torch.no_grad():
            answer_embedding = self.model.encode(
                student_answer, 
                convert_to_tensor=True,
                show_progress_bar=False
            )
            reference_embedding = self.model.encode(
                full_reference,
                convert_to_tensor=True,
                show_progress_bar=False
            )
        
        # Calculate cosine similarity
        similarity = util.cos_sim(answer_embedding, reference_embedding).item()
        
        # Determine if answer is correct based on threshold
        # Thresholds:
        # - >= 0.5: Very good match (definitely correct)
        # - >= 0.35: Good match (likely correct)
        # - >= 0.25: Some relevance (partially correct)
        # - < 0.25: Poor match (incorrect)
        
        is_correct = similarity >= 0.35
        
        details = {
            "similarity_score": round(similarity, 4),
            "threshold": 0.35,
            "confidence": self._get_confidence_level(similarity),
            "reference_length": len(full_reference),
            "answer_length": len(student_answer)
        }
        
        return is_correct, similarity, details

    def _get_confidence_level(self, similarity: float) -> str:
        """Get confidence level based on similarity score."""
        if similarity >= 0.5:
            return "high"
        elif similarity >= 0.35:
            return "medium"
        elif similarity >= 0.25:
            return "low"
        else:
            return "very_low"


def initialize_validator():
    """Initialize the validator (call during app startup)."""
    validator = AnswerValidator()
    validator.load_model()
    return validator
