// PerformancePlanning.tsx — Table shows EXACTLY what LLM returns, per-row edit modal

import { useState } from 'react';
import {
  Sparkles, Plus, ChevronDown, Save, Edit2, Trash2,
  RefreshCw, AlertCircle, Target, X, Check, Download,
} from 'lucide-react';
import Layout from '../components/Layout';
import {
  DIVISIONS, DEPARTMENTS, UNITS, JOB_TITLES, JOB_TITLES_BY_UNIT,
  type ObjectiveSet,
} from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

// ── Exact shape the backend/LLM returns ──────────────────────────────────────
interface LLMObjective {
  id:              string;   // client-only
  objective:       string;   // "Define and update all ATM terminals..."
  measure:         string;   // "%"  |  "Number"  |  "Various"
  target:          string;   // "100%"  |  "50% of manager's target"
  weight_percent:  number;   // 50 | 15 | 10 …
  category:        string;   // "Cannot Exceed" | "Can Exceed"
  tracking_source: string;   // "System" | "Manual" | "System & Manual"
  time_frame:      string;   // "Quarterly" | "Annual" …
}

interface BackendObjective {
  objective: string; measure: string; target: string;
  weight_percent: number; category: string;
  tracking_source: string; time_frame: string;
}
interface BackendResponse {
  employee_profile: Record<string, string>;
  objectives: BackendObjective[];
  total_weight: number;
}

function uid() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }

function fromBackend(b: BackendObjective): LLMObjective {
  return {
    id:              uid(),
    objective:       b.objective,
    measure:         b.measure,
    target:          b.target,
    weight_percent:  b.weight_percent,
    category:        b.category,        // "Cannot Exceed" / "Can Exceed"
    tracking_source: b.tracking_source,
    time_frame:      b.time_frame,
  };
}

async function callAPI(
  division: string, department: string, unit: string,
  jobTitle: string, jobGrade: string, count: number,
): Promise<LLMObjective[]> {
  const res = await fetch(`${API_URL}/api/generate`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      division, department, unit,
      job_title: jobTitle, job_grade: jobGrade, num_objectives: count,
    }),
  });
  if (!res.ok)
    throw new Error(`Backend error ${res.status}: ${await res.text().catch(() => res.statusText)}`);
  const data: BackendResponse = await res.json();
  return data.objectives.map(fromBackend);
}

