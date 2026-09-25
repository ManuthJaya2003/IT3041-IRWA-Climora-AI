import asyncio
import hashlib
import os
import re
import time
from typing import Optional


# Directory to store generated audio files
AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "audio_cache",
)


class TTSService:
    """Text-to-Speech service supporting gTTS (online) and pyttsx3 (offline)."""

    def __init__(self):
        self._available = False
        self._has_gtts = False
        self._has_pyttsx3 = False
        os.makedirs(AUDIO_DIR, exist_ok=True)

    async def initialize(self):
        """Check for available TTS engines."""
        try:
            from gtts import gTTS
            self._has_gtts = True
        except ImportError:
            self._has_gtts = False

        try:
            import importlib
            importlib.import_module("pyttsx3")
            self._has_pyttsx3 = True
        except Exception:
            self._has_pyttsx3 = False

        self._available = self._has_gtts or self._has_pyttsx3

        if self._has_gtts:
            print(f"   [OK] TTS service initialized (engine: gTTS, cache: {AUDIO_DIR})")
        elif self._has_pyttsx3:
            print(f"   [OK] TTS service initialized (engine: pyttsx3 offline fallback, cache: {AUDIO_DIR})")
        else:
            print("   [!] TTS service: Neither gTTS nor pyttsx3 installed - run: pip install gTTS")

    def is_available(self) -> bool:
        return self._available

    @staticmethod
    def _clean_text_for_speech(text: str) -> str:
        """Strip markdown syntax and formatting so TTS speaks naturally."""
        if not text:
            return ""
        # Remove URLs: [label](http...) -> label
        cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Remove raw URLs
        cleaned = re.sub(r'https?://\S+', '', cleaned)
        # Remove bold / italic markers
        cleaned = re.sub(r'[*_~`#>]', '', cleaned)
        # Remove bullet markers at line start
        cleaned = re.sub(r'^\s*[-+*]\s+', '', cleaned, flags=re.MULTILINE)
        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    async def synthesize(self, text: str, language: str = "en") -> Optional[str]:
        """
        Convert text to speech and save as MP3 file.

        Args:
            text: Text to convert to speech.
            language: Language code ('en', 'si', 'ta').

        Returns:
            Path to the generated audio file, or None if failed.
        """
        if not self._available or not text.strip():
            return None

        # Clean text for TTS
        clean_text = self._clean_text_for_speech(text)
        if not clean_text:
            return None

        # Limit text length to prevent giant generation requests
        if len(clean_text) > 3000:
            clean_text = clean_text[:3000] + "..."

        # Generate a cache key based on language + content hash
        cache_key = hashlib.md5(f"{language}:{clean_text}".encode("utf-8")).hexdigest()
        filename = f"{cache_key}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)

        # Check existing cache
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath

        # 1. Try gTTS first (higher quality, multilingual support)
        if self._has_gtts:
            try:
                from gtts import gTTS
                lang_map = {"en": "en", "si": "si", "ta": "ta"}
                gtts_lang = lang_map.get(language, "en")

                def _generate_gtts():
                    tts = gTTS(text=clean_text, lang=gtts_lang, slow=False)
                    tts.save(filepath)

                await asyncio.to_thread(_generate_gtts)
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    return filepath
            except Exception as e:
                print(f"   [!] gTTS failed ({e}), trying offline fallback...")

        # 2. Offline fallback: pyttsx3
        if self._has_pyttsx3:
            try:
                def _generate_pyttsx3():
                    import importlib
                    pyttsx3 = importlib.import_module("pyttsx3")
                    wav_path = filepath.replace(".mp3", ".wav")
                    engine = pyttsx3.init()
                    engine.setProperty("rate", 160)
                    engine.save_to_file(clean_text, wav_path)
                    engine.runAndWait()
                    if os.path.exists(wav_path):
                        os.replace(wav_path, filepath)

                await asyncio.to_thread(_generate_pyttsx3)
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    return filepath
            except Exception as e2:
                print(f"   [!] Offline TTS also failed: {e2}")

        return None

    async def get_audio_path(self, filename: str) -> Optional[str]:
        """Get full path to a cached audio file."""
        filepath = os.path.join(AUDIO_DIR, filename)
        if os.path.exists(filepath) and os.path.isfile(filepath):
            return filepath
        return None

    async def cleanup_old_files(self, max_age_hours: int = 24):
        """Remove audio files older than max_age_hours."""
        now = time.time()
        max_age_seconds = max_age_hours * 3600

        try:
            for filename in os.listdir(AUDIO_DIR):
                filepath = os.path.join(AUDIO_DIR, filename)
                if os.path.isfile(filepath):
                    file_age = now - os.path.getmtime(filepath)
                    if file_age > max_age_seconds:
                        try:
                            os.remove(filepath)
                        except OSError:
                            pass
        except OSError:
            pass


# Singleton instance
tts_service = TTSService()
