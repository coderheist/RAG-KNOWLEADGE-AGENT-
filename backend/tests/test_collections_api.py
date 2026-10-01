"""Integration tests for collections. They need the running stack (docker compose up) and a Gemini key:
uploads embed text and questions run the router. Every test cleans up the documents and collections it creates."""
import json
import os
import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration

API = os.environ.get("API_URL", "http://localhost:8000")


@pytest.fixture
async def client():
    async with httpx.AsyncClient(timeout=180) as c:
        yield c


@pytest.fixture
async def cleanup(client):
    """Collect ids to delete after the test, whatever its outcome."""
    docs: list[str] = []
    colls: list[str] = []
    yield docs, colls
    for d in docs:
        await client.delete(f"{API}/documents/{d}")
    for c in colls:
        await client.delete(f"{API}/collections/{c}")


def tag() -> str:
    return uuid.uuid4().hex[:10]


async def new_collection(client, cleanup, name: str) -> dict:
    resp = await client.post(f"{API}/collections", json={"name": name})
    assert resp.status_code == 201, resp.text
    cleanup[1].append(resp.json()["id"])
    return resp.json()


async def upload(client, cleanup, label: str, collection_id: str | None = None, body: str | None = None):
    text = body or f"# Note {label}\n\nThe {label} beacon transmits on {label[:4]} kilohertz every night.\n"
    data = {"collection_id": collection_id} if collection_id else {}
    resp = await client.post(
        f"{API}/upload", files={"files": (f"note_{label}.md", text.encode(), "text/markdown")}, data=data
    )
    if resp.status_code == 200:
        for d in resp.json()["documents"]:
            cleanup[0].append(d["document_id"])
    return resp


async def collection_of(client, document_id: str) -> str | None:
    docs = (await client.get(f"{API}/documents", params={"limit": 100})).json()["documents"]
    return next(d["collection_id"] for d in docs if d["document_id"] == document_id)


async def count_in(client, collection_id: str) -> int:
    resp = await client.get(f"{API}/documents", params={"collection_id": collection_id})
    return resp.json()["total"]


async def first_sources(client, question: str, collection_id: str | None = None):
    """(status, filenames of the first retrieval) without waiting for the answer to be generated."""
    body = {"query": question, "top_k": 5}
    if collection_id:
        body["collection_id"] = collection_id
    async with client.stream("POST", f"{API}/query", json=body) as resp:
        if resp.status_code != 200:
            return resp.status_code, None
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if event.get("type") == "sources":
                return 200, [s["filename"] for s in event["sources"]]
    return 200, []


async def test_create_list_and_reject_bad_names(client, cleanup) -> None:
    name = f"QA {tag()}"
    made = await new_collection(client, cleanup, name)
    assert made["name"] == name and made["document_count"] == 0 and uuid.UUID(made["id"])

    listed = (await client.get(f"{API}/collections")).json()
    assert any(c["id"] == made["id"] and c["document_count"] == 0 for c in listed["collections"])

    assert (await client.post(f"{API}/collections", json={"name": name.upper()})).status_code == 409  # case-insensitive
    for bad in ("", "   ", "x" * 81):
        assert (await client.post(f"{API}/collections", json={"name": bad})).status_code == 422


async def test_ids_are_validated_and_unknown_ones_are_404(client) -> None:
    assert (await client.delete(f"{API}/collections/{uuid.uuid4()}")).status_code == 404
    assert (await client.delete(f"{API}/collections/not-a-uuid")).status_code == 422
    # The UI used to delete raw vector-store collections through this route; it must not any more.
    assert (await client.delete(f"{API}/collections/documents")).status_code == 422
    assert (await client.patch(f"{API}/documents/{uuid.uuid4()}", json={"collection_id": None})).status_code == 404


