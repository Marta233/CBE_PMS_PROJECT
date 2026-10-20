export type PageKey = 'dashboard' | 'ingestion' | 'planning' | 'tracking' | 'appraisal' | 'feedback';

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
  'RBB',
  'Digital Banking',
];

export const DEPARTMENTS: Record<string, string[]> = {
  // ── RBB Division ──────────────────────────────────────────────────────────
  RBB: [
    'Corporate',
    'Operations',
    'Commercial',
    'Technology',
    'Finance',
    'Human Resources',
    'Legal & Compliance',
    'Strategy & Planning',
  ],

  // ── Digital Banking Division (from CBE Digital Banking JD) ────────────────
  'Digital Banking': [
    'Internal Control',
    'Digital Banking Reconciliation and Dispute Management',
    'Merchant and Agent Management',
    'Mobile and Internet Banking',
    'Mobile Money',
    'Card Banking',
  ],
};

export const UNITS: Record<string, string[]> = {
  // ── RBB units ─────────────────────────────────────────────────────────────
  Corporate: ['Corporate'],
  Operations: ['Operations'],
  Commercial: ['Commercial'],
  Technology: ['Technology'],
  Finance: ['Finance'],
  'Human Resources': ['Human Resources'],
  'Legal & Compliance': ['Legal & Compliance'],
  'Strategy & Planning': ['Strategy & Planning'],

  // ── Digital Banking Units ─────────────────────────────────────────────────

  // Department 1: Internal Control
  'Internal Control': ['Internal Control'],

  // Department 2: Digital Banking Reconciliation and Dispute Management
  'Digital Banking Reconciliation and Dispute Management': [
    'Digital Banking Reconciliation and Dispute Management',
    'Merchant and Agent Reconciliation',
    'Mobile and Internet Banking Reconciliation',
    'International Card Transaction Reconciliation',
    'Domestic Card Transaction Reconciliation',
    'Mobile Money Reconciliation',
  ],

  // Department 3: Merchant and Agent Management
  'Merchant and Agent Management': [
    'Merchant and Agent Management',
    'Merchant Management',
    'Agent Management',
    'Digital Partners Relationship',
  ],

  // Department 4: Mobile and Internet Banking
  'Mobile and Internet Banking': [
    'Mobile and Internet Banking',
    'Mobile Banking Business',
    'Internet Banking Business',
  ],

  // Department 5: Mobile Money
  'Mobile Money': [
    'Mobile Money',
    'Mobile Money Business',
  ],

  // Department 6: Card Banking
  'Card Banking': [
    'Card Banking',
    'ATM Operations Support',
    'Card Banking Business',
    'Card Production and Distribution',
    'Card Issuance Solution Management',
  ],
};

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
