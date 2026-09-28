"""
Localization service - Sinhala (si) and Tamil (ta) output for Climora AI.

Strategy (works even when no LLM is configured):
  1. A reviewed catalogue of every fixed string the agents can emit (recommendations,
     risk labels, disclaimers, guard messages) -> exact, instant, offline.
  2. Sentence templates for the rule-based risk explanation / detailed analysis and
     a data-based summary built from live readings (temperature, rain, AQI ...).
  3. Optional LLM translation for anything else (e.g. LLM-written recommendations).
  4. Otherwise the original English text is kept - a response is never dropped.

NOTE: all Sinhala/Tamil wording was drafted by an AI and should be reviewed by
native speakers before public release.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("en", "si", "ta")

# Recommendation library strings (generated; order matches recommendation_agent).
_REC_CATALOG: dict = {
    "Monitor official weather and disaster-management alerts for your area": (
        "ඔබේ ප්‍රදේශය සඳහා නිල කාලගුණ සහ ආපදා කළමනාකරණ අනතුරු ඇඟවීම් නිරීක්ෂණය කරන්න",
        "உங்கள் பகுதிக்கான அதிகாரப்பூர்வ வானிலை மற்றும் பேரிடர் மேலாண்மை எச்சரிக்கைகளைக் கண்காணியுங்கள்"),
    "Staying informed lets you act before conditions worsen.": (
        "දැනුවත්ව සිටීමෙන් තත්ත්වය නරක අතට හැරීමට පෙර ක්‍රියා කිරීමට හැකිය.",
        "தகவல் அறிந்திருப்பது நிலைமை மோசமடைவதற்கு முன் செயல்பட உதவும்."),
    "Prepare an emergency kit with water, food, first aid, and documents": (
        "ජලය, ආහාර, ප්‍රථමාධාර සහ ලේඛන සහිත හදිසි අවස්ථා කට්ටලයක් සූදානම් කරන්න",
        "தண்ணீர், உணவு, முதலுதவிப் பொருட்கள் மற்றும் ஆவணங்களுடன் அவசரகாலப் பெட்டியைத் தயார் செய்யுங்கள்"),
    "Being ready reduces harm if the situation escalates.": (
        "තත්ත්වය උග්‍ර වුවහොත් සූදානමින් සිටීම හානිය අඩු කරයි.",
        "நிலைமை தீவிரமடைந்தால், தயார்நிலை பாதிப்பைக் குறைக்கும்."),
    "Review evacuation routes and emergency contacts": (
        "ඉවත් වීමේ මාර්ග සහ හදිසි සම්බන්ධතා අංක පරීක්ෂා කරන්න",
        "வெளியேறும் வழிகளையும் அவசரத் தொடர்பு எண்களையும் சரிபார்த்துக் கொள்ளுங்கள்"),
    "Knowing where to go saves critical time in an emergency.": (
        "කොහාට යා යුතුදැයි දැන සිටීමෙන් හදිසි අවස්ථාවකදී වැදගත් කාලය ඉතිරි වේ.",
        "எங்கே செல்ல வேண்டும் என்பதை அறிந்திருப்பது அவசரத்தில் முக்கியமான நேரத்தைச் சேமிக்கும்."),
    "Stay informed about local climate conditions and forecasts": (
        "ප්‍රාදේශීය දේශගුණික තත්ත්වයන් සහ පුරෝකථන ගැන දැනුවත්ව සිටින්න",
        "உள்ளூர் காலநிலை நிலவரங்கள் மற்றும் முன்னறிவிப்புகள் குறித்துத் தெரிந்துகொள்ளுங்கள்"),
    "Awareness is the first step in preparedness.": (
        "දැනුවත්භාවය සූදානමේ පළමු පියවරයි.",
        "விழிப்புணர்வே முன்தயாரிப்பின் முதல் படி."),
    "Check and refresh your household emergency supplies": (
        "ඔබේ නිවසේ හදිසි සැපයුම් පරීක්ෂා කර අලුත් කරගන්න",
        "உங்கள் வீட்டு அவசரகாலப் பொருட்களைச் சரிபார்த்துப் புதுப்பியுங்கள்"),
    "Ready supplies help you cope with disruptions.": (
        "සූදානම් කර ඇති සැපයුම් බාධා වලට මුහුණ දීමට උපකාරී වේ.",
        "தயாராக உள்ள பொருட்கள் இடையூறுகளைச் சமாளிக்க உதவும்."),
    "Ongoing awareness supports good long-term decisions.": (
        "අඛණ්ඩ දැනුවත්භාවය හොඳ දිගුකාලීන තීරණ ගැනීමට සහාය වේ.",
        "தொடர்ந்த விழிப்புணர்வு நல்ல நீண்டகால முடிவுகளுக்கு உதவும்."),
    "Review your property and household resilience to climate events": (
        "දේශගුණික සිදුවීම් වලට ඔබේ දේපළ සහ නිවසේ ඔරොත්තු දීමේ හැකියාව සමාලෝචනය කරන්න",
        "காலநிலை நிகழ்வுகளை எதிர்கொள்ளும் உங்கள் சொத்து மற்றும் வீட்டின் தாங்குதிறனை மதிப்பாய்வு செய்யுங்கள்"),
    "Proactive measures reduce future vulnerability.": (
        "පූර්වගාමී පියවර අනාගත අවදානම අඩු කරයි.",
        "முன்கூட்டிய நடவடிக்கைகள் எதிர்கால பாதிப்பைக் குறைக்கும்."),
    "Connect with local disaster-management resources": (
        "ප්‍රාදේශීය ආපදා කළමනාකරණ සම්පත් සමඟ සම්බන්ධ වන්න",
        "உள்ளூர் பேரிடர் மேலாண்மை வளங்களுடன் தொடர்பில் இருங்கள்"),
    "Knowing local resources helps in future events.": (
        "ප්‍රාදේශීය සම්පත් ගැන දැන සිටීම අනාගත සිදුවීම් වලදී උපකාරී වේ.",
        "உள்ளூர் வளங்களை அறிந்திருப்பது எதிர்கால நிகழ்வுகளில் உதவும்."),
    "Move valuables and important documents to higher ground": (
        "වටිනා භාණ්ඩ සහ වැදගත් ලේඛන උසස් ස්ථානයකට ගෙන යන්න",
        "மதிப்புமிக்க பொருட்களையும் முக்கிய ஆவணங்களையும் உயரமான இடத்திற்கு மாற்றுங்கள்"),
    "Flood water can rise quickly and damage belongings.": (
        "ගංවතුර ඉක්මනින් ඉහළ නැගී දේපළ වලට හානි කළ හැක.",
        "வெள்ளநீர் விரைவாக உயர்ந்து உடைமைகளைச் சேதப்படுத்தக்கூடும்."),
    "Avoid crossing flooded roads or fast-moving water on foot or by vehicle": (
        "ගංවතුරෙන් යටවූ මාර්ග හෝ වේගයෙන් ගලා යන ජලය පයින් හෝ වාහනයෙන් තරණය කිරීමෙන් වළකින්න",
        "வெள்ளத்தில் மூழ்கிய சாலைகளையோ வேகமாக ஓடும் நீரையோ நடந்தோ வாகனத்திலோ கடக்க வேண்டாம்"),
    "Most flood deaths happen when people enter moving water.": (
        "ගංවතුර මරණ බොහොමයක් සිදුවන්නේ මිනිසුන් ගලා යන ජලයට ඇතුළු වන විටය.",
        "பெரும்பாலான வெள்ள உயிரிழப்புகள் மக்கள் ஓடும் நீரில் இறங்கும்போதே நிகழ்கின்றன."),
    "Prepare a grab bag with water, medicine, and documents in a waterproof pouch": (
        "ජලය, ඖෂධ සහ ලේඛන ජල-ආරක්ෂිත මල්ලක දමා හදිසි මල්ලක් සූදානම් කරන්න",
        "தண்ணீர், மருந்துகள், ஆவணங்களை நீர்புகாப் பையில் வைத்து அவசரப் பையைத் தயார் செய்யுங்கள்"),
    "Being ready to leave quickly reduces risk if water rises.": (
        "ජලය ඉහළ ගියහොත් ඉක්මනින් පිටත්ව යාමට සූදානමින් සිටීම අවදානම අඩු කරයි.",
        "நீர் மட்டம் உயர்ந்தால் விரைவாக வெளியேறத் தயாராக இருப்பது ஆபத்தைக் குறைக்கும்."),
    "Clear drains and gutters around your property before heavy rain": (
        "අධික වර්ෂාවට පෙර ඔබේ දේපළ අවට කාණු සහ ජලනල පිරිසිදු කරන්න",
        "கனமழைக்கு முன் உங்கள் சொத்தைச் சுற்றியுள்ள வடிகால்களையும் நீர்க்குழாய்களையும் சுத்தம் செய்யுங்கள்"),
    "Good drainage lowers the chance of local flooding.": (
        "හොඳ ජල බැස යාමක් ප්‍රාදේශීය ගංවතුර අවදානම අඩු කරයි.",
        "நல்ல வடிகால் அமைப்பு உள்ளூர் வெள்ளத்தின் வாய்ப்பைக் குறைக்கும்."),
    "Store and conserve drinking water now": (
        "පානීය ජලය දැන්ම ගබඩා කර ඉතිරි කරගන්න",
        "குடிநீரை இப்போதே சேமித்து சிக்கனமாகப் பயன்படுத்துங்கள்"),
    "Water supplies can become scarce during prolonged dry spells.": (
        "දිගු වියළි කාලවලදී ජල සැපයුම් හිඟ විය හැක.",
        "நீண்ட வறண்ட காலங்களில் நீர் விநியோகம் பற்றாக்குறையாகலாம்."),
    "Prioritize water for essential needs and reduce non-essential use": (
        "අත්‍යවශ්‍ය අවශ්‍යතා සඳහා ජලයට මුල් තැන දී අනවශ්‍ය භාවිතය අඩු කරන්න",
        "அத்தியாவசியத் தேவைகளுக்கு நீருக்கு முன்னுரிமை கொடுத்து, அத்தியாவசியமற்ற பயன்பாட்டைக் குறையுங்கள்"),
    "Rationing early makes limited water last longer.": (
        "කලින් සීමා කිරීමෙන් සීමිත ජලය වැඩි කාලයක් පවතී.",
        "முன்கூட்டியே கட்டுப்படுத்துவது குறைந்த நீரை நீண்ட நாட்களுக்கு நீடிக்கச் செய்யும்."),
    "Consider drought-tolerant crops and efficient irrigation": (
        "නියඟයට ඔරොත්තු දෙන බෝග සහ කාර්යක්ෂම වාරිමාර්ග ක්‍රම සලකා බලන්න",
        "வறட்சியைத் தாங்கும் பயிர்களையும் திறமையான நீர்ப்பாசனத்தையும் பரிசீலியுங்கள்"),
    "Reduces vulnerability to future dry seasons.": (
        "අනාගත වියළි කාලවලට ඇති අවදානම අඩු කරයි.",
        "எதிர்கால வறண்ட பருவங்களால் ஏற்படும் பாதிப்பைக் குறைக்கும்."),
    "Stay hydrated and avoid outdoor activity during peak afternoon heat": (
        "ජලය බොමින් සිටින්න; දහවල් උපරිම රස්නය ඇති වේලාවේ එළිමහන් ක්‍රියාකාරකම් වලින් වළකින්න",
        "போதுமான தண்ணீர் அருந்தி, உச்ச வெப்பமுள்ள பிற்பகல் நேரத்தில் வெளிப்புறச் செயல்பாடுகளைத் தவிர்க்கவும்"),
    "Heat stress and heatstroke rise sharply in extreme heat.": (
        "අධික රස්නයේදී තාප ආතතිය සහ තාප ආඝාතය තියුණු ලෙස වැඩි වේ.",
        "கடும் வெப்பத்தில் வெப்ப அழுத்தமும் வெப்பத் தாக்கமும் கடுமையாக அதிகரிக்கும்."),
    "Check on elderly, children, and outdoor workers": (
        "වයස්ගත අය, ළමයින් සහ එළිමහනේ වැඩ කරන්නන් ගැන සොයා බලන්න",
        "முதியவர்கள், குழந்தைகள் மற்றும் வெளியில் வேலை செய்பவர்களைக் கவனித்துக் கொள்ளுங்கள்"),
    "Vulnerable people are most at risk during heat waves.": (
        "උණුසුම් කාලවලදී අවදානමට වැඩියෙන්ම ලක්වන්නේ අවදානම් තත්ත්වයේ සිටින අයයි.",
        "வெப்ப அலைகளின்போது பாதிக்கப்படக்கூடிய மக்களுக்கே ஆபத்து அதிகம்."),
    "Keep living spaces cool and ventilated": (
        "නිවාස පරිශ්‍ර සිසිල්ව සහ වාතාශ්‍රයෙන් යුතුව තබාගන්න",
        "வசிக்கும் இடங்களைக் குளிர்ச்சியாகவும் காற்றோட்டமாகவும் வைத்திருங்கள்"),
    "A cooler indoor environment reduces heat-related illness.": (
        "සිසිල් ගෘහස්ථ පරිසරයක් රස්නය නිසා ඇතිවන රෝග අඩු කරයි.",
        "குளிர்ச்சியான உட்புறச் சூழல் வெப்பம் தொடர்பான நோய்களைக் குறைக்கும்."),
    "Secure loose outdoor objects and reinforce doors and windows": (
        "එළිමහනේ ඇති ලිහිල් භාණ්ඩ ආරක්ෂිත කර දොරවල් සහ ජනෙල් ශක්තිමත් කරන්න",
        "வெளியிலுள்ள தளர்வான பொருட்களைப் பாதுகாத்து, கதவுகளையும் ஜன்னல்களையும் உறுதிப்படுத்துங்கள்"),
    "High winds turn loose items into dangerous projectiles.": (
        "අධික සුළං නිසා ලිහිල් භාණ්ඩ අනතුරුදායක ලෙස ඈතට විසි වේ.",
        "பலத்த காற்று தளர்வான பொருட்களை ஆபத்தான முறையில் தூக்கி வீசும்."),
    "Follow official evacuation orders without delay": (
        "නිල ඉවත් වීමේ නියෝග ප්‍රමාද නොකර පිළිපදින්න",
        "அதிகாரப்பூர்வ வெளியேற்ற உத்தரவுகளை தாமதமின்றி பின்பற்றுங்கள்"),
    "Timely evacuation is the most effective way to stay safe.": (
        "නියමිත වේලාවට ඉවත් වීම ආරක්ෂිතව සිටීමේ වඩාත්ම ඵලදායී ක්‍රමයයි.",
        "சரியான நேரத்தில் வெளியேறுவதே பாதுகாப்பாக இருக்க மிகச் சிறந்த வழி."),
    "Stock emergency supplies for at least three days": (
        "අවම වශයෙන් දින තුනකට හදිසි සැපයුම් ගබඩා කරගන්න",
        "குறைந்தது மூன்று நாட்களுக்கான அவசரகாலப் பொருட்களை இருப்பு வையுங்கள்"),
    "Storms can cut power and access to shops for days.": (
        "කුණාටු නිසා දින ගණනාවක් විදුලිය සහ සාප්පු වෙත ප්‍රවේශය බාධා විය හැක.",
        "புயல்கள் பல நாட்களுக்கு மின்சாரத்தையும் கடைகளுக்கான அணுகலையும் துண்டிக்கக்கூடும்."),
    "Move away from steep slopes and identified landslide-prone areas": (
        "බෑවුම් සහිත ප්‍රදේශ සහ නායයාමට ලක්විය හැකි බව හඳුනාගත් ප්‍රදේශ වලින් ඉවත් වන්න",
        "செங்குத்தான சரிவுகளிலிருந்தும் நிலச்சரிவு அபாயம் உள்ளதாக அடையாளம் காணப்பட்ட பகுதிகளிலிருந்தும் விலகிச் செல்லுங்கள்"),
    "Landslides can occur suddenly during and after heavy rain.": (
        "අධික වර්ෂාව අතරතුර සහ පසුව නායයෑම් හදිසියේ සිදුවිය හැක.",
        "கனமழையின்போதும் அதன் பின்னரும் நிலச்சரிவுகள் திடீரென ஏற்படலாம்."),
    "Watch for warning signs: cracks, tilting trees, sudden water changes": (
        "අනතුරු ඇඟවීමේ සලකුණු ගැන අවධානයෙන් සිටින්න: ඉරිතැලීම්, ඇල වන ගස්, ජලයේ හදිසි වෙනස්කම්",
        "எச்சரிக்கை அறிகுறிகளைக் கவனியுங்கள்: விரிசல்கள், சாயும் மரங்கள், நீரில் திடீர் மாற்றங்கள்"),
    "Early signs give a short window to move to safety.": (
        "මුල් සලකුණු ආරක්ෂිත ස්ථානයකට යාමට කෙටි කාලයක් ලබා දේ.",
        "ஆரம்ப அறிகுறிகள் பாதுகாப்பான இடத்திற்குச் செல்ல குறுகிய அவகாசத்தை அளிக்கின்றன."),
    "Avoid building or planting on unstable slopes": (
        "අස්ථාවර බෑවුම් මත ගොඩනැගීම් හෝ වගා කිරීමෙන් වළකින්න",
        "நிலையற்ற சரிவுகளில் கட்டுமானம் அல்லது நடவு செய்வதைத் தவிர்க்கவும்"),
    "Reduces long-term exposure to slope failure.": (
        "බෑවුම් කඩා වැටීමට ඇති දිගුකාලීන අවදානම අඩු කරයි.",
        "சரிவு சீர்குலைவால் ஏற்படும் நீண்டகால ஆபத்தைக் குறைக்கும்."),
    "Stay indoors and avoid unnecessary travel during heavy rain": (
        "අධික වර්ෂාව තුළ ගෘහස්ථව සිට අනවශ්‍ය ගමන් වළකින්න",
        "கனமழையின்போது வீட்டிற்குள்ளேயே இருந்து தேவையற்ற பயணங்களைத் தவிர்க்கவும்"),
    "Reduced visibility and water on roads increase accident risk.": (
        "දැක්ම අඩුවීම සහ මාර්ග මත ජලය නිසා අනතුරු අවදානම වැඩි වේ.",
        "பார்வைத் தெளிவு குறைவதும் சாலைகளில் நீர் தேங்குவதும் விபத்து அபாயத்தை அதிகரிக்கும்."),
    "Monitor local weather updates and flood advisories": (
        "ප්‍රාදේශීය කාලගුණ යාවත්කාලීන සහ ගංවතුර උපදෙස් නිරීක්ෂණය කරන්න",
        "உள்ளூர் வானிலை அறிவிப்புகளையும் வெள்ள எச்சரிக்கைகளையும் கண்காணியுங்கள்"),
    "Heavy rain can quickly lead to flooding or landslides.": (
        "අධික වර්ෂාව ඉක්මනින් ගංවතුර හෝ නායයෑම් වලට හේතු විය හැක.",
        "கனமழை விரைவாக வெள்ளத்தையோ நிலச்சரிவையோ ஏற்படுத்தக்கூடும்."),
    "Stay away from the shoreline during high waves or surge warnings": (
        "අධික රළ හෝ මුහුදු රළ පිම්බීමේ අනතුරු ඇඟවීම් ඇති විට වෙරළ තීරයෙන් ඈතින් සිටින්න",
        "உயர் அலைகள் அல்லது கடல் எழுச்சி எச்சரிக்கைகளின்போது கடற்கரையிலிருந்து விலகியிருங்கள்"),
    "Storm surge and high waves are dangerous near the coast.": (
        "කුණාටු රළ සහ අධික රළ වෙරළ ආසන්නයේ අනතුරුදායකය.",
        "புயல் எழுச்சியும் உயர் அலைகளும் கடற்கரைக்கு அருகில் ஆபத்தானவை."),
    "Plan for coastal flooding if you live in a low-lying area": (
        "පහත් බිම් ප්‍රදේශයක ජීවත් වන්නේ නම් වෙරළබඩ ගංවතුර සඳහා සැලසුම් කරන්න",
        "தாழ்வான பகுதியில் வசித்தால் கடலோர வெள்ளத்திற்குத் திட்டமிடுங்கள்"),
    "Low-lying coastal zones flood first during surges.": (
        "රළ පිම්බෙන විට පහත් වෙරළබඩ කලාප මුලින්ම ගංවතුරට ලක්වේ.",
        "கடல் எழுச்சியின்போது தாழ்வான கடலோரப் பகுதிகளே முதலில் வெள்ளத்தில் மூழ்கும்."),
    "Limit outdoor exposure and wear a mask if air quality is poor": (
        "වායු ගුණාත්මකභාවය දුර්වල නම් එළිමහනේ රැඳී සිටීම සීමා කර මුඛ ආවරණයක් පළඳින්න",
        "காற்றின் தரம் மோசமாக இருந்தால் வெளியே செல்வதைக் குறைத்து முகக்கவசம் அணியுங்கள்"),
    "Fine particulates affect the lungs and heart.": (
        "සියුම් අංශු පෙනහළු සහ හදවතට බලපායි.",
        "நுண்துகள்கள் நுரையீரலையும் இதயத்தையும் பாதிக்கும்."),
    "Keep windows closed and use air filtration if available": (
        "ජනෙල් වසා තබා, හැකි නම් වායු පෙරහන් භාවිතා කරන්න",
        "ஜன்னல்களை மூடி வைத்து, இருந்தால் காற்று வடிகட்டியைப் பயன்படுத்துங்கள்"),
    "Reduces indoor exposure to polluted air.": (
        "දූෂිත වාතයට ගෘහස්ථව නිරාවරණය වීම අඩු කරයි.",
        "மாசடைந்த காற்றுக்கு உட்புறத்தில் ஆளாவதைக் குறைக்கும்."),
    "Be ready to evacuate and keep an escape route clear": (
        "ඉවත් වීමට සූදානමින් සිට ගැලවීමේ මාර්ගයක් පැහැදිලිව තබාගන්න",
        "வெளியேறத் தயாராக இருந்து தப்பிக்கும் வழியைத் தடையின்றி வைத்திருங்கள்"),
    "Wildfires can spread rapidly and change direction.": (
        "වනගිනි වේගයෙන් පැතිරී දිශාව වෙනස් කළ හැක.",
        "காட்டுத்தீ வேகமாகப் பரவி திசையையும் மாற்றக்கூடும்."),
    "Create defensible space by clearing dry vegetation near buildings": (
        "ගොඩනැගිලි අසල වියළි වෘක්ෂලතා ඉවත් කර ආරක්ෂිත අවකාශයක් සාදන්න",
        "கட்டிடங்களுக்கு அருகிலுள்ள உலர்ந்த தாவரங்களை அகற்றிப் பாதுகாப்பு இடைவெளியை உருவாக்குங்கள்"),
    "Reduces the chance of fire reaching structures.": (
        "ගින්න ගොඩනැගිලි වලට ළඟා වීමේ හැකියාව අඩු කරයි.",
        "தீ கட்டமைப்புகளை அடையும் வாய்ப்பைக் குறைக்கும்."),
    "Avoid disturbing vulnerable soil during heavy rain": (
        "අධික වර්ෂාව තුළ අවදානම් පස කැලඹීමෙන් වළකින්න",
        "கனமழையின்போது பாதிக்கப்படக்கூடிய மண்ணைக் கிளறுவதைத் தவிர்க்கவும்"),
    "Exposed soil erodes faster and can destabilize land.": (
        "නිරාවරණය වූ පස වේගයෙන් ඛාදනය වී ඉඩම අස්ථාවර කළ හැක.",
        "திறந்த மண் வேகமாக அரிக்கப்பட்டு நிலத்தை நிலைகுலையச் செய்யலாம்."),
    "Plant ground cover or build terraces on sloped land": (
        "බෑවුම් සහිත ඉඩම්වල බිම් ආවරණ ශාක සිටුවන්න හෝ පඩි ඉදිකරන්න",
        "சரிவான நிலத்தில் தரைமூடி தாவரங்களை நடவும் அல்லது படிக்கட்டு அமைப்புகளை உருவாக்கவும்"),
    "Vegetation and terracing hold soil in place.": (
        "ශාක සහ පඩි ක්‍රමය පස රඳවා තබයි.",
        "தாவரங்களும் படிக்கட்டு அமைப்புகளும் மண்ணைப் பிடித்து வைக்கும்."),
    "Protect or harvest vulnerable crops ahead of the expected event": (
        "අපේක්ෂිත සිදුවීමට පෙර අවදානම් බෝග ආරක්ෂා කරන්න හෝ අස්වනු නෙළන්න",
        "எதிர்பார்க்கப்படும் நிகழ்வுக்கு முன் பாதிக்கப்படக்கூடிய பயிர்களைப் பாதுகாக்கவும் அல்லது அறுவடை செய்யவும்"),
    "Timely action can save part of the yield.": (
        "නියමිත වේලාවට ක්‍රියා කිරීමෙන් අස්වැන්නෙන් කොටසක් බේරා ගත හැක.",
        "சரியான நேரத்தில் செயல்பட்டால் விளைச்சலின் ஒரு பகுதியைக் காப்பாற்றலாம்."),
    "Adjust planting and irrigation schedules to the forecast": (
        "පුරෝකථනයට අනුව වගා කිරීම් සහ වාරිමාර්ග කාලසටහන් සකස් කරන්න",
        "முன்னறிவிப்புக்கு ஏற்ப நடவு மற்றும் நீர்ப்பாசன அட்டவணைகளை மாற்றியமையுங்கள்"),
    "Aligning with conditions reduces crop loss.": (
        "තත්ත්වයන්ට අනුගත වීමෙන් බෝග හානිය අඩු වේ.",
        "நிலவரத்துக்கு ஏற்ப மாற்றிக்கொள்வது பயிர் இழப்பைக் குறைக்கும்."),
    "Diversify crops and improve soil health for resilience": (
        "ඔරොත්තු දීමේ හැකියාව සඳහා බෝග විවිධාංගීකරණය කර පසේ සෞඛ්‍යය වැඩිදියුණු කරන්න",
        "தாங்குதிறனுக்காகப் பயிர்களை பல்வகைப்படுத்தி மண் வளத்தை மேம்படுத்துங்கள்"),
    "Diverse, healthy systems withstand climate stress better.": (
        "විවිධ, සෞඛ්‍ය සම්පන්න ක්‍රම දේශගුණික පීඩනයට වඩා හොඳින් ඔරොත්තු දේ.",
        "பல்வகை, ஆரோக்கியமான அமைப்புகள் காலநிலை அழுத்தத்தை சிறப்பாகத் தாங்கும்."),
}


# ---------------------------------------------------------------------------
# Small vocabularies
# ---------------------------------------------------------------------------
_SCRIPT_RANGES = {"si": ("\u0D80", "\u0DFF"), "ta": ("\u0B80", "\u0BFF")}

# Risk level as a full phrase ("moderate risk") so sentences need no inflection.
LEVEL_PHRASE = {
    "en": {"low": "low risk", "moderate": "moderate risk", "high": "high risk",
           "critical": "critical risk", "unknown": "unknown risk"},
    "si": {"low": "අඩු අවදානම", "moderate": "මධ්‍යම අවදානම", "high": "ඉහළ අවදානම",
           "critical": "බරපතල අවදානම", "unknown": "නොදන්නා අවදානම"},
    "ta": {"low": "குறைந்த ஆபத்து", "moderate": "மிதமான ஆபத்து", "high": "அதிக ஆபத்து",
           "critical": "தீவிர ஆபத்து", "unknown": "அறியப்படாத ஆபத்து"},
}

FACTOR = {
    "flooding": ("ගංවතුර", "வெள்ளம்"),
    "drought": ("නියඟය", "வறட்சி"),
    "extreme heat": ("අධික උෂ්ණත්වය", "கடும் வெப்பம்"),
    "cyclone / storm": ("සුළි සුළං / කුණාටු", "சூறாவளி / புயல்"),
    "landslide": ("නායයෑම්", "நிலச்சரிவு"),
    "heavy rainfall": ("අධික වර්ෂාපතනය", "கனமழை"),
    "coastal / sea-level risk": ("වෙරළබඩ / මුහුදු මට්ටමේ අවදානම", "கடலோர / கடல் மட்ட ஆபத்து"),
    "poor air quality": ("දුර්වල වායු ගුණාත්මකභාවය", "மோசமான காற்றின் தரம்"),
    "wildfire": ("වනගිනි", "காட்டுத்தீ"),
    "soil erosion": ("පස ඛාදනය", "மண் அரிப்பு"),
    "crop / agricultural risk": ("බෝග / කෘෂිකාර්මික අවදානම", "பயிர் / விவசாய ஆபத்து"),
}

PLACE = {   # canonical English -> (Sinhala, Tamil)
    "Colombo": ("කොළඹ", "கொழும்பு"), "Gampaha": ("ගම්පහ", "கம்பஹா"),
    "Kalutara": ("කළුතර", "களுத்துறை"), "Kandy": ("මහනුවර", "கண்டி"),
    "Matale": ("මාතලේ", "மாத்தளை"), "Nuwara Eliya": ("නුවරඑළිය", "நுவரெலியா"),
    "Galle": ("ගාල්ල", "காலி"), "Matara": ("මාතර", "மாத்தறை"),
    "Hambantota": ("හම්බන්තොට", "அம்பாந்தோட்டை"), "Jaffna": ("යාපනය", "யாழ்ப்பாணம்"),
    "Kilinochchi": ("කිලිනොච්චි", "கிளிநொச்சி"), "Mannar": ("මන්නාරම", "மன்னார்"),
    "Vavuniya": ("වව්නියාව", "வவுனியா"), "Mullaitivu": ("මුලතිව්", "முல்லைத்தீவு"),
    "Batticaloa": ("මඩකලපුව", "மட்டக்களப்பு"), "Ampara": ("අම්පාර", "அம்பாறை"),
    "Trincomalee": ("ත්‍රිකුණාමලය", "திருகோணமலை"), "Kurunegala": ("කුරුණෑගල", "குருநாகல்"),
    "Puttalam": ("පුත්තලම", "புத்தளம்"), "Anuradhapura": ("අනුරාධපුරය", "அனுராதபுரம்"),
    "Polonnaruwa": ("පොළොන්නරුව", "பொலன்னறுவை"), "Badulla": ("බදුල්ල", "பதுளை"),
    "Monaragala": ("මොණරාගල", "மொனராகலை"), "Ratnapura": ("රත්නපුර", "இரத்தினபுரி"),
    "Kegalle": ("කෑගල්ල", "கேகாலை"),
    "Western Province": ("බස්නාහිර පළාත", "மேல் மாகாணம்"),
    "Central Province": ("මධ්‍යම පළාත", "மத்திய மாகாணம்"),
    "Southern Province": ("දකුණු පළාත", "தெற்கு மாகாணம்"),
    "Northern Province": ("උතුරු පළාත", "வடக்கு மாகாணம்"),
    "Eastern Province": ("නැගෙනහිර පළාත", "கிழக்கு மாகாணம்"),
    "North Western Province": ("වයඹ පළාත", "வடமேல் மாகாணம்"),
    "North Central Province": ("උතුරු මැද පළාත", "வட மத்திய மாகாணம்"),
    "Uva Province": ("ඌව පළාත", "ஊவா மாகாணம்"),
    "Sabaragamuwa Province": ("සබරගමුව පළාත", "சப்ரகமுவ மாகாணம்"),
    "Dry Zone": ("වියළි කලාපය", "வறண்ட வலயம்"),
    "Central Highlands": ("මධ්‍යම කඳුකරය", "மத்திய மலைநாடு"),
    "Sri Lanka": ("ශ්‍රී ලංකාව", "இலங்கை"),
}

USER_TYPE = {   # type -> (si, ta) label,  (si, ta) focus areas
    "individual": (("පුද්ගලයෙකු", "தனிநபர்"),
                   ("පුද්ගලික ආරක්ෂාව, නිවාස ආරක්ෂාව, හදිසි කට්ටල සහ ඉවත් වීමේ සැලසුම්",
                    "தனிப்பட்ட பாதுகாப்பு, வீட்டுப் பாதுகாப்பு, அவசரகாலப் பெட்டிகள், வெளியேற்றத் திட்டங்கள்")),
    "student": (("සිසුවෙකු", "மாணவர்"),
                ("අවදානම තේරුම් ගැනීම, පුද්ගලික සහ පාසල් ආරක්ෂාව, ප්‍රජා දැනුවත්භාවය",
                 "ஆபத்தைப் புரிந்துகொள்ளுதல், தனிப்பட்ட மற்றும் பள்ளிப் பாதுகாப்பு, சமூக விழிப்புணர்வு")),
    "farmer": (("ගොවියෙකු", "விவசாயி"),
               ("බෝග ආරක්ෂාව, වාරිමාර්ග කාලසටහන, පශු සම්පත් ආරක්ෂාව, අස්වනු තීරණ",
                "பயிர்ப் பாதுகாப்பு, நீர்ப்பாசன நேரம், கால்நடைப் பாதுகாப்பு, அறுவடை முடிவுகள்")),
    "business": (("ව්‍යාපාරයක්", "வணிக நிறுவனம்"),
                 ("මෙහෙයුම් අඛණ්ඩතාව, සැපයුම් දාමය, සේවක ආරක්ෂාව, වත්කම් ආරක්ෂාව",
                  "செயல்பாட்டுத் தொடர்ச்சி, விநியோகச் சங்கிலி, ஊழியர் பாதுகாப்பு, சொத்துப் பாதுகாப்பு")),
    "organization": (("සංවිධානයක්", "அமைப்பு"),
                     ("යටිතල පහසුකම්, ප්‍රජා සැලසුම්කරණය, සම්පත් වෙන් කිරීම, ප්‍රතිපත්ති ප්‍රතිචාර",
                      "உள்கட்டமைப்பு, சமூகத் திட்டமிடல், வளப் பகிர்வு, கொள்கை நடவடிக்கை")),
    "institution": (("ආයතනයක්", "நிறுவனம்"),
                    ("යටිතල පහසුකම්, අඛණ්ඩතා සැලසුම්කරණය, පදිංචිකරුවන්ගේ ආරක්ෂාව, බලධාරීන් සමඟ සම්බන්ධීකරණය",
                     "உள்கட்டமைப்பு, தொடர்ச்சித் திட்டமிடல், வசிப்பவர் பாதுகாப்பு, அதிகாரிகளுடன் ஒருங்கிணைப்பு")),
}

# OpenWeatherMap "description" values.
CONDITION = {
    "clear sky": ("පැහැදිලි අහස", "தெளிவான வானம்"),
    "few clouds": ("සුළු වලාකුළු", "சில மேகங்கள்"),
    "scattered clouds": ("විසිරුණු වලාකුළු", "சிதறிய மேகங்கள்"),
    "broken clouds": ("කඩින් කඩ වලාකුළු", "இடையிடையே மேகங்கள்"),
    "overcast clouds": ("වලාකුළු වැසුණු අහස", "மேகமூட்டம்"),
    "light rain": ("සැහැල්ලු වැස්ස", "லேசான மழை"),
    "moderate rain": ("මධ්‍යම වැස්ස", "மிதமான மழை"),
    "heavy intensity rain": ("තද වැස්ස", "கனமழை"),
    "very heavy rain": ("ඉතා තද වැස්ස", "மிகக் கனமழை"),
    "shower rain": ("වැසි වැටීම්", "சாரல் மழை"),
    "light intensity shower rain": ("සැහැල්ලු වැසි වැටීම්", "லேசான சாரல் மழை"),
    "thunderstorm": ("ගිගුරුම් සහිත කුණාටුව", "இடியுடன் கூடிய புயல்"),
    "thunderstorm with rain": ("වැස්ස සහිත ගිගුරුම්", "இடியுடன் கூடிய மழை"),
    "thunderstorm with light rain": ("සැහැල්ලු වැස්ස සහිත ගිගුරුම්", "லேசான மழையுடன் இடி"),
    "drizzle": ("සිහින් වැහි බිංදු", "தூறல்"),
    "light intensity drizzle": ("සැහැල්ලු සිහින් වැස්ස", "லேசான தூறல்"),
    "mist": ("මීදුම", "மூடுபனி"),
    "haze": ("දූවිලි මීදුම", "புகைமூட்டம்"),
    "fog": ("ඝන මීදුම", "பனிமூட்டம்"),
    "smoke": ("දුම", "புகை"),
}

AQI_CATEGORY = [   # (max AQI, en, si, ta)
    (50, "good", "හොඳයි", "நல்லது"),
    (100, "moderate", "මධ්‍යමයි", "மிதமானது"),
    (150, "unhealthy for sensitive groups", "සංවේදී පුද්ගලයන්ට අහිතකරයි", "உணர்திறன் உள்ளவர்களுக்கு ஆரோக்கியமற்றது"),
    (200, "unhealthy", "අහිතකරයි", "ஆரோக்கியமற்றது"),
    (300, "very unhealthy", "ඉතා අහිතකරයි", "மிகவும் ஆரோக்கியமற்றது"),
    (10**9, "hazardous", "අනතුරුදායකයි", "ஆபத்தானது"),
]

# Fixed messages (exact English -> (si, ta)).
_STATIC = {
    "This information is for awareness purposes. For emergency situations, contact local authorities.": (
        "මෙම තොරතුරු දැනුවත් කිරීමේ අරමුණු සඳහා පමණි. හදිසි අවස්ථාවලදී ප්‍රාදේශීය බලධාරීන් අමතන්න.",
        "இந்தத் தகவல் விழிப்புணர்வுக்காக மட்டுமே. அவசர சூழ்நிலைகளில் உள்ளூர் அதிகாரிகளைத் தொடர்பு கொள்ளுங்கள்."),
    "I can only answer climate and environmental questions for locations in Sri Lanka. Please ask about weather, hazards, climate risks, flood, drought, or preparedness for a Sri Lankan location.": (
        "මට පිළිතුරු දිය හැක්කේ ශ්‍රී ලංකාවේ ස්ථාන සඳහා දේශගුණ සහ පරිසර ප්‍රශ්නවලට පමණි. කරුණාකර ශ්‍රී ලංකාවේ ස්ථානයක කාලගුණය, උපද්‍රව, දේශගුණ අවදානම්, ගංවතුර, නියඟය හෝ සූදානම ගැන අසන්න.",
        "இலங்கையிலுள்ள இடங்களுக்கான காலநிலை மற்றும் சுற்றுச்சூழல் கேள்விகளுக்கு மட்டுமே என்னால் பதிலளிக்க முடியும். இலங்கையிலுள்ள ஓர் இடத்தின் வானிலை, அபாயங்கள், காலநிலை ஆபத்துகள், வெள்ளம், வறட்சி அல்லது முன்தயாரிப்பு பற்றிக் கேளுங்கள்."),
    "Please specify a location in Sri Lanka for your query. For example: 'What is the weather in Colombo?', 'Is there a flood risk in Kandy?', or 'What is the drought situation in Jaffna?'": (
        "කරුණාකර ඔබේ ප්‍රශ්නය සඳහා ශ්‍රී ලංකාවේ ස්ථානයක් සඳහන් කරන්න. උදාහරණ: 'කොළඹ කාලගුණය කුමක්ද?', 'මහනුවර ගංවතුර අවදානමක් තිබේද?', හෝ 'යාපනයේ නියඟ තත්ත්වය කුමක්ද?'",
        "உங்கள் கேள்விக்கு இலங்கையிலுள்ள ஓர் இடத்தைக் குறிப்பிடுங்கள். எடுத்துக்காட்டு: 'கொழும்பில் வானிலை எப்படி?', 'கண்டியில் வெள்ள அபாயம் உள்ளதா?', அல்லது 'யாழ்ப்பாணத்தில் வறட்சி நிலை என்ன?'"),
    "I can only answer climate and environmental questions. Please ask about weather, hazards, climate risks, or preparedness.": (
        "මට පිළිතුරු දිය හැක්කේ දේශගුණ සහ පරිසර ප්‍රශ්නවලට පමණි. කරුණාකර කාලගුණය, උපද්‍රව, දේශගුණ අවදානම් හෝ සූදානම ගැන අසන්න.",
        "காலநிலை மற்றும் சுற்றுச்சூழல் கேள்விகளுக்கு மட்டுமே என்னால் பதிலளிக்க முடியும். வானிலை, அபாயங்கள், காலநிலை ஆபத்துகள் அல்லது முன்தயாரிப்பு பற்றிக் கேளுங்கள்."),
    "Tailoring actions to your situation makes them more effective.": (
        "ඔබේ තත්ත්වයට ගැලපෙන පරිදි ක්‍රියාමාර්ග සකස් කිරීම ඒවා වඩා ඵලදායී කරයි.",
        "உங்கள் சூழலுக்கு ஏற்ப நடவடிக்கைகளை அமைத்துக்கொள்வது அவை மேலும் பயனுள்ளதாக இருக்கும்."),
    "No supporting evidence was retrieved, so a risk level cannot be assigned.": (
        "සහාය දක්වන සාක්ෂි කිසිවක් ලබාගත නොහැකි වූ බැවින් අවදානම් මට්ටමක් නියම කළ නොහැක.",
        "ஆதரிக்கும் சான்றுகள் எதுவும் கிடைக்காததால் ஆபத்து நிலையை நிர்ணயிக்க முடியாது."),
}
_STATIC.update({en: pair for en, pair in _REC_CATALOG.items()})

_IDX = {"si": 0, "ta": 1}


# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------
def resolve_language(query: str, requested: Optional[str] = None) -> str:
    """
    Output language for a request.
      1. A Sinhala/Tamil query is answered in that language.
      2. Otherwise an explicit `requested` language ("si"/"ta") is honoured
         (e.g. English question, Sinhala answer selected in the UI).
      3. Otherwise English.
    """
    from app.services.language_service import detect_language
    detected = detect_language(query)
    if detected in ("si", "ta"):
        return detected
    if requested in ("si", "ta"):
        return requested
    return "en"


def is_in_language(text: str, lang: str) -> bool:
    """True if a meaningful share of the letters in `text` are in `lang`'s script."""
    if lang not in _SCRIPT_RANGES or not text:
        return lang == "en"
    lo, hi = _SCRIPT_RANGES[lang]
    letters = [c for c in text if c.isalpha() or lo <= c <= hi]
    if not letters:
        return False
    return sum(1 for c in letters if lo <= c <= hi) / len(letters) > 0.3


