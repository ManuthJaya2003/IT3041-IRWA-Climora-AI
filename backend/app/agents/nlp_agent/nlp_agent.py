"""
NLP Agent (Query & NLP Agent) - MCP Server

Responsibilities:
- Intent detection: Identify what the user wants (risk_awareness, forecast, preparedness, etc.)
- Entity extraction: Extract location, date/time, climate topic, hazard type
- Query expansion: Add related terms to improve retrieval
- Summarization: Condense long text into concise evidence snippets

Tools exposed via MCP:
- process_query: Full NLP pipeline on user input
- extract_entities: Named Entity Recognition for climate entities
- expand_query: Query expansion for better retrieval
- summarize_text: Summarize retrieved documents

Design notes:
- The core pipeline is rule-based so the agent works with zero external
  dependencies (mirrors the orchestrator's fallback NLP but is more complete).
- If spaCy is installed, it is used to enrich location/date entity extraction.
- If the LLM is available, it is used to refine query expansion and to power
  summarization. Every LLM/spaCy path degrades gracefully to rules on failure.

Output contract (consumed by the Orchestrator + IR Agent):
    process_query -> {
        "intent": str,
        "entities": {location, date, climate_topic, hazard_type},
        "structured_query": {"original_query": str, "processed": True},
        "expanded_terms": [str, ...],
        "expanded_query": str,
    }

Port: 8101
"""

import logging

from app.mcp.base_agent_server import BaseAgentServer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static knowledge bases (kept module-level so they are built once per process)
# ---------------------------------------------------------------------------

# All 25 Sri Lanka districts + 9 provinces + common sub-regions.
# Ordered longest/most specific first so "nuwara eliya" matches before "eliya".
# ---------------------------------------------------------------------------
# Sri Lanka gazetteer — kept as SEPARATE lists by category so districts,
# cities/towns, provinces, regions and Sinhala/Tamil names can be maintained
# independently. SRI_LANKA_LOCATIONS (combined, longest-first) is the single
# list the matcher iterates, preserving previous matching behaviour.
# ---------------------------------------------------------------------------

# 25 administrative districts (canonical spellings).
SRI_LANKA_DISTRICTS: list[tuple[str, str]] = [
    ("nuwara eliya",            "Nuwara Eliya, Sri Lanka"),
    ("anuradhapura",            "Anuradhapura, Sri Lanka"),
    ("polonnaruwa",             "Polonnaruwa, Sri Lanka"),
    ("trincomalee",             "Trincomalee, Sri Lanka"),
    ("hambantota",              "Hambantota, Sri Lanka"),
    ("kilinochchi",             "Kilinochchi, Sri Lanka"),
    ("mullaitivu",              "Mullaitivu, Sri Lanka"),
    ("vavuniya",                "Vavuniya, Sri Lanka"),
    ("batticaloa",              "Batticaloa, Sri Lanka"),
    ("monaragala",              "Monaragala, Sri Lanka"),
    ("kurunegala",              "Kurunegala, Sri Lanka"),
    ("ratnapura",               "Ratnapura, Sri Lanka"),
    ("kalutara",                "Kalutara, Sri Lanka"),
    ("gampaha",                 "Gampaha, Sri Lanka"),
    ("matale",                  "Matale, Sri Lanka"),
    ("badulla",                 "Badulla, Sri Lanka"),
    ("kegalle",                 "Kegalle, Sri Lanka"),
    ("ampara",                  "Ampara, Sri Lanka"),
    ("puttalam",                "Puttalam, Sri Lanka"),
    ("matara",                  "Matara, Sri Lanka"),
    ("mannar",                  "Mannar, Sri Lanka"),
    ("kandy",                   "Kandy, Sri Lanka"),
    ("galle",                   "Galle, Sri Lanka"),
    ("jaffna",                  "Jaffna, Sri Lanka"),
    ("colombo",                 "Colombo, Sri Lanka"),
]

# Alternate district spellings, abbreviations and transliterations.
SRI_LANKA_DISTRICT_ALIASES: list[tuple[str, str]] = [
    ("nuwaraeliya",             "Nuwara Eliya, Sri Lanka"),
    ("nuwara-eliya",            "Nuwara Eliya, Sri Lanka"),
    ("moneragala",              "Monaragala, Sri Lanka"),
    ("monaragla",               "Monaragala, Sri Lanka"),
    ("kegalla",                 "Kegalle, Sri Lanka"),
    ("kegala",                  "Kegalle, Sri Lanka"),
    ("anuradapura",             "Anuradhapura, Sri Lanka"),
    ("anuradhapuraya",          "Anuradhapura, Sri Lanka"),
    ("polonaruwa",              "Polonnaruwa, Sri Lanka"),
    ("pollonnaruwa",            "Polonnaruwa, Sri Lanka"),
    ("batticalo",               "Batticaloa, Sri Lanka"),
    ("mullativu",               "Mullaitivu, Sri Lanka"),
    ("mulativu",                "Mullaitivu, Sri Lanka"),
    ("mullaitheevu",            "Mullaitivu, Sri Lanka"),
    ("killinochchi",            "Kilinochchi, Sri Lanka"),
    ("kilinochi",               "Kilinochchi, Sri Lanka"),
    ("hambanthota",             "Hambantota, Sri Lanka"),
    ("kurunegela",              "Kurunegala, Sri Lanka"),
    ("kurunagala",              "Kurunegala, Sri Lanka"),
    ("puttlam",                 "Puttalam, Sri Lanka"),
    ("vavunia",                 "Vavuniya, Sri Lanka"),
    ("amparai",                 "Ampara, Sri Lanka"),
    ("trinco",                  "Trincomalee, Sri Lanka"),
    ("kaluthara",               "Kalutara, Sri Lanka"),
]

