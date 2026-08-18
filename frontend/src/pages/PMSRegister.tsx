import { useEffect, useMemo, useState } from 'react';
import Layout from '../components/Layout';
import ObjectiveWeightBadge from '../components/ObjectiveWeightBadge';
import WorkflowBreadcrumb from '../components/WorkflowBreadcrumb';
import WorkflowMenuCard from '../components/WorkflowMenuCard';
import { workflowStatusLabel } from '../lib/workflowStatus';
import { DEPARTMENTS, DIVISIONS, UNITS } from '../types';

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
  status: string;
  current_version: number;
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
  rating_guidance_json?: { rating_5?: string } | null;
};

type SetDetail = {
  id: number;
  unit: { id: number; name: string; division: string; department: string };
  objectives: ObjectiveRow[];
  position_statuses?: { position_id: number; status: string }[];
};

type PositionRow = { id: number; title: string };

export default function PMSRegister() {
  const [rows, setRows] = useState<ObjectiveSetRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedDivision, setSelectedDivision] = useState<string | null>(null);
  const [selectedDepartment, setSelectedDepartment] = useState<string | null>(null);
  const [selectedUnitName, setSelectedUnitName] = useState<string | null>(null);
  const [selectedSetId, setSelectedSetId] = useState<number | null>(null);
  const [selectedPositionId, setSelectedPositionId] = useState<number | null>(null);
  const [expandedObjectiveId, setExpandedObjectiveId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SetDetail | null>(null);
  const [positionsById, setPositionsById] = useState<Record<number, PositionRow>>({});

  const finalRows = useMemo(
    () => rows.filter(r =>
      r.status === 'sent_to_pms'
      || (r.position_statuses || []).some(p => p.status === 'sent_to_pms'),
    ),
    [rows],
  );

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/objective-sets?status=sent_to_pms');
      if (!res.ok) throw new Error(await res.text());
      setRows(await res.json() as ObjectiveSetRow[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load finalized sets.');
    } finally {
      setLoading(false);
    }
  }

  async function loadSetDetail(setId: number) {
    const target = finalRows.find(r => r.id === setId);
    if (!target) return;
    const dRes = await apiFetch(`/api/objective-sets/${setId}`);
    if (!dRes.ok) throw new Error(await dRes.text());
    const dJson = await dRes.json() as SetDetail;
    const pRes = await apiFetch(`/api/objective-sets/positions?unit_id=${target.unit_id}`);
    if (!pRes.ok) throw new Error(await pRes.text());
    const pJson = await pRes.json() as Array<{ id: number; title: string }>;
    const map: Record<number, PositionRow> = {};
    pJson.forEach(p => { map[p.id] = p; });
    setPositionsById(map);
    setDetail(dJson);
  }

  useEffect(() => { refresh(); }, []);

  const divisionCards = useMemo(() => {
    const map = new Map<string, number>();
    DIVISIONS.forEach(d => map.set(d, 0));
    finalRows.forEach(r => map.set(r.unit.division, (map.get(r.unit.division) ?? 0) + 1));
    return Array.from(map.entries()).map(([name, count]) => ({ name, count }));
  }, [finalRows]);

  const departments = useMemo(() => {
    const map = new Map<string, number>();
    (selectedDivision ? (DEPARTMENTS[selectedDivision] || []) : []).forEach(d => map.set(d, 0));
    finalRows.filter(r => selectedDivision ? r.unit.division === selectedDivision : false)
      .forEach(r => map.set(r.unit.department, (map.get(r.unit.department) ?? 0) + 1));
    return Array.from(map.entries()).map(([name, count]) => ({ name, count }));
  }, [finalRows, selectedDivision]);

  const units = useMemo(() => {
    const map = new Map<string, { name: string; count: number }>();
    (selectedDepartment ? (UNITS[selectedDepartment] || []) : []).forEach(u => map.set(u, { name: u, count: 0 }));
    finalRows
      .filter(r => (selectedDivision ? r.unit.division === selectedDivision : false) && (selectedDepartment ? r.unit.department === selectedDepartment : false))
      .forEach(r => {
        const key = r.unit.name;
        const x = map.get(key);
        if (x) x.count += 1;
        else map.set(key, { name: r.unit.name, count: 1 });
      });
    return Array.from(map.values());
  }, [finalRows, selectedDivision, selectedDepartment]);

  const setsForUnit = useMemo(
    () => finalRows.filter(r => (selectedUnitName ? r.unit.name === selectedUnitName : false)),
    [finalRows, selectedUnitName],
  );

  const objectivesForPosition = useMemo(
    () => detail?.objectives.filter(o => o.position_id === selectedPositionId) ?? [],
    [detail, selectedPositionId],
  );

  function resetToDivisions() {
    setSelectedDivision(null);
    setSelectedDepartment(null);
    setSelectedUnitName(null);
    setSelectedSetId(null);
    setSelectedPositionId(null);
    setDetail(null);
  }

  function resetToDepartments() {
    setSelectedDepartment(null);
    setSelectedUnitName(null);
    setSelectedSetId(null);
    setSelectedPositionId(null);
    setDetail(null);
  }

  function resetToUnits() {
    setSelectedUnitName(null);
    setSelectedSetId(null);
    setSelectedPositionId(null);
    setDetail(null);
  }

  const breadcrumbItems = useMemo(() => {
    const root = selectedDivision || 'Digital Banking';
    const items: { label: string; onClick?: () => void }[] = [
      {
        label: root,
        onClick: selectedDivision || selectedDepartment || selectedUnitName
          ? resetToDivisions
          : undefined,
      },
    ];
    if (selectedDepartment) {
      items.push({
        label: `${selectedDepartment} Director`,
        onClick: selectedUnitName ? resetToDepartments : undefined,
      });
    }
    if (selectedUnitName) {
      items.push({
        label: selectedUnitName,
        onClick: selectedSetId ? resetToUnits : undefined,
      });
    }
    return items;
  }, [selectedDivision, selectedDepartment, selectedUnitName, selectedSetId]);

  return (
    <Layout title="PMS Register" subtitle="Final workflow registry by division, department, and unit.">
      <WorkflowBreadcrumb items={breadcrumbItems} />

      {error && (
        <div className="mb-4 p-3 rounded-lg border border-red-200 dark:border-red-800/40 bg-red-50/60 dark:bg-red-900/15 text-sm text-red-700 dark:text-red-200">
          {error}
        </div>
      )}

      <div className="card p-5 mb-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">Select Division</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">{finalRows.length} finalized set(s) {loading ? '(loading...)' : ''}</p>
          </div>
          <button className="btn-secondary" onClick={refresh}>Refresh</button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {divisionCards.map(d => (
            <WorkflowMenuCard
              key={d.name}
              title={d.name}
              pendingCount={d.count}
              badge={`${d.count} set(s)`}
              selected={selectedDivision === d.name}
              onClick={() => {
                setSelectedDivision(d.name);
                setSelectedDepartment(null);
                setSelectedUnitName(null);
                setSelectedSetId(null);
                setDetail(null);
              }}
            />
          ))}
        </div>
      </div>

      {selectedDivision && (
        <div className="card p-5 mb-5">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">Select Department</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {departments.map(d => (
              <WorkflowMenuCard
                key={d.name}
                title={d.name}
                pendingCount={d.count}
                badge={`${d.count} set(s)`}
                selected={selectedDepartment === d.name}
                onClick={() => {
                  setSelectedDepartment(d.name);
                  setSelectedUnitName(null);
                  setSelectedSetId(null);
                  setDetail(null);
                }}
              />
            ))}
          </div>
        </div>
      )}

      {selectedDepartment && (
        <div className="card p-5 mb-5">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">Select Unit</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {units.map(u => (
              <WorkflowMenuCard
                key={u.name}
                title={u.name}
                pendingCount={u.count}
                badge={`${u.count} set(s)`}
                selected={selectedUnitName === u.name}
                onClick={() => {
                  setSelectedUnitName(u.name);
                  setSelectedSetId(null);
                  setDetail(null);
                }}
              />
            ))}
          </div>
        </div>
      )}

      {selectedUnitName && (
        <div className="card p-5 mb-5">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">Select Finalized Set</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {setsForUnit.map(r => (
              <WorkflowMenuCard
                key={r.id}
                title={`Set #${r.id}`}
                subtitle={`Finalized ${new Date(r.updated_at).toLocaleString()}`}
                pendingCount={1}
                badge={workflowStatusLabel(r.status)}
                selected={selectedSetId === r.id}
                onClick={() => {
                  setSelectedSetId(r.id);
                  setSelectedPositionId(null);
                  setExpandedObjectiveId(null);
                  loadSetDetail(r.id).catch(e => setError(String(e)));
                }}
              />
            ))}
            {setsForUnit.length === 0 && (
              <div className="col-span-full text-sm text-slate-500 dark:text-slate-400 py-6 text-center border border-dashed border-slate-300 dark:border-slate-700 rounded-xl">
                No finalized sets yet for this unit. Card shown for indicative workflow.
              </div>
            )}
          </div>
        </div>
      )}

      {detail && (
        <div className="card p-5">
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-4">
            PMS View · Set #{detail.id} · {detail.unit.name}
          </h3>
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            <div className="lg:col-span-1 border border-slate-200 dark:border-slate-700 rounded-xl p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Positions</p>
              <div className="space-y-2">
                {Array.from(new Set(detail.objectives.map(o => o.position_id)))
                  .filter(pid => {
                    const st = (detail.position_statuses || []).find(p => p.position_id === pid)?.status;
                    return !st || st === 'sent_to_pms';
                  })
                  .map(pid => (
                  <button
                    key={pid}
                    onClick={() => {
                      setSelectedPositionId(pid);
                      setExpandedObjectiveId(null);
                    }}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                      selectedPositionId === pid
                        ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200'
                        : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200'
                    }`}
                  >
                    {positionsById[pid]?.title ?? `Position #${pid}`}
                  </button>
                ))}
              </div>
            </div>
            <div className="lg:col-span-3 border border-slate-200 dark:border-slate-700 rounded-xl p-3">
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Objectives</p>
                {selectedPositionId && objectivesForPosition.length > 0 && (
                  <ObjectiveWeightBadge weights={objectivesForPosition.map(o => o.weight)} />
                )}
              </div>
              {!selectedPositionId && (
                <p className="text-sm text-slate-500 dark:text-slate-400 py-8 text-center">Choose a position to view finalized objectives.</p>
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
                          <div className="p-3 border-t border-slate-200 dark:border-slate-700 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                            <p><span className="font-medium">Measure:</span> {o.measurement}</p>
                            <p><span className="font-medium">Target:</span> {o.target}</p>
                            <p><span className="font-medium">Category:</span> {o.category}</p>
                            <p><span className="font-medium">Tracking:</span> {o.tracking_source}</p>
                            <p><span className="font-medium">Time Frame:</span> {o.time_frame}</p>
                            <p><span className="font-medium">Appraisal:</span> {o.rating_guidance_json?.rating_5 ?? '-'}</p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