def level_phrase(level: str, lang: str) -> str:
    table = LEVEL_PHRASE.get(lang, LEVEL_PHRASE["en"])
    return table.get(str(level).lower(), table["unknown"])


def localize_factor(factor: str, lang: str) -> str:
    if lang in _IDX:
        pair = FACTOR.get(factor.lower().replace("-", " ").strip())
        if pair:
            return pair[_IDX[lang]]
    return factor.replace("-", " ")


def localize_factors(factors: list, lang: str) -> list:
    return [localize_factor(f, lang) for f in factors]


def localize_place(location: str, lang: str) -> str:
    """'Jaffna, Sri Lanka' -> 'යාපනය, ශ්‍රී ලංකාව'. Unknown places are left as-is."""
    if lang not in _IDX or not location:
        return location
    parts = [p.strip() for p in location.split(",")]
    out = []
    for p in parts:
        key = next((k for k in PLACE if k.lower() == p.lower()), None)
        out.append(PLACE[key][_IDX[lang]] if key else p)
    return ", ".join(out)


def localize_static(text: str, lang: str) -> str:
    """Exact-match translation of fixed strings; returns the original if unknown."""
    if lang in _IDX:
        pair = _STATIC.get(text)
        if pair:
            return pair[_IDX[lang]]
    return text


