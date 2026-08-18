import { useEffect, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import DataIngestion from './pages/DataIngestion';
import PerformancePlanning from './pages/PerformancePlanning';
import DirectorPlanning from './pages/DirectorPlanning';
import DirectorReview from './pages/DirectorReview';
import VPReview from './pages/VPReview';
import PMSRegister from './pages/PMSRegister';
import DataTracking from './pages/DataTracking';
import PerformanceAppraisal from './pages/PerformanceAppraisal';
import FeedbackCoaching from './pages/FeedbackCoaching';
import Login from './pages/Login';
import { clearSeenNotifications } from './components/NotificationBell';
import type { PageKey } from './types';

const PAGE_KEYS: PageKey[] = [
  'dashboard',
  'ingestion',
  'planning',
  'director_planning',
  'director_review',
  'vp_review',
  'pms_register',
  'tracking',
  'appraisal',
  'feedback',
];

const PAGES_BY_ROLE: Record<string, PageKey[]> = {
  manager: ['dashboard', 'planning'],
  unit_director: ['dashboard', 'director_planning', 'director_review'],
  vp: ['dashboard', 'vp_review'],
  pms: ['dashboard', 'ingestion', 'pms_register'],
  hr_director: ['dashboard', 'director_review', 'vp_review', 'pms_register'],
};

function isPageKey(value: string | null | undefined): value is PageKey {
  return !!value && PAGE_KEYS.includes(value as PageKey);
}

function allowedPagesForRoles(roles: string[]): PageKey[] {
  const role = roles[0] || 'user';
  return PAGES_BY_ROLE[role] ?? ['dashboard'];
}

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>('dashboard');
  const [me, setMe] = useState<{ name: string; email: string; roles: string[] } | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const ignoreNextHistoryPushRef = useRef(false);
  const historyInitializedRef = useRef(false);

  async function refreshMe() {
    const token = localStorage.getItem('pms_access_token');
    if (!token) {
      setMe(null);
      setAuthReady(true);
      return;
    }
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error();
      const json = await res.json() as { name: string; email: string; roles: string[] };
      setMe({ name: json.name || json.email, email: json.email || '', roles: json.roles || [] });
    } catch {
      localStorage.removeItem('pms_access_token');
      clearSeenNotifications();
      setMe(null);
    } finally {
      setAuthReady(true);
    }
  }

  useEffect(() => { void refreshMe(); }, []);

  function handleLogout() {
    localStorage.removeItem('pms_access_token');
    clearSeenNotifications();
    setMe(null);
    setActivePage('dashboard');
    historyInitializedRef.current = false;
    ignoreNextHistoryPushRef.current = false;
    window.history.replaceState({}, '', window.location.pathname + window.location.search);
  }

  function navigate(page: PageKey) {
    if (!me) return;
    const allowed = allowedPagesForRoles(me.roles);
    setActivePage(allowed.includes(page) ? page : 'dashboard');
  }

  const pages: Record<PageKey, React.ReactElement> = {
    dashboard: <Dashboard />,
    ingestion: <DataIngestion />,
    planning:  <PerformancePlanning />,
    director_planning: <DirectorPlanning />,
    director_review: <DirectorReview />,
    vp_review: <VPReview />,
    pms_register: <PMSRegister />,
    tracking:  <DataTracking />,
    appraisal: <PerformanceAppraisal />,
    feedback:  <FeedbackCoaching />,
  };

  useEffect(() => {
    if (!authReady || !me || historyInitializedRef.current) return;

    const allowed = allowedPagesForRoles(me.roles);
    const fromState = window.history.state?.page as string | undefined;
    const fromHash = window.location.hash?.replace('#', '');
    const requested = isPageKey(fromState) ? fromState : (isPageKey(fromHash) ? fromHash : 'dashboard');
    const initialPage = allowed.includes(requested) ? requested : 'dashboard';

    ignoreNextHistoryPushRef.current = true;
    setActivePage(initialPage);
    window.history.replaceState({ page: initialPage }, '', `${window.location.pathname}${window.location.search}#${initialPage}`);
    historyInitializedRef.current = true;

    function onPopState(e: PopStateEvent) {
      const statePage = e.state?.page as string | undefined;
      const hashPage = window.location.hash?.replace('#', '');
      const nextRequested = isPageKey(statePage) ? statePage : (isPageKey(hashPage) ? hashPage : 'dashboard');
      const nextPage = allowed.includes(nextRequested) ? nextRequested : 'dashboard';
      ignoreNextHistoryPushRef.current = true;
      setActivePage(nextPage);
    }

    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [authReady, me]);

  useEffect(() => {
    if (!me || !historyInitializedRef.current) return;
    const allowed = allowedPagesForRoles(me.roles);
    if (!allowed.includes(activePage)) {
      ignoreNextHistoryPushRef.current = true;
      setActivePage('dashboard');
      return;
    }
    if (ignoreNextHistoryPushRef.current) {
      ignoreNextHistoryPushRef.current = false;
      return;
    }
    window.history.pushState({ page: activePage }, '', `${window.location.pathname}${window.location.search}#${activePage}`);
  }, [activePage, me]);

  if (!authReady) {
    return <div className="min-h-screen bg-slate-100 dark:bg-slate-900" />;
  }

  if (!me) {
    return <Login onLoggedIn={refreshMe} />;
  }

  return (
    <div className="flex min-h-screen bg-slate-100 dark:bg-slate-900 transition-colors duration-200">
      <Sidebar
        activePage={activePage}
        onNavigate={navigate}
        onLogout={handleLogout}
        me={me}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        {pages[activePage]}
      </div>
    </div>
  );
}
