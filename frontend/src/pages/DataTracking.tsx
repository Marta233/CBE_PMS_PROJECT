// DataTracking.tsx  —  Supabase removed; objectives live in React state only.
// NOTE: objectives generated in PerformancePlanning are page-local state.
// To share them, lift state to App.tsx and pass as a prop, or use Context.
// For now this page ships with its own sample data so it is always useful.

import { useState } from 'react';
import { ChartBar as BarChart2, ListFilter as Filter, ChevronDown, Download } from 'lucide-react';
import Layout from '../components/Layout';
import { STATUS_COLORS, type Objective } from '../types';

// ── Sample objectives so the page is useful without a backend ────────────────
const SAMPLE_OBJECTIVES: Objective[] = [
  {
    id: '1', set_id: 's1', title: 'Increase digital wallet adoption by 20%',
    description: 'Drive mobile money user growth across key regions.',
    key_results: [{ text: 'Wallet registrations', target: '20% growth', measure: 'System reports' }],
    weight: 20, timeline: 'Q2', status: 'in_progress', progress: 65,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  },
  {
    id: '2', set_id: 's1', title: 'Reduce card dispute resolution time to 48h',
    description: 'Streamline dispute workflow for faster customer resolution.',
    key_results: [{ text: 'Avg resolution time', target: '≤48 hours', measure: 'Ticketing system' }],
    weight: 15, timeline: 'H1', status: 'in_progress', progress: 40,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  },
  {
    id: '3', set_id: 's1', title: 'Complete AML policy documentation update',
    description: 'Update all AML compliance documents to 2026 standards.',
    key_results: [{ text: 'Documents reviewed and approved', target: '100%', measure: 'Compliance tracker' }],
    weight: 20, timeline: 'Q1', status: 'completed', progress: 100,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  },
  {
    id: '4', set_id: 's1', title: 'Train 50 agents on mobile money procedures',
    description: 'Deliver structured training programme to agent network.',
    key_results: [{ text: 'Agents trained', target: '50 agents', measure: 'Training records' }],
    weight: 15, timeline: 'Annual', status: 'in_progress', progress: 72,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  },
  {
    id: '5', set_id: 's1', title: 'Launch internet banking 2FA rollout',
    description: 'Deploy two-factor authentication for all IB customers.',
    key_results: [{ text: '2FA enabled users', target: '100% of active users', measure: 'Auth system logs' }],
    weight: 15, timeline: 'Q3', status: 'draft', progress: 10,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  },
  {
    id: '6', set_id: 's2', title: 'Achieve 99.5% ATM uptime for Q2',
    description: 'Minimise ATM downtime through proactive maintenance scheduling.',
    key_results: [{ text: 'ATM uptime', target: '≥99.5%', measure: 'Network monitoring system' }],
    weight: 15, timeline: 'Q2', status: 'in_progress', progress: 88,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  },
];