def foreign_message(lang: str, place: str) -> str:
    """'Sri Lanka only' notice for a place outside Sri Lanka."""
    if lang == "si":
        return (f"Climora AI දැනට ආවරණය කරන්නේ ශ්‍රී ලංකාව පමණි. '{place}' සඳහා දේශගුණ දත්ත මෙම පද්ධතියේ නොමැත. "
                "කරුණාකර ශ්‍රී ලංකාව තුළ ස්ථානයක් ගැන අසන්න — උදාහරණ: 'කොළඹ කාලගුණය කුමක්ද?' හෝ 'මහනුවර ගංවතුර අවදානම කුමක්ද?'")
    if lang == "ta":
        return (f"Climora AI தற்போது இலங்கையை மட்டுமே உள்ளடக்குகிறது. '{place}' க்கான காலநிலைத் தரவு இந்த அமைப்பில் இல்லை. "
                "இலங்கைக்குள் உள்ள ஓர் இடத்தைப் பற்றிக் கேளுங்கள் — எடுத்துக்காட்டு: 'கொழும்பில் வானிலை எப்படி?' அல்லது 'கண்டியில் வெள்ள அபாயம் என்ன?'")
    return (f"Climora AI currently covers Sri Lanka only. Climate data for '{place}' is not available in this system. "
            "Please ask about a location within Sri Lanka — for example: "
            "'What is the weather in Colombo?' or 'What is the flood risk in Kandy?'")