async def test_assign_filter_count_and_release(client, cleanup) -> None:
    coll = await new_collection(client, cleanup, f"QA {tag()}")
    doc = (await upload(client, cleanup, tag())).json()["documents"][0]["document_id"]
    assert await collection_of(client, doc) is None

    assert (await client.patch(f"{API}/documents/{doc}", json={"collection_id": coll["id"]})).status_code == 200
    assert await collection_of(client, doc) == coll["id"]
    assert await count_in(client, coll["id"]) == 1
    listed = (await client.get(f"{API}/collections")).json()["collections"]
    assert next(c for c in listed if c["id"] == coll["id"])["document_count"] == 1

    assert (await client.patch(f"{API}/documents/{doc}", json={"collection_id": str(uuid.uuid4())})).status_code == 404
    assert (await client.patch(f"{API}/documents/{doc}", json={"collection_id": "not-a-uuid"})).status_code == 422

    assert (await client.patch(f"{API}/documents/{doc}", json={"collection_id": None})).status_code == 200
    assert await collection_of(client, doc) is None
    assert await count_in(client, coll["id"]) == 0


async def test_upload_straight_into_a_collection(client, cleanup) -> None:
    coll = await new_collection(client, cleanup, f"QA {tag()}")
    resp = await upload(client, cleanup, tag(), collection_id=coll["id"])
    assert resp.status_code == 200 and resp.json()["succeeded"] == 1
    assert await collection_of(client, resp.json()["documents"][0]["document_id"]) == coll["id"]

    ghost = await upload(client, cleanup, tag(), collection_id=str(uuid.uuid4()))
    assert ghost.status_code == 404  # rejected before anything is indexed


async def test_an_already_indexed_file_keeps_its_collection(client, cleanup) -> None:
    first = await new_collection(client, cleanup, f"QA {tag()}")
    second = await new_collection(client, cleanup, f"QA {tag()}")
    label = tag()
    a = await upload(client, cleanup, label, collection_id=first["id"])
    b = await upload(client, cleanup, label, collection_id=second["id"])  # identical content
    assert b.json()["documents"][0]["status"] == "already_exists"
    assert await collection_of(client, a.json()["documents"][0]["document_id"]) == first["id"]


async def test_a_question_only_sees_the_chosen_collection(client, cleanup) -> None:
    a = await new_collection(client, cleanup, f"QA A {tag()}")
    b = await new_collection(client, cleanup, f"QA B {tag()}")
    label_a, label_b = tag(), tag()
    await upload(client, cleanup, label_a, collection_id=a["id"])
    await upload(client, cleanup, label_b, collection_id=b["id"])
    question = f"At what frequency does the {label_a} beacon transmit?"

    status, sources = await first_sources(client, question, a["id"])
    assert status == 200 and f"note_{label_a}.md" in sources
    status, sources = await first_sources(client, question, b["id"])
    assert status == 200 and f"note_{label_a}.md" not in sources
    status, sources = await first_sources(client, question)  # no collection: the whole library
    assert status == 200 and f"note_{label_a}.md" in sources

    assert (await first_sources(client, question, str(uuid.uuid4())))[0] == 404


async def test_deleting_a_collection_keeps_its_documents(client, cleanup) -> None:
    coll = await new_collection(client, cleanup, f"QA {tag()}")
    label = tag()
    doc = (await upload(client, cleanup, label, collection_id=coll["id"])).json()["documents"][0]["document_id"]

    resp = await client.delete(f"{API}/collections/{coll['id']}")
    assert resp.status_code == 200 and resp.json()["documents_released"] == 1

    assert await collection_of(client, doc) is None  # still in the library, just unassigned
    assert (await first_sources(client, "anything", coll["id"]))[0] == 404
    status, sources = await first_sources(client, f"At what frequency does the {label} beacon transmit?")
    assert status == 200 and f"note_{label}.md" in sources  # its vectors are intact and unscoped search finds them


async def test_the_vector_store_admin_api_moved(client) -> None:
    admin = (await client.get(f"{API}/admin/vector-collections")).json()
    assert {"name", "points_count"} <= set(admin["collections"][0])
    product = (await client.get(f"{API}/collections")).json()
    assert all({"id", "name", "document_count"} <= set(c) for c in product["collections"])
