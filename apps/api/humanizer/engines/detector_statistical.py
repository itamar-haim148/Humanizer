"""Statistical AI-detector (12 metrics).

No machine-learning models, no external APIs. Each metric is a pure function
of the input text and a small bundled frequency list. The fusion that turns
the 12 sub-scores into a single ai_probability lives in `pipeline.py`.

Ported / adapted from the heuristic detector in
rudra496/StealthHumanizer (MIT).

The 12 metrics:

  Part 1 (US-008)
    1. perplexity_proxy   — average inverse-rank score from freq list
    2. burstiness         — stdev / mean of sentence word counts
    3. avg_sentence_length
    4. sentence_length_stdev

  Part 2 (US-009)
    5. ai_phrase_density          — share of AI-typical phrases/words
    6. passive_voice_ratio        — EN: be+pp regex; HE: binyan markers
    7. transition_word_frequency

  Part 3 (US-010)
    8. vocab_diversity            — type-token ratio
    9. hedging_ratio
   10. sentence_start_diversity
   11. quantifier_overuse
   12. pronoun_pattern_score
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Literal

Language = Literal["en", "he"]

_DATA_DIR = Path(__file__).parent / "data"
_FREQ_EN_PATH = _DATA_DIR / "freq_en.txt"
_FREQ_HE_PATH = _DATA_DIR / "freq_he.txt"

# Phrase / AI-vocabulary lookups (reused from lexical engines).
_AI_EN_PATH = Path(__file__).parent / "ai_phrases" / "en.json"
_AI_HE_PATH = Path(__file__).parent / "ai_phrases" / "he.json"


# ---------------------------------------------------------------------------
# Lazy resource loaders (frequency lists are large)
# ---------------------------------------------------------------------------


def _load_freq(path: Path) -> dict[str, int]:
    if not path.exists():
        # Allow startup even before US-008 freq lists are seeded.
        return {}
    table: dict[str, int] = {}
    with path.open(encoding="utf-8") as f:
        for rank, line in enumerate(f, start=1):
            word = line.strip().lower()
            if word:
                table[word] = rank
    return table


def _load_ai(path: Path) -> tuple[set[str], list[str]]:
    if not path.exists():
        return set(), []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    words = set(data.get("single_words", {}).keys())
    phrases = list(data.get("phrases", {}).keys())
    return words, phrases


_FREQ_EN = _load_freq(_FREQ_EN_PATH)
_FREQ_HE = _load_freq(_FREQ_HE_PATH)
_AI_WORDS_EN, _AI_PHRASES_EN = _load_ai(_AI_EN_PATH)
_AI_WORDS_HE, _AI_PHRASES_HE = _load_ai(_AI_HE_PATH)


# ---------------------------------------------------------------------------
# Language packs
# ---------------------------------------------------------------------------


_TRANSITIONS_EN = {
    "however", "moreover", "furthermore", "additionally", "consequently",
    "nevertheless", "nonetheless", "subsequently", "therefore", "thus",
    "hence", "indeed", "specifically", "particularly", "essentially",
}

_TRANSITIONS_HE = {
    "לפיכך", "בנוסף", "יתרה", "אולם", "ברם", "אומנם", "מאידך", "מכאן",
    "ולכן", "כך", "אכן", "במיוחד", "בפרט",
}

_HEDGING_EN = {
    "might", "could", "may", "perhaps", "possibly", "seemingly", "arguably",
    "presumably", "likely", "potentially", "apparently", "supposedly",
}

_HEDGING_HE = {
    "אולי", "ייתכן", "כנראה", "ככל", "כביכול", "לכאורה", "כפי", "נראה",
    "ייתכן", "עשוי", "עשויה", "יתכן",
}

_QUANTIFIERS_EN = {
    "many", "several", "various", "numerous", "multiple", "a lot",
    "a few", "several", "plenty", "myriad", "plethora",
}

_QUANTIFIERS_HE = {
    "רבים", "רבות", "מספר", "כמה", "מגוון", "שונים", "שונות", "מרובים",
    "המוני", "המון",
}

_PRONOUNS_EN = {
    "i", "we", "us", "our", "you", "they", "them", "their", "it", "its",
    "he", "she", "him", "her", "his", "hers",
}

_PRONOUNS_HE = {
    "אני", "אנחנו", "אנו", "אתה", "את", "אתם", "אתן", "הוא", "היא",
    "הם", "הן", "שלי", "שלנו", "שלך", "שלו", "שלה", "שלהם", "שלהן",
}

# EN passive voice: be-verb + past participle (regular -ed or common irregulars).
_BE_VERBS = r"(am|is|are|was|were|be|been|being)"
_PP = r"[A-Za-z]+(ed|en|own|orn|ought|ought|ought|aught|ade|one)"
_PASSIVE_EN_RE = re.compile(rf"\b{_BE_VERBS}\s+{_PP}\b", re.IGNORECASE)

# HE binyan markers (very rough): נפעל (nif'al), פֻעַל (pu'al), הֻפְעַל (huf'al)
# We approximate by looking for words starting with "נ" + 3 letters or "הו" + ...
_PASSIVE_HE_RE = re.compile(r"\b(?:נ[\u05D0-\u05EA]{3,5}|הו[\u05D0-\u05EA]{2,4})\b")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SENTENCE_RE = re.compile(r"[.!?]+\s+")
_WORD_EN_RE = re.compile(r"[A-Za-z']+")
_WORD_HE_RE = re.compile(r"[\u05D0-\u05EA]+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def _words(text: str, language: Language) -> list[str]:
    pattern = _WORD_EN_RE if language == "en" else _WORD_HE_RE
    return [w.lower() for w in pattern.findall(text)]


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _normalize(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


# ---------------------------------------------------------------------------
# Part 1
# ---------------------------------------------------------------------------


def compute_part1(text: str, language: Language) -> dict[str, float]:
    sentences = _sentences(text)
    words = _words(text, language)
    if not words:
        return {
            "perplexity_proxy": 0.0,
            "perplexity_sub": 0.0,
            "burstiness": 0.0,
            "burstiness_sub": 1.0,  # No words → looks AI-like.
            "avg_sentence_length": 0.0,
            "sentence_length_stdev": 0.0,
        }

    # Perplexity proxy: average rank in frequency list, normalized.
    # AI text tends to use higher-rank (more common) words → smaller rank,
    # i.e. *lower* perplexity → *higher* AI score.
    freq = _FREQ_EN if language == "en" else _FREQ_HE
    if freq:
        ranks = [freq.get(w, len(freq) + 1) for w in words]
        avg_rank = sum(ranks) / len(ranks)
        # Log-scale: lower avg_rank → higher AI-likelihood
        proxy = math.log(avg_rank + 1) / math.log(len(freq) + 2)
        # Sub-score: invert (low proxy = high AI prob).
        perplexity_sub = 1.0 - proxy
    else:
        proxy = 0.5
        perplexity_sub = 0.5

    counts = [len(_words(s, language)) for s in sentences] or [len(words)]
    n = len(counts)
    mean = sum(counts) / n
    var = sum((c - mean) ** 2 for c in counts) / n
    stdev = var ** 0.5
    burst = _safe_div(stdev, mean)
    # Low burstiness (< 0.3) → AI-like; high (>= 0.8) → human-like.
    burst_sub = 1.0 - _normalize(burst, 0.3, 0.9)

    return {
        "perplexity_proxy": float(proxy),
        "perplexity_sub": float(perplexity_sub),
        "burstiness": float(burst),
        "burstiness_sub": float(burst_sub),
        "avg_sentence_length": float(mean),
        "sentence_length_stdev": float(stdev),
    }


# ---------------------------------------------------------------------------
# Part 2
# ---------------------------------------------------------------------------


def compute_part2(text: str, language: Language) -> dict[str, float]:
    words = _words(text, language)
    sentences = _sentences(text)
    if not words:
        return {
            "ai_phrase_density": 0.0,
            "ai_phrase_density_sub": 0.0,
            "passive_voice_ratio": 0.0,
            "passive_voice_sub": 0.0,
            "transition_word_frequency": 0.0,
            "transition_sub": 0.0,
        }

    ai_words = _AI_WORDS_EN if language == "en" else _AI_WORDS_HE
    ai_phrases = _AI_PHRASES_EN if language == "en" else _AI_PHRASES_HE
    transitions = _TRANSITIONS_EN if language == "en" else _TRANSITIONS_HE
    passive_re = _PASSIVE_EN_RE if language == "en" else _PASSIVE_HE_RE

    ai_hits = sum(1 for w in words if w in ai_words)
    phrase_hits = sum(
        text.lower().count(p.lower()) for p in ai_phrases
    )
    density = _safe_div(ai_hits + phrase_hits * 3, len(words))
    ai_phrase_sub = _normalize(density, 0.0, 0.08)

    passive_matches = len(passive_re.findall(text))
    passive_ratio = _safe_div(passive_matches, max(len(sentences), 1))
    passive_sub = _normalize(passive_ratio, 0.0, 0.6)

    trans_hits = sum(1 for w in words if w in transitions)
    trans_freq = _safe_div(trans_hits, len(words))
    trans_sub = _normalize(trans_freq, 0.0, 0.035)

    return {
        "ai_phrase_density": float(density),
        "ai_phrase_density_sub": float(ai_phrase_sub),
        "passive_voice_ratio": float(passive_ratio),
        "passive_voice_sub": float(passive_sub),
        "transition_word_frequency": float(trans_freq),
        "transition_sub": float(trans_sub),
    }


# ---------------------------------------------------------------------------
# Part 3
# ---------------------------------------------------------------------------


def compute_part3(text: str, language: Language) -> dict[str, float]:
    words = _words(text, language)
    sentences = _sentences(text)
    if not words:
        return {
            "vocab_diversity": 0.0,
            "vocab_diversity_sub": 0.0,
            "hedging_ratio": 0.0,
            "hedging_sub": 0.0,
            "sentence_start_diversity": 0.0,
            "sentence_start_diversity_sub": 0.0,
            "quantifier_overuse": 0.0,
            "quantifier_sub": 0.0,
            "pronoun_pattern_score": 0.0,
            "pronoun_sub": 0.0,
        }

    # Type-token ratio. AI text tends to have a moderate, *flat* TTR.
    types = len(set(words))
    ttr = _safe_div(types, len(words))
    # Lower TTR → AI; higher TTR → human. Sub-score inverts.
    vocab_sub = 1.0 - _normalize(ttr, 0.3, 0.75)

    hedging = _HEDGING_EN if language == "en" else _HEDGING_HE
    hedge_hits = sum(1 for w in words if w in hedging)
    hedge_ratio = _safe_div(hedge_hits, len(words))
    # AI text *over-hedges*: too many "might/could/perhaps".
    hedge_sub = _normalize(hedge_ratio, 0.005, 0.04)

    starts = []
    word_re = _WORD_EN_RE if language == "en" else _WORD_HE_RE
    for s in sentences:
        m = word_re.search(s)
        if m:
            starts.append(m.group(0).lower())
    start_diversity = _safe_div(len(set(starts)), max(len(starts), 1))
    # Low diversity → AI.
    start_sub = 1.0 - _normalize(start_diversity, 0.5, 0.95)

    quantifiers = _QUANTIFIERS_EN if language == "en" else _QUANTIFIERS_HE
    q_hits = sum(1 for w in words if w in quantifiers) + sum(
        text.lower().count(q) for q in quantifiers if " " in q
    )
    q_ratio = _safe_div(q_hits, len(words))
    q_sub = _normalize(q_ratio, 0.0, 0.04)

    pronouns = _PRONOUNS_EN if language == "en" else _PRONOUNS_HE
    p_hits = sum(1 for w in words if w in pronouns)
    p_ratio = _safe_div(p_hits, len(words))
    # AI under-uses 1st/2nd person; very low first-person ratio → AI.
    pronoun_sub = 1.0 - _normalize(p_ratio, 0.0, 0.08)

    return {
        "vocab_diversity": float(ttr),
        "vocab_diversity_sub": float(vocab_sub),
        "hedging_ratio": float(hedge_ratio),
        "hedging_sub": float(hedge_sub),
        "sentence_start_diversity": float(start_diversity),
        "sentence_start_diversity_sub": float(start_sub),
        "quantifier_overuse": float(q_ratio),
        "quantifier_sub": float(q_sub),
        "pronoun_pattern_score": float(p_ratio),
        "pronoun_sub": float(pronoun_sub),
    }


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------


def compute_all(text: str, language: Language) -> dict[str, float]:
    """All 12 metric values + the 10 sub-scores used by fusion."""
    return {**compute_part1(text, language), **compute_part2(text, language), **compute_part3(text, language)}
