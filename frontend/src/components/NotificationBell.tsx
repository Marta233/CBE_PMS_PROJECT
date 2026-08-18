import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Bell, CheckCheck } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';
const SEEN_KEY = 'pms_seen_notification_ids';

type NotificationItem = {
  id: string;
  set_id: number;
  title: string;
  message: string;
  unit_name: string;
  timestamp: string;
};

type NotificationsResponse = {
  unread_count: number;
  notifications: NotificationItem[];
};

function token() {
  return localStorage.getItem('pms_access_token');
}

function loadSeenIds(): Set<string> {
  try {
    const raw = localStorage.getItem(SEEN_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as string[];
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
}

function saveSeenIds(ids: Set<string>) {
  localStorage.setItem(SEEN_KEY, JSON.stringify(Array.from(ids)));
}

export function clearSeenNotifications() {
  localStorage.removeItem(SEEN_KEY);
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [seenIds, setSeenIds] = useState<Set<string>>(() => loadSeenIds());
  const ref = useRef<HTMLDivElement>(null);

  const unreadCount = useMemo(
    () => items.filter(n => !seenIds.has(n.id)).length,
    [items, seenIds],
  );

  const markSeen = useCallback((ids: string[]) => {
    if (ids.length === 0) return;
    setSeenIds(prev => {
      const next = new Set(prev);
      ids.forEach(id => next.add(id));
      saveSeenIds(next);
      return next;
    });
  }, []);

  const refresh = useCallback(async () => {
    const t = token();
    if (!t) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/notifications`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (!res.ok) return;
      const json = await res.json() as NotificationsResponse;
      setItems(json.notifications || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => { void refresh(); }, 60000);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (!open) return;
    markSeen(items.map(n => n.id));
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open, items, markSeen]);

  if (!token()) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => {
          setOpen(v => !v);
          void refresh();
        }}
        className="relative p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
        aria-label="Notifications"
      >
        <Bell size={18} className="text-slate-500 dark:text-slate-400" />
        {unreadCount > 0 && (
          <span
            className="absolute top-1 right-1 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold text-white flex items-center justify-center"
            style={{ backgroundColor: '#16a34a' }}
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 max-h-[70vh] overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-xl z-50">
          <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">Notifications</p>
            {loading && <span className="text-xs text-slate-400">Updating…</span>}
          </div>
          <div className="overflow-y-auto max-h-[60vh]">
            {items.length === 0 && (
              <p className="px-4 py-8 text-sm text-center text-slate-500 dark:text-slate-400">
                No pending approvals right now.
              </p>
            )}
            {items.map(n => {
              const seen = seenIds.has(n.id);
              return (
                <div
                  key={n.id}
                  className={`px-4 py-3 border-b border-slate-100 dark:border-slate-700 last:border-b-0 hover:bg-slate-50 dark:hover:bg-slate-700/40 ${
                    seen ? 'opacity-80' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className={`text-xs font-semibold ${seen ? 'text-slate-500 dark:text-slate-400' : 'text-purple-700 dark:text-purple-300'}`}>
                        {n.title}
                      </p>
                      <p className="text-sm text-slate-700 dark:text-slate-200 mt-1 leading-snug">{n.message}</p>
                      <p className="text-[11px] text-slate-400 mt-1">
                        {new Date(n.timestamp).toLocaleString()}
                      </p>
                    </div>
                    {seen && (
                      <span title="Seen" className="shrink-0 mt-0.5">
                        <CheckCheck
                          size={16}
                          className="text-sky-500 dark:text-sky-400"
                          aria-label="Seen"
                        />
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
