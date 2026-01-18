import type { Metadata } from 'next'
import { Sidebar } from '@/components/Sidebar'
import { ProgressProvider } from '@/lib/ProgressContext'
import './globals.css'

export const metadata: Metadata = {
  title: 'Corvin',
  description: 'Video download manager',
}

const sidebarScript = `
(function() {
  try {
    var collapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    if (collapsed) {
      document.documentElement.classList.add('sidebar-collapsed');
    }
  } catch (e) {}
})();
`

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: sidebarScript }} />
      </head>
      <body className="antialiased">
        <ProgressProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
        </ProgressProvider>
      </body>
    </html>
  )
}
