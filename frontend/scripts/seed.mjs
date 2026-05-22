import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  'https://whovwsuqrjhmnfdrlvul.supabase.co',
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indob3Z3c3VxcmpobW5mZHJsdnVsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkwNTY1NDMsImV4cCI6MjA5NDYzMjU0M30.dBhVyYxs9LdOw0FuuIBVY9mnbRO4WQfGZq8DjQ8Q-Jk'
);

// ── Seed data definitions ──────────────────────────────────────────────────

const objectiveSetsData = [
  // Technology
  { division: 'Technology', department: 'Engineering', unit: 'Frontend',  job_title: 'Senior Manager',   num_objectives: 5, status: 'active' },
  { division: 'Technology', department: 'Engineering', unit: 'Backend',   job_title: 'Manager',          num_objectives: 5, status: 'active' },
  { division: 'Technology', department: 'Engineering', unit: 'DevOps',    job_title: 'Specialist',       num_objectives: 4, status: 'active' },
  { division: 'Technology', department: 'Engineering', unit: 'QA',        job_title: 'Analyst',          num_objectives: 4, status: 'active' },
  { division: 'Technology', department: 'Product',     unit: '',          job_title: 'Director',         num_objectives: 5, status: 'active' },
  { division: 'Technology', department: 'Cybersecurity',unit: '',         job_title: 'Senior Specialist',num_objectives: 4, status: 'active' },

  // Commercial
  { division: 'Commercial', department: 'Sales',           unit: 'Enterprise Sales', job_title: 'Senior Director', num_objectives: 5, status: 'active' },
  { division: 'Commercial', department: 'Sales',           unit: 'SMB Sales',        job_title: 'Manager',         num_objectives: 5, status: 'active' },
  { division: 'Commercial', department: 'Marketing',       unit: 'Growth',           job_title: 'Manager',         num_objectives: 4, status: 'active' },
  { division: 'Commercial', department: 'Marketing',       unit: 'Brand',            job_title: 'Specialist',      num_objectives: 4, status: 'active' },
  { division: 'Commercial', department: 'Customer Success',unit: '',                 job_title: 'Director',        num_objectives: 5, status: 'active' },

  // Finance
  { division: 'Finance', department: 'Accounting',                   unit: 'General Ledger',    job_title: 'Senior Manager',   num_objectives: 5, status: 'active' },
  { division: 'Finance', department: 'Accounting',                   unit: 'Accounts Payable',  job_title: 'Analyst',          num_objectives: 4, status: 'active' },
  { division: 'Finance', department: 'Financial Planning & Analysis',unit: '',                  job_title: 'Director',         num_objectives: 5, status: 'active' },
  { division: 'Finance', department: 'Internal Audit',               unit: '',                  job_title: 'Senior Specialist',num_objectives: 4, status: 'active' },

  // Human Resources
  { division: 'Human Resources', department: 'Talent Acquisition', unit: 'Technical Recruiting', job_title: 'Manager',        num_objectives: 4, status: 'active' },
  { division: 'Human Resources', department: 'L&D',                unit: '',                     job_title: 'Senior Specialist',num_objectives: 4, status: 'active' },
  { division: 'Human Resources', department: 'Total Rewards',      unit: '',                     job_title: 'Specialist',     num_objectives: 3, status: 'active' },

  // Operations
  { division: 'Operations', department: 'Supply Chain', unit: 'Procurement',     job_title: 'Senior Manager', num_objectives: 5, status: 'active' },
  { division: 'Operations', department: 'Supply Chain', unit: 'Inventory',       job_title: 'Analyst',        num_objectives: 4, status: 'active' },
  { division: 'Operations', department: 'Logistics',    unit: '',                job_title: 'Manager',        num_objectives: 4, status: 'active' },

  // Corporate
  { division: 'Corporate', department: 'Executive Office',        unit: '', job_title: 'Chief Executive Officer', num_objectives: 5, status: 'active' },
  { division: 'Corporate', department: 'Corporate Communications',unit: '', job_title: 'Director',               num_objectives: 4, status: 'active' },

  // Legal & Compliance
  { division: 'Legal & Compliance', department: 'Compliance',     unit: '', job_title: 'Senior Specialist', num_objectives: 4, status: 'active' },
  { division: 'Legal & Compliance', department: 'Risk Management',unit: '', job_title: 'Manager',           num_objectives: 4, status: 'active' },

  // Strategy & Planning
  { division: 'Strategy & Planning', department: 'Corporate Strategy', unit: '', job_title: 'Vice President', num_objectives: 5, status: 'active' },
  { division: 'Strategy & Planning', department: 'PMO',                unit: '', job_title: 'Director',       num_objectives: 4, status: 'active' },
];

