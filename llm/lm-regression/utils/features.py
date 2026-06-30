"""
Feature extraction utilities for source code analysis.

Provides functions to compute lexical/structural code metrics,
TF-IDF vectorization, and BPE token length estimation.
"""

import keyword
import re
import tokenize
import io

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


# ---------------------------------------------------------------------------
# Basic code metrics
# ---------------------------------------------------------------------------

def compute_code_metrics(code_str: str) -> dict:
    """
    Compute basic structural metrics from a source code string.

    Parameters
    ----------
    code_str : str
        Raw source code text.

    Returns
    -------
    dict with keys:
        - loc: lines of code (non-empty lines)
        - total_lines: total lines including blanks
        - code_size_bytes: byte length of the code string
        - max_line_length: length of the longest line
        - avg_line_length: average line length
        - num_keywords: count of Python keywords used
        - unique_tokens: approximate unique identifier count
        - vocabulary_size: Halstead-like vocabulary (unique operators + operands)
        - nesting_depth: estimated max indentation depth
    """
    if not isinstance(code_str, str) or not code_str.strip():
        return {
            "loc": 0, "total_lines": 0, "code_size_bytes": 0,
            "max_line_length": 0, "avg_line_length": 0.0,
            "num_keywords": 0, "unique_tokens": 0,
            "vocabulary_size": 0, "nesting_depth": 0,
        }

    lines = code_str.split("\n")
    non_empty_lines = [l for l in lines if l.strip()]
    line_lengths = [len(l) for l in non_empty_lines] if non_empty_lines else [0]

    # Keyword counting
    words = re.findall(r"\b[a-zA-Z_]\w*\b", code_str)
    python_keywords = set(keyword.kwlist)
    kw_count = sum(1 for w in words if w in python_keywords)

    # Unique tokens (identifiers)
    unique_words = set(words)

    # Simple operator detection
    operators = set(re.findall(r"[+\-*/%=<>!&|^~]", code_str))
    vocabulary_size = len(unique_words) + len(operators)

    # Nesting depth estimation via indentation
    depths = []
    for line in non_empty_lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        depths.append(indent)
    max_depth = max(depths) if depths else 0
    # Convert spaces to depth levels (assume 4 spaces per level, fallback to 2)
    nesting_depth = max_depth // 4 if max_depth >= 4 else max_depth // 2

    return {
        "loc": len(non_empty_lines),
        "total_lines": len(lines),
        "code_size_bytes": len(code_str.encode("utf-8", errors="replace")),
        "max_line_length": max(line_lengths),
        "avg_line_length": float(np.mean(line_lengths)),
        "num_keywords": kw_count,
        "unique_tokens": len(unique_words),
        "vocabulary_size": vocabulary_size,
        "nesting_depth": nesting_depth,
    }


def compute_code_metrics_batch(
    series: pd.Series,
    show_progress: bool = True,
) -> pd.DataFrame:
    """
    Apply compute_code_metrics to a Series of code strings.

    Parameters
    ----------
    series : pd.Series of str
    show_progress : bool

    Returns
    -------
    pd.DataFrame with one row per input, columns from compute_code_metrics.
    """
    from tqdm import tqdm

    records = []
    iterator = tqdm(series, desc="Computing code metrics") if show_progress else series
    for code in iterator:
        records.append(compute_code_metrics(code))

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# TF-IDF feature extraction
# ---------------------------------------------------------------------------

def compute_tfidf_features(
    texts: pd.Series,
    max_features: int = 5000,
    ngram_range: tuple = (1, 2),
    analyzer: str = "char_wb",
    sublinear_tf: bool = True,
) -> tuple:
    """
    Build a TF-IDF sparse feature matrix from code text.

    Parameters
    ----------
    texts : pd.Series of str
        Raw source code strings.
    max_features : int
        Maximum vocabulary size.
    ngram_range : tuple
        Range of n-grams (min_n, max_n).
    analyzer : str
        'char_wb' for character n-grams with word boundaries,
        'word' for word-level n-grams.
    sublinear_tf : bool
        Apply sublinear TF scaling (1 + log(tf)).

    Returns
    -------
    (sparse_matrix, vectorizer)
        The TF-IDF matrix and the fitted vectorizer.
    """
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=ngram_range,
        analyzer=analyzer,
        sublinear_tf=sublinear_tf,
        dtype=np.float32,
    )

    X = vectorizer.fit_transform(texts.fillna(""))
    print(f"  TF-IDF matrix shape: {X.shape}")
    print(f"  Vocabulary size: {len(vectorizer.vocabulary_)}")

    return X, vectorizer


# ---------------------------------------------------------------------------
# Tiktoken tokenization
# ---------------------------------------------------------------------------

def tokenize_with_tiktoken(
    texts: pd.Series,
    encoding_name: str = "cl100k_base",
    show_progress: bool = True,
) -> np.ndarray:
    """
    Compute BPE token lengths for each text using tiktoken.

    Parameters
    ----------
    texts : pd.Series of str
    encoding_name : str
        Tiktoken encoding name (e.g., 'cl100k_base').
    show_progress : bool

    Returns
    -------
    np.ndarray of int
        Token counts per text.
    """
    import tiktoken
    from tqdm import tqdm

    enc = tiktoken.get_encoding(encoding_name)

    lengths = []
    iterator = tqdm(texts, desc="Tokenizing with tiktoken") if show_progress else texts
    for text in iterator:
        if not isinstance(text, str):
            lengths.append(0)
        else:
            lengths.append(len(enc.encode(text, disallowed_special=())))

    return np.array(lengths, dtype=np.int32)