// ── Downloads ─────────────────────────────────────────────────────────────────
function downloadCSV(rows: LLMObjective[], meta: ObjectiveSet | null) {
  const header = ['#', 'Objective', 'Measure', 'Target', 'Weight (%)', 'Category', 'Tracking Source', 'Time Frame'];
  const body   = rows.map((r, i) => [
    i + 1,
    `"${r.objective.replace(/"/g, '""')}"`,
    `"${r.measure}"`,
    `"${r.target.replace(/"/g, '""')}"`,
    r.weight_percent,
    `"${r.category}"`,
    `"${r.tracking_source}"`,
    `"${r.time_frame}"`,
  ]);
  const metaLines = meta
    ? `Division,${meta.division}\nDepartment,${meta.department}\nUnit,${meta.unit}\nJob Title,${meta.job_title}\nGenerated,${new Date().toLocaleString()}\n\n`
    : '';
  const csv  = metaLines + [header.join(','), ...body.map(r => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a'); a.href = url; a.download = 'objectives.csv'; a.click();
  URL.revokeObjectURL(url);
}

function downloadJSON(rows: LLMObjective[], meta: ObjectiveSet | null) {
  const payload = { employee_profile: meta ?? {}, generated_at: new Date().toISOString(), objectives: rows };
  const blob    = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url     = URL.createObjectURL(blob);
  const a       = document.createElement('a'); a.href = url; a.download = 'objectives.json'; a.click();
  URL.revokeObjectURL(url);
}

// ── Edit modal ────────────────────────────────────────────────────────────────
function EditModal({
  row, onSave, onClose,
}: {
  row:     LLMObjective;
  onSave:  (updated: LLMObjective) => void;
  onClose: () => void;
}) {
  const [d, setD] = useState<LLMObjective>({ ...row });

  const inputCls = 'w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 text-sm text-slate-800 dark:text-slate-100 bg-white dark:bg-slate-700 focus:outline-none focus:ring-2 transition-all';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-700">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white"
              style={{ backgroundColor: '#892d8f' }}>
              <Edit2 size={13} />
            </div>
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Edit Objective</h2>
          </div>
          <button onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Fields */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">

          {/* Objective */}
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Objective</label>
            <textarea rows={3} value={d.objective}
              onChange={e => setD(p => ({ ...p, objective: e.target.value }))}
              className={`${inputCls} resize-none`} />
          </div>

          {/* Measure + Target */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Measure</label>
              <input type="text" value={d.measure}
                onChange={e => setD(p => ({ ...p, measure: e.target.value }))}
                className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Target</label>
              <input type="text" value={d.target}
                onChange={e => setD(p => ({ ...p, target: e.target.value }))}
                className={inputCls} />
            </div>
          </div>

          {/* Weight + Category */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Weight (%)</label>
              <input type="number" value={d.weight_percent}
                onChange={e => setD(p => ({ ...p, weight_percent: parseFloat(e.target.value) || 0 }))}
                className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Category</label>
              <select value={d.category}
                onChange={e => setD(p => ({ ...p, category: e.target.value }))}
                className={inputCls}>
                <option>Cannot Exceed</option>
                <option>Can Exceed</option>
              </select>
            </div>
          </div>

          {/* Tracking Source + Time Frame */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Tracking Source</label>
              <select value={d.tracking_source}
                onChange={e => setD(p => ({ ...p, tracking_source: e.target.value }))}
                className={inputCls}>
                <option>System</option>
                <option>Manual</option>
                <option>System &amp; Manual</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Time Frame</label>
              <select value={d.time_frame}
                onChange={e => setD(p => ({ ...p, time_frame: e.target.value }))}
                className={inputCls}>
                {['Monthly', 'Quarterly', 'Annual', 'Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2'].map(o => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100 dark:border-slate-700">
          <button onClick={onClose}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors">
            <X size={14} />Cancel
          </button>
          <button onClick={() => onSave(d)}
            className="inline-flex items-center gap-2 px-4 py-2 text-white text-sm font-medium rounded-lg transition-colors"
            style={{ backgroundColor: '#892d8f' }}>
            <Check size={14} />Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
export default function PerformancePlanning() {
  const [division,      setDivision]      = useState('');
  const [department,    setDepartment]    = useState('');
  const [unit,          setUnit]          = useState('');
  const [jobTitle,      setJobTitle]      = useState('');
  const [jobGrade,      setJobGrade]      = useState('');
  const [numObjectives, setNumObjectives] = useState(5);
  const [generating,    setGenerating]    = useState(false);
  const [genError,      setGenError]      = useState<string | null>(null);

  const [currentSet,  setCurrentSet]  = useState<ObjectiveSet | null>(null);
  const [objectives,  setObjectives]  = useState<LLMObjective[]>([]);
  const [editingRow,  setEditingRow]  = useState<LLMObjective | null>(null);

  const availableDepartments = division   ? DEPARTMENTS[division]           || [] : [];
  const availableUnits       = department ? UNITS[department]               || [] : [];
  const availableJobTitles   = unit
    ? JOB_TITLES_BY_UNIT[unit]       || JOB_TITLES
    : department
    ? JOB_TITLES_BY_UNIT[department] || JOB_TITLES
    : JOB_TITLES;

  const canGenerate = !!(division && department && jobTitle);

  async function handleGenerate(isRegen = false) {
    if (!canGenerate) return;
    setGenerating(true); setGenError(null);
    try {
      const rows = await callAPI(division, department, unit, jobTitle, jobGrade, numObjectives);
      if (!isRegen || !currentSet) {
        setCurrentSet({
          id: uid(), division, department, unit, job_title: jobTitle,
          num_objectives: numObjectives, status: 'draft',
          created_at: new Date().toISOString(),
        });
      }
      setObjectives(rows);
    } catch (err) {
      setGenError(err instanceof Error ? err.message : 'Failed to generate. Is the backend running?');
    } finally {
      setGenerating(false);
    }
  }

  function saveEdit(updated: LLMObjective) {
    setObjectives(prev => prev.map(o => o.id === updated.id ? updated : o));
    setEditingRow(null);
  }

  function deleteRow(id: string) {
    setObjectives(prev => prev.filter(o => o.id !== id));
  }

  function addRow() {
    if (!currentSet) return;
    setObjectives(prev => [...prev, {
      id: uid(),
      objective:       'New Objective',
      measure:         '%',
      target:          'Define target',
      weight_percent:  10,
      category:        'Can Exceed',
      tracking_source: 'System',
      time_frame:      'Quarterly',
    }]);
  }

  const totalWeight = objectives.reduce((s, o) => s + o.weight_percent, 0);
  const weightOk    = Math.abs(totalWeight - 100) <= 1;

  return (
    <Layout title="Performance Planning"
      subtitle="Generate AI-powered objectives aligned to your role and department">

      {/* ── Config panel ──────────────────────────────────────────────────── */}
      <div className="card p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <Sparkles size={18} style={{ color: '#892d8f' }} />
          <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">
            Configure Objective Generation
          </h2>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          {/* Division */}
          <div>
            <label className="label">Division</label>
            <div className="relative">
              <select value={division}
                onChange={e => { setDivision(e.target.value); setDepartment(''); setUnit(''); setJobTitle(''); }}
                className="select-field pr-8">
                <option value="">Select division</option>
                {DIVISIONS.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>
          {/* Department */}
          <div>
            <label className="label">Department</label>
            <div className="relative">
              <select value={department} disabled={!division}
                onChange={e => { setDepartment(e.target.value); setUnit(''); setJobTitle(''); }}
                className="select-field pr-8 disabled:opacity-50">
                <option value="">Select department</option>
                {availableDepartments.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>
          {/* Unit */}
          <div>
            <label className="label">Unit </label>
            <div className="relative">
              <select value={unit} disabled={!department}
                onChange={e => { setUnit(e.target.value); setJobTitle(''); }}
                className="select-field pr-8 disabled:opacity-50">
                <option value="">Select unit</option>
                {availableUnits.map(u => <option key={u} value={u}>{u}</option>)}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>
          {/* Job Title */}
          <div>
            <label className="label">Job Title</label>
            <div className="relative">
              <select value={jobTitle} onChange={e => setJobTitle(e.target.value)} className="select-field pr-8">
                <option value="">Select title</option>
                {availableJobTitles.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>
        </div>

        <div className="flex items-end gap-4 flex-wrap">
          {/* Job Grade */}
          <div>
            <label className="label">Job Grade <span className="text-slate-400 normal-case font-normal">(optional)</span></label>
            <input type="text" value={jobGrade} onChange={e => setJobGrade(e.target.value)}
              placeholder="e.g. 13" className="select-field w-28" />
          </div>
          {/* Num Objectives */}
          <div>
            <label className="label">No. of Objectives</label>
            <div className="flex items-center border border-slate-200 dark:border-slate-600 rounded-lg overflow-hidden bg-white dark:bg-slate-700 h-[42px]">
              <input type="number" min={2} max={10} value={numObjectives}
                onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setNumObjectives(Math.min(10, Math.max(2, v))); }}
                className="w-16 px-3 text-sm font-semibold text-slate-800 dark:text-slate-100 bg-transparent focus:outline-none" />
              <div className="flex flex-col h-full border-l border-slate-200 dark:border-slate-600">
                <button onClick={() => setNumObjectives(n => Math.min(10, n + 1))} disabled={numObjectives >= 10}
                  className="flex-1 w-8 flex items-center justify-center text-slate-500 hover:text-purple-600 disabled:opacity-30 border-b border-slate-200 text-xs font-bold">+</button>
                <button onClick={() => setNumObjectives(n => Math.max(2, n - 1))} disabled={numObjectives <= 2}
                  className="flex-1 w-8 flex items-center justify-center text-slate-500 hover:text-purple-600 disabled:opacity-30 text-xs font-bold">−</button>
              </div>
            </div>
          </div>
          {/* Generate */}
          <div className="flex items-center gap-3 pb-0.5">
            <button onClick={() => handleGenerate(false)} disabled={!canGenerate || generating}
              className="btn-primary">
              {generating
                ? <><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                    </svg>Generating...</>
                : <><Sparkles size={16}/>Generate Objectives</>}
            </button>
            {!canGenerate && (
              <p className="text-sm text-slate-400">Fill in Division, Department, and Job Title first</p>
            )}
          </div>
        </div>

        {genError && (
          <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
            <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
            <span>{genError}</span>
          </div>
        )}
      </div>

      {/* ── Results table ─────────────────────────────────────────────────── */}
      {objectives.length > 0 && (
        <div>
          {/* Toolbar */}
          <div className="flex items-center justify-between mb-3 flex-wrap gap-3">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">Generated Objectives</h2>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                {objectives.length} objectives
              </span>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${weightOk ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                Total weight: {totalWeight}% {weightOk ? '✓' : '⚠ should be 100%'}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button onClick={() => handleGenerate(true)} disabled={generating}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50">
                <RefreshCw size={14} className={generating ? 'animate-spin' : ''}/>Regenerate
              </button>
              <button onClick={addRow}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors">
                <Plus size={14}/>Add Row
              </button>
              <button onClick={() => downloadCSV(objectives, currentSet)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors">
                <Download size={14}/>CSV
              </button>
              <button onClick={() => downloadJSON(objectives, currentSet)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors">
                <Download size={14}/>JSON
              </button>
              <button
                onClick={() => setCurrentSet(s => s ? { ...s, status: 'active' } : s)}
                className="inline-flex items-center gap-2 px-4 py-2 text-white text-sm font-medium rounded-lg transition-colors"
                style={{ backgroundColor: '#892d8f' }}>
                <Save size={14}/>Save & Activate
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" style={{ minWidth: '960px' }}>
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                    {[
                      { label: '#',         cls: 'w-10'  },
                      { label: 'Objective', cls: 'w-72'  },
                      { label: 'Measure',   cls: 'w-24'  },
                      { label: 'Target',    cls: 'w-52'  },
                      { label: 'Weight (%)',cls: 'w-28'  },
                      { label: 'Category',  cls: 'w-36'  },
                      { label: 'Actions',   cls: 'w-24'  },
                    ].map(c => (
                      <th key={c.label}
                        className={`text-left px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap ${c.cls}`}>
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {objectives.map((obj, idx) => (
                    <tr key={obj.id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors group align-top">

                      {/* # */}
                      <td className="px-4 py-3.5">
                        <div className="w-6 h-6 rounded-md flex items-center justify-center text-white text-xs font-bold"
                          style={{ backgroundColor: '#892d8f' }}>
                          {idx + 1}
                        </div>
                      </td>

                      {/* Objective */}
                      <td className="px-4 py-3.5">
                        <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-snug">
                          {obj.objective}
                        </p>
                        {idx === 0 && (
                          <span className="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                            📌 Critical Target
                          </span>
                        )}
                      </td>

                      {/* Measure */}
                      <td className="px-4 py-3.5">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 whitespace-nowrap">
                          {obj.measure}
                        </span>
                      </td>

                      {/* Target */}
                      <td className="px-4 py-3.5">
                        <p className="text-sm text-slate-700 dark:text-slate-200 leading-snug">{obj.target}</p>
                      </td>

                      {/* Weight */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-800 dark:text-slate-100 w-10">
                            {obj.weight_percent}%
                          </span>
                          <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden w-10">
                            <div className="h-full rounded-full"
                              style={{ width: `${Math.min(100, obj.weight_percent)}%`, backgroundColor: '#892d8f' }} />
                          </div>
                        </div>
                      </td>

                      {/* Category — "Cannot Exceed" / "Can Exceed" */}
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${
                          obj.category === 'Cannot Exceed'
                            ? 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                            : 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                        }`}>
                          {obj.category}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-1.5">
                          <button onClick={() => setEditingRow(obj)}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-white transition-colors"
                            style={{ backgroundColor: '#892d8f' }}>
                            <Edit2 size={11}/>Edit
                          </button>
                          <button onClick={() => deleteRow(obj.id)}
                            className="p-1.5 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
                            <Trash2 size={13}/>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>

                {/* Total weight footer */}
                <tfoot>
                  <tr className="bg-slate-50 dark:bg-slate-700/30 border-t-2 border-slate-200 dark:border-slate-600">
                    <td className="px-4 py-3" colSpan={4}>
                      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Weight</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-sm font-bold ${weightOk ? 'text-green-600' : 'text-amber-600'}`}>
                        {totalWeight}% {weightOk ? '✓' : '⚠'}
                      </span>
                    </td>
                    <td colSpan={2}/>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {objectives.length === 0 && !generating && (
        <div className="card p-12 text-center">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ backgroundColor: 'rgba(137,45,143,0.08)' }}>
            <Target size={28} style={{ color: '#892d8f' }} />
          </div>
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-2">No Objectives Generated Yet</h3>
          <p className="text-sm text-slate-500 max-w-sm mx-auto">
            Select your division, department, job title, and number of objectives, then click "Generate Objectives".
          </p>
        </div>
      )}

      {/* Edit modal */}
      {editingRow && (
        <EditModal row={editingRow} onSave={saveEdit} onClose={() => setEditingRow(null)} />
      )}
    </Layout>
  );
}