# ---------------------------------------------------------------------------
# Localizers for the rule-based sentences (each returns None if the text does
# not match a known template, so the caller can fall back to the LLM / English)
# ---------------------------------------------------------------------------
_EXPL_RE = re.compile(
    r"Assessed severity (\d)/5 and probability (\d)/5 \(risk score (\d+)/25\), "
    r"indicating (\w+) risk(?: driven primarily by (.+?)\.| based on the retrieved climate evidence\.)"
    r"(?: Adjusted to '(\w+)' after considering the language and context of the retrieved evidence\.)?\s*$",
    re.S,
)


def localize_explanation(text: str, lang: str) -> Optional[str]:
    if lang not in _IDX:
        return text
    m = _EXPL_RE.match(text or "")
    if not m:
        return localize_static(text, lang) if text in _STATIC else None
    sev, prob, score, level, hazard, adjusted = m.groups()
    phrase = level_phrase(level, lang)
    hz = localize_factor(hazard, lang) if hazard else None
    if lang == "si":
        s = f"තීව්‍රතාව {sev}/5, සම්භාවිතාව {prob}/5 (අවදානම් ලකුණු {score}/25) — සමස්ත තත්ත්වය: {phrase}."
        s += f" ප්‍රධාන හේතුව: {hz}." if hz else " මෙම තක්සේරුව ලබාගත් දේශගුණික සාක්ෂි මත පදනම් වේ."
        if adjusted:
            s += f" ලබාගත් සාක්ෂිවල භාෂාව සහ සන්දර්භය සලකා බැලීමෙන් පසු '{level_phrase(adjusted, lang)}' ලෙස සකස් කරන ලදී."
    else:
        s = f"தீவிரம் {sev}/5, நிகழ்தகவு {prob}/5 (ஆபத்து மதிப்பெண் {score}/25) — ஒட்டுமொத்த நிலை: {phrase}."
        s += f" முக்கிய காரணம்: {hz}." if hz else " இந்த மதிப்பீடு பெறப்பட்ட காலநிலைச் சான்றுகளை அடிப்படையாகக் கொண்டது."
        if adjusted:
            s += f" பெறப்பட்ட சான்றுகளின் மொழி மற்றும் சூழலைக் கருத்தில் கொண்டு '{level_phrase(adjusted, lang)}' ஆக சரிசெய்யப்பட்டது."
    return s