// ── CSV download ──────────────────────────────────────────────────────────────
function downloadCSV(objectives: Objective[]) {
  const header = ['Title', 'Timeline', 'Weight (%)', 'Progress (%)', 'Status'];
  const rows = objectives.map((o) => [
    `"${o.title.replace(/"/g, '""')}"`,
    o.timeline, o.weight, o.progress, o.status,
  ]);
  const csv = [header.join(','), ...rows.map((r) => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'data-tracking.csv'; a.click();
  URL.revokeObjectURL(url);
}

export default function DataTracking() {
  const [objectives, setObjectives] = useState<Objective[]>(SAMPLE_OBJECTIVES);
  const [filterStatus, setFilterStatus]     = useState('all');
  const [filterTimeline, setFilterTimeline] = useState('all');

  function updateProgress(id: string, progress: number) {
    const clamped = Math.min(100, Math.max(0, progress));
    const status  = clamped >= 100 ? 'completed' : clamped > 0 ? 'in_progress' : 'draft';
    setObjectives((prev) =>
      prev.map((o) => (o.id === id ? { ...o, progress: clamped, status } : o))
    );
  }

  const filtered = objectives.filter((o) => {
    if (filterStatus !== 'all' && o.status !== filterStatus) return false;
    if (filterTimeline !== 'all' && o.timeline !== filterTimeline) return false;
    return true;
  });

  const statuses  = ['all', 'draft', 'in_progress', 'completed', 'cancelled'];
  const timelines = ['all', 'Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2', 'Annual'];
  const avg = filtered.length > 0
    ? Math.round(filtered.reduce((s, o) => s + o.progress, 0) / filtered.length) : 0;

  return (
    <Layout
      title="Data Tracking"
      subtitle="Monitor and update progress on all objectives"
      actions={
        <button onClick={() => downloadCSV(filtered)} className="btn-secondary text-xs flex items-center gap-1.5">
          <Download size={14} /> Export CSV
        </button>
      }
    >
      {/* Summary Bar */}
      <div className="grid grid-cols-4 gap-4 mb-5">
        {[
          { label: 'Total Objectives', value: filtered.length,                                       color: 'text-slate-900 dark:text-white' },
          { label: 'Avg. Progress',    value: `${avg}%`,                                             color: 'text-brand-500' },
          { label: 'Completed',        value: filtered.filter((o) => o.status === 'completed').length, color: 'text-green-600' },
          { label: 'In Progress',      value: filtered.filter((o) => o.status === 'in_progress').length, color: 'text-amber-600' },
        ].map((s, i) => (
          <div key={i} className="card p-4">
            <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="card p-4 mb-4 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Filter size={15} className="text-slate-400" />
          <span className="font-medium">Filter:</span>
        </div>
        <div className="relative">
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="select-field pr-8 text-xs py-1.5 w-36">
            {statuses.map((s) => <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s.replace('_', ' ')}</option>)}
          </select>
          <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        </div>
        <div className="relative">
          <select value={filterTimeline} onChange={(e) => setFilterTimeline(e.target.value)} className="select-field pr-8 text-xs py-1.5 w-36">
            {timelines.map((t) => <option key={t} value={t}>{t === 'all' ? 'All Timelines' : t}</option>)}
          </select>
          <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        </div>
        <span className="text-xs text-slate-400 ml-auto">{filtered.length} objectives shown</span>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="card p-12 text-center">
          <BarChart2 size={32} className="text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-slate-500">No objectives match the current filters.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-2/5">Objective</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Timeline</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Weight</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider w-36">Progress</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Update</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {filtered.map((obj) => (
                <tr key={obj.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors group">
                  <td className="px-5 py-3.5">
                    <p className="font-medium text-slate-800 dark:text-slate-100 truncate max-w-xs">{obj.title}</p>
                  </td>
                  <td className="px-3 py-3.5">
                    <span className="text-xs font-medium text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded">
                      {obj.timeline}
                    </span>
                  </td>
                  <td className="px-3 py-3.5">
                    <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">{obj.weight}%</span>
                  </td>
                  <td className="px-3 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            obj.progress >= 100 ? 'bg-green-500' : obj.progress >= 60 ? 'bg-brand-500' : obj.progress >= 30 ? 'bg-amber-500' : 'bg-slate-300'
                          }`}
                          style={{ width: `${obj.progress}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium text-slate-600 dark:text-slate-300 w-8 text-right">{obj.progress}%</span>
                    </div>
                  </td>
                  <td className="px-3 py-3.5">
                    <span className={`badge ${STATUS_COLORS[obj.status] || 'bg-slate-100 text-slate-600'}`}>
                      {obj.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-3 py-3.5">
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {[0, 25, 50, 75, 100].map((p) => (
                        <button
                          key={p}
                          onClick={() => updateProgress(obj.id, p)}
                          className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                            obj.progress === p
                              ? 'bg-brand-500 text-white'
                              : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-brand-100 hover:text-brand-600'
                          }`}
                        >
                          {p}%
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Layout>
  );
}
