'use client'

import { useState, useEffect } from 'react'
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

const SIDEBAR_COLLAPSED_KEY = 'sidebar-collapsed'

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const [mounted, setMounted] = useState(false)
  const pathname = usePathname()

  useEffect(() => {
    // Read from localStorage and sync with CSS class
    const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
    const isCollapsed = stored === 'true'
    setCollapsed(isCollapsed)
    document.documentElement.classList.toggle('sidebar-collapsed', isCollapsed)
    setMounted(true)
  }, [])

  const toggleCollapsed = () => {
    const newValue = !collapsed
    setCollapsed(newValue)
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(newValue))
    document.documentElement.classList.toggle('sidebar-collapsed', newValue)
  }

  // Use CSS variable for width (set by inline script), React state only for content
  return (
    <>
      <aside
        className="fixed top-0 left-0 flex flex-col h-screen bg-[var(--card)] border-r border-[var(--border)] z-10 w-[var(--sidebar-width)] transition-[width] duration-300"
      >
      <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
        <span className={clsx('text-lg font-semibold tracking-tight overflow-hidden whitespace-nowrap', collapsed && mounted ? 'w-0' : 'w-auto')}>
          Corvin
        </span>
        <button
          onClick={toggleCollapsed}
          className="p-1.5 rounded-md hover:bg-[var(--card-hover)] text-[var(--prose-color)] hover:text-[var(--foreground)] transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed && mounted ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
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
                'flex items-center gap-3 px-3 py-2 rounded-md transition-colors overflow-hidden',
                isActive
                  ? 'bg-[var(--accent)] text-white'
                  : 'text-[var(--prose-color)] hover:bg-[var(--card-hover)] hover:text-[var(--foreground)]'
              )}
              title={collapsed && mounted ? label : undefined}
            >
              <Icon size={20} className="shrink-0" />
              <span className={clsx('text-sm whitespace-nowrap', collapsed && mounted ? 'w-0 opacity-0' : 'w-auto opacity-100')}>{label}</span>
            </Link>
          )
        })}
      </nav>

      <div className="p-4 border-t border-[var(--border)] overflow-hidden">
        <p className={clsx('text-xs text-[var(--prose-color)] whitespace-nowrap', collapsed && mounted ? 'opacity-0' : 'opacity-100')}>v{packageJson.version}</p>
      </div>
      </aside>
      {/* Spacer to push content */}
      <div className="shrink-0 w-[var(--sidebar-width)] transition-[width] duration-300" />
    </>
  )
}
