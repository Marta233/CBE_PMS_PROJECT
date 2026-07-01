// PerformancePlanning.tsx — Table shows EXACTLY what LLM returns, per-row edit modal

import { useState, Fragment } from 'react';
import {
  Sparkles, Plus, ChevronDown, ChevronRight, Save, Edit2, Trash2,
  RefreshCw, AlertCircle, Target, X, Check, Download, Scale, Info,
} from 'lucide-react';
import Layout from '../components/Layout';
import {
  DIVISIONS, DEPARTMENTS, UNITS, JOB_TITLES, JOB_TITLES_BY_UNIT,
  type ObjectiveSet,
} from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

type ObjectiveCategory = 'Cannot Exceed' | 'Can Exceed' | 'Major Critical';

const CATEGORIES: ObjectiveCategory[] = ['Cannot Exceed', 'Can Exceed', 'Major Critical'];

function categoryBadgeCls(category: string): string {
  if (category === 'Major Critical')
    return 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300';
  if (category === 'Cannot Exceed')
    return 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300';
  return 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300';
}

// ── Exact shape the backend/LLM returns ──────────────────────────────────────
interface AppraisalLogic {
  rating_5: string;
  rating_4: string;
  rating_3: string;
  rating_2: string;
  rating_1: string;
}

interface LLMObjective {
  id:              string;   // client-only
  objective:       string;
  measure:         string;
  target:          string;
  weight_percent:  number;
  category:        ObjectiveCategory;
  tracking_source: string;
  time_frame:      string;
  source?:         string;
  bsc_kpi?:                    string;
  bsc_strategic_objective?:    string;
  los_alignment?:              string;
  appraisal_logic?:            AppraisalLogic;
}

interface BackendObjective {
  objective: string; measure: string; target: string;
  weight_percent: number; category: string;
  tracking_source: string; time_frame: string;
  source?: string;
  bsc_kpi?: string;
  bsc_strategic_objective?: string;
  los_alignment?: string;
  appraisal_logic?: AppraisalLogic;
  appraisalLogic?: AppraisalLogic;
  appraisal?: AppraisalLogic;
  appraisal_scale?: AppraisalLogic;
}

interface EmployeeProfile {
  division:    string;
  department:  string;
  unit:        string;
  job_title:   string;
  job_grade:   number | string;
  grade_band:  string;
}

interface BackendResponse {
  employee_profile: EmployeeProfile;
  objectives: BackendObjective[];
  total_weight: number;
  pipeline_meta?: Record<string, unknown>;
}

interface JobAcceptedResponse {
  job_id: string;
  status: string;
  poll_url: string;
  message?: string;
}

interface JobStatusResponse {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  result?: BackendResponse;
  partial_result?: BackendResponse;
  progress?: {
    stage?: string;
    message?: string;
  };
  error?: string;
  detail?: Record<string, unknown>;
}

const POLL_INTERVAL_MS = 2000;
// Keep this comfortably above worst-case Step 3 LLM runtime.
const POLL_TIMEOUT_MS = 25 * 60 * 1000;

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function pollJobUntilDone(
  pollUrl: string,
  onProgress?: (partial: BackendResponse, progress?: JobStatusResponse['progress']) => void,
): Promise<{ data: BackendResponse; warning?: string }> {
  const started = Date.now();
  const url = pollUrl.startsWith('http') ? pollUrl : `${API_URL}${pollUrl}`;
  let latestPartial: BackendResponse | null = null;
  let latestProgress: JobStatusResponse['progress'] | undefined;

  while (Date.now() - started < POLL_TIMEOUT_MS) {
    const res = await fetch(url);
    if (!res.ok) {
      let detail: unknown = null;
      try {
        const body = await res.json();
        detail = body.detail ?? body.message ?? null;
      } catch {
        detail = res.statusText;
      }
      throw new Error(friendlyApiError(res.status, detail));
    }

    const job: JobStatusResponse = await res.json();
    if (job.partial_result) {
      latestPartial = job.partial_result;
      latestProgress = job.progress;
      onProgress?.(job.partial_result, job.progress);
    }

    if (job.status === 'completed' && job.result) {
      return { data: job.result };
    }
    if (job.status === 'failed') {
      if (latestPartial) {
        return {
          data: latestPartial,
          warning:
            latestProgress?.message ??
            'Generation partially completed. Step 3 failed, so appraisal logic was not generated for all objectives.',
        };
      }
      throw new Error(friendlyApiError(502, job.detail ?? job.error ?? 'Generation failed.'));
    }

    await sleep(POLL_INTERVAL_MS);
  }

  throw new Error(
    'Generation is still running on the server and may need more time for appraisal logic. Please wait, then click Retry to continue polling this job.',
  );
}

