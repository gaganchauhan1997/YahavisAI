# 🤖 YahavisAI - AI Operating System

[![GitHub Stars](https://img.shields.io/github/stars/gaganchauhan1997/YahavisAI?style=social)](https://github.com/gaganchauhan1997/YahavisAI)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Node](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org)

> **Yahavis-inspired AI Operating System with cross-platform automation**

YahavisAI is a production-ready AI assistant that works across **Web**, **Android**, and **Windows Desktop**. Inspired by Iron Man's Yahavis, it provides voice-controlled automation, workflow orchestration, and intelligent task management.

## ✨ Features

### 🎯 Core Capabilities
- **Voice Commands** - Hindi + English speech recognition
- **AI Orchestration** - Gemini 2.5 powered intent understanding
- **Cross-Device Sync** - Real-time communication across all devices
- **Workflow Automation** - n8n integration for complex tasks
- **Memory System** - Short & long-term context awareness

### 🌐 Supported Platforms
| Platform | Features |
|----------|----------|
| **Web Dashboard** | Chat UI, workflow designer, device management |
| **Android App** | Floating bubble, accessibility automation, voice |
| **Windows Desktop** | Browser automation, desktop control, file management |

### 🤖 Automation Types
- **Communication**: WhatsApp, Email, SMS
- **Social Media**: Instagram posts, stories, DMs
- **Browser**: Chrome automation, web scraping, searches
- **Desktop**: App control, keyboard/mouse, screenshots
- **System**: File management, volume, brightness, shutdown

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Web UI     │     │ Mobile App  │     │   Desktop   │
│  (Next.js)  │     │  (Flutter)  │     │   Agent     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │ WebSocket
                           ▼
               ┌───────────────────────┐
               │   FastAPI Backend    │
               │  ├─ AI Orchestrator  │
               │  ├─ Task Queue        │
               │  ├─ Memory System     │
               │  └─ n8n Integration   │
               └───────────────────────┘
                           │
               ┌───────────┴───────────┐
               ▼                       ▼
        ┌─────────────┐         ┌─────────────┐
        │  Supabase   │         │    Redis    │
        │  (Auth+DB)  │         │   (Queue)   │
        └─────────────┘         └─────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Flutter 3.0+ (for mobile)
- Redis (for task queue)
- Supabase account

### 1. Clone & Setup

```bash
git clone https://github.com/gaganchauhan1997/YahavisAI.git
cd YahavisAI
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Run server
uvicorn main:app --reload
```

### 3. Frontend Setup

```bash
cd frontend
npm install

# Copy environment
cp .env.example .env.local

# Run dev server
npm run dev
```

### 4. Desktop Agent Setup

```bash
cd desktop-agent
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

python main.py
```

### 5. Mobile App

```bash
cd mobile-app
flutter pub get
flutter run
```

## ⚙️ Environment Variables

Create `.env` files in each project directory:

### Backend (`backend/.env`)
```env
# Required
GEMINI_API_KEY=your_gemini_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SECRET_KEY=your_jwt_secret

# Optional
REDIS_URL=redis://localhost:6379/0
N8N_WEBHOOK_URL=your_n8n_url
```

### Frontend (`frontend/.env.local`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture & design |
| [API.md](docs/API.md) | REST API & WebSocket reference |
| [AUTOMATION.md](docs/AUTOMATION.md) | Creating custom automations |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment guide |

## 🎯 Example Commands

### Voice Commands (Hindi + English)
```
"Rahul ko message bhejo ke meeting 3 baje hai"
"Post my photo on Instagram with AI caption"
"Chrome open karo aur Python tutorials search karo"
"File copy karo Documents se Desktop pe"
"Volume 50% karo"
```

### AI Response Structure
```json
{
  "response_text": "I'm sending message the message to...",
  "confidence": 0.95,
  "actions": [
    {
      "action": "send_whatsapp",
      "params": {"contact": "Rahul", "message": "Meeting 3 baje hai"},
      "device_target": "mobile",
      "requires_confirmation": false
    }
  ]
}
```

## 🔐 Security

- JWT authentication with refresh tokens
- End-to-end encryption for sensitive data
- Rate limiting on all APIs
- Confirmation required for destructive actions
- Secure WebSocket connections

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- Google Gemini API for AI orchestration
- OpenAI Whisper for voice recognition
- n8n for workflow automation
- Supabase for backend infrastructure

---

**⭐ Star this repo if you find it useful!**

Built with ❤️ by [Gagan Chauhan](https://github.com/gaganchauhan1997)
