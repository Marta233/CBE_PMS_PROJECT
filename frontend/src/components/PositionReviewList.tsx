import { workflowStatusBadgeCls, workflowStatusLabel } from '../lib/workflowStatus';

type PositionItem = {
  id: number;
  title: string;
  objectiveCount: number;
  isNew?: boolean;
  status?: string | null;
  checkable?: boolean;
};

type PositionReviewListProps = {
  positions: PositionItem[];
  selectedPositionId: number | null;
  checkedPositionIds: Set<number>;
  onSelectPosition: (id: number) => void;
  onToggleCheck: (id: number) => void;
  onSelectAll: () => void;
  onClearChecks: () => void;
};

export default function PositionReviewList({
  positions,
  selectedPositionId,
  checkedPositionIds,
  onSelectPosition,
  onToggleCheck,
  onSelectAll,
  onClearChecks,
}: PositionReviewListProps) {
  const reviewable = positions.filter(p => p.checkable !== false && p.objectiveCount > 0);
  const allChecked = reviewable.length > 0 && reviewable.every(p => checkedPositionIds.has(p.id));

  return (
    <div>
      <div className="flex items-center justify-between mb-2 gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Positions</p>
        <div className="flex items-center gap-2">
          <button type="button" className="text-[11px] text-purple-700 dark:text-purple-300 hover:underline" onClick={onSelectAll}>
            Select all
          </button>
          <button type="button" className="text-[11px] text-slate-500 hover:underline" onClick={onClearChecks}>
            Clear
          </button>
        </div>
      </div>
      <p className="text-[11px] text-slate-400 mb-2">
        {checkedPositionIds.size} of {reviewable.length} selected for approval
      </p>
      <div className="space-y-2">
        {positions.map(p => {
          const hasObjectives = p.objectiveCount > 0;
          const canCheck = hasObjectives && p.checkable !== false;
          const isChecked = checkedPositionIds.has(p.id);
          const isActive = selectedPositionId === p.id;

          return (
            <div
              key={p.id}
              className={`flex items-center gap-2 rounded-lg border px-2 py-2 ${
                !hasObjectives
                  ? 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 opacity-75'
                  : isActive
                    ? 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800'
                    : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-800/60'
              }`}
            >
              <input
                type="checkbox"
                disabled={!canCheck}
                checked={isChecked}
                onChange={() => onToggleCheck(p.id)}
                className="accent-purple-700"
                aria-label={`Select ${p.title}`}
              />
              <button
                type="button"
                disabled={!hasObjectives}
                onClick={() => onSelectPosition(p.id)}
                className={`flex-1 text-left text-sm ${
                  !hasObjectives
                    ? 'text-slate-400 cursor-not-allowed'
                    : 'text-slate-700 dark:text-slate-200'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span>{p.title}</span>
                  <span className="flex items-center gap-1 flex-shrink-0">
                    {hasObjectives && p.isNew && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                        New
                      </span>
                    )}
                    {hasObjectives && p.status && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${workflowStatusBadgeCls(p.status)}`}>
                        {workflowStatusLabel(p.status)}
                      </span>
                    )}
                  </span>
                </div>
              </button>
            </div>
          );
        })}
      </div>
      {allChecked && reviewable.length > 0 && (
        <p className="mt-2 text-[11px] text-emerald-600 dark:text-emerald-400">All reviewable positions selected — ready to approve.</p>
      )}
    </div>
  );
}
