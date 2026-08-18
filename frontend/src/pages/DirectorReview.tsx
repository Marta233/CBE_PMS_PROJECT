import { useEffect, useMemo, useState } from 'react';
import Layout from '../components/Layout';
import ObjectiveWeightBadge from '../components/ObjectiveWeightBadge';
import PositionReviewList from '../components/PositionReviewList';
import WorkflowBreadcrumb from '../components/WorkflowBreadcrumb';
import WorkflowMenuCard from '../components/WorkflowMenuCard';
import { DEPARTMENTS, UNITS } from '../types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

function token() {
  return localStorage.getItem('pms_access_token');
}

async function apiFetch(path: string, init?: RequestInit) {
  const headers = new Headers(init?.headers || {});
  headers.set('Content-Type', headers.get('Content-Type') || 'application/json');
  const t = token();
  if (t) headers.set('Authorization', `Bearer ${t}`);
  return fetch(`${API_URL}${path}`, { ...init, headers });
}

type ObjectiveSetRow = {
  id: number;
  unit_id: number;
  cycle_id: number;
  manager_id: number;
  status: string;
  current_version: number;
  created_at: string;
  updated_at: string;
  unit: { id: number; name: string; division: string; department: string };
  position_statuses?: { position_id: number; status: string }[];
};

type ObjectiveRow = {
  id: number;
  position_id: number;
  goal_statement: string;
  measurement: string;
  target: string;
  weight: number;
  category: string;
  tracking_source: string;
  time_frame: string;
  rating_guidance_json?: {
    rating_5?: string;
    rating_4?: string;
    rating_3?: string;
    rating_2?: string;
    rating_1?: string;
  } | null;
  bsc_link?: string | null;
  strategy_link?: string | null;
  los_alignment?: string | null;
};

type SetDetail = {
  id: number;
  status: string;
  unit: { id: number; name: string; division: string; department: string };
  objectives: ObjectiveRow[];
  position_statuses?: { position_id: number; status: string }[];
};

type PositionRow = { id: number; unit_id: number; title: string; grade_level: number | null };

type MeResponse = {
  director_scope?: { departments: string[]; division: string } | null;
};

const DIRECTOR_QUEUE_STATUSES = new Set(['activated_to_director', 'vp_rejected_to_director']);

function setHasDirectorQueue(row: { status: string; position_statuses?: { position_id: number; status: string }[] }) {
  if (row.position_statuses?.some(p => DIRECTOR_QUEUE_STATUSES.has(p.status))) return true;
  return DIRECTOR_QUEUE_STATUSES.has(row.status);
}

function positionStatusMap(detail: SetDetail | null): Record<number, string> {
  const map: Record<number, string> = {};
  (detail?.position_statuses || []).forEach(p => { map[p.position_id] = p.status; });
  return map;
}

function divisionForDepartment(department: string, fallback = ''): string {
  for (const [division, departments] of Object.entries(DEPARTMENTS)) {
    if (departments.includes(department)) return division;
  }
  return fallback;
}

