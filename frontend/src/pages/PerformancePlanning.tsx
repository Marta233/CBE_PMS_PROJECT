import { useState } from 'react';
import {
  Sparkles, Plus, Trash2, ChevronDown, Save,
  CreditCard as Edit2, Check, X, Target, Clock,
  TrendingUp, RefreshCw, AlertCircle,
} from 'lucide-react';
import Layout from '../components/Layout';
import { supabase } from '../lib/supabase';
import {
  DIVISIONS,
  DEPARTMENTS,
  UNITS,
  JOB_TITLES,
  JOB_TITLES_BY_UNIT,
  TIMELINES,
  STATUS_COLORS,
  type Objective,
  type ObjectiveSet,
  type KeyResult,
} from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

// ── Backend response shape ────────────────────────────────────────────────────
interface BackendObjective {
  objective: string;
  measure: string;
  target: string;
  weight_percent: number;
  category: string;
  tracking_source: string;
  time_frame: string;
}

interface BackendResponse {
  employee_profile: Record<string, string>;
  objectives: BackendObjective[];
  total_weight: number;
}

// ── Map backend time_frame → frontend timeline ────────────────────────────────
function mapTimeFrame(tf: string): string {
  const map: Record<string, string> = {
    Monthly: 'Q1',
    Quarterly: 'Q1',
    Annually: 'Annual',
    Annual: 'Annual',
  };
  return map[tf] ?? 'Annual';
}

// ── Transform backend objectives → frontend Objective shape ───────────────────
function mapBackendObjectives(
  backendObjs: BackendObjective[],
): Omit<Objective, 'id' | 'set_id' | 'created_at' | 'updated_at'>[] {
  return backendObjs.map((obj) => ({
    title: obj.objective,
    description: `[${obj.category}] Tracked via: ${obj.tracking_source}. Measure: ${obj.measure}.`,
    key_results: [
      { text: obj.objective, target: obj.target, measure: obj.measure },
    ],
    weight: obj.weight_percent,
    timeline: mapTimeFrame(obj.time_frame),
    status: 'draft',
    progress: 0,
  }));
}

// ── Call the FastAPI backend ──────────────────────────────────────────────────
async function fetchObjectivesFromAPI(
  division: string,
  department: string,
  unit: string,
  jobTitle: string,
  count: number,
): Promise<Omit<Objective, 'id' | 'set_id' | 'created_at' | 'updated_at'>[]> {
  const res = await fetch(`${API_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      division,
      department,
      unit,
      job_title: jobTitle,
      num_objectives: count,
    }),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Backend error ${res.status}: ${detail}`);
  }

  const data: BackendResponse = await res.json();
  return mapBackendObjectives(data.objectives);
}

interface EditingState {
  objectiveId: string | null;
  field: string | null;
}