_DET_P1 = re.compile(r"Based on (\d+) retrieved source\(s\), the overall climate risk for (.+?) is assessed as (\w+)\.")
_DET_P2 = re.compile(r"Key risk factors identified: (.+?)\.(?= |$)")
_DET_P3 = re.compile(r"Primary evidence came from: (.+?)\.(?= This assessment| ?$)")
_DET_P4 = ("This assessment reflects the available evidence and should be read alongside "
           "official meteorological and disaster-management guidance.")


def localize_detailed(text: str, lang: str) -> Optional[str]:
    if lang not in _IDX or not text:
        return text
    hits = 0

    def p1(m):
        nonlocal hits; hits += 1
        n, loc, level = m.groups()
        place, phrase = localize_place(loc, lang), level_phrase(level, lang)
        if lang == "si":
            return f"{place} සඳහා සමස්ත දේශගුණ අවදානම: {phrase} (මූලාශ්‍ර {n}ක් මත පදනම්ව)."
        return f"{place} க்கான ஒட்டுமொத்த காலநிலை ஆபத்து: {phrase} ({n} ஆதாரங்களின் அடிப்படையில்)."

    def p2(m):
        nonlocal hits; hits += 1
        items = ", ".join(localize_factor(f.strip(), lang) for f in m.group(1).split(", "))
        return (f"හඳුනාගත් ප්‍රධාන අවදානම් සාධක: {items}." if lang == "si"
                else f"அடையாளம் காணப்பட்ட முக்கிய ஆபத்து காரணிகள்: {items}.")

    def p3(m):
        nonlocal hits; hits += 1
        return (f"ප්‍රධාන සාක්ෂි ලැබුණු මූලාශ්‍ර: {m.group(1)}." if lang == "si"
                else f"முக்கிய சான்றுகள் கிடைத்த மூலங்கள்: {m.group(1)}.")

    out = _DET_P1.sub(p1, text)
    out = _DET_P2.sub(p2, out)
    out = _DET_P3.sub(p3, out)
    if _DET_P4 in out:
        hits += 1
        out = out.replace(_DET_P4, "මෙම තක්සේරුව පවතින සාක්ෂි පිළිබිඹු කරන අතර, නිල කාලගුණ විද්‍යා සහ ආපදා කළමනාකරණ මාර්ගෝපදේශ සමඟ එක්ව කියවිය යුතුය."
                          if lang == "si" else
                          "இந்த மதிப்பீடு கிடைத்துள்ள சான்றுகளைப் பிரதிபலிக்கிறது; அதிகாரப்பூர்வ வானிலை மற்றும் பேரிடர் மேலாண்மை வழிகாட்டுதல்களுடன் சேர்த்துப் படிக்க வேண்டும்.")
    return out if hits >= 2 else None


