/*
  # AI-Powered PMS Database Schema

  ## New Tables

  ### objective_sets
  Groups of AI-generated objectives per planning session.
  - id: UUID primary key
  - division: organizational division
  - department: department name
  - unit: team/unit name
  - job_title: employee job title
  - num_objectives: how many objectives were requested
  - status: draft | active | archived
  - created_at: timestamp

  ### objectives
  Individual performance objectives linked to an objective set.
  - id: UUID primary key
  - set_id: FK to objective_sets
  - title: short objective title
  - description: detailed objective description
  - key_results: JSONB array of measurable key results
  - weight: percentage weight (1-100)
  - timeline: Q1/Q2/Q3/Q4/Annual
  - status: draft | in_progress | completed | cancelled
  - progress: 0-100 percent
  - created_at, updated_at timestamps

  ### performance_reviews
  Stores appraisal and review data.
  - id, employee_name, department, rating (1-5), comments, period, created_at

  ### feedback_records
  Coaching and feedback entries.
  - id, employee_name, department, feedback_type (coaching/recognition/development), content, created_at

  ## Security
  - RLS enabled on all tables
  - Anon and authenticated users can CRUD (public demo app with no user-specific data)
*/

-- Objective Sets table
CREATE TABLE IF NOT EXISTS objective_sets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  division text NOT NULL DEFAULT '',
  department text NOT NULL DEFAULT '',
  unit text NOT NULL DEFAULT '',
  job_title text NOT NULL DEFAULT '',
  num_objectives integer NOT NULL DEFAULT 3,
  status text NOT NULL DEFAULT 'draft',
  created_at timestamptz DEFAULT now()
);

ALTER TABLE objective_sets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anon select on objective_sets"
  ON objective_sets FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "Allow anon insert on objective_sets"
  ON objective_sets FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY "Allow anon update on objective_sets"
  ON objective_sets FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow anon delete on objective_sets"
  ON objective_sets FOR DELETE
  TO anon, authenticated
  USING (true);

-- Objectives table
CREATE TABLE IF NOT EXISTS objectives (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  set_id uuid REFERENCES objective_sets(id) ON DELETE CASCADE,
  title text NOT NULL DEFAULT '',
  description text NOT NULL DEFAULT '',
  key_results jsonb NOT NULL DEFAULT '[]',
  weight integer NOT NULL DEFAULT 20,
  timeline text NOT NULL DEFAULT 'Annual',
  status text NOT NULL DEFAULT 'draft',
  progress integer NOT NULL DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE objectives ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anon select on objectives"
  ON objectives FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "Allow anon insert on objectives"
  ON objectives FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY "Allow anon update on objectives"
  ON objectives FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow anon delete on objectives"
  ON objectives FOR DELETE
  TO anon, authenticated
  USING (true);

-- Performance Reviews table
CREATE TABLE IF NOT EXISTS performance_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_name text NOT NULL DEFAULT '',
  department text NOT NULL DEFAULT '',
  job_title text NOT NULL DEFAULT '',
  rating numeric(3,1) NOT NULL DEFAULT 3.0,
  comments text NOT NULL DEFAULT '',
  period text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'pending',
  created_at timestamptz DEFAULT now()
);

ALTER TABLE performance_reviews ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anon select on performance_reviews"
  ON performance_reviews FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "Allow anon insert on performance_reviews"
  ON performance_reviews FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY "Allow anon update on performance_reviews"
  ON performance_reviews FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow anon delete on performance_reviews"
  ON performance_reviews FOR DELETE
  TO anon, authenticated
  USING (true);

-- Feedback Records table
CREATE TABLE IF NOT EXISTS feedback_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_name text NOT NULL DEFAULT '',
  department text NOT NULL DEFAULT '',
  feedback_type text NOT NULL DEFAULT 'coaching',
  content text NOT NULL DEFAULT '',
  rating integer DEFAULT NULL,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE feedback_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anon select on feedback_records"
  ON feedback_records FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "Allow anon insert on feedback_records"
  ON feedback_records FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY "Allow anon update on feedback_records"
  ON feedback_records FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow anon delete on feedback_records"
  ON feedback_records FOR DELETE
  TO anon, authenticated
  USING (true);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_objectives_set_id ON objectives(set_id);
CREATE INDEX IF NOT EXISTS idx_objectives_status ON objectives(status);
CREATE INDEX IF NOT EXISTS idx_objective_sets_department ON objective_sets(department);
CREATE INDEX IF NOT EXISTS idx_performance_reviews_department ON performance_reviews(department);
CREATE INDEX IF NOT EXISTS idx_feedback_records_department ON feedback_records(department);
