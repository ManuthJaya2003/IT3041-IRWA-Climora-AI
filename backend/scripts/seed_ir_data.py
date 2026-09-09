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

Batch 1 (original): 20 documents covering initial district gaps
Batch 2 (Kandy fix): 5 Kandy/Central Province flood & landslide documents
Batch 3 (this run):  60 documents covering:
  - 10 previously uncovered districts (Anuradhapura, Badulla, Gampaha, Kalutara,
    Kegalle, Kilinochchi, Matara, Mullaitivu, Nuwara Eliya, Polonnaruwa)
  - Missing topic-location combos for existing districts
  - 2 new topics: wildfire/forest-fire, inland erosion
  - Normalised location names (e.g. "Kandy, Sri Lanka" consistently)

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
    # --- Kandy ---
    {
        "content": "Kandy district faces significant flood risk during both southwest (May–September) and northeast (December–February) monsoon seasons. The Mahaweli River and its tributaries overflow during prolonged heavy rainfall, inundating low-lying areas around Peradeniya and Gampola. Flash floods triggered by upstream rainfall in the central highlands can cause rapid river-level rises within 2–3 hours.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "flood", "location": "Kandy, Sri Lanka", "date": "2024-07-10"},
    },
    {
        "content": "Landslides are a recurring hazard in Kandy district, especially on steep slopes around Hantana, Kundasale, and Madawala. Prolonged rainfall saturating hillside soils causes soil slippage, road blockages, and property damage. The National Building Research Organisation has identified several high-risk zones in the Kandy hills that require monitoring during monsoon periods.",
        "metadata": {"source": "National Building Research Organisation", "topic": "landslide", "location": "Kandy, Sri Lanka", "date": "2024-08-05"},
    },
    {
        "content": "Urban flooding in Kandy city centre worsens during monsoon months due to inadequate stormwater drainage capacity in older infrastructure. The Kandy Lake overflow has been recorded during extreme rainfall events exceeding 80mm in 24 hours. Central Province authorities issue evacuation advisories for riverside settlements along the Mahaweli corridor during high-alert periods.",
        "metadata": {"source": "Urban Development Authority", "topic": "flood", "location": "Kandy, Sri Lanka", "date": "2024-06-20"},
    },
    {
        "content": "The Mahaweli River at Kandy carries significantly elevated discharge during heavy monsoon rainfall in the central highlands. River gauges at Peradeniya have recorded flows exceeding 1500 m³/s during extreme events, compared to a dry-season baseline of approximately 50 m³/s. Downstream communities from Kandy to Mahiyangana are placed on flood watch when upstream rainfall exceeds 100mm in 48 hours.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Kandy, Sri Lanka", "date": "2024-09-12"},
    },
    # --- Central Province broader ---
    {
        "content": "Central Province districts including Kandy, Matale, and Nuwara Eliya experience elevated landslide and flood risk during both monsoon seasons. The terrain's steep gradients, combined with high annual rainfall averaging 2000–3000mm, creates conditions where even moderate rainfall events can trigger slope failures. Vulnerable communities are mapped and monitored by the District Secretariats.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "flood", "location": "Central Province, Sri Lanka", "date": "2024-07-01"},
    },
    # --- Existing documents below ---
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

    # =========================================================================
    # BATCH 3 — Previously uncovered districts, missing topic-location combos,
    #           and new topics (wildfire, inland erosion)
    # =========================================================================

    # --- Anuradhapura (North Central Province) ---
    {
        "content": "Anuradhapura district experiences some of the most severe drought conditions in Sri Lanka, with average annual rainfall of 1200–1400mm concentrated in two short monsoon windows. Prolonged dry spells lasting 4–5 months deplete reservoirs and reduce paddy cultivation yields significantly. The ancient tank irrigation network, if fully restored, could buffer drought stress for over 200,000 farming families.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "drought", "location": "Anuradhapura, Sri Lanka", "date": "2024-05-14"},
    },
    {
        "content": "Flash floods in Anuradhapura district follow heavy rain events that overwhelm the capacity of ancient irrigation tanks and canal spillways. Low-lying paddy fields adjacent to Nuwara Wewa and Tissawewa reservoirs flood rapidly when reservoir sluice gates are opened during excess inflow. Communities downstream of these tanks are placed on flood watch by the District Secretariat during red-level rainfall alerts.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "flood", "location": "Anuradhapura, Sri Lanka", "date": "2024-11-20"},
    },
    {
        "content": "Dry-season forest fires in Anuradhapura district, particularly around Wilpattu National Park, are increasing in frequency and intensity. Hot, dry conditions from April to September combined with invasive vegetation create high fire-load landscapes. Fires damage wildlife corridors and release stored carbon, worsening local air quality. The Forest Department and Department of Wildlife Conservation coordinate fire-response teams during the fire season.",
        "metadata": {"source": "Forest Department Sri Lanka", "topic": "wildfire", "location": "Anuradhapura, Sri Lanka", "date": "2024-04-18"},
    },

    # --- Polonnaruwa (North Central Province) ---
    {
        "content": "Polonnaruwa district's agricultural economy is highly vulnerable to erratic rainfall. The Minneriya and Kaudulla reservoir systems supply irrigation to over 40,000 hectares of paddy land. Below-normal northeast monsoon performance leaves these tanks at critically low levels, forcing water rationing and reducing the cultivated area in the Maha season.",
        "metadata": {"source": "Mahaweli Authority of Sri Lanka", "topic": "drought", "location": "Polonnaruwa, Sri Lanka", "date": "2024-02-10"},
    },
    {
        "content": "Polonnaruwa district experiences periodic flooding when the Mahaweli River and its distributaries overflow during peak monsoon discharge. The Flood Management Improvement Programme has installed telemetry gauges on major water bodies, enabling 12–18 hour advance warnings for downstream communities. Climate projections indicate a 15–20% increase in extreme rainfall events in the North Central Province by 2050.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Polonnaruwa, Sri Lanka", "date": "2024-10-05"},
    },

    # --- Badulla (Uva Province) ---
    {
        "content": "Badulla district, situated in the Uva highlands, experiences frequent landslides during the inter-monsoon period from October to November. Steep terrain with thin soils over weathered metamorphic rock is highly susceptible to shallow translational landslides when rainfall exceeds 50mm per day. The Ella and Hali-Ela areas have recorded multiple fatalities from landslides over the past decade.",
        "metadata": {"source": "National Building Research Organisation", "topic": "landslide", "location": "Badulla, Sri Lanka", "date": "2024-10-30"},
    },
    {
        "content": "Tea and rubber cultivation in Badulla district are severely impacted by climate variability. Prolonged dry spells reduce flush growth in tea, while excessive rainfall causes root rot in rubber plantations. Average temperatures in Badulla have risen by 0.8°C over the past 30 years, shifting the optimal growing altitude for premium tea upward by approximately 150 metres.",
        "metadata": {"source": "Tea Research Institute of Sri Lanka", "topic": "agriculture", "location": "Badulla, Sri Lanka", "date": "2024-03-22"},
    },
    {
        "content": "Badulla district's river systems, including the Uma Oya and Kirindi Oya tributaries, show increasing peak-flow variability. Drought years reduce stream flows to below minimum ecological requirements, affecting both agriculture and domestic water supply for rural communities. Watershed degradation from encroachment on forest reserves accelerates surface runoff and reduces groundwater recharge.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "water-scarcity", "location": "Badulla, Sri Lanka", "date": "2024-07-15"},
    },

    # --- Nuwara Eliya (Central Province) ---
    {
        "content": "Nuwara Eliya district is one of the wettest areas in Sri Lanka, receiving over 2000mm of rainfall annually from both monsoons. However, the highland terrain and deforested slopes create extreme landslide risk. The Bogawantalawa and Hatton areas have documented over 30 landslide events since 2016, displacing estate workers from line rooms on steep hillside tea estates.",
        "metadata": {"source": "National Building Research Organisation", "topic": "landslide", "location": "Nuwara Eliya, Sri Lanka", "date": "2024-09-08"},
    },
    {
        "content": "Frost risk in Nuwara Eliya district during December and January affects high-elevation tea estates and vegetable cultivation. As climate change shifts temperature patterns, frost events are becoming less predictable, creating uncertainty for farmers who rely on frost-free growing windows. Conversely, the same warming trend is gradually making the district's cooler microclimates less suitable for varieties that require cool temperatures.",
        "metadata": {"source": "Tea Research Institute of Sri Lanka", "topic": "heat-wave", "location": "Nuwara Eliya, Sri Lanka", "date": "2024-01-12"},
    },
    {
        "content": "Flood risk in Nuwara Eliya district is concentrated along the Kotmale Oya and its tributaries, which drain the Pidurutalagala massif. Intense orographic rainfall events can produce flash floods that damage road infrastructure and isolate highland communities for days. The Kotmale reservoir moderates downstream flooding but cannot fully contain extreme inflow events exceeding its operational capacity.",
        "metadata": {"source": "Ceylon Electricity Board", "topic": "flood", "location": "Nuwara Eliya, Sri Lanka", "date": "2024-08-25"},
    },

    # --- Kegalle (Sabaragamuwa Province) ---
    {
        "content": "Kegalle district has one of the highest landslide incidence rates in Sri Lanka due to its combination of steep hills, deeply weathered soils, and high rainfall from the southwest monsoon. The 2016 Aranayake landslide killed over 100 people and destroyed an entire village. Early warning systems and community-based evacuation drills have since been expanded across high-risk Grama Niladhari divisions.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "landslide", "location": "Kegalle, Sri Lanka", "date": "2024-06-16"},
    },
    {
        "content": "Rubber plantations in Kegalle district are increasingly stressed by climate variability. Extended dry spells reduce latex yield, while excessive rainfall promotes Phytophthora root disease and abnormal leaf fall. Smallholder rubber farmers, who make up over 70% of the district's cultivated area, lack resources for climate adaptation and are particularly vulnerable to income losses during adverse weather years.",
        "metadata": {"source": "Rubber Research Institute of Sri Lanka", "topic": "agriculture", "location": "Kegalle, Sri Lanka", "date": "2024-04-05"},
    },
    {
        "content": "Flooding along the Kelani River in Kegalle district affects low-lying paddy fields and settlements during southwest monsoon peaks. Upstream deforestation in the Sinharaja buffer zone has increased surface runoff and peak discharge, reducing the lead time available for flood evacuation. Kegalle town itself has been partially flooded in three of the past five years.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Kegalle, Sri Lanka", "date": "2024-07-03"},
    },

    # --- Gampaha (Western Province) ---
    {
        "content": "Gampaha district, Sri Lanka's most densely populated district outside Colombo, faces severe urban and peri-urban flooding during the southwest monsoon. Rapid conversion of paddy fields and wetlands to residential and industrial uses has eliminated natural flood retention capacity. The Dandugam Oya and Kelani River tributaries regularly overflow, flooding residential areas in Wattala, Ja-Ela, and Negombo.",
        "metadata": {"source": "Urban Development Authority", "topic": "flood", "location": "Gampaha, Sri Lanka", "date": "2024-06-12"},
    },
    {
        "content": "Air quality in Gampaha district deteriorates significantly during southwest monsoon onset when wind patterns trap vehicle emissions and industrial pollutants from the Colombo–Katunayake industrial corridor. The Free Trade Zone and surrounding manufacturing areas are major point sources of particulate matter. Residents in Ekala and Ja-Ela report elevated respiratory complaints during low-wind periods.",
        "metadata": {"source": "Central Environmental Authority", "topic": "air-quality", "location": "Gampaha, Sri Lanka", "date": "2024-03-30"},
    },
    {
        "content": "Dengue and leptospirosis outbreaks in Gampaha district spike after flooding events, when floodwaters carry pathogens into residential areas and contaminate wells. Gampaha district consistently reports some of the highest dengue case counts in the Western Province. The close proximity of drainage canals, paddy fields, and residential areas creates persistent breeding habitats for Aedes mosquitoes.",
        "metadata": {"source": "Epidemiology Unit, Ministry of Health", "topic": "climate-health", "location": "Gampaha, Sri Lanka", "date": "2024-07-20"},
    },

    # --- Kalutara (Western Province) ---
    {
        "content": "Kalutara district's low-lying coastal strip and river delta areas face compounding flood and sea-level-rise risk. The Kalu Ganga river, one of Sri Lanka's highest-discharge rivers, regularly floods riverside paddy land and settlements during southwest monsoon peaks. Flood damage to the coastal road between Panadura and Kalutara town has been recorded multiple times, disrupting the main southern highway.",
        "metadata": {"source": "Road Development Authority Sri Lanka", "topic": "flood", "location": "Kalutara, Sri Lanka", "date": "2024-08-14"},
    },
    {
        "content": "Coastal erosion in Kalutara district has accelerated over the past two decades due to reduced sediment supply from the Kalu Ganga following upstream sand mining and the construction of small hydropower structures. Several beach resorts and fishing communities between Beruwala and Aluthgama face active erosion affecting their shoreline. The Coast Conservation Department has deployed rock armour groyne structures in the most severely affected sections.",
        "metadata": {"source": "Coast Conservation Department", "topic": "sea-level-rise", "location": "Kalutara, Sri Lanka", "date": "2024-09-25"},
    },
    {
        "content": "Inland soil erosion in Kalutara district's rubber and cinnamon cultivation areas is a growing concern as intense rainfall events strip topsoil from slopes with inadequate ground cover. Eroded soil loads the Kalu Ganga river system, elevating flood levels downstream and smothering paddy irrigation intakes with sediment. Contour planting and cover cropping are promoted by the Department of Agriculture as low-cost erosion control measures.",
        "metadata": {"source": "Department of Agriculture Sri Lanka", "topic": "erosion", "location": "Kalutara, Sri Lanka", "date": "2024-05-08"},
    },

    # --- Matara (Southern Province) ---
    {
        "content": "Matara district on Sri Lanka's southern coast experiences significant flooding during both southwest monsoon and cyclone-related rainfall events. The Nilwala Ganga river basin is particularly prone to flash floods; water levels can rise by over three metres within six hours of extreme upstream rainfall. Matara city, situated at the river mouth, has invested in a flood bund and pump station system to reduce inundation frequency.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Matara, Sri Lanka", "date": "2024-08-30"},
    },
    {
        "content": "Coastal erosion and storm-surge flooding threaten Matara district's southern shoreline, particularly between Polhena and Mirissa. Sea level rise combined with weakened reef structures reduces the natural wave-energy dissipation that historically protected the coast. Coastal erosion rates of 0.5–1.5 metres per year have been documented, threatening beachside properties and turtle nesting beaches.",
        "metadata": {"source": "Coast Conservation Department", "topic": "sea-level-rise", "location": "Matara, Sri Lanka", "date": "2024-07-18"},
    },
    {
        "content": "Cinnamon and tea cultivation in Matara district's hinterland faces increasing stress from erratic rainfall distribution. Prolonged dry spells between December and March — normally the driest period — are becoming more severe, reducing soil moisture below critical thresholds for spice crops. Conversely, intense rain in May and June causes waterlogging and root disease in low-lying cinnamon gardens.",
        "metadata": {"source": "Export Development Board Sri Lanka", "topic": "agriculture", "location": "Matara, Sri Lanka", "date": "2024-02-28"},
    },

    # --- Kilinochchi (Northern Province) ---
    {
        "content": "Kilinochchi district in the Northern Province is one of the most drought-prone areas in Sri Lanka. Annual rainfall averages below 1000mm, confined mainly to the northeast monsoon from November to January. Extended dry seasons from February to October deplete small tanks and wells that supply drinking water and small-scale agriculture for communities still rebuilding after the conflict period.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "drought", "location": "Kilinochchi, Sri Lanka", "date": "2024-04-25"},
    },
    {
        "content": "Flooding in Kilinochchi district occurs during the northeast monsoon when the Iranamadu tank spillway discharges and low-lying agricultural land is inundated. The district's flat terrain means floodwaters spread widely but drain slowly, keeping paddy fields waterlogged for extended periods and damaging standing crops. The Irrigation Department monitors Iranamadu tank levels daily during the monsoon.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Kilinochchi, Sri Lanka", "date": "2024-12-10"},
    },
    {
        "content": "Food security in Kilinochchi district is directly tied to climate variability. Erratic northeast monsoon performance disrupts the single annual paddy cultivation cycle that most smallholder farmers depend on. When the monsoon fails or is delayed by more than three weeks, crop losses exceed 30%, pushing vulnerable households into debt. Post-conflict rehabilitation of irrigation infrastructure has improved resilience but gaps remain.",
        "metadata": {"source": "Ministry of Agriculture Sri Lanka", "topic": "agriculture", "location": "Kilinochchi, Sri Lanka", "date": "2024-09-14"},
    },

    # --- Mullaitivu (Northern Province) ---
    {
        "content": "Mullaitivu district on Sri Lanka's northeast coast faces elevated cyclone exposure from Bay of Bengal tropical storms. The low-lying coastal strip, with elevations below 5 metres, has limited natural shelter from storm surge inundation. Community cyclone shelters built after the 2004 tsunami serve dual purpose during extreme weather events, and the district has improved early warning dissemination through village-level alert networks.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "cyclone", "location": "Mullaitivu, Sri Lanka", "date": "2024-11-05"},
    },
    {
        "content": "Coastal fisheries in Mullaitivu district are severely affected by extreme weather events. Cyclone-force winds and elevated seas reduce safe fishing days by approximately 40% during the northeast monsoon season. Fishing boat damage from sudden squalls has been documented repeatedly, with significant economic loss for households that rely on artisanal fishing as their primary income source.",
        "metadata": {"source": "Department of Fisheries and Aquatic Resources", "topic": "fisheries", "location": "Mullaitivu, Sri Lanka", "date": "2024-10-18"},
    },
    {
        "content": "Groundwater availability in Mullaitivu district is under stress from declining recharge due to reduced and erratic rainfall. Shallow dug wells, the primary water source for many rural households, dry up earlier each year during the pre-monsoon dry season. Saltwater intrusion into coastal aquifers is advancing inland as groundwater extraction increases and sea levels rise, reducing available freshwater volume.",
        "metadata": {"source": "Water Supply and Drainage Board Sri Lanka", "topic": "water-scarcity", "location": "Mullaitivu, Sri Lanka", "date": "2024-06-08"},
    },

    # =========================================================================
    # Missing topic-location combos for well-covered districts
    # =========================================================================

    # Colombo — additional topics
    {
        "content": "Heat stress in Colombo city is intensifying due to the urban heat island effect combined with a long-term warming trend. Average maximum temperatures have increased by approximately 1.2°C since 1990. Densely built commercial districts in Fort and Pettah trap heat overnight, preventing the city from cooling adequately. Outdoor workers, street vendors, and construction labourers face elevated risk of heat exhaustion during April and May.",
        "metadata": {"source": "World Meteorological Organization", "topic": "heat-wave", "location": "Colombo, Sri Lanka", "date": "2024-05-10"},
    },
    {
        "content": "Colombo's coastal suburbs including Mount Lavinia, Dehiwala, and Kollupitiya face accelerating shoreline erosion due to sea level rise and reduced natural sediment supply. Beach widths have narrowed by an average of 15 metres over the past 20 years. During high tides combined with south-westerly swell, wave overtopping causes flooding of the coastal road and damage to seafront properties.",
        "metadata": {"source": "Coast Conservation Department", "topic": "sea-level-rise", "location": "Colombo, Sri Lanka", "date": "2024-07-30"},
    },
    {
        "content": "Water supply resilience in Colombo depends heavily on the Kelani River intake at Ambatale, which faces both drought-year low-flow risk and monsoon-flood turbidity spikes that disrupt treatment. The National Water Supply and Drainage Board has invested in additional storage and treatment capacity, but a severe drought year reducing Kelani flow below 10 m³/s could create supply shortfalls for the capital.",
        "metadata": {"source": "National Water Supply and Drainage Board Sri Lanka", "topic": "water-scarcity", "location": "Colombo, Sri Lanka", "date": "2024-04-15"},
    },

    # Jaffna — expanded coverage with consistent naming
    {
        "content": "Jaffna district faces recurring flood risk during the northeast monsoon when heavy rainfall overwhelms the flat, low-lying peninsula's limited drainage capacity. The district's sandy soils absorb water quickly in shallow events, but prolonged rainfall saturates the soil profile, leading to widespread surface flooding. Jaffna town, Nallur, and low-lying agricultural areas are the most frequently affected.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "flood", "location": "Jaffna, Sri Lanka", "date": "2024-12-15"},
    },
    {
        "content": "Agricultural productivity in Jaffna district is critically dependent on the northeast monsoon, which delivers 70–80% of the district's annual rainfall in a two-month window. Onion, chilli, and tobacco — the district's major cash crops — require precise water management. Drought years with below-normal northeast monsoon rainfall force farmers to rely entirely on costly groundwater pumping, reducing farm income margins significantly.",
        "metadata": {"source": "Department of Agriculture Sri Lanka", "topic": "agriculture", "location": "Jaffna, Sri Lanka", "date": "2024-03-05"},
    },
    {
        "content": "Vector-borne disease risk in Jaffna district elevates after northeast monsoon flooding creates standing water pools in agricultural fields and urban drainage blockages. Dengue, chikungunya, and leptospirosis cases increase sharply in the weeks following major flood events. The peninsular geography limits vector dispersal to some extent, but climate change is extending the transmission season by approximately 3–4 weeks.",
        "metadata": {"source": "Epidemiology Unit, Ministry of Health", "topic": "climate-health", "location": "Jaffna, Sri Lanka", "date": "2024-01-20"},
    },

    # Galle — flood and cyclone
    {
        "content": "Galle district experiences significant flooding during the southwest monsoon season when the Gin Ganga and Nilwala Ganga tributaries overflow into low-lying paddy land and residential areas. The Galle Fort, a UNESCO World Heritage Site, has recorded seawater intrusion through its historic ramparts during storm-surge events combined with monsoon swells. Climate change projections indicate a 20% increase in extreme rainfall events in Southern Province by 2050.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Galle, Sri Lanka", "date": "2024-06-28"},
    },
    {
        "content": "Galle district's fishing industry faces increasing disruption from cyclone-related bad weather windows originating in the Indian Ocean and Bay of Bengal. Deep-sea fishing boats operating out of Galle Fisheries Harbour are restricted from departing during storm warnings. Annual lost fishing days due to extreme weather have increased from an average of 18 days in the 1990s to over 30 days in the 2020s.",
        "metadata": {"source": "Department of Fisheries and Aquatic Resources", "topic": "cyclone", "location": "Galle, Sri Lanka", "date": "2024-09-10"},
    },

    # Hambantota — flood, cyclone, drought
    {
        "content": "Hambantota district is in the rain shadow of the central highlands and receives below-average annual rainfall, making it one of Sri Lanka's most drought-prone southern districts. The Bundala and Lunugamvehera reservoir system is the primary water source for irrigation and domestic supply. In severe drought years both reservoirs drop to critical levels, forcing water rationing and threatening saltpan industries in the coastal zone.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "drought", "location": "Hambantota, Sri Lanka", "date": "2024-03-18"},
    },
    {
        "content": "Hambantota district lies on a direct cyclone approach path from the Bay of Bengal and Indian Ocean. The 2021 cyclone season and remnants of tropical storm systems regularly bring strong winds and heavy rainfall to the district. Hambantota Port and surrounding industrial zones have cyclone preparedness protocols including asset securing and personnel evacuation plans for wind speeds exceeding 60 knots.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "cyclone", "location": "Hambantota, Sri Lanka", "date": "2024-11-22"},
    },

    # Trincomalee — flood, agriculture
    {
        "content": "Trincomalee district experiences flooding primarily during the northeast monsoon from November to January, when rivers draining the eastern slopes of the Knuckles and Central Highlands carry high discharge. Low-lying agricultural areas in the Mahaweli flood plain near Mutur and Kinniya are regularly inundated. The Kantale reservoir, when operated at maximum capacity, provides some upstream retention but cannot fully moderate extreme flood events.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Trincomalee, Sri Lanka", "date": "2024-12-20"},
    },
    {
        "content": "Paddy cultivation in Trincomalee district relies on the northeast monsoon rains and Mahaweli system irrigation. The district produces significant quantities of rice in the Maha season. Delayed or deficient northeast monsoon years reduce planting by 20–30%, forcing farmers to abandon fields or shift to short-duration drought-tolerant varieties. Rising temperatures are also shortening the effective growing period for some traditional paddy varieties.",
        "metadata": {"source": "Department of Agriculture Sri Lanka", "topic": "agriculture", "location": "Trincomalee, Sri Lanka", "date": "2024-02-22"},
    },

    # Kurunegala — flood, heat-wave
    {
        "content": "Kurunegala district experiences periodic flooding when the Deduru Oya and Mee Oya overflow during southwest monsoon peak flows. Low-lying paddy land in the Kurunegala–Maho corridor is the most frequently inundated area. Several large irrigation tanks in the district act as natural buffers but can spill during sustained heavy rainfall exceeding their design capacity.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Kurunegala, Sri Lanka", "date": "2024-07-08"},
    },
    {
        "content": "Heat stress during the pre-monsoon period in Kurunegala district, particularly in April and May, affects outdoor agricultural workers in coconut and rubber estates. Maximum temperatures regularly exceed 34°C during this period, and urban areas in Kurunegala town experience heat island amplification of 1–2°C. Occupational heat illness cases are underreported but known to reduce productivity during the hottest weeks.",
        "metadata": {"source": "Occupational Health Unit, Ministry of Health Sri Lanka", "topic": "heat-wave", "location": "Kurunegala, Sri Lanka", "date": "2024-04-30"},
    },

    # Ratnapura — flood, agriculture
    {
        "content": "Ratnapura district is one of the wettest districts in Sri Lanka, receiving over 3500mm of rainfall annually. The Kalu Ganga originates here and is prone to flash flooding during intense rainfall events. Ratnapura town itself has flooded severely multiple times in the past decade, with 2017 and 2020 events displacing thousands of residents. The terrain's extreme relief means flood-to-evacuation windows can be as short as one to two hours.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "flood", "location": "Ratnapura, Sri Lanka", "date": "2024-06-05"},
    },
    {
        "content": "Rubber and paddy cultivation in Ratnapura district face distinct but overlapping climate challenges. Excessive rainfall during the southwest monsoon causes waterlogging and root disease in rubber, while flooding destroys standing paddy crops. The district's gem mining industry also loses productive days during extreme rainfall events when pits flood. Adaptation strategies include raised paddy varieties and improved rubber drainage systems.",
        "metadata": {"source": "Rubber Research Institute of Sri Lanka", "topic": "agriculture", "location": "Ratnapura, Sri Lanka", "date": "2024-05-20"},
    },

    # Matale — flood, landslide
    {
        "content": "Matale district's hilly terrain and moderate-to-high rainfall create recurring landslide risk, particularly on slopes cleared for vegetable and spice cultivation. The Knuckles Range bordering the district experiences orographic rainfall exceeding 100mm per day during active monsoon periods, triggering shallow landslides that block the Matale–Kandy road corridor. Several fatalities have been recorded from landslide events in Ukuwela and Rattota over the past five years.",
        "metadata": {"source": "National Building Research Organisation", "topic": "landslide", "location": "Matale, Sri Lanka", "date": "2024-10-12"},
    },
    {
        "content": "Flooding in Matale district affects the Matale valley floor during southwest and northeast monsoon peaks. The Amban Ganga and Rattota Oya regularly overflow into paddy fields and riverside homesteads. Climate change is intensifying peak flows; the Matale valley has recorded three 50-year flood-level events within the past decade, suggesting a shortening of extreme flood return periods.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Matale, Sri Lanka", "date": "2024-09-01"},
    },

    # Mannar — flood, fisheries, drought
    {
        "content": "Mannar district's flat, dry landscape is vulnerable to flooding when the northeast monsoon delivers concentrated rainfall over a short period. Giant Tank and associated irrigation infrastructure in the district moderate some flood peak flows, but downstream agricultural areas along the Malwathu Oya remain exposed. Post-flood waterlogging damages onion and sesame crops that are major income sources for Mannar farmers.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "flood", "location": "Mannar, Sri Lanka", "date": "2024-12-05"},
    },
    {
        "content": "Mannar district's fisheries sector, one of the most productive in Northern Province, is increasingly threatened by extreme weather events and warming Gulf of Mannar waters. Coral bleaching in the Gulf of Mannar marine protected area has reduced fish habitat quality. Fishers from Mannar Island report declining catches of high-value species including sea cucumber and prawn, impacting livelihoods that have only recently recovered from the conflict period.",
        "metadata": {"source": "Department of Fisheries and Aquatic Resources", "topic": "fisheries", "location": "Mannar, Sri Lanka", "date": "2024-08-12"},
    },
    {
        "content": "Mannar district receives among the lowest annual rainfall in Sri Lanka — averaging 900–1100mm — and experiences a pronounced dry season lasting 7–8 months. Groundwater is the primary resource for both agriculture and domestic supply, but aquifer levels are declining due to over-extraction and reduced monsoon recharge. The Government's Accelerated Mahaweli Development Programme has extended irrigation canals to Mannar, partially alleviating drought stress for some farming communities.",
        "metadata": {"source": "Mahaweli Authority of Sri Lanka", "topic": "drought", "location": "Mannar, Sri Lanka", "date": "2024-04-10"},
    },

    # Puttalam — flood, coastal-protection
    {
        "content": "Puttalam district's coastal lagoon system, including Puttalam Lagoon and Dutch Bay, is highly vulnerable to storm surge inundation during cyclone events. Low-lying salt pans and fishing settlements around the lagoon perimeter have limited natural elevation above sea level. The district's mangrove restoration programme in Kalpitiya aims to rebuild natural coastal buffers that reduce wave energy and erosion.",
        "metadata": {"source": "Coast Conservation Department", "topic": "coastal-protection", "location": "Puttalam, Sri Lanka", "date": "2024-06-22"},
    },
    {
        "content": "Flooding in Puttalam district during the northeast monsoon affects low-lying agricultural areas and fishing communities around the lagoon margins. The Kala Oya and Mi Oya systems carry elevated discharge during peak monsoon events, backing up into the coastal plain. Puttalam town has experienced repeated flood events in recent years that have damaged market infrastructure and disrupted the salt-trading economy.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "flood", "location": "Puttalam, Sri Lanka", "date": "2024-12-02"},
    },

    # =========================================================================
    # New topics: wildfire and inland erosion
    # =========================================================================

    # Wildfire
    {
        "content": "Yala National Park in Southern Sri Lanka experiences dry-season wildfires from June to September when vegetation moisture content drops to critical levels. Fires driven by strong southwest winds can spread rapidly through dry scrub and grassland, threatening wildlife and burning up to several thousand hectares in severe years. The Department of Wildlife Conservation maintains fire-line clearances and rapid response teams, but climate change is extending the fire season.",
        "metadata": {"source": "Department of Wildlife Conservation", "topic": "wildfire", "location": "Hambantota, Sri Lanka", "date": "2024-07-14"},
    },
    {
        "content": "Forest fires in Knuckles Conservation Forest in Matale and Kandy districts have increased in frequency since 2018, coinciding with more intense dry seasons. Invasive grass species in cleared areas create high fuel loads that ignite easily during hot, dry pre-monsoon months. Fires damage cloud forest habitats that are critical for watershed protection and are home to numerous endemic species found nowhere else on Earth.",
        "metadata": {"source": "Forest Department Sri Lanka", "topic": "wildfire", "location": "Kandy, Sri Lanka", "date": "2024-03-15"},
    },
    {
        "content": "Horton Plains National Park in Nuwara Eliya district is experiencing increasing wildfire pressure during prolonged dry spells. The montane grasslands, locally called patanas, are fire-adapted but more frequent burning is altering species composition and degrading peat soils that store significant carbon reserves. Fire management balances conservation needs with the reality of climate-driven drying trends in the highland zone.",
        "metadata": {"source": "Department of Wildlife Conservation", "topic": "wildfire", "location": "Nuwara Eliya, Sri Lanka", "date": "2024-02-18"},
    },

    # Inland erosion
    {
        "content": "Inland soil erosion is a major climate-linked environmental threat in Sri Lanka's hill country, particularly in Nuwara Eliya, Badulla, and Ratnapura districts. Intense rainfall on steep slopes with inadequate ground cover removes topsoil at rates estimated at 20–80 tonnes per hectare per year in the most degraded areas. Eroded sediment reduces the lifespan of downstream reservoirs and irrigation canals, undermining long-term water security.",
        "metadata": {"source": "Central Environmental Authority", "topic": "erosion", "location": "Central Highlands, Sri Lanka", "date": "2024-05-05"},
    },
    {
        "content": "Streambank erosion along the Kelani and Kalu Ganga river systems has accelerated due to increased peak-flow events driven by changing rainfall patterns and upstream deforestation. Eroding banks threaten riverside homesteads, agricultural land, and rural road infrastructure. The Irrigation Department has prioritised bioengineering interventions — using vetiver grass and native tree planting — as cost-effective bank stabilisation measures.",
        "metadata": {"source": "Irrigation Department Sri Lanka", "topic": "erosion", "location": "Kegalle, Sri Lanka", "date": "2024-07-29"},
    },
    {
        "content": "Landslide-generated debris flows in Kandy and Matale districts carry large volumes of eroded soil into the Mahaweli River system. Sedimentation rates in Polgolla reservoir have increased measurably over the past decade, reducing active storage capacity and interfering with intake structures for the trans-basin irrigation tunnel that supplies water to the Dry Zone. Reforestation of critical upper catchment areas is identified as the most effective long-term erosion control strategy.",
        "metadata": {"source": "Mahaweli Authority of Sri Lanka", "topic": "erosion", "location": "Kandy, Sri Lanka", "date": "2024-08-22"},
    },

    # =========================================================================
    # National / cross-cutting documents
    # =========================================================================
    {
        "content": "Sri Lanka's updated Nationally Determined Contribution under the Paris Agreement commits to reducing greenhouse gas emissions by 14.5% unconditionally and 23% conditionally by 2030 relative to 2010 levels. The adaptation component includes establishing 100% renewable electricity by 2050, expanding climate-smart agriculture to 50% of cultivated area, and embedding climate risk screening into all public infrastructure investment decisions.",
        "metadata": {"source": "Ministry of Environment, Sri Lanka", "topic": "climate-policy", "location": "Sri Lanka", "date": "2024-11-10"},
    },
    {
        "content": "Sri Lanka's Multi-Hazard Early Warning System (MHEWS) provides integrated alerts for floods, landslides, cyclones, and drought through SMS, radio, and community siren networks. Coverage has expanded to 90% of high-risk Grama Niladhari divisions since 2020. Response time from hazard detection to community alert dissemination has improved from 6 hours to under 90 minutes for riverine flood events. Continued investment in last-mile communication remains a priority for reaching isolated rural communities.",
        "metadata": {"source": "Disaster Management Centre Sri Lanka", "topic": "climate-policy", "location": "Sri Lanka", "date": "2024-10-28"},
    },
    {
        "content": "Climate-induced internal migration is emerging as a growing challenge in Sri Lanka. Communities in flood-prone coastal areas of Galle and Kalutara, drought-stressed northern districts, and landslide-risk highland settlements are experiencing increasing out-migration. The World Bank estimates that without adaptation investment, 1.2 to 2.5 million Sri Lankans could be forced to relocate due to climate impacts by 2050.",
        "metadata": {"source": "World Meteorological Organization", "topic": "climate-policy", "location": "Sri Lanka", "date": "2024-09-15"},
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