// Objective templates per department
function makeObjectives(setId, division, department, unit, jobTitle, count) {
  const timelines = ['Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2', 'Annual'];
  const statuses  = ['completed', 'completed', 'in_progress', 'in_progress', 'in_progress', 'draft', 'cancelled'];

  const templates = [
    {
      title: `Strategic Alignment & Goal Setting`,
      description: `As ${jobTitle} in ${division} - ${department}${unit ? ` (${unit})` : ''}, align all team activities with organizational strategic priorities to maximize business impact across all quarters.`,
      key_results: [
        { text: 'Define and document strategic alignment plan', target: 'Q1 completion', measure: 'Planning documentation' },
        { text: 'Achieve departmental KPI targets', target: '100%', measure: 'Quarterly KPI reviews' },
        { text: 'Deliver key strategic initiatives on time', target: '90% on-time', measure: 'Project tracker' },
      ],
    },
    {
      title: `Operational Excellence & Process Improvement`,
      description: `Drive continuous improvement initiatives within ${department}${unit ? ` - ${unit}` : ''} to enhance efficiency, reduce waste, and deliver higher value outcomes.`,
      key_results: [
        { text: 'Identify and document improvement opportunities', target: '10 initiatives', measure: 'Process audit' },
        { text: 'Implement quick-win process improvements', target: '5 completed', measure: 'Implementation tracker' },
        { text: 'Achieve efficiency improvement', target: '15%', measure: 'Productivity metrics' },
      ],
    },
    {
      title: `Talent Development & Team Leadership`,
      description: `Invest in the professional growth of direct reports and build a high-performing team culture within ${unit || department}.`,
      key_results: [
        { text: 'Complete individual development plans', target: '100% of team', measure: 'HR system' },
        { text: 'Achieve team engagement score', target: '> 4.2/5', measure: 'Engagement survey' },
        { text: 'Reduce team attrition rate', target: '< 12%', measure: 'HR analytics' },
      ],
    },
    {
      title: `Customer & Stakeholder Experience`,
      description: `Deliver exceptional experiences for internal and external customers of ${department}, building trust and long-term relationships.`,
      key_results: [
        { text: 'Achieve NPS/CSAT score', target: '> 75 NPS', measure: 'Survey platform' },
        { text: 'Reduce response/resolution time', target: '< 24 hours', measure: 'Service metrics' },
        { text: 'Increase customer retention', target: '> 92%', measure: 'CRM analytics' },
      ],
    },
    {
      title: `Financial Performance & Budget Management`,
      description: `Manage the ${department} budget responsibly, maximizing ROI while ensuring alignment with ${division} division financial objectives.`,
      key_results: [
        { text: 'Deliver within approved budget', target: '< 5% variance', measure: 'Budget reports' },
        { text: 'Identify cost-saving opportunities', target: '$500K savings', measure: 'Finance tracker' },
        { text: 'Complete monthly budget reviews', target: '100% on time', measure: 'Finance calendar' },
      ],
    },
    {
      title: `Innovation & Digital Transformation`,
      description: `Champion digital innovation within ${department} by identifying technology opportunities and building a culture of experimentation.`,
      key_results: [
        { text: 'Launch digital improvement initiatives', target: '3 initiatives', measure: 'Innovation tracker' },
        { text: 'Achieve adoption rate for new tools', target: '> 80%', measure: 'Usage analytics' },
        { text: 'Deliver measurable digital ROI', target: '20% efficiency gain', measure: 'ROI assessment' },
      ],
    },
    {
      title: `Risk Management & Governance`,
      description: `Proactively identify, assess, and mitigate risks within ${department}'s scope, ensuring robust governance frameworks are in place.`,
      key_results: [
        { text: 'Complete departmental risk assessment', target: 'Q1 completion', measure: 'Risk register' },
        { text: 'Achieve compliance audit score', target: '> 95%', measure: 'Audit results' },
        { text: 'Implement risk mitigation controls', target: '100% of critical risks', measure: 'Controls dashboard' },
      ],
    },
    {
      title: `Data-Driven Decision Making`,
      description: `Establish data-driven practices across ${unit || department} to improve decision quality and reporting accuracy.`,
      key_results: [
        { text: 'Implement KPI dashboards', target: '3 dashboards live', measure: 'BI platform' },
        { text: 'Achieve data accuracy rate', target: '> 98%', measure: 'Data quality reports' },
        { text: 'Train team on data tools', target: '100% completion', measure: 'LMS records' },
      ],
    },
  ];

  const baseWeight = Math.floor(100 / count);
  const remainder = 100 - baseWeight * count;

  return templates.slice(0, count).map((t, i) => {
    const statusIdx = Math.floor(Math.random() * statuses.length);
    const status = statuses[statusIdx];
    const progress = status === 'completed' ? 100
      : status === 'in_progress' ? 20 + Math.floor(Math.random() * 70)
      : status === 'draft' ? 0
      : 0;
    return {
      set_id: setId,
      title: t.title,
      description: t.description,
      key_results: t.key_results,
      weight: baseWeight + (i === 0 ? remainder : 0),
      timeline: timelines[Math.floor(Math.random() * timelines.length)],
      status,
      progress,
    };
  });
}

