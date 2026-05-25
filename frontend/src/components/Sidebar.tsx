import { LayoutDashboard, Target, ChartBar as BarChart2, Star, MessageSquareHeart, ChevronRight, Database } from 'lucide-react';
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
  { key: 'tracking',  label: 'Data Tracking',         icon: BarChart2,          description: 'Monitor progress'           },
  { key: 'appraisal', label: 'Performance Appraisal', icon: Star,               description: 'Reviews & ratings'          },
  { key: 'feedback',  label: 'Feedback & Coaching',   icon: MessageSquareHeart, description: 'Development & growth'       },
];

interface SidebarProps {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
}

export default function Sidebar({ activePage, onNavigate }: SidebarProps) {
  return (
    <aside className="w-64 min-h-screen flex flex-col flex-shrink-0" style={{ backgroundColor: '#5a1d5e' }}>

      {/* Brand */}
      <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
        <div className="flex items-center gap-3">
          <img
            src="/cbe-logo.jpg"
            alt="Commercial Bank of Ethiopia"
            className="w-10 h-10 rounded-lg object-contain flex-shrink-0"
            style={{ background: 'rgba(255,255,255,0.08)' }}
          />
          <div className="min-w-0">
            <p className="text-white font-bold text-sm leading-tight tracking-wide truncate">AI Based</p>
            <p className="text-xs truncate" style={{ color: 'rgba(255,255,255,0.45)' }}>CBE PMS Management System</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <p className="px-3 mb-3 text-xs font-semibold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.35)' }}>
          Main Menu
        </p>
        {navItems.map((item) => {
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
                <p className="text-sm font-medium truncate" style={{ color: isActive ? '#fff' : 'rgba(255,255,255,0.75)' }}>
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

      {/* Footer */}
      <div className="px-4 py-4" style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }}>
        <div className="flex items-center gap-3 px-2">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #892d8f, #6e2473)' }}
          >
            AD
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-xs font-semibold truncate">Admin User</p>
            <p className="text-xs truncate" style={{ color: 'rgba(255,255,255,0.4)' }}>HR Director</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
