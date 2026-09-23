"""
Seed weather, temperature, and climate-condition documents into the FAISS vector store.

Why this script exists:
When users ask "what is the weather in [district]?" the FAISS store needs
district-level climate profile documents to supplement the live OpenWeatherMap
and Open-Meteo API results. Without these, the analysis agent has no contextual
reference for what "normal" conditions look like in each district, and can
misidentify routine weather as a hazard.

Documents added:
- Climate profile (temperature, rainfall pattern, humidity) for all 25 districts
- Heat and temperature context for districts with extreme seasonal variation
- Monsoon seasonality context for each district
- Overall Sri Lanka climate summary

Usage:
    1. Start the IR Agent:
       python -m app.agents.ir_agent.ir_agent
    2. Run this script:
       python scripts/seed_weather_data.py
"""

import sys
import httpx

IR_AGENT_URL = "http://localhost:8102/tools/index_document"

DOCUMENTS = [
    # =========================================================================
    # Sri Lanka national climate overview
    # =========================================================================
    {
        "content": "Sri Lanka has a tropical climate with temperatures ranging from 27°C to 32°C in coastal lowlands and 15°C to 25°C in the central highlands. The island receives rainfall from two monsoons: the southwest monsoon (May–September) and northeast monsoon (November–January). Humidity is consistently high, averaging 70–90% throughout the year. The inter-monsoon periods (March–April and October) bring convective thunderstorms across the island.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Sri Lanka", "date": "2024-01-01"},
    },
    {
        "content": "Sri Lanka experiences four distinct climate seasons driven by monsoon patterns. The first inter-monsoon (March–April) brings isolated thunderstorms. The southwest monsoon (May–September) delivers heavy rainfall to the western and central regions. The second inter-monsoon (October–November) brings widespread rain. The northeast monsoon (December–February) brings rain to the north and east. Average annual temperatures have risen 0.5°C since 1980.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Sri Lanka", "date": "2024-02-15"},
    },

    # =========================================================================
    # Colombo
    # =========================================================================
    {
        "content": "Colombo experiences a hot tropical climate year-round. Average daily temperatures range from 26°C at night to 32°C during the day. The city receives approximately 2,400mm of rainfall annually, primarily during the southwest monsoon. Humidity averages 75–90%. The urban heat island effect raises temperatures 1–2°C above surrounding areas. Peak heat occurs in March–April before the southwest monsoon onset.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Colombo, Sri Lanka", "date": "2024-03-01"},
    },

    # =========================================================================
    # Gampaha
    # =========================================================================
    {
        "content": "Gampaha district has a hot humid tropical climate similar to Colombo. Temperatures typically range from 25°C to 32°C throughout the year. The district receives heavy rainfall during the southwest monsoon (May–September), with monthly totals reaching 300–400mm. High humidity averaging 80–88% makes outdoor conditions feel significantly warmer than the recorded temperature. The Katunayake area near the international airport records some of the highest rainfall totals in the country.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Gampaha, Sri Lanka", "date": "2024-03-10"},
    },

    # =========================================================================
    # Kalutara
    # =========================================================================
    {
        "content": "Kalutara district has a wet tropical climate with some of the highest rainfall totals in Sri Lanka. The district receives over 2,500mm annually. Temperatures remain relatively constant at 26–31°C throughout the year. The southwest monsoon brings intense rainfall from May to August. Coastal areas experience sea breezes that moderate temperatures compared to inland areas. High humidity is persistent, rarely falling below 75%.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Kalutara, Sri Lanka", "date": "2024-04-01"},
    },

    # =========================================================================
    # Kandy
    # =========================================================================
    {
        "content": "Kandy city, situated at 500 metres elevation in the central highlands, has a cooler and more moderate climate than coastal Sri Lanka. Average temperatures range from 20°C at night to 29°C during the day. Annual rainfall is approximately 1,900mm, spread across both monsoon seasons. Humidity is moderate at 70–80%. The surrounding Kandy plateau creates localised rainfall patterns. Climate change has caused a gradual warming trend of approximately 0.7°C over the past three decades.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Kandy, Sri Lanka", "date": "2024-03-15"},
    },

    # =========================================================================
    # Matale
    # =========================================================================
    {
        "content": "Matale district has a transitional climate between the wet zone and dry zone. Temperatures average 26–32°C in the lowlands and 20–27°C in higher elevation areas near the Knuckles Range. The district receives rainfall from both monsoons, with annual totals of 1,500–2,000mm. Hot and dry conditions prevail from June to September in the lower valleys. The Dambulla area in the north of the district is significantly drier and hotter than the rest.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Matale, Sri Lanka", "date": "2024-04-05"},
    },

    # =========================================================================
    # Nuwara Eliya
    # =========================================================================
    {
        "content": "Nuwara Eliya is Sri Lanka's coolest district, situated at 1,889 metres above sea level. Average temperatures range from 8°C at night to 19°C during the day. The area receives over 2,500mm of rainfall annually from both monsoons and has frequent mist and cloud cover. Frost occurs occasionally in December and January. The cool climate supports tea cultivation and vegetable farming. Visitors should note that temperatures feel significantly colder than coastal Sri Lanka.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Nuwara Eliya, Sri Lanka", "date": "2024-02-20"},
    },

    # =========================================================================
    # Galle
    # =========================================================================
    {
        "content": "Galle district on Sri Lanka's southern coast has a warm tropical climate with temperatures of 25–31°C throughout the year. The southwest monsoon (May–September) brings heavy rainfall and strong winds from the Indian Ocean. Annual rainfall averages 2,200mm. Sea surface temperatures remain warm at 27–30°C year-round. Coastal humidity is high, typically 78–88%. During the southwest monsoon, Galle experiences rough seas and reduced sunshine hours.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Galle, Sri Lanka", "date": "2024-05-01"},
    },

    # =========================================================================
    # Matara
    # =========================================================================
    {
        "content": "Matara district has a hot tropical climate at the southern tip of Sri Lanka. Temperatures range from 24°C to 32°C throughout the year with minimal seasonal variation. The district receives approximately 2,100mm of annual rainfall, heavily concentrated in the southwest monsoon period. Coastal areas experience strong sea breezes during the monsoon season. High humidity averaging 78–85% is characteristic of the district.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Matara, Sri Lanka", "date": "2024-05-10"},
    },

    # =========================================================================
    # Hambantota
    # =========================================================================
    {
        "content": "Hambantota district is one of the hottest and driest districts in Sri Lanka due to its location in the rain shadow of the central highlands. Average temperatures range from 26°C to 34°C, with extreme heat events reaching 38°C during April and May. Annual rainfall is only 900–1,100mm, heavily concentrated in the northeast monsoon period. Low humidity during dry months creates arid conditions. The district experiences the most sunshine hours in Sri Lanka.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "heat-wave", "location": "Hambantota, Sri Lanka", "date": "2024-04-15"},
    },

    # =========================================================================
    # Jaffna
    # =========================================================================
    {
        "content": "Jaffna district has a semi-arid tropical climate with pronounced dry and wet seasons. Temperatures range from 25°C to 36°C, with April and May being the hottest months when temperatures regularly exceed 35°C. Annual rainfall is approximately 1,100mm, almost entirely from the northeast monsoon (November–January). The dry season from February to October is prolonged and hot. Sea breezes provide some relief in coastal areas. The limestone geology provides poor water retention, intensifying drought impacts.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Jaffna, Sri Lanka", "date": "2024-04-20"},
    },

    # =========================================================================
    # Kilinochchi
    # =========================================================================
    {
        "content": "Kilinochchi district experiences a dry tropical climate with high temperatures and low rainfall. Average temperatures range from 26°C to 36°C. The extended dry season from February to October sees temperatures regularly exceeding 34°C with low humidity. The northeast monsoon (November–January) provides the majority of the annual rainfall of approximately 1,000mm. Hot and dusty conditions during the dry season pose health risks for outdoor workers and vulnerable populations.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "heat-wave", "location": "Kilinochchi, Sri Lanka", "date": "2024-04-25"},
    },

    # =========================================================================
    # Mannar
    # =========================================================================
    {
        "content": "Mannar district has a hot, arid tropical climate — one of the driest and hottest in Sri Lanka. Average temperatures of 28–36°C are common, and during April and May temperatures can reach 39°C. Annual rainfall averages only 900–1,000mm, restricted to the northeast monsoon season. Strong winds from the Gulf of Mannar provide some cooling but also increase evaporation. Water scarcity during the dry season is a regular challenge. The district records some of the highest heat index values in Sri Lanka.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "heat-wave", "location": "Mannar, Sri Lanka", "date": "2024-05-05"},
    },

    # =========================================================================
    # Vavuniya
    # =========================================================================
    {
        "content": "Vavuniya district has a dry tropical climate in the northern interior of Sri Lanka. Temperatures average 26–35°C with significant diurnal variation. The dry season (February–October) is long and hot. Annual rainfall of approximately 1,100mm arrives mainly in the northeast monsoon period. Inland location away from sea breezes means temperatures feel higher. Pre-monsoon heat (March–May) regularly exceeds 37°C.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Vavuniya, Sri Lanka", "date": "2024-04-10"},
    },

    # =========================================================================
    # Mullaitivu
    # =========================================================================
    {
        "content": "Mullaitivu district on the northeast coast has a tropical climate moderated by sea breezes from the Bay of Bengal. Temperatures range from 25°C to 34°C. The northeast monsoon (November–January) is the main rainfall season, delivering 1,200–1,500mm. The remaining months are hot and dry. Coastal humidity is high during the monsoon season but drops significantly in the dry period. Cyclone season (October–December) requires particular weather vigilance.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Mullaitivu, Sri Lanka", "date": "2024-03-20"},
    },

    # =========================================================================
    # Trincomalee
    # =========================================================================
    {
        "content": "Trincomalee district on the northeast coast experiences a hot tropical climate with two distinct seasons. The northeast monsoon (November–January) brings heavy rainfall and rough seas. The dry season (May–September) is hot and sunny with temperatures reaching 34–38°C. Annual rainfall averages 1,500mm. The natural harbour moderates extreme temperatures in the city area. Strong seasonal winds are characteristic — northeast monsoon winds from the Bay of Bengal and southwest winds during the dry season.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Trincomalee, Sri Lanka", "date": "2024-03-25"},
    },

    # =========================================================================
    # Batticaloa
    # =========================================================================
    {
        "content": "Batticaloa district on the east coast has a tropical climate governed by the northeast monsoon. Average temperatures range from 25°C to 33°C. The northeast monsoon (October–January) is the primary rainfall season, delivering 1,600–1,900mm. The dry season (May–September) is hot with low rainfall. Coastal humidity is high year-round. The lagoon system provides some temperature moderation. Batticaloa experiences more rainfall than the northern districts due to its more southerly location.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Batticaloa, Sri Lanka", "date": "2024-03-30"},
    },

    # =========================================================================
    # Ampara
    # =========================================================================
    {
        "content": "Ampara district in the southeastern part of Sri Lanka has a dry tropical climate with distinct wet and dry seasons. Temperatures average 27–33°C in coastal areas and 24–30°C in the higher inland areas near the Knuckles foothills. Annual rainfall of 1,400–1,800mm is concentrated in the northeast monsoon period. The dry season from May to September is hot and largely rainless in the coastal areas. Ampara town and surrounding paddy areas experience significant temperature fluctuation between day and night.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Ampara, Sri Lanka", "date": "2024-04-02"},
    },

    # =========================================================================
    # Polonnaruwa
    # =========================================================================
    {
        "content": "Polonnaruwa district in the north-central dry zone has a hot tropical climate with long dry seasons. Average temperatures range from 27°C to 35°C, with the pre-monsoon period (March–May) recording the highest temperatures, often exceeding 37°C. Annual rainfall of 1,500–1,700mm arrives mainly from the northeast monsoon. The ancient city of Polonnaruwa and surrounding agricultural areas are exposed to intense heat during the dry season. Irrigation tanks moderate local humidity around the reservoir system.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "heat-wave", "location": "Polonnaruwa, Sri Lanka", "date": "2024-04-08"},
    },

    # =========================================================================
    # Anuradhapura
    # =========================================================================
    {
        "content": "Anuradhapura district is one of the hottest districts in Sri Lanka, with a dry tropical climate and extended dry season. Temperatures regularly reach 36–39°C in April and May before the onset of the northeast monsoon. Average temperatures range from 24°C at night to 34°C during the day. Annual rainfall of 1,200–1,400mm is spread across both monsoons but insufficient to prevent long dry spells. The flat terrain provides no topographic relief from heat. Heat stress is a significant risk for outdoor agricultural workers.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "heat-wave", "location": "Anuradhapura, Sri Lanka", "date": "2024-04-12"},
    },

    # =========================================================================
    # Kurunegala
    # =========================================================================
    {
        "content": "Kurunegala district lies in the transitional zone between Sri Lanka's wet and dry zones. Temperatures range from 24°C to 33°C, with the pre-monsoon period (March–April) being the hottest. Annual rainfall of 1,600–1,800mm comes from both monsoons. The district experiences hot and dry conditions from June to September. Kurunegala town records higher temperatures than surrounding areas due to its urban heat island effect. Humidity is moderate at 65–80%.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Kurunegala, Sri Lanka", "date": "2024-03-05"},
    },

    # =========================================================================
    # Puttalam
    # =========================================================================
    {
        "content": "Puttalam district on the northwest coast has a hot and relatively dry climate. Temperatures range from 25°C to 35°C, with peak heat in April and May. Annual rainfall of 900–1,100mm is low compared to western Sri Lanka, as the district sits partly in the rain shadow during the southwest monsoon. Sea breezes moderate coastal temperatures but the inland salt flat areas experience severe heat. The district has one of the longest sunshine durations in Sri Lanka.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Puttalam, Sri Lanka", "date": "2024-03-12"},
    },

    # =========================================================================
    # Kegalle
    # =========================================================================
    {
        "content": "Kegalle district in the Sabaragamuwa foothills has a warm and very wet tropical climate. Temperatures range from 22°C to 31°C, with highland areas being noticeably cooler. The district is one of the wettest in Sri Lanka, receiving 3,000–4,000mm of annual rainfall from both monsoons. High humidity of 80–90% is characteristic throughout the year. The wet conditions support extensive rubber cultivation. Cloud cover is frequent, limiting sunshine hours compared to coastal areas.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Kegalle, Sri Lanka", "date": "2024-03-18"},
    },

    # =========================================================================
    # Ratnapura
    # =========================================================================
    {
        "content": "Ratnapura, known as the City of Gems, is one of the wettest places in Sri Lanka. The district receives over 3,500mm of rainfall annually, making it exceptionally wet. Temperatures range from 22°C to 32°C, moderated by the elevated terrain and frequent cloud cover. Humidity is persistently high at 85–95%. The orographic effect of the central highlands causes intense rainfall events during both monsoon seasons. Sunshine is limited due to persistent cloud cover.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Ratnapura, Sri Lanka", "date": "2024-03-22"},
    },

    # =========================================================================
    # Badulla
    # =========================================================================
    {
        "content": "Badulla district in the Uva highlands has a cooler, variable climate due to its elevation of 600–2,000 metres. Temperatures range from 14°C at night in highland areas to 28°C during the day in lower valleys. Annual rainfall varies dramatically from 1,200mm in the Uva basin to over 2,500mm on windward slopes. The Uva dry season (July–September) is distinctive — a dry continental air mass creates unusually low humidity and clear skies. This seasonal dryness is critical for tea processing.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Badulla, Sri Lanka", "date": "2024-02-25"},
    },

    # =========================================================================
    # Monaragala
    # =========================================================================
    {
        "content": "Monaragala district in the Uva province spans from lowland dry zone to highland wet zone. Temperatures in the lowlands average 27–35°C while highland areas are considerably cooler at 20–28°C. Annual rainfall ranges from 1,200mm in the dry lowlands to 2,000mm in the highlands. The dry season (May–September) in the lowland areas can be prolonged with temperatures exceeding 36°C. The district's agricultural communities are highly vulnerable to temperature extremes and irregular rainfall.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Monaragala, Sri Lanka", "date": "2024-04-18"},
    },

    # =========================================================================
    # Additional climate-health documents for high-heat districts
    # =========================================================================
    {
        "content": "Heat-related illness is a growing public health concern in Sri Lanka's dry zone districts including Anuradhapura, Polonnaruwa, Hambantota, Mannar, and Kilinochchi. Agricultural workers in these districts face elevated risk of heat exhaustion and heatstroke during the pre-monsoon period (March–May). The Ministry of Health has issued heat action guidelines recommending hydration, work schedule adjustment, and rest periods during peak heat hours (11am–3pm). Climate change projections indicate 30–40 additional extreme heat days per year by 2050.",
        "metadata": {"source": "Epidemiology Unit, Ministry of Health Sri Lanka", "topic": "climate-health", "location": "Dry Zone, Sri Lanka", "date": "2024-05-15"},
    },
    {
        "content": "Urban heat island effects in Sri Lanka's major cities — Colombo, Kandy, Galle, and Jaffna — amplify ambient temperatures by 1–3°C compared to surrounding rural areas. Paved surfaces, reduced vegetation, and waste heat from buildings and vehicles contribute to elevated urban temperatures. Night-time temperatures in urban areas remain 2–4°C warmer than rural zones, reducing the body's overnight recovery from heat stress. Green infrastructure such as urban trees and parks can reduce the urban heat island effect by up to 2°C.",
        "metadata": {"source": "World Meteorological Organization", "topic": "heat-wave", "location": "Sri Lanka", "date": "2024-06-01"},
    },
    {
        "content": "Sri Lanka's monsoon transition periods — March to April and October to November — are characterised by high humidity combined with moderate temperatures of 28–33°C. The combination of high temperature and high relative humidity creates apparent (feels-like) temperatures of 35–42°C, significantly increasing physiological heat stress. The wet bulb globe temperature (WBGT) index regularly reaches dangerous levels for outdoor workers during these transition periods. Sri Lanka's Occupational Health Department recommends acclimatisation protocols for workers new to outdoor activities during these months.",
        "metadata": {"source": "Occupational Health Unit, Ministry of Health Sri Lanka", "topic": "climate-health", "location": "Sri Lanka", "date": "2024-04-30"},
    },
    {
        "content": "Rainfall patterns across Sri Lanka in 2024 showed significant spatial variability. The southwest monsoon delivered above-average rainfall to Colombo, Gampaha, Kalutara, and Ratnapura districts. The northeast monsoon was below average in Jaffna, Kilinochchi, and Mannar. Central highland districts — Kandy, Nuwara Eliya, and Badulla — received near-average annual totals. Climate projections from the Department of Meteorology indicate increasing rainfall intensity with shorter duration events, raising runoff and flood risk even in districts with average total rainfall.",
        "metadata": {"source": "Department of Meteorology Sri Lanka", "topic": "temperature", "location": "Sri Lanka", "date": "2024-12-20"},
    },
]


