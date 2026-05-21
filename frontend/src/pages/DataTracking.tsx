import { useEffect, useState } from 'react';
import { ChartBar as BarChart2, ListFilter as Filter, ChevronDown } from 'lucide-react';
import Layout from '../components/Layout';
import { supabase } from '../lib/supabase';
import { STATUS_COLORS, type Objective } from '../types';

export default function DataTracking() {
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterTimeline, setFilterTimeline] = useState('all');

  useEffect(() => {
    loadObjectives();
  }, []);

  async function loadObjectives() {
    setLoading(true);
    const { data } = await supabase
      .from('objectives')
      .select('*, objective_sets(division, department, unit, job_title)')
      .order('created_at', { ascending: false });
    setObjectives((data || []) as unknown as Objective[]);
    setLoading(false);
  }

  async function updateProgress(id: string, progress: number) {
    const clamped = Math.min(100, Math.max(0, progress));
    const status = clamped >= 100 ? 'completed' : clamped > 0 ? 'in_progress' : 'draft';
    await supabase
      .from('objectives')
      .update({ progress: clamped, status, updated_at: new Date().toISOString() })
      .eq('id', id);
    setObjectives((prev) =>
      prev.map((o) => (o.id === id ? { ...o, progress: clamped, status } : o))
    );
  }

  const filtered = objectives.filter((o) => {
    if (filterStatus !== 'all' && o.status !== filterStatus) return false;
    if (filterTimeline !== 'all' && o.timeline !== filterTimeline) return false;
    return true;
  });

  const statuses = ['all', 'draft', 'in_progress', 'completed', 'cancelled'];
  const timelines = ['all', 'Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2', 'Annual'];

  const avg = filtered.length > 0
    ? Math.round(filtered.reduce((s, o) => s + o.progress, 0) / filtered.length)
    : 0;

  return (
    <Layout title="Data Tracking" subtitle="Monitor and update progress on all objectives">
      {/* Summary Bar */}
      <div className="grid grid-cols-4 gap-4 mb-5">
        {[
          { label: 'Total Objectives', value: filtered.length, color: 'text-slate-900 dark:text-white' },
          { label: 'Avg. Progress', value: `${avg}%`, color: 'text-purple-600' },
          { label: 'Completed', value: filtered.filter((o) => o.status === 'completed').length, color: 'text-green-600' },
          { label: 'In Progress', value: filtered.filter((o) => o.status === 'in_progress').length, color: 'text-amber-600' },
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
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="select-field pr-8 text-xs py-1.5 w-36"
          >
            {statuses.map((s) => (
              <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s.replace('_', ' ')}</option>
            ))}
          </select>
          <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        </div>
        <div className="relative">
          <select
            value={filterTimeline}
            onChange={(e) => setFilterTimeline(e.target.value)}
            className="select-field pr-8 text-xs py-1.5 w-36"
          >
            {timelines.map((t) => (
              <option key={t} value={t}>{t === 'all' ? 'All Timelines' : t}</option>
            ))}
          </select>
          <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        </div>
        <span className="text-xs text-slate-400 ml-auto">{filtered.length} objectives shown</span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="card p-12 text-center">
          <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm text-slate-500">Loading objectives...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-12 text-center">
          <BarChart2 size={32} className="text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-slate-500">No objectives to track. Generate objectives in Performance Planning.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider w-2/5">Objective</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Timeline</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Weight</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider w-36">Progress</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Status</th>
                <th className="text-left px-3 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Update</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {filtered.map((obj) => (
                <tr key={obj.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors group">
                  <td className="px-5 py-3.5">
                    <p className="font-medium text-slate-800 dark:text-slate-100 truncate max-w-xs">{obj.title}</p>
                    <p className="text-xs text-slate-400 truncate max-w-xs mt-0.5">
                      {(obj as unknown as Record<string, Record<string, string>>).objective_sets?.department} &bull; {(obj as unknown as Record<string, Record<string, string>>).objective_sets?.job_title}
                    </p>
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
                            obj.progress >= 100 ? 'bg-green-500' : obj.progress >= 60 ? 'bg-purple-500' : obj.progress >= 30 ? 'bg-amber-500' : 'bg-slate-300'
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
                              ? 'bg-purple-600 text-white'
                              : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-purple-100 hover:text-purple-700'
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
