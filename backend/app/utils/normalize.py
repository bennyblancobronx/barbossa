"""Text normalization utilities."""
import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison.

    - Lowercase
    - Remove parenthetical content (Deluxe), (Remaster), etc.
    - Remove bracketed content [Explicit], etc.
    - Remove punctuation
    - Collapse whitespace
    - Normalize unicode
    """
    if not text:
        return ""

    # Normalize unicode
    text = unicodedata.normalize("NFKD", text)

    # Lowercase
    text = text.lower()

    # Remove parenthetical content
    text = re.sub(r"\([^)]*\)", "", text)

    # Remove bracketed content
    text = re.sub(r"\[[^\]]*\]", "", text)

    # Remove punctuation (keep alphanumeric and spaces)
    text = re.sub(r"[^a-z0-9\s]", "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_sort_name(name: str) -> str:
    """
    Create a sort-friendly name.

    - "The Beatles" -> "Beatles, The"
    - "A Tribe Called Quest" -> "Tribe Called Quest, A"
    """
    if not name:
        return ""

    articles = ["The ", "A ", "An "]

    for article in articles:
        if name.startswith(article):
            return f"{name[len(article):]}, {article.strip()}"

    return name
