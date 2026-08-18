"""
Vector Store management endpoints.
Allows viewing, adding, searching, and managing documents in FAISS.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services.vector_store_service import vector_store_service

router = APIRouter()


# --- Request Models ---

class AddDocumentRequest(BaseModel):
    """Request to add a document to the vector store."""
    content: str = Field(..., description="Document text content")
    source: str = Field(..., description="Source name (e.g., NOAA, NASA, news outlet)")
    url: Optional[str] = Field(None, description="Source URL")
    topic: Optional[str] = Field(None, description="Climate topic (flood, drought, temperature, etc.)")
    location: Optional[str] = Field(None, description="Geographic location this relates to")
    date: Optional[str] = Field(None, description="Date of the information")


class AddBulkDocumentsRequest(BaseModel):
    """Request to add multiple documents at once."""
    documents: list[AddDocumentRequest]


class SearchRequest(BaseModel):
    """Request to search the vector store."""
    query: str = Field(..., description="Search query in natural language")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results")


# --- Endpoints ---

@router.get("/stats")
async def get_stats():
    """Get vector store statistics."""
    return await vector_store_service.get_collection_stats()


@router.get("/documents")
async def list_documents(limit: int = 50, offset: int = 0):
    """List all documents in the vector store with their metadata."""
    if not vector_store_service.is_available():
        raise HTTPException(status_code=503, detail="Vector store not available")

    docs = vector_store_service._documents
    total = len(docs)

    # Paginate
    paginated = docs[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "documents": [
            {
                "id": doc["id"],
                "content_preview": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"],
                "metadata": doc["metadata"],
                "added_at": doc.get("added_at"),
            }
            for doc in paginated
        ],
    }


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get a specific document by ID."""
    if not vector_store_service.is_available():
        raise HTTPException(status_code=503, detail="Vector store not available")

    for doc in vector_store_service._documents:
        if doc["id"] == doc_id:
            return doc

    raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")


@router.post("/documents")
async def add_document(request: AddDocumentRequest):
    """Add a single document to the vector store."""
    import uuid

    doc_id = f"doc-{uuid.uuid4().hex[:8]}"

    metadata = {
        "source": request.source,
        "url": request.url,
        "topic": request.topic,
        "location": request.location,
        "date": request.date,
    }
    # Remove None values
    metadata = {k: v for k, v in metadata.items() if v is not None}

    result = await vector_store_service.add_documents(
        documents=[request.content],
        metadatas=[metadata],
        ids=[doc_id],
    )

    return {
        "id": doc_id,
        "result": result,
        "message": "Document added successfully" if result.get("added") else "Failed to add document",
    }


@router.post("/documents/bulk")
async def add_bulk_documents(request: AddBulkDocumentsRequest):
    """Add multiple documents at once."""
    import uuid

    documents = []
    metadatas = []
    ids = []

    for doc in request.documents:
        doc_id = f"doc-{uuid.uuid4().hex[:8]}"
        metadata = {
            "source": doc.source,
            "url": doc.url,
            "topic": doc.topic,
            "location": doc.location,
            "date": doc.date,
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}

        documents.append(doc.content)
        metadatas.append(metadata)
        ids.append(doc_id)

    result = await vector_store_service.add_documents(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )

    return {
        "ids": ids,
        "result": result,
        "message": f"Added {result.get('added', 0)} documents",
    }