const reviewsData = [
  { employee_name: 'Abebe Girma',      department: 'Engineering',                   job_title: 'Senior Manager',    rating: 5, period: 'Annual 2025', status: 'approved', comments: 'Exceptional leadership in delivering the core banking modernization project ahead of schedule. Demonstrated outstanding technical depth and team mentorship.' },
  { employee_name: 'Tigist Haile',     department: 'Sales',                         job_title: 'Director',          rating: 4, period: 'Annual 2025', status: 'approved', comments: 'Exceeded revenue targets by 18% and successfully expanded the enterprise client portfolio. Strong stakeholder management skills.' },
  { employee_name: 'Dawit Bekele',     department: 'Financial Planning & Analysis', job_title: 'Senior Specialist', rating: 4, period: 'Annual 2025', status: 'approved', comments: 'Delivered highly accurate financial forecasts with less than 2% variance. Improved the monthly close process by 3 days.' },
  { employee_name: 'Meron Tadesse',    department: 'Talent Acquisition',            job_title: 'Manager',           rating: 3, period: 'Annual 2025', status: 'approved', comments: 'Met hiring targets for most departments. Time-to-fill improved by 12%. Opportunity to strengthen technical recruiting pipeline.' },
  { employee_name: 'Yonas Alemu',      department: 'Product',                       job_title: 'Director',          rating: 5, period: 'Annual 2025', status: 'approved', comments: 'Launched 3 major product features that drove a 25% increase in digital banking adoption. Excellent cross-functional collaboration.' },
  { employee_name: 'Hiwot Tesfaye',    department: 'Compliance',                    job_title: 'Senior Specialist', rating: 4, period: 'Annual 2025', status: 'approved', comments: 'Maintained 100% regulatory compliance score. Led successful NBE audit with zero findings. Proactive risk identification.' },
  { employee_name: 'Biruk Mengistu',   department: 'Supply Chain',                  job_title: 'Senior Manager',    rating: 3, period: 'Annual 2025', status: 'pending',  comments: 'Managed procurement effectively within budget. Some delays in vendor onboarding impacted Q3 delivery timelines.' },
  { employee_name: 'Selam Worku',      department: 'Marketing',                     job_title: 'Manager',           rating: 4, period: 'Annual 2025', status: 'approved', comments: 'Drove a 40% increase in digital marketing ROI. Brand awareness campaigns exceeded reach targets by 22%.' },
  { employee_name: 'Natnael Girma',    department: 'Cybersecurity',                 job_title: 'Senior Specialist', rating: 5, period: 'Annual 2025', status: 'approved', comments: 'Zero security incidents in 2025. Implemented advanced threat detection system and trained 200+ staff on security protocols.' },
  { employee_name: 'Rahel Assefa',     department: 'Customer Success',              job_title: 'Director',          rating: 4, period: 'Annual 2025', status: 'approved', comments: 'Achieved NPS of 78, up from 65 the prior year. Reduced customer churn by 15% through proactive engagement programs.' },
  { employee_name: 'Fikadu Lemma',     department: 'Accounting',                    job_title: 'Senior Manager',    rating: 3, period: 'Q2 2026',    status: 'pending',  comments: 'Consistent and reliable financial reporting. Opportunity to accelerate automation of reconciliation processes.' },
  { employee_name: 'Azeb Hailu',       department: 'L&D',                           job_title: 'Senior Specialist', rating: 4, period: 'Q2 2026',    status: 'approved', comments: 'Designed and delivered 12 training programs reaching 350 employees. Learning completion rate of 94%.' },
  { employee_name: 'Tesfaye Kebede',   department: 'Corporate Strategy',            job_title: 'Vice President',    rating: 5, period: 'Annual 2025', status: 'approved', comments: 'Spearheaded the 5-year strategic plan with exceptional stakeholder alignment. Identified 3 high-value M&A opportunities.' },
  { employee_name: 'Lidya Bekele',     department: 'Risk Management',               job_title: 'Manager',           rating: 4, period: 'Annual 2025', status: 'approved', comments: 'Strengthened enterprise risk framework. Reduced operational risk incidents by 30% year-over-year.' },
  { employee_name: 'Samuel Teshome',   department: 'Logistics',                     job_title: 'Manager',           rating: 3, period: 'Annual 2025', status: 'approved', comments: 'Maintained delivery SLAs at 91%. Opportunity to improve last-mile efficiency and reduce logistics costs.' },
];

