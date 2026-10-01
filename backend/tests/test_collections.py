"""Unit tests for user collections: name validation and the retrieval filter (no services needed)."""
import pytest
from pydantic import ValidationError
from test_hybrid import FakeClient, hit, settings, stub_sparse_query  # noqa: F401  (autouse fixture)

from app.schemas.library import CollectionCreate
from app.services import retrieval_service


def test_names_are_trimmed_and_bounded() -> None:
    assert CollectionCreate(name="  Contracts  ").name == "Contracts"
    assert CollectionCreate(name="x" * 80).name == "x" * 80
    for bad in ("", "   ", "x" * 81):
        with pytest.raises(ValidationError):
            CollectionCreate(name=bad)


def test_no_collection_means_no_filter() -> None:
    assert retrieval_service.collection_filter(None) is None
    assert retrieval_service.collection_filter("") is None


def test_filter_matches_the_payload_field() -> None:
    flt = retrieval_service.collection_filter("c-1")
    assert flt is not None and len(flt.must) == 1
    assert flt.must[0].key == "collection_id" and flt.must[0].match.value == "c-1"


async def test_the_filter_reaches_both_the_dense_and_the_sparse_search() -> None:
    client = FakeClient(dense=[hit("a", 0.9, "x")], sparse=[hit("a", 5.0, "x")], vectors={})
    flt = retrieval_service.collection_filter("c-1")
    await retrieval_service._hybrid_candidates(client, "docs", "q", [1.0, 1.0], 3, settings(), flt)
    assert client.filters == [flt, flt]


async def test_without_a_collection_both_searches_are_unfiltered() -> None:
    client = FakeClient(dense=[hit("a", 0.9, "x")], sparse=[hit("a", 5.0, "x")], vectors={})
    await retrieval_service._hybrid_candidates(client, "docs", "q", [1.0, 1.0], 3, settings())
    assert client.filters == [None, None]