@router.post("/search")
async def search_documents(request: SearchRequest):
    """Search for similar documents using natural language."""
    results = await vector_store_service.query_similar(
        query_text=request.query,
        top_k=request.top_k,
    )

    return {
        "query": request.query,
        "results_count": len(results),
        "results": results,
    }


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a specific document by ID."""
    result = await vector_store_service.delete_documents(ids=[doc_id])
    return result


@router.delete("/reset")
async def reset_vector_store():
    """Delete ALL documents. Use with caution."""
    result = await vector_store_service.reset()
    return result


@router.post("/seed")
async def seed_sample_data():
    """
    Seed the vector store with sample climate documents for testing.
    This gives you something to search against immediately.
    """
    import uuid

    sample_documents = [
        {
            "content": "Colombo, Sri Lanka faces significant flood risk during the southwest monsoon season from May to September. Urban flooding is exacerbated by inadequate drainage systems and rapid urbanization. The Kelani River basin is particularly vulnerable to overflow during heavy rainfall events.",
            "metadata": {
                "source": "Sri Lanka Disaster Management Centre",
                "topic": "flood",
                "location": "Colombo, Sri Lanka",
                "date": "2024-06-15",
            },
        },
        {
            "content": "The Dry Zone of Sri Lanka, covering the north-central and southeastern regions, experiences periodic drought conditions. Climate projections suggest increasing drought frequency due to changing monsoon patterns. Agriculture in these areas, particularly rice cultivation, is highly vulnerable to water scarcity.",
            "metadata": {
                "source": "Department of Meteorology Sri Lanka",
                "topic": "drought",
                "location": "Dry Zone, Sri Lanka",
                "date": "2024-03-10",
            },
        },
        {
            "content": "Global sea surface temperatures reached record highs in 2024, contributing to intensified tropical cyclone activity in the Indian Ocean. Coastal communities in South Asia face elevated storm surge risk. Early warning systems and coastal protection infrastructure are critical for preparedness.",
            "metadata": {
                "source": "NOAA Climate Report",
                "topic": "sea-level-rise",
                "location": "Indian Ocean, South Asia",
                "date": "2024-08-01",
            },
        },
        {
            "content": "Heat waves in South Asia are becoming more frequent and intense due to climate change. Urban heat island effects in cities like Colombo amplify temperatures by 2-4 degrees Celsius compared to surrounding rural areas. Vulnerable populations including outdoor workers, elderly, and children face heightened health risks.",
            "metadata": {
                "source": "World Meteorological Organization",
                "topic": "heat-wave",
                "location": "South Asia",
                "date": "2024-05-20",
            },
        },
        {
            "content": "Landslide risk in Sri Lanka's central highlands increases significantly during both monsoon seasons. Districts including Badulla, Nuwara Eliya, and Ratnapura have experienced deadly landslides triggered by prolonged heavy rainfall saturating hillside soils. Deforestation and unplanned development contribute to slope instability.",
            "metadata": {
                "source": "National Building Research Organisation",
                "topic": "landslide",
                "location": "Central Highlands, Sri Lanka",
                "date": "2024-07-05",
            },
        },
        {
            "content": "Coral bleaching events in Sri Lanka's coastal waters have intensified due to rising ocean temperatures. The marine ecosystems around Hikkaduwa and Pigeon Island are particularly affected. Loss of coral reefs impacts fisheries, tourism, and coastal protection from wave action.",
            "metadata": {
                "source": "Marine Environment Protection Authority",
                "topic": "ocean-warming",
                "location": "Coastal Sri Lanka",
                "date": "2024-04-12",
            },
        },
        {
            "content": "Agricultural adaptation to climate change in Sri Lanka includes shifting planting calendars, adopting drought-resistant rice varieties, and improving irrigation efficiency. The Mahaweli river system provides critical water resources for cultivation, but changing rainfall patterns threaten reliable water supply.",
            "metadata": {
                "source": "Ministry of Agriculture Sri Lanka",
                "topic": "agriculture",
                "location": "Sri Lanka",
                "date": "2024-02-28",
            },
        },
        {
            "content": "Air quality in Colombo deteriorates during dry seasons and periods of low wind, with particulate matter PM2.5 exceeding WHO guidelines. Vehicle emissions, industrial activity, and construction dust are primary contributors. Respiratory health impacts are concentrated in high-traffic urban corridors.",
            "metadata": {
                "source": "Central Environmental Authority",
                "topic": "air-quality",
                "location": "Colombo, Sri Lanka",
                "date": "2024-01-15",
            },
        },
    ]

    documents = [doc["content"] for doc in sample_documents]
    metadatas = [doc["metadata"] for doc in sample_documents]
    ids = [f"seed-{uuid.uuid4().hex[:8]}" for _ in sample_documents]

    result = await vector_store_service.add_documents(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )

    return {
        "message": f"Seeded {result.get('added', 0)} sample climate documents",
        "ids": ids,
        "result": result,
    }