# Cities, towns and DS divisions -> their district.
SRI_LANKA_CITIES: list[tuple[str, str]] = [
    ("ambalantota",             "Hambantota, Sri Lanka"),
    ("vavuniya south",          "Vavuniya, Sri Lanka"),
    ("kalpitiya",               "Kalpitiya, Sri Lanka"),
    ("tangalle",                "Hambantota, Sri Lanka"),
    ("moratuwa",                "Colombo, Sri Lanka"),
    ("kotte",                   "Colombo, Sri Lanka"),
    ("gampola",                 "Kandy, Sri Lanka"),
    ("ella",                    "Badulla, Sri Lanka"),
    ("mirissa",                 "Matara, Sri Lanka"),
    ("chilaw",                  "Puttalam, Sri Lanka"),
    ("kuliyapitiya",            "Kurunegala, Sri Lanka"),
    ("embilipitiya",            "Ratnapura, Sri Lanka"),
    ("yarlpanam",               "Jaffna, Sri Lanka"),
    ("point pedro",             "Jaffna, Sri Lanka"),
    ("negombo",                 "Gampaha, Sri Lanka"),
    ("dambulla",                "Matale, Sri Lanka"),
    ("sigiriya",                "Matale, Sri Lanka"),
    ("peradeniya",              "Kandy, Sri Lanka"),
    ("hikkaduwa",               "Galle, Sri Lanka"),
    ("bentota",                 "Galle, Sri Lanka"),
    ("sri jayawardenepura kotte", "Colombo, Sri Lanka"),
    ("nugegoda",                "Colombo, Sri Lanka"),
    ("maharagama",              "Colombo, Sri Lanka"),
    ("dehiwala",                "Colombo, Sri Lanka"),
    ("mount lavinia",           "Colombo, Sri Lanka"),
    ("kesbewa",                 "Colombo, Sri Lanka"),
    ("homagama",                "Colombo, Sri Lanka"),
    ("piliyandala",             "Colombo, Sri Lanka"),
    ("boralesgamuwa",           "Colombo, Sri Lanka"),
    ("kolonnawa",               "Colombo, Sri Lanka"),
    ("kaduwela",                "Colombo, Sri Lanka"),
    ("avissawella",             "Colombo, Sri Lanka"),
    ("padukka",                 "Colombo, Sri Lanka"),
    ("wattala",                 "Gampaha, Sri Lanka"),
    ("mirigama",                "Gampaha, Sri Lanka"),
    ("minuwangoda",             "Gampaha, Sri Lanka"),
    ("attanagalla",             "Gampaha, Sri Lanka"),
    ("kelaniya",                "Gampaha, Sri Lanka"),
    ("biyagama",                "Gampaha, Sri Lanka"),
    ("kiribathgoda",            "Gampaha, Sri Lanka"),
    ("katana",                  "Gampaha, Sri Lanka"),
    ("divulapitiya",            "Gampaha, Sri Lanka"),
    ("panadura",                "Kalutara, Sri Lanka"),
    ("horana",                  "Kalutara, Sri Lanka"),
    ("bandaragama",             "Kalutara, Sri Lanka"),
    ("wadduwa",                 "Kalutara, Sri Lanka"),
    ("beruwala",                "Kalutara, Sri Lanka"),
    ("aluthgama",               "Kalutara, Sri Lanka"),
    ("mathugama",               "Kalutara, Sri Lanka"),
    ("agalawatta",              "Kalutara, Sri Lanka"),
    ("bulathsinhala",           "Kalutara, Sri Lanka"),
    ("ingiriya",                "Kalutara, Sri Lanka"),
    ("nawalapitiya",            "Kandy, Sri Lanka"),
    ("katugastota",             "Kandy, Sri Lanka"),
    ("kundasale",               "Kandy, Sri Lanka"),
    ("galaha",                  "Kandy, Sri Lanka"),
    ("nugawela",                "Kandy, Sri Lanka"),
    ("galagedara",              "Kandy, Sri Lanka"),
    ("akurana",                 "Kandy, Sri Lanka"),
    ("pujapitiya",              "Kandy, Sri Lanka"),
    ("pathadumbara",            "Kandy, Sri Lanka"),
    ("udadumbara",              "Kandy, Sri Lanka"),
    ("minipe",                  "Kandy, Sri Lanka"),
    ("doluwa",                  "Kandy, Sri Lanka"),
    ("yatinuwara",              "Kandy, Sri Lanka"),
    ("udunuwara",               "Kandy, Sri Lanka"),
    ("galewela",                "Matale, Sri Lanka"),
    ("ukuwela",                 "Matale, Sri Lanka"),
    ("rattota",                 "Matale, Sri Lanka"),
    ("pallepola",               "Matale, Sri Lanka"),
    ("yatawatta",               "Matale, Sri Lanka"),
    ("naula",                   "Matale, Sri Lanka"),
    ("wilgamuwa",               "Matale, Sri Lanka"),
    ("laggala",                 "Matale, Sri Lanka"),
    ("hatton",                  "Nuwara Eliya, Sri Lanka"),
    ("talawakelle",             "Nuwara Eliya, Sri Lanka"),
    ("hanguranketha",           "Nuwara Eliya, Sri Lanka"),
    ("walapane",                "Nuwara Eliya, Sri Lanka"),
    ("kotmale",                 "Nuwara Eliya, Sri Lanka"),
    ("maskeliya",               "Nuwara Eliya, Sri Lanka"),
    ("nanu oya",                "Nuwara Eliya, Sri Lanka"),
    ("ambalangoda",             "Galle, Sri Lanka"),
    ("elpitiya",                "Galle, Sri Lanka"),
    ("baddegama",               "Galle, Sri Lanka"),
    ("karapitiya",              "Galle, Sri Lanka"),
    ("habaraduwa",              "Galle, Sri Lanka"),
    ("imaduwa",                 "Galle, Sri Lanka"),
    ("weligama",                "Matara, Sri Lanka"),
    ("akuressa",                "Matara, Sri Lanka"),
    ("kamburupitiya",           "Matara, Sri Lanka"),
    ("hakmana",                 "Matara, Sri Lanka"),
    ("dikwella",                "Matara, Sri Lanka"),
    ("devinuwara",              "Matara, Sri Lanka"),
    ("malimbada",               "Matara, Sri Lanka"),
    ("tissamaharama",           "Hambantota, Sri Lanka"),
    ("beliatta",                "Hambantota, Sri Lanka"),
    ("weeraketiya",             "Hambantota, Sri Lanka"),
    ("katuwana",                "Hambantota, Sri Lanka"),
    ("sooriyawewa",             "Hambantota, Sri Lanka"),
    ("lunugamvehera",           "Hambantota, Sri Lanka"),
    ("chavakachcheri",          "Jaffna, Sri Lanka"),
    ("nallur",                  "Jaffna, Sri Lanka"),
    ("kopay",                   "Jaffna, Sri Lanka"),
    ("tellippalai",             "Jaffna, Sri Lanka"),
    ("karainagar",              "Jaffna, Sri Lanka"),
    ("velanai",                 "Jaffna, Sri Lanka"),
    ("kayts",                   "Jaffna, Sri Lanka"),
    ("paranthan",               "Kilinochchi, Sri Lanka"),
    ("poonakari",               "Kilinochchi, Sri Lanka"),
    ("kandavalai",              "Kilinochchi, Sri Lanka"),
    ("karachchi",               "Kilinochchi, Sri Lanka"),
    ("pallai",                  "Kilinochchi, Sri Lanka"),
    ("nanattan",                "Mannar, Sri Lanka"),
    ("musali",                  "Mannar, Sri Lanka"),
    ("madhu",                   "Mannar, Sri Lanka"),
    ("manthai",                 "Mannar, Sri Lanka"),
    ("cheddikulam",             "Vavuniya, Sri Lanka"),
    ("nedunkerny",              "Vavuniya, Sri Lanka"),
    ("puthukudiyiruppu",        "Mullaitivu, Sri Lanka"),
    ("oddusuddan",              "Mullaitivu, Sri Lanka"),
    ("welioya",                 "Mullaitivu, Sri Lanka"),
    ("thunukkai",               "Mullaitivu, Sri Lanka"),
    ("kattankudy",              "Batticaloa, Sri Lanka"),
    ("eravur",                  "Batticaloa, Sri Lanka"),
    ("kaluwanchikudy",          "Batticaloa, Sri Lanka"),
    ("valaichchenai",           "Batticaloa, Sri Lanka"),
    ("oddamavadi",              "Batticaloa, Sri Lanka"),
    ("kalkudah",                "Batticaloa, Sri Lanka"),
    ("kalmunai",                "Ampara, Sri Lanka"),
    ("akkaraipattu",            "Ampara, Sri Lanka"),
    ("pottuvil",                "Ampara, Sri Lanka"),
    ("sammanthurai",            "Ampara, Sri Lanka"),
    ("mahaoya",                 "Ampara, Sri Lanka"),
    ("uhana",                   "Ampara, Sri Lanka"),
    ("kinniya",                 "Trincomalee, Sri Lanka"),
    ("mutur",                   "Trincomalee, Sri Lanka"),
    ("kantale",                 "Trincomalee, Sri Lanka"),
    ("kuchchaveli",             "Trincomalee, Sri Lanka"),
    ("seruvila",                "Trincomalee, Sri Lanka"),
    ("narammala",               "Kurunegala, Sri Lanka"),
    ("wariyapola",              "Kurunegala, Sri Lanka"),
    ("pannala",                 "Kurunegala, Sri Lanka"),
    ("polgahawela",             "Kurunegala, Sri Lanka"),
    ("alawwa",                  "Kurunegala, Sri Lanka"),
    ("mawathagama",             "Kurunegala, Sri Lanka"),
    ("rideegama",               "Kurunegala, Sri Lanka"),
    ("wennappuwa",              "Puttalam, Sri Lanka"),
    ("nattandiya",              "Puttalam, Sri Lanka"),
    ("anamaduwa",               "Puttalam, Sri Lanka"),
    ("mundel",                  "Puttalam, Sri Lanka"),
    ("pallama",                 "Puttalam, Sri Lanka"),
    ("kekirawa",                "Anuradhapura, Sri Lanka"),
    ("eppawala",                "Anuradhapura, Sri Lanka"),
    ("mihintale",               "Anuradhapura, Sri Lanka"),
    ("medawachchiya",           "Anuradhapura, Sri Lanka"),
    ("horowpothana",            "Anuradhapura, Sri Lanka"),
    ("galnewa",                 "Anuradhapura, Sri Lanka"),
    ("tambuttegama",            "Anuradhapura, Sri Lanka"),
    ("nochchiyagama",           "Anuradhapura, Sri Lanka"),
    ("kaduruwela",              "Polonnaruwa, Sri Lanka"),
    ("hingurakgoda",            "Polonnaruwa, Sri Lanka"),
    ("medirigiriya",            "Polonnaruwa, Sri Lanka"),
    ("elahera",                 "Polonnaruwa, Sri Lanka"),
    ("dimbulagala",             "Polonnaruwa, Sri Lanka"),
    ("lankapura",               "Polonnaruwa, Sri Lanka"),
    ("bandarawela",             "Badulla, Sri Lanka"),
    ("haputale",                "Badulla, Sri Lanka"),
    ("welimada",                "Badulla, Sri Lanka"),
    ("mahiyanganaya",           "Badulla, Sri Lanka"),
    ("passara",                 "Badulla, Sri Lanka"),
    ("lunugala",                "Badulla, Sri Lanka"),
    ("wellawaya",               "Monaragala, Sri Lanka"),
    ("bibile",                  "Monaragala, Sri Lanka"),
    ("medagama",                "Monaragala, Sri Lanka"),
    ("siyambalanduwa",          "Monaragala, Sri Lanka"),
    ("buttala",                 "Monaragala, Sri Lanka"),
    ("katharagama",             "Monaragala, Sri Lanka"),
    ("balangoda",               "Ratnapura, Sri Lanka"),
    ("eheliyagoda",             "Ratnapura, Sri Lanka"),
    ("kuruwita",                "Ratnapura, Sri Lanka"),
    ("pelmadulla",              "Ratnapura, Sri Lanka"),
    ("nivithigala",             "Ratnapura, Sri Lanka"),
    ("kahawatta",               "Ratnapura, Sri Lanka"),
    ("godakawela",              "Ratnapura, Sri Lanka"),
    ("mawanella",               "Kegalle, Sri Lanka"),
    ("rambukkana",              "Kegalle, Sri Lanka"),
    ("yatiyantota",             "Kegalle, Sri Lanka"),
    ("dehiowita",               "Kegalle, Sri Lanka"),
    ("warakapola",              "Kegalle, Sri Lanka"),
    ("ruwanwella",              "Kegalle, Sri Lanka"),
    ("galigamuwa",              "Kegalle, Sri Lanka"),
    ("aranayaka",               "Kegalle, Sri Lanka"),
    ("ratmalana",               "Colombo, Sri Lanka"),
    ("kottawa",                 "Colombo, Sri Lanka"),
    ("veyangoda",               "Gampaha, Sri Lanka"),
    ("nittambuwa",              "Gampaha, Sri Lanka"),
    ("weliweriya",              "Gampaha, Sri Lanka"),
    ("pugoda",                  "Gampaha, Sri Lanka"),
    ("kirindiwela",             "Gampaha, Sri Lanka"),
    ("dodangoda",               "Kalutara, Sri Lanka"),
    ("millaniya",               "Kalutara, Sri Lanka"),
    ("palindanuwara",           "Kalutara, Sri Lanka"),
    ("udapalatha",              "Kandy, Sri Lanka"),
    ("thumpane",                "Kandy, Sri Lanka"),
    ("harispattuwa",            "Kandy, Sri Lanka"),
    ("medadumbara",             "Kandy, Sri Lanka"),
    ("hatharaliyadda",          "Kandy, Sri Lanka"),
    ("ambanganga",              "Matale, Sri Lanka"),
    ("udapussellawa",           "Nuwara Eliya, Sri Lanka"),
    ("nildandahinna",           "Nuwara Eliya, Sri Lanka"),
    ("yakkalamulla",            "Galle, Sri Lanka"),
    ("nagoda",                  "Galle, Sri Lanka"),
    ("thawalama",               "Galle, Sri Lanka"),
    ("neluwa",                  "Galle, Sri Lanka"),
    ("hiniduma",                "Galle, Sri Lanka"),
    ("pitabeddara",             "Matara, Sri Lanka"),
    ("kotapola",                "Matara, Sri Lanka"),
    ("pasgoda",                 "Matara, Sri Lanka"),
    ("thihagoda",               "Matara, Sri Lanka"),
    ("okewela",                 "Hambantota, Sri Lanka"),
    ("angunakolapelessa",       "Hambantota, Sri Lanka"),
    ("sandilipay",              "Jaffna, Sri Lanka"),
    ("uduvil",                  "Jaffna, Sri Lanka"),
    ("maruthankerny",           "Jaffna, Sri Lanka"),
    ("karanthurai",             "Jaffna, Sri Lanka"),
    ("pungudutivu",             "Jaffna, Sri Lanka"),
    ("karaveddy",               "Jaffna, Sri Lanka"),
    ("vaddukoddai",             "Jaffna, Sri Lanka"),
    ("atpatti",                 "Mannar, Sri Lanka"),
    ("vankalai",                "Mannar, Sri Lanka"),
    ("manthai east",            "Mullaitivu, Sri Lanka"),
    ("kiran",                   "Batticaloa, Sri Lanka"),
    ("kalkudah",                "Batticaloa, Sri Lanka"),
    ("chenkalady",              "Batticaloa, Sri Lanka"),
    ("dehiattakandiya",         "Ampara, Sri Lanka"),
    ("gomon",                   "Trincomalee, Sri Lanka"),
    ("gomarankadawala",         "Trincomalee, Sri Lanka"),
    ("morawewa",                "Trincomalee, Sri Lanka"),
    ("giribawa",                "Kurunegala, Sri Lanka"),
    ("mahawa",                  "Kurunegala, Sri Lanka"),
    ("hiriyala",                "Kurunegala, Sri Lanka"),
    ("arachchikattuwa",         "Puttalam, Sri Lanka"),
    ("kahatagasdigiliya",       "Anuradhapura, Sri Lanka"),
    ("mahavilachchiya",         "Anuradhapura, Sri Lanka"),
    ("haliela",                 "Badulla, Sri Lanka"),
    ("meegahakiula",            "Badulla, Sri Lanka"),
    ("badalkumbura",            "Monaragala, Sri Lanka"),
    ("weligepola",              "Ratnapura, Sri Lanka"),
    ("ayagama",                 "Ratnapura, Sri Lanka"),
    ("bulathkohupitiya",        "Kegalle, Sri Lanka"),
    ("knuckles",                "Matale, Sri Lanka"),
    ("horton plains",           "Nuwara Eliya, Sri Lanka"),
    ("wilpattu",                "Anuradhapura, Sri Lanka"),
    ("yala",                    "Hambantota, Sri Lanka"),
    ("kelani",                  "Colombo, Sri Lanka"),
]