_FRAMING_RE = re.compile(r"^As an? (\w+), focus your preparations on .+$")


def localize_recommendation_text(text: str, lang: str) -> Optional[str]:
    """Translate one recommendation action/explanation, or None if unknown."""
    if lang not in _IDX:
        return text
    if text in _STATIC:
        return localize_static(text, lang)
    m = _FRAMING_RE.match(text or "")
    if m and m.group(1) in USER_TYPE:
        label, focus = USER_TYPE[m.group(1)]
        i = _IDX[lang]
        return (f"{label[i]} ලෙස, ඔබේ සූදානම {focus[i]} කෙරෙහි යොමු කරන්න" if lang == "si"
                else f"{label[i]} என்ற முறையில், உங்கள் தயாரிப்புகளை {focus[i]} மீது கவனம் செலுத்துங்கள்")
    return None


# ---------------------------------------------------------------------------
# Data-based summary (works with no LLM)
# ---------------------------------------------------------------------------
def _live_readings(docs: list) -> dict:
    """Pull headline numbers out of the live evidence text."""
    r: dict = {}
    for d in docs:
        t = (d.get("content") or d.get("snippet") or "")
        low = t.lower()
        m = re.search(r"current weather in .+?: (.+?), temperature: (-?[\d.]+)°c, humidity: (\d+)%, wind speed: ([\d.]+) m/s", low)
        if m and "cond" not in r:
            r["cond"], r["temp"], r["hum"], r["wind"] = m.group(1), float(m.group(2)), int(m.group(3)), float(m.group(4))
        m = re.search(r"temperature is (-?[\d.]+)°c, wind speed is ([\d.]+) km/h", low)
        if m and "temp" not in r:
            r["temp"], r["wind"] = float(m.group(1)), round(float(m.group(2)) / 3.6, 1)
        m = re.search(r"precipitation totals? (?:are )?\[([^\]]+)\]", low)
        if m and "rain_mm" not in r:
            vals = [float(v) for v in re.findall(r"\d+\.?\d*", m.group(1))]
            if vals:
                r["rain_mm"] = round(sum(vals), 1)
        m = re.search(r"precipitation probabilit[a-z]* (?:are |of )?\[([^\]]+)\]", low)
        if m and "rain_prob" not in r:
            vals = [float(v) for v in re.findall(r"\d+\.?\d*", m.group(1))]
            if vals:
                r["rain_prob"] = int(max(vals))
        m = re.search(r"us aqi is (\d+)", low)
        if m and "aqi" not in r:
            r["aqi"] = int(m.group(1))
    return r


