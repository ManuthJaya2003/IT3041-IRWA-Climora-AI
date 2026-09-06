"""
Seed additional climate documents into the IR Agent's FAISS vector store.

Why this script exists:
The built-in /api/v1/vectors/seed endpoint (backend/app/routers/vector_store.py)
only ships 24 sample documents, all clustered around a handful of topics/locations.
This script adds a further batch covering districts and hazard types the original
seed set didn't touch, so retrieve_documents has real breadth to search over
instead of just 24 near-duplicate test entries.

This is a standalone script (not a shared service file) - it just calls the IR
Agent's own index_document tool over HTTP, the same way the Orchestrator would.
It does not modify any file another teammate owns.

Usage:
    1. Start the IR Agent in another terminal:
       python -m app.agents.ir_agent.ir_agent
    2. Run this script:
       python scripts/seed_ir_data.py
"""

import sys
import httpx

IR_AGENT_URL = "http://localhost:8102/tools/index_document"

DOCUMENTS = [
    {
        "content": "Batticaloa lagoon's salinity levels fluctuate sharply with monsoon rainfall and dry-season evaporation. Reduced freshwater inflow during prolonged dry spells increases salinity, threatening lagoon fisheries that thousands of local families depend on for income.",
        "metadata": {"source": "National Aquatic Resources Research Agency", "topic": "water-scarcity", "location": "Batticaloa, Sri Lanka", "date": "2024-06-10"},
    },
    {
        "content": "Paddy cultivation in Ampara district relies heavily on the Gal Oya irrigation system. Erratic monsoon onset in recent years has disrupted traditional planting calendars, forcing farmers to delay or replant, reducing yields in years with delayed rains.",
        "metadata": {"source": "Department of Agriculture Sri Lanka", "topic": "agriculture", "location": "Ampara, Sri Lanka", "date": "2024-04-18"},
    },
    {
        "content": "Salt production in Puttalam's coastal salt pans depends on consistent dry-season heat and low rainfall. Unseasonal rain events in recent years have damaged evaporation ponds and reduced annual salt yields for small-scale producers.",
        "metadata": {"source": "Ministry of Industries Sri Lanka", "topic": "heat-wave", "location": "Puttalam, Sri Lanka", "date": "2024-02-05"},
    },
    {
        "content": "Trincomalee's natural harbour area is periodically evacuated during cyclone warnings from the Bay of Bengal. Community cyclone shelters built after the 2004 tsunami are increasingly used for monsoon flood evacuation as well, given rising extreme rainfall frequency.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "cyclone", "location": "Trincomalee, Sri Lanka", "date": "2024-11-15"},
    },
    {
        "content": "Coastal erosion near Hambantota port has accelerated due to changed sediment patterns following port construction combined with rising sea levels. Nearby fishing communities report shrinking usable beach area for boat landing over the past decade.",
        "metadata": {"source": "Coast Conservation Department", "topic": "sea-level-rise", "location": "Hambantota, Sri Lanka", "date": "2024-09-08"},
    },
    {
        "content": "Spice cultivation in Matale district, particularly cinnamon and pepper, requires consistent humidity and moderate rainfall. Increasingly erratic rainfall distribution has led to more frequent crop stress periods, affecting yield and quality of export-grade spices.",
        "metadata": {"source": "Export Development Board Sri Lanka", "topic": "agriculture", "location": "Matale, Sri Lanka", "date": "2024-07-22"},
    },
    {
        "content": "Coconut cultivation in Kurunegala district shows measurable yield decline during extended dry periods, as coconut palms require consistent soil moisture. Farmers have begun adopting drip irrigation and mulching techniques to reduce drought stress on young palms.",
        "metadata": {"source": "Coconut Research Institute Sri Lanka", "topic": "drought", "location": "Kurunegala, Sri Lanka", "date": "2024-03-14"},
    },
    {
        "content": "Gem mining pits in Ratnapura district become significantly more hazardous during heavy monsoon rainfall, with waterlogged pits increasing landslide and collapse risk for informal miners working in hillside excavation sites.",
        "metadata": {"source": "National Gem and Jewellery Authority", "topic": "landslide", "location": "Ratnapura, Sri Lanka", "date": "2024-06-25"},
    },
    {
        "content": "Groundwater extraction in Vavuniya district has increased as farmers supplement irregular rainfall with well water for cultivation. Falling water tables in parts of the district raise concerns about long-term aquifer sustainability under continued dry-season pressure.",
        "metadata": {"source": "Water Resources Board Sri Lanka", "topic": "water-scarcity", "location": "Vavuniya, Sri Lanka", "date": "2024-05-30"},
    },
    {
        "content": "Traditional chena (slash-and-burn) cultivation in Monaragala district is highly sensitive to rainfall timing. Farmers report that unpredictable monsoon onset has made it harder to plan the annual chena cycle, pushing some households toward alternative livelihoods.",
        "metadata": {"source": "Ministry of Agriculture Sri Lanka", "topic": "agriculture", "location": "Monaragala, Sri Lanka", "date": "2024-08-19"},
    },
    {
        "content": "Human-elephant conflict incidents in dry zone areas correlate with drought severity, as elephants range further from shrinking forest water sources into agricultural land in search of food and water, increasing crop damage and safety incidents.",
        "metadata": {"source": "Department of Wildlife Conservation", "topic": "drought", "location": "Dry Zone, Sri Lanka", "date": "2024-04-02"},
    },
    {
        "content": "Kandy city experiences a measurable urban heat island effect during dry months, with paved central areas running several degrees warmer than surrounding hill country vegetation. Tree cover loss from urban development has been linked to rising local temperatures.",
        "metadata": {"source": "Urban Development Authority", "topic": "heat-wave", "location": "Kandy, Sri Lanka", "date": "2024-01-28"},
    },
    {
        "content": "Wind energy potential in Mannar district is among the highest in Sri Lanka, and several wind farm projects have been developed to diversify the national grid away from hydropower, which is increasingly vulnerable to rainfall variability.",
        "metadata": {"source": "Sustainable Energy Authority Sri Lanka", "topic": "climate-policy", "location": "Mannar, Sri Lanka", "date": "2024-10-05"},
    },
    {
        "content": "Reservoir levels at the Victoria hydropower dam fluctuate significantly with monsoon performance, directly affecting national electricity generation capacity. Below-average rainfall years have historically forced increased reliance on costlier thermal power generation.",
        "metadata": {"source": "Ceylon Electricity Board", "topic": "water-resources", "location": "Victoria Reservoir, Sri Lanka", "date": "2024-09-20"},
    },
    {
        "content": "Malaria and other vector-borne diseases, historically rare in Sri Lanka's cooler hill country, are being monitored more closely as warming highland temperatures create conditions more suitable for mosquito breeding at higher elevations than before.",
        "metadata": {"source": "Epidemiology Unit, Ministry of Health", "topic": "climate-health", "location": "Central Highlands, Sri Lanka", "date": "2024-07-11"},
    },
    {
        "content": "Bar Reef in Kalpitiya, one of Sri Lanka's largest coral reef systems, has experienced repeated bleaching events linked to elevated sea surface temperatures. Local dive operators report visibly reduced coral cover compared to a decade ago.",
        "metadata": {"source": "Marine Environment Protection Authority", "topic": "ocean-warming", "location": "Kalpitiya, Sri Lanka", "date": "2024-05-16"},
    },
    {
        "content": "Solid waste accumulation in Colombo's Kolonnawa area worsens urban flooding by blocking drainage canals during heavy rainfall. Municipal clean-up efforts before monsoon season are now considered a standard flood-mitigation measure by city authorities.",
        "metadata": {"source": "Central Environmental Authority", "topic": "flood", "location": "Kolonnawa, Colombo, Sri Lanka", "date": "2024-04-29"},
    },
    {
        "content": "Sri Lanka's ancient cascading tank (wewa) irrigation systems in the dry zone were engineered centuries ago for drought resilience. Restoration programs are reviving these systems as a low-cost climate adaptation strategy for water storage during erratic rainfall years.",
        "metadata": {"source": "Department of Agrarian Development", "topic": "climate-policy", "location": "Dry Zone, Sri Lanka", "date": "2024-08-08"},
    },
    {
        "content": "Coastal households in low-lying parts of Galle district have begun relocating inland as recurring flood and erosion damage makes rebuilding in place increasingly costly, an early example of climate-linked internal displacement in Sri Lanka.",
        "metadata": {"source": "Ministry of Environment, Sri Lanka", "topic": "sea-level-rise", "location": "Galle, Sri Lanka", "date": "2024-10-22"},
    },
    {
        "content": "School-based climate education programs have expanded across Sri Lanka's Western and Southern provinces, teaching students about flood preparedness, water conservation, and disaster response as part of a national climate resilience awareness initiative.",
        "metadata": {"source": "Ministry of Education Sri Lanka", "topic": "climate-policy", "location": "Sri Lanka", "date": "2024-06-01"},
    },
]


def main():
    print(f"Seeding {len(DOCUMENTS)} additional documents into the IR Agent's vector store...\n")

    success_count = 0
    fail_count = 0

    with httpx.Client(timeout=10.0) as client:
        for i, doc in enumerate(DOCUMENTS, start=1):
            try:
                resp = client.post(IR_AGENT_URL, json=doc)
                resp.raise_for_status()
                result = resp.json()

                if result.get("indexed"):
                    print(f"[{i}/{len(DOCUMENTS)}] Indexed: {doc['metadata']['location']} - {doc['metadata']['topic']}")
                    success_count += 1
                else:
                    print(f"[{i}/{len(DOCUMENTS)}] FAILED: {result.get('error', 'unknown error')}")
                    fail_count += 1

            except httpx.ConnectError:
                print("Could not connect to the IR Agent at http://localhost:8102")
                print("Make sure it's running: python -m app.agents.ir_agent.ir_agent")
                sys.exit(1)
            except Exception as e:
                print(f"[{i}/{len(DOCUMENTS)}] FAILED: {e}")
                fail_count += 1

    print(f"\nDone. {success_count} indexed, {fail_count} failed.")


if __name__ == "__main__":
    main()