# Provinces.
SRI_LANKA_PROVINCES: list[tuple[str, str]] = [
    ("western province",        "Western Province, Sri Lanka"),
    ("central province",        "Central Province, Sri Lanka"),
    ("southern province",       "Southern Province, Sri Lanka"),
    ("northern province",       "Northern Province, Sri Lanka"),
    ("eastern province",        "Eastern Province, Sri Lanka"),
    ("north western province",  "North Western Province, Sri Lanka"),
    ("north central province",  "North Central Province, Sri Lanka"),
    ("uva province",            "Uva Province, Sri Lanka"),
    ("sabaragamuwa",            "Sabaragamuwa Province, Sri Lanka"),
]

# Geographic regions, landmarks and the country name.
SRI_LANKA_REGIONS: list[tuple[str, str]] = [
    ("dry zone",                "Dry Zone, Sri Lanka"),
    ("hill country",            "Central Highlands, Sri Lanka"),
    ("sinharaja",               "Sinharaja, Sri Lanka"),
    ("mahaweli",                "Mahaweli Basin, Sri Lanka"),
    ("sri lanka",               "Sri Lanka"),
    ("ශ්‍රී ලංකා",              "Sri Lanka"),
    ("இலங்கை",                  "Sri Lanka"),
    ("වියළි කලාප",              "Dry Zone, Sri Lanka"),
    ("வறண்ட வலய",               "Dry Zone, Sri Lanka"),
    ("මධ්‍යම කඳුකර",            "Central Highlands, Sri Lanka"),
    ("மத்திய மலைநாடு",          "Central Highlands, Sri Lanka"),
]

