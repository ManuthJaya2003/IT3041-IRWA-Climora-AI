"""
Text-to-Speech Service using gTTS.

Converts text responses into audio files in English, Sinhala, or Tamil.
Uses Google Translate's TTS engine (free, no API key needed).

Supported languages:
- 'en' → English
- 'si' → Sinhala
- 'ta' → Tamil
"""

import os
import uuid
import hashlib
from pathlib import Path


# Directory to store generated audio files
AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "audio_cache",
)


class TTSService:
    """Text-to-Speech service using gTTS."""

    def __init__(self):
        self._available = False
        os.makedirs(AUDIO_DIR, exist_ok=True)

    async def initialize(self):
        """Check if gTTS is available."""
        try:
            from gtts import gTTS
            self._available = True
            print(f"   ✓ TTS service initialized (engine: gTTS, cache: {AUDIO_DIR})")
        except ImportError:
            self._available = False
            print("   ⚠ TTS service: gTTS not installed - run: pip install gTTS")

    def is_available(self) -> bool:
        return self._available

    async def synthesize(self, text: str, language: str = "en") -> str | None:
        """
        Convert text to speech and save as MP3 file.

        Args:
            text: Text to convert to speech.
            language: Language code ('en', 'si', 'ta').

        Returns:
            Path to the generated audio file, or None if failed.
        """
        if not self._available:
            return None

        # Clean text for TTS (remove markdown bold markers, etc.)
        clean_text = text.replace("**", "").replace("*", "")

        # Limit text length
        if len(clean_text) > 3000:
            clean_text = clean_text[:3000] + "..."

        # Generate a cache key based on text + language
        import hashlib
        cache_key = hashlib.md5(f"{language}:{clean_text}".encode()).hexdigest()
        filename = f"{cache_key}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        # Check cache
        if os.path.exists(filepath):
            return filepath

        # Try gTTS first (better quality, needs internet)
        try:
            from gtts import gTTS
            lang_map = {"en": "en", "si": "si", "ta": "ta"}
            gtts_lang = lang_map.get(language, "en")

            tts = gTTS(text=clean_text, lang=gtts_lang, slow=False)
            tts.save(filepath)
            return filepath
        except Exception as e:
            print(f"   ⚠ gTTS failed ({e}), trying offline fallback...")

        # Fallback: pyttsx3 (offline, English only but always works)
        try:
            import pyttsx3
            wav_path = filepath.replace(".mp3", ".wav")
            engine = pyttsx3.init()
            engine.setProperty('rate', 160)
            engine.save_to_file(clean_text, wav_path)
            engine.runAndWait()

            # pyttsx3 saves as WAV — rename to serve
            os.rename(wav_path, filepath)
            return filepath
        except Exception as e2:
            print(f"   ✗ Offline TTS also failed: {e2}")
            return None

    async def get_audio_path(self, filename: str) -> str | None:
        """Get full path to a cached audio file."""
        filepath = os.path.join(AUDIO_DIR, filename)
        if os.path.exists(filepath):
            return filepath
        return None

    async def cleanup_old_files(self, max_age_hours: int = 24):
        """Remove audio files older than max_age_hours."""
        import time

        now = time.time()
        max_age_seconds = max_age_hours * 3600

        for filename in os.listdir(AUDIO_DIR):
            filepath = os.path.join(AUDIO_DIR, filename)
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)


# Singleton instance
tts_service = TTSService()
