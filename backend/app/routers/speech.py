"""
Speech API endpoints — Text-to-Speech and voice query support.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.services.tts_service import tts_service
from app.services.language_service import detect_language
from app.agents.orchestrator.orchestrator_agent import OrchestratorAgent
from app.models.schemas import ChatRequest

router = APIRouter()

orchestrator = OrchestratorAgent()


# --- Request Models ---

class SpeakRequest(BaseModel):
    """Request to convert text to speech."""
    text: str = Field(..., description="Text to convert to speech")
    language: Optional[str] = Field(None, description="Language code (en, si, ta). Auto-detected if not provided.")


class VoiceQueryRequest(BaseModel):
    """Voice query — text from speech recognition sent for processing + TTS response."""
    query: str = Field(..., description="Transcribed text from user's voice input")
    location: Optional[str] = Field(None, description="User's location")
    session_id: Optional[str] = Field(None, description="Session ID for continuity")


# --- Endpoints ---

@router.post("/speak")
async def text_to_speech(request: SpeakRequest):
    """
    Convert text to speech audio.
    Returns an MP3 audio file.
    """
    # Lazy initialize if startup hasn't run yet (e.g. first request race condition)
    if not tts_service.is_available():
        await tts_service.initialize()

    if not tts_service.is_available():
        raise HTTPException(status_code=503, detail="TTS service not available. Install gTTS: pip install gTTS")

    # Auto-detect language if not provided
    language = request.language or detect_language(request.text)

    audio_path = await tts_service.synthesize(text=request.text, language=language)

    if not audio_path:
        raise HTTPException(status_code=500, detail="Failed to generate audio")

    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        filename="climora_response.mp3",
    )


@router.post("/voice-query")
async def voice_query(request: VoiceQueryRequest):
    """
    Process a voice query: runs through the full pipeline and returns
    both the text response AND an audio file URL.

    Frontend flow:
    1. User speaks → Web Speech API transcribes → sends text here
    2. Backend processes through orchestrator pipeline
    3. Returns JSON response + audio URL for playback
    """
    # Process through normal pipeline
    chat_request = ChatRequest(
        query=request.query,
        location=request.location,
        session_id=request.session_id,
    )

    response = await orchestrator.process_user_query(chat_request)

    # Generate TTS audio for the summary
    audio_url = None
    if not tts_service.is_available():
        await tts_service.initialize()
    if tts_service.is_available():
        audio_path = await tts_service.synthesize(
            text=response.summary,
            language=response.language,
        )
        if audio_path:
            # Return the filename — frontend will fetch from /api/v1/speech/audio/{filename}
            import os
            audio_url = f"/api/v1/speech/audio/{os.path.basename(audio_path)}"

    return {
        "response": response.model_dump(),
        "audio_url": audio_url,
        "language": response.language,
    }


@router.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve a cached audio file."""
    # Sanitize filename to prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    audio_path = await tts_service.get_audio_path(filename)

    if not audio_path:
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
    )