# Sinhala / Tamil district, province and zone names.
SRI_LANKA_LOCAL_NAMES: list[tuple[str, str]] = [
    ("කොළඹ",                    "Colombo, Sri Lanka"),
    ("கொழும்பு",                "Colombo, Sri Lanka"),
    ("கொழும்ப",                 "Colombo, Sri Lanka"),
    ("ගම්පහ",                   "Gampaha, Sri Lanka"),
    ("கம்பஹா",                  "Gampaha, Sri Lanka"),
    ("කළුතර",                   "Kalutara, Sri Lanka"),
    ("களுத்துறை",               "Kalutara, Sri Lanka"),
    ("මහනුවර",                  "Kandy, Sri Lanka"),
    ("கண்டி",                   "Kandy, Sri Lanka"),
    ("මාතලේ",                   "Matale, Sri Lanka"),
    ("மாத்தளை",                 "Matale, Sri Lanka"),
    ("නුවරඑළිය",                "Nuwara Eliya, Sri Lanka"),
    ("நுவரெலியா",               "Nuwara Eliya, Sri Lanka"),
    ("ගාල්ල",                   "Galle, Sri Lanka"),
    ("காலி",                    "Galle, Sri Lanka"),
    ("මාතර",                    "Matara, Sri Lanka"),
    ("மாத்தறை",                 "Matara, Sri Lanka"),
    ("හම්බන්තොට",               "Hambantota, Sri Lanka"),
    ("அம்பாந்தோட்டை",           "Hambantota, Sri Lanka"),
    ("යාපනය",                   "Jaffna, Sri Lanka"),
    ("யாழ்ப்பாணம்",             "Jaffna, Sri Lanka"),
    ("කිලිනොච්චි",              "Kilinochchi, Sri Lanka"),
    ("கிளிநொச்சி",              "Kilinochchi, Sri Lanka"),
    ("මන්නාරම",                 "Mannar, Sri Lanka"),
    ("மன்னார்",                 "Mannar, Sri Lanka"),
    ("වව්නියාව",                "Vavuniya, Sri Lanka"),
    ("வவுனியா",                 "Vavuniya, Sri Lanka"),
    ("මුලතිව්",                 "Mullaitivu, Sri Lanka"),
    ("முல்லைத்தீவு",            "Mullaitivu, Sri Lanka"),
    ("මඩකලපුව",                 "Batticaloa, Sri Lanka"),
    ("மட்டக்களப்பு",            "Batticaloa, Sri Lanka"),
    ("අම්පාර",                  "Ampara, Sri Lanka"),
    ("அம்பாறை",                 "Ampara, Sri Lanka"),
    ("ත්‍රිකුණාමලය",            "Trincomalee, Sri Lanka"),
    ("திருகோணமலை",              "Trincomalee, Sri Lanka"),
    ("කුරුණෑගල",                "Kurunegala, Sri Lanka"),
    ("குருநாகல்",               "Kurunegala, Sri Lanka"),
    ("පුත්තලම",                 "Puttalam, Sri Lanka"),
    ("புத்தளம்",                "Puttalam, Sri Lanka"),
    ("අනුරාධපුරය",              "Anuradhapura, Sri Lanka"),
    ("அனுராதபுரம்",             "Anuradhapura, Sri Lanka"),
    ("පොළොන්නරුව",              "Polonnaruwa, Sri Lanka"),
    ("பொலன்னறுவை",              "Polonnaruwa, Sri Lanka"),
    ("බදුල්ල",                  "Badulla, Sri Lanka"),
    ("பதுளை",                   "Badulla, Sri Lanka"),
    ("මොණරාගල",                 "Monaragala, Sri Lanka"),
    ("மொனராகலை",                "Monaragala, Sri Lanka"),
    ("රත්නපුර",                 "Ratnapura, Sri Lanka"),
    ("இரத்தினபுரி",             "Ratnapura, Sri Lanka"),
    ("කෑගල්ල",                  "Kegalle, Sri Lanka"),
    ("கேகாலை",                  "Kegalle, Sri Lanka"),
]