export default function PerformancePlanning() {
  const [division, setDivision] = useState('');
  const [department, setDepartment] = useState('');
  const [unit, setUnit] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [numObjectives, setNumObjectives] = useState(5);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  const [currentSet, setCurrentSet] = useState<ObjectiveSet | null>(null);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [editing, setEditing] = useState<EditingState>({ objectiveId: null, field: null });
  const [editValue, setEditValue] = useState('');

  const availableDepartments = division ? DEPARTMENTS[division] || [] : [];
  const availableUnits = department ? UNITS[department] || [] : [];
  const availableJobTitles = unit
    ? JOB_TITLES_BY_UNIT[unit] || JOB_TITLES
    : department
    ? JOB_TITLES_BY_UNIT[department] || JOB_TITLES
    : JOB_TITLES;

  const canGenerate = division && department && jobTitle && numObjectives > 0;

  async function handleGenerate() {
    if (!canGenerate) return;
    setGenerating(true);
    setGenError(null);
    try {
      // 1. Call the real backend API
      const generated = await fetchObjectivesFromAPI(
        division, department, unit, jobTitle, numObjectives,
      );

      // 2. Create objective_set record in Supabase
      const { data: setData, error: setError } = await supabase
        .from('objective_sets')
        .insert({
          division,
          department,
          unit,
          job_title: jobTitle,
          num_objectives: numObjectives,
          status: 'draft',
        })
        .select()
        .single();

      if (setError) throw setError;
      setCurrentSet(setData);

      // 3. Insert objectives into Supabase
      const { data: objData, error: objError } = await supabase
        .from('objectives')
        .insert(generated.map((o) => ({ ...o, set_id: setData.id })))
        .select();

      if (objError) throw objError;
      setObjectives(objData || []);
    } catch (err: any) {
      console.error('Generate error:', err);
      setGenError(err?.message ?? 'Failed to generate objectives. Is the backend running?');
    } finally {
      setGenerating(false);
    }
  }

  async function handleRegenerate() {
    if (!currentSet) return;
    setGenerating(true);
    setGenError(null);
    try {
      const generated = await fetchObjectivesFromAPI(
        division, department, unit, jobTitle, numObjectives,
      );

      await supabase.from('objectives').delete().eq('set_id', currentSet.id);

      const { data, error } = await supabase
        .from('objectives')
        .insert(generated.map((o) => ({ ...o, set_id: currentSet.id })))
        .select();
      if (error) throw error;
      setObjectives(data || []);
    } catch (err: any) {
      console.error('Regenerate error:', err);
      setGenError(err?.message ?? 'Failed to regenerate objectives.');
    } finally {
      setGenerating(false);
    }
  }

  function startEdit(objectiveId: string, field: string, currentValue: string) {
    setEditing({ objectiveId, field });
    setEditValue(currentValue);
  }

  async function commitEdit(objective: Objective) {
    if (!editing.objectiveId || !editing.field) return;
    const updates: Partial<Objective> = { updated_at: new Date().toISOString() };
    if (editing.field === 'title') updates.title = editValue;
    if (editing.field === 'description') updates.description = editValue;
    if (editing.field === 'timeline') updates.timeline = editValue;
    if (editing.field === 'weight') updates.weight = parseInt(editValue) || objective.weight;
    if (editing.field === 'progress') updates.progress = Math.min(100, Math.max(0, parseInt(editValue) || 0));
    if (editing.field === 'status') updates.status = editValue;

    const { error } = await supabase.from('objectives').update(updates).eq('id', objective.id);
    if (!error) {
      setObjectives((prev) =>
        prev.map((o) => (o.id === objective.id ? { ...o, ...updates } : o))
      );
    }
    setEditing({ objectiveId: null, field: null });
  }

  async function updateKeyResult(objectiveId: string, index: number, field: keyof KeyResult, value: string) {
    const obj = objectives.find((o) => o.id === objectiveId);
    if (!obj) return;
    const updatedKRs = obj.key_results.map((kr, i) =>
      i === index ? { ...kr, [field]: value } : kr
    );
    const { error } = await supabase
      .from('objectives')
      .update({ key_results: updatedKRs, updated_at: new Date().toISOString() })
      .eq('id', objectiveId);
    if (!error) {
      setObjectives((prev) =>
        prev.map((o) => (o.id === objectiveId ? { ...o, key_results: updatedKRs } : o))
      );
    }
  }

  async function addKeyResult(objectiveId: string) {
    const obj = objectives.find((o) => o.id === objectiveId);
    if (!obj) return;
    const newKR: KeyResult = { text: 'New key result', target: 'Target', measure: 'Measurement method' };
    const updatedKRs = [...obj.key_results, newKR];
    const { error } = await supabase
      .from('objectives')
      .update({ key_results: updatedKRs })
      .eq('id', objectiveId);
    if (!error) {
      setObjectives((prev) =>
        prev.map((o) => (o.id === objectiveId ? { ...o, key_results: updatedKRs } : o))
      );
    }
  }

  async function removeKeyResult(objectiveId: string, index: number) {
    const obj = objectives.find((o) => o.id === objectiveId);
    if (!obj) return;
    const updatedKRs = obj.key_results.filter((_, i) => i !== index);
    const { error } = await supabase
      .from('objectives')
      .update({ key_results: updatedKRs })
      .eq('id', objectiveId);
    if (!error) {
      setObjectives((prev) =>
        prev.map((o) => (o.id === objectiveId ? { ...o, key_results: updatedKRs } : o))
      );
    }
  }

  async function removeObjective(objectiveId: string) {
    const { error } = await supabase.from('objectives').delete().eq('id', objectiveId);
    if (!error) {
      setObjectives((prev) => prev.filter((o) => o.id !== objectiveId));
    }
  }

  async function addObjective() {
    if (!currentSet) return;
    const newObj = {
      set_id: currentSet.id,
      title: 'New Objective',
      description: 'Describe this objective and its business impact.',
      key_results: [{ text: 'Key result 1', target: 'Target', measure: 'Measurement' }],
      weight: 10,
      timeline: 'Annual',
      status: 'draft',
      progress: 0,
    };
    const { data, error } = await supabase.from('objectives').insert(newObj).select().single();
    if (!error && data) {
      setObjectives((prev) => [...prev, data]);
    }
  }

  async function handleSave() {
    if (!currentSet) return;
    setSaving(true);
    const { error } = await supabase
      .from('objective_sets')
      .update({ status: 'active' })
      .eq('id', currentSet.id);
    if (!error) {
      setCurrentSet({ ...currentSet, status: 'active' });
    }
    setSaving(false);
  }

  const totalWeight = objectives.reduce((sum, o) => sum + o.weight, 0);

  return (
    <Layout
      title="Performance Planning"
      subtitle="Generate AI-powered objectives aligned to your role and department"
    >
      {/* Config Panel */}
      <div className="card p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <Sparkles size={18} className="text-brand-500" />
          <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">
            Configure Objective Generation
          </h2>
        </div>

        {/* Row 1: Division / Department / Unit / Job Title */}
        <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          {/* Division */}
          <div>
            <label className="label">Division</label>
            <div className="relative">
              <select
                value={division}
                onChange={(e) => { setDivision(e.target.value); setDepartment(''); setUnit(''); }}
                className="select-field pr-8"
              >
                <option value="">Select division</option>
                {DIVISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Department */}
          <div>
            <label className="label">Department</label>
            <div className="relative">
              <select
                value={department}
                onChange={(e) => { setDepartment(e.target.value); setUnit(''); setJobTitle(''); }}
                disabled={!division}
                className="select-field pr-8 disabled:opacity-50"
              >
                <option value="">Select department</option>
                {availableDepartments.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Unit */}
          <div>
            <label className="label">
              Unit <span className="text-slate-400 normal-case font-normal">(optional)</span>
            </label>
            <div className="relative">
              <select
                value={unit}
                onChange={(e) => { setUnit(e.target.value); setJobTitle(''); }}
                disabled={!department}
                className="select-field pr-8 disabled:opacity-50"
              >
                <option value="">Select unit</option>
                {availableUnits.map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Job Title */}
          <div>
            <label className="label">Job Title</label>
            <div className="relative">
              <select
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                className="select-field pr-8"
              >
                <option value="">Select title</option>
                {availableJobTitles.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Row 2: Num Objectives + Generate button */}
        <div className="flex items-end gap-4">
          {/* Number of Objectives */}
          <div>
            <label className="label">No. of Objectives</label>
            <div className="flex items-center border border-slate-200 dark:border-slate-600 rounded-lg overflow-hidden bg-white dark:bg-slate-700 h-[42px]">
              <input
                type="number"
                min={2}
                max={10}
                value={numObjectives}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  if (!isNaN(v)) setNumObjectives(Math.min(10, Math.max(2, v)));
                }}
                className="w-16 px-3 text-sm font-semibold text-slate-800 dark:text-slate-100 bg-transparent focus:outline-none"
              />
              <div className="flex flex-col h-full border-l border-slate-200 dark:border-slate-600 flex-shrink-0">
                <button
                  type="button"
                  onClick={() => setNumObjectives((n) => Math.min(10, n + 1))}
                  disabled={numObjectives >= 10}
                  className="flex-1 w-8 flex items-center justify-center text-slate-500 dark:text-slate-300 hover:bg-brand-50 dark:hover:bg-brand-800/30 hover:text-brand-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors border-b border-slate-200 dark:border-slate-600 text-xs font-bold leading-none"
                  aria-label="Increase"
                >+</button>
                <button
                  type="button"
                  onClick={() => setNumObjectives((n) => Math.max(2, n - 1))}
                  disabled={numObjectives <= 2}
                  className="flex-1 w-8 flex items-center justify-center text-slate-500 dark:text-slate-300 hover:bg-brand-50 dark:hover:bg-brand-800/30 hover:text-brand-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-xs font-bold leading-none"
                  aria-label="Decrease"
                >−</button>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 pb-0.5">
            <button
              onClick={handleGenerate}
              disabled={!canGenerate || generating}
              className="btn-primary"
            >
              {generating ? (
                <>
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  Generate Objectives
                </>
              )}
            </button>
            {!canGenerate && (
              <p className="text-sm text-slate-400">Fill in Division, Department, and Job Title to generate</p>
            )}
          </div>
        </div>

        {/* Error banner */}
        {genError && (
          <div className="mt-4 flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
            <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
            <span>{genError}</span>
          </div>
        )}
      </div>

      {/* Generated Objectives */}
      {objectives.length > 0 && (
        <div className="animate-slide-up">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">
                Generated Objectives
              </h2>
              <span className="badge bg-brand-100 text-brand-600">
                {objectives.length} objectives
              </span>
              <span
                className={`badge ${
                  Math.abs(totalWeight - 100) > 1 ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'
                }`}
              >
                Weight: {totalWeight}%
              </span>
              {currentSet && (
                <span className={`badge ${STATUS_COLORS[currentSet.status]}`}>
                  {currentSet.status}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={handleRegenerate} disabled={generating} className="btn-secondary text-xs">
                <RefreshCw size={14} className={generating ? 'animate-spin' : ''} />
                Regenerate
              </button>
              <button onClick={addObjective} className="btn-secondary text-xs">
                <Plus size={14} />
                Add Objective
              </button>
              <button onClick={handleSave} disabled={saving} className="btn-primary text-xs">
                <Save size={14} />
                {saving ? 'Saving...' : 'Save & Activate'}
              </button>
            </div>
          </div>

          <div className="space-y-4">
            {objectives.map((obj, idx) => (
              <ObjectiveCard
                key={obj.id}
                objective={obj}
                index={idx}
                editing={editing}
                editValue={editValue}
                setEditValue={setEditValue}
                onStartEdit={startEdit}
                onCommitEdit={commitEdit}
                onCancelEdit={() => setEditing({ objectiveId: null, field: null })}
                onUpdateKeyResult={updateKeyResult}
                onAddKeyResult={addKeyResult}
                onRemoveKeyResult={removeKeyResult}
                onRemoveObjective={removeObjective}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {objectives.length === 0 && !generating && (
        <div className="card p-12 text-center">
          <div className="w-16 h-16 bg-brand-50 dark:bg-brand-800/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <Target size={28} className="text-brand-500" />
          </div>
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-2">
            No Objectives Generated Yet
          </h3>
          <p className="text-sm text-slate-500 max-w-sm mx-auto">
            Select your division, department, job title, and number of objectives, then click "Generate Objectives" to create AI-powered performance goals.
          </p>
        </div>
      )}
    </Layout>
  );
}

// ── ObjectiveCard ─────────────────────────────────────────────────────────────

interface ObjectiveCardProps {
  objective: Objective;
  index: number;
  editing: EditingState;
  editValue: string;
  setEditValue: (v: string) => void;
  onStartEdit: (id: string, field: string, value: string) => void;
  onCommitEdit: (obj: Objective) => void;
  onCancelEdit: () => void;
  onUpdateKeyResult: (id: string, index: number, field: keyof KeyResult, value: string) => void;
  onAddKeyResult: (id: string) => void;
  onRemoveKeyResult: (id: string, index: number) => void;
  onRemoveObjective: (id: string) => void;
}

function ObjectiveCard({
  objective,
  index,
  editing,
  editValue,
  setEditValue,
  onStartEdit,
  onCommitEdit,
  onCancelEdit,
  onUpdateKeyResult,
  onAddKeyResult,
  onRemoveKeyResult,
  onRemoveObjective,
}: ObjectiveCardProps) {
  const isEditingThis = editing.objectiveId === objective.id;

  function InlineEdit({
    field,
    value,
    multiline = false,
    inputType = 'text',
    selectOptions,
    className = '',
  }: {
    field: string;
    value: string | number;
    multiline?: boolean;
    inputType?: string;
    selectOptions?: string[];
    className?: string;
  }) {
    const isActive = isEditingThis && editing.field === field;
    if (isActive) {
      if (selectOptions) {
        return (
          <span className="inline-flex items-center gap-1">
            <select
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="border border-brand-400 rounded px-2 py-0.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 dark:bg-slate-700 dark:text-slate-100"
              autoFocus
            >
              {selectOptions.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <button onClick={() => onCommitEdit(objective)} className="text-green-600 hover:text-green-700"><Check size={14} /></button>
            <button onClick={onCancelEdit} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
          </span>
        );
      }
      if (multiline) {
        return (
          <span className="block">
            <textarea
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="w-full border border-brand-400 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none dark:bg-slate-700 dark:text-slate-100"
              rows={3}
              autoFocus
            />
            <span className="inline-flex gap-1 mt-1">
              <button onClick={() => onCommitEdit(objective)} className="text-green-600 hover:text-green-700"><Check size={14} /></button>
              <button onClick={onCancelEdit} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
            </span>
          </span>
        );
      }
      return (
        <span className="inline-flex items-center gap-1">
          <input
            type={inputType}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onCommitEdit(objective);
              if (e.key === 'Escape') onCancelEdit();
            }}
            className={`border border-brand-400 rounded px-2 py-0.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 dark:bg-slate-700 dark:text-slate-100 ${className}`}
            autoFocus
          />
          <button onClick={() => onCommitEdit(objective)} className="text-green-600 hover:text-green-700"><Check size={14} /></button>
          <button onClick={onCancelEdit} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
        </span>
      );
    }
    return (
      <span
        className="cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700 rounded px-1 -mx-1 group inline-flex items-center gap-1 transition-colors"
        onClick={() => onStartEdit(objective.id, field, String(value))}
      >
        <span>{String(value)}</span>
        <Edit2 size={11} className="text-slate-300 group-hover:text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" />
      </span>
    );
  }

  return (
    <div className="card overflow-hidden">
      {/* Card header */}
      <div className="flex items-start justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/40">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5">
            {index + 1}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-900 dark:text-white text-sm">
              <InlineEdit field="title" value={objective.title} className="w-72" />
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2 ml-3 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            <Clock size={13} className="text-slate-400" />
            <span className="text-xs text-slate-600 dark:text-slate-300">
              <InlineEdit field="timeline" value={objective.timeline} selectOptions={TIMELINES} />
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <TrendingUp size={13} className="text-slate-400" />
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
              <InlineEdit field="weight" value={objective.weight} inputType="number" className="w-16" />%
            </span>
          </div>
          <span className={`badge ${STATUS_COLORS[objective.status]}`}>
            <InlineEdit
              field="status"
              value={objective.status}
              selectOptions={['draft', 'in_progress', 'completed', 'cancelled']}
            />
          </span>
          <button
            onClick={() => onRemoveObjective(objective.id)}
            className="p-1 text-slate-300 hover:text-red-500 transition-colors rounded"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <div className="px-5 py-4">
        {/* Description */}
        <div className="mb-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Description</p>
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            <InlineEdit field="description" value={objective.description} multiline />
          </p>
        </div>

        {/* Progress */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Progress</p>
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
              <InlineEdit field="progress" value={objective.progress} inputType="number" className="w-16" />%
            </span>
          </div>
          <div className="w-full h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 rounded-full transition-all duration-500"
              style={{ width: `${objective.progress}%` }}
            />
          </div>
        </div>

        {/* Key Results */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Key Results</p>
            <button
              onClick={() => onAddKeyResult(objective.id)}
              className="text-xs text-brand-500 hover:text-brand-600 flex items-center gap-1 font-medium"
            >
              <Plus size={12} /> Add KR
            </button>
          </div>
          <div className="space-y-2">
            {objective.key_results.map((kr, krIdx) => (
              <div
                key={krIdx}
                className="flex items-start gap-2 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg group"
              >
                <div className="w-4 h-4 rounded-full border-2 border-brand-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0 grid grid-cols-3 gap-2">
                  <div className="col-span-3 md:col-span-1">
                    <input
                      type="text"
                      value={kr.text}
                      onChange={(e) => onUpdateKeyResult(objective.id, krIdx, 'text', e.target.value)}
                      className="w-full text-sm text-slate-700 dark:text-slate-200 bg-transparent border-0 focus:outline-none focus:bg-white dark:focus:bg-slate-700 focus:border focus:border-brand-300 rounded px-1 -mx-1"
                      placeholder="Key result..."
                    />
                  </div>
                  <div>
                    <input
                      type="text"
                      value={kr.target}
                      onChange={(e) => onUpdateKeyResult(objective.id, krIdx, 'target', e.target.value)}
                      className="w-full text-xs text-brand-600 dark:text-brand-300 font-medium bg-transparent border-0 focus:outline-none focus:bg-white dark:focus:bg-slate-700 focus:border focus:border-brand-300 rounded px-1 -mx-1"
                      placeholder="Target..."
                    />
                  </div>
                  <div>
                    <input
                      type="text"
                      value={kr.measure}
                      onChange={(e) => onUpdateKeyResult(objective.id, krIdx, 'measure', e.target.value)}
                      className="w-full text-xs text-slate-500 dark:text-slate-400 bg-transparent border-0 focus:outline-none focus:bg-white dark:focus:bg-slate-700 focus:border focus:border-brand-300 rounded px-1 -mx-1"
                      placeholder="Measurement..."
                    />
                  </div>
                </div>
                <button
                  onClick={() => onRemoveKeyResult(objective.id, krIdx)}
                  className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-500 transition-all flex-shrink-0"
                >
                  <X size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
