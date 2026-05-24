// FeedbackCoaching.tsx  —  Supabase removed; state is in-memory React only.

import { useState } from 'react';
import {
  MessageSquareHeart, Plus, ChevronDown, Trash2,
  ThumbsUp, BookOpen, Lightbulb, Download,
} from 'lucide-react';
import Layout from '../components/Layout';
import { DEPARTMENTS, type FeedbackRecord } from '../types';

function uid() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }

const FEEDBACK_TYPES = [
  { value: 'coaching',     label: 'Coaching',     icon: BookOpen,  color: 'bg-blue-100 text-blue-700'  },
  { value: 'recognition',  label: 'Recognition',  icon: ThumbsUp,  color: 'bg-green-100 text-green-700' },
  { value: 'development',  label: 'Development',  icon: Lightbulb, color: 'bg-amber-100 text-amber-700' },
];

// ── Sample records ────────────────────────────────────────────────────────────
const SAMPLE_RECORDS: FeedbackRecord[] = [
  { id: '1', employee_name: 'Abebe Girma',    department: 'Card Banking',          feedback_type: 'recognition',
    content: 'Exceptional performance during the card issuance upgrade. Stayed late to resolve production issues without being asked.',
    rating: null, created_at: new Date(Date.now() - 86400000 * 3).toISOString() },
  { id: '2', employee_name: 'Mekdes Haile',   department: 'Mobile and Internet Banking', feedback_type: 'coaching',
    content: 'We discussed improving stakeholder communication during project status updates. Agreed to send weekly email summaries starting next sprint.',
    rating: null, created_at: new Date(Date.now() - 86400000 * 7).toISOString() },
  { id: '3', employee_name: 'Solomon Tesfaye', department: 'Internal Control',     feedback_type: 'development',
    content: 'Recommended enrolling in the AML Advanced Certification programme offered by the CBE training unit to strengthen compliance skills.',
    rating: null, created_at: new Date(Date.now() - 86400000 * 14).toISOString() },
];

function downloadCSV(records: FeedbackRecord[]) {
  const header = ['Employee', 'Department', 'Type', 'Date', 'Content'];
  const rows = records.map((r) => [
    `"${r.employee_name}"`, `"${r.department}"`, r.feedback_type,
    new Date(r.created_at).toLocaleDateString(),
    `"${r.content.replace(/"/g, '""')}"`,
  ]);
  const csv = [header.join(','), ...rows.map((r) => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'feedback-records.csv'; a.click();
  URL.revokeObjectURL(url);
}

export default function FeedbackCoaching() {
  const [records, setRecords]   = useState<FeedbackRecord[]>(SAMPLE_RECORDS);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving]     = useState(false);
  const [activeType, setActiveType] = useState('all');

  const [form, setForm] = useState({
    employee_name: '', department: '', feedback_type: 'coaching', content: '',
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.employee_name || !form.content) return;
    setSaving(true);
    setTimeout(() => {
      const newRecord: FeedbackRecord = {
        ...form, id: uid(), rating: null, created_at: new Date().toISOString(),
      };
      setRecords((prev) => [newRecord, ...prev]);
      setForm({ employee_name: '', department: '', feedback_type: 'coaching', content: '' });
      setShowForm(false);
      setSaving(false);
    }, 200);
  }

  function deleteRecord(id: string) {
    setRecords((prev) => prev.filter((r) => r.id !== id));
  }

  const allDepts = Object.values(DEPARTMENTS).flat();
  const filtered = activeType === 'all' ? records : records.filter((r) => r.feedback_type === activeType);

  const counts = {
    all:         records.length,
    coaching:    records.filter((r) => r.feedback_type === 'coaching').length,
    recognition: records.filter((r) => r.feedback_type === 'recognition').length,
    development: records.filter((r) => r.feedback_type === 'development').length,
  };

  return (
    <Layout
      title="Feedback & Coaching"
      subtitle="Document coaching conversations and recognition"
      actions={
        <div className="flex gap-2">
          <button onClick={() => downloadCSV(filtered)} className="btn-secondary text-xs flex items-center gap-1.5">
            <Download size={14} /> Export CSV
          </button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary text-xs">
            <Plus size={14} />Add Feedback
          </button>
        </div>
      }
    >
      {/* Type Tabs */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {[
          { key: 'all',         label: 'All' },
          { key: 'coaching',    label: 'Coaching' },
          { key: 'recognition', label: 'Recognition' },
          { key: 'development', label: 'Development' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveType(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all duration-150 flex items-center gap-2 ${
              activeType === tab.key
                ? 'bg-slate-900 text-white border-slate-900 dark:bg-slate-100 dark:text-slate-900'
                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
            }`}
          >
            {tab.label}
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${activeType === tab.key ? 'bg-white/20' : 'bg-slate-100 text-slate-500 dark:bg-slate-700'}`}>
              {counts[tab.key as keyof typeof counts]}
            </span>
          </button>
        ))}
      </div>

      {/* Form */}
      {showForm && (
        <div className="card p-6 mb-5 animate-slide-up border-l-4 border-l-brand-500">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-4">New Feedback Entry</h3>
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
                  <select value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className="select-field pr-8">
                    <option value="">Select department</option>
                    {allDepts.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
              </div>
            </div>

            <div>
              <label className="label">Feedback Type</label>
              <div className="flex gap-3">
                {FEEDBACK_TYPES.map((t) => {
                  const Icon = t.icon;
                  return (
                    <button key={t.value} type="button" onClick={() => setForm({ ...form, feedback_type: t.value })}
                      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                        form.feedback_type === t.value
                          ? `${t.color} border-current`
                          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300'
                      }`}>
                      <Icon size={15} />{t.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="label">Feedback Content</label>
              <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })}
                className="select-field resize-none" rows={4}
                placeholder="Describe the feedback, coaching session, or recognition in detail..." required />
            </div>

            <div className="flex gap-3">
              <button type="submit" disabled={saving} className="btn-primary">
                {saving ? 'Saving...' : 'Save Feedback'}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Records */}
      {filtered.length === 0 ? (
        <div className="card p-12 text-center">
          <MessageSquareHeart size={32} className="text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-slate-500">No feedback records yet. Click "Add Feedback" to start.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((record) => {
            const typeInfo = FEEDBACK_TYPES.find((t) => t.value === record.feedback_type);
            const Icon = typeInfo?.icon || MessageSquareHeart;
            return (
              <div key={record.id} className="card p-5 hover:shadow-sm transition-shadow group">
                <div className="flex items-start justify-between mb-3">
                  <div className={`flex items-center gap-2 badge ${typeInfo?.color || 'bg-slate-100 text-slate-600'}`}>
                    <Icon size={12} />{typeInfo?.label || record.feedback_type}
                  </div>
                  <button onClick={() => deleteRecord(record.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-300 hover:text-red-500 transition-all rounded">
                    <Trash2 size={13} />
                  </button>
                </div>
                <h3 className="font-semibold text-slate-900 dark:text-white text-sm mb-0.5">{record.employee_name}</h3>
                {record.department && <p className="text-xs text-slate-400 mb-2">{record.department}</p>}
                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed line-clamp-4">{record.content}</p>
                <p className="text-xs text-slate-400 mt-3">
                  {new Date(record.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </Layout>
  );
}
