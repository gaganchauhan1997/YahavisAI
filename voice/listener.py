"""
YAHAVIS — voice/listener.py
Continuous microphone listener with hotword detection.
Hotword: "Hey Yahavi" → capture command → transcribe → handle
Fallback: Ctrl+Space keyboard shortcut for push-to-talk
"""

import asyncio
import logging
import os
import queue
import threading
import time
from pathlib import Path

log = logging.getLogger("yahavis.listener")

HOTWORD        = os.getenv("YAHAVIS_HOTWORD", "hey yahavi")
PTT_SHORTCUT   = os.getenv("PTT_SHORTCUT", "ctrl+space")
SILENCE_SECS   = float(os.getenv("SILENCE_THRESHOLD_SECS", "1.5"))
MAX_LISTEN     = float(os.getenv("MAX_LISTEN_SECS", "30"))
WHISPER_MODEL  = os.getenv("WHISPER_MODEL", "base")


class VoiceListener:
    """
    Listens for hotword → records command → transcribes → sends to orchestrator.
    Falls back to keyboard push-to-talk if mic unavailable.
    """

    def __init__(self):
        self._transcriber = self._init_transcriber()
        self._active = False
        self._ptt_mode = False
        log.info(f"Listener ready — hotword: '{HOTWORD}', PTT: {PTT_SHORTCUT}")

    def _init_transcriber(self):
        """Try faster-whisper first, fall back to SpeechRecognition."""
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(WHISPER_MODEL, device="cpu",
                                 compute_type="int8")
            log.info(f"Using faster-whisper ({WHISPER_MODEL})")
            return ("whisper", model)
        except ImportError:
            pass
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            log.info("Using SpeechRecognition (Google online)")
            return ("sr", recognizer)
        except ImportError:
            log.warning("No transcription engine found — using keyboard input mode.")
            return ("keyboard", None)

    async def start(self, orchestrator):
        """Main entry — start listening loop."""
        self._active = True
        engine = self._transcriber[0]

        if engine == "keyboard":
            await self._keyboard_loop(orchestrator)
            return

        # Set up keyboard PTT shortcut in background
        threading.Thread(
            target=self._setup_ptt_shortcut,
            args=(orchestrator,),
            daemon=True,
        ).start()

        # Main hotword + listening loop
        await self._mic_loop(orchestrator)

    async def _mic_loop(self, orchestrator):
        """Continuous mic monitoring with hotword detection."""
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        mic = sr.Microphone()

        log.info("Microphone active. Say 'Hey Yahavi' to activate.")

        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)

        while self._active:
            try:
                with mic as source:
                    audio = await asyncio.to_thread(
                        recognizer.listen, source,
                        timeout=None, phrase_time_limit=MAX_LISTEN
                    )

                text = await self._transcribe(audio)
                if not text:
                    continue

                log.debug(f"Heard: {text}")

                # Check for hotword
                if HOTWORD.lower() in text.lower():
                    command = text.lower().replace(HOTWORD.lower(), "").strip()
                    if command:
                        await orchestrator.handle(command)
                    else:
                        # Hotword only — wait for follow-up
                        await self._listen_for_command(orchestrator, mic, recognizer)

            except Exception as e:
                if "WaitTimeoutError" not in type(e).__name__:
                    log.warning(f"Listener error: {e}")
                await asyncio.sleep(0.1)

    async def _listen_for_command(self, orchestrator, mic, recognizer):
        """After hotword detected, listen for the actual command."""
        import speech_recognition as sr
        log.info("Hotword detected — listening for command...")
        try:
            with mic as source:
                audio = await asyncio.to_thread(
                    recognizer.listen, source,
                    timeout=5, phrase_time_limit=MAX_LISTEN
                )
            command = await self._transcribe(audio)
            if command:
                await orchestrator.handle(command)
        except Exception as e:
            log.warning(f"Command capture error: {e}")

    async def _transcribe(self, audio) -> str:
        """Transcribe audio to text using the configured engine."""
        engine, model = self._transcriber

        if engine == "whisper":
            return await asyncio.to_thread(self._whisper_transcribe, audio, model)
        elif engine == "sr":
            return await asyncio.to_thread(self._sr_transcribe, audio, model)
        return ""

    def _whisper_transcribe(self, audio, model) -> str:
        try:
            import io
            import numpy as np
            import soundfile as sf

            wav_data = audio.get_wav_data()
            audio_array, sample_rate = sf.read(io.BytesIO(wav_data))
            if audio_array.ndim > 1:
                audio_array = audio_array.mean(axis=1)
            audio_float = audio_array.astype(np.float32)

            segments, _ = model.transcribe(audio_float, language=None)
            return " ".join(s.text for s in segments).strip()
        except Exception as e:
            log.warning(f"Whisper transcription error: {e}")
            return ""

    def _sr_transcribe(self, audio, recognizer) -> str:
        import speech_recognition as sr
        try:
            return recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            log.warning(f"SR request error: {e}")
            return ""

    def _setup_ptt_shortcut(self, orchestrator):
        """Set up Ctrl+Space as push-to-talk in background thread."""
        try:
            import keyboard
            log.info(f"PTT shortcut: {PTT_SHORTCUT}")
            keyboard.add_hotkey(
                PTT_SHORTCUT,
                lambda: asyncio.run_coroutine_threadsafe(
                    self._ptt_activate(orchestrator),
                    asyncio.get_event_loop(),
                ),
            )
            keyboard.wait()
        except Exception as e:
            log.warning(f"PTT setup failed: {e}")

    async def _ptt_activate(self, orchestrator):
        """Push-to-talk activation handler."""
        log.info("PTT activated — listening...")
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
        with mic as source:
            audio = await asyncio.to_thread(
                recognizer.listen, source, phrase_time_limit=MAX_LISTEN
            )
        text = await self._transcribe(audio)
        if text:
            await orchestrator.handle(text)

    async def _keyboard_loop(self, orchestrator):
        """Text input fallback when no microphone available."""
        print("\n\033[33m[YAHAVIS] Keyboard mode — type commands and press Enter.\033[0m")
        print("\033[33m[YAHAVIS] Type 'quit' or 'exit' to stop.\033[0m\n")
        while self._active:
            try:
                text = await asyncio.to_thread(input, "\033[36mYou> \033[0m")
                if text.lower() in ("quit", "exit", "stop"):
                    self._active = False
                    break
                if text.strip():
                    await orchestrator.handle(text.strip())
            except (EOFError, KeyboardInterrupt):
                self._active = False

    def stop(self):
        self._active = False