def main():
    print(f"Seeding {len(DOCUMENTS)} weather/climate documents into the IR Agent's vector store...\n")

    success_count = 0
    fail_count = 0

    with httpx.Client(timeout=10.0) as client:
        for i, doc in enumerate(DOCUMENTS, start=1):
            try:
                resp = client.post(IR_AGENT_URL, json=doc)
                resp.raise_for_status()
                result = resp.json()

                if result.get("indexed"):
                    loc = doc["metadata"].get("location", "?")
                    topic = doc["metadata"].get("topic", "?")
                    print(f"[{i:2}/{len(DOCUMENTS)}] {loc:35} | {topic}")
                    success_count += 1
                else:
                    print(f"[{i:2}/{len(DOCUMENTS)}] FAILED: {result.get('error', 'unknown error')}")
                    fail_count += 1

            except httpx.ConnectError:
                print("Could not connect to the IR Agent at http://localhost:8102")
                print("Make sure it is running: python -m app.agents.ir_agent.ir_agent")
                sys.exit(1)
            except Exception as e:
                print(f"[{i:2}/{len(DOCUMENTS)}] FAILED: {e}")
                fail_count += 1

    print(f"\nDone. {success_count} indexed, {fail_count} failed.")
    print("Restart the IR agent and backend for changes to take effect.")


if __name__ == "__main__":
    main()