const feedbackData = [
  { employee_name: 'Abebe Girma',    department: 'Engineering',    feedback_type: 'recognition',  content: 'Outstanding work leading the core banking API migration. The team delivered zero-downtime deployment across all 500+ branches — a remarkable technical achievement that sets a new standard for the division.' },
  { employee_name: 'Tigist Haile',   department: 'Sales',          feedback_type: 'recognition',  content: 'Congratulations on closing the largest enterprise deal in CBE history this quarter. Your persistence, relationship-building, and deep product knowledge made the difference.' },
  { employee_name: 'Meron Tadesse',  department: 'Talent Acquisition', feedback_type: 'coaching', content: 'Let\'s work on building a stronger technical talent pipeline. I recommend partnering with university programs and tech communities to source candidates earlier in the hiring cycle. Happy to connect you with our university relations team.' },
  { employee_name: 'Dawit Bekele',   department: 'Financial Planning & Analysis', feedback_type: 'development', content: 'You have strong analytical skills. To grow into a senior leadership role, focus on developing executive communication — specifically translating complex financial models into concise board-level narratives. Consider enrolling in the executive communication program.' },
  { employee_name: 'Yonas Alemu',    department: 'Product',        feedback_type: 'recognition',  content: 'The mobile banking feature you shipped in Q2 has already been adopted by 1.2M customers. The user research process you championed is now being adopted as the standard across all product teams.' },
  { employee_name: 'Hiwot Tesfaye',  department: 'Compliance',     feedback_type: 'coaching',     content: 'Great job on the NBE audit. For your next growth area, I\'d encourage you to take a more proactive role in shaping compliance policy rather than just enforcing it. Your insights from the field are valuable at the policy level.' },
  { employee_name: 'Biruk Mengistu', department: 'Supply Chain',   feedback_type: 'coaching',     content: 'The Q3 vendor delays impacted downstream teams. Let\'s build a more robust vendor risk assessment process and establish earlier escalation triggers. I\'d like to review your vendor scorecard framework together next week.' },
  { employee_name: 'Selam Worku',    department: 'Marketing',      feedback_type: 'recognition',  content: 'The Ramadan campaign you led generated our highest-ever digital engagement. The creative strategy and channel mix were spot-on. This work has been shared as a best practice across the Commercial division.' },
  { employee_name: 'Natnael Girma',  department: 'Cybersecurity',  feedback_type: 'recognition',  content: 'Your threat intelligence work this year has been exceptional. Identifying and neutralizing the phishing campaign before it reached customers saved the bank significant reputational and financial risk.' },
  { employee_name: 'Rahel Assefa',   department: 'Customer Success', feedback_type: 'development', content: 'You\'ve built a great customer success function. To scale further, focus on building self-service capabilities and a customer health scoring model that can predict churn 90 days in advance. I can share some frameworks that have worked well in similar organizations.' },
  { employee_name: 'Fikadu Lemma',   department: 'Accounting',     feedback_type: 'development',  content: 'Your technical accounting skills are solid. The next step is to lead the automation initiative for the reconciliation process. I\'d recommend a 3-month pilot with the RPA team — this could save 40+ hours per month.' },
  { employee_name: 'Azeb Hailu',     department: 'L&D',            feedback_type: 'recognition',  content: 'The leadership development program you designed has received outstanding feedback from participants. 94% completion rate is exceptional. The program is being expanded to all regional offices next year.' },
  { employee_name: 'Tesfaye Kebede', department: 'Corporate Strategy', feedback_type: 'coaching', content: 'Your strategic thinking is excellent. To maximize your impact, work on bringing more diverse perspectives into the strategy process — particularly from frontline staff and regional branches who have ground-level insights.' },
  { employee_name: 'Lidya Bekele',   department: 'Risk Management', feedback_type: 'development', content: 'Strong risk management fundamentals. To advance to senior director level, develop deeper expertise in model risk and quantitative risk assessment. The FRM certification would be a valuable investment.' },
  { employee_name: 'Samuel Teshome', department: 'Logistics',      feedback_type: 'coaching',     content: 'Let\'s focus on the last-mile delivery efficiency gap. I\'d like you to lead a cross-functional task force with Operations and Technology to identify route optimization opportunities using our new data analytics platform.' },
  { employee_name: 'Abebe Girma',    department: 'Engineering',    feedback_type: 'development',  content: 'You\'re ready for a VP-level role. To prepare, focus on enterprise architecture thinking and building relationships with the C-suite. I\'d recommend shadowing the CTO in the next board technology committee meeting.' },
  { employee_name: 'Tigist Haile',   department: 'Sales',          feedback_type: 'coaching',     content: 'As you scale the team, invest more time in coaching your junior sales staff. Your deal-closing expertise is a competitive advantage — systematize it into a playbook the whole team can use.' },
];

