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
        {
            "content": "Tropical cyclone Michaung in December 2023 caused severe flooding in southern India and Sri Lanka's northern coast. Over 200mm of rainfall was recorded in 24 hours, displacing thousands. Climate models project increasing intensity of Indian Ocean cyclones due to warmer sea surface temperatures, with a 10-15% increase in peak wind speeds expected by 2050.",
            "metadata": {
                "source": "India Meteorological Department",
                "topic": "cyclone",
                "location": "Northern Sri Lanka, Southern India",
                "date": "2024-01-20",
            },
        },
        {
            "content": "Groundwater levels in Sri Lanka's Jaffna Peninsula have declined by 2-3 meters over the past decade due to over-extraction and reduced recharge from irregular rainfall. Saltwater intrusion threatens freshwater aquifers in coastal areas. The Water Supply and Drainage Board recommends rainwater harvesting and managed aquifer recharge as adaptation strategies.",
            "metadata": {
                "source": "Water Supply and Drainage Board Sri Lanka",
                "topic": "water-scarcity",
                "location": "Jaffna Peninsula, Sri Lanka",
                "date": "2024-04-22",
            },
        },
        {
            "content": "Dengue fever outbreaks in Sri Lanka correlate strongly with monsoon rainfall patterns and temperature. Colombo, Gampaha, and Kalutara districts report the highest case counts. Standing water from flooding creates breeding grounds for Aedes mosquitoes. Climate change is expanding the geographic range and seasonal duration of dengue transmission.",
            "metadata": {
                "source": "Epidemiology Unit, Ministry of Health",
                "topic": "climate-health",
                "location": "Western Province, Sri Lanka",
                "date": "2024-06-30",
            },
        },
        {
            "content": "Sri Lanka's tea plantation sector faces declining yields due to shifting rainfall patterns and rising temperatures in hill country. Nuwara Eliya and Badulla districts report 15-20% yield reduction in drought years. Tea requires consistent rainfall of 1200-1400mm annually and temperatures between 18-25 degrees Celsius. Prolonged dry spells and extreme rainfall events both damage crops.",
            "metadata": {
                "source": "Tea Research Institute of Sri Lanka",
                "topic": "agriculture",
                "location": "Hill Country, Sri Lanka",
                "date": "2024-03-18",
            },
        },
        {
            "content": "Mangrove ecosystems along Sri Lanka's western and northwestern coasts provide critical natural protection against storm surges and coastal erosion. An estimated 60% of original mangrove cover has been lost to shrimp farming, urban development, and pollution. Restoration programs in Puttalam and Negombo lagoons aim to rebuild this natural coastal defense.",
            "metadata": {
                "source": "IUCN Sri Lanka",
                "topic": "coastal-protection",
                "location": "Western Coast, Sri Lanka",
                "date": "2024-05-10",
            },
        },
        {
            "content": "The Northeast monsoon from December to February brings heavy rainfall to Sri Lanka's eastern and northern provinces. Batticaloa and Trincomalee districts are prone to flooding during this season. Flash floods in river basins like the Kalu Ganga and Nilwala Ganga can develop within hours of heavy rainfall onset, leaving limited evacuation time for downstream communities.",
            "metadata": {
                "source": "Irrigation Department Sri Lanka",
                "topic": "flood",
                "location": "Eastern Province, Sri Lanka",
                "date": "2024-12-05",
            },
        },
        {
            "content": "Solar radiation levels in Sri Lanka's dry zone are among the highest in South Asia, with annual averages exceeding 5.5 kWh/m2/day. While this presents opportunities for renewable energy, it also intensifies evapotranspiration rates, accelerating soil moisture loss during drought periods. Farmers in Anuradhapura and Polonnaruwa face compounding water stress from both reduced rainfall and increased evaporation.",
            "metadata": {
                "source": "Sustainable Energy Authority Sri Lanka",
                "topic": "drought",
                "location": "North Central Province, Sri Lanka",
                "date": "2024-08-15",
            },
        },
        {
            "content": "Sea level around Sri Lanka has risen approximately 3.5mm per year over the past three decades, higher than the global average. Coastal erosion affects over 65% of the western and southern coastlines. Low-lying areas in Galle, Matara, and Hambantota face increasing inundation risk during storm surges combined with high tides. Coastal communities are being relocated in the most severely affected areas.",
            "metadata": {
                "source": "Coast Conservation Department",
                "topic": "sea-level-rise",
                "location": "Southern Coast, Sri Lanka",
                "date": "2024-07-20",
            },
        },
        {
            "content": "Climate change threatens Sri Lanka's biodiversity hotspots including the Sinharaja rainforest and Knuckles mountain range. Rising temperatures are shifting species distribution upward in elevation, compressing habitat for endemic species. The country has over 900 endemic plant species and 240 endemic vertebrate species at risk from habitat loss and changing climate conditions.",
            "metadata": {
                "source": "Department of Wildlife Conservation",
                "topic": "biodiversity",
                "location": "Sinharaja, Knuckles Range, Sri Lanka",
                "date": "2024-09-01",
            },
        },
        {
            "content": "Colombo's urban drainage system was designed for rainfall intensities of 50mm/hour but extreme events now regularly exceed 75-100mm/hour due to climate change. The city's rapid development has reduced permeable surfaces by 40% since 2000, increasing surface runoff. The Metro Colombo Urban Development Project is investing in improved storm water drainage and retention ponds to mitigate urban flooding.",
            "metadata": {
                "source": "Urban Development Authority",
                "topic": "flood",
                "location": "Colombo, Sri Lanka",
                "date": "2024-10-12",
            },
        },
        {
            "content": "Sri Lanka's fisheries sector is heavily impacted by climate variability. Shifting ocean currents and warmer waters are altering fish migration patterns. Small-scale fishers report declining catches of traditional species like tuna and sardines. Extreme weather events also reduce the number of safe fishing days, with an estimated 30% reduction during monsoon months.",
            "metadata": {
                "source": "Department of Fisheries and Aquatic Resources",
                "topic": "fisheries",
                "location": "Coastal Sri Lanka",
                "date": "2024-02-14",
            },
        },
        {
            "content": "The Mahaweli River basin, Sri Lanka's largest watershed, supplies water to over 30% of the island's irrigated agriculture. Climate models project a 10-20% reduction in average annual flow by 2050 under moderate emission scenarios. Reservoir storage optimization and demand management are critical to maintaining water security for both agriculture and hydropower generation.",
            "metadata": {
                "source": "Mahaweli Authority of Sri Lanka",
                "topic": "water-resources",
                "location": "Mahaweli Basin, Sri Lanka",
                "date": "2024-05-25",
            },
        },
        {
            "content": "Microplastic pollution in Sri Lanka's waterways increases during monsoon flooding as runoff carries urban waste into rivers and coastal waters. Studies detected microplastic concentrations of 500-2000 particles per liter in the Kelani River during flood events. This contamination affects water treatment plants and enters the food chain through freshwater fisheries.",
            "metadata": {
                "source": "University of Moratuwa Environmental Research",
                "topic": "pollution",
                "location": "Kelani River, Sri Lanka",
                "date": "2024-08-30",
            },
        },
        {
            "content": "Sri Lanka's National Adaptation Plan identifies five priority sectors for climate resilience: food security, water resources, coastal and marine ecosystems, health, and human settlements and infrastructure. The government has committed to reducing climate vulnerability through ecosystem-based adaptation, early warning systems, climate-smart agriculture, and resilient infrastructure development.",
            "metadata": {
                "source": "Ministry of Environment, Sri Lanka",
                "topic": "climate-policy",
                "location": "Sri Lanka",
                "date": "2024-11-01",
            },
        },
        {
            "content": "Lightning strikes during pre-monsoon thunderstorms (March-April) kill an average of 50-70 people annually in Sri Lanka, one of the highest per-capita lightning fatality rates globally. Agricultural workers and those in open areas are most vulnerable. The Department of Meteorology issues thunderstorm warnings but rural communities often lack access to timely alerts.",
            "metadata": {
                "source": "Department of Meteorology Sri Lanka",
                "topic": "thunderstorm",
                "location": "Sri Lanka",
                "date": "2024-03-25",
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
