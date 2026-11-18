import re

from pawpal_ai.advisor import MIN_RELEVANCE
from pawpal_ai.knowledge_base import KnowledgeBase, tokenize


def test_loads_chunks_rules_and_hazards():
    kb = KnowledgeBase()
    assert len(kb.chunks) >= 10
    assert kb.recommendations and kb.hazards
    assert {"dog", "cat"} <= kb.covered_species()


def test_comment_markup_is_not_left_in_chunk_text():
    kb = KnowledgeBase()
    assert all("<!--" not in c.text for c in kb.chunks)


def test_walk_query_for_dog_finds_the_walk_section_with_full_relevance():
    hit = KnowledgeBase().search("walk", "dog", k=1)[0]
    assert hit.chunk.citation == "dog_care.md#Daily walks and exercise"
    assert hit.relevance == 1.0


def test_cat_queries_never_return_dog_only_sections():
    kb = KnowledgeBase()
    for category in ("walk", "feeding", "enrichment", "grooming", "meds"):
        assert all(h.chunk.species in ("cat", "all") for h in kb.search(category, "cat", k=5))


def test_task_title_can_steer_ranking_toward_water_guidance():
    hit = KnowledgeBase().search("feeding", "dog", "Refill water bowl",
                                 k=1, title="Refill water bowl")[0]
    assert hit.chunk.heading == "Water"


def test_unusual_title_cannot_lower_relevance():
    kb = KnowledgeBase()
    plain = kb.search("walk", "dog", k=1)[0].relevance
    odd = kb.search("walk", "dog", "zzz qqq xyzzy", k=1, title="zzz qqq xyzzy")[0].relevance
    assert odd >= plain


def test_species_without_documents_never_clears_the_abstain_threshold():
    kb = KnowledgeBase()
    for category in ("walk", "feeding", "enrichment", "grooming", "meds"):
        for hit in kb.search(category, "hamster", k=5):
            assert hit.relevance < MIN_RELEVANCE


def test_unknown_category_returns_nothing_instead_of_crashing():
    assert KnowledgeBase().search("", "dog") == []


def test_missing_directory_gives_an_empty_but_working_knowledge_base(tmp_path):
    kb = KnowledgeBase(tmp_path / "does_not_exist")
    assert kb.chunks == [] and kb.search("walk", "dog") == []


def test_tokenizer_handles_plurals_and_endings():
    assert tokenize("toys") == tokenize("toy")
    assert tokenize("walking") == tokenize("walk")
    assert tokenize("The dog and the cat") == ["dog", "cat"]


def test_recommendation_and_hazard_parsing(tmp_path):
    (tmp_path / "x.md").write_text(
        "# X\n<!-- species: dog -->\n## Rule\nSome text here.\n"
        "<!-- rec: species=dog category=walk min_minutes=45 -->\n"
        "<!-- hazard: species=dog terms=Grapes, Raisins -->\n")
    kb = KnowledgeBase(tmp_path)
    assert kb.recommendations[0].min_minutes == 45
    assert kb.hazards[0].terms == ["grapes", "raisins"]


def test_no_species_content_leaks_into_another_species():
    """A dog must never be shown guidance written for cats, and vice versa.

    The check looks at section headings, not just the species tag, so it cannot pass
    vacuously when a file is tagged for all species.
    """
    kb = KnowledgeBase()
    titles = ["", "Give chocolate treat", "Lily centerpiece", "Morning walk", "Refill water bowl"]
    for species, other in (("dog", "cat"), ("cat", "dog")):
        for category in ("walk", "feeding", "enrichment", "grooming", "meds"):
            for title in titles:
                for hit in kb.search(category, species, title, k=5, title=title):
                    assert not re.search(rf"\b{other}s?\b", hit.chunk.heading.lower()), (
                        f"{species}/{category}/{title!r} got {hit.chunk.citation}")


def test_every_knowledge_section_is_tagged_for_one_species_audience():
    """Sections whose heading names a species must live in a file tagged for that species."""
    for chunk in KnowledgeBase().chunks:
        for species in ("dog", "cat"):
            if re.search(rf"\b{species}s?\b", chunk.heading.lower()):
                assert chunk.species == species, chunk.citation
