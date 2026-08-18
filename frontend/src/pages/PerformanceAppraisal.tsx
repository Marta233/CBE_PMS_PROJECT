// PerformanceAppraisal.tsx  —  Supabase removed; state is in-memory React only.

import { useState } from 'react';
import { Star, Plus, ChevronDown, Trash2, CircleCheck as CheckCircle, Download } from 'lucide-react';
import Layout from '../components/Layout';
import { DEPARTMENTS, JOB_TITLES, type PerformanceReview } from '../types';

const PERIODS = ['Q1 2026', 'Q2 2026', 'H1 2026', 'Annual 2025', 'Annual 2026'];

function uid() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }

// ── Sample reviews ────────────────────────────────────────────────────────────
const SAMPLE_REVIEWS: PerformanceReview[] = [
  { id: '1', employee_name: 'Abebe Girma',    department: 'Card Banking',          job_title: 'Manager Card Banking Business',   rating: 4, comments: 'Consistently exceeds expectations on card operations KPIs.',   period: 'Annual 2025', status: 'approved', created_at: new Date().toISOString() },
  { id: '2', employee_name: 'Mekdes Haile',   department: 'Mobile and Internet Banking', job_title: 'Senior Digital Banking Officer', rating: 5, comments: 'Outstanding leadership in the 2FA rollout project.',           period: 'Q1 2026',     status: 'approved', created_at: new Date().toISOString() },
  { id: '3', employee_name: 'Solomon Tesfaye', department: 'Internal Control',     job_title: 'Internal Control Officer',        rating: 3, comments: 'Meets expectations; opportunity to improve documentation speed.', period: 'Annual 2025', status: 'pending',  created_at: new Date().toISOString() },
];

function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((s) => (
        <button key={s} type="button" onClick={() => onChange(s)}
          onMouseEnter={() => setHover(s)} onMouseLeave={() => setHover(0)} className="focus:outline-none">
          <Star size={22} className={`transition-colors ${s <= (hover || value) ? 'fill-amber-400 text-amber-400' : 'text-slate-200'}`} />
        </button>
      ))}
    </div>
  );
}

const ratingLabels: Record<number, { label: string; color: string }> = {
  1: { label: 'Unsatisfactory',     color: 'text-red-600'    },
  2: { label: 'Below Expectations', color: 'text-orange-600' },
  3: { label: 'Meets Expectations', color: 'text-amber-600'  },
  4: { label: 'Exceeds Expectations', color: 'text-blue-600' },
  5: { label: 'Exceptional',        color: 'text-green-600'  },
};

