-- =============================================================================
-- SkillPilot — Supabase SQL Schema
-- Run this entire script in the Supabase SQL Editor to bootstrap the database.
-- =============================================================================


-- =============================================================================
-- 1. TABLE: user_profiles
--    Stores supplemental profile data tied to Supabase Auth users.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.user_profiles (
    id               UUID         PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name        TEXT,
    target_role      TEXT,
    extracted_skills TEXT[]       DEFAULT '{}',
    created_at       TIMESTAMPTZ  DEFAULT NOW()
);

COMMENT ON TABLE  public.user_profiles                  IS 'Extended profile data for each authenticated SkillPilot user.';
COMMENT ON COLUMN public.user_profiles.id               IS 'Matches the Supabase Auth user UUID.';
COMMENT ON COLUMN public.user_profiles.extracted_skills IS 'Skills parsed from the user''s most recent resume upload.';


-- =============================================================================
-- 2. TABLE: user_progress
--    XP, gamification badges, and course completion tracking per user.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.user_progress (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    total_xp          INTEGER     NOT NULL DEFAULT 0 CHECK (total_xp >= 0),
    completed_courses INTEGER     NOT NULL DEFAULT 0 CHECK (completed_courses >= 0),
    badges            TEXT[]      NOT NULL DEFAULT '{}',
    last_activity     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT user_progress_user_id_unique UNIQUE (user_id)
);

COMMENT ON TABLE  public.user_progress                   IS 'Tracks XP, badges, and course completion for gamification.';
COMMENT ON COLUMN public.user_progress.total_xp          IS 'Cumulative experience points earned by the user.';
COMMENT ON COLUMN public.user_progress.completed_courses IS 'Total number of courses the user has marked as complete.';
COMMENT ON COLUMN public.user_progress.badges            IS 'Array of badge identifiers unlocked by the user.';


-- =============================================================================
-- 3. TABLE: course_catalog
--    Central catalog of courses that can be recommended to users.
--    Pre-seeded with curated entries below.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.course_catalog (
    id             UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    skill          TEXT           NOT NULL,
    course_title   TEXT           NOT NULL,
    provider       TEXT           NOT NULL,
    url            TEXT           NOT NULL,
    rating         NUMERIC(3, 1)  CHECK (rating >= 0 AND rating <= 5),
    duration_hours INTEGER        CHECK (duration_hours > 0)
);

COMMENT ON TABLE  public.course_catalog               IS 'Curated course catalog used to drive the recommendation engine.';
COMMENT ON COLUMN public.course_catalog.skill         IS 'The skill this course teaches (e.g. "React", "Docker").';
COMMENT ON COLUMN public.course_catalog.rating        IS 'Average user rating out of 5.0.';
COMMENT ON COLUMN public.course_catalog.duration_hours IS 'Approximate course duration in hours.';

-- Index for fast skill lookups (used by the recommendation endpoint)
CREATE INDEX IF NOT EXISTS idx_course_catalog_skill ON public.course_catalog (skill);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- NOTE: The FastAPI backend acts as a trusted server and should be configured with
-- the Supabase 'service_role' key, which bypasses RLS to allow direct profile and
-- progress updates. These RLS policies protect direct queries from the client application
-- (e.g. Flutter app) when authenticated as a user using the public 'anon' key.
-- =============================================================================

-- ── user_profiles ─────────────────────────────────────────────────────────────

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Users may view only their own profile row
CREATE POLICY "user_profiles: select own row"
    ON public.user_profiles
    FOR SELECT
    USING (auth.uid() = id);

-- Users may insert their own profile row (sign-up flow)
CREATE POLICY "user_profiles: insert own row"
    ON public.user_profiles
    FOR INSERT
    WITH CHECK (auth.uid() = id);

-- Users may update only their own profile row
CREATE POLICY "user_profiles: update own row"
    ON public.user_profiles
    FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Users may delete their own profile row
CREATE POLICY "user_profiles: delete own row"
    ON public.user_profiles
    FOR DELETE
    USING (auth.uid() = id);


-- ── user_progress ─────────────────────────────────────────────────────────────

ALTER TABLE public.user_progress ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_progress: select own row"
    ON public.user_progress
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "user_progress: insert own row"
    ON public.user_progress
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "user_progress: update own row"
    ON public.user_progress
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "user_progress: delete own row"
    ON public.user_progress
    FOR DELETE
    USING (auth.uid() = user_id);


-- ── course_catalog ────────────────────────────────────────────────────────────
-- The course catalog is public read-only; only service-role can mutate it.

ALTER TABLE public.course_catalog ENABLE ROW LEVEL SECURITY;

CREATE POLICY "course_catalog: public read"
    ON public.course_catalog
    FOR SELECT
    USING (true);   -- any authenticated or anonymous user can read


-- =============================================================================
-- SEED DATA — course_catalog (10 curated courses)
-- =============================================================================

