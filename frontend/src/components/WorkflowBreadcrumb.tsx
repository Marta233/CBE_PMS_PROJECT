import { ChevronRight } from 'lucide-react';

export type BreadcrumbItem = {
  label: string;
  onClick?: () => void;
};

type WorkflowBreadcrumbProps = {
  items: BreadcrumbItem[];
};

export default function WorkflowBreadcrumb({ items }: WorkflowBreadcrumbProps) {
  if (items.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="mb-4 flex items-center flex-wrap gap-x-1.5 gap-y-1 text-sm">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        const content =
          isLast || !item.onClick ? (
            <span
              className={
                isLast
                  ? 'font-semibold text-slate-800 dark:text-white'
                  : 'text-slate-500 dark:text-slate-400'
              }
            >
              {item.label}
            </span>
          ) : (
            <button
              type="button"
              onClick={item.onClick}
              className="text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
            >
              {item.label}
            </button>
          );

        return (
          <span key={`${item.label}-${index}`} className="inline-flex items-center gap-1.5">
            {index > 0 && (
              <ChevronRight size={14} className="text-slate-400 dark:text-slate-500 shrink-0" aria-hidden />
            )}
            {content}
          </span>
        );
      })}
    </nav>
  );
}
