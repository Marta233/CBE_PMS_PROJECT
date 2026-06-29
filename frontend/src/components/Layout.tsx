import type { ReactNode } from 'react';
import { Bell, Search, Sun, Moon } from 'lucide-react';
import { useTheme } from '../lib/theme';

interface LayoutProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}

export default function Layout({ title, subtitle, actions, children }: LayoutProps) {
  const { theme, toggle } = useTheme();

  return (
    <div className="flex flex-col flex-1 min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* Top bar */}
      <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between sticky top-0 z-10 shadow-sm">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: '#892d8f' }}>{title}</h1>
          {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-2">
          {actions}

          {/* Search */}
          <div className="relative hidden md:block">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search..."
              className="pl-9 pr-4 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-slate-50 dark:bg-slate-700 dark:text-slate-100 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 w-48 transition-colors"
            />
          </div>

          {/* Theme toggle */}
          <button
            onClick={toggle}
            aria-label="Toggle dark mode"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200 border"
            style={
              theme === 'dark'
                ? { backgroundColor: '#1e293b', borderColor: '#334155', color: '#fbbf24' }
                : { backgroundColor: '#f8fafc', borderColor: '#e2e8f0', color: '#64748b' }
            }
          >
            {theme === 'dark' ? (
              <>
                <Sun size={15} />
                <span className="hidden sm:inline">Light</span>
              </>
            ) : (
              <>
                <Moon size={15} />
                <span className="hidden sm:inline">Dark</span>
              </>
            )}
          </button>

          {/* Notifications */}
          <button className="relative p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
            <Bell size={18} className="text-slate-500 dark:text-slate-400" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full" style={{ backgroundColor: '#892d8f' }} />
          </button>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 p-6 animate-fade-in">{children}</main>
    </div>
  );
}