def build_summary(lang: str, location: str, live_docs: list, level: str, factors: list) -> str:
    """
    Plain-language summary built from the live readings and the risk result,
    in English, Sinhala or Tamil. Used when no LLM is available.
    """
    lang = lang if lang in ("en", "si", "ta") else "en"
    r = _live_readings(live_docs)
    place = localize_place(location or "Sri Lanka", lang)
    i = _IDX.get(lang)
    parts: list = []

    if "temp" in r:
        cond = r.get("cond", "")
        cond_txt = (CONDITION[cond][i] if (i is not None and cond in CONDITION) else cond)
        cond_txt = f"{cond_txt}, " if cond_txt else ""
        hum = f", {'ආර්ද්‍රතාව' if lang == 'si' else 'ஈரப்பதம்' if lang == 'ta' else 'humidity'} {r['hum']}%" if "hum" in r else ""
        wind_lbl = "සුළං වේගය" if lang == "si" else "காற்றின் வேகம்" if lang == "ta" else "wind"
        wind = f", {wind_lbl} {r['wind']} m/s" if "wind" in r else ""
        head = {"en": "Current weather", "si": "වත්මන් කාලගුණය", "ta": "தற்போதைய வானிலை"}[lang]
        parts.append(f"{place} — {head}: {cond_txt}{r['temp']}°C{hum}{wind}." if lang != "en"
                     else f"{head} in {place}: {cond_txt}{r['temp']}°C{hum}{wind}.")

    if "rain_mm" in r:
        prob = r.get("rain_prob")
        if lang == "si":
            parts.append(f"දින 7 වර්ෂා පුරෝකථනය: මුළු වර්ෂාපතනය ආසන්න වශයෙන් {r['rain_mm']} mm" + (f"; වැස්ස සම්භාවිතාව උපරිම {prob}%." if prob is not None else "."))
        elif lang == "ta":
            parts.append(f"7 நாள் மழை முன்னறிவிப்பு: மொத்த மழை ஏறத்தாழ {r['rain_mm']} மி.மீ" + (f"; மழை வாய்ப்பு அதிகபட்சம் {prob}%." if prob is not None else "."))
        else:
            parts.append(f"7-day rainfall outlook: about {r['rain_mm']} mm in total" + (f", with up to a {prob}% chance of rain." if prob is not None else "."))

    if "aqi" in r:
        cat = next(c for c in AQI_CATEGORY if r["aqi"] <= c[0])
        cat_txt = cat[1] if lang == "en" else cat[2 if lang == "si" else 3]
        lbl = {"en": "Air quality", "si": "වායු ගුණාත්මකභාවය", "ta": "காற்றின் தரம்"}[lang]
        parts.append(f"{lbl}: {cat_txt} (AQI {r['aqi']}).")

    if not parts:
        parts.append({"en": f"Assessment for {place} based on the retrieved evidence.",
                      "si": f"{place} සඳහා ලබාගත් සාක්ෂි මත පදනම් වූ තක්සේරුව.",
                      "ta": f"{place} க்கான, பெறப்பட்ட சான்றுகளின் அடிப்படையிலான மதிப்பீடு."}[lang])

    phrase = level_phrase(level, lang)
    if lang == "si":
        risk = f"සමස්ත දේශගුණ අවදානම: {phrase}."
        if factors: risk += f" ප්‍රධාන සාධක: {', '.join(localize_factors(factors, lang))}."
    elif lang == "ta":
        risk = f"ஒட்டுமொத்த காலநிலை ஆபத்து: {phrase}."
        if factors: risk += f" முக்கிய காரணிகள்: {', '.join(localize_factors(factors, lang))}."
    else:
        risk = f"Overall climate risk: {phrase}."
        if factors: risk += f" Main factors: {', '.join(factors)}."
    parts.append(risk)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Optional LLM fallback for free-form text the catalogue doesn't know
