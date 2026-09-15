"""
Language Detection & Multilingual Support Service.

Detects whether user input is in English, Sinhala, or Tamil based on
Unicode character ranges. No external dependencies needed.

Sinhala Unicode: U+0D80 – U+0DFF
Tamil Unicode:  U+0B80 – U+0BFF
"""


# Language codes matching gTTS and Web Speech API
LANG_ENGLISH = "en"
LANG_SINHALA = "si"
LANG_TAMIL = "ta"

LANGUAGE_NAMES = {
    LANG_ENGLISH: "English",
    LANG_SINHALA: "Sinhala",
    LANG_TAMIL: "Tamil",
}


def detect_language(text: str) -> str:
    """
    Detect language from text using Unicode character ranges.

    Returns:
        Language code: 'en', 'si', or 'ta'
    """
    if not text:
        return LANG_ENGLISH

    sinhala_count = 0
    tamil_count = 0
    latin_count = 0
    total_alpha = 0

    for char in text:
        if char.isalpha() or '\u0D80' <= char <= '\u0DFF' or '\u0B80' <= char <= '\u0BFF':
            total_alpha += 1
            # Sinhala: U+0D80 to U+0DFF
            if '\u0D80' <= char <= '\u0DFF':
                sinhala_count += 1
            # Tamil: U+0B80 to U+0BFF
            elif '\u0B80' <= char <= '\u0BFF':
                tamil_count += 1
            # Latin characters (English)
            elif char.isascii() and char.isalpha():
                latin_count += 1

    if total_alpha == 0:
        return LANG_ENGLISH

    # If more than 20% of characters are Sinhala/Tamil, classify as that language
    sinhala_ratio = sinhala_count / total_alpha
    tamil_ratio = tamil_count / total_alpha

    if sinhala_ratio > 0.2:
        return LANG_SINHALA
    elif tamil_ratio > 0.2:
        return LANG_TAMIL
    else:
        return LANG_ENGLISH


def get_language_name(lang_code: str) -> str:
    """Get human-readable language name."""
    return LANGUAGE_NAMES.get(lang_code, "English")


def get_response_instruction(lang_code: str) -> str:
    """
    Get the system prompt instruction for responding in the detected language.
    """
    if lang_code == LANG_SINHALA:
        return (
            "IMPORTANT: The user is writing in Sinhala (සිංහල). "
            "You MUST respond entirely in Sinhala language using Sinhala script. "
            "Do not mix English unless it's a technical term with no Sinhala equivalent."
        )
    elif lang_code == LANG_TAMIL:
        return (
            "IMPORTANT: The user is writing in Tamil (தமிழ்). "
            "You MUST respond entirely in Tamil language using Tamil script. "
            "Do not mix English unless it's a technical term with no Tamil equivalent."
        )
    else:
        return "Respond in English."
