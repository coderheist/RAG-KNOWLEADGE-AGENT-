"""
User collections API.

  GET    /collections                 list collections with document counts
  POST   /collections                 create one
  DELETE /collections/{id}            delete one; its documents stay in the library, unassigned
  PATCH  /documents/{id}              move a document into a collection (or out, with null)

The raw vector-store administration API lives under /admin/vector-collections (see api/collections.py).
"""
import uuid

from fastapi import APIRouter, HTTPException, status

from app.schemas.library import (
    AssignRequest,
    AssignResponse,
    CollectionCreate,
    CollectionDeleteResponse,
    CollectionListResponse,
    CollectionOut,
)
from app.services import library_service as svc

router = APIRouter(tags=["Collections"])


@router.get("/collections", response_model=CollectionListResponse, summary="List collections")
async def list_collections_endpoint() -> CollectionListResponse:
    items = await svc.list_collections()
    return CollectionListResponse(total=len(items), collections=items)


@router.post(
    "/collections", response_model=CollectionOut, status_code=status.HTTP_201_CREATED, summary="Create a collection"
)
async def create_collection_endpoint(payload: CollectionCreate) -> CollectionOut:
    try:
        return await svc.create_collection(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/collections/{collection_id}", response_model=CollectionDeleteResponse, summary="Delete a collection")
async def delete_collection_endpoint(collection_id: uuid.UUID) -> CollectionDeleteResponse:
    try:
        name, released = await svc.delete_collection(collection_id)
    except svc.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return CollectionDeleteResponse(id=collection_id, name=name, documents_released=released)


@router.patch("/documents/{document_id}", response_model=AssignResponse, summary="Move a document to a collection")
async def assign_document_endpoint(document_id: uuid.UUID, body: AssignRequest) -> AssignResponse:
    try:
        await svc.assign_document(document_id, body.collection_id)
    except svc.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return AssignResponse(document_id=document_id, collection_id=body.collection_id)
