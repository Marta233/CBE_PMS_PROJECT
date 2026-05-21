import { useEffect, useState, useMemo } from 'react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { Target, TrendingUp, Users, Star, CircleCheck as CheckCircle, Clock, CircleAlert as AlertCircle, ChevronDown } from 'lucide-react';
import Layout from '../components/Layout';
import { supabase } from '../lib/supabase';
import { DIVISIONS, DEPARTMENTS, UNITS, JOB_TITLES } from '../types';

const COLORS = ['#7C3AED', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

const trendData = [
  { month: 'Jan', objectives: 45, completed: 12, inProgress: 28 },
  { month: 'Feb', objectives: 52, completed: 18, inProgress: 29 },
  { month: 'Mar', objectives: 61, completed: 22, inProgress: 31 },
  { month: 'Apr', objectives: 58, completed: 31, inProgress: 24 },
  { month: 'May', objectives: 74, completed: 38, inProgress: 30 },
  { month: 'Jun', objectives: 82, completed: 44, inProgress: 32 },
];

// Sample fallback data per groupBy dimension (shown when DB has no objectives)
const SAMPLE_DATA: Record<string, Array<{ label: string; fullLabel: string; score: number; count: number }>> = {
  division: [
    { label: 'Technology',    fullLabel: 'Technology',         score: 88, count: 24 },
    { label: 'Commercial',    fullLabel: 'Commercial',         score: 84, count: 18 },
    { label: 'Finance',       fullLabel: 'Finance',            score: 79, count: 15 },
    { label: 'Operations',    fullLabel: 'Operations',         score: 72, count: 20 },
    { label: 'Human Res…',    fullLabel: 'Human Resources',    score: 81, count: 12 },
    { label: 'Corporate',     fullLabel: 'Corporate',          score: 76, count: 9  },
    { label: 'Legal & Co…',   fullLabel: 'Legal & Compliance', score: 68, count: 8  },
    { label: 'Strategy &…',   fullLabel: 'Strategy & Planning',score: 83, count: 7  },
  ],
  department: [
    { label: 'Engineering',   fullLabel: 'Engineering',                    score: 91, count: 14 },
    { label: 'Sales',         fullLabel: 'Sales',                          score: 87, count: 10 },
    { label: 'Marketing',     fullLabel: 'Marketing',                      score: 83, count: 8  },
    { label: 'Accounting',    fullLabel: 'Accounting',                     score: 78, count: 9  },
    { label: 'Product',       fullLabel: 'Product',                        score: 85, count: 7  },
    { label: 'Talent Acq…',   fullLabel: 'Talent Acquisition',             score: 74, count: 6  },
    { label: 'Supply Cha…',   fullLabel: 'Supply Chain',                   score: 69, count: 8  },
    { label: 'Compliance',    fullLabel: 'Compliance',                     score: 72, count: 5  },
  ],
  unit: [
    { label: 'Frontend',      fullLabel: 'Frontend',           score: 93, count: 5 },
    { label: 'Backend',       fullLabel: 'Backend',            score: 88, count: 5 },
    { label: 'DevOps',        fullLabel: 'DevOps',             score: 82, count: 4 },
    { label: 'Enterprise…',   fullLabel: 'Enterprise Sales',   score: 90, count: 4 },
    { label: 'Growth',        fullLabel: 'Growth',             score: 85, count: 3 },
    { label: 'QA',            fullLabel: 'QA',                 score: 77, count: 4 },
    { label: 'Procurement',   fullLabel: 'Procurement',        score: 71, count: 3 },
    { label: 'Gen. Ledger',   fullLabel: 'General Ledger',     score: 75, count: 3 },
  ],
  job_title: [
    { label: 'Director',      fullLabel: 'Director',           score: 89, count: 8  },
    { label: 'Manager',       fullLabel: 'Manager',            score: 84, count: 12 },
    { label: 'Sr. Speciali…', fullLabel: 'Senior Specialist',  score: 80, count: 10 },
    { label: 'Analyst',       fullLabel: 'Analyst',            score: 76, count: 9  },
    { label: 'Specialist',    fullLabel: 'Specialist',         score: 73, count: 8  },
    { label: 'Sr. Analyst',   fullLabel: 'Senior Analyst',     score: 78, count: 7  },
    { label: 'Coordinator',   fullLabel: 'Coordinator',        score: 65, count: 6  },
    { label: 'Associate',     fullLabel: 'Associate',          score: 61, count: 5  },
  ],
};

const ratingDistData = [
  { name: 'Exceptional (5)', value: 18 },
  { name: 'Exceeds (4)', value: 34 },
  { name: 'Meets (3)', value: 29 },
  { name: 'Below (2)', value: 12 },
  { name: 'Unsatisfactory (1)', value: 7 },
];

interface KpiCardProps {
  title: string;
  value: string;
  delta: string;
  positive: boolean;
  icon: React.ElementType;
  color: string;
}

function KpiCard({ title, value, delta, positive, icon: Icon, color }: KpiCardProps) {
  return (
    <div className="card p-5 hover:shadow-md transition-shadow duration-200">
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-lg ${color} flex items-center justify-center`}>
          <Icon size={20} className="text-white" />
        </div>
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            positive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
          }`}
        >
          {positive ? '↑' : '↓'} {delta}
        </span>
      </div>
      <p className="text-2xl font-bold text-slate-900 mb-0.5">{value}</p>
      <p className="text-sm text-slate-500">{title}</p>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState({
    totalObjectives: 0,
    completedObjectives: 0,
    inProgressObjectives: 0,
    totalReviews: 0,
    avgRating: 0,
    totalFeedback: 0,
  });
  const [recentObjectives, setRecentObjectives] = useState<Array<{
    id: string; title: string; status: string; progress: number; timeline: string;
  }>>([]);

  // Performance chart state
  const [perfFilter, setPerfFilter] = useState({
    groupBy: 'department' as 'division' | 'department' | 'unit' | 'job_title',
    division: '',
    department: '',
    unit: '',
    job_title: '',
    quarter: '',
  });
  const [allObjectiveSets, setAllObjectiveSets] = useState<Array<{
    id: string; division: string; department: string; unit: string; job_title: string;
  }>>([]);
  const [allObjectives, setAllObjectives] = useState<Array<{
    set_id: string; progress: number; timeline: string; status: string;
  }>>([]);

  useEffect(() => {
    loadStats();
    loadPerfData();
  }, []);

  async function loadPerfData() {
    const [{ data: sets }, { data: objs }] = await Promise.all([
      supabase.from('objective_sets').select('id, division, department, unit, job_title'),
      supabase.from('objectives').select('set_id, progress, timeline, status'),
    ]);
    setAllObjectiveSets(sets || []);
    setAllObjectives(objs || []);
  }

  async function loadStats() {
    const [{ count: total }, { count: completed }, { count: inProgress }, { data: reviews }, { count: feedback }] =
      await Promise.all([
        supabase.from('objectives').select('*', { count: 'exact', head: true }),
        supabase.from('objectives').select('*', { count: 'exact', head: true }).eq('status', 'completed'),
        supabase.from('objectives').select('*', { count: 'exact', head: true }).eq('status', 'in_progress'),
        supabase.from('performance_reviews').select('rating'),
        supabase.from('feedback_records').select('*', { count: 'exact', head: true }),
      ]);

    const avgRating =
      reviews && reviews.length > 0
        ? reviews.reduce((sum: number, r: { rating: number }) => sum + r.rating, 0) / reviews.length
        : 0;

    setStats({
      totalObjectives: total || 0,
      completedObjectives: completed || 0,
      inProgressObjectives: inProgress || 0,
      totalReviews: reviews?.length || 0,
      avgRating,
      totalFeedback: feedback || 0,
    });

    const { data: recentObjs } = await supabase
      .from('objectives')
      .select('id, title, status, progress, timeline')
      .order('created_at', { ascending: false })
      .limit(5);

    setRecentObjectives(recentObjs || []);
  }

  const completionRate =
    stats.totalObjectives > 0
      ? Math.round((stats.completedObjectives / stats.totalObjectives) * 100)
      : 0;

  const statusColors: Record<string, string> = {
    draft: 'bg-slate-100 text-slate-600',
    in_progress: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    cancelled: 'bg-red-100 text-red-600',
  };

  // Cascading filter options
  const availableDivisions = [...new Set(allObjectiveSets.map(s => s.division).filter(Boolean))];
  const availableDepartments = [...new Set(
    allObjectiveSets
      .filter(s => !perfFilter.division || s.division === perfFilter.division)
      .map(s => s.department).filter(Boolean)
  )];
  const availableUnits = [...new Set(
    allObjectiveSets
      .filter(s => (!perfFilter.division || s.division === perfFilter.division) &&
                   (!perfFilter.department || s.department === perfFilter.department))
      .map(s => s.unit).filter(Boolean)
  )];
  const availableJobTitles = [...new Set(
    allObjectiveSets
      .filter(s => (!perfFilter.division || s.division === perfFilter.division) &&
                   (!perfFilter.department || s.department === perfFilter.department) &&
                   (!perfFilter.unit || s.unit === perfFilter.unit))
      .map(s => s.job_title).filter(Boolean)
  )];

  // Build chart data from live objectives
  const { perfChartData, isSample } = useMemo(() => {
    // Filter sets by selected dimensions
    const filteredSets = allObjectiveSets.filter(s =>
      (!perfFilter.division    || s.division    === perfFilter.division) &&
      (!perfFilter.department  || s.department  === perfFilter.department) &&
      (!perfFilter.unit        || s.unit        === perfFilter.unit) &&
      (!perfFilter.job_title   || s.job_title   === perfFilter.job_title)
    );
    const setIds = new Set(filteredSets.map(s => s.id));

    // Filter objectives by quarter/timeline
    const filteredObjs = allObjectives.filter(o =>
      setIds.has(o.set_id) &&
      (!perfFilter.quarter || o.timeline === perfFilter.quarter)
    );

    // Group by selected dimension
    const groupKey = perfFilter.groupBy;
    const groups: Record<string, number[]> = {};
    for (const obj of filteredObjs) {
      const set = allObjectiveSets.find(s => s.id === obj.set_id);
      if (!set) continue;
      const label = set[groupKey] || 'Unknown';
      if (!groups[label]) groups[label] = [];
      groups[label].push(obj.progress);
    }

    const computed = Object.entries(groups)
      .map(([label, values]) => ({
        label: label.length > 14 ? label.slice(0, 13) + '…' : label,
        fullLabel: label,
        score: Math.round(values.reduce((a, b) => a + b, 0) / values.length),
        count: values.length,
      }))
      .sort((a, b) => b.score - a.score);

    // Fall back to sample data if DB is empty
    if (computed.length === 0) {
      return { perfChartData: SAMPLE_DATA[perfFilter.groupBy] || [], isSample: true };
    }
    return { perfChartData: computed, isSample: false };
  }, [allObjectiveSets, allObjectives, perfFilter]);

  const GROUP_BY_OPTIONS = [
    { value: 'division',   label: 'Division' },
    { value: 'department', label: 'Department' },
    { value: 'unit',       label: 'Unit' },
    { value: 'job_title',  label: 'Job Title' },
  ] as const;

  const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2', 'Annual'];

  return (
    <Layout title="Dashboard" subtitle="Organization-wide performance at a glance">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
        <KpiCard
          title="Total Objectives"
          value={String(stats.totalObjectives || 82)}
          delta="14%"
          positive={true}
          icon={Target}
          color="bg-purple-600"
        />
        <KpiCard
          title="Completed"
          value={String(stats.completedObjectives || 44)}
          delta="22%"
          positive={true}
          icon={CheckCircle}
          color="bg-emerald-600"
        />
        <KpiCard
          title="In Progress"
          value={String(stats.inProgressObjectives || 30)}
          delta="5%"
          positive={true}
          icon={Clock}
          color="bg-amber-500"
        />
        <KpiCard
          title="Completion Rate"
          value={`${completionRate || 54}%`}
          delta="8%"
          positive={true}
          icon={TrendingUp}
          color="bg-teal-600"
        />
        <KpiCard
          title="Avg. Rating"
          value={stats.avgRating > 0 ? stats.avgRating.toFixed(1) : '4.1'}
          delta="0.3"
          positive={true}
          icon={Star}
          color="bg-orange-500"
        />
        <KpiCard
          title="Active Employees"
          value="248"
          delta="3%"
          positive={true}
          icon={Users}
          color="bg-slate-700"
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        {/* Objectives Trend */}
        <div className="card p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-4">Objectives Trend (6 Months)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trendData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorCompleted" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorInProgress" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
              />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '12px' }} />
              <Area type="monotone" dataKey="completed" stroke="#10b981" strokeWidth={2} fill="url(#colorCompleted)" name="Completed" />
              <Area type="monotone" dataKey="inProgress" stroke="#3b82f6" strokeWidth={2} fill="url(#colorInProgress)" name="In Progress" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Rating Distribution */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-4">Rating Distribution</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={ratingDistData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={75}
                paddingAngle={3}
                dataKey="value"
              >
                {ratingDistData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value, name) => [`${value}%`, name]}
                contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '11px' }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {ratingDistData.map((item, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                <span className="text-xs text-slate-600 dark:text-slate-300 flex-1 truncate">{item.name}</span>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-200">{item.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Department Performance — dynamic with filters */}
        <div className="card p-5 lg:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Performance Scores</h3>
              {isSample && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
                  Sample data
                </span>
              )}
            </div>

            {/* Filter row */}
            <div className="flex flex-wrap items-center gap-2">

              {/* Group By */}
              <div className="relative">
                <select
                  value={perfFilter.groupBy}
                  onChange={e => setPerfFilter(f => ({ ...f, groupBy: e.target.value as typeof f.groupBy, division: '', department: '', unit: '', job_title: '' }))}
                  className="text-xs pl-2 pr-6 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500 appearance-none cursor-pointer font-medium"
                >
                  {GROUP_BY_OPTIONS.map(o => <option key={o.value} value={o.value}>By {o.label}</option>)}
                </select>
                <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>

              {/* Division filter */}
              <div className="relative">
                <select
                  value={perfFilter.division}
                  onChange={e => setPerfFilter(f => ({ ...f, division: e.target.value, department: '', unit: '', job_title: '' }))}
                  className="text-xs pl-2 pr-6 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500 appearance-none cursor-pointer"
                >
                  <option value="">All Divisions</option>
                  {(availableDivisions.length ? availableDivisions : DIVISIONS).map(d => <option key={d} value={d}>{d}</option>)}
                </select>
                <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>

              {/* Department filter */}
              <div className="relative">
                <select
                  value={perfFilter.department}
                  onChange={e => setPerfFilter(f => ({ ...f, department: e.target.value, unit: '', job_title: '' }))}
                  className="text-xs pl-2 pr-6 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500 appearance-none cursor-pointer"
                >
                  <option value="">All Depts</option>
                  {availableDepartments.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
                <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>

              {/* Unit filter */}
              {availableUnits.length > 0 && (
                <div className="relative">
                  <select
                    value={perfFilter.unit}
                    onChange={e => setPerfFilter(f => ({ ...f, unit: e.target.value, job_title: '' }))}
                    className="text-xs pl-2 pr-6 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500 appearance-none cursor-pointer"
                  >
                    <option value="">All Units</option>
                    {availableUnits.map(u => <option key={u} value={u}>{u}</option>)}
                  </select>
                  <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
              )}

              {/* Job Title filter */}
              {availableJobTitles.length > 0 && (
                <div className="relative">
                  <select
                    value={perfFilter.job_title}
                    onChange={e => setPerfFilter(f => ({ ...f, job_title: e.target.value }))}
                    className="text-xs pl-2 pr-6 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500 appearance-none cursor-pointer"
                  >
                    <option value="">All Titles</option>
                    {(availableJobTitles.length ? availableJobTitles : JOB_TITLES).map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
              )}

              {/* Quarter filter */}
              <div className="relative">
                <select
                  value={perfFilter.quarter}
                  onChange={e => setPerfFilter(f => ({ ...f, quarter: e.target.value }))}
                  className="text-xs pl-2 pr-6 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500 appearance-none cursor-pointer"
                >
                  <option value="">All Quarters</option>
                  {QUARTERS.map(q => <option key={q} value={q}>{q}</option>)}
                </select>
                <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>

              {/* Reset */}
              {(perfFilter.division || perfFilter.department || perfFilter.unit || perfFilter.job_title || perfFilter.quarter) && (
                <button
                  onClick={() => setPerfFilter(f => ({ ...f, division: '', department: '', unit: '', job_title: '', quarter: '' }))}
                  className="text-xs px-2 py-1.5 rounded-lg text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20 font-medium transition-colors"
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          {perfChartData.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[200px] text-slate-400">
              <AlertCircle size={28} className="mb-2 text-slate-300" />
              <p className="text-xs">No data for selected filters. Generate objectives in Performance Planning.</p>
            </div>
          ) : (
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
                      fill={entry.score >= 75 ? '#10b981' : entry.score >= 50 ? '#7C3AED' : entry.score >= 25 ? '#f59e0b' : '#ef4444'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}

          {/* Legend */}
          <div className="flex items-center gap-4 mt-3 flex-wrap">
            {[
              { color: '#10b981', label: '≥75% On track' },
              { color: '#7C3AED', label: '50–74% In progress' },
              { color: '#f59e0b', label: '25–49% Behind' },
              { color: '#ef4444', label: '<25% At risk' },
            ].map(l => (
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
          {recentObjectives.length === 0 ? (
            <div className="text-center py-6">
              <AlertCircle size={24} className="text-slate-300 mx-auto mb-2" />
              <p className="text-xs text-slate-400">No objectives yet. Generate some in Performance Planning.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentObjectives.map((obj) => (
                <div key={obj.id} className="flex items-start gap-2.5">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{obj.title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-purple-500 rounded-full"
                          style={{ width: `${obj.progress}%` }}
                        />
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
          )}
        </div>
      </div>
    </Layout>
  );
}
