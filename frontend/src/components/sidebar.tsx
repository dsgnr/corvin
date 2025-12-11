'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { clsx } from 'clsx'
import {
  LayoutDashboard,
  ListVideo,
  Settings,
  History,
  ChevronLeft,
  ChevronRight,
  Download,
  FolderCog,
} from 'lucide-react'
import packageJson from '../../package.json'

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/lists', label: 'Lists', icon: ListVideo },
  { href: '/downloads', label: 'Downloads', icon: Download },
  { href: '/profiles', label: 'Profiles', icon: FolderCog },
  { href: '/history', label: 'History', icon: History },
  { href: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const pathname = usePathname()

  return (
    <aside
      className={clsx(
        'flex flex-col h-screen bg-[var(--card)] border-r border-[var(--border)] transition-all duration-300',
        collapsed ? 'w-16' : 'w-56'
      )}
    >
      <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
        {!collapsed && (
          <span className="text-lg font-semibold tracking-tight">Corvin</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--prose-color)] hover:text-[var(--foreground)] transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <nav className="flex-1 p-2 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded-md transition-colors',
                isActive
                  ? 'bg-[var(--accent)] text-white'
                  : 'text-[var(--prose-color)] hover:bg-[var(--card-hover)] hover:text-[var(--foreground)]'
              )}
              title={collapsed ? label : undefined}
            >
              <Icon size={20} />
              {!collapsed && <span className="text-sm">{label}</span>}
            </Link>
          )
        })}
      </nav>

      <div className="p-4 border-t border-[var(--border)]">
        {!collapsed && (
          <p className="text-xs text-[var(--prose-color)]">v{packageJson.version}</p>
        )}
      </div>
    </aside>
  )
}
