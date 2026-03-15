-- Migration: Rubric Category → Judge Integration
-- Run manually against the database

-- 1. Add category to judges (existing judges get default 'accuracy')
ALTER TABLE judges ADD COLUMN IF NOT EXISTS category VARCHAR DEFAULT 'accuracy' NOT NULL;

-- 2. Correct the 2 common judges
UPDATE judges SET category = 'common' WHERE model_name = 'litellm_proxy/gemini-2.5-flash-lite';
UPDATE judges SET category = 'common' WHERE model_name = 'azure/gpt-5-nano-2025-08-07';

-- 3. Add rubric_id to qa_jobs (nullable, existing rows get NULL)
ALTER TABLE qa_jobs ADD COLUMN IF NOT EXISTS rubric_id INTEGER REFERENCES target_rubrics(id) ON DELETE SET NULL;

-- 4. Replace old unique constraint with two partial indexes
DROP INDEX IF EXISTS uix_snapshot_question_judge;
CREATE UNIQUE INDEX IF NOT EXISTS uix_accuracy_jobs ON qa_jobs (snapshot_id, question_id, judge_id) WHERE rubric_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uix_rubric_jobs ON qa_jobs (snapshot_id, question_id, judge_id, rubric_id) WHERE rubric_id IS NOT NULL;

-- 5. Create rubric_answer_scores table
CREATE TABLE IF NOT EXISTS rubric_answer_scores (
    id SERIAL PRIMARY KEY,
    answer_id INTEGER NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
    rubric_id INTEGER NOT NULL REFERENCES target_rubrics(id) ON DELETE CASCADE,
    judge_id INTEGER NOT NULL REFERENCES judges(id) ON DELETE CASCADE,
    option_chosen VARCHAR NOT NULL,
    explanation TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    CONSTRAINT uix_answer_rubric_judge UNIQUE (answer_id, rubric_id, judge_id)
);
