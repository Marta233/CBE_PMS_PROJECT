type WorkflowMenuCardProps = {
  title: string;
  subtitle?: string;
  pendingCount?: number;
  badge?: string;
  selected?: boolean;
  selectable?: boolean;
  checked?: boolean;
  onCheckChange?: (checked: boolean) => void;
  onClick: () => void;
};

export default function WorkflowMenuCard({
  title,
  subtitle,
  pendingCount = 0,
  badge,
  selected = false,
  selectable = false,
  checked = false,
  onCheckChange,
  onClick,
}: WorkflowMenuCardProps) {
  const hasPending = pendingCount > 0;

  return (
    <div
      className={`group relative rounded-xl border bg-white dark:bg-slate-800/60 p-4 cursor-pointer transition-all duration-200 ease-out ${
        selected
          ? 'border-purple-400 bg-purple-50/70 dark:bg-purple-900/25 shadow-md shadow-purple-200/50 dark:shadow-purple-950/40 -translate-y-0.5'
          : 'border-slate-200 dark:border-slate-700 shadow-sm hover:border-purple-400 hover:bg-purple-50/50 dark:hover:bg-purple-900/20 hover:shadow-lg hover:shadow-purple-200/40 dark:hover:shadow-purple-950/50 hover:-translate-y-1'
      }`}
    >
      {selectable && (
        <input
          type="checkbox"
          checked={checked}
          disabled={!hasPending}
          onChange={e => onCheckChange?.(e.target.checked)}
          className="absolute top-3 left-3 accent-purple-700"
          aria-label={`Select ${title}`}
        />
      )}
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left ${selectable ? 'pl-6' : ''}`}
    >
      {hasPending && (
        <span
          className="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 rounded-full bg-emerald-500 ring-2 ring-white dark:ring-slate-800 shadow-sm"
          title={`${pendingCount} pending`}
          aria-label={`${pendingCount} pending`}
        />
      )}
      <p className={`text-sm font-semibold pr-4 transition-colors ${
        selected
          ? 'text-purple-800 dark:text-purple-200'
          : 'text-slate-800 dark:text-slate-100 group-hover:text-purple-700 dark:group-hover:text-purple-300'
      }`}>{title}</p>
      {subtitle && (
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{subtitle}</p>
      )}
      {badge && (
        <p className={`mt-2 text-xs inline-flex px-2 py-0.5 rounded-full ${
          hasPending
            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
            : 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-200'
        }`}>
          {badge}
        </p>
      )}
    </button>
    </div>
  );
}
