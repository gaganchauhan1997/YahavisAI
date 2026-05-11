import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'YahavisAI - AI Operating System',
  description: 'Voice-controlled AI assistant with cross-platform automation',
  viewport: 'width=device-width, initial-scale=1'
}

export default function RootLayout({
  children
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-dark-900 text-white min-h-screen">
        {children}
      </body>
    </html>
  )
}
