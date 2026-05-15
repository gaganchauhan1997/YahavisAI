"""
YAHAVIS — voice/speaker.py
Text-to-speech output engine.
Primary: edge-tts (Microsoft Neural, free, natural)
Fallback: pyttsx3 (fully offline)
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger("yahavis.speaker")

VOICE    = os.getenv("TTS_VOICE", "en-US-GuyNeural")
RATE     = os.getenv("TTS_RATE",  "+10%")
PITCH    = os.getenv("TTS_PITCH", "+0Hz")


class VoiceSpeaker:
    """
    JARVIS-style TTS speaker.
    Usage:
        speaker = VoiceSpeaker()
        await speaker.say("Online and ready, Boss.")
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._engine = self._detect_engine()
        log.info(f"Speaker ready — engine: {self._engine}, voice: {VOICE}")

    def _detect_engine(self) -> str:
        try:
            import edge_tts  # noqa
            return "edge_tts"
        except ImportError:
            pass
        try:
            import pyttsx3  # noqa
            return "pyttsx3"
        except ImportError:
            pass
        log.warning("No TTS engine found — speech will be silent.")
        return "none"

    async def say(self, text: str):
        """Speak text aloud. Thread-safe (queues if already speaking)."""
        if not text.strip():
            return
        async with self._lock:
            log.info(f"[SPEAK] {text[:80]}{'...' if len(text)>80 else ''}")
            if self._engine == "edge_tts":
                await self._speak_edge(text)
            elif self._engine == "pyttsx3":
                await asyncio.to_thread(self._speak_pyttsx3, text)
            else:
                print(f"[YAHAVIS] {text}")

    async def _speak_edge(self, text: str):
        try:
            import edge_tts
            import pygame

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name

            communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
            await communicate.save(tmp_path)

            # Play via pygame
            await asyncio.to_thread(self._play_audio, tmp_path)

            # Cleanup
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        except Exception as e:
            log.warning(f"edge-tts failed: {e} — falling back to pyttsx3")
            await asyncio.to_thread(self._speak_pyttsx3, text)

    def _play_audio(self, path: str):
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            log.warning(f"Audio playback error: {e}")

    def _speak_pyttsx3(self, text: str):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.setProperty("volume", 0.9)
            voices = engine.getProperty("voices")
            # Try to find a male voice
            for voice in voices:
                if "male" in voice.name.lower() or "david" in voice.name.lower():
                    engine.setProperty("voice", voice.id)
                    break
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            log.warning(f"pyttsx3 failed: {e}")
            print(f"[YAHAVIS] {text}")

    async def set_voice(self, voice_name: str):
        global VOICE
        VOICE = voice_name
        log.info(f"Voice changed to: {voice_name}")

    async def list_voices(self) -> list[str]:
        """List available edge-tts voices."""
        try:
            import edge_tts
            voices = await edge_tts.list_voices()
            return [v["ShortName"] for v in voices if "en" in v["ShortName"].lower()]
        except Exception:
            return [VOICE]
