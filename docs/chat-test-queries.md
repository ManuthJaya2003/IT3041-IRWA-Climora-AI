# Climora AI Chat Test Queries

Use these queries to test different Sri Lankan locations, crops, user types,
languages, and weather scenarios. The user type does not need to be changed in
Settings because the backend should infer it from the query.

## English farmer queries

### Tea - Nuwara Eliya

> I am a tea farmer in Nuwara Eliya. Should I apply fertilizer this week considering the current rainfall and temperature?

### Coconut - Kurunegala

> I grow coconut in Kurunegala. How should I manage irrigation and coconut pest risks over the next 30 days?

### Rubber - Kegalle

> I am a rubber farmer in Kegalle. Is it safe to tap rubber trees during the expected rain, and how can I reduce fungal disease?

### Vegetables - Badulla

> I grow vegetables in Badulla. Which crops are suitable for planting now, and how should I protect them from heavy rain?

### Rice - Polonnaruwa

> I am a paddy farmer in Polonnaruwa. Should I start planting now, and how should I manage water levels in my field?

### Mixed farming - Matale

> I have a mixed farm in Matale with vegetables and fruit trees. What weather-related risks should I prepare for this week?

## Other user types

### Student - Colombo

> I am a student in Colombo preparing for exams. How could the current heat and rainfall affect my study schedule and travel plans?

### Business - Galle

> I run a tourism business in Galle. What weather risks should I consider for customers and outdoor activities this week?

### Organization - Batticaloa

> Our community organization in Batticaloa is planning flood preparedness activities. What should we prioritize based on the current weather?

### Institution - Kandy

> I manage a school in Kandy. What precautions should we take for students during heavy rain and possible flooding?

## Sinhala queries

### Tea

> මම නුවරඑළියේ තේ ගොවියෙක්මි. වර්තමාන වැසි සහ උෂ්ණත්වය අනුව මේ සතියේ පොහොර යෙදීම සුදුසුද?

### Coconut

> මම කුරුණෑගල පොල් වගාකරුවෙක්මි. ඉදිරි දින 30 තුළ ජලසම්පාදනය සහ පොල් කෘමි අවදානම් කළමනාකරණය කරන්නේ කෙසේද?

### Rice

> මම පොළොන්නරුවේ වී ගොවියෙක්මි. දැන් වගා කිරීම ආරම්භ කළ යුතුද? කුඹුරේ ජල මට්ටම කළමනාකරණය කරන්නේ කෙසේද?

### Student

> මම කොළඹ ශිෂ්‍යයෙක්මි. වර්තමාන උෂ්ණත්වය සහ වැසි මගේ අධ්‍යයන කාලසටහනට බලපාන්නේ කෙසේද?

## Tamil queries

### Tea

> நான் நுவரெலியாவில் தேயிலை விவசாயி. தற்போதைய மழை மற்றும் வெப்பநிலையை கருத்தில் கொண்டு இந்த வாரம் உரமிடலாமா?

### Rubber

> நான் கேகாலை பகுதியில் ரப்பர் விவசாயம் செய்கிறேன். எதிர்பார்க்கப்படும் மழையின் போது ரப்பர் மரங்களில் பால் வடிக்கலாமா?

### Vegetables

> நான் பதுளையில் காய்கறி விவசாயி. இப்போது எந்த பயிர்களை நடவு செய்யலாம்? அதிக மழையிலிருந்து அவற்றை எவ்வாறு பாதுகாப்பது?

### Institution

> நான் கண்டியில் ஒரு பள்ளியை நிர்வகிக்கிறேன். கனமழை மற்றும் வெள்ள அபாயத்தின் போது மாணவர்களுக்காக என்ன முன்னெச்சரிக்கைகள் எடுக்க வேண்டும்?

## Automatic role inference

These queries should infer the farmer role even when the Settings role is
Individual:

```text
I need advice about planting tea and managing fertilizer in Hatton.
```

```text
எனது தென்னை தோட்டத்திற்கு மட்டக்களப்பில் நீர் மேலாண்மை ஆலோசனை வேண்டும்.
```

```text
මගේ රබර් වගාව සඳහා කෑගල්ලේ වැසි කාලයේ රෝග පාලනය කරන්නේ කෙසේද?
```

## Traveller queries (all three languages)

Role inference picks Traveller even when Settings stays on the default
Individual role — no settings change needed.

### English

> I am a tourist visiting Galle. Is it safe to go sightseeing and visit the beaches this week?

### Sinhala

> මම ගාල්ලට සංචාරකයෙක් ලෙස යනවා. මෙම සතියේ මුහුදු වෙරළ නැරඹීම ආරක්ෂිතද?

### Tamil

> நான் காலிக்கு சுற்றுலா பயணியாக வருகிறேன். இந்த வாரம் கடற்கரைக்கு செல்வது பாதுகாப்பானதா?

## More role queries in Sinhala and Tamil

### Student (Tamil)

> நான் கொழும்பில் ஒரு மாணவர். தற்போதைய வெப்பம் மற்றும் மழை எனது படிப்பு அட்டவணையை எவ்வாறு பாதிக்கும்?

### Business (Sinhala)

> මම ගාල්ලේ සංචාරක ව්‍යාපාරයක් පවත්වාගෙන යනවා. මේ සතියේ ගනුදෙනුකරුවන් සඳහා කාලගුණ අවදානම් මොනවද?

### Business (Tamil)

> நான் காலியில் சுற்றுலா வணிகம் நடத்துகிறேன். வாடிக்கையாளர்களுக்கான வானிலை அபாயங்கள் என்ன?

### Organization (Sinhala)

> මඩකලපුවේ අපේ ප්‍රජා සංවිධානය ගංවතුර සූදානම් කටයුතු සැලසුම් කරනවා. වර්තමාන කාලගුණය අනුව ප්‍රමුඛතා මොනවද?

### Institution (Sinhala)

> මම මහනුවර පාසලක් කළමනාකරණය කරනවා. අධික වර්ෂාවේදී සිසුන් සඳහා ගත යුතු පූර්වාරක්ෂා මොනවද?

## Note on Settings role vs query role

If Settings keeps the default Individual role, a query that names a role
(for example starting with "as a student..." or containing "I am a farmer")
still gets that role's tailored recommendations, because query wording
overrides the stored setting. The stored setting applies only when the
query itself names no role.

## Bedrock and verification test

This query should produce multiple evidence-based claims:

> I am a vegetable farmer in Badulla. Analyze the current weather, identify the main climate risks, and give evidence-based recommendations for irrigation, fertilizer, and disease prevention over the next 30 days.

When testing, check the backend logs for:

- No `NameError`.
- No `AWS Bedrock is unavailable` message from the verification agent.
- A successful `/tools/verify_claims` request.
- Farmer and crop-specific recommendations.
- A Sinhala or Tamil response for queries in those languages.
- The newest conversation appearing first in Recent chats.
