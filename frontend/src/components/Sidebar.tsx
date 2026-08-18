import { useEffect, useRef, useState } from 'react';
import {
  LayoutDashboard, Target, ChartBar as BarChart2, Star, MessageSquareHeart,
  ChevronRight, Database, LogOut,
} from 'lucide-react';
import type { PageKey } from '../types';

interface NavItem {
  key: PageKey;
  label: string;
  icon: React.ElementType;
  description: string;
}

const navItems: NavItem[] = [
  { key: 'dashboard', label: 'Dashboard',            icon: LayoutDashboard,    description: 'Overview & KPIs'           },
  { key: 'ingestion', label: 'Data Ingestion',        icon: Database,           description: 'Upload BSC, JD & LOS'      },
  { key: 'planning',  label: 'Performance Planning',  icon: Target,             description: 'Set & generate objectives'  },
  { key: 'director_planning', label: 'Performance Planning', icon: Target,     description: 'Set & generate objectives'  },
  { key: 'director_review', label: 'Director Review', icon: Target,             description: 'Approve or reject sets'     },
  { key: 'vp_review',       label: 'Review Performance Plan', icon: Star,       description: 'Division approval queue'    },
  { key: 'pms_register',    label: 'PMS Register',    icon: BarChart2,          description: 'Final approved record'      },
  { key: 'tracking',  label: 'Data Tracking',         icon: BarChart2,          description: 'Monitor progress'           },
  { key: 'appraisal', label: 'Performance Appraisal', icon: Star,               description: 'Reviews & ratings'          },
  { key: 'feedback',  label: 'Feedback & Coaching',   icon: MessageSquareHeart, description: 'Development & growth'       },
];

interface SidebarProps {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
  onLogout: () => void;
  me: { name: string; email: string; roles: string[] };
}

export default function Sidebar({ activePage, onNavigate, onLogout, me }: SidebarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const brandTitleRef = useRef<HTMLParagraphElement>(null);
  const brandSubtitleRef = useRef<HTMLParagraphElement>(null);
  const [titleShift, setTitleShift] = useState(0);
  const [subtitleShift, setSubtitleShift] = useState(0);
  const role = me.roles[0] || 'user';

  useEffect(() => {
    function measure(el: HTMLParagraphElement | null, setShift: (v: number) => void) {
      if (!el?.parentElement) return;
      const overflow = el.scrollWidth - el.parentElement.clientWidth;
      setShift(overflow > 2 ? overflow : 0);
    }
    function check() {
      measure(brandTitleRef.current, setTitleShift);
      measure(brandSubtitleRef.current, setSubtitleShift);
    }
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);
  const filteredNavItems = navItems.filter((item) => {
    if (role === 'manager') return ['dashboard', 'planning'].includes(item.key);
    if (role === 'unit_director') return ['dashboard', 'director_planning', 'director_review'].includes(item.key);
    if (role === 'vp') return ['dashboard', 'vp_review'].includes(item.key);
    if (role === 'pms') return ['dashboard', 'ingestion', 'pms_register'].includes(item.key);
    if (role === 'hr_director') return ['dashboard', 'director_review', 'vp_review', 'pms_register'].includes(item.key);
    return ['dashboard'].includes(item.key);
  });
  return (
    <aside className="w-72 min-h-screen flex flex-col flex-shrink-0" style={{ backgroundColor: '#5a1d5e' }}>

      {/* Brand */}
      <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
        <div className="flex items-center gap-3">
          <img
            src="/cbe-logo.svg"
            alt="Commercial Bank of Ethiopia"
            className="w-11 h-11 object-contain flex-shrink-0"
          />
          <div className="min-w-0 overflow-hidden">
            <div className="overflow-hidden">
              <p
                ref={brandTitleRef}
                className={`text-white font-bold text-sm leading-tight tracking-wide whitespace-nowrap ${titleShift ? 'brand-slide' : ''}`}
                style={titleShift ? { ['--brand-shift' as string]: `-${titleShift}px` } : undefined}
              >
                Commercial Bank of Ethiopia
              </p>
            </div>
            <div className="overflow-hidden mt-0.5">
              <p
                ref={brandSubtitleRef}
                className={`text-xs leading-snug whitespace-nowrap ${subtitleShift ? 'brand-slide' : ''}`}
                style={{
                  color: 'rgba(255,255,255,0.5)',
                  ...(subtitleShift ? { ['--brand-shift' as string]: `-${subtitleShift}px` } : {}),
                }}
              >
                AI Powered Performance Management System
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <p className="px-3 mb-3 text-xs font-semibold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.35)' }}>
          Main Menu
        </p>
        {filteredNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onNavigate(item.key)}
              className="w-full text-left flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 cursor-pointer group"
              style={
                isActive
                  ? { backgroundColor: '#892d8f', color: '#fff' }
                  : { color: 'rgba(255,255,255,0.6)' }
              }
              onMouseEnter={(e) => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(255,255,255,0.08)';
              }}
              onMouseLeave={(e) => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
              }}
            >
              <Icon
                size={18}
                style={{ color: isActive ? '#fff' : 'rgba(255,255,255,0.5)' }}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium leading-snug" style={{ color: isActive ? '#fff' : 'rgba(255,255,255,0.75)' }}>
                  {item.label}
                </p>
                <p className="text-xs truncate" style={{ color: isActive ? 'rgba(255,255,255,0.65)' : 'rgba(255,255,255,0.35)' }}>
                  {item.description}
                </p>
              </div>
              {isActive && <ChevronRight size={14} style={{ color: 'rgba(255,255,255,0.6)', flexShrink: 0 }} />}
            </button>
          );
        })}
      </nav>

      {/* User menu */}
      <div className="px-4 py-4 relative" style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }} ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen(open => !open)}
          className="w-full flex items-center gap-3 px-2 py-2 rounded-xl transition-colors cursor-pointer text-left"
          style={{ backgroundColor: menuOpen ? 'rgba(255,255,255,0.1)' : 'transparent' }}
          onMouseEnter={(e) => {
            if (!menuOpen) (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(255,255,255,0.08)';
          }}
          onMouseLeave={(e) => {
            if (!menuOpen) (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
          }}
          aria-expanded={menuOpen}
          aria-haspopup="menu"
        >
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #892d8f, #6e2473)' }}
          >
            {(me.name?.match(/[A-Za-z]/)?.[0] || 'U').toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-xs font-semibold truncate">{me.name}</p>
            <p className="text-xs truncate" style={{ color: 'rgba(255,255,255,0.4)' }}>{me.email}</p>
          </div>
          <ChevronRight
            size={14}
            style={{
              color: 'rgba(255,255,255,0.5)',
              flexShrink: 0,
              transform: menuOpen ? 'rotate(90deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s',
            }}
          />
        </button>

        {menuOpen && (
          <div
            className="absolute bottom-full left-4 right-4 mb-2 rounded-xl overflow-hidden shadow-lg"
            style={{ backgroundColor: '#4a1850', border: '1px solid rgba(255,255,255,0.12)' }}
            role="menu"
          >
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                onLogout();
              }}
              className="w-full flex items-center gap-2.5 px-4 py-3 text-sm text-left transition-colors"
              style={{ color: 'rgba(255,255,255,0.85)' }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(255,255,255,0.08)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
              }}
            >
              <LogOut size={16} style={{ color: 'rgba(255,255,255,0.6)' }} />
              Sign out
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
