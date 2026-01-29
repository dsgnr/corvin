'use client'

import { useState, useEffect, useSyncExternalStore } from 'react'
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
  ListTodo,
  FolderCog,
  Menu,
  X,
  Github,
} from 'lucide-react'
import packageJson from '../../package.json'

const SIDEBAR_COLLAPSED_KEY = 'sidebar-collapsed'

/** Navigation items for the sidebar menu */
const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/lists', label: 'Lists', icon: ListVideo },
  { href: '/tasks', label: 'Tasks', icon: ListTodo },
  { href: '/profiles', label: 'Profiles', icon: FolderCog },
  { href: '/history', label: 'History', icon: History },
  { href: '/settings', label: 'Settings', icon: Settings },
]

// Subscribe function for useSyncExternalStore (no-op since we just need the snapshot)
const subscribe = () => () => {}
const getSnapshot = () => true
const getServerSnapshot = () => false

/**
 * Main navigation sidebar component.
 * Supports collapsing to save space, with state persisted to localStorage.
 * On mobile, shows a hamburger menu that opens a full-width sidebar overlay.
 */
export function Sidebar() {
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
    }
    return false
  })
  const [mobileOpen, setMobileOpen] = useState(false)
  // Use useSyncExternalStore to safely detect client-side rendering
  const mounted = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
  const pathname = usePathname()

  // Sync collapsed state to DOM
  useEffect(() => {
    document.documentElement.classList.toggle('sidebar-collapsed', collapsed)
  }, [collapsed])

  // Sync mobile open state to DOM and prevent body scroll
  useEffect(() => {
    document.documentElement.classList.toggle('sidebar-mobile-open', mobileOpen)
    if (mobileOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [mobileOpen])

  // Close mobile sidebar on route change
  // Using flushSync would work but is overkill - instead we close on link click
  const closeMobileSidebar = () => setMobileOpen(false)

  // Close mobile sidebar on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false)
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [])

  const toggleCollapsed = () => {
    const newValue = !collapsed
    setCollapsed(newValue)
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(newValue))
    document.documentElement.classList.toggle('sidebar-collapsed', newValue)
  }

  return (
    <>
      {/* Mobile header bar - fixed at top */}
      <header className="fixed top-0 right-0 left-0 z-50 flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--card)] px-4 md:hidden">
        <button
          onClick={() => setMobileOpen(true)}
          className="rounded-md p-2 text-[var(--foreground)] transition-colors hover:bg-[var(--card-hover)]"
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Corvin
        </Link>
        <div className="w-9" /> {/* Spacer for centering */}
      </header>

      {/* Mobile overlay */}
      <div
        className={clsx(
          'fixed inset-0 z-50 bg-black/50 transition-opacity md:hidden',
          mobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        )}
        onClick={() => setMobileOpen(false)}
      />

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed top-0 left-0 z-50 flex h-screen flex-col border-r border-[var(--border)] bg-[var(--card)] transition-transform duration-300 md:z-10 md:transition-[width]',
          // Desktop: use CSS variable width, always visible
          'md:w-[var(--sidebar-width)] md:translate-x-0',
          // Mobile: fixed width, slide in/out
          'w-64',
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] p-4">
          <Link
            href="/"
            onClick={closeMobileSidebar}
            className={clsx(
              'overflow-hidden text-lg font-bold tracking-tight whitespace-nowrap transition-all',
              collapsed && mounted ? 'md:w-0 md:opacity-0' : 'w-auto opacity-100'
            )}
          >
            Corvin
          </Link>
          {/* Mobile close button */}
          <button
            onClick={() => setMobileOpen(false)}
            className="btn-ghost rounded-md p-1.5 md:hidden"
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
          {/* Desktop collapse button */}
          <button
            onClick={toggleCollapsed}
            className="btn-ghost hidden rounded-md p-1.5 md:block"
            aria-label={collapsed && mounted ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed && mounted ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
          {navItems.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href || (href !== '/' && pathname.startsWith(href))
            return (
              <Link
                key={href}
                href={href}
                onClick={closeMobileSidebar}
                className={clsx(
                  'flex items-center gap-3 overflow-hidden rounded-lg px-3 py-2.5 transition-all duration-150',
                  isActive
                    ? 'bg-[var(--accent)] text-white shadow-sm'
                    : 'text-[var(--muted)] hover:bg-[var(--card-hover)] hover:text-[var(--foreground)]'
                )}
                title={collapsed && mounted ? label : undefined}
              >
                <Icon size={20} className="shrink-0" />
                <span
                  className={clsx(
                    'text-sm font-medium whitespace-nowrap transition-all',
                    collapsed && mounted ? 'md:w-0 md:opacity-0' : 'w-auto opacity-100'
                  )}
                >
                  {label}
                </span>
              </Link>
            )
          })}
        </nav>

        <div className="flex items-center justify-between overflow-hidden border-t border-[var(--border)] p-4">
          <p
            className={clsx(
              'text-xs font-medium whitespace-nowrap text-[var(--muted-foreground)] transition-opacity',
              collapsed && mounted ? 'md:opacity-0' : 'opacity-100'
            )}
          >
            v{packageJson.version}
          </p>
          <a
            href="https://github.com/dsgnr/corvin"
            target="_blank"
            rel="noopener noreferrer"
            className={clsx(
              'text-[var(--muted-foreground)] transition-all hover:text-[var(--foreground)]',
              collapsed && mounted ? 'md:opacity-0' : 'opacity-100'
            )}
            title="View on GitHub"
          >
            <Github size={16} />
          </a>
        </div>
      </aside>

      {/* Desktop spacer to push main content */}
      <div className="hidden w-[var(--sidebar-width)] shrink-0 transition-[width] duration-300 md:block" />
    </>
  )
}