export default function DirectorReview() {
  const [rows, setRows] = useState<ObjectiveSetRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const pending = useMemo(
    () => rows.filter(setHasDirectorQueue),
    [rows],
  );

  const [selectedUnitName, setSelectedUnitName] = useState<string | null>(null);
  const [selectedSetId, setSelectedSetId] = useState<number | null>(null);
  const [selectedPositionId, setSelectedPositionId] = useState<number | null>(null);
  const [checkedPositionIds, setCheckedPositionIds] = useState<Set<number>>(new Set());
  const [expandedObjectiveId, setExpandedObjectiveId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SetDetail | null>(null);
  const [positionsById, setPositionsById] = useState<Record<number, PositionRow>>({});
  const [view, setView] = useState<'menu' | 'unit'>('menu');
  const [directorDepartments, setDirectorDepartments] = useState<string[]>([]);
  const [directorDivision, setDirectorDivision] = useState('');

  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyJson, setHistoryJson] = useState<any>(null);

  async function openHistory(setId: number) {
    const res = await apiFetch(`/api/objective-sets/${setId}/history`);
    if (!res.ok) throw new Error(await res.text());
    setHistoryJson(await res.json());
    setHistoryOpen(true);
  }

  async function refresh() {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch('/api/objective-sets');
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json() as ObjectiveSetRow[];
      setRows(json);
      if (selectedSetId && !json.some(r => r.id === selectedSetId)) {
        setSelectedSetId(null);
        setDetail(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load objective sets.');
    } finally {
      setLoading(false);
    }
  }

  async function loadSetDetail(setId: number) {
    const target = pending.find(r => r.id === setId) ?? rows.find(r => r.id === setId);
    if (!target) return;
    const detailRes = await apiFetch(`/api/objective-sets/${setId}`);
    if (!detailRes.ok) throw new Error(await detailRes.text());
    const detailJson = await detailRes.json() as SetDetail;
    const posRes = await apiFetch(`/api/objective-sets/positions?unit_id=${target.unit_id}`);
    if (!posRes.ok) throw new Error(await posRes.text());
    const posJson = await posRes.json() as PositionRow[];
    const nextPosMap: Record<number, PositionRow> = {};
    posJson.forEach(p => { nextPosMap[p.id] = p; });
    setPositionsById(nextPosMap);
    setDetail(detailJson);
    const statusByPos = positionStatusMap(detailJson);
    const reviewable = [...new Set(detailJson.objectives.map(o => o.position_id))]
      .filter(pid => DIRECTOR_QUEUE_STATUSES.has(statusByPos[pid] || detailJson.status));
    setCheckedPositionIds(new Set(reviewable));
    if (reviewable.length > 0) setSelectedPositionId(reviewable[0]);
    else {
      const anyPos = [...new Set(detailJson.objectives.map(o => o.position_id))];
      if (anyPos.length > 0) setSelectedPositionId(anyPos[0]);
    }
  }

  async function loadUnitWorkspace(unitName: string) {
    setSelectedPositionId(null);
    setCheckedPositionIds(new Set());
    setExpandedObjectiveId(null);
    setDetail(null);
    setPositionsById({});
    setSelectedSetId(null);

    const unitRows = rows
      .filter(r => r.unit.name === unitName && setHasDirectorQueue(r))
      .sort((a, b) => +new Date(b.updated_at) - +new Date(a.updated_at));

    if (unitRows.length > 0) {
      const latest = unitRows[0];
      setSelectedSetId(latest.id);
      await loadSetDetail(latest.id);
    }
  }

  async function saveCurrentEdits() {
    if (!detail) return;
    setSaving(true);
    try {
      const editableIds = reviewablePositionIds;
      const payload = {
        objectives: detail.objectives.map(o => ({
          position_id: o.position_id,
          goal_statement: o.goal_statement,
          measurement: o.measurement,
          target: o.target,
          weight: o.weight,
          category: o.category,
          tracking_source: o.tracking_source,
          time_frame: o.time_frame,
          rating_guidance_json: o.rating_guidance_json ?? null,
          bsc_link: o.bsc_link ?? null,
          strategy_link: o.strategy_link ?? null,
          los_alignment: o.los_alignment ?? null,
        })),
        position_ids: editableIds,
        snapshot_json: {
          reviewed_by: 'unit_director',
          reviewed_at: new Date().toISOString(),
          unit: detail.unit,
        },
      };
      const saveRes = await apiFetch(`/api/objective-sets/${detail.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      if (!saveRes.ok) throw new Error(await saveRes.text());
      const saved = await saveRes.json() as ObjectiveSetRow;
      setDetail(prev => prev ? {
        ...prev,
        status: saved.status,
        position_statuses: saved.position_statuses,
      } : prev);
      setNotice('Changes saved.');
      await refresh();
    } finally {
      setSaving(false);
    }
  }

  async function approveAndActivate(id: number) {
    const selectedIds = reviewablePositionIds.filter(pid => checkedPositionIds.has(pid));
    if (selectedIds.length === 0) return;
    if (
      !window.confirm(
        `Approve and send ${selectedIds.length} position${selectedIds.length === 1 ? '' : 's'} to VP? Unselected positions stay in Director Review.`,
      )
    ) {
      return;
    }
    if (detail && detail.id === id) {
      await saveCurrentEdits();
    }
    const res = await apiFetch(`/api/objective-sets/${id}/activate`, {
      method: 'POST',
      body: JSON.stringify({ position_ids: selectedIds }),
    });
    if (!res.ok) throw new Error(await res.text());
    setNotice(`Approved ${selectedIds.length} position(s) and sent to VP.`);
    setDetail(null);
    setSelectedSetId(null);
    setSelectedPositionId(null);
    setCheckedPositionIds(new Set());
    await refresh();
  }

  async function rejectToManager(id: number) {
    const selectedIds = reviewablePositionIds.filter(pid => checkedPositionIds.has(pid));
    if (selectedIds.length === 0) {
      setError('Select at least one position to reject.');
      return;
    }
    const comment = prompt('Rejection reason (required):');
    if (!comment || !comment.trim()) return;
    const res = await apiFetch(`/api/objective-sets/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ comment, position_ids: selectedIds }),
    });
    if (!res.ok) throw new Error(await res.text());
    setNotice(`Rejected ${selectedIds.length} position(s) back to manager.`);
    await refresh();
    if (detail?.id === id) await loadSetDetail(id);
  }

  useEffect(() => {
    void refresh();
    void (async () => {
      try {
        const res = await apiFetch('/api/auth/me');
        if (!res.ok) return;
        const me = await res.json() as MeResponse;
        if (me.director_scope) {
          setDirectorDepartments(me.director_scope.departments);
          setDirectorDivision(me.director_scope.division);
        }
      } catch {
        // Non-fatal: unit menu falls back to pending-only rows.
      }
    })();
  }, []);

  const units = useMemo(() => {
    const map = new Map<string, { unit_id: number | null; unit_name: string; department: string; division: string; count: number }>();
    for (const r of pending) {
      const key = r.unit.name;
      const x = map.get(key);
      if (x) x.count += 1;
      else {
        map.set(key, {
          unit_id: r.unit_id,
          unit_name: r.unit.name,
          department: r.unit.department,
          division: r.unit.division,
          count: 1,
        });
      }
    }
    for (const department of directorDepartments) {
      const division = directorDivision || divisionForDepartment(department);
      for (const unitName of UNITS[department] || []) {
        if (!map.has(unitName)) {
          map.set(unitName, {
            unit_id: null,
            unit_name: unitName,
            department,
            division,
            count: 0,
          });
        }
      }
    }
    return Array.from(map.values()).sort((a, b) => a.unit_name.localeCompare(b.unit_name));
  }, [pending, directorDepartments, directorDivision]);

  const selectedUnitCard = useMemo(
    () => units.find(u => u.unit_name === selectedUnitName) ?? null,
    [units, selectedUnitName],
  );

  const objectivesForPosition = useMemo(
    () => detail?.objectives.filter(o => o.position_id === selectedPositionId) ?? [],
    [detail, selectedPositionId],
  );
  const positionRows = useMemo(
    () => Object.values(positionsById).sort((a, b) => a.title.localeCompare(b.title)),
    [positionsById],
  );
  const objectiveCountByPosition = useMemo(() => {
    const map: Record<number, number> = {};
    (detail?.objectives || []).forEach(o => { map[o.position_id] = (map[o.position_id] || 0) + 1; });
    return map;
  }, [detail]);
  const statusByPosition = useMemo(() => positionStatusMap(detail), [detail]);
  const positionListItems = useMemo(
    () => positionRows.map(p => {
      const status = statusByPosition[p.id] || null;
      const objectiveCount = objectiveCountByPosition[p.id] || 0;
      const inQueue = !!status && DIRECTOR_QUEUE_STATUSES.has(status);
      return {
        id: p.id,
        title: p.title,
        objectiveCount,
        status,
        isNew: objectiveCount > 0 && inQueue,
        checkable: objectiveCount > 0 && inQueue,
      };
    }),
    [positionRows, objectiveCountByPosition, statusByPosition],
  );
  const reviewablePositionIds = useMemo(
    () => positionListItems.filter(p => p.checkable).map(p => p.id),
    [positionListItems],
  );
  const selectedReviewableCount = reviewablePositionIds.filter(id => checkedPositionIds.has(id)).length;
  const canApproveSelected = selectedReviewableCount > 0;
  const hasDirectorQueuePositions = reviewablePositionIds.length > 0;

  function togglePositionCheck(id: number) {
    setCheckedPositionIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAllPositions() {
    setCheckedPositionIds(new Set(reviewablePositionIds));
  }

  function clearPositionChecks() {
    setCheckedPositionIds(new Set());
  }

  function updateObjective(id: number, patch: Partial<ObjectiveRow>) {
    setDetail(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        objectives: prev.objectives.map(o => (o.id === id ? { ...o, ...patch } : o)),
      };
    });
  }

  function resetToMenu() {
    setView('menu');
    setSelectedUnitName(null);
    setSelectedSetId(null);
    setSelectedPositionId(null);
    setCheckedPositionIds(new Set());
    setDetail(null);
  }

  const breadcrumbItems = useMemo(() => {
    const departmentLabel =
      selectedUnitCard?.department
      ?? directorDepartments[0]
      ?? null;
    const items: { label: string; onClick?: () => void }[] = [
      {
        label: 'Digital Banking',
        onClick: view === 'unit' ? resetToMenu : undefined,
      },
    ];
    if (departmentLabel && view === 'unit') {
      items.push({
        label: `${departmentLabel} Director`,
        onClick: resetToMenu,
      });
    }
    if (selectedUnitName && view === 'unit') {
      items.push({ label: selectedUnitName });
    }
    return items;
  }, [view, selectedUnitName, selectedUnitCard, directorDepartments]);

  return (
    <Layout
      title="Director Review"
      subtitle="Review objective sets submitted by Managers and approve, edit or reject."
    >
      <WorkflowBreadcrumb items={breadcrumbItems} />

      {error && (
        <div className="mb-4 p-3 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50/60 dark:bg-red-900/15 text-sm text-red-700 dark:text-red-200">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 p-3 rounded-lg border border-emerald-200 dark:border-emerald-800/40 bg-emerald-50/60 dark:bg-emerald-900/15 text-sm text-emerald-700 dark:text-emerald-200">
          {notice}
        </div>
      )}

      {view === 'menu' && (
        <div className="card p-5 mb-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">Choose a Unit</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Click a unit card to enter its review page.</p>
            </div>
            <button className="btn-secondary" onClick={refresh} disabled={loading}>Refresh</button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {units.map(u => (
              <WorkflowMenuCard
                key={u.unit_name}
                title={u.unit_name}
                subtitle={`${u.department} · ${u.division}`}
                pendingCount={u.count}
                badge={`${u.count} submission(s)`}
                onClick={() => {
                  setSelectedUnitName(u.unit_name);
                  setView('unit');
                  loadUnitWorkspace(u.unit_name).catch(e => setError(String(e)));
                }}
              />
            ))}
            {units.length === 0 && (
              <div className="col-span-full text-sm text-slate-500 dark:text-slate-400 py-6 text-center">
                No units pending director review.
              </div>
            )}
          </div>
        </div>
      )}

      {view === 'unit' && selectedUnitName && (
        <div className="card p-5 mb-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">
                {selectedUnitCard?.unit_name ?? 'Unit'} Review
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {selectedUnitCard?.department} · {selectedUnitCard?.division}
              </p>
            </div>
            <button className="btn-secondary" onClick={resetToMenu}>
              Back to Units
            </button>
          </div>
          {!detail && (
            <div className="text-sm text-slate-500 dark:text-slate-400 py-4 border border-dashed border-slate-300 dark:border-slate-700 rounded-xl px-4">
              No active pending package for this unit right now.
            </div>
          )}
          {detail && (
          <div className="mt-4">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
            <div>
              <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">
                {detail.unit.name} Objectives
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Select one or more positions in Director Review, then approve. Only checked positions move to VP.
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button className="btn-secondary" disabled={saving} onClick={() => saveCurrentEdits().catch(e => setError(String(e)))}>
                {saving ? 'Saving...' : 'Save Edits'}
              </button>
              <button className="btn-secondary" onClick={() => openHistory(detail.id).catch(e => setError(String(e)))}>History</button>
              {hasDirectorQueuePositions && (
                <button
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={!canApproveSelected}
                  title={canApproveSelected ? undefined : 'Select at least one position with objectives to approve'}
                  onClick={() => approveAndActivate(detail.id).catch(e => setError(String(e)))}
                >
                  Approve & Send to VP ({selectedReviewableCount}/{reviewablePositionIds.length})
                </button>
              )}
              {hasDirectorQueuePositions && (
                <button
                  className="btn-danger disabled:opacity-50"
                  disabled={!canApproveSelected}
                  onClick={() => rejectToManager(detail.id).catch(e => setError(String(e)))}
                >
                  Reject
                </button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            <div className="lg:col-span-1 border border-slate-200 dark:border-slate-700 rounded-xl p-3">
              <PositionReviewList
                positions={positionListItems}
                selectedPositionId={selectedPositionId}
                checkedPositionIds={checkedPositionIds}
                onSelectPosition={id => {
                  setSelectedPositionId(id);
                  setExpandedObjectiveId(null);
                }}
                onToggleCheck={togglePositionCheck}
                onSelectAll={selectAllPositions}
                onClearChecks={clearPositionChecks}
              />
            </div>

            <div className="lg:col-span-3 border border-slate-200 dark:border-slate-700 rounded-xl p-3">
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Objectives</p>
                {selectedPositionId && objectivesForPosition.length > 0 && (
                  <ObjectiveWeightBadge weights={objectivesForPosition.map(o => o.weight)} />
                )}
              </div>
              {!selectedPositionId && (
                <p className="text-sm text-slate-500 dark:text-slate-400 py-8 text-center">Choose a position to review objectives.</p>
              )}
              {selectedPositionId && (
                <div className="space-y-3">
                  {objectivesForPosition.map((o, idx) => {
                    const expanded = expandedObjectiveId === o.id;
                    return (
                      <div key={o.id} className="border border-slate-200 dark:border-slate-700 rounded-xl">
                        <button
                          onClick={() => setExpandedObjectiveId(expanded ? null : o.id)}
                          className="w-full text-left p-3 flex items-center justify-between"
                        >
                          <div className="min-w-0 pr-2">
                            <p className="text-sm text-slate-700 dark:text-slate-200">
                              <span className="font-semibold text-slate-800 dark:text-slate-100">{idx + 1}. </span>
                              <span className="text-slate-600 dark:text-slate-400">{o.goal_statement}</span>
                            </p>
                          </div>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-200">
                            {o.weight}%
                          </span>
                        </button>
                        {expanded && (
                          <div className="p-3 border-t border-slate-200 dark:border-slate-700 grid grid-cols-1 md:grid-cols-2 gap-3">
                            <label className="text-xs text-slate-600 dark:text-slate-300 md:col-span-2">
                              Objective
                              <textarea value={o.goal_statement} onChange={e => updateObjective(o.id, { goal_statement: e.target.value })} className="mt-1 w-full select-field" rows={3} />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                              Measure
                              <input value={o.measurement} onChange={e => updateObjective(o.id, { measurement: e.target.value })} className="mt-1 w-full select-field" />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                              Target
                              <input value={o.target} onChange={e => updateObjective(o.id, { target: e.target.value })} className="mt-1 w-full select-field" />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                              Weight
                              <input type="number" value={o.weight} onChange={e => updateObjective(o.id, { weight: Number(e.target.value) || 0 })} className="mt-1 w-full select-field" />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                              Category
                              <input value={o.category} onChange={e => updateObjective(o.id, { category: e.target.value })} className="mt-1 w-full select-field" />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                              Tracking Source
                              <input value={o.tracking_source} onChange={e => updateObjective(o.id, { tracking_source: e.target.value })} className="mt-1 w-full select-field" />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                              Time Frame
                              <input value={o.time_frame} onChange={e => updateObjective(o.id, { time_frame: e.target.value })} className="mt-1 w-full select-field" />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300 md:col-span-2">
                              Appraisal (5)
                              <textarea
                                value={o.rating_guidance_json?.rating_5 ?? ''}
                                onChange={e => updateObjective(o.id, { rating_guidance_json: { ...(o.rating_guidance_json ?? {}), rating_5: e.target.value } })}
                                className="mt-1 w-full select-field"
                                rows={2}
                              />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300 md:col-span-2">
                              Appraisal (4)
                              <textarea
                                value={o.rating_guidance_json?.rating_4 ?? ''}
                                onChange={e => updateObjective(o.id, { rating_guidance_json: { ...(o.rating_guidance_json ?? {}), rating_4: e.target.value } })}
                                className="mt-1 w-full select-field"
                                rows={2}
                              />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300 md:col-span-2">
                              Appraisal (3)
                              <textarea
                                value={o.rating_guidance_json?.rating_3 ?? ''}
                                onChange={e => updateObjective(o.id, { rating_guidance_json: { ...(o.rating_guidance_json ?? {}), rating_3: e.target.value } })}
                                className="mt-1 w-full select-field"
                                rows={2}
                              />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300 md:col-span-2">
                              Appraisal (2)
                              <textarea
                                value={o.rating_guidance_json?.rating_2 ?? ''}
                                onChange={e => updateObjective(o.id, { rating_guidance_json: { ...(o.rating_guidance_json ?? {}), rating_2: e.target.value } })}
                                className="mt-1 w-full select-field"
                                rows={2}
                              />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300 md:col-span-2">
                              Appraisal (1)
                              <textarea
                                value={o.rating_guidance_json?.rating_1 ?? ''}
                                onChange={e => updateObjective(o.id, { rating_guidance_json: { ...(o.rating_guidance_json ?? {}), rating_1: e.target.value } })}
                                className="mt-1 w-full select-field"
                                rows={2}
                              />
                            </label>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {objectivesForPosition.length === 0 && (
                    <p className="text-sm text-slate-500 dark:text-slate-400 py-8 text-center">No objectives found for this position.</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
          )}
        </div>
      )}

      {historyOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setHistoryOpen(false)}>
          <div className="card max-w-3xl w-full p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Audit trail</h3>
              <button className="btn-secondary" onClick={() => setHistoryOpen(false)}>Close</button>
            </div>
            <pre className="text-xs bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 rounded-lg p-3 overflow-auto max-h-[60vh]">
              {JSON.stringify(historyJson, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </Layout>
  );
}