# Combined matcher list (longest-first so specific towns such as
# "tangalle" match before any shorter district substring they contain).
# The generic country entry goes last so specific regions ("dry zone")
# win over "sri lanka" when both appear in one query.
SRI_LANKA_LOCATIONS: list[tuple[str, str]] = (
    SRI_LANKA_DISTRICTS
    + SRI_LANKA_DISTRICT_ALIASES
    + SRI_LANKA_CITIES
    + SRI_LANKA_PROVINCES
    + SRI_LANKA_REGIONS
    + SRI_LANKA_LOCAL_NAMES
)
SRI_LANKA_LOCATIONS.sort(key=lambda _entry: len(_entry[0]), reverse=True)
SRI_LANKA_LOCATIONS = [
    _entry for _entry in SRI_LANKA_LOCATIONS if _entry[0] != "sri lanka"
] + [("sri lanka", "Sri Lanka")]

# Inflection-tolerant stems for non-ASCII place names.
# Tamil case suffixes replace a final "ம்" (e.g. யாழ்ப்பாணம் -> யாழ்ப்பாணத்தில்
# "in Jaffna", அனுராதபுரம் -> அனுராதபுரத்தில்), so the base form is NOT a
# substring of inflected text and the exact matcher above misses it.
# Stems are checked only when no exact gazetteer entry matched, longest
# first, so they can never shadow a more specific exact hit.
SRI_LANKA_LOCATION_STEMS: list[tuple[str, str]] = []
for _kw, _canon in SRI_LANKA_LOCATIONS:
    if not _kw.isascii() and _kw.endswith("ம்") and len(_kw) > 3:
        _stem = _kw[:-2]  # strip "ம்" (U+0BAE + U+0BCD pulli)
        if len(_stem) >= 4 and all(_stem != _k for _k, _ in SRI_LANKA_LOCATIONS):
            SRI_LANKA_LOCATION_STEMS.append((_stem, _canon))
SRI_LANKA_LOCATION_STEMS.sort(key=lambda _entry: len(_entry[0]), reverse=True)
del _kw, _canon, _stem

# Climate topic -> keyword triggers. First match wins (dict preserves order).
# Sinhala/Tamil triggers are appended right after this dict (see below).
TOPIC_KEYWORDS: dict[str, list[str]] = {
    # Hazards first: "heat wave" must win over the generic "conditions"
    # trigger in temperature; plain "hot" still falls through correctly.
    "heat-wave":      ["heat wave", "heatwave", "heat stress", "heat island",
                       "extreme heat", "heat index"],
    # General weather — checked before remaining topics so
    # "weather/forecast/temperature" queries don't inherit a hazard topic.
    "temperature":    ["weather", "forecast", "humidity", "wind speed", "conditions",
                       "temperature", "hot", "warming", "cold", "climate change"],
    "flood":          ["flood", "flooding", "inundation", "overflow", "waterlog",
                       "flash flood", "river level", "discharge"],
    "drought":        ["drought", "dry spell", "water scarcity", "arid",
                       "low rainfall", "water shortage"],
    "cyclone":        ["cyclone", "hurricane", "typhoon", "tropical storm",
                       "storm surge", "wind speed"],
    "landslide":      ["landslide", "mudslide", "slope failure", "debris flow",
                       "hillside collapse"],
    "sea-level-rise": ["sea level", "coastal erosion", "shoreline erosion",
                       "tidal flooding", "sea", "ocean", "coast", "coastal",
                       "beach", "wave", "waves", "tide", "tides", "marine",
                       "fishing", "fisherman", "fishermen", "fisher", "fisheries",
                       "boat", "sailing", "harbour", "harbor"],
    "rain":           ["rainfall", "monsoon", "precipitation", "downpour",
                       "heavy rain", "rain"],
    "air-quality":    ["air quality", "pollution", "pm2.5", "smog",
                       "particulate", "aqi"],
    "wildfire":       ["wildfire", "forest fire", "fire risk", "bush fire",
                       "burning forest"],
    "erosion":        ["erosion", "soil erosion", "bank erosion", "sediment",
                       "topsoil loss"],
    "water-scarcity": ["groundwater", "aquifer", "water table",
                       "drinking water shortage", "water stress"],
    "agriculture":    ["crop failure", "crop damage", "harvest loss",
                       "farming climate", "climate agriculture", "drought crop",
                       "flood crop", "monsoon farming", "yield decline",
                       "agriculture", "irrigation", "fishing", "fisherman",
                       "fishermen", "fisheries", "catch"],
    "storm":          ["storm", "thunderstorm", "lightning", "gale", "wind", "waves"],
}

