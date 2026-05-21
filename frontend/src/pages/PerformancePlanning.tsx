import { useState } from 'react';
import { Sparkles, Plus, Trash2, ChevronDown, Save, CreditCard as Edit2, Check, X, Target, Clock, TrendingUp, RefreshCw } from 'lucide-react';
import Layout from '../components/Layout';
import { supabase } from '../lib/supabase';
import {
  DIVISIONS,
  DEPARTMENTS,
  UNITS,
  JOB_TITLES,
  TIMELINES,
  STATUS_COLORS,
  type Objective,
  type ObjectiveSet,
  type KeyResult,
} from '../types';

const NUM_OBJECTIVES_OPTIONS = [2, 3, 4, 5, 6, 7, 8];

function generateObjectives(
  division: string,
  department: string,
  unit: string,
  jobTitle: string,
  count: number
): Omit<Objective, 'id' | 'set_id' | 'created_at' | 'updated_at'>[] {
  const templates: Record<string, Array<Omit<Objective, 'id' | 'set_id' | 'created_at' | 'updated_at'>>> = {
    Engineering: [
      {
        title: 'Improve System Reliability & Uptime',
        description: `As ${jobTitle} in ${unit || department}, lead initiatives to achieve and maintain 99.9% system uptime through proactive monitoring, incident response improvements, and infrastructure hardening.`,
        key_results: [
          { text: 'Achieve 99.9% uptime SLA', target: '99.9%', measure: 'Monthly uptime reports' },
          { text: 'Reduce mean time to resolution (MTTR)', target: '< 30 minutes', measure: 'Incident tracking system' },
          { text: 'Implement automated health checks', target: '100% services covered', measure: 'Monitoring dashboard' },
        ],
        weight: 25, timeline: 'Annual', status: 'draft', progress: 0,
      },
      {
        title: 'Accelerate Software Delivery Velocity',
        description: `Drive ${department} team productivity by optimizing CI/CD pipelines, reducing deployment lead time, and increasing release frequency through agile best practices.`,
        key_results: [
          { text: 'Reduce deployment lead time', target: '< 2 hours', measure: 'CI/CD metrics' },
          { text: 'Increase deployment frequency', target: '4x per week', measure: 'Release calendar' },
          { text: 'Achieve zero-downtime deployments', target: '100%', measure: 'Deployment logs' },
        ],
        weight: 20, timeline: 'Annual', status: 'draft', progress: 0,
      },
      {
        title: 'Enhance Code Quality & Test Coverage',
        description: `Establish and enforce engineering excellence standards across the ${unit || department} team, focusing on test coverage, code reviews, and technical debt reduction.`,
        key_results: [
          { text: 'Increase unit test coverage', target: '> 85%', measure: 'Coverage reports' },
          { text: 'Reduce critical bug escape rate', target: '< 5%', measure: 'Bug tracking system' },
          { text: 'Complete code review SLA', target: '< 24 hours', measure: 'PR metrics' },
        ],
        weight: 20, timeline: 'Q2', status: 'draft', progress: 0,
      },
      {
        title: 'Drive Technical Innovation & R&D',
        description: `Lead exploration and adoption of emerging technologies relevant to ${division} division objectives, evaluating and piloting solutions that deliver measurable business value.`,
        key_results: [
          { text: 'Complete technology assessments', target: '3 evaluations', measure: 'R&D reports' },
          { text: 'Deliver proof-of-concept projects', target: '2 POCs', measure: 'Demo presentations' },
          { text: 'Reduce technical debt backlog', target: '30% reduction', measure: 'Tech debt tracker' },
        ],
        weight: 15, timeline: 'Annual', status: 'draft', progress: 0,
      },
      {
        title: 'Build & Retain High-Performing Engineering Team',
        description: `Develop talent within the ${unit || department} team through structured mentoring, skills development, and creating a culture of continuous learning and psychological safety.`,
        key_results: [
          { text: 'Achieve team satisfaction score', target: '> 4.2/5', measure: 'Engagement survey' },
          { text: 'Complete professional development plans', target: '100% of team', measure: 'HR system' },
          { text: 'Reduce voluntary attrition', target: '< 10%', measure: 'HR analytics' },
        ],
        weight: 20, timeline: 'Annual', status: 'draft', progress: 0,
      },
    ],
    Sales: [
      {
        title: 'Achieve Revenue Growth Targets',
        description: `As ${jobTitle} in ${division} - ${department}, drive consistent pipeline growth and close deals to meet or exceed quarterly and annual revenue targets.`,
        key_results: [
          { text: 'Achieve quarterly revenue quota', target: '105% of target', measure: 'CRM revenue reports' },
          { text: 'Grow annual recurring revenue (ARR)', target: '25% YoY', measure: 'Financial dashboard' },
          { text: 'Maintain pipeline coverage ratio', target: '3x quota', measure: 'CRM pipeline' },
        ],
        weight: 35, timeline: 'Annual', status: 'draft', progress: 0,
      },
      {
        title: 'Expand Key Account Portfolio',
        description: `Deepen relationships with strategic accounts in ${division} division by delivering value, identifying expansion opportunities, and securing multi-year commitments.`,
        key_results: [
          { text: 'Expand existing accounts', target: '20% net revenue retention', measure: 'Account health scores' },
          { text: 'Convert upsell opportunities', target: '15 expansions', measure: 'CRM opportunity tracker' },
          { text: 'Achieve customer health score', target: '> 8/10', measure: 'Customer success platform' },
        ],
        weight: 25, timeline: 'Annual', status: 'draft', progress: 0,
      },
      {
        title: 'Improve Sales Cycle Efficiency',
        description: `Optimize the sales process to reduce time-to-close and increase win rates by refining qualification, improving proposal quality, and strengthening objection handling.`,
        key_results: [
          { text: 'Reduce average sales cycle length', target: '< 45 days', measure: 'CRM stage analytics' },
          { text: 'Improve win rate', target: '> 35%', measure: 'CRM win/loss analysis' },
          { text: 'Increase average deal size', target: '15% increase', measure: 'Revenue analytics' },
        ],
        weight: 20, timeline: 'H1', status: 'draft', progress: 0,
      },
    ],
    Finance: [
      {
        title: 'Ensure Financial Reporting Accuracy & Compliance',
        description: `Maintain the highest standards of financial reporting accuracy and ensure full regulatory compliance across all ${department} functions within the ${division} division.`,
        key_results: [
          { text: 'Close books on schedule', target: '100% on time', measure: 'Close calendar' },
          { text: 'Achieve zero material audit findings', target: '0 findings', measure: 'External audit results' },
          { text: 'Maintain SOX compliance score', target: '100%', measure: 'Compliance tracker' },
        ],
        weight: 30, timeline: 'Annual', status: 'draft', progress: 0,
      },
      {
        title: 'Drive Cost Optimization & Operational Efficiency',
        description: `Identify and implement cost reduction initiatives across ${division} while maintaining or improving service quality and operational capabilities.`,
        key_results: [
          { text: 'Achieve cost savings target', target: '$2M savings', measure: 'Budget variance reports' },
          { text: 'Reduce operational costs', target: '8% reduction', measure: 'P&L analysis' },
          { text: 'Automate manual finance processes', target: '5 processes', measure: 'Process documentation' },
        ],
        weight: 25, timeline: 'Annual', status: 'draft', progress: 0,
      },
      {
        title: 'Enhance Financial Planning & Forecasting Accuracy',
        description: `Improve the quality and timeliness of financial forecasts to enable better decision-making for senior leadership across ${division}.`,
        key_results: [
          { text: 'Achieve forecast accuracy rate', target: '> 95%', measure: 'Variance analysis' },
          { text: 'Deliver rolling 12-month forecasts', target: 'Monthly cadence', measure: 'Planning calendar' },
          { text: 'Implement scenario planning models', target: '3 scenarios', measure: 'Planning platform' },
        ],
        weight: 20, timeline: 'Q1', status: 'draft', progress: 0,
      },
    ],
  };

  const defaultTemplates: Omit<Objective, 'id' | 'set_id' | 'created_at' | 'updated_at'>[] = [
    {
      title: `Strategic Goal Alignment for ${jobTitle}`,
      description: `As ${jobTitle} in ${division} - ${department}${unit ? ` (${unit})` : ''}, align all activities and team efforts with the organization's strategic priorities to maximize business impact.`,
      key_results: [
        { text: 'Define and document strategic alignment plan', target: 'Completed by Q1', measure: 'Planning documentation' },
        { text: 'Achieve departmental KPI targets', target: '100%', measure: 'Quarterly KPI reviews' },
        { text: 'Deliver key strategic initiatives on time', target: '90% on-time', measure: 'Project tracker' },
      ],
      weight: 25, timeline: 'Annual', status: 'draft', progress: 0,
    },
    {
      title: 'Operational Excellence & Process Improvement',
      description: `Drive continuous improvement initiatives within ${department}${unit ? ` - ${unit}` : ''} to enhance efficiency, reduce waste, and deliver higher value outcomes.`,
      key_results: [
        { text: 'Identify and document improvement opportunities', target: '10 initiatives', measure: 'Process audit' },
        { text: 'Implement quick-win process improvements', target: '5 completed', measure: 'Implementation tracker' },
        { text: 'Achieve efficiency improvement', target: '15%', measure: 'Productivity metrics' },
      ],
      weight: 20, timeline: 'Annual', status: 'draft', progress: 0,
    },
    {
      title: 'Stakeholder Engagement & Communication',
      description: `Build and maintain strong relationships with key stakeholders across ${division} division, ensuring clear and consistent communication of priorities, progress, and outcomes.`,
      key_results: [
        { text: 'Conduct stakeholder mapping and engagement plan', target: 'Q1 completion', measure: 'Stakeholder register' },
        { text: 'Achieve stakeholder satisfaction score', target: '> 4.0/5', measure: 'Stakeholder survey' },
        { text: 'Deliver executive updates on schedule', target: '100% on time', measure: 'Communication calendar' },
      ],
      weight: 15, timeline: 'Annual', status: 'draft', progress: 0,
    },
    {
      title: 'Talent Development & Team Leadership',
      description: `Invest in the professional growth of direct reports and build a high-performing team culture within ${unit || department} that attracts and retains top talent.`,
      key_results: [
        { text: 'Complete individual development plans', target: '100% of team', measure: 'HR system' },
        { text: 'Achieve team engagement score', target: '> 4.2/5', measure: 'Engagement survey' },
        { text: 'Reduce team attrition rate', target: '< 12%', measure: 'HR analytics' },
      ],
      weight: 20, timeline: 'Annual', status: 'draft', progress: 0,
    },
    {
      title: 'Innovation & Digital Transformation',
      description: `Champion digital innovation within ${department} by identifying technology opportunities, piloting new tools, and building a culture of experimentation and learning.`,
      key_results: [
        { text: 'Launch digital improvement initiatives', target: '3 initiatives', measure: 'Innovation tracker' },
        { text: 'Achieve adoption rate for new tools', target: '> 80%', measure: 'Usage analytics' },
        { text: 'Deliver measurable digital ROI', target: '20% efficiency gain', measure: 'ROI assessment' },
      ],
      weight: 20, timeline: 'H2', status: 'draft', progress: 0,
    },
    {
      title: 'Risk Management & Governance',
      description: `Proactively identify, assess, and mitigate risks within ${department}'s scope of responsibility, ensuring robust governance frameworks are in place and followed.`,
      key_results: [
        { text: 'Complete departmental risk assessment', target: 'Q1 completion', measure: 'Risk register' },
        { text: 'Achieve compliance audit score', target: '> 95%', measure: 'Audit results' },
        { text: 'Implement risk mitigation controls', target: '100% of critical risks', measure: 'Controls dashboard' },
      ],
      weight: 15, timeline: 'Annual', status: 'draft', progress: 0,
    },
    {
      title: 'Customer & Partner Experience',
      description: `Deliver exceptional experiences for internal and external customers of ${department}, building trust, loyalty, and long-term relationships that drive business growth.`,
      key_results: [
        { text: 'Achieve NPS/CSAT score', target: '> 75 NPS', measure: 'Survey platform' },
        { text: 'Reduce response/resolution time', target: '< 24 hours', measure: 'Service metrics' },
        { text: 'Increase customer retention', target: '> 92%', measure: 'CRM analytics' },
      ],
      weight: 20, timeline: 'Annual', status: 'draft', progress: 0,
    },
    {
      title: 'Financial Performance & Budget Management',
      description: `Manage the ${department} budget responsibly, maximizing return on investment while ensuring all activities align with the financial objectives of ${division} division.`,
      key_results: [
        { text: 'Deliver within approved budget', target: '< 5% variance', measure: 'Budget reports' },
        { text: 'Identify cost-saving opportunities', target: '$500K savings', measure: 'Finance tracker' },
        { text: 'Complete monthly budget reviews', target: '100% on time', measure: 'Finance calendar' },
      ],
      weight: 15, timeline: 'Annual', status: 'draft', progress: 0,
    },
  ];

  const dept = Object.keys(templates).find((k) => department.includes(k) || (unit && unit.includes(k)));
  const pool = dept ? [...(templates[dept] || []), ...defaultTemplates] : defaultTemplates;

  const selected = pool.slice(0, count);
  const totalWeight = 100;
  const baseWeight = Math.floor(totalWeight / count);
  const remainder = totalWeight - baseWeight * count;

  return selected.map((obj, i) => ({
    ...obj,
    weight: baseWeight + (i === 0 ? remainder : 0),
  }));
}

