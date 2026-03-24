-- 001_create_tables.sql
-- Core application tables

CREATE TABLE users (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  google_id TEXT UNIQUE,
  plan TEXT DEFAULT 'free',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE student_profiles (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  level TEXT DEFAULT 'beginner',
  total_sessions INT DEFAULT 0,
  streak_days INT DEFAULT 0
);

CREATE TABLE sessions (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id INT REFERENCES users(id),
  agent_type TEXT CHECK (agent_type IN ('chat', 'voice')),
  started_at TIMESTAMPTZ DEFAULT now(),
  ended_at TIMESTAMPTZ,
  summary TEXT
);

CREATE TABLE tasks (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id INT REFERENCES users(id),
  title TEXT NOT NULL,
  due_date DATE,
  completed_at TIMESTAMPTZ,
  assigned_by_agent TEXT
);

CREATE TABLE grammar_notes (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id INT REFERENCES sessions(id),
  error_type TEXT,
  original_text TEXT,
  correction TEXT,
  timestamp TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE payments (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id INT REFERENCES users(id),
  stripe_subscription_id TEXT,
  status TEXT DEFAULT 'active',
  next_billing_date DATE
);