# Intent -> keyword triggers. Evaluated in priority order (most specific first).
INTENT_KEYWORDS: list[tuple[str, list[str]]] = [
    ("preparedness",  ["prepare", "should i", "what to do", "how to", "advice",
                       "protect", "ready", "precaution", "safety", "safe", "mitigate",
                       "is it safe", "travel advisory", "evacuate", "warning"]),
    ("forecast",      ["forecast", "predict", "next week", "tomorrow", "upcoming",
                       "this week", "will it", "expected", "outlook"]),
    ("trend_analysis",["history", "trend", "past", "change over", "last year",
                       "over the years", "historical", "compared to"]),
    ("risk_awareness",["risk", "danger", "threat", "vulnerable", "hazard",
                       "impact", "affected", "damage"]),
]

# Off-topic terms that should never be treated as climate questions even if
# a Sri Lanka place name is present (e.g. "Kandy train timetable").
# --- Sinhala / Tamil topic keywords (matching is by substring, so inflected forms
# such as "යාපනයේ" still match). Please have a native speaker review these lists.
_MULTILINGUAL_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "temperature":    ["කාලගුණ", "උෂ්ණත්ව", "දේශගුණ", "ආර්ද්‍රතා",            # Sinhala: weather, temperature, climate, humidity
                       "வானிலை", "வெப்பநிலை", "காலநிலை", "ஈரப்பதம்", "முன்னறிவிப்பு"],  # Tamil: weather, temperature, climate, humidity, forecast
    "flood":          ["ගංවතුර", "ගං වතුර", "ජල ගැලීම",
                       "வெள்ள",   # stem: வெள்ளம், வெள்ளப்பெருக்கு, வெள்ள அபாயம் (final "ம்" drops before a noun)
                       ],
    "drought":        ["නියඟ", "නියග", "නියං", "ජල හිඟ",
                       "வறட்சி", "தண்ணீர் பற்றாக்குறை"],
    "heat-wave":      ["අධික රස්නය", "රස්නය", "வெப்ப அலை", "கடும் வெப்பம்"],
    "cyclone":        ["සුළි සුළං", "සුළිසුළං", "සුළිසුළඟ", "சூறாவளி"],
    "landslide":      ["නායයෑම", "නායයාම", "නායයෑ", "நிலச்சரிவு", "மண்சரிவு"],
    "sea-level-rise": ["මුහුදු මට්ටම", "கடல் மட்டம்"],
    "rain":           ["වැස්ස", "වර්ෂා", "මෝසම්", "மழை", "பருவமழை"],
    "air-quality":    ["වායු දූෂණ", "වායු ගුණාත්මක", "காற்று மாசு", "காற்றின் தரம்"],
    "storm":          ["කුණාටු", "புயல்"],
    "agriculture":    ["කෘෂිකර්ම", "ගොවි", "விவசாய"],
}
for _topic, _kws in _MULTILINGUAL_TOPIC_KEYWORDS.items():
    if _topic in TOPIC_KEYWORDS:
        TOPIC_KEYWORDS[_topic].extend(_kws)

NON_CLIMATE_TERMS: list[str] = [
    "price of", "cost of", "how much does", "how much is",
    "train", "bus", "flight", "timetable", "schedule", "ticket",
    "president", "prime minister", "minister", "government",
    "election", "vote", "parliament", "political",
    "recipe", "cook",
    "cricket", "football", "sport", "match", "score",
    "exam", "admission",
    "salary", "job", "vacancy", "hire",
    "population", "history of", "capital of",
]
# NOTE: tourism words ("tourist", "hotel", "restaurant") and "school" /
# "university" are deliberately NOT blocklisted: tourists, schools and
# campuses are core audiences, and a climate term in the query (e.g.
# "weather risks for my tourism business") makes the question in-scope.


def contains_non_climate_term(text_lower: str) -> bool:
    """Word-boundary blocklist match.

    Plain substring matching caused false refusals ("bus" inside
    "business", "match" inside "mismatched"). Single-word terms match on
    word boundaries; multi-word phrases match as-is.
    """
    import re as _re

    for term in NON_CLIMATE_TERMS:
        if " " in term:
            if term in text_lower:
                return True
        elif _re.search(r"\b" + _re.escape(term) + r"\b", text_lower):
            return True
    return False


def keyword_hit(keyword: str, text_lower: str) -> bool:
    """Boundary-aware keyword match for topics and intents.

    Single ASCII words match on word boundaries so "hot" doesn't fire
    inside "hotels" and "rain" doesn't fire inside "train". Phrases and
    Sinhala/Tamil terms match as substrings (word boundaries are
    unreliable for those scripts).
    """
    import re as _re

    if keyword.isascii() and " " not in keyword:
        return _re.search(r"\b" + _re.escape(keyword) + r"\b", text_lower) is not None
    return keyword in text_lower

# Any of these words confirms a query is climate-related.
CLIMATE_TERMS: tuple[str, ...] = (
    "climate", "weather", "flood", "drought", "rain", "rainfall", "monsoon",
    "storm", "cyclone", "heat", "temperature", "humidity", "wind", "agriculture",
    "environment", "pollution", "landslide", "water", "irrigation", "sea level",
    "forecast", "disaster", "preparedness", "risk", "erosion", "wildfire",
    "air quality", "hazard",
)

