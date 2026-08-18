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
  rating_guidance_json?: { rating_5?: string; rating_4?: string; rating_3?: string; rating_2?: string; rating_1?: string } | null;
};

type SetDetail = {
  id: number;
  status: string;
  unit: { id: number; name: string; division: string; department: string };
  objectives: ObjectiveRow[];
  position_statuses?: { position_id: number; status: string }[];
};

type PositionRow = { id: number; unit_id: number; title: string; grade_level: number | null };

const VP_QUEUE_STATUS = 'director_approved_and_activated_to_vp';
const VP_FINAL_STATUS = 'vp_approved_final';

function setHasPositionStatus(
  row: { status: string; position_statuses?: { position_id: number; status: string }[] },
  status: string,
) {
  if (row.position_statuses?.some(p => p.status === status)) return true;
  return row.status === status;
}

function positionIdsInStatus(
  row: { position_statuses?: { position_id: number; status: string }[] },
  status: string,
): number[] {
  return (row.position_statuses || []).filter(p => p.status === status).map(p => p.position_id);
}

function positionStatusMap(detail: SetDetail | null): Record<number, string> {
  const map: Record<number, string> = {};
  (detail?.position_statuses || []).forEach(p => { map[p.position_id] = p.status; });
  return map;
}

export default function VPReview() {
  const [rows, setRows] = useState<ObjectiveSetRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [bulkWorking, setBulkWorking] = useState(false);

  const pendingApproval = useMemo(
    () => rows.filter(r => setHasPositionStatus(r, VP_QUEUE_STATUS)),
    [rows],
  );
  const pendingPms = useMemo(
    () => rows.filter(r => setHasPositionStatus(r, VP_FINAL_STATUS)),
    [rows],
  );
  const pending = useMemo(
    () => [...pendingApproval, ...pendingPms],
    [pendingApproval, pendingPms],
  );

  const [selectedDirectorKey, setSelectedDirectorKey] = useState<string | null>(null);
  const [selectedUnitName, setSelectedUnitName] = useState<string | null>(null);
  const [checkedUnitNames, setCheckedUnitNames] = useState<Set<string>>(new Set());
  const [selectedSetId, setSelectedSetId] = useState<number | null>(null);
  const [selectedPositionId, setSelectedPositionId] = useState<number | null>(null);
  const [checkedPositionIds, setCheckedPositionIds] = useState<Set<number>>(new Set());
  const [expandedObjectiveId, setExpandedObjectiveId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SetDetail | null>(null);
  const [positionsById, setPositionsById] = useState<Record<number, PositionRow>>({});
  const [view, setView] = useState<'directors' | 'units' | 'unit'>('directors');

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
    const map: Record<number, PositionRow> = {};
    posJson.forEach(p => { map[p.id] = p; });
    setPositionsById(map);
    setDetail(detailJson);
    const statusByPos = positionStatusMap(detailJson);
    const reviewable = [...new Set(detailJson.objectives.map(o => o.position_id))]
      .filter(pid => {
        const st = statusByPos[pid] || detailJson.status;
        return st === VP_QUEUE_STATUS || st === VP_FINAL_STATUS;
      });
    setCheckedPositionIds(new Set(reviewable.filter(pid => (statusByPos[pid] || detailJson.status) === VP_QUEUE_STATUS)));
    if (reviewable.length > 0) setSelectedPositionId(reviewable[0]);
  }

  async function loadUnitWorkspace(unitName: string) {
    setSelectedPositionId(null);
    setCheckedPositionIds(new Set());
    setExpandedObjectiveId(null);
    setDetail(null);
    setPositionsById({});
    setSelectedSetId(null);

    const unitRows = pending
      .filter(r => r.unit.name === unitName)
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
      const editableIds = Object.entries(positionStatusMap(detail))
        .filter(([, st]) => st === VP_QUEUE_STATUS || st === VP_FINAL_STATUS)
        .map(([id]) => Number(id));
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
          bsc_link: null,
          strategy_link: null,
          los_alignment: null,
        })),
        position_ids: editableIds,
        snapshot_json: { reviewed_by: 'vp', reviewed_at: new Date().toISOString(), unit: detail.unit },
      };
      const res = await apiFetch(`/api/objective-sets/${detail.id}`, { method: 'PUT', body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(await res.text());
      const saved = await res.json() as ObjectiveSetRow;
      setDetail(prev => prev ? { ...prev, status: saved.status, position_statuses: saved.position_statuses } : prev);
      setNotice('Changes saved.');
      await refresh();
    } finally {
      setSaving(false);
    }
  }

  async function approve(id: number) {
    const selectedIds = reviewablePositionIds.filter(pid => checkedPositionIds.has(pid));
    if (selectedIds.length === 0) return;
    if (
      !window.confirm(
        `Approve ${selectedIds.length} position${selectedIds.length === 1 ? '' : 's'}? Unselected positions stay in the VP queue.`,
      )
    ) {
      return;
    }
    if (detail && detail.id === id) await saveCurrentEdits();
    const res = await apiFetch(`/api/objective-sets/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ position_ids: selectedIds }),
    });
    if (!res.ok) throw new Error(await res.text());
    setNotice(`Approved ${selectedIds.length} position(s). You can send approved ones to PMS.`);
    await refresh();
    if (detail?.id === id) await loadSetDetail(id);
  }

  async function activateToPms(id: number) {
    const selectedIds = pmsReadyPositionIds.filter(pid => checkedPositionIds.has(pid));
    const ids = selectedIds.length > 0 ? selectedIds : pmsReadyPositionIds;
    if (ids.length === 0) {
      setError('No approved positions ready to send to PMS.');
      return;
    }
    if (!window.confirm(`Send ${ids.length} position${ids.length === 1 ? '' : 's'} to PMS?`)) return;
    if (detail && detail.id === id) await saveCurrentEdits();
    const res = await apiFetch(`/api/objective-sets/${id}/activate`, {
      method: 'POST',
      body: JSON.stringify({ position_ids: ids }),
    });
    if (!res.ok) throw new Error(await res.text());
    setNotice(`Sent ${ids.length} position(s) to PMS.`);
    setDetail(null);
    setSelectedSetId(null);
    setSelectedPositionId(null);
    setCheckedPositionIds(new Set());
    setView('units');
    await refresh();
  }

  async function rejectToDirector(id: number) {
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
    setNotice(`Rejected ${selectedIds.length} position(s) back to Director.`);
    setDetail(null);
    setSelectedSetId(null);
    setView('units');
    await refresh();
  }

  async function bulkApproveUnits() {
    const sets = Array.from(checkedUnitNames)
      .map(name => latestSetForUnit(name, VP_QUEUE_STATUS))
      .filter((s): s is ObjectiveSetRow => Boolean(s));
    if (sets.length === 0) return;
    if (!window.confirm(`Approve all VP-queue positions in ${sets.length} unit(s)?`)) return;
    setBulkWorking(true);
    try {
      for (const s of sets) {
        let ids = positionIdsInStatus(s, VP_QUEUE_STATUS);
        if (ids.length === 0) {
          const detailRes = await apiFetch(`/api/objective-sets/${s.id}`);
          if (!detailRes.ok) throw new Error(await detailRes.text());
          const d = await detailRes.json() as SetDetail;
          ids = positionIdsInStatus(d, VP_QUEUE_STATUS);
        }
        if (ids.length === 0) continue;
        const res = await apiFetch(`/api/objective-sets/${s.id}/approve`, {
          method: 'POST',
          body: JSON.stringify({ position_ids: ids }),
        });
        if (!res.ok) throw new Error(await res.text());
      }
      setNotice(`Approved positions in ${sets.length} unit(s).`);
      setCheckedUnitNames(new Set());
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Bulk approve failed.');
    } finally {
      setBulkWorking(false);
    }
  }

  async function bulkSendToPms() {
    const sets = Array.from(checkedUnitNames)
      .map(name => latestSetForUnit(name, VP_FINAL_STATUS))
      .filter((s): s is ObjectiveSetRow => Boolean(s));
    if (sets.length === 0) return;
    if (!window.confirm(`Send approved positions in ${sets.length} unit(s) to PMS?`)) return;
    setBulkWorking(true);
    try {
      for (const s of sets) {
        let ids = positionIdsInStatus(s, VP_FINAL_STATUS);
        if (ids.length === 0) {
          const detailRes = await apiFetch(`/api/objective-sets/${s.id}`);
          if (!detailRes.ok) throw new Error(await detailRes.text());
          const d = await detailRes.json() as SetDetail;
          ids = positionIdsInStatus(d, VP_FINAL_STATUS);
        }
        if (ids.length === 0) continue;
        const res = await apiFetch(`/api/objective-sets/${s.id}/activate`, {
          method: 'POST',
          body: JSON.stringify({ position_ids: ids }),
        });
        if (!res.ok) throw new Error(await res.text());
      }
      setNotice(`Sent positions in ${sets.length} unit(s) to PMS.`);
      setCheckedUnitNames(new Set());
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Bulk send failed.');
    } finally {
      setBulkWorking(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  const directorCards = useMemo(() => {
    const grouped = new Map<string, { key: string; label: string; count: number }>();
    for (const departments of Object.values(DEPARTMENTS)) {
      for (const dept of departments) {
        grouped.set(dept, { key: dept, label: `${dept} Director`, count: 0 });
      }
    }
    for (const r of pending) {
      const key = r.unit.department;
      const existing = grouped.get(key);
      if (existing) existing.count += 1;
      else grouped.set(key, { key, label: `${r.unit.department} Director`, count: 1 });
    }
    return Array.from(grouped.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [pending]);

  const rowsForDirector = useMemo(
    () => pending.filter(r => (selectedDirectorKey ? r.unit.department === selectedDirectorKey : false)),
    [pending, selectedDirectorKey],
  );

  function latestSetForUnit(unitName: string, status?: string) {
    return rowsForDirector
      .filter(r => r.unit.name === unitName && (!status || setHasPositionStatus(r, status)))
      .sort((a, b) => +new Date(b.updated_at) - +new Date(a.updated_at))[0] ?? null;
  }

  const unitCards = useMemo(() => {
    const map = new Map<string, { unit_name: string; approvalCount: number; pmsCount: number }>();
    for (const unitName of (selectedDirectorKey ? (UNITS[selectedDirectorKey] || []) : [])) {
      map.set(unitName, { unit_name: unitName, approvalCount: 0, pmsCount: 0 });
    }
    for (const r of rowsForDirector) {
      const key = r.unit.name;
      const x = map.get(key) ?? { unit_name: r.unit.name, approvalCount: 0, pmsCount: 0 };
      const vpCount = positionIdsInStatus(r, VP_QUEUE_STATUS).length || (r.status === VP_QUEUE_STATUS ? 1 : 0);
      const finalCount = positionIdsInStatus(r, VP_FINAL_STATUS).length || (r.status === VP_FINAL_STATUS ? 1 : 0);
      x.approvalCount += vpCount;
      x.pmsCount += finalCount;
      map.set(key, x);
    }
    return Array.from(map.values()).sort((a, b) => a.unit_name.localeCompare(b.unit_name));
  }, [rowsForDirector, selectedDirectorKey]);

  const selectableUnitNames = useMemo(
    () => unitCards.filter(u => u.approvalCount > 0 || u.pmsCount > 0).map(u => u.unit_name),
    [unitCards],
  );
  const checkedApprovalUnits = useMemo(
    () => Array.from(checkedUnitNames).filter(name => latestSetForUnit(name, VP_QUEUE_STATUS)),
    [checkedUnitNames, rowsForDirector],
  );
  const checkedPmsUnits = useMemo(
    () => Array.from(checkedUnitNames).filter(name => latestSetForUnit(name, VP_FINAL_STATUS)),
    [checkedUnitNames, rowsForDirector],
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
      const inVpQueue = status === VP_QUEUE_STATUS;
      const pmsReady = status === VP_FINAL_STATUS;
      return {
        id: p.id,
        title: p.title,
        objectiveCount,
        status,
        isNew: objectiveCount > 0 && inVpQueue,
        checkable: objectiveCount > 0 && (inVpQueue || pmsReady),
      };
    }),
    [positionRows, objectiveCountByPosition, statusByPosition],
  );
  const reviewablePositionIds = useMemo(
    () => positionListItems.filter(p => p.status === VP_QUEUE_STATUS).map(p => p.id),
    [positionListItems],
  );
  const pmsReadyPositionIds = useMemo(
    () => positionListItems.filter(p => p.status === VP_FINAL_STATUS).map(p => p.id),
    [positionListItems],
  );
  const selectedReviewableCount = reviewablePositionIds.filter(id => checkedPositionIds.has(id)).length;
  const canApproveSelected = selectedReviewableCount > 0;
  const hasVpQueuePositions = reviewablePositionIds.length > 0;
  const hasPmsReadyPositions = pmsReadyPositionIds.length > 0;

  const objectivesForPosition = useMemo(
    () => detail?.objectives.filter(o => o.position_id === selectedPositionId) ?? [],
    [detail, selectedPositionId],
  );

  function togglePositionCheck(id: number) {
    setCheckedPositionIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleUnitCheck(unitName: string, checked: boolean) {
    setCheckedUnitNames(prev => {
      const next = new Set(prev);
      if (checked) next.add(unitName);
      else next.delete(unitName);
      return next;
    });
  }

  function selectAllUnits() {
    setCheckedUnitNames(new Set(selectableUnitNames));
  }

  function clearUnitChecks() {
    setCheckedUnitNames(new Set());
  }

  function updateObjective(id: number, patch: Partial<ObjectiveRow>) {
    setDetail(prev => {
      if (!prev) return prev;
      return { ...prev, objectives: prev.objectives.map(o => (o.id === id ? { ...o, ...patch } : o)) };
    });
  }

  function resetToDirectors() {
    setView('directors');
    setSelectedDirectorKey(null);
    setSelectedUnitName(null);
    setCheckedUnitNames(new Set());
    setSelectedSetId(null);
    setSelectedPositionId(null);
    setCheckedPositionIds(new Set());
    setDetail(null);
  }

  function resetToUnits() {
    setView('units');
    setSelectedUnitName(null);
    setSelectedSetId(null);
    setSelectedPositionId(null);
    setCheckedPositionIds(new Set());
    setDetail(null);
  }

  const breadcrumbItems = useMemo(() => {
    const items: { label: string; onClick?: () => void }[] = [
      {
        label: 'Digital Banking',
        onClick: view !== 'directors' ? resetToDirectors : undefined,
      },
    ];
    if (selectedDirectorKey && (view === 'units' || view === 'unit')) {
      items.push({
        label: `${selectedDirectorKey} Director`,
        onClick: view === 'unit' ? resetToUnits : undefined,
      });
    }
    if (selectedUnitName && view === 'unit') {
      items.push({ label: selectedUnitName });
    }
    return items;
  }, [view, selectedDirectorKey, selectedUnitName]);

  return (
    <Layout
      title="Review Performance Plan"
      subtitle="Review director-approved objective sets."
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

      {view === 'directors' && (
        <div className="card p-5 mb-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">Select Director</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">{pending.length} set(s) {loading ? '(loading...)' : ''}</p>
            </div>
            <button className="btn-secondary" onClick={refresh} disabled={loading}>Refresh</button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {directorCards.map(d => (
              <WorkflowMenuCard
                key={d.key}
                title={d.label}
                pendingCount={d.count}
                badge={`${d.count} set(s)`}
                onClick={() => {
                  setSelectedDirectorKey(d.key);
                  setSelectedUnitName(null);
                  setCheckedUnitNames(new Set());
                  setView('units');
                }}
              />
            ))}
          </div>
        </div>
      )}

      {view === 'units' && selectedDirectorKey && (
        <div className="card p-5 mb-5">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div>
              <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{selectedDirectorKey} · Units</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Select units for bulk actions, or open a unit to review positions.
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button type="button" className="text-xs text-purple-700 dark:text-purple-300 hover:underline" onClick={selectAllUnits}>
                Select all pending
              </button>
              <button type="button" className="text-xs text-slate-500 hover:underline" onClick={clearUnitChecks}>
                Clear
              </button>
              <button className="btn-secondary" onClick={resetToDirectors}>
                Back
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <button
              className="btn-primary disabled:opacity-50"
              disabled={bulkWorking || checkedApprovalUnits.length === 0}
              onClick={() => bulkApproveUnits().catch(e => setError(String(e)))}
            >
              Approve selected ({checkedApprovalUnits.length})
            </button>
            <button
              className="btn-primary disabled:opacity-50"
              disabled={bulkWorking || checkedPmsUnits.length === 0}
              onClick={() => bulkSendToPms().catch(e => setError(String(e)))}
            >
              Send selected to PMS ({checkedPmsUnits.length})
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {unitCards.map(u => {
              const pendingCount = u.approvalCount + u.pmsCount;
              const badge = u.approvalCount && u.pmsCount
                ? `${u.approvalCount} to approve · ${u.pmsCount} to PMS`
                : u.approvalCount
                  ? `${u.approvalCount} awaiting VP`
                  : u.pmsCount
                    ? `${u.pmsCount} ready for PMS`
                    : 'No pending';
              return (
                <WorkflowMenuCard
                  key={u.unit_name}
                  title={u.unit_name}
                  pendingCount={pendingCount}
                  badge={badge}
                  selectable
                  checked={checkedUnitNames.has(u.unit_name)}
                  onCheckChange={checked => toggleUnitCheck(u.unit_name, checked)}
                  selected={selectedUnitName === u.unit_name}
                  onClick={() => {
                    setSelectedUnitName(u.unit_name);
                    setView('unit');
                    loadUnitWorkspace(u.unit_name).catch(e => setError(String(e)));
                  }}
                />
              );
            })}
          </div>
        </div>
      )}

      {view === 'unit' && selectedUnitName && (
        <div className="card p-5">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
            <div>
              <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">Review Performance Plan · {selectedUnitName}</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">{selectedDirectorKey}</p>
            </div>
            <button className="btn-secondary" onClick={resetToUnits}>
              Back to Units
            </button>
          </div>

          {!detail && (
            <div className="text-sm text-slate-500 dark:text-slate-400 py-4 border border-dashed border-slate-300 dark:border-slate-700 rounded-xl px-4">
              No active package for this unit right now.
            </div>
          )}

          {detail && (
            <>
              <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Select one or more positions in the VP queue, then approve. Only checked positions advance.
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  <button className="btn-secondary" onClick={() => saveCurrentEdits().catch(e => setError(String(e)))} disabled={saving}>
                    {saving ? 'Saving...' : 'Save Edits'}
                  </button>
                  <button className="btn-secondary" onClick={() => openHistory(detail.id).catch(e => setError(String(e)))}>History</button>
                  {hasVpQueuePositions && (
                    <button
                      className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                      disabled={!canApproveSelected}
                      title={canApproveSelected ? undefined : 'Select at least one position with objectives to approve'}
                      onClick={() => approve(detail.id).catch(e => setError(String(e)))}
                    >
                      Approve ({selectedReviewableCount}/{reviewablePositionIds.length})
                    </button>
                  )}
                  {hasPmsReadyPositions && (
                    <button
                      className="btn-primary"
                      onClick={() => activateToPms(detail.id).catch(e => setError(String(e)))}
                    >
                      Send to PMS ({pmsReadyPositionIds.length})
                    </button>
                  )}
                  {hasVpQueuePositions && (
                    <button
                      className="btn-danger disabled:opacity-50"
                      disabled={!canApproveSelected}
                      onClick={() => rejectToDirector(detail.id).catch(e => setError(String(e)))}
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
                    onSelectAll={() => setCheckedPositionIds(new Set(reviewablePositionIds))}
                    onClearChecks={() => setCheckedPositionIds(new Set())}
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
                            <button onClick={() => setExpandedObjectiveId(expanded ? null : o.id)} className="w-full text-left p-3 flex items-center justify-between">
                              <div className="min-w-0 pr-2">
                                <p className="text-sm text-slate-700 dark:text-slate-200">
                                  <span className="font-semibold text-slate-800 dark:text-slate-100">{idx + 1}. </span>
                                  <span className="text-slate-600 dark:text-slate-400">{o.goal_statement}</span>
                                </p>
                              </div>
                              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-200">{o.weight}%</span>
                            </button>
                            {expanded && (
                              <div className="p-3 border-t border-slate-200 dark:border-slate-700 grid grid-cols-1 md:grid-cols-2 gap-3">
                                <label className="text-xs text-slate-600 dark:text-slate-300 md:col-span-2">Objective
                                  <textarea value={o.goal_statement} onChange={e => updateObjective(o.id, { goal_statement: e.target.value })} className="mt-1 w-full select-field" rows={3} />
                                </label>
                                <label className="text-xs text-slate-600 dark:text-slate-300">Measure
                                  <input value={o.measurement} onChange={e => updateObjective(o.id, { measurement: e.target.value })} className="mt-1 w-full select-field" />
                                </label>
                                <label className="text-xs text-slate-600 dark:text-slate-300">Target
                                  <input value={o.target} onChange={e => updateObjective(o.id, { target: e.target.value })} className="mt-1 w-full select-field" />
                                </label>
                                <label className="text-xs text-slate-600 dark:text-slate-300">Weight
                                  <input type="number" value={o.weight} onChange={e => updateObjective(o.id, { weight: Number(e.target.value) || 0 })} className="mt-1 w-full select-field" />
                                </label>
                                <label className="text-xs text-slate-600 dark:text-slate-300">Category
                                  <input value={o.category} onChange={e => updateObjective(o.id, { category: e.target.value })} className="mt-1 w-full select-field" />
                                </label>
                                <label className="text-xs text-slate-600 dark:text-slate-300 md:col-span-2">Appraisal
                                  <textarea value={o.rating_guidance_json?.rating_5 ?? ''} onChange={e => updateObjective(o.id, { rating_guidance_json: { ...(o.rating_guidance_json ?? {}), rating_5: e.target.value } })} className="mt-1 w-full select-field" rows={2} />
                                </label>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </>
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
