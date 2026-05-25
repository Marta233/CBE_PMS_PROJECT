import { useState } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import DataIngestion from './pages/DataIngestion';
import PerformancePlanning from './pages/PerformancePlanning';
import DataTracking from './pages/DataTracking';
import PerformanceAppraisal from './pages/PerformanceAppraisal';
import FeedbackCoaching from './pages/FeedbackCoaching';
import type { PageKey } from './types';

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>('dashboard');

  const pages: Record<PageKey, React.ReactElement> = {
    dashboard: <Dashboard />,
    ingestion: <DataIngestion />,
    planning:  <PerformancePlanning />,
    tracking:  <DataTracking />,
    appraisal: <PerformanceAppraisal />,
    feedback:  <FeedbackCoaching />,
  };

  return (
    <div className="flex min-h-screen bg-slate-100 dark:bg-slate-900 transition-colors duration-200">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <div className="flex-1 flex flex-col overflow-hidden">
        {pages[activePage]}
      </div>
    </div>
  );
}
