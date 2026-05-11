# YahavisAI - Complete Project Structure

```
YahavisAI/
├── 📁 frontend/                    # Next.js 15 Dashboard
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── (dashboard)/
│   │   │   ├── chat/
│   │   │   ├── workflows/
│   │   │   ├── automations/
│   │   │   ├── analytics/
│   │   │   └── settings/
│   │   ├── api/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── ui/                    # Shadcn components
│   │   ├── chat/
│   │   ├── voice/
│   │   ├── workflow/
│   │   └── layout/
│   ├── hooks/
│   ├── lib/
│   ├── store/                     # Zustand state
│   ├── types/
│   └── styles/
│
├── 📁 backend/                     # YahavisAI Backend
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── routes/
│   │   │   │   │   ├── auth.py
│   │   │   │   │   ├── chat.py
│   │   │   │   │   ├── tasks.py
│   │   │   │   │   ├── workflows.py
│   │   │   │   │   ├── automations.py
│   │   │   │   │   └── devices.py
│   │   │   │   └── deps.py
│   │   │   └── websocket/
│   │   │       └── agent_socket.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── services/
│   │   │   ├── ai/
│   │   │   │   ├── gemini_service.py
│   │   │   │   ├── whisper_service.py
│   │   │   │   └── orchestrator.py
│   │   │   ├── memory/
│   │   │   │   ├── conversation_memory.py
│   │   │   │   └── long_term_memory.py
│   │   │   ├── queue/
│   │   │   │   └── task_queue.py
│   │   │   └── automation/
│   │   │       ├── action_parser.py
│   │   │       └── workflow_engine.py
│   │   ├── models/
│   │   └── db/
│   │       └── supabase_client.py
│   ├── tests/
│   ├── alembic/
│   └── main.py
│
├── 📁 desktop-agent/               # Windows Desktop Agent
│   ├── src/
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── core.py
│   │   │   └── config.py
│   │   ├── automations/
│   │   │   ├── browser/
│   │   │   │   ├── playwright_controller.py
│   │   │   │   ├── instagram_automation.py
│   │   │   │   └── whatsapp_web.py
│   │   │   ├── desktop/
│   │   │   │   ├── pyautogui_controller.py
│   │   │   │   ├── keyboard_mouse.py
│   │   │   │   └── window_manager.py
│   │   │   └── system/
│   │   │       ├── file_manager.py
│   │   │       └── app_launcher.py
│   │   ├── websocket/
│   │   │   └── client.py
│   │   ├── voice/
│   │   │   └── listener.py
│   │   └── utils/
│   ├── requirements.txt
│   └── main.py
│
├── 📁 mobile-app/                  # Flutter Android App
│   ├── lib/
│   │   ├── main.dart
│   │   ├── app.dart
│   │   ├── core/
│   │   │   ├── constants/
│   │   │   ├── theme/
│   │   │   └── utils/
│   │   ├── data/
│   │   │   ├── models/
│   │   │   ├── repositories/
│   │   │   └── services/
│   │   ├── presentation/
│   │   │   ├── screens/
│   │   │   ├── widgets/
│   │   │   └── blocs/
│   │   └── services/
│   │       ├── accessibility/
│   │       │   └── automation_service.dart
│   │       ├── voice/
│   │       │   └── speech_service.dart
│   │       └── websocket/
│   │           └── socket_client.dart
│   ├── android/
│   │   └── app/
│   │       └── src/
│   │           └── main/
│   │               └── java/
│   │                   └── accessibility/
│   │                       └── JarvisAccessibilityService.java
│   └── pubspec.yaml
│
├── 📁 n8n-workflows/               # n8n Automation Templates
│   ├── whatsapp/
│   ├── instagram/
│   ├── email/
│   └── system/
│
├── 📁 shared/                      # Shared Types & Constants
│   ├── types/
│   │   ├── actions.ts
│   │   ├── messages.ts
│   │   └── devices.ts
│   └── constants/
│       └── commands.ts
│
├── 📁 infrastructure/              # Docker & Deployment
│   ├── docker/
│   │   ├── frontend.Dockerfile
│   │   ├── backend.Dockerfile
│   │   ├── agent.Dockerfile
│   │   └── docker-compose.yml
│   ├── kubernetes/
│   ├── terraform/
│   └── scripts/
│       ├── deploy.sh
│       └── setup.sh
│
├── 📁 docs/                        # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── AUTOMATION.md
│   ├── DEPLOYMENT.md
│   └── SETUP.md
│
└── 📁 database/
    ├── schema/
    │   ├── 001_initial.sql
    │   └── 002_automations.sql
    └── migrations/

```

## 🎯 Core System Components

### 1. Frontend (Next.js 15)
- **Route Groups**: Auth + Dashboard separation
- **Real-time Chat**: WebSocket integration
- **Voice Interface**: Web Speech API + Whisper
- **Workflow Designer**: Visual automation builder
- **Device Management**: Monitor connected agents

### 2. Backend (FastAPI)
- **AI Orchestrator**: Gemini 2.5 integration
- **Memory System**: Conversation + long-term memory
- **Task Queue**: Redis-based job queue
- **WebSocket Hub**: Real-time communication
- **Action Parser**: JSON → executable commands

### 3. Desktop Agent (Python)
- **WebSocket Client**: Maintains connection to cloud
- **Browser Controller**: Playwright-based automation
- **Desktop Controller**: PyAutoGUI for OS-level control
- **Voice Listener**: Local wake word detection
- **System Integration**: File/app management

### 4. Mobile App (Flutter)
- **Floating Bubble**: Overlay assistant UI
- **Accessibility Service**: Android automation
- **Voice Recognition**: On-device + cloud hybrid
- **Real-time Sync**: WebSocket connection
- **Push Notifications**: FCM integration

### 5. Automation Engine
- **n8n Integration**: Workflow execution
- **Action Parser**: Validates and routes actions
- **Retry System**: Exponential backoff
- **Logging**: Complete audit trail
- **Safety Guards**: Confirmation for destructive actions

## 🔐 Security Architecture

- JWT tokens with refresh mechanism
- End-to-end encryption for sensitive automations
- Rate limiting on all APIs
- RBAC (Role-Based Access Control)
- Environment variable isolation
- Secure WebSocket with auth

## 📡 Communication Flow

```
┌─────────────┐     WebSocket      ┌──────────────┐
│  Mobile App │◄───────────────────►│   Backend    │
└─────────────┘                    │   (FastAPI)  │
                                  └──────┬───────┘
┌─────────────┐     WebSocket         │
│    Web UI   │◄───────────────────────┤
└─────────────┘                        │
                                       │ REST API
┌─────────────┐     WebSocket         │
│Desktop Agent│◄───────────────────────┘
└─────────────┘
```