INSERT INTO public.course_catalog (skill, course_title, provider, url, rating, duration_hours) VALUES

    (
        'Python',
        '100 Days of Code: The Complete Python Pro Bootcamp',
        'Udemy',
        'https://www.udemy.com/course/100-days-of-code/',
        4.7,
        60
    ),

    (
        'JavaScript',
        'The Complete JavaScript Course 2024: From Zero to Expert!',
        'Udemy',
        'https://www.udemy.com/course/the-complete-javascript-course/',
        4.7,
        69
    ),

    (
        'React',
        'React - The Complete Guide (incl. Next.js, Redux)',
        'Udemy',
        'https://www.udemy.com/course/react-the-complete-guide-incl-redux/',
        4.6,
        68
    ),

    (
        'Flutter',
        'Flutter & Dart - The Complete Guide',
        'Udemy',
        'https://www.udemy.com/course/learn-flutter-dart-to-build-ios-android-apps/',
        4.6,
        42
    ),

    (
        'SQL',
        'The Complete SQL Bootcamp: Go from Zero to Hero',
        'Udemy',
        'https://www.udemy.com/course/the-complete-sql-bootcamp/',
        4.7,
        9
    ),

    (
        'Docker',
        'Docker & Kubernetes: The Practical Guide',
        'Udemy',
        'https://www.udemy.com/course/docker-kubernetes-the-practical-guide/',
        4.7,
        24
    ),

    (
        'AWS',
        'Ultimate AWS Certified Developer Associate 2024',
        'Udemy',
        'https://www.udemy.com/course/aws-certified-developer-associate-dva-c01/',
        4.7,
        32
    ),

    (
        'FastAPI',
        'FastAPI - The Complete Course (Beginner + Advanced)',
        'Udemy',
        'https://www.udemy.com/course/fastapi-the-complete-course-beginner-advanced/',
        4.6,
        19
    ),

    (
        'Machine Learning',
        'Machine Learning A-Z: AI, Python & R + ChatGPT Prize',
        'Udemy',
        'https://www.udemy.com/course/machinelearning/',
        4.5,
        44
    ),

    (
        'Git',
        'Git & GitHub Bootcamp',
        'Udemy',
        'https://www.udemy.com/course/git-and-github-bootcamp/',
        4.7,
        17
    )

ON CONFLICT DO NOTHING;


-- =============================================================================
-- 4. SCHEMA ENHANCEMENTS & CHAT HISTORY TABLE
-- =============================================================================

-- Add columns to user_profiles if they don't exist
ALTER TABLE public.user_profiles ADD COLUMN IF NOT EXISTS resume_filename TEXT;
ALTER TABLE public.user_profiles ADD COLUMN IF NOT EXISTS experience_summary TEXT;
ALTER TABLE public.user_profiles ADD COLUMN IF NOT EXISTS education_summary TEXT;
ALTER TABLE public.user_profiles ADD COLUMN IF NOT EXISTS resume_uploaded_at TIMESTAMPTZ;

COMMENT ON COLUMN public.user_profiles.resume_filename IS 'Filename of the uploaded resume.';
COMMENT ON COLUMN public.user_profiles.experience_summary IS 'Extracted professional experience summary.';
COMMENT ON COLUMN public.user_profiles.education_summary IS 'Extracted education background summary.';
COMMENT ON COLUMN public.user_profiles.resume_uploaded_at IS 'Timestamp when the resume was uploaded.';

-- Create Chat History Table
CREATE TABLE IF NOT EXISTS public.chat_history (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role        TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.chat_history            IS 'Stores career coaching conversation history turns per user.';
COMMENT ON COLUMN public.chat_history.id         IS 'Primary key uniquely identifying the message turn.';
COMMENT ON COLUMN public.chat_history.user_id    IS 'Reference to the auth.users entry.';
COMMENT ON COLUMN public.chat_history.role       IS 'Role of the message author: user or assistant.';
COMMENT ON COLUMN public.chat_history.content    IS 'Text content of the message.';

-- Create index for fast retrieval of latest conversation history per user
CREATE INDEX IF NOT EXISTS idx_chat_history_user_created ON public.chat_history (user_id, created_at DESC);

-- Enable RLS
ALTER TABLE public.chat_history ENABLE ROW LEVEL SECURITY;

-- Note: The FastAPI backend connects using the service_role key, which bypasses RLS checks.
-- Consequently, no backend policies are required for backend operations on this table.
-- The policies below secure direct authenticated client/frontend queries.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'chat_history' AND policyname = 'chat_history: select own rows'
    ) THEN
        CREATE POLICY "chat_history: select own rows" ON public.chat_history
            FOR SELECT USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'chat_history' AND policyname = 'chat_history: insert own rows'
    ) THEN
        CREATE POLICY "chat_history: insert own rows" ON public.chat_history
            FOR INSERT WITH CHECK (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'chat_history' AND policyname = 'chat_history: delete own rows'
    ) THEN
        CREATE POLICY "chat_history: delete own rows" ON public.chat_history
            FOR DELETE USING (auth.uid() = user_id);
    END IF;
END
$$;

