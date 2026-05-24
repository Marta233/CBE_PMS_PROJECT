// Dashboard.tsx  —  Supabase removed; all data is static/in-memory.
import { useState, useMemo } from 'react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  Target, TrendingUp, Users, Star,
  CircleCheck as CheckCircle, Clock,
  CircleAlert as AlertCircle, ChevronDown,
} from 'lucide-react';
import Layout from '../components/Layout';
import { DIVISIONS, DEPARTMENTS, UNITS, JOB_TITLES } from '../types';

const COLORS = ['#2596be', '#10b981', '#f59e0b', '#ef4444', '#1e7ea3', '#06b6d4'];

const trendData = [
  { month: 'Jan', objectives: 45, completed: 12, inProgress: 28 },
  { month: 'Feb', objectives: 52, completed: 18, inProgress: 29 },
  { month: 'Mar', objectives: 61, completed: 22, inProgress: 31 },
  { month: 'Apr', objectives: 58, completed: 31, inProgress: 24 },
  { month: 'May', objectives: 74, completed: 38, inProgress: 30 },
  { month: 'Jun', objectives: 82, completed: 44, inProgress: 32 },
];

const SAMPLE_DATA: Record<string, Array<{ label: string; fullLabel: string; score: number; count: number }>> = {
  division: [
    { label: 'Technology',  fullLabel: 'Technology',          score: 88, count: 24 },
    { label: 'Commercial',  fullLabel: 'Commercial',          score: 84, count: 18 },
    { label: 'Finance',     fullLabel: 'Finance',             score: 79, count: 15 },
    { label: 'Operations',  fullLabel: 'Operations',          score: 72, count: 20 },
    { label: 'Human Res…',  fullLabel: 'Human Resources',     score: 81, count: 12 },
    { label: 'Corporate',   fullLabel: 'Corporate',           score: 76, count: 9  },
    { label: 'Legal & Co…', fullLabel: 'Legal & Compliance',  score: 68, count: 8  },
    { label: 'Strategy &…', fullLabel: 'Strategy & Planning', score: 83, count: 7  },
  ],
  department: [
    { label: 'Engineering',  fullLabel: 'Engineering',          score: 91, count: 14 },
    { label: 'Sales',        fullLabel: 'Sales',                score: 87, count: 10 },
    { label: 'Marketing',    fullLabel: 'Marketing',            score: 83, count: 8  },
    { label: 'Accounting',   fullLabel: 'Accounting',           score: 78, count: 9  },
    { label: 'Product',      fullLabel: 'Product',              score: 85, count: 7  },
    { label: 'Talent Acq…',  fullLabel: 'Talent Acquisition',   score: 74, count: 6  },
    { label: 'Supply Cha…',  fullLabel: 'Supply Chain',         score: 69, count: 8  },
    { label: 'Compliance',   fullLabel: 'Compliance',           score: 72, count: 5  },
  ],
  unit: [
    { label: 'Frontend',    fullLabel: 'Frontend',          score: 93, count: 5 },
    { label: 'Backend',     fullLabel: 'Backend',           score: 88, count: 5 },
    { label: 'DevOps',      fullLabel: 'DevOps',            score: 82, count: 4 },
    { label: 'Enterprise…', fullLabel: 'Enterprise Sales',  score: 90, count: 4 },
    { label: 'Growth',      fullLabel: 'Growth',            score: 85, count: 3 },
    { label: 'QA',          fullLabel: 'QA',                score: 77, count: 4 },
    { label: 'Procurement', fullLabel: 'Procurement',       score: 71, count: 3 },
    { label: 'Gen. Ledger', fullLabel: 'General Ledger',    score: 75, count: 3 },
  ],
  job_title: [
    { label: 'Director',      fullLabel: 'Director',         score: 89, count: 8  },
    { label: 'Manager',       fullLabel: 'Manager',          score: 84, count: 12 },
    { label: 'Sr. Speciali…', fullLabel: 'Senior Specialist',score: 80, count: 10 },
    { label: 'Analyst',       fullLabel: 'Analyst',          score: 76, count: 9  },
    { label: 'Specialist',    fullLabel: 'Specialist',       score: 73, count: 8  },
    { label: 'Sr. Analyst',   fullLabel: 'Senior Analyst',   score: 78, count: 7  },
    { label: 'Coordinator',   fullLabel: 'Coordinator',      score: 65, count: 6  },
    { label: 'Associate',     fullLabel: 'Associate',        score: 61, count: 5  },
  ],
};

