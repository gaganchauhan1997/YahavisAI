# YAHAVIS — Yahavi AI System

```
 ██╗   ██╗ █████╗ ██╗  ██╗ █████╗ ██╗   ██╗██╗███████╗
  ╚██╗ ██╔╝██╔══██╗██║  ██║██╔══██╗██║   ██║██║██╔════╝
   ╚████╔╝ ███████║███████║███████║██║   ██║██║███████╗
    ╚██╔╝  ██╔══██║██╔══██║██╔══██║╚██╗ ██╔╝██║╚════██║
     ██║   ██║  ██║██║  ██║██║  ██║ ╚████╔╝ ██║███████║
     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
```

**Yahavi AI System v1.0** · Built by [Hackknow](https://hackknow.com) · Operator: Myth

> *"Free intelligence, infinite capability."*

A fully local, 100% free JARVIS-style AI assistant for Windows 10/11.
Voice-controlled. Computer-controlling. Hackknow-integrated.

---

## Features

| Capability         | Technology                                    |
|--------------------|-----------------------------------------------|
| 🧠 LLM Brain       | Ollama (local) → Groq → Gemini (free fallback)|
| 🎤 Voice Input     | Faster-Whisper (local) + SpeechRecognition    |
| 🔊 Voice Output    | edge-tts (Microsoft Neural) + pyttsx3         |
| 🖱️ Computer Control| pyautogui + pynput + pygetwindow              |
| 📁 File Ops        | Python os, shutil, pathlib                    |
| 🌐 Browser Auto    | Playwright (async, Chromium)                  |
| 👁️ Screen Vision   | PIL + pytesseract + Ollama llava              |
| 🏪 Hackknow Ops    | WooCommerce REST API                          |
| 🔍 Web Search      | DuckDuckGo (no API key needed)                |
| 💻 UI Dashboard    | FastAPI + WebSocket + Neon HUD                |

---

## Quick Start

### 1. Prerequisites
- Python 3.10+
- Windows 10/11 (16GB RAM recommended)
- [Ollama](https://ollama.ai) installed and running locally
- Git

### 2. Install Ollama + pull model
```bash
# Download from https://ollama.ai and install
ollama pull mistral
```

### 3. Clone and install
```bash
git clone https://github.com/gaganchauhan1997/YahavisAI.git
cd YahavisAI
pip install -r requirements.txt
python -m playwright install chromium
```

### 4. Configure
```bash
cp .env.example .env
# Edit .env — add Groq/Gemini keys (optional, free tier)
```

### 5. Run
```bash
python main.py
```

YAHAVIS boots, opens the HUD at **http://localhost:7070**, and listens for **"Hey Yahavi"**.

---

## Voice Commands

Say **"Hey Yahavi"** followed by any of these (Hindi/English mix works):

```
"Hey Yahavi, open VS Code"
"Hey Yahavi, screenshot le aur bata screen pe kya hai"
"Hey Yahavi, Chrome mein hackknow.com khol"
"Hey Yahavi, Downloads mein saari PDFs dhundh"
"Hey Yahavi, volume 50 percent kar"
"Hey Yahavi, ek React login form likh"
"Hey Yahavi, Hackknow ke new orders check kar"
"Hey Yahavi, 10 minute baad shutdown kar"
"Hey Yahavi, latest cybersecurity news search kar"
```

**Push-to-talk:** `Ctrl+Space`  
**Text mode:** Type in the dashboard input box

---

## Project Structure

```
YahavisAI/
├── main.py                    # Entry point — boot + async loop
├── yahavis.config.json        # All runtime settings
├── .env.example               # API keys template
├── requirements.txt           # All Python dependencies
│
├── core/
│   ├── brain.py               # LLM orchestration + streaming
│   ├── intent_parser.py       # NLU: voice → structured intent
│   ├── task_orchestrator.py   # Priority queue + parallel exec
│   └── api_router.py          # 8-provider rotation + fallback
│
├── voice/
│   ├── listener.py            # Mic input + hotword detection
│   ├── speaker.py             # edge-tts + pyttsx3 TTS
│   └── wakeword.py            # Porcupine / energy-based
│
├── computer/
│   ├── mouse_keyboard.py      # pyautogui controls
│   ├── file_ops.py            # File system operations
│   ├── app_manager.py         # Open/close/switch apps
│   ├── browser_control.py     # Playwright browser automation
│   ├── system_ops.py          # Volume, brightness, screenshot
│   └── screen_reader.py       # Screenshot + OCR + vision LLM
│
├── skills/
│   ├── hackknow_ops.py        # WooCommerce + site health
│   ├── web_search.py          # DuckDuckGo free search
│   ├── code_writer.py         # Generate + save + open code
│   ├── content_engine.py      # Title → full content package
│   └── scheduler.py           # Reminders + cron tasks
│
├── ui/
│   ├── index.html             # JARVIS HUD dashboard
│   ├── style.css              # Neon terminal CSS
│   ├── app.js                 # Live WebSocket UI
│   └── server.py              # FastAPI + WebSocket server
│
├── memory/
│   ├── short_term.py          # Session context (rolling)
│   └── long_term.py           # JSON persistent memory
│
└── prompts/
    ├── system_prompt.txt      # YAHAVIS personality
    ├── intent_prompts.py      # Per-intent prompt templates
    └── hackknow_context.txt   # Hackknow platform knowledge
```

---

## API Key Setup (All Free)

| Provider   | Get Key                          | Limit/Day  |
|------------|----------------------------------|------------|
| Groq       | console.groq.com (instant)       | 14,400 req |
| Gemini     | aistudio.google.com              | 1,500 req  |
| Porcupine  | picovoice.io (wake word, free)   | Always free|
| Ollama     | Local — no key needed            | Unlimited  |

---

## Hackknow Integration

Add WooCommerce credentials to `.env`:
```
WC_SITE_URL=https://shop.hackknow.com
WC_CONSUMER_KEY=ck_xxxx
WC_CONSUMER_SECRET=cs_xxxx
```

Then say:
```
"Hey Yahavi, check orders"
"Hey Yahavi, add product 'Nmap Script Pack' at 299 rupees"
"Hey Yahavi, write description for Python Hacking Bundle"
```

---

## Built By
**Myth** · Founder, Hackknow  
Email: ceo.hackknow@gmail.com  
Site: [hackknow.com](https://hackknow.com)

*YAHAVIS — Free intelligence, infinite capability.*