const APPRAISAL_RATINGS = [
  { key: 'rating_5' as const, label: '5', title: 'Outstanding',  ring: 'ring-emerald-200 dark:ring-emerald-800', bg: 'bg-emerald-50 dark:bg-emerald-900/20', badge: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' },
  { key: 'rating_4' as const, label: '4', title: 'Exceeds',      ring: 'ring-blue-200 dark:ring-blue-800',     bg: 'bg-blue-50 dark:bg-blue-900/20',     badge: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' },
  { key: 'rating_3' as const, label: '3', title: 'Meets',        ring: 'ring-amber-200 dark:ring-amber-800',   bg: 'bg-amber-50 dark:bg-amber-900/20',   badge: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' },
  { key: 'rating_2' as const, label: '2', title: 'Partially',    ring: 'ring-orange-200 dark:ring-orange-800', bg: 'bg-orange-50 dark:bg-orange-900/20', badge: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300' },
  { key: 'rating_1' as const, label: '1', title: 'Unsatisfactory', ring: 'ring-red-200 dark:ring-red-800',     bg: 'bg-red-50 dark:bg-red-900/20',       badge: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300' },
];

const EMPTY_APPRAISAL: AppraisalLogic = {
  rating_5: '', rating_4: '', rating_3: '', rating_2: '', rating_1: '',
};

function normalizeAppraisalLogic(value: unknown): AppraisalLogic | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const raw = value as Record<string, unknown>;
  const normalized: AppraisalLogic = {
    rating_5: String(raw.rating_5 ?? raw.rating5 ?? raw['5'] ?? '').trim(),
    rating_4: String(raw.rating_4 ?? raw.rating4 ?? raw['4'] ?? '').trim(),
    rating_3: String(raw.rating_3 ?? raw.rating3 ?? raw['3'] ?? '').trim(),
    rating_2: String(raw.rating_2 ?? raw.rating2 ?? raw['2'] ?? '').trim(),
    rating_1: String(raw.rating_1 ?? raw.rating1 ?? raw['1'] ?? '').trim(),
  };
  const hasAnyValue = APPRAISAL_RATINGS.some(({ key }) => normalized[key].length > 0);
  return hasAnyValue ? normalized : undefined;
}

function formatGradeBand(band: string): string {
  return band.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function uid() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }

type PipelineStage =
  | 'step1_draft'
  | 'step2_metrics'
  | 'step3_appraisal'
  | 'step3_failed'
  | 'completed'
  | null;

function stageProgressLabel(stage: PipelineStage): string {
  switch (stage) {
    case 'step1_draft':     return 'Step 1 of 3 — Drafting objectives';
    case 'step2_metrics':   return 'Step 2 of 3 — Assigning metrics & weights';
    case 'step3_appraisal': return 'Step 3 of 3 — Writing appraisal logic';
    case 'step3_failed':    return 'Step 3 failed — showing metrics without appraisal';
    default:                return 'Generation in progress…';
  }
}
function resolvePipelineStage(
  progressStage?: string,
  metaStage?: string,
): PipelineStage {
  const stage = progressStage ?? metaStage;
  if (stage === 'step1_draft') return 'step1_draft';
  if (stage === 'step2_metrics') return 'step2_metrics';
  if (stage === 'step3_appraisal') return 'step3_appraisal';
  if (stage === 'step3_failed') return 'step3_failed';
  return null;
}

function backendToFields(b: BackendObjective): Omit<LLMObjective, 'id'> {
  const appraisalLogic = normalizeAppraisalLogic(
    b.appraisal_logic ?? b.appraisalLogic ?? b.appraisal ?? b.appraisal_scale,
  );
  return {
    objective:       b.objective,
    measure:         b.measure,
    target:          b.target,
    weight_percent:  b.weight_percent,
    category:        b.category as ObjectiveCategory,
    tracking_source: b.tracking_source,
    time_frame:      b.time_frame,
    source:          b.source,
    bsc_kpi:                    b.bsc_kpi,
    bsc_strategic_objective:    b.bsc_strategic_objective,
    los_alignment:              b.los_alignment,
    appraisal_logic:            appraisalLogic,
  };
}

function mergeObjectivesFromBackend(
  backendObjs: BackendObjective[],
  prev: LLMObjective[],
): LLMObjective[] {
  return backendObjs.map((b, index) => {
    const id = prev[index]?.id ?? `row-${index}`;
    return { id, ...backendToFields(b) };
  });
}

function fromBackend(b: BackendObjective, index = 0): LLMObjective {
  return { id: `row-${index}`, ...backendToFields(b) };
}

function detailMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (typeof detail === 'object' && detail !== null) {
    const obj = detail as Record<string, unknown>;
    if (typeof obj.message === 'string') return obj.message;
  }
  return '';
}

function detailErrorCode(detail: unknown): string | null {
  if (typeof detail === 'object' && detail !== null) {
    const code = (detail as Record<string, unknown>).error;
    if (typeof code === 'string') return code;
  }
  return null;
}

function friendlyApiError(status: number, detail: unknown): string {
  const text = detailMessage(detail);
  const code = detailErrorCode(detail);

  if (code === 'server_initializing' || text.toLowerCase().includes('initializing'))
    return text || 'The server is still starting up. Please wait a moment and try again.';

  if (code === 'llm_unavailable' || text.toLowerCase().includes('llm unavailable'))
    return text || 'The AI service (Ollama) is not available. Please ensure Ollama is running, then try again.';

  if (status === 503)
    return text || 'The server is temporarily unavailable. Please try again shortly.';

  if (status === 422 && typeof detail === 'object' && detail !== null) {
    const obj = detail as Record<string, unknown>;
    if (obj.error === 'retrieval_incomplete' && typeof obj.message === 'string')
      return obj.message;
  }

  if (text.includes('Extraction failed'))
    return 'We could not find role information for your selection. Check division, department, and job title, then try again.';

  if (code === 'invalid_json' || text.includes('invalid JSON') || text.includes('JSONDecodeError'))
    return 'The AI returned an unexpected response after several attempts. Please try generating again.';

  if (text.includes('Step 1') && text.includes('drafts'))
    return 'The AI did not produce enough objective ideas. Please try again.';

  if (text.includes('Step 2') && text.includes('objectives'))
    return 'The AI did not return the full set of objectives. Please try again.';

  if (text.includes('Step 3'))
    return 'The AI did not complete appraisal ratings for all objectives. Please try again.';

  if (typeof detail === 'object' && detail !== null) {
    const obj = detail as Record<string, unknown>;
    if (Array.isArray(obj.validation_errors) && obj.validation_errors.length > 0)
      return 'Some objectives were missing required fields. Please try generating again.';
    if (typeof obj.message === 'string')
      return obj.message;
  }

  if (status === 502)
    return 'Objective generation did not complete successfully. Please try again.';
  if (status === 422)
    return text || 'Required role information is missing from the system. Please contact the PMS team.';
  if (status === 500)
    return 'Something went wrong while preparing your request. Please try again.';

  return 'We could not generate objectives this time. Please try again.';
}

async function callAPI(
  division: string, department: string, unit: string,
  jobTitle: string, jobGrade: string, count: number,
  onProgress?: (
    partial: BackendResponse,
    progress?: JobStatusResponse['progress'],
  ) => void,
): Promise<{ objectives: LLMObjective[]; employeeProfile: EmployeeProfile; warning?: string }> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/generate`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        division, department, unit,
        job_title: jobTitle, job_grade: jobGrade, num_objectives: count,
      }),
    });
  } catch {
    throw new Error(
      'Could not reach the server. If it is still starting up, wait a few seconds and try again.',
    );
  }

  if (res.status === 202) {
    const accepted: JobAcceptedResponse = await res.json();
    const { data, warning } = await pollJobUntilDone(accepted.poll_url, (partial, progress) => {
      onProgress?.(partial, progress);
    });
    return {
      objectives:      data.objectives.map((o, i) => fromBackend(o, i)),
      employeeProfile: data.employee_profile,
      warning,
    };
  }

  if (!res.ok) {
    let detail: unknown = null;
    try {
      const body = await res.json();
      detail = body.detail ?? body.message ?? null;
    } catch {
      detail = await res.text().catch(() => res.statusText);
    }
    throw new Error(friendlyApiError(res.status, detail));
  }
  const data: BackendResponse = await res.json();
  return {
    objectives:      data.objectives.map((o, i) => fromBackend(o, i)),
    employeeProfile: data.employee_profile,
    warning: undefined,
  };
}

// ── Downloads ─────────────────────────────────────────────────────────────────
function downloadCSV(
  rows: LLMObjective[],
  meta: ObjectiveSet | null,
  profile: EmployeeProfile | null,
) {
  const header = [
    '#', 'Objective', 'Measure', 'Target', 'Weight (%)', 'Category',
    'Tracking Source', 'Time Frame', 'BSC KPI', 'BSC Strategic Objective',
    'LOS Alignment', 'Rating 5', 'Rating 4', 'Rating 3', 'Rating 2', 'Rating 1',
  ];
  const esc = (s: string) => `"${s.replace(/"/g, '""')}"`;
  const body = rows.map((r, i) => {
    const a = r.appraisal_logic ?? EMPTY_APPRAISAL;
    return [
      i + 1,
      esc(r.objective),
      esc(r.measure),
      esc(r.target),
      r.weight_percent,
      esc(r.category),
      esc(r.tracking_source),
      esc(r.time_frame),
      esc(r.bsc_kpi ?? ''),
      esc(r.bsc_strategic_objective ?? ''),
      esc(r.los_alignment ?? ''),
      esc(a.rating_5), esc(a.rating_4), esc(a.rating_3), esc(a.rating_2), esc(a.rating_1),
    ];
  });
  const metaLines = [
    meta ? `Division,${meta.division}` : '',
    meta ? `Department,${meta.department}` : '',
    meta ? `Unit,${meta.unit}` : '',
    meta ? `Job Title,${meta.job_title}` : '',
    profile?.grade_band ? `Grade Band,${formatGradeBand(profile.grade_band)}` : '',
    `Generated,${new Date().toLocaleString()}`,
    '',
  ].filter(Boolean).join('\n');
  const csv  = metaLines + [header.join(','), ...body.map(r => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a'); a.href = url; a.download = 'objectives.csv'; a.click();
  URL.revokeObjectURL(url);
}

function downloadJSON(
  rows: LLMObjective[],
  meta: ObjectiveSet | null,
  profile: EmployeeProfile | null,
) {
  const payload = {
    employee_profile: profile ?? meta ?? {},
    generated_at: new Date().toISOString(),
    objectives: rows.map(({ id, ...rest }) => rest),
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a'); a.href = url; a.download = 'objectives.json'; a.click();
  URL.revokeObjectURL(url);
}

type ObjectiveFormData = {
  objective:       string;
  measure:         string;
  target:          string;
  weight_percent:  string;
  category:        string;
  tracking_source: string;
  time_frame:      string;
};

const EMPTY_FORM: ObjectiveFormData = {
  objective:       '',
  measure:         '',
  target:          '',
  weight_percent:  '',
  category:        '',
  tracking_source: '',
  time_frame:      '',
};

function formFromRow(row: LLMObjective): ObjectiveFormData {
  return {
    objective:       row.objective,
    measure:         row.measure,
    target:          row.target,
    weight_percent:  String(row.weight_percent),
    category:        row.category,
    tracking_source: row.tracking_source,
    time_frame:      row.time_frame,
  };
}

function validateForm(d: ObjectiveFormData): Partial<Record<keyof ObjectiveFormData, string>> {
  const errors: Partial<Record<keyof ObjectiveFormData, string>> = {};
  if (!d.objective.trim()) errors.objective = 'Objective is required';
  if (!d.measure.trim()) errors.measure = 'Measure is required';
  if (!d.target.trim()) errors.target = 'Target is required';
  if (!d.weight_percent.trim() || isNaN(Number(d.weight_percent)) || Number(d.weight_percent) <= 0)
    errors.weight_percent = 'Enter a valid weight greater than 0';
  if (!d.category) errors.category = 'Category is required';
  if (!d.tracking_source) errors.tracking_source = 'Tracking source is required';
  if (!d.time_frame) errors.time_frame = 'Time frame is required';
  return errors;
}

// ── Add / Edit modal ────────────────────────────────────────────────────────
function ObjectiveFormModal({
  mode, row, isCriticalRow, onSave, onClose,
}: {
  mode:           'add' | 'edit';
  row?:           LLMObjective;
  isCriticalRow?: boolean;
  onSave:         (updated: LLMObjective) => void;
  onClose:        () => void;
}) {
  const [d, setD] = useState<ObjectiveFormData>(
    mode === 'edit' && row ? formFromRow(row) : { ...EMPTY_FORM },
  );
  const [errors, setErrors] = useState<Partial<Record<keyof ObjectiveFormData, string>>>({});

  const inputCls = (field: keyof ObjectiveFormData) =>
    `w-full px-3 py-2 rounded-lg border text-sm text-slate-800 dark:text-slate-100 bg-white dark:bg-slate-700 focus:outline-none focus:ring-2 transition-all ${
      errors[field]
        ? 'border-red-400 focus:ring-red-300'
        : 'border-slate-200 dark:border-slate-600 focus:ring-purple-300'
    }`;

  const selectCls = (field: keyof ObjectiveFormData) =>
    `${inputCls(field)} ${!d[field] ? 'text-slate-400' : ''}`;

  function handleSubmit() {
    const nextErrors = validateForm(d);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    onSave({
      id:              row?.id ?? uid(),
      objective:       d.objective.trim(),
      measure:         d.measure.trim(),
      target:          d.target.trim(),
      weight_percent:  parseFloat(d.weight_percent),
      category:        d.category as ObjectiveCategory,
      tracking_source: d.tracking_source,
      time_frame:      d.time_frame,
      source:                    row?.source,
      bsc_kpi:                   row?.bsc_kpi,
      bsc_strategic_objective:   row?.bsc_strategic_objective,
      los_alignment:             row?.los_alignment,
      appraisal_logic:           row?.appraisal_logic,
    });
  }

  const isAdd = mode === 'add';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-700">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white"
              style={{ backgroundColor: '#892d8f' }}>
              {isAdd ? <Plus size={13} /> : <Edit2 size={13} />}
            </div>
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              {isAdd ? 'Add Objective' : 'Edit Objective'}
            </h2>
          </div>
          <button onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Fields */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
              Objective <span className="text-red-500">*</span>
            </label>
            <textarea rows={3} value={d.objective}
              onChange={e => { setD(p => ({ ...p, objective: e.target.value })); setErrors(p => ({ ...p, objective: undefined })); }}
              placeholder="e.g. Increase active channel users by 15% within Q2"
              className={`${inputCls('objective')} resize-none`} />
            {errors.objective && <p className="mt-1 text-xs text-red-500">{errors.objective}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Measure <span className="text-red-500">*</span>
              </label>
              <input type="text" value={d.measure}
                onChange={e => { setD(p => ({ ...p, measure: e.target.value })); setErrors(p => ({ ...p, measure: undefined })); }}
                placeholder="e.g. Percentage, Number, Quality"
                className={inputCls('measure')} />
              {errors.measure && <p className="mt-1 text-xs text-red-500">{errors.measure}</p>}
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Target <span className="text-red-500">*</span>
              </label>
              <input type="text" value={d.target}
                onChange={e => { setD(p => ({ ...p, target: e.target.value })); setErrors(p => ({ ...p, target: undefined })); }}
                placeholder="e.g. As per quarterly action plan of 100%"
                className={inputCls('target')} />
              {errors.target && <p className="mt-1 text-xs text-red-500">{errors.target}</p>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Weight (%) <span className="text-red-500">*</span>
              </label>
              <input type="number" min={0.1} max={100} step={0.1} value={d.weight_percent}
                onChange={e => { setD(p => ({ ...p, weight_percent: e.target.value })); setErrors(p => ({ ...p, weight_percent: undefined })); }}
                placeholder="e.g. 10"
                className={inputCls('weight_percent')} />
              {errors.weight_percent && <p className="mt-1 text-xs text-red-500">{errors.weight_percent}</p>}
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Category <span className="text-red-500">*</span>
              </label>
              {isCriticalRow ? (
                <div className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 text-sm bg-slate-50 dark:bg-slate-700/50 text-purple-700 dark:text-purple-300">
                  Major Critical
                  <p className="mt-1 text-xs font-normal text-slate-400 normal-case tracking-normal">
                    Fixed for the critical target row — cannot be changed.
                  </p>
                </div>
              ) : (
                <select value={d.category}
                  onChange={e => { setD(p => ({ ...p, category: e.target.value })); setErrors(p => ({ ...p, category: undefined })); }}
                  className={selectCls('category')}>
                  {isAdd && <option value="">Select category</option>}
                  {CATEGORIES.filter(c => c !== 'Major Critical').map(c => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              )}
              {errors.category && <p className="mt-1 text-xs text-red-500">{errors.category}</p>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Tracking Source <span className="text-red-500">*</span>
              </label>
              <select value={d.tracking_source}
                onChange={e => { setD(p => ({ ...p, tracking_source: e.target.value })); setErrors(p => ({ ...p, tracking_source: undefined })); }}
                className={selectCls('tracking_source')}>
                {isAdd && <option value="">Select tracking source</option>}
                <option>System</option>
                <option>Manual</option>
                <option>System &amp; Manual</option>
              </select>
              {errors.tracking_source && <p className="mt-1 text-xs text-red-500">{errors.tracking_source}</p>}
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Time Frame <span className="text-red-500">*</span>
              </label>
              <select value={d.time_frame}
                onChange={e => { setD(p => ({ ...p, time_frame: e.target.value })); setErrors(p => ({ ...p, time_frame: undefined })); }}
                className={selectCls('time_frame')}>
                {isAdd && <option value="">Select time frame</option>}
                {['Monthly', 'Quarterly', 'Annual', 'Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2'].map(o => (
                  <option key={o}>{o}</option>
                ))}
              </select>
              {errors.time_frame && <p className="mt-1 text-xs text-red-500">{errors.time_frame}</p>}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100 dark:border-slate-700">
          <button onClick={onClose}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors">
            <X size={14} />Cancel
          </button>
          <button onClick={handleSubmit}
            className="inline-flex items-center gap-2 px-4 py-2 text-white text-sm font-medium rounded-lg transition-colors"
            style={{ backgroundColor: '#892d8f' }}>
            <Check size={14} />{isAdd ? 'Add Objective' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Expandable appraisal panel ──────────────────────────────────────────────
function AppraisalExpandPanel({
  obj, onUpdate,
}: {
  obj:      LLMObjective;
  onUpdate: (updated: AppraisalLogic) => void;
}) {
  const logic = obj.appraisal_logic ?? EMPTY_APPRAISAL;
  const hasAlignment = !!(obj.bsc_kpi || obj.bsc_strategic_objective || obj.los_alignment);

  function updateRating(key: keyof AppraisalLogic, value: string) {
    onUpdate({ ...logic, [key]: value });
  }

  return (
    <div className="px-4 py-4 bg-slate-50/80 dark:bg-slate-800/50 border-t border-slate-100 dark:border-slate-700">
      {hasAlignment && (
        <div className="mb-4 flex items-start gap-2">
          <Info size={14} className="text-slate-400 mt-0.5 flex-shrink-0" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 flex-1">
            {obj.bsc_kpi && (
              <div className="rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-0.5">BSC KPI</p>
                <p className="text-xs text-slate-700 dark:text-slate-200 leading-snug">{obj.bsc_kpi}</p>
              </div>
            )}
            {obj.bsc_strategic_objective && (
              <div className="rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-0.5">Strategic Objective</p>
                <p className="text-xs text-slate-700 dark:text-slate-200 leading-snug">{obj.bsc_strategic_objective}</p>
              </div>
            )}
            {obj.los_alignment && (
              <div className="rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-0.5">LOS Alignment</p>
                <p className="text-xs text-slate-700 dark:text-slate-200 leading-snug">{obj.los_alignment}</p>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 mb-3">
        <Scale size={14} style={{ color: '#892d8f' }} />
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Appraisal Scale
        </h4>
        <span className="text-[10px] text-slate-400 normal-case tracking-normal">
          — edit rating descriptions below
        </span>
      </div>

      <div className="space-y-2.5">
        {APPRAISAL_RATINGS.map(({ key, label, title, ring, bg, badge }) => (
          <div key={key}
            className={`flex gap-3 rounded-xl border border-slate-200 dark:border-slate-600 ${bg} ring-1 ${ring} p-3 transition-shadow focus-within:ring-2 focus-within:ring-purple-300`}>
            <div className="flex flex-col items-center gap-0.5 flex-shrink-0 w-16 pt-0.5">
              <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${badge}`}>
                {label}
              </span>
              <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 text-center leading-tight">
                {title}
              </span>
            </div>
            <textarea
              rows={2}
              value={logic[key]}
              onChange={e => updateRating(key, e.target.value)}
              placeholder={`Describe what a rating of ${label} (${title}) looks like for this objective…`}
              className="flex-1 resize-none rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 leading-relaxed focus:outline-none focus:ring-2 focus:ring-purple-300 transition-all"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function GenerationProgressBanner({
  stage,
  message,
  generating,
}: {
  stage: PipelineStage;
  message: string | null;
  generating: boolean;
}) {
  if (!generating) return null;

  return (
    <div className="mb-4 flex items-start gap-3 p-4 rounded-lg border border-purple-100 dark:border-purple-800/40 bg-purple-50/60 dark:bg-purple-900/15">
      <svg className="animate-spin w-5 h-5 text-purple-600 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
      </svg>
      <div>
        <p className="text-sm font-semibold text-purple-900 dark:text-purple-100">
          {stageProgressLabel(stage)}
        </p>
        {message && (
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{message}</p>
        )}
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
  const [genProgress,   setGenProgress]   = useState<string | null>(null);
  const [pipelineStage, setPipelineStage] = useState<PipelineStage>(null);

  const [currentSet,  setCurrentSet]  = useState<ObjectiveSet | null>(null);
  const [employeeProfile, setEmployeeProfile] = useState<EmployeeProfile | null>(null);
  const [objectives,  setObjectives]  = useState<LLMObjective[]>([]);
  const [editingRow,  setEditingRow]  = useState<LLMObjective | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

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
    setGenerating(true);
    setGenError(null);
    setGenProgress(null);
    setPipelineStage(null);
    try {
      const { objectives: rows, employeeProfile: profile, warning } = await callAPI(
        division, department, unit, jobTitle, jobGrade, numObjectives,
        (partial, progress) => {
          const stage = resolvePipelineStage(
            progress?.stage,
            typeof partial.pipeline_meta?.stage === 'string'
              ? partial.pipeline_meta.stage
              : undefined,
          );
          setPipelineStage(stage);
          setEmployeeProfile(partial.employee_profile);
          setObjectives(prev => {
            const merged = mergeObjectivesFromBackend(partial.objectives, prev);
            if (stage === 'step1_draft') {
              setExpandedRows(new Set(
                merged
                  .filter(o => o.bsc_kpi || o.bsc_strategic_objective || o.los_alignment)
                  .map(o => o.id),
              ));
            }
            return merged;
          });
          setGenProgress(
            progress?.message ?? stageProgressLabel(stage),
          );
        },
      );
      if (rows.length !== numObjectives) {
        throw new Error(
          `Expected ${numObjectives} objectives but received ${rows.length}. Please try again.`,
        );
      }
      if (!isRegen || !currentSet) {
        setCurrentSet({
          id: uid(), division, department, unit, job_title: jobTitle,
          num_objectives: numObjectives, status: 'draft',
          created_at: new Date().toISOString(),
        });
      }
      setEmployeeProfile(profile);
      setObjectives(rows);
      setGenProgress(null);
      setPipelineStage('completed');
      setExpandedRows(new Set());
      if (warning) {
        setGenError(warning);
      }
    } catch (err) {
      console.error('Objective generation failed:', err);
      setGenError(err instanceof Error ? err.message : 'We could not generate objectives this time. Please try again.');
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

  function saveAdd(row: LLMObjective) {
    setObjectives(prev => [...prev, row]);
    setShowAddModal(false);
  }

  function toggleExpand(id: string) {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function updateAppraisal(id: string, appraisal_logic: AppraisalLogic) {
    setObjectives(prev => prev.map(o =>
      o.id === id ? { ...o, appraisal_logic } : o,
    ));
  }

  function openAddModal() {
    if (!currentSet) return;
    setShowAddModal(true);
  }

  const totalWeight = objectives.reduce((s, o) => s + o.weight_percent, 0);
  const weightOk    = Math.abs(totalWeight - 100) <= 1;
  const editingIndex = editingRow ? objectives.findIndex(o => o.id === editingRow.id) : -1;

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
            {generating && genProgress && (
              <p className="text-sm text-slate-500 dark:text-slate-300">{genProgress}</p>
            )}
          </div>
        </div>

        {genError && (
          <div className="mt-4 flex items-center justify-between gap-4 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
            <div className="flex items-start gap-2 text-sm text-amber-800 dark:text-amber-200">
              <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
              <span>{genError}</span>
            </div>
            <button
              onClick={() => handleGenerate(objectives.length > 0)}
              disabled={generating || !canGenerate}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors flex-shrink-0 disabled:opacity-50"
              style={{ backgroundColor: '#892d8f' }}>
              <RefreshCw size={14} className={generating ? 'animate-spin' : ''} />
              Retry
            </button>
          </div>
        )}

        {employeeProfile?.grade_band && (
          <div className="mt-4 flex items-center gap-3 p-3 rounded-lg border border-purple-100 dark:border-purple-800/40 bg-purple-50/60 dark:bg-purple-900/15">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white flex-shrink-0"
              style={{ backgroundColor: '#892d8f' }}>
              <Scale size={14} />
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Resolved Grade Band</p>
              <p className="text-sm font-semibold text-purple-800 dark:text-purple-200">
                {formatGradeBand(employeeProfile.grade_band)}
                {employeeProfile.job_grade != null && (
                  <span className="ml-2 text-xs font-normal text-slate-500 dark:text-slate-400">
                    (JG-{employeeProfile.job_grade})
                  </span>
                )}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* ── Results table ─────────────────────────────────────────────────── */}
      {objectives.length > 0 && (
        <div>
          <GenerationProgressBanner
            stage={pipelineStage}
            message={genProgress}
            generating={generating}
          />

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
              <button onClick={openAddModal}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors">
                <Plus size={14}/>Add Row
              </button>
              <button onClick={() => downloadCSV(objectives, currentSet, employeeProfile)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors">
                <Download size={14}/>CSV
              </button>
              <button onClick={() => downloadJSON(objectives, currentSet, employeeProfile)}
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
                      { label: '',          cls: 'w-8'   },
                      { label: '#',         cls: 'w-10'  },
                      { label: 'Objective', cls: 'w-72'  },
                      { label: 'Measure',   cls: 'w-24'  },
                      { label: 'Target',    cls: 'w-52'  },
                      { label: 'Weight (%)',cls: 'w-28'  },
                      { label: 'Category',  cls: 'w-36'  },
                      { label: 'Actions',   cls: 'w-24'  },
                    ].map(c => (
                      <th key={c.label || 'expand'}
                        className={`text-left px-4 py-3 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap ${c.cls}`}>
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {objectives.map((obj, idx) => {
                    const isExpanded = expandedRows.has(obj.id);
                    const hasAppraisal = !!obj.appraisal_logic;
                    const hasAlignment = !!(obj.bsc_kpi || obj.bsc_strategic_objective || obj.los_alignment);
                    return (
                    <Fragment key={obj.id}>
                    <tr
                      className="hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors group align-top">

                      {/* Expand toggle */}
                      <td className="px-2 py-3.5">
                        <button
                          onClick={() => toggleExpand(obj.id)}
                          title={isExpanded ? 'Collapse details' : 'Expand BSC / LOS / appraisal details'}
                          className={`p-1.5 rounded-lg transition-all ${
                            isExpanded
                              ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300'
                              : 'text-slate-400 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20'
                          }`}>
                          <ChevronRight size={16}
                            className={`transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`} />
                        </button>
                      </td>

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
                        {obj.category === 'Major Critical' && (
                          <span className="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                            📌 Critical Target
                          </span>
                        )}
                        {hasAlignment && !isExpanded && (
                          <button
                            onClick={() => toggleExpand(obj.id)}
                            className="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors">
                            <Info size={10} /> View details
                          </button>
                        )}
                        {hasAppraisal && !isExpanded && (
                          <button
                            onClick={() => toggleExpand(obj.id)}
                            className="mt-1.5 ml-1 inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors">
                            <Scale size={10} /> View appraisal scale
                          </button>
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

                      {/* Category */}
                      <td className="px-4 py-3.5">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${categoryBadgeCls(obj.category)}`}>
                          {obj.category}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3.5">
                        {!generating && (
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
                        )}
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr>
                        <td colSpan={8} className="p-0">
                          <AppraisalExpandPanel
                            obj={obj}
                            onUpdate={logic => updateAppraisal(obj.id, logic)}
                          />
                        </td>
                      </tr>
                    )}
                    </Fragment>
                    );
                  })}
                </tbody>

                {/* Total weight footer */}
                <tfoot>
                  <tr className="bg-slate-50 dark:bg-slate-700/30 border-t-2 border-slate-200 dark:border-slate-600">
                    <td className="px-4 py-3" colSpan={5}>
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
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-2">
            {genError ? 'Generation Unsuccessful' : 'No Objectives Generated Yet'}
          </h3>
          <p className="text-sm text-slate-500 max-w-sm mx-auto">
            {genError
              ? genError
              : 'Select your division, department, job title, and number of objectives, then click "Generate Objectives".'}
          </p>
        </div>
      )}

      {/* Add / Edit modals */}
      {showAddModal && (
        <ObjectiveFormModal
          mode="add"
          onSave={saveAdd}
          onClose={() => setShowAddModal(false)}
        />
      )}
      {editingRow && (
        <ObjectiveFormModal
          mode="edit"
          row={editingRow}
          isCriticalRow={editingIndex === 0}
          onSave={saveEdit}
          onClose={() => setEditingRow(null)}
        />
      )}
    </Layout>
  );
}
