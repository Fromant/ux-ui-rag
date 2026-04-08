"""
Text cleaning utilities for PDF text extraction.

Handles common PDF text extraction artifacts:
- Hyphenated words split across lines
- Truncated word stems
- Code artifacts
- Language-specific stopwords
"""

import re
from typing import Set, List


# Russian stopwords - comprehensive list
RUSSIAN_STOPWORDS = {
    # Basic stopwords
    'это', 'такой', 'который', 'является', 'имеет', 'может', 'для', 'при', 'что',
    'также', 'где', 'когда', 'этом', 'этой', 'другой', 'только', 'было', 'будет',
    'как', 'так', 'все', 'всё', 'весь', 'вся', 'всего', 'всей', 'всем', 'всеми',
    'каждый', 'каждая', 'каждое', 'каждые', 'любой', 'любые',
    'или', 'и', 'а', 'но', 'же', 'бы', 'ли', 'если', 'то', 'чем', 'чем',
    'о', 'об', 'от', 'до', 'из', 'за', 'на', 'в', 'с', 'у', 'к', 'по',
    'его', 'ее', 'их', 'мой', 'твой', 'наш', 'ваш', 'свой',
    'он', 'она', 'оно', 'они', 'мы', 'вы', 'я', 'ты',
    'мне', 'тебе', 'ему', 'ей', 'нам', 'вам', 'им',
    'меня', 'тебя', 'его', 'ее', 'нас', 'вас', 'их',
    'мной', 'тобой', 'ним', 'ней', 'ними', 'вами',
    'без', 'через', 'после', 'перед', 'между', 'под', 'над',
    'уже', 'еще', 'более', 'менее', 'очень', 'просто', 'даже',
    'тут', 'там', 'здесь', 'туда', 'сюда', 'оттуда', 'отсюда',
    'потому', 'поэтому', 'зачем', 'почему', 'сколько', 'столько',
    'кого', 'кому', 'кем', 'чем', 'кого', 'что',
    # Common academic words that aren't useful as keywords
    'пусть', 'тогда', 'значит', 'следовательно', 'например', 'вообще',
    'поэтому', 'потому', 'именно', 'хотя', 'однако', 'итак',
    'ввиду', 'вследствие', 'несмотря', 'вроде', 'типа',
    'является', 'являются', 'называется', 'называются',
    'рассмотрим', 'получим', 'заметим', 'отметим', 'покажем',
    # English stopwords
    'the', 'and', 'for', 'are', 'from', 'that', 'with', 'this', 'have', 'has',
    'are', 'were', 'been', 'being', 'is', 'am', 'was', 'be',
    'of', 'in', 'to', 'by', 'on', 'at', 'an',
    'it', 'its', 'their', 'them', 'they', 'these', 'those',
    'not', 'no', 'nor', 'so', 'if', 'then', 'than', 'too', 'very',
    'can', 'will', 'just', 'should', 'now',
}

# Programming language keywords that appear in pseudocode
CODE_KEYWORDS = {
    'def', 'yield', 'end', 'while', 'if', 'else', 'elif', 'return', 'import',
    'from', 'class', 'func', 'let', 'var', 'const', 'function', 'then', 'do',
    'loop', 'switch', 'case', 'break', 'continue', 'try', 'catch',
    'except', 'finally', 'throw', 'new', 'delete', 'print', 'input', 'open',
    'div', 'mod', 'nil', 'null', 'true', 'false', 'void', 'int', 'float',
    'string', 'bool', 'char', 'double', 'long', 'short', 'unsigned', 'signed',
}

# Common Russian word endings - helps detect truncated words
COMMON_RUSSIAN_ENDINGS = {
    'ение', 'ание', 'ость', 'ство', 'ние', 'тие', 'ция', 'ция',
    'ный', 'ной', 'ная', 'ное', 'ные', 'тые',
    'ить', 'ать', 'ять', 'еть', 'уть', 'оть',
    'ого', 'его', 'ому', 'ему', 'ыми', 'ими',
    'ция', 'кция', 'кция', 'ться', 'ется', 'ются',
}