interface EditingState {
  objectiveId: string | null;
  field: string | null;
}

export default function PerformancePlanning() {
  const [division, setDivision] = useState('');
  const [department, setDepartment] = useState('');
  const [unit, setUnit] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [numObjectives, setNumObjectives] = useState(5);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);

  const [currentSet, setCurrentSet] = useState<ObjectiveSet | null>(null);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [editing, setEditing] = useState<EditingState>({ objectiveId: null, field: null });
  const [editValue, setEditValue] = useState('');

  const availableDepartments = division ? DEPARTMENTS[division] || [] : [];
  const availableUnits = department ? UNITS[department] || [] : [];

  const canGenerate = division && department && jobTitle && numObjectives > 0;

  async function handleGenerate() {
    if (!canGenerate) return;
    setGenerating(true);
    try {
      const { data: setData, error: setError } = await supabase
        .from('objective_sets')
        .insert({
          division,
          department,
          unit,
          job_title: jobTitle,
          num_objectives: numObjectives,
          status: 'draft',
        })
        .select()
        .single();

      if (setError) throw setError;
      setCurrentSet(setData);

      const generated = generateObjectives(division, department, unit, jobTitle, numObjectives);
      const { data: objData, error: objError } = await supabase
        .from('objectives')
        .insert(generated.map((o) => ({ ...o, set_id: setData.id })))
        .select();

      if (objError) throw objError;
      setObjectives(objData || []);
    } catch (err) {
      console.error('Generate error:', err);
    } finally {
      setGenerating(false);
    }
  }

  async function handleRegenerate() {
    if (!currentSet) return;
    setGenerating(true);
    try {
      await supabase.from('objectives').delete().eq('set_id', currentSet.id);
      const generated = generateObjectives(division, department, unit, jobTitle, numObjectives);
      const { data, error } = await supabase
        .from('objectives')
        .insert(generated.map((o) => ({ ...o, set_id: currentSet.id })))
        .select();
      if (error) throw error;
      setObjectives(data || []);
    } catch (err) {
      console.error('Regenerate error:', err);
    } finally {
      setGenerating(false);
    }
  }

  function startEdit(objectiveId: string, field: string, currentValue: string) {
    setEditing({ objectiveId, field });
    setEditValue(currentValue);
  }

  async function commitEdit(objective: Objective) {
    if (!editing.objectiveId || !editing.field) return;
    const updates: Partial<Objective> = { updated_at: new Date().toISOString() };
    if (editing.field === 'title') updates.title = editValue;
    if (editing.field === 'description') updates.description = editValue;
    if (editing.field === 'timeline') updates.timeline = editValue;
    if (editing.field === 'weight') updates.weight = parseInt(editValue) || objective.weight;
    if (editing.field === 'progress') updates.progress = Math.min(100, Math.max(0, parseInt(editValue) || 0));
    if (editing.field === 'status') updates.status = editValue;

    const { error } = await supabase.from('objectives').update(updates).eq('id', objective.id);
    if (!error) {
      setObjectives((prev) =>
        prev.map((o) => (o.id === objective.id ? { ...o, ...updates } : o))
      );
    }
    setEditing({ objectiveId: null, field: null });
  }

  async function updateKeyResult(objectiveId: string, index: number, field: keyof KeyResult, value: string) {
    const obj = objectives.find((o) => o.id === objectiveId);
    if (!obj) return;
    const updatedKRs = obj.key_results.map((kr, i) =>
      i === index ? { ...kr, [field]: value } : kr
    );
    const { error } = await supabase
      .from('objectives')
      .update({ key_results: updatedKRs, updated_at: new Date().toISOString() })
      .eq('id', objectiveId);
    if (!error) {
      setObjectives((prev) =>
        prev.map((o) => (o.id === objectiveId ? { ...o, key_results: updatedKRs } : o))
      );
    }
  }

  async function addKeyResult(objectiveId: string) {
    const obj = objectives.find((o) => o.id === objectiveId);
    if (!obj) return;
    const newKR: KeyResult = { text: 'New key result', target: 'Target', measure: 'Measurement method' };
    const updatedKRs = [...obj.key_results, newKR];
    const { error } = await supabase
      .from('objectives')
      .update({ key_results: updatedKRs })
      .eq('id', objectiveId);
    if (!error) {
      setObjectives((prev) =>
        prev.map((o) => (o.id === objectiveId ? { ...o, key_results: updatedKRs } : o))
      );
    }
  }

  async function removeKeyResult(objectiveId: string, index: number) {
    const obj = objectives.find((o) => o.id === objectiveId);
    if (!obj) return;
    const updatedKRs = obj.key_results.filter((_, i) => i !== index);
    const { error } = await supabase
      .from('objectives')
      .update({ key_results: updatedKRs })
      .eq('id', objectiveId);
    if (!error) {
      setObjectives((prev) =>
        prev.map((o) => (o.id === objectiveId ? { ...o, key_results: updatedKRs } : o))
      );
    }
  }

  async function removeObjective(objectiveId: string) {
    const { error } = await supabase.from('objectives').delete().eq('id', objectiveId);
    if (!error) {
      setObjectives((prev) => prev.filter((o) => o.id !== objectiveId));
    }
  }

  async function addObjective() {
    if (!currentSet) return;
    const newObj = {
      set_id: currentSet.id,
      title: 'New Objective',
      description: 'Describe this objective and its business impact.',
      key_results: [{ text: 'Key result 1', target: 'Target', measure: 'Measurement' }],
      weight: 10,
      timeline: 'Annual',
      status: 'draft',
      progress: 0,
    };
    const { data, error } = await supabase.from('objectives').insert(newObj).select().single();
    if (!error && data) {
      setObjectives((prev) => [...prev, data]);
    }
  }

  async function handleSave() {
    if (!currentSet) return;
    setSaving(true);
    const { error } = await supabase
      .from('objective_sets')
      .update({ status: 'active' })
      .eq('id', currentSet.id);
    if (!error) {
      setCurrentSet({ ...currentSet, status: 'active' });
    }
    setSaving(false);
  }

  const totalWeight = objectives.reduce((sum, o) => sum + o.weight, 0);

  return (
    <Layout
      title="Performance Planning"
      subtitle="Generate AI-powered objectives aligned to your role and department"
    >
      {/* Filter Panel */}
      <div className="card p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <Sparkles size={18} className="text-purple-600" />
          <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">Configure Objective Generation</h2>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-5">
          {/* Division */}
          <div>
            <label className="label">Division</label>
            <div className="relative">
              <select
                value={division}
                onChange={(e) => {
                  setDivision(e.target.value);
                  setDepartment('');
                  setUnit('');
                }}
                className="select-field pr-8"
              >
                <option value="">Select division</option>
                {DIVISIONS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Department */}
          <div>
            <label className="label">Department</label>
            <div className="relative">
              <select
                value={department}
                onChange={(e) => {
                  setDepartment(e.target.value);
                  setUnit('');
                }}
                disabled={!division}
                className="select-field pr-8 disabled:opacity-50"
              >
                <option value="">Select department</option>
                {availableDepartments.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Unit */}
          <div>
            <label className="label">Unit <span className="text-slate-400 normal-case font-normal">(optional)</span></label>
            <div className="relative">
              <select
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                disabled={!department}
                className="select-field pr-8 disabled:opacity-50"
              >
                <option value="">Select unit</option>
                {availableUnits.map((u) => (
                  <option key={u} value={u}>{u}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Job Title */}
          <div>
            <label className="label">Job Title</label>
            <div className="relative">
              <select
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                className="select-field pr-8"
              >
                <option value="">Select title</option>
                {JOB_TITLES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {/* Number of Objectives — input with stacked +/- on right */}
          <div>
            <label className="label">No. of Objectives</label>
            <div className="flex items-center border border-slate-200 dark:border-slate-600 rounded-lg overflow-hidden bg-white dark:bg-slate-700 h-[42px]">
              <input
                type="number"
                min={2}
                max={8}
                value={numObjectives}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  if (!isNaN(v)) setNumObjectives(Math.min(8, Math.max(2, v)));
                }}
                className="flex-1 min-w-0 px-3 text-sm font-semibold text-slate-800 dark:text-slate-100 bg-transparent focus:outline-none"
              />
              {/* Stacked +/- buttons */}
              <div className="flex flex-col h-full border-l border-slate-200 dark:border-slate-600 flex-shrink-0">
                <button
                  type="button"
                  onClick={() => setNumObjectives((n) => Math.min(8, n + 1))}
                  disabled={numObjectives >= 8}
                  className="flex-1 w-8 flex items-center justify-center text-slate-500 dark:text-slate-300 hover:bg-purple-50 dark:hover:bg-purple-900/30 hover:text-purple-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors border-b border-slate-200 dark:border-slate-600 text-xs font-bold leading-none"
                  aria-label="Increase"
                >
                  +
                </button>
                <button
                  type="button"
                  onClick={() => setNumObjectives((n) => Math.max(2, n - 1))}
                  disabled={numObjectives <= 2}
                  className="flex-1 w-8 flex items-center justify-center text-slate-500 dark:text-slate-300 hover:bg-purple-50 dark:hover:bg-purple-900/30 hover:text-purple-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-xs font-bold leading-none"
                  aria-label="Decrease"
                >
                  −
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerate}
            disabled={!canGenerate || generating}
            className="btn-primary"
          >
            {generating ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Generating...
              </>
            ) : (
              <>
                <Sparkles size={16} />
                Generate Objectives
              </>
            )}
          </button>

          {!canGenerate && (
            <p className="text-sm text-slate-400">Fill in Division, Department, and Job Title to generate</p>
          )}
        </div>
      </div>

      {/* Generated Objectives */}
      {objectives.length > 0 && (
        <div className="animate-slide-up">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100">
                Generated Objectives
              </h2>
              <span className="badge bg-purple-100 text-purple-700">
                {objectives.length} objectives
              </span>
              <span
                className={`badge ${
                  Math.abs(totalWeight - 100) > 1 ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'
                }`}
              >
                Weight: {totalWeight}%
              </span>
              {currentSet && (
                <span className={`badge ${STATUS_COLORS[currentSet.status]}`}>
                  {currentSet.status}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={handleRegenerate} disabled={generating} className="btn-secondary text-xs">
                <RefreshCw size={14} className={generating ? 'animate-spin' : ''} />
                Regenerate
              </button>
              <button onClick={addObjective} className="btn-secondary text-xs">
                <Plus size={14} />
                Add Objective
              </button>
              <button onClick={handleSave} disabled={saving} className="btn-primary text-xs">
                <Save size={14} />
                {saving ? 'Saving...' : 'Save & Activate'}
              </button>
            </div>
          </div>

          {/* Objectives List */}
          <div className="space-y-4">
            {objectives.map((obj, idx) => (
              <ObjectiveCard
                key={obj.id}
                objective={obj}
                index={idx}
                editing={editing}
                editValue={editValue}
                setEditValue={setEditValue}
                onStartEdit={startEdit}
                onCommitEdit={commitEdit}
                onCancelEdit={() => setEditing({ objectiveId: null, field: null })}
                onUpdateKeyResult={updateKeyResult}
                onAddKeyResult={addKeyResult}
                onRemoveKeyResult={removeKeyResult}
                onRemoveObjective={removeObjective}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {objectives.length === 0 && !generating && (
        <div className="card p-12 text-center">
          <div className="w-16 h-16 bg-purple-50 dark:bg-purple-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <Target size={28} className="text-purple-500" />
          </div>
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-2">No Objectives Generated Yet</h3>
          <p className="text-sm text-slate-500 max-w-sm mx-auto">
            Select your division, department, job title, and number of objectives, then click "Generate Objectives" to create AI-powered performance goals.
          </p>
        </div>
      )}
    </Layout>
  );
}

interface ObjectiveCardProps {
  objective: Objective;
  index: number;
  editing: EditingState;
  editValue: string;
  setEditValue: (v: string) => void;
  onStartEdit: (id: string, field: string, value: string) => void;
  onCommitEdit: (obj: Objective) => void;
  onCancelEdit: () => void;
  onUpdateKeyResult: (id: string, index: number, field: keyof KeyResult, value: string) => void;
  onAddKeyResult: (id: string) => void;
  onRemoveKeyResult: (id: string, index: number) => void;
  onRemoveObjective: (id: string) => void;
}

function ObjectiveCard({
  objective,
  index,
  editing,
  editValue,
  setEditValue,
  onStartEdit,
  onCommitEdit,
  onCancelEdit,
  onUpdateKeyResult,
  onAddKeyResult,
  onRemoveKeyResult,
  onRemoveObjective,
}: ObjectiveCardProps) {
  const isEditingThis = editing.objectiveId === objective.id;

  function InlineEdit({
    field,
    value,
    multiline = false,
    inputType = 'text',
    selectOptions,
    className = '',
  }: {
    field: string;
    value: string | number;
    multiline?: boolean;
    inputType?: string;
    selectOptions?: string[];
    className?: string;
  }) {
    const isActive = isEditingThis && editing.field === field;
    if (isActive) {
      if (selectOptions) {
        return (
          <span className="inline-flex items-center gap-1">
            <select
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="border border-purple-400 rounded px-2 py-0.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 dark:bg-slate-700 dark:text-slate-100"
              autoFocus
            >
              {selectOptions.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <button onClick={() => onCommitEdit(objective)} className="text-green-600 hover:text-green-700"><Check size={14} /></button>
            <button onClick={onCancelEdit} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
          </span>
        );
      }
      if (multiline) {
        return (
          <span className="block">
            <textarea
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="w-full border border-purple-400 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none dark:bg-slate-700 dark:text-slate-100"
              rows={3}
              autoFocus
            />
            <span className="inline-flex gap-1 mt-1">
              <button onClick={() => onCommitEdit(objective)} className="text-green-600 hover:text-green-700"><Check size={14} /></button>
              <button onClick={onCancelEdit} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
            </span>
          </span>
        );
      }
      return (
        <span className="inline-flex items-center gap-1">
          <input
            type={inputType}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onCommitEdit(objective);
              if (e.key === 'Escape') onCancelEdit();
            }}
            className={`border border-purple-400 rounded px-2 py-0.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 dark:bg-slate-700 dark:text-slate-100 ${className}`}
            autoFocus
          />
          <button onClick={() => onCommitEdit(objective)} className="text-green-600 hover:text-green-700"><Check size={14} /></button>
          <button onClick={onCancelEdit} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
        </span>
      );
    }
    return (
      <span
        className="cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700 rounded px-1 -mx-1 group inline-flex items-center gap-1 transition-colors"
        onClick={() => onStartEdit(objective.id, field, String(value))}
      >
        <span>{String(value)}</span>
        <Edit2 size={11} className="text-slate-300 group-hover:text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" />
      </span>
    );
  }

  return (
    <div className="card overflow-hidden">
      {/* Card header */}
      <div className="flex items-start justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/40">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-purple-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5">
            {index + 1}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-900 dark:text-white text-sm">
              <InlineEdit field="title" value={objective.title} className="w-72" />
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2 ml-3 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            <Clock size={13} className="text-slate-400" />
            <span className="text-xs text-slate-600 dark:text-slate-300">
              <InlineEdit field="timeline" value={objective.timeline} selectOptions={TIMELINES} />
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <TrendingUp size={13} className="text-slate-400" />
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
              <InlineEdit field="weight" value={objective.weight} inputType="number" className="w-16" />%
            </span>
          </div>
          <span className={`badge ${STATUS_COLORS[objective.status]}`}>
            <InlineEdit
              field="status"
              value={objective.status}
              selectOptions={['draft', 'in_progress', 'completed', 'cancelled']}
            />
          </span>
          <button
            onClick={() => onRemoveObjective(objective.id)}
            className="p-1 text-slate-300 hover:text-red-500 transition-colors rounded"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <div className="px-5 py-4">
        {/* Description */}
        <div className="mb-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Description</p>
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            <InlineEdit field="description" value={objective.description} multiline />
          </p>
        </div>

        {/* Progress */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Progress</p>
            <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
              <InlineEdit field="progress" value={objective.progress} inputType="number" className="w-16" />%
            </span>
          </div>
          <div className="w-full h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-500 rounded-full transition-all duration-500"
              style={{ width: `${objective.progress}%` }}
            />
          </div>
        </div>

        {/* Key Results */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Key Results</p>
            <button
              onClick={() => onAddKeyResult(objective.id)}
              className="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1 font-medium"
            >
              <Plus size={12} /> Add KR
            </button>
          </div>
          <div className="space-y-2">
            {objective.key_results.map((kr, krIdx) => (
              <div
                key={krIdx}
                className="flex items-start gap-2 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg group"
              >
                <div className="w-4 h-4 rounded-full border-2 border-purple-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0 grid grid-cols-3 gap-2">
                  <div className="col-span-3 md:col-span-1">
                    <input
                      type="text"
                      value={kr.text}
                      onChange={(e) => onUpdateKeyResult(objective.id, krIdx, 'text', e.target.value)}
                      className="w-full text-sm text-slate-700 dark:text-slate-200 bg-transparent border-0 focus:outline-none focus:bg-white dark:focus:bg-slate-700 focus:border focus:border-purple-300 rounded px-1 -mx-1"
                      placeholder="Key result..."
                    />
                  </div>
                  <div>
                    <input
                      type="text"
                      value={kr.target}
                      onChange={(e) => onUpdateKeyResult(objective.id, krIdx, 'target', e.target.value)}
                      className="w-full text-xs text-purple-700 dark:text-purple-300 font-medium bg-transparent border-0 focus:outline-none focus:bg-white dark:focus:bg-slate-700 focus:border focus:border-purple-300 rounded px-1 -mx-1"
                      placeholder="Target..."
                    />
                  </div>
                  <div>
                    <input
                      type="text"
                      value={kr.measure}
                      onChange={(e) => onUpdateKeyResult(objective.id, krIdx, 'measure', e.target.value)}
                      className="w-full text-xs text-slate-500 dark:text-slate-400 bg-transparent border-0 focus:outline-none focus:bg-white dark:focus:bg-slate-700 focus:border focus:border-purple-300 rounded px-1 -mx-1"
                      placeholder="Measurement..."
                    />
                  </div>
                </div>
                <button
                  onClick={() => onRemoveKeyResult(objective.id, krIdx)}
                  className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-500 transition-all flex-shrink-0"
                >
                  <X size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
