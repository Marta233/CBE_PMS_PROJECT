export type PageKey = 'dashboard' | 'planning' | 'tracking' | 'appraisal' | 'feedback';

export interface ObjectiveSet {
  id: string;
  division: string;
  department: string;
  unit: string;
  job_title: string;
  num_objectives: number;
  status: string;
  created_at: string;
}

export interface KeyResult {
  text: string;
  target: string;
  measure: string;
}

export interface Objective {
  id: string;
  set_id: string;
  title: string;
  description: string;
  key_results: KeyResult[];
  weight: number;
  timeline: string;
  status: string;
  progress: number;
  created_at: string;
  updated_at: string;
}

export interface PerformanceReview {
  id: string;
  employee_name: string;
  department: string;
  job_title: string;
  rating: number;
  comments: string;
  period: string;
  status: string;
  created_at: string;
}

export interface FeedbackRecord {
  id: string;
  employee_name: string;
  department: string;
  feedback_type: string;
  content: string;
  rating: number | null;
  created_at: string;
}

export const DIVISIONS = [
  'Corporate',
  'Operations',
  'Commercial',
  'Technology',
  'Finance',
  'Human Resources',
  'Legal & Compliance',
  'Strategy & Planning',
];

export const DEPARTMENTS: Record<string, string[]> = {
  Corporate: ['Executive Office', 'Board Affairs', 'Corporate Communications'],
  Operations: ['Supply Chain', 'Logistics', 'Facilities', 'Quality Assurance'],
  Commercial: ['Sales', 'Marketing', 'Customer Success', 'Business Development'],
  Technology: ['Engineering', 'Product', 'Data & Analytics', 'IT Infrastructure', 'Cybersecurity'],
  Finance: ['Accounting', 'Treasury', 'Financial Planning & Analysis', 'Internal Audit'],
  'Human Resources': ['Talent Acquisition', 'L&D', 'Total Rewards', 'HR Business Partners'],
  'Legal & Compliance': ['Legal Affairs', 'Risk Management', 'Compliance', 'Privacy'],
  'Strategy & Planning': ['Corporate Strategy', 'M&A', 'PMO'],
};

export const UNITS: Record<string, string[]> = {
  Engineering: ['Frontend', 'Backend', 'DevOps', 'QA', 'Mobile'],
  Product: ['Product Management', 'UX/UI Design', 'Product Analytics'],
  Sales: ['Enterprise Sales', 'SMB Sales', 'Inside Sales', 'Pre-Sales'],
  Marketing: ['Brand', 'Growth', 'Content', 'Digital Marketing'],
  'Talent Acquisition': ['Campus Recruiting', 'Executive Search', 'Technical Recruiting'],
  Accounting: ['General Ledger', 'Accounts Payable', 'Accounts Receivable'],
  'Supply Chain': ['Procurement', 'Inventory', 'Vendor Management'],
};

export const JOB_TITLES = [
  'Chief Executive Officer',
  'Chief Financial Officer',
  'Chief Technology Officer',
  'Chief Operating Officer',
  'Vice President',
  'Senior Director',
  'Director',
  'Senior Manager',
  'Manager',
  'Senior Specialist',
  'Specialist',
  'Senior Analyst',
  'Analyst',
  'Associate',
  'Coordinator',
];

export const TIMELINES = ['Q1', 'Q2', 'Q3', 'Q4', 'H1', 'H2', 'Annual'];

export const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-600',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-600',
  active: 'bg-emerald-100 text-emerald-700',
  pending: 'bg-amber-100 text-amber-700',
  approved: 'bg-green-100 text-green-700',
};