# Query-expansion synonym map — deterministic term expansion for better recall.
EXPANSION_SYNONYMS: dict[str, list[str]] = {
    "flood":       ["flooding", "inundation", "river overflow", "flash flood"],
    "drought":     ["dry spell", "water scarcity", "rainfall deficit"],
    "heat-wave":   ["extreme heat", "heat stress", "high temperature"],
    "cyclone":     ["tropical storm", "storm surge", "high winds"],
    "landslide":   ["mudslide", "slope failure", "debris flow"],
    "rain":        ["rainfall", "precipitation", "monsoon"],
    "air-quality": ["pm2.5", "air pollution", "aqi"],
    "sea-level-rise": ["coastal flooding", "shoreline erosion", "storm surge"],
    "wildfire":    ["forest fire", "bushfire", "fire risk"],
    "erosion":     ["soil erosion", "sediment loss"],
    "agriculture": ["crops", "harvest", "farming", "irrigation"],
}

# Simple relative-date vocabulary for lightweight date extraction (no spaCy needed).
DATE_KEYWORDS: tuple[str, ...] = (
    "today", "tomorrow", "yesterday", "tonight", "this week", "next week",
    "this month", "next month", "this year", "next year", "this weekend",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    # Sinhala: now, today, tomorrow, yesterday
    "දැන්", "අද", "හෙට", "ඊයේ",
    # Tamil: now, today, tomorrow, yesterday
    "இப்போது", "இன்று", "நாளை", "நேற்று",
)