def is_truncated_word(word: str) -> bool:
    """
    Check if a word looks truncated (e.g., from hyphenation in PDF).

    Examples: 'множе' instead of 'множество', 'отно' instead of 'отношение'
    """
    if len(word) < 5:
        return False

    word_lower = word.lower()

    # Check if word ends with common Russian stem that's incomplete
    truncated_stems = {
        'множе', 'отно', 'отноше', 'вычисле', 'определе', 'множе',
        'свойст', 'алгоритм', 'граф', 'функц', 'матриц', 'вероятност',
        'дерев', 'разбиен', 'покрыт', 'композ', 'бин', 'послед',
        'отношен', 'определен', 'вычислен', 'преобразова', 'преобразован',
        'эквивалентн', 'непрерывн', 'дифференци', 'интегральн',
    }

    # Direct stem match
    if word_lower in truncated_stems:
        return True

    # Check if word ends mid-stem (less than full word)
    # Common pattern: 5-8 letters that are clearly not complete words
    if 5 <= len(word) <= 8:
        # Ends with consonant cluster (rare in complete Russian words)
        if re.match(r'.*[бвгджзклмнпрстфхцчшщ]{3,}$', word_lower):
            return True
        # Ends with typical incomplete stem
        for ending in COMMON_RUSSIAN_ENDINGS:
            if word_lower.endswith(ending[:len(ending)//2]):
                # Only first half of ending - likely truncated
                if not word_lower.endswith(ending):
                    return True

    return False


def is_code_artifact(word: str) -> bool:
    """Check if word is likely a programming artifact."""
    word_lower = word.lower()
    return word_lower in CODE_KEYWORDS


def is_valid_keyword(word: str, min_length: int = 3) -> bool:
    """
    Check if a word is suitable as a keyword.

    Filters out:
    - Too short words
    - Stopwords
    - Code artifacts
    - Truncated words
    - Pure numbers
    - Mixed garbage
    """
    if len(word) < min_length:
        return False

    word_lower = word.lower()

    # Skip stopwords
    if word_lower in RUSSIAN_STOPWORDS:
        return False

    # Skip code artifacts
    if is_code_artifact(word):
        return False

    # Skip truncated words
    if is_truncated_word(word):
        return False

    # Skip pure numbers
    if word.isdigit():
        return False

    # Skip section numbers
    if re.match(r'^\d+\.\d+', word):
        return False

    # Must contain at least one letter
    if not re.search(r'[А-Яа-яёЁA-Za-z]', word):
        return False

    # Skip very long words (likely concatenated)
    if len(word) > 50:
        return False

    # Skip words with mixed character sets (likely artifacts)
    # e.g., "abc123xyz" or "текст123more"
    has_cyrillic = bool(re.search(r'[А-Яа-яёЁ]', word))
    has_latin = bool(re.search(r'[A-Za-z]', word))
    has_digits = bool(re.search(r'\d', word))

    # If has all three, likely artifact
    if has_cyrillic and has_latin and has_digits:
        return False

    return True


def clean_text_for_keywords(text: str) -> str:
    """
    Clean text extracted from PDF to remove common artifacts.

    Handles:
    - Hyphenated line breaks: "множе-\nство" -> "множество"
    - Extra whitespace
    - Common PDF artifacts
    """
    # Fix hyphenated line breaks
    # Pattern: word-\n followed by continuation
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def extract_keywords_from_text(text: str, top_k: int = 10) -> List[str]:
    """
    Extract keywords from text using frequency analysis.

    Applies all cleaning and filtering rules.
    """
    # Clean text first
    text = clean_text_for_keywords(text)

    # Extract words (3+ letters, Cyrillic or Latin)
    words = re.findall(r'\b[А-Яа-яёЁA-Za-z]{3,}\b', text)

    # Count frequencies
    word_freq = {}
    for word in words:
        word_lower = word.lower()
        if is_valid_keyword(word):
            word_freq[word_lower] = word_freq.get(word_lower, 0) + 1

    # Sort by frequency
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    # Return top-k
    return [w[0] for w in sorted_words[:top_k]]
