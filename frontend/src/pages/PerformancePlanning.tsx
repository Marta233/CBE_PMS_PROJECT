// PerformancePlanning.tsx — Table shows EXACTLY what LLM returns, per-row edit modal

import { useEffect, useMemo, useRef, useState, Fragment } from 'react';
import {
  Sparkles, Plus, ChevronDown, ChevronRight, Save, Edit2, Trash2,
  RefreshCw, AlertCircle, Target, X, Check, Download, Scale, Info,
} from 'lucide-react';
import Layout from '../components/Layout';
import {
  DEPARTMENTS, UNITS,
  type ObjectiveSet,
} from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

function getAccessToken(): string | null {
  return localStorage.getItem('pms_access_token');
}

async function apiFetch(path: string, init?: RequestInit) {
  const token = getAccessToken();
  const headers = new Headers(init?.headers || {});
  headers.set('Content-Type', headers.get('Content-Type') || 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  return res;
}

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
// Backend runs 3 sequential LLM steps (draft, metrics, appraisal), each with
// its own timeout (see config.py: OLLAMA_TIMEOUT_SECONDS / STEP3_OLLAMA_TIMEOUT_SECONDS,
// default 600s each = 1800s / 30 min worst case). Keep this comfortably above
// that combined worst case, not just Step 3 alone.
const POLL_TIMEOUT_MS = 40 * 60 * 1000;

interface MeResponse {
  id: number;
  email: string;
  name: string;
  roles: string[];
  assignments: Array<{ role: string; scope_type: string; scope_id: number | null }>;
  manager_scope?: {
    unit_id: number;
    unit_name: string;
    department: string;
    division: string;
  } | null;
  director_scope?: {
    departments: string[];
    division: string;
  } | null;
}

interface ObjectiveSetApi {
  id: number;
  unit_id: number;
  cycle_id: number;
  status: string;
  current_version: number;
  position_statuses?: { position_id: number; status: string }[];
}

interface PositionRow {
  id: number;
  unit_id: number;
  title: string;
  grade_level: number | null;
}

function positionStatusForSet(set: ObjectiveSetApi | null | undefined, positionId: number): string | null {
  if (!set?.position_statuses) return null;
  return set.position_statuses.find(p => p.position_id === positionId)?.status ?? null;
}

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
  onJobAccepted?: (pollUrl: string) => void,
  resumePollUrl?: string,
): Promise<{ objectives: LLMObjective[]; employeeProfile: EmployeeProfile; warning?: string }> {
  if (resumePollUrl) {
    const { data, warning } = await pollJobUntilDone(resumePollUrl, (partial, progress) => {
      onProgress?.(partial, progress);
    });
    return {
      objectives:      data.objectives.map((o, i) => fromBackend(o, i)),
      employeeProfile: data.employee_profile,
      warning,
    };
  }

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
    onJobAccepted?.(accepted.poll_url);
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
  const OBJ_COLS = 6;       // #, Objective, Measure, Target, Weight (%), Category
  const APPRAISAL_COLS = 7; // #, Objective, Rating 5..Rating 1

  const esc = (s: string) => `"${(s ?? '').replace(/"/g, '""')}"`;
  const pad = (cells: (string | number)[], width: number): (string | number)[] => {
    const out = [...cells];
    while (out.length < width) out.push('');
    return out;
  };
  const row = (cells: (string | number)[], width: number) => pad(cells, width).join(',');

  const now = new Date();
  const datePart = `${String(now.getDate()).padStart(2, '0')}/${String(now.getMonth() + 1).padStart(2, '0')}/${now.getFullYear()}`;
  const timePart = now.toTimeString().split(' ')[0];

  const lines: string[] = [];

  if (meta) {
    lines.push(row(['Division', esc(meta.division)], OBJ_COLS));
    lines.push(row(['Department', esc(meta.department)], OBJ_COLS));
    lines.push(row(['Unit', esc(meta.unit)], OBJ_COLS));
    lines.push(row(['Job Title', esc(meta.job_title)], OBJ_COLS));
  }
  if (profile?.grade_band) {
    lines.push(row(['Grade Band', esc(formatGradeBand(profile.grade_band))], OBJ_COLS));
  }
  lines.push(row(['Generated', datePart, timePart], OBJ_COLS));
  lines.push(row([''], OBJ_COLS));

  lines.push(row(['#', 'Objective', 'Measure', 'Target', 'Weight (%)', 'Category'], OBJ_COLS));
  rows.forEach((r, i) => {
    lines.push(row([
      i + 1, esc(r.objective), esc(r.measure), esc(r.target), r.weight_percent, esc(r.category),
    ], OBJ_COLS));
  });

  lines.push(row([''], OBJ_COLS));
  lines.push(row(['Appraisal'], OBJ_COLS));
  lines.push(row([
    '#', 'Objective',
    ...APPRAISAL_RATINGS.map(rt => `Rating ${rt.label} - ${rt.title}`),
  ], APPRAISAL_COLS));
  rows.forEach((r, i) => {
    const a = r.appraisal_logic ?? EMPTY_APPRAISAL;
    lines.push(row([
      i + 1, esc(r.objective),
      esc(a.rating_5), esc(a.rating_4), esc(a.rating_3), esc(a.rating_2), esc(a.rating_1),
    ], APPRAISAL_COLS));
  });

  const csv = lines.join('\n');
  // Prepend a UTF-8 BOM. Without it, Excel assumes the system codepage
  // (e.g. Windows-1252) instead of UTF-8 and renders multi-byte characters
  // like em dashes (—) as mojibake (â€”).
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
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
              placeholder={`Describe what a rating of ${label} (${title}) looks like for this objective`}
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
export default function PerformancePlanning({ mode = 'manager' }: { mode?: 'manager' | 'director' }) {
  const isDirectorMode = mode === 'director';
  const [authError, setAuthError] = useState<string | null>(null);
  const [directorDepartments, setDirectorDepartments] = useState<string[]>([]);
  const [unitsInScope, setUnitsInScope] = useState<Array<{ id: number; name: string; department: string; division: string }>>([]);
  const [selectedUnitId, setSelectedUnitId] = useState<number | null>(null);
  const [apiSet, setApiSet] = useState<ObjectiveSetApi | null>(null);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [selectedPositionId, setSelectedPositionId] = useState<number | ''>('');

  const [division,      setDivision]      = useState('');
  const [department,    setDepartment]    = useState('');
  const [unit,          setUnit]          = useState('');
  const [jobTitle,      setJobTitle]      = useState('');
  const [jobGrade,      setJobGrade]      = useState('');
  const [numObjectives, setNumObjectives] = useState(5);
  const [generating,    setGenerating]    = useState(false);
  const [generatingPositionId, setGeneratingPositionId] = useState<number | null>(null);
  const [genError,      setGenError]      = useState<string | null>(null);
  const [genProgress,   setGenProgress]   = useState<string | null>(null);
  const [pipelineStage, setPipelineStage] = useState<PipelineStage>(null);
  // Tracks the poll_url of a job that timed out on the client but may still
  // be running on the server, keyed by position id. Retry resumes this job
  // instead of submitting a duplicate /api/generate request.
  const pendingJobRef = useRef<Record<number, string>>({});

  const [currentSet,  setCurrentSet]  = useState<ObjectiveSet | null>(null);
  const [employeeProfile, setEmployeeProfile] = useState<EmployeeProfile | null>(null);
  const [objectives,  setObjectives]  = useState<LLMObjective[]>([]);
  const [objectivesByPosition, setObjectivesByPosition] = useState<Record<number, LLMObjective[]>>({});
  const [editingRow,  setEditingRow]  = useState<LLMObjective | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [savingDraft, setSavingDraft] = useState(false);
  const [submittingToDirector, setSubmittingToDirector] = useState(false);
  const [submissionNotice, setSubmissionNotice] = useState<string | null>(null);
  const [contentDirty, setContentDirty] = useState(false);

  const selectedPositionIdRef = useRef(selectedPositionId);
  const generatingPositionIdRef = useRef<number | null>(null);
  const contentDirtyRef = useRef(false);
  selectedPositionIdRef.current = selectedPositionId;
  generatingPositionIdRef.current = generatingPositionId;
  contentDirtyRef.current = contentDirty;

  const selectedPosition = useMemo(
    () => positions.find(p => p.id === selectedPositionId) || null,
    [positions, selectedPositionId],
  );
  const generatingPosition = useMemo(
    () => (generatingPositionId == null ? null : positions.find(p => p.id === generatingPositionId) || null),
    [positions, generatingPositionId],
  );
  const viewingGeneratingPosition =
    generating && generatingPositionId != null && generatingPositionId === selectedPositionId;

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      const token = getAccessToken();
      if (!token) {
        setAuthError('Not logged in. Please log in to continue.');
        return;
      }

      try {
        const meRes = await apiFetch('/api/auth/me');
        if (!meRes.ok) throw new Error('Failed to load session.');
        const meJson = (await meRes.json()) as MeResponse;
        if (cancelled) return;

        if (meJson.manager_scope) {
          setDivision(meJson.manager_scope.division);
          setDepartment(meJson.manager_scope.department);
          setUnit(meJson.manager_scope.unit_name);
        }

        if (isDirectorMode) {
          if (!meJson.director_scope) {
            throw new Error('Director scope is not configured for your account.');
          }
          setDirectorDepartments(meJson.director_scope.departments);
          setDivision(meJson.director_scope.division);
          if (meJson.director_scope.departments.length === 1) {
            setDepartment(meJson.director_scope.departments[0]);
          }
          const unitsRes = await apiFetch('/api/objective-sets/units');
          if (!unitsRes.ok) throw new Error('Failed to load units in your scope.');
          const unitsJson = await unitsRes.json() as Array<{ id: number; name: string; department: string; division: string }>;
          if (cancelled) return;
          setUnitsInScope(unitsJson);
          return;
        }

        // Create-or-get the manager's unit objective set (active cycle).
        const setRes = await apiFetch('/api/objective-sets', { method: 'POST', body: JSON.stringify({}) });
        if (!setRes.ok) throw new Error('Failed to create objective set.');
        const setJson = (await setRes.json()) as ObjectiveSetApi;
        if (cancelled) return;
        setApiSet(setJson);

        // Load positions for the manager's unit.
        const posRes = await apiFetch(`/api/objective-sets/positions?unit_id=${setJson.unit_id}`);
        if (!posRes.ok) throw new Error('Failed to load positions.');
        const posJson = (await posRes.json()) as PositionRow[];
        if (cancelled) return;
        setPositions(posJson);

      } catch (e) {
        if (cancelled) return;
        setAuthError(e instanceof Error ? e.message : 'Failed to initialize session.');
      }
    }

    boot();
    return () => {
      cancelled = true;
    };
  }, [isDirectorMode]);

  async function loadDirectorUnitWorkspace(unitName: string) {
    const unitRow = unitsInScope.find(u => u.name === unitName);
    if (!unitRow) return;
    setUnit(unitName);
    setDivision(unitRow.division);
    setDepartment(unitRow.department);
    setSelectedUnitId(unitRow.id);
    setSelectedPositionId('');
    setObjectives([]);
    setObjectivesByPosition({});
    setContentDirty(false);
    setApiSet(null);

    const setRes = await apiFetch(`/api/objective-sets/by-unit/${unitRow.id}`, { method: 'POST', body: '{}' });
    if (!setRes.ok) {
      let detail = '';
      try {
        const j = await setRes.json();
        detail = typeof j?.detail === 'string' ? j.detail : '';
      } catch {
        detail = await setRes.text();
      }
      throw new Error(detail || 'Failed to open objective set for this unit.');
    }
    const setJson = await setRes.json() as ObjectiveSetApi;
    setApiSet(setJson);

    const posRes = await apiFetch(`/api/objective-sets/positions?unit_id=${unitRow.id}`);
    if (!posRes.ok) {
      let detail = '';
      try {
        const j = await posRes.json();
        detail = typeof j?.detail === 'string' ? j.detail : '';
      } catch {
        detail = await posRes.text();
      }
      throw new Error(detail || 'Failed to load positions for this unit.');
    }
    setPositions(await posRes.json() as PositionRow[]);
  }

  useEffect(() => {
    if (!submissionNotice) return;
    const timer = window.setTimeout(() => setSubmissionNotice(null), 3500);
    return () => window.clearTimeout(timer);
  }, [submissionNotice]);

  useEffect(() => {
    let cancelled = false;
    async function loadSetDetail() {
      if (!apiSet || selectedPositionId === '') return;
      try {
        const res = await apiFetch(`/api/objective-sets/${apiSet.id}`);
        if (!res.ok) return;
        const json = await res.json() as {
          objectives?: Array<{ position_id: number } & Record<string, unknown>>;
          position_statuses?: { position_id: number; status: string }[];
          status?: string;
          current_version?: number;
        };
        if (!cancelled && json.position_statuses) {
          setApiSet(prev => prev ? {
            ...prev,
            status: json.status ?? prev.status,
            current_version: json.current_version ?? prev.current_version,
            position_statuses: json.position_statuses,
          } : prev);
        }
        const grouped: Record<number, LLMObjective[]> = {};
        const rows = (json.objectives || []) as any[];
        for (const r of rows) {
          const pid = Number(r.position_id);
          const obj: LLMObjective = {
            id: uid(),
            objective: String(r.goal_statement ?? ''),
            measure: String(r.measurement ?? ''),
            target: String(r.target ?? ''),
            weight_percent: Number(r.weight ?? 0),
            category: (r.category ?? 'Can Exceed') as ObjectiveCategory,
            tracking_source: String(r.tracking_source ?? ''),
            time_frame: String(r.time_frame ?? ''),
            bsc_kpi: r.bsc_link ? String(r.bsc_link) : undefined,
            bsc_strategic_objective: r.strategy_link ? String(r.strategy_link) : undefined,
            los_alignment: r.los_alignment ? String(r.los_alignment) : undefined,
            appraisal_logic: (r.rating_guidance_json ?? undefined) as AppraisalLogic | undefined,
          };
          grouped[pid] = grouped[pid] || [];
          grouped[pid].push(obj);
        }
        if (cancelled) return;
        const inFlightId = generatingPositionIdRef.current;
        const viewingId = Number(selectedPositionId);
        let preferredForView: LLMObjective[] = grouped[viewingId] || [];
        setObjectivesByPosition(prev => {
          const next = { ...grouped };
          // Keep in-progress / just-generated local rows the server does not have yet.
          if (inFlightId != null && prev[inFlightId]?.length) {
            next[inFlightId] = prev[inFlightId];
          }
          if (contentDirtyRef.current) {
            for (const [pid, rows] of Object.entries(prev)) {
              const id = Number(pid);
              if (rows.length > 0 && (!next[id] || next[id].length === 0)) {
                next[id] = rows;
              }
            }
          }
          preferredForView = next[viewingId] || [];
          return next;
        });
        if (inFlightId != null && viewingId === inFlightId) {
          // Leave the live streaming table alone while this position is generating.
          return;
        }
        setObjectives(preferredForView);
        if (!contentDirtyRef.current) {
          setContentDirty(false);
        }
      } catch {
        // Non-fatal: keep local state.
      }
    }
    loadSetDetail();
    return () => { cancelled = true; };
  }, [apiSet, selectedPositionId]);

  const availableDepartments = useMemo(() => {
    if (isDirectorMode && directorDepartments.length > 0) return directorDepartments;
    return division ? DEPARTMENTS[division] || [] : [];
  }, [isDirectorMode, directorDepartments, division]);
  const availableUnits = useMemo(() => {
    if (isDirectorMode) {
      return unitsInScope
        .filter(u => !department || u.department === department)
        .map(u => u.name);
    }
    return department ? UNITS[department] || [] : [];
  }, [isDirectorMode, unitsInScope, department]);
  // Job titles are derived from the selected position (unit scope).

  const canGenerate = !!(
    division && department && unit && selectedPosition && apiSet
    && (!isDirectorMode || selectedUnitId)
  );

  function handlePositionChange(rawId: string) {
    const id = rawId ? Number(rawId) : '';
    setSelectedPositionId(id);
    if (id === '') {
      setObjectives([]);
      setJobTitle('');
      setJobGrade('');
      return;
    }
    const pos = positions.find(p => p.id === id);
    if (pos) {
      setJobTitle(pos.title);
      setJobGrade(pos.grade_level != null ? String(pos.grade_level) : '');
      setObjectives(objectivesByPosition[id] || []);
    }
  }

  async function handleGenerate(isRegen = false, isRetry = false) {
    if (!canGenerate || generateLocked) return;
    const pos = selectedPosition;
    if (!pos || selectedPositionId === '') {
      setGenError('Please select a position.');
      return;
    }
    const genPosId = Number(selectedPositionId);
    const genPosTitle = pos.title;
    const effectiveJobTitle = pos.title;
    const effectiveJobGrade = jobGrade;
    const effectiveNumObjectives = numObjectives;
    const effectiveDivision = division;
    const effectiveDepartment = department;
    const effectiveUnit = unit;
    const resumeUrl = isRetry ? pendingJobRef.current[genPosId] : undefined;

    setGenerating(true);
    setGeneratingPositionId(genPosId);
    setContentDirty(true);
    setGenError(null);
    setGenProgress(resumeUrl ? 'Reconnecting to your in-progress generation…' : null);
    setPipelineStage(null);
    setJobTitle(effectiveJobTitle);

    try {
      const { objectives: rows, employeeProfile: profile, warning } = await callAPI(
        effectiveDivision, effectiveDepartment, effectiveUnit,
        effectiveJobTitle, effectiveJobGrade, effectiveNumObjectives,
        (partial, progress) => {
          const stage = resolvePipelineStage(
            progress?.stage,
            typeof partial.pipeline_meta?.stage === 'string'
              ? partial.pipeline_meta.stage
              : undefined,
          );
          setPipelineStage(stage);
          setGenProgress(progress?.message ?? stageProgressLabel(stage));

          setObjectivesByPosition(prev => {
            const merged = mergeObjectivesFromBackend(partial.objectives, prev[genPosId] || []);
            if (selectedPositionIdRef.current === genPosId) {
              setEmployeeProfile(partial.employee_profile);
              setObjectives(merged);
              if (stage === 'step1_draft') {
                setExpandedRows(new Set(
                  merged
                    .filter(o => o.bsc_kpi || o.bsc_strategic_objective || o.los_alignment)
                    .map(o => o.id),
                ));
              }
            }
            return { ...prev, [genPosId]: merged };
          });
        },
        (pollUrl) => { pendingJobRef.current[genPosId] = pollUrl; },
        resumeUrl,
      );
      delete pendingJobRef.current[genPosId];
      if (rows.length !== effectiveNumObjectives) {
        throw new Error(
          `Expected ${effectiveNumObjectives} objectives but received ${rows.length}. Please try again.`,
        );
      }
      if (!isRegen || !currentSet) {
        setCurrentSet({
          id: uid(),
          division: effectiveDivision,
          department: effectiveDepartment,
          unit: effectiveUnit,
          job_title: effectiveJobTitle,
          num_objectives: effectiveNumObjectives,
          status: 'draft',
          created_at: new Date().toISOString(),
        });
      }
      setObjectivesByPosition(prev => ({ ...prev, [genPosId]: rows }));
      if (selectedPositionIdRef.current === genPosId) {
        setEmployeeProfile(profile);
        setObjectives(rows);
        setExpandedRows(new Set());
        setGenProgress(null);
        setPipelineStage('completed');
        if (warning) setGenError(warning);
      } else {
        setSubmissionNotice(`Objectives ready for ${genPosTitle}. Switch back to that position to review.`);
        if (warning) setGenError(`${genPosTitle}: ${warning}`);
      }
    } catch (err) {
      console.error('Objective generation failed:', err);
      // Keep pendingJobRef intact on failure — the job may still be running
      // server-side, and the Retry button should reconnect to it rather
      // than submit a duplicate request.
      const message = err instanceof Error ? err.message : 'We could not generate objectives this time. Please try again.';
      if (selectedPositionIdRef.current === genPosId) {
        setGenError(message);
      } else {
        setGenError(`${genPosTitle}: ${message}`);
      }
    } finally {
      setGenerating(false);
      setGeneratingPositionId(null);
    }
  }

  function saveEdit(updated: LLMObjective) {
    setContentDirty(true);
    setObjectives(prev => prev.map(o => o.id === updated.id ? updated : o));
    if (selectedPositionId !== '') {
      setObjectivesByPosition(prev => ({
        ...prev,
        [Number(selectedPositionId)]: (prev[Number(selectedPositionId)] || []).map(o => o.id === updated.id ? updated : o),
      }));
    }
    setEditingRow(null);
  }

  function deleteRow(id: string) {
    setContentDirty(true);
    setObjectives(prev => prev.filter(o => o.id !== id));
    if (selectedPositionId !== '') {
      setObjectivesByPosition(prev => ({
        ...prev,
        [Number(selectedPositionId)]: (prev[Number(selectedPositionId)] || []).filter(o => o.id !== id),
      }));
    }
  }

  function saveAdd(row: LLMObjective) {
    setContentDirty(true);
    setObjectives(prev => [...prev, row]);
    if (selectedPositionId !== '') {
      setObjectivesByPosition(prev => ({
        ...prev,
        [Number(selectedPositionId)]: [...(prev[Number(selectedPositionId)] || []), row],
      }));
    }
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
    setContentDirty(true);
    setObjectives(prev => prev.map(o =>
      o.id === id ? { ...o, appraisal_logic } : o,
    ));
  }

  function openAddModal() {
    if (!currentSet) return;
    setShowAddModal(true);
  }

  function buildObjectiveSavePayload() {
    if (!selectedPositionId) return null;
    const allObjectives = Object.entries(objectivesByPosition).flatMap(([pid, rows]) =>
      rows.map((o) => ({
        position_id: Number(pid),
        goal_statement: o.objective,
        measurement: o.measure,
        target: o.target,
        weight: Math.round(o.weight_percent),
        category: o.category,
        tracking_source: o.tracking_source,
        time_frame: o.time_frame,
        rating_guidance_json: o.appraisal_logic ?? null,
        bsc_link: o.bsc_kpi ?? null,
        strategy_link: o.bsc_strategic_objective ?? null,
        los_alignment: o.los_alignment ?? null,
      })),
    );

    // Also include the currently visible objectives, even if the user hasn't switched positions yet.
    const pid = Number(selectedPositionId);
    const merged = new Map<string, any>();
    for (const row of [...allObjectives, ...objectives.map(o => ({
      position_id: pid,
      goal_statement: o.objective,
      measurement: o.measure,
      target: o.target,
      weight: Math.round(o.weight_percent),
      category: o.category,
      tracking_source: o.tracking_source,
      time_frame: o.time_frame,
      rating_guidance_json: o.appraisal_logic ?? null,
      bsc_link: o.bsc_kpi ?? null,
      strategy_link: o.bsc_strategic_objective ?? null,
      los_alignment: o.los_alignment ?? null,
    }))]) {
      merged.set(`${row.position_id}:${row.goal_statement}:${row.measurement}:${row.target}`, row);
    }

    return {
      objectives: Array.from(merged.values()),
      position_ids: Number.isFinite(pid) ? [pid] : [],
      snapshot_json: {
        division,
        department,
        unit,
        saved_from: 'frontend',
        employee_profile: employeeProfile,
      },
    };
  }

  function positionStatus(positionId: number | '' | null | undefined): string | null {
    if (positionId === '' || positionId == null) return null;
    return positionStatusForSet(apiSet, Number(positionId));
  }

  async function saveDraftOnly() {
    if (!apiSet) {
      setGenError('No objective set is available for your session.');
      return;
    }
    if (!selectedPositionId) {
      setGenError('Please select a position first.');
      return;
    }
    try {
      setSavingDraft(true);
      setGenError(null);
      setSubmissionNotice(null);
      const payload = buildObjectiveSavePayload();
      if (!payload) {
        throw new Error('Please select a position first.');
      }

      const saveRes = await apiFetch(`/api/objective-sets/${apiSet.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      if (!saveRes.ok) {
        let detail = '';
        try {
          const j = await saveRes.json();
          detail = typeof j?.detail === 'string' ? j.detail : '';
        } catch {
          detail = await saveRes.text();
        }
        throw new Error(detail || 'Failed to save objective set.');
      }
      const savedSet = (await saveRes.json()) as ObjectiveSetApi;
      setApiSet(savedSet);
      setContentDirty(false);
      const posStatus = positionStatusForSet(savedSet, Number(selectedPositionId));
      setGenProgress('Draft saved. You can continue editing or submit to Director when ready.');
      setSubmissionNotice(
        isDirectorMode
          ? 'Objectives saved for the unit manager. They can review and submit to Director Review.'
          : posStatus === 'saved' || !posStatus
            ? 'Draft saved successfully. Submit to Director when weights total 100%.'
            : 'Draft saved successfully. This position remains editable until you submit it to Director.',
      );
    } catch (e) {
      setGenError(e instanceof Error ? e.message : 'Failed to save draft.');
    } finally {
      setSavingDraft(false);
    }
  }

  async function submitToDirector() {
    if (!apiSet) {
      setGenError('No objective set is available for your session.');
      return;
    }
    if (!selectedPositionId) {
      setGenError('Please select a position first.');
      return;
    }
    const posId = Number(selectedPositionId);
    if (!window.confirm('Submit this position to Unit Director? You will no longer be able to edit it as manager.')) {
      return;
    }
    try {
      setSubmittingToDirector(true);
      setGenError(null);
      setSubmissionNotice(null);

      const payload = buildObjectiveSavePayload();
      if (!payload) {
        throw new Error('Please select a position first.');
      }
      const saveRes = await apiFetch(`/api/objective-sets/${apiSet.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      if (!saveRes.ok) {
        let detail = '';
        try {
          const j = await saveRes.json();
          detail = typeof j?.detail === 'string' ? j.detail : '';
        } catch {
          detail = await saveRes.text();
        }
        throw new Error(detail || 'Failed to save objective set before submission.');
      }
      const savedSet = (await saveRes.json()) as ObjectiveSetApi;
      setApiSet(savedSet);

      const actRes = await apiFetch(`/api/objective-sets/${apiSet.id}/activate`, {
        method: 'POST',
        body: JSON.stringify({ position_ids: [posId] }),
      });
      if (!actRes.ok) {
        let detail = '';
        try {
          const j = await actRes.json();
          detail = typeof j?.detail === 'string' ? j.detail : '';
        } catch {
          detail = await actRes.text();
        }
        if (detail.includes('invalid transition for your role')) {
          const st = positionStatusForSet(savedSet, posId);
          const statusHint = st ? ` Current status: ${st.replaceAll('_', ' ')}.` : '';
          setGenProgress('Could not submit this position from its current workflow status.');
          setSubmissionNotice(
            `Submit failed because this position is not ready for Director submission.${statusHint}`,
          );
          return;
        }
        throw new Error(detail || 'Failed to activate objective set.');
      }
      const activatedSet = (await actRes.json()) as ObjectiveSetApi;
      setApiSet(activatedSet);
      setContentDirty(false);

      setCurrentSet(s => s ? { ...s, status: 'active' } : s);
      setGenProgress('Saved and sent to Unit Director for approval.');
      setSubmissionNotice('This position is now in Director Review and remains viewable here as read-only.');
    } catch (e) {
      setGenError(e instanceof Error ? e.message : 'Failed to submit to Director.');
    } finally {
      setSubmittingToDirector(false);
    }
  }

  const totalWeight = objectives.reduce((s, o) => s + o.weight_percent, 0);
  const weightOk    = Math.abs(totalWeight - 100) <= 1;
  const editingIndex = editingRow ? objectives.findIndex(o => o.id === editingRow.id) : -1;
  const positionHasObjectives = objectives.length > 0;
  const selectedPosStatus = positionStatus(selectedPositionId);
  const inDirectorQueue =
    selectedPosStatus === 'activated_to_director' ||
    selectedPosStatus === 'vp_rejected_to_director';
  const pastDirectorApproval =
    selectedPosStatus === 'director_approved_and_activated_to_vp' ||
    selectedPosStatus === 'vp_approved_final' ||
    selectedPosStatus === 'sent_to_pms';
  const alreadySubmittedByManager =
    !viewingGeneratingPosition &&
    !contentDirty &&
    weightOk &&
    positionHasObjectives &&
    (inDirectorQueue || pastDirectorApproval);
  const needsResubmit =
    contentDirty &&
    (selectedPosStatus === 'activated_to_director' ||
      selectedPosStatus === 'director_rejected_to_manager');
  // Lock generate only for the selected position that already has submitted objectives.
  const setSubmittedToDirector =
    !isDirectorMode &&
    inDirectorQueue &&
    !contentDirty &&
    positionHasObjectives;
  const generateLocked = isDirectorMode
    ? (generating || submittingToDirector)
    : (setSubmittedToDirector
      || (pastDirectorApproval && !contentDirty && positionHasObjectives)
      || submittingToDirector
      || generating);
  const managerReadOnly = isDirectorMode
    ? (viewingGeneratingPosition || submittingToDirector)
    : (alreadySubmittedByManager || submittingToDirector || viewingGeneratingPosition);
  const saveBusy = savingDraft || submittingToDirector || viewingGeneratingPosition;
  const submitDisabled = saveBusy || alreadySubmittedByManager || !weightOk;
  const submitLabel = viewingGeneratingPosition
    ? 'Generating...'
    : submittingToDirector
      ? 'Submitting...'
      : alreadySubmittedByManager
        ? selectedPosStatus === 'director_approved_and_activated_to_vp'
          ? 'Already with VP'
          : selectedPosStatus === 'vp_approved_final' || selectedPosStatus === 'sent_to_pms'
            ? 'Finalized'
            : 'Submitted to Director'
        : needsResubmit
          ? 'Resubmit to Director'
          : 'Submit to Director';

  return (
    <Layout title="Performance Planning">

      {authError && (
        <div className="mb-6 p-4 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50/60 dark:bg-red-900/15 text-sm text-red-700 dark:text-red-200">
          {authError}
        </div>
      )}
      {submissionNotice && (
        <div className="fixed top-4 right-4 z-50 max-w-md p-3 rounded-lg border border-emerald-200 dark:border-emerald-800/40 bg-emerald-50/95 dark:bg-emerald-900/90 text-sm text-emerald-800 dark:text-emerald-200 shadow-lg">
          {submissionNotice}
        </div>
      )}
      {generating && generatingPosition && !viewingGeneratingPosition && (
        <div className="mb-4 flex items-center justify-between gap-3 p-3 rounded-lg border border-purple-200 dark:border-purple-800/40 bg-purple-50/70 dark:bg-purple-900/20">
          <div className="flex items-start gap-2 text-sm text-purple-900 dark:text-purple-100 min-w-0">
            <svg className="animate-spin w-4 h-4 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
            </svg>
            <div className="min-w-0">
              <p className="font-medium">
                Generating in background for {generatingPosition.title}
              </p>
              {genProgress && (
                <p className="mt-0.5 text-xs text-purple-700/80 dark:text-purple-200/80">{genProgress}</p>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => handlePositionChange(String(generatingPosition.id))}
            className="text-xs font-semibold text-purple-700 dark:text-purple-200 hover:underline flex-shrink-0"
          >
            View progress
          </button>
        </div>
      )}

      {/* ── Config panel ──────────────────────────────────────────────────── */}
      <div className="card p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <Sparkles size={18} style={{ color: '#892d8f' }} />
          <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">
            {unit
              ? <>Planning for <span style={{ color: '#892d8f' }}>{unit}</span>: Objective Generation</>
              : 'Objective Generation'}
          </h2>
        </div>

        {/* Org context — only show known facts (never blank dashes) */}
        {(() => {
          const facts = [
            { label: 'Division', value: division },
            { label: 'Department', value: department },
            // Unit is a fact for managers; directors select it in the controls row
            ...(!isDirectorMode && unit ? [{ label: 'Unit', value: unit }] : []),
          ].filter(f => f.value);
          if (facts.length === 0) return null;
          return (
            <div className="mb-5 flex flex-wrap items-stretch gap-px rounded-xl overflow-hidden border border-slate-200 dark:border-slate-600 bg-slate-200 dark:bg-slate-600">
              {facts.map(({ label, value }) => (
                <div
                  key={label}
                  className="flex-1 min-w-[140px] px-4 py-3 bg-slate-50 dark:bg-slate-800/80"
                >
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-0.5">
                    {label}
                  </p>
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate" title={value}>
                    {value}
                  </p>
                </div>
              ))}
            </div>
          );
        })()}

        {/* Configurable controls — full-width row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-4 items-end">
          {isDirectorMode && availableDepartments.length > 1 && (
            <div className="lg:col-span-2">
              <label className="label">Department</label>
              <div className="relative">
                <select
                  value={department}
                  disabled={!division}
                  onChange={e => {
                    setDepartment(e.target.value);
                    setUnit('');
                    setJobTitle('');
                    setSelectedUnitId(null);
                    setApiSet(null);
                    setPositions([]);
                    setSelectedPositionId('');
                  }}
                  className="select-field pr-8 w-full disabled:opacity-70 disabled:cursor-not-allowed"
                >
                  <option value="">Select department</option>
                  {availableDepartments.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
                <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>
            </div>
          )}

          {isDirectorMode && (
            <div className={availableDepartments.length > 1 ? 'lg:col-span-2' : 'lg:col-span-3'}>
              <label className="label">Unit</label>
              <div className="relative">
                <select
                  value={unit}
                  disabled={!department}
                  onChange={e => {
                    loadDirectorUnitWorkspace(e.target.value).catch(err => {
                      setAuthError(err instanceof Error ? err.message : 'Failed to load unit.');
                    });
                  }}
                  className="select-field pr-8 w-full disabled:opacity-70 disabled:cursor-not-allowed"
                >
                  <option value="">Select unit</option>
                  {availableUnits.map(u => <option key={u} value={u}>{u}</option>)}
                </select>
                <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>
            </div>
          )}

          <div className={isDirectorMode
            ? (availableDepartments.length > 1 ? 'lg:col-span-3' : 'lg:col-span-3')
            : 'lg:col-span-4'}>
            <label className="label">Position</label>
            <div className="relative">
              <select
                value={selectedPositionId}
                onChange={e => handlePositionChange(e.target.value)}
                disabled={isDirectorMode && !apiSet}
                className="select-field pr-8 w-full disabled:opacity-70 disabled:cursor-not-allowed"
              >
                <option value="">{isDirectorMode ? 'Select position in unit' : 'Select position in your unit'}</option>
                {positions.map(p => (
                  <option key={p.id} value={p.id}>{p.title}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          <div className="lg:col-span-2">
            <label className="label">Job Grade <span className="text-slate-400 normal-case font-normal">(optional)</span></label>
            <input type="text" value={jobGrade} onChange={e => setJobGrade(e.target.value)}
              placeholder="e.g. 13" className="select-field w-full" />
          </div>

          <div className="lg:col-span-2">
            <label className="label">No. of Objectives</label>
            <div className="flex items-center border border-slate-200 dark:border-slate-600 rounded-lg overflow-hidden bg-white dark:bg-slate-700 h-[42px] w-full">
              <input type="number" min={2} max={10} value={numObjectives}
                onChange={e => { const v = parseInt(e.target.value); if (!isNaN(v)) setNumObjectives(Math.min(10, Math.max(2, v))); }}
                className="flex-1 min-w-0 px-3 text-sm font-semibold text-slate-800 dark:text-slate-100 bg-transparent focus:outline-none" />
              <div className="flex flex-col h-full border-l border-slate-200 dark:border-slate-600 flex-shrink-0">
                <button type="button" onClick={() => setNumObjectives(n => Math.min(10, n + 1))} disabled={numObjectives >= 10}
                  className="flex-1 w-8 flex items-center justify-center text-slate-500 hover:text-purple-600 disabled:opacity-30 border-b border-slate-200 dark:border-slate-600 text-xs font-bold">+</button>
                <button type="button" onClick={() => setNumObjectives(n => Math.max(2, n - 1))} disabled={numObjectives <= 2}
                  className="flex-1 w-8 flex items-center justify-center text-slate-500 hover:text-purple-600 disabled:opacity-30 text-xs font-bold">−</button>
              </div>
            </div>
          </div>

          <div className={`flex flex-col gap-1.5 ${
            isDirectorMode
              ? (availableDepartments.length > 1 ? 'lg:col-span-3' : 'lg:col-span-2')
              : 'lg:col-span-4'
          }`}>
            <label className="label invisible select-none" aria-hidden="true">Action</label>
            <div className="flex items-center gap-3 min-h-[42px]">
              <button onClick={() => handleGenerate(false)} disabled={!canGenerate || generateLocked}
                className="btn-primary flex-1 justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                title={
                  generating && !viewingGeneratingPosition
                    ? `Generation in progress for ${generatingPosition?.title || 'another position'}`
                    : setSubmittedToDirector
                      ? 'This position was already submitted to Director'
                      : undefined
                }>
                {generating
                  ? <><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                      </svg>{viewingGeneratingPosition ? 'Generating...' : 'Generating elsewhere...'}</>
                  : <><Sparkles size={16}/>Generate Objectives</>}
              </button>
            </div>
            {!canGenerate && (
              <p className="text-sm text-slate-400">
                {isDirectorMode && !unit ? 'Select a unit first' : 'Select a position first'}
              </p>
            )}
            {canGenerate && setSubmittedToDirector && (
              <p className="text-sm text-slate-500 dark:text-slate-400">Already submitted to Director</p>
            )}
            {viewingGeneratingPosition && genProgress && (
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
              onClick={() => handleGenerate(objectives.length > 0, true)}
              disabled={generateLocked || !canGenerate}
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
            generating={viewingGeneratingPosition}
          />

          {/* Toolbar */}
          <div className="flex items-center justify-between mb-3 flex-wrap gap-3">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">Generated Objectives</h2>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                {objectives.length} objectives
              </span>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                weightOk
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                  : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
              }`}>
                Total weight: {totalWeight}%{weightOk ? ' ✓' : ' — must be 100%'}
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button onClick={() => handleGenerate(true)} disabled={generateLocked || managerReadOnly}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50">
                <RefreshCw size={14} className={viewingGeneratingPosition ? 'animate-spin' : ''}/>Regenerate
              </button>
              <button onClick={openAddModal} disabled={managerReadOnly}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50">
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
                onClick={saveDraftOnly}
                disabled={saveBusy || (!isDirectorMode && alreadySubmittedByManager)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50">
                <Save size={14}/>
                {savingDraft
                  ? 'Saving...'
                  : isDirectorMode
                    ? 'Save for Manager'
                    : 'Save Draft'}
              </button>
              {!isDirectorMode && (
              <button
                onClick={submitToDirector}
                disabled={submitDisabled}
                title={!weightOk && !generating && !alreadySubmittedByManager ? 'Total weight must equal 100% before submitting' : undefined}
                className="inline-flex items-center gap-2 px-4 py-2 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-70"
                style={{ backgroundColor: '#892d8f' }}>
                {viewingGeneratingPosition ? (
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                  </svg>
                ) : (
                  <Save size={14}/>
                )}
                {submitLabel}
              </button>
              )}
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
                        {!viewingGeneratingPosition && !managerReadOnly && (
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
      {objectives.length === 0 && !viewingGeneratingPosition && (
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
              : generating
                ? `Generation is running for ${generatingPosition?.title || 'another position'}. You can keep browsing here.`
                : 'Select a position and number of objectives, then click "Generate Objectives".'}
          </p>
        </div>
      )}
      {objectives.length === 0 && viewingGeneratingPosition && (
        <div className="card p-12 text-center">
          <GenerationProgressBanner
            stage={pipelineStage}
            message={genProgress}
            generating
          />
          <p className="text-sm text-slate-500 max-w-sm mx-auto">
            You can switch to another position while this finishes in the background.
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
