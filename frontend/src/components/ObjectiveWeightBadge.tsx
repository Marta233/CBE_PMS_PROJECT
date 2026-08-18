type ObjectiveWeightBadgeProps = {
  weights: number[];
};

export default function ObjectiveWeightBadge({ weights }: ObjectiveWeightBadgeProps) {
  const total = weights.reduce((sum, w) => sum + (Number(w) || 0), 0);
  const isPerfect = total === 100;

  return (
    <span
      className={`text-xs font-semibold px-2.5 py-1 rounded-full shrink-0 ${
        isPerfect
          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
          : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
      }`}
    >
      Total: {total}%{isPerfect ? ' ✓' : ' — must be 100%'}
    </span>
  );
}
