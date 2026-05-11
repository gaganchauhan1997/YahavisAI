'use client'

import { useState, useEffect, useRef } from 'react'
import { Mic, Send, Settings, Command, Activity, Smartphone, Monitor } from 'lucide-react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  actions?: any[]
}

interface Device {
  id: string
  type: 'desktop' | 'mobile'
  name: string
  status: 'online' | 'offline'
  lastSeen: Date
}

export default function Dashboard() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [devices, setDevices] = useState<Device[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // WebSocket connection
  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws'
    const ws = new WebSocket(`${wsUrl}/agent?user_id=demo&device_id=browser`)
    
    ws.onopen = () => {
      setIsConnected(true)
      console.log('Connected to YahavisAI')
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      handleWebSocketMessage(data)
    }
    
    ws.onclose = () => {
      setIsConnected(false)
      console.log('Disconnected from YahavisAI')
    }
    
    wsRef.current = ws
    
    return () => ws.close()
  }, [])

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'ai_response':
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: data.message,
          timestamp: new Date()
        }])
        break
      case 'device_list':
        setDevices(data.devices || [])
        break
      case 'actions_queued':
        // Show action status
        break
    }
  }

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current) return
    
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date()
    }
    
    setMessages(prev => [...prev, userMessage])
    
    wsRef.current.send(JSON.stringify({
      type: 'user_input',
      message: input,
      conversation_id: 'demo-chat'
    }))
    
    setInput('')
  }

  const toggleVoice = () => {
    setIsRecording(!isRecording)
    // Voice recognition logic here
  }

  return (
    <div className="min-h-screen bg-dark-900 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-dark-800 border-r border-dark-600 p-4 hidden md:block">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-full bg-primary-500 flex items-center justify-center glow-primary">
            <Command className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg">YahavisAI</h1>
            <p className="text-xs text-gray-400">AI Operating System</p>
          </div>
        </div>

        <nav className="space-y-2">
          <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg bg-primary-500/20 text-primary-400">
            <Activity className="w-5 h-5" />
            <span>Dashboard</span>
          </a>
          <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-dark-700 text-gray-300">
            <Command className="w-5 h-5" />
            <span>Automations</span>
          </a>
          <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-dark-700 text-gray-300">
            <Settings className="w-5 h-5" />
            <span>Settings</span>
          </a>
        </nav>

        {/* Devices */}
        <div className="mt-8">
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Connected Devices</h3>
          <div className="space-y-2">
            {devices.map(device => (
              <div key={device.id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-dark-700">
                {device.type === 'desktop' ? <Monitor className="w-4 h-4" /> : <Smartphone className="w-4 h-4" />}
                <span className="text-sm">{device.name}</span>
                <span className={`w-2 h-2 rounded-full ${device.status === 'online' ? 'bg-green-500' : 'bg-gray-500'}`} />
              </div>
            ))}
            {devices.length === 0 && (
              <p className="text-xs text-gray-500 px-3">No devices connected</p>
            )}
          </div>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-16 border-b border-dark-600 flex items-center justify-between px-4 glass">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <div className="flex items-center gap-4">
            <button className="p-2 rounded-lg hover:bg-dark-700">
              <Settings className="w-5 h-5 text-gray-400" />
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-20">
              <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-primary-500/20 flex items-center justify-center glow-primary">
                <Command className="w-10 h-10 text-primary-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Welcome to YahavisAI</h2>
              <p className="text-gray-400 max-w-md mx-auto">
                Your AI Operating System. I can help you with WhatsApp, Instagram, 
                browser automation, and desktop control. Try asking in Hindi or English.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {["Rahul ko message bhejo", "Chrome open karo", "Volume badhao"].map((cmd) => (
                  <button
                    key={cmd}
                    onClick={() => { setInput(cmd); }}
                    className="px-4 py-2 rounded-full bg-dark-700 hover:bg-dark-600 text-sm"
                  >
                    {cmd}
                  </button>
                ))}
              </div>
            </div>
          )}
          
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
            >
              <div
                className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                  msg.role === 'user'
                    ? 'bg-primary-500 text-white rounded-br-md'
                    : 'bg-dark-700 text-gray-100 rounded-bl-md'
                }`}
              >
                <p className="text-sm">{msg.content}</p>
                <span className="text-xs opacity-50 mt-1 block">
                  {msg.timestamp.toLocaleTimeString()}
                </span>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-dark-600">
          <div className="flex items-center gap-2 glass rounded-2xl p-2">
            <button
              onClick={toggleVoice}
              className={`p-3 rounded-xl transition-all ${
                isRecording 
                  ? 'bg-red-500/20 text-red-400 animate-pulse' 
                  : 'hover:bg-dark-700 text-gray-400'
              }`}
            >
              <Mic className="w-5 h-5" />
            </button>
            
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Type in Hindi or English..."
              className="flex-1 bg-transparent outline-none text-white placeholder-gray-500"
            />
            
            <button
              onClick={sendMessage}
              disabled={!input.trim()}
              className="p-3 bg-primary-500 rounded-xl hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-5 h-5 text-white" />
            </button>
          </div>
          <p className="text-xs text-gray-500 text-center mt-2">
            Press Enter to send • Click mic for voice input
          </p>
        </div>
      </main>
    </div>
  )
}