function downloadCSV(reviews: PerformanceReview[]) {
  const header = ['Employee', 'Department', 'Job Title', 'Rating', 'Label', 'Period', 'Status', 'Comments'];
  const rows = reviews.map((r) => [
    `"${r.employee_name}"`, `"${r.department}"`, `"${r.job_title}"`,
    r.rating, ratingLabels[Math.round(r.rating)]?.label ?? '',
    r.period, r.status,
    `"${(r.comments || '').replace(/"/g, '""')}"`,
  ]);
  const csv = [header.join(','), ...rows.map((r) => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'performance-reviews.csv'; a.click();
  URL.revokeObjectURL(url);
}

export default function PerformanceAppraisal() {
  const [reviews, setReviews]     = useState<PerformanceReview[]>(SAMPLE_REVIEWS);
  const [showForm, setShowForm]   = useState(false);
  const [saving, setSaving]       = useState(false);

  const [form, setForm] = useState({
    employee_name: '', department: '', job_title: '',
    rating: 3, comments: '', period: 'Annual 2025',
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.employee_name || !form.department) return;
    setSaving(true);
    setTimeout(() => {
      const newReview: PerformanceReview = {
        ...form, id: uid(), status: 'pending', created_at: new Date().toISOString(),
      };
      setReviews((prev) => [newReview, ...prev]);
      setForm({ employee_name: '', department: '', job_title: '', rating: 3, comments: '', period: 'Annual 2025' });
      setShowForm(false);
      setSaving(false);
    }, 200);
  }

  function updateStatus(id: string, status: string) {
    setReviews((prev) => prev.map((r) => (r.id === id ? { ...r, status } : r)));
  }

  function deleteReview(id: string) {
    setReviews((prev) => prev.filter((r) => r.id !== id));
  }

  const allDepts = Object.values(DEPARTMENTS).flat();

  return (
    <Layout
      title="Performance Appraisal"
      subtitle="Conduct and manage employee performance reviews"
      actions={
        <div className="flex gap-2">
          <button onClick={() => downloadCSV(reviews)} className="btn-secondary text-xs flex items-center gap-1.5">
            <Download size={14} /> Export CSV
          </button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
            <Plus size={14} />New Review
          </button>
        </div>
      }
    >
      {/* New Review Form */}
      {showForm && (
        <div className="card p-6 mb-5 animate-slide-up border-l-4 border-l-brand-500">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-4">New Performance Review</h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Employee Name</label>
                <input type="text" value={form.employee_name}
                  onChange={(e) => setForm({ ...form, employee_name: e.target.value })}
                  className="select-field" placeholder="Full name" required />
              </div>
              <div>
                <label className="label">Department</label>
                <div className="relative">
                  <select value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}
                    className="select-field pr-8" required>
                    <option value="">Select department</option>
                    {allDepts.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
              </div>
              <div>
                <label className="label">Job Title</label>
                <div className="relative">
                  <select value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} className="select-field pr-8">
                    <option value="">Select title</option>
                    {JOB_TITLES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
              </div>
              <div>
                <label className="label">Review Period</label>
                <div className="relative">
                  <select value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} className="select-field pr-8">
                    {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
              </div>
            </div>

            <div>
              <label className="label">Overall Rating</label>
              <div className="flex items-center gap-4">
                <StarRating value={form.rating} onChange={(v) => setForm({ ...form, rating: v })} />
                <span className={`text-sm font-medium ${ratingLabels[form.rating]?.color}`}>
                  {ratingLabels[form.rating]?.label}
                </span>
              </div>
            </div>

            <div>
              <label className="label">Comments & Notes</label>
              <textarea value={form.comments} onChange={(e) => setForm({ ...form, comments: e.target.value })}
                className="select-field resize-none" rows={3}
                placeholder="Performance summary, key achievements, areas for improvement..." />
            </div>

            <div className="flex gap-3">
              <button type="submit" disabled={saving} className="btn-primary">
                {saving ? 'Saving...' : 'Submit Review'}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Reviews List */}
      {reviews.length === 0 ? (
        <div className="card p-12 text-center">
          <Star size={32} className="text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-slate-500">No reviews yet. Click "New Review" to create one.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {reviews.map((r) => (
            <div key={r.id} className="card p-5 hover:shadow-sm transition-shadow group">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-slate-900 dark:text-white text-sm">{r.employee_name}</h3>
                    <span className="text-xs text-slate-400">&bull;</span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">{r.job_title || 'N/A'}</span>
                    <span className="text-xs text-slate-400">&bull;</span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">{r.department}</span>
                  </div>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <Star key={s} size={14} className={s <= r.rating ? 'fill-amber-400 text-amber-400' : 'text-slate-200 dark:text-slate-600'} />
                      ))}
                    </div>
                    <span className={`text-xs font-medium ${ratingLabels[Math.round(r.rating)]?.color || 'text-slate-600'}`}>
                      {ratingLabels[Math.round(r.rating)]?.label}
                    </span>
                    <span className="text-xs text-slate-400">Period: {r.period}</span>
                  </div>
                  {r.comments && <p className="text-sm text-slate-600 dark:text-slate-300 line-clamp-2">{r.comments}</p>}
                </div>
                <div className="flex items-center gap-2 ml-4 opacity-0 group-hover:opacity-100 transition-opacity">
                  {r.status === 'pending' && (
                    <button onClick={() => updateStatus(r.id, 'approved')}
                      className="text-xs flex items-center gap-1 text-green-600 hover:text-green-700 bg-green-50 hover:bg-green-100 px-2.5 py-1 rounded-lg transition-colors">
                      <CheckCircle size={13} /> Approve
                    </button>
                  )}
                  <button onClick={() => deleteReview(r.id)} className="p-1.5 text-slate-300 hover:text-red-500 transition-colors rounded">
                    <Trash2 size={14} />
                  </button>
                </div>
                <span className={`ml-3 badge flex-shrink-0 ${r.status === 'approved' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-600'}`}>
                  {r.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
