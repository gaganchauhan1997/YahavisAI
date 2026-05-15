"""
YAHAVIS — voice/wakeword.py
Always-on wake word detection using Porcupine (free tier).
Falls back to simple energy-based hotword if no Porcupine key.
"""

import asyncio
import logging
import os

log = logging.getLogger("yahavis.wakeword")

PORCUPINE_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")


class WakeWordDetector:
    """
    Detects 'Hey Yahavi' wake word with minimal CPU usage.
    Uses Porcupine for accurate detection when key is available,
    falls back to basic energy + SpeechRecognition check.
    """

    def __init__(self, on_wake_callback):
        self.callback = on_wake_callback
        self._active = False
        self.engine = self._select_engine()

    def _select_engine(self) -> str:
        if PORCUPINE_KEY:
            try:
                import pvporcupine  # noqa
                return "porcupine"
            except ImportError:
                pass
        return "energy"

    async def start(self):
        self._active = True
        if self.engine == "porcupine":
            await asyncio.to_thread(self._porcupine_loop)
        else:
            log.warning("No Porcupine key — using energy-based wake detection.")
            await self._energy_loop()

    def _porcupine_loop(self):
        """Run Porcupine wake word detection in a blocking thread."""
        import pvporcupine
        import pyaudio
        import struct

        porcupine = pvporcupine.create(
            access_key=PORCUPINE_KEY,
            keywords=["hey google"],  # Closest built-in; replace with custom model
        )
        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
        )
        log.info("Porcupine wake word active — listening...")

        while self._active:
            pcm = audio_stream.read(porcupine.frame_length)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            result = porcupine.process(pcm)
            if result >= 0:
                log.info("Wake word detected!")
                asyncio.run_coroutine_threadsafe(self.callback(), asyncio.get_event_loop())

        audio_stream.close()
        pa.terminate()
        porcupine.delete()

    async def _energy_loop(self):
        """Simple energy-based loop — listens for speech above threshold."""
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        mic = sr.Microphone()

        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)

        while self._active:
            try:
                with mic as source:
                    audio = await asyncio.to_thread(
                        recognizer.listen, source, timeout=None, phrase_time_limit=4
                    )
                text = await asyncio.to_thread(
                    recognizer.recognize_google, audio
                )
                if any(kw in text.lower() for kw in ["hey yahavi", "yahavi", "yahavis"]):
                    log.info(f"Wake word detected via SR: '{text}'")
                    await self.callback()
            except Exception:
                pass

    def stop(self):
        self._active = False