const ratingDistData = [
  { name: 'Exceptional (5)', value: 18 },
  { name: 'Exceeds (4)',     value: 34 },
  { name: 'Meets (3)',       value: 29 },
  { name: 'Below (2)',       value: 12 },
  { name: 'Unsatisfactory (1)', value: 7 },
];

const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2', 'Annual'];

const statusColors: Record<string, string> = {
  draft:       'bg-slate-100 text-slate-600',
  in_progress: 'bg-blue-100 text-blue-700',
  completed:   'bg-green-100 text-green-700',
  cancelled:   'bg-red-100 text-red-600',
};

// Static KPI numbers (replace with real aggregated data when backend is live)
const STATIC_STATS = {
  totalObjectives:     113,
  completedObjectives:  44,
  inProgressObjectives: 34,
  totalReviews:         29,
  avgRating:           3.8,
  totalFeedback:        18,
};

const STATIC_RECENT = [
  { id: '1', title: 'Increase digital wallet adoption by 20%',    status: 'in_progress', progress: 65, timeline: 'Q2' },
  { id: '2', title: 'Reduce card dispute resolution time to 48h', status: 'in_progress', progress: 40, timeline: 'H1' },
  { id: '3', title: 'Complete AML policy documentation update',   status: 'completed',   progress: 100, timeline: 'Q1' },
  { id: '4', title: 'Train 50 agents on mobile money procedures', status: 'in_progress', progress: 72, timeline: 'Annual' },
  { id: '5', title: 'Launch internet banking 2FA rollout',        status: 'draft',       progress: 10, timeline: 'Q3' },
];

interface KpiCardProps {
  title: string; value: string; delta: string; positive: boolean;
  icon: React.ElementType; color: string;
}