// ── Main seed function ─────────────────────────────────────────────────────

async function seed() {
  console.log('🌱 Starting CBE PerformAI data seed...\n');

  // Clear existing data
  console.log('🗑️  Clearing existing data...');
  await supabase.from('feedback_records').delete().neq('id', '00000000-0000-0000-0000-000000000000');
  await supabase.from('performance_reviews').delete().neq('id', '00000000-0000-0000-0000-000000000000');
  await supabase.from('objectives').delete().neq('id', '00000000-0000-0000-0000-000000000000');
  await supabase.from('objective_sets').delete().neq('id', '00000000-0000-0000-0000-000000000000');
  console.log('   ✓ Cleared\n');

  // Insert objective sets
  console.log('📋 Inserting objective sets...');
  const { data: sets, error: setsErr } = await supabase
    .from('objective_sets')
    .insert(objectiveSetsData)
    .select();
  if (setsErr) { console.error('   ✗ Sets error:', setsErr.message); process.exit(1); }
  console.log(`   ✓ ${sets.length} objective sets inserted\n`);

  // Insert objectives for each set
  console.log('🎯 Inserting objectives...');
  let totalObjs = 0;
  for (const set of sets) {
    const objs = makeObjectives(set.id, set.division, set.department, set.unit, set.job_title, set.num_objectives);
    const { error } = await supabase.from('objectives').insert(objs);
    if (error) console.error(`   ✗ Objectives error for set ${set.id}:`, error.message);
    else totalObjs += objs.length;
  }
  console.log(`   ✓ ${totalObjs} objectives inserted\n`);

  // Insert performance reviews
  console.log('⭐ Inserting performance reviews...');
  const { data: reviews, error: revErr } = await supabase
    .from('performance_reviews')
    .insert(reviewsData)
    .select();
  if (revErr) { console.error('   ✗ Reviews error:', revErr.message); }
  else console.log(`   ✓ ${reviews.length} performance reviews inserted\n`);

  // Insert feedback records
  console.log('💬 Inserting feedback records...');
  const { data: feedback, error: fbErr } = await supabase
    .from('feedback_records')
    .insert(feedbackData)
    .select();
  if (fbErr) { console.error('   ✗ Feedback error:', fbErr.message); }
  else console.log(`   ✓ ${feedback.length} feedback records inserted\n`);

  console.log('✅ Seed complete! Refresh the app to see live data.');
}

seed().catch(console.error);