# ---------------------------------------------------------------------------
_LLM_CACHE: dict = {}


async def _llm_translate(text: str, lang: str) -> str:
    """Translate free text with the LLM if one is available; else return it unchanged."""
    key = (lang, text)
    if key in _LLM_CACHE:
        return _LLM_CACHE[key]
    try:
        from app.services.llm_service import llm_service
        if not llm_service.is_available():
            return text
        name = {"si": "Sinhala", "ta": "Tamil"}[lang]
        out = await llm_service.invoke_model(
            prompt=(f"Translate the following climate-safety text into {name} using {name} script. "
                    f"Keep numbers, units and proper names. Output ONLY the translation.\n\n{text}"),
            system_prompt=f"You are a precise English-to-{name} translator for public safety information.",
            max_tokens=600, temperature=0.1,
        )
        out = (out or "").strip()
        if out and is_in_language(out, lang):
            _LLM_CACHE[key] = out
            return out
    except Exception as exc:  # never let translation break the response
        logger.warning("LLM translation failed: %s", exc)
    return text


async def localize_text(text: str, lang: str, kind: str = "static") -> str:
    """
    Localize one text. Order: exact catalogue -> sentence templates -> LLM -> original.
    kind: "explanation" | "detailed" | "recommendation" | "static"
    """
    if lang not in _IDX or not text:
        return text
    if kind == "explanation":
        out = localize_explanation(text, lang)
    elif kind == "detailed":
        out = localize_detailed(text, lang)
    elif kind == "recommendation":
        out = localize_recommendation_text(text, lang)
    else:
        out = localize_static(text, lang)
        out = out if out != text else None
    if out is not None and out != text:
        return out
    return await _llm_translate(text, lang)