class NLPAgent(BaseAgentServer):
    """NLP Agent for intent detection, entity extraction, and query processing."""

    def __init__(self):
        super().__init__(
            name="nlp_agent",
            port=8101,
            description="Handles intent detection, entity extraction, query expansion and summarization",
        )

        # spaCy is optional. If present, it enriches entity extraction; if not,
        # rule-based extraction is used. Loaded lazily on first use.
        self._spacy_nlp = None
        self._spacy_loaded = False

        # Register tools
        self.register_tool(
            "process_query",
            self.process_query,
            "Full NLP processing: intent detection + entity extraction + query structuring",
        )
        self.register_tool(
            "extract_entities",
            self.extract_entities,
            "Extract named entities (location, date, topic, hazard) from text",
        )
        self.register_tool(
            "expand_query",
            self.expand_query,
            "Expand query with related terms for better retrieval",
        )
        self.register_tool(
            "summarize_text",
            self.summarize_text,
            "Summarize long text into concise snippets",
        )

    # =========================================================================
    # Optional spaCy loader
    # =========================================================================

    def _get_spacy(self):
        """
        Lazily load the spaCy English model. Returns the nlp object or None.
        Cached so the (expensive) load happens at most once per process.
        """
        if self._spacy_loaded:
            return self._spacy_nlp

        self._spacy_loaded = True
        try:
            import spacy
            self._spacy_nlp = spacy.load("en_core_web_sm")
            logger.info("NLP Agent: spaCy model 'en_core_web_sm' loaded for NER")
        except Exception as exc:  # ImportError or model-not-downloaded
            logger.info(
                "NLP Agent: spaCy unavailable (%s) — using rule-based entity extraction",
                exc,
            )
            self._spacy_nlp = None
        return self._spacy_nlp

    # =========================================================================
    # Tool: process_query
    # =========================================================================

    async def process_query(self, arguments: dict) -> dict:
        """
        Full NLP pipeline on user input.

        Input:
            - query (str): User's raw query text
            - location (str, optional): Provided location field
            - user_type (str, optional): Type of user

        Output:
            - intent (str)
            - entities (dict): {location, date, climate_topic, hazard_type}
            - structured_query (dict)
            - expanded_terms (list)
            - expanded_query (str)
        """
        query = (arguments.get("query") or "").strip()
        location_field = arguments.get("location")

        if not query:
            return {
                "intent": "general_climate_query",
                "entities": {},
                "structured_query": {"original_query": "", "processed": False},
                "expanded_terms": [],
                "expanded_query": "",
            }

        query_lower = query.lower()

        # 2. Entity extraction (rules + optional spaCy) runs FIRST so the
        #    off-topic guard below only fires when there is genuinely no
        #    climate signal (e.g. "my study schedule" blocks, but "study
        #    schedule during heavy rain" proceeds).
        entities = self._extract_entities_impl(query, location_field)

        # 3. Intent detection
        intent = self._classify_intent(query_lower)

        # 1. Off-topic guard — blocklisted terms (e.g. "Kandy train times")
        #    refuse only when the query carries no climate meaning.
        if contains_non_climate_term(query_lower) and not entities.get(
            "climate_topic"
        ):
            from app.agents.ir_agent.ir_agent import query_has_climate_term

            if not query_has_climate_term(query):
                return {
                    "intent": "non_climate",
                    "entities": {},
                    "structured_query": {"original_query": query, "processed": True},
                    "expanded_terms": [],
                    "expanded_query": query,
                }

        # 4. Query expansion (deterministic synonyms + optional LLM refinement)
        expansion = await self._expand_query_impl(query, entities)

        return {
            "intent": intent,
            "entities": entities,
            "structured_query": {"original_query": query, "processed": True},
            "expanded_terms": expansion["expanded_terms"],
            "expanded_query": expansion["expanded_query"],
        }

    # =========================================================================
    # Tool: extract_entities
    # =========================================================================

    async def extract_entities(self, arguments: dict) -> dict:
        """
        Extract named entities from text.

        Input:
            - text (str): Text to extract entities from
            - location (str, optional): Explicit location hint

        Output:
            - entities (dict): {location, date, climate_topic, hazard_type}
        """
        text = arguments.get("text") or arguments.get("query") or ""
        location_hint = arguments.get("location")
        entities = self._extract_entities_impl(text, location_hint)
        return {"entities": entities}

    def _extract_entities_impl(self, text: str, location_hint=None) -> dict:
        """
        Core entity extraction.

        Strategy:
        - Location: keyword gazetteer (query text preferred) + spaCy GPE/LOC.
        - Date: relative-date keywords + spaCy DATE labels.
        - Climate topic + hazard type: keyword matching against TOPIC_KEYWORDS.
        """
        text_lower = text.lower()

        # --- Location ---
        detected_location = None
        for keyword, canonical in SRI_LANKA_LOCATIONS:
            if keyword in text_lower:
                detected_location = canonical
                break
        if not detected_location:
            # Inflected Tamil forms (e.g. யாழ்ப்பாணத்தில் "in Jaffna")
            # drop the final "ம்", so fall back to stem matching.
            for stem, canonical in SRI_LANKA_LOCATION_STEMS:
                if stem in text_lower:
                    detected_location = canonical
                    break

        # --- Date (rule-based) ---
        dates: list[str] = [kw for kw in DATE_KEYWORDS if kw in text_lower]

        # --- spaCy enrichment (optional) ---
        nlp = self._get_spacy()
        if nlp is not None:
            try:
                doc = nlp(text)
                for ent in doc.ents:
                    if ent.label_ in ("GPE", "LOC") and not detected_location:
                        detected_location = ent.text
                    elif ent.label_ == "DATE" and ent.text.lower() not in dates:
                        dates.append(ent.text)
            except Exception as exc:
                logger.warning("NLP Agent: spaCy NER failed: %s", exc)

        # Fall back to the explicit location field last.
        if not detected_location and location_hint:
            detected_location = str(location_hint)

        # --- Climate topic + hazard type ---
        climate_topic = None
        hazard_type = None
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword_hit(kw, text_lower) for kw in keywords):
                climate_topic = topic
                hazard_type = topic
                break

        entities: dict = {}
        if detected_location:
            entities["location"] = detected_location
        if dates:
            # De-duplicate while preserving order
            entities["date"] = list(dict.fromkeys(dates))
        if climate_topic:
            entities["climate_topic"] = climate_topic
            entities["hazard_type"] = hazard_type

        return entities

    # =========================================================================
    # Tool: expand_query
    # =========================================================================

    async def expand_query(self, arguments: dict) -> dict:
        """
        Expand a query with related terms for better retrieval.

        Input:
            - query (str): Original query
            - entities (dict, optional): Pre-extracted entities

        Output:
            - expanded_terms (list)
            - expanded_query (str)
        """
        query = arguments.get("query", "")
        entities = arguments.get("entities")
        if entities is None:
            entities = self._extract_entities_impl(query, arguments.get("location"))
        return await self._expand_query_impl(query, entities)

    async def _expand_query_impl(self, query: str, entities: dict) -> dict:
        """
        Build expansion terms deterministically from the detected topic/location,
        then (best-effort) ask the LLM for a few more domain synonyms.
        """
        expanded_terms: list[str] = []

        # Deterministic synonyms from the detected climate topic
        topic = entities.get("climate_topic")
        if topic and topic in EXPANSION_SYNONYMS:
            expanded_terms.extend(EXPANSION_SYNONYMS[topic])

        # Include the location token so retrieval can match location-tagged docs
        location = entities.get("location")
        if location:
            expanded_terms.append(str(location))

        # Optional LLM refinement — never fatal if the LLM is unavailable
        try:
            from app.services.llm_service import llm_service

            if llm_service.is_available() and llm_service.get_provider() != "mock":
                prompt = (
                    "Give 3 to 5 short climate/weather search keywords related to this "
                    f'query, comma-separated, no explanation:\n"{query}"'
                )
                response = await llm_service.invoke_model(
                    prompt=prompt,
                    system_prompt="Return only a comma-separated list of short keywords.",
                    max_tokens=60,
                    temperature=0.2,
                )
                for term in response.split(","):
                    cleaned = term.strip().strip(".").lower()
                    if cleaned and len(cleaned) < 40 and cleaned not in expanded_terms:
                        expanded_terms.append(cleaned)
        except Exception as exc:
            logger.warning("NLP Agent: LLM query expansion skipped: %s", exc)

        # De-duplicate, drop terms already present verbatim in the query
        query_lower = query.lower()
        final_terms: list[str] = []
        for term in expanded_terms:
            if term.lower() not in query_lower and term not in final_terms:
                final_terms.append(term)

        expanded_query = query
        if final_terms:
            expanded_query = f"{query} {' '.join(final_terms)}"

        return {"expanded_terms": final_terms, "expanded_query": expanded_query}

    # =========================================================================
    # Tool: summarize_text
    # =========================================================================

    async def summarize_text(self, arguments: dict) -> dict:
        """
        Summarize long text into concise snippets.

        Input:
            - text (str): Long text to summarize
            - max_length (int, optional): Approximate max words in the summary

        Output:
            - summary (str)
        """
        text = (arguments.get("text") or "").strip()
        max_length = int(arguments.get("max_length", 60) or 60)

        if not text:
            return {"summary": ""}

        # Prefer LLM summarization when a real provider is configured.
        try:
            from app.services.llm_service import llm_service

            if llm_service.is_available() and llm_service.get_provider() != "mock":
                prompt = (
                    f"Summarize the following climate/weather text in at most "
                    f"{max_length} words. Preserve numbers, locations and dates.\n\n{text}"
                )
                summary = await llm_service.invoke_model(
                    prompt=prompt,
                    system_prompt="You are a precise climate information summarizer.",
                    max_tokens=max(120, max_length * 4),
                    temperature=0.2,
                )
                if summary and not summary.startswith("[MOCK RESPONSE"):
                    return {"summary": summary.strip()}
        except Exception as exc:
            logger.warning("NLP Agent: LLM summarization failed, using extractive fallback: %s", exc)

        # Extractive fallback: keep leading sentences up to the word budget.
        return {"summary": self._extractive_summary(text, max_length)}

    @staticmethod
    def _extractive_summary(text: str, max_words: int) -> str:
        """Simple extractive summary — first sentences up to the word budget."""
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        summary_words: list[str] = []
        for sentence in sentences:
            words = sentence.split()
            if not words:
                continue
            if len(summary_words) + len(words) > max_words and summary_words:
                break
            summary_words.extend(words)
        summary = " ".join(summary_words).strip()
        if not summary:
            summary = " ".join(text.split()[:max_words])
        return summary

    # =========================================================================
    # Intent classification helper
    # =========================================================================

    @staticmethod
    def _classify_intent(query_lower: str) -> str:
        """Keyword-based intent classification, evaluated in priority order."""
        for intent, keywords in INTENT_KEYWORDS:
            if any(keyword_hit(kw, query_lower) for kw in keywords):
                return intent
        return "general_climate_query"


# Entry point for running this agent standalone
if __name__ == "__main__":
    agent = NLPAgent()
    agent.run()