function KpiCard({ title, value, delta, positive, icon: Icon, color }: KpiCardProps) {
  return (
    <div className="card p-5 hover:shadow-md transition-shadow duration-200">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-lg ${color} flex items-center justify-center`}>
          <Icon size={20} className="text-white" />
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${positive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}>
          {positive ? '↑' : '↓'} {delta}
        </span>
      </div>
      <p className="text-2xl font-bold text-slate-900 mb-0.5">{value}</p>
      <p className="text-sm text-slate-500">{title}</p>
    </div>
  );
}

export default function Dashboard() {
  const stats = STATIC_STATS;
  const recentObjectives = STATIC_RECENT;

  const [perfFilter, setPerfFilter] = useState({
    groupBy:    'department' as 'division' | 'department' | 'unit' | 'job_title',
    division:   '',
    department: '',
    unit:       '',
    job_title:  '',
    quarter:    '',
  });

  // Performance chart: always shows sample data (no DB)
  const perfChartData = useMemo(() => SAMPLE_DATA[perfFilter.groupBy] ?? [], [perfFilter.groupBy]);

  const availableDepartments = perfFilter.division ? DEPARTMENTS[perfFilter.division] || [] : [];
  const availableUnits       = perfFilter.department ? UNITS[perfFilter.department] || [] : [];
  const availableJobTitles   = perfFilter.unit
    ? (UNITS[perfFilter.unit] ? JOB_TITLES : JOB_TITLES)
    : JOB_TITLES;

  return (
    <Layout title="Dashboard" subtitle="Performance management overview">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        <KpiCard title="Total Objectives"   value={String(stats.totalObjectives)}     delta="12%"  positive icon={Target}      color="bg-brand-500" />
        <KpiCard title="Completed"          value={String(stats.completedObjectives)}  delta="8%"   positive icon={CheckCircle} color="bg-green-500" />
        <KpiCard title="In Progress"        value={String(stats.inProgressObjectives)} delta="3%"   positive icon={TrendingUp}  color="bg-blue-500"  />
        <KpiCard title="Total Reviews"      value={String(stats.totalReviews)}         delta="5%"   positive icon={Users}       color="bg-purple-500" />
        <KpiCard title="Avg Rating"         value={stats.avgRating.toFixed(1)}         delta="0.2"  positive icon={Star}        color="bg-amber-500" />
        <KpiCard title="Feedback Records"   value={String(stats.totalFeedback)}        delta="15%"  positive icon={Clock}       color="bg-teal-500"  />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        {/* Trend */}
        <div className="card p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-4">Objective Trend</h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={trendData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#892d8f" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#892d8f" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gDone" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }} />
              <Area type="monotone" dataKey="objectives"  stroke="#892d8f" fill="url(#gTotal)" strokeWidth={2} name="Total"       />
              <Area type="monotone" dataKey="completed"   stroke="#10b981" fill="url(#gDone)"  strokeWidth={2} name="Completed"   />
              <Area type="monotone" dataKey="inProgress"  stroke="#2596be" fill="none"          strokeWidth={2} name="In Progress" strokeDasharray="4 2" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Rating dist */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-4">Rating Distribution</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={ratingDistData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value">
                {ratingDistData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1 mt-2">
            {ratingDistData.map((d, i) => (
              <div key={d.name} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: COLORS[i] }} />
                <span className="text-xs text-slate-500 dark:text-slate-400 flex-1">{d.name}</span>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-200">{d.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Performance by dimension + Recent */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Performance by</h3>
            <div className="flex items-center gap-2 flex-wrap">
              {(['division', 'department', 'unit', 'job_title'] as const).map((g) => (
                <button
                  key={g}
                  onClick={() => setPerfFilter((f) => ({ ...f, groupBy: g }))}
                  className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
                    perfFilter.groupBy === g
                      ? 'border-brand-500 text-brand-600 bg-brand-50 dark:bg-brand-800/20'
                      : 'border-slate-200 text-slate-500 hover:border-slate-300'
                  }`}
                >
                  {g.replace('_', ' ')}
                </button>
              ))}

              {/* Division filter */}
              <div className="relative">
                <select
                  value={perfFilter.division}
                  onChange={(e) => setPerfFilter((f) => ({ ...f, division: e.target.value, department: '', unit: '', job_title: '' }))}
                  className="text-xs pl-2 pr-6 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 appearance-none cursor-pointer"
                >
                  <option value="">All Divisions</option>
                  {DIVISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
                <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>

              {availableDepartments.length > 0 && (
                <div className="relative">
                  <select
                    value={perfFilter.department}
                    onChange={(e) => setPerfFilter((f) => ({ ...f, department: e.target.value, unit: '', job_title: '' }))}
                    className="text-xs pl-2 pr-6 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 appearance-none cursor-pointer"
                  >
                    <option value="">All Depts</option>
                    {availableDepartments.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                  <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
              )}

              <div className="relative">
                <select
                  value={perfFilter.quarter}
                  onChange={(e) => setPerfFilter((f) => ({ ...f, quarter: e.target.value }))}
                  className="text-xs pl-2 pr-6 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 appearance-none cursor-pointer"
                >
                  <option value="">All Quarters</option>
                  {QUARTERS.map((q) => <option key={q} value={q}>{q}</option>)}
                </select>
                <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={perfChartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                formatter={(v, _name, props) => [`${v}%`, `Avg Progress (${props.payload.count} objectives)`]}
                labelFormatter={(_label, payload) => payload?.[0]?.payload?.fullLabel || _label}
              />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {perfChartData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.score >= 75 ? '#10b981' : entry.score >= 50 ? '#2596be' : entry.score >= 25 ? '#f59e0b' : '#ef4444'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <div className="flex items-center gap-4 mt-3 flex-wrap">
            {[
              { color: '#10b981', label: '≥75% On track' },
              { color: '#2596be', label: '50–74% In progress' },
              { color: '#f59e0b', label: '25–49% Behind' },
              { color: '#ef4444', label: '<25% At risk' },
            ].map((l) => (
              <div key={l.label} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: l.color }} />
                <span className="text-xs text-slate-500 dark:text-slate-400">{l.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Objectives */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-4">Recent Objectives</h3>
          <div className="space-y-3">
            {recentObjectives.map((obj) => (
              <div key={obj.id} className="flex items-start gap-2.5">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{obj.title}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full bg-brand-500 rounded-full" style={{ width: `${obj.progress}%` }} />
                    </div>
                    <span className="text-xs text-slate-400 flex-shrink-0">{obj.progress}%</span>
                  </div>
                </div>
                <span className={`badge text-xs flex-shrink-0 ${statusColors[obj.status] || 'bg-slate-100 text-slate-600'}`}>
                  {obj.status.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  );
}
