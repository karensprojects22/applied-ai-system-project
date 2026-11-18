"""Retrieval layer (the "R" in RAG) for PawPal+.

Loads the markdown files in ``knowledge/``, splits them into chunks at ``##``
headings, and ranks chunks for a task with BM25. Each result carries a
``relevance`` score between 0 and 1 so the rest of the system can decide
whether the evidence is good enough to cite or whether to abstain.

Only the standard library is used, so it runs anywhere.

Special comments inside the knowledge files are parsed into structured data:
    <!-- species: dog -->                              file-level species
    <!-- rec: species=dog category=walk min_minutes=30 -->   a recommendation
    <!-- hazard: species=dog terms=chocolate,grapes -->     a safety hazard list
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_KB_DIR = Path(__file__).resolve().parent.parent / "knowledge"

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
    "it", "of", "on", "or", "that", "the", "to", "with", "your", "you", "can",
    "should", "this", "their", "they", "than", "such", "most", "more", "any",
}

# Words that describe what a task category means, so a task titled "Refill water
# bowl" (category "feeding") still retrieves hydration guidance.
CATEGORY_KEYWORDS = {
    "walk": ["walk", "exercise", "outing"],
    "feeding": ["feeding", "food", "meal", "water", "fed"],
    "meds": ["medication", "dose", "preventive", "veterinarian"],
    "enrichment": ["enrichment", "play", "training", "toy"],
    "grooming": ["grooming", "brushing", "coat", "nail"],
}

_COMMENT_RE = re.compile(r"<!--\s*(\w+)\s*:\s*(.*?)\s*-->")


def tokenize(text: str) -> list[str]:
    """Lowercase, split into words, drop stopwords and apply a light stemmer."""
    words = re.findall(r"[a-z]+", text.lower())
    return [_stem(w) for w in words if w not in _STOPWORDS and len(w) > 1]


def _stem(word: str) -> str:
    """Very light stemming: dogs->dog, toys->toy, walking->walk, brushes->brush."""
    if word.endswith("ing") and len(word) - 3 >= 4:
        return word[:-3]
    if word.endswith("es") and len(word) - 2 >= 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) - 1 >= 3:
        return word[:-1]
    return word


@dataclass
class Chunk:
    source: str       # file name, e.g. "dog_care.md"
    heading: str      # section heading
    text: str
    species: str      # "dog", "cat" or "all"
    tokens: list[str] = field(default_factory=list, repr=False)

    @property
    def citation(self) -> str:
        return f"{self.source}#{self.heading}"


@dataclass
class Recommendation:
    species: str
    category: str
    min_minutes: int
    citation: str


@dataclass
class Hazard:
    species: str
    terms: list[str]
    citation: str


@dataclass
class Hit:
    chunk: Chunk
    score: float       # raw BM25 score, only meaningful for ranking
    relevance: float   # 0..1, how well the chunk covers what was asked


class KnowledgeBase:
    """Chunked, searchable pet-care knowledge with structured rules attached."""

    # Relevance is multiplied by GENERAL_FACTOR when a chunk is general ("all")
    # rather than written for the pet's species, because it is a slightly weaker
    # match. If the knowledge base has no species-specific documents for the pet's
    # species at all, UNCOVERED_FACTOR pushes relevance below the abstain
    # threshold: the system would rather say "ask a vet" than cite general text
    # for an animal it has no real guidance on.
    GENERAL_FACTOR = 0.9
    UNCOVERED_FACTOR = 0.5

    def __init__(self, directory: Optional[Path] = None):
        self.directory = Path(directory) if directory else DEFAULT_KB_DIR
        self.chunks: list[Chunk] = []
        self.recommendations: list[Recommendation] = []
        self.hazards: list[Hazard] = []
        self._load()
        self._build_index()

    # ----------------------------------------------------------------- loading
    def _load(self) -> None:
        if not self.directory.is_dir():
            return
        for path in sorted(self.directory.glob("*.md")):
            self._load_file(path)

    def _load_file(self, path: Path) -> None:
        raw = path.read_text(encoding="utf-8")
        file_species = "all"
        for kind, value in _COMMENT_RE.findall(raw):
            if kind == "species":
                file_species = value.strip().lower()
                break

        heading = None
        body: list[str] = []

        def flush() -> None:
            if heading is None:
                return
            text = " ".join(line.strip() for line in body if line.strip())
            if text:
                self.chunks.append(Chunk(path.name, heading, text, file_species))

        for line in raw.splitlines():
            if line.startswith("## "):
                flush()
                heading, body = line[3:].strip(), []
                continue
            if heading is None:
                continue
            match = _COMMENT_RE.fullmatch(line.strip())
            if match:
                self._parse_rule(match.group(1), match.group(2),
                                 file_species, f"{path.name}#{heading}")
            else:
                body.append(line)
        flush()

    def _parse_rule(self, kind: str, value: str, file_species: str, citation: str) -> None:
        # A value runs until the next "key=", so "terms=a, b" keeps both terms.
        fields = {k: v.strip() for k, v in re.findall(r"(\w+)=(.*?)(?=\s+\w+=|$)", value)}
        species = fields.get("species", file_species).lower()
        if kind == "rec" and "category" in fields and "min_minutes" in fields:
            self.recommendations.append(Recommendation(
                species, fields["category"].lower(), int(fields["min_minutes"]), citation))
        elif kind == "hazard" and "terms" in fields:
            terms = [t.strip().lower() for t in fields["terms"].split(",") if t.strip()]
            self.hazards.append(Hazard(species, terms, citation))

    def _build_index(self) -> None:
        for chunk in self.chunks:
            chunk.tokens = tokenize(f"{chunk.heading} {chunk.text}")
        n = len(self.chunks)
        self._avg_len = (sum(len(c.tokens) for c in self.chunks) / n) if n else 0.0
        doc_freq: dict[str, int] = {}
        for chunk in self.chunks:
            for term in set(chunk.tokens):
                doc_freq[term] = doc_freq.get(term, 0) + 1
        self._idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in doc_freq.items()}

    # ------------------------------------------------------------------ search
    def covered_species(self) -> set[str]:
        """Species that have at least one species-specific document."""
        return {c.species for c in self.chunks if c.species != "all"}

    def search(self, category: str, species: str, extra_text: str = "", k: int = 2,
               title: str = "") -> list[Hit]:
        """Return the top-k chunks for a task category and species.

        ``category`` and ``species`` decide which words count as the question
        and drive the relevance score. ``extra_text`` (task title, breed, special
        needs) only helps ranking. ``title`` is the task title; a chunk matching it
        well can raise relevance, but an unusual title can never lower it.
        """
        species = (species or "").lower()
        core = tokenize(" ".join(CATEGORY_KEYWORDS.get(category.lower(), [category])))
        if not core or not self.chunks:
            return []
        boost = set(tokenize(extra_text)) - set(core)

        hits: list[Hit] = []
        for chunk in self.chunks:
            if chunk.species not in ("all", species):
                continue
            score = self._bm25(core, chunk) + 2.0 * self._bm25(list(boost), chunk)
            if score <= 0:
                continue
            hits.append(Hit(chunk, score, self._relevance(core, chunk, species, set(tokenize(title)))))
        hits.sort(key=lambda h: (-h.score, h.chunk.citation))
        return hits[:k]

    def _bm25(self, query: list[str], chunk: Chunk, k1: float = 1.5, b: float = 0.75) -> float:
        score = 0.0
        length = len(chunk.tokens) or 1
        for term in set(query):
            freq = chunk.tokens.count(term)
            if not freq:
                continue
            norm = freq + k1 * (1 - b + b * length / (self._avg_len or 1))
            score += self._idf.get(term, 0.0) * freq * (k1 + 1) / norm
        return score

    def _relevance(self, core: list[str], chunk: Chunk, species: str, extra: set[str]) -> float:
        """Share of the question's words found in the chunk, scaled by species match.

        Coverage is the better of (a) the category keywords and (b) the task's own
        title words, so a chunk that answers the title precisely is not marked down.
        """
        present = set(chunk.tokens)
        coverage = sum(1 for t in set(core) if t in present) / len(set(core))
        if extra:
            coverage = max(coverage, sum(1 for t in extra if t in present) / len(extra))
        factor = 1.0 if chunk.species == species else self.GENERAL_FACTOR
        if species not in self.covered_species():
            factor *= self.UNCOVERED_FACTOR
        return round(coverage * factor, 3)

    def chunk_by_citation(self, citation: str) -> Optional[Chunk]:
        return next((c for c in self.chunks if c.citation == citation), None)

    # --------------------------------------------------------- structured rules
    def recommendations_for(self, species: str) -> list[Recommendation]:
        species = (species or "").lower()
        return [r for r in self.recommendations if r.species in (species, "all")]

    def hazard_terms_for(self, species: str) -> list[Hazard]:
        species = (species or "").lower()
        return [h for h in self.hazards if h.species in (species, "all")]
