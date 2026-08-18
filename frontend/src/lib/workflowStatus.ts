export function workflowStatusLabel(status: string): string {
  return status.replaceAll('_', ' ');
}

export function workflowStatusBadgeCls(status: string): string {
  switch (status) {
    case 'draft':
      return 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-200';
    case 'saved':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200';
    case 'activated_to_director':
      return 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-200';
    case 'director_rejected_to_manager':
    case 'vp_rejected_to_director':
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-200';
    case 'director_approved_and_activated_to_vp':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-200';
    case 'vp_approved_final':
      return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200';
    case 'sent_to_pms':
      return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-200';
    default:
      return 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-200';
  }
}

