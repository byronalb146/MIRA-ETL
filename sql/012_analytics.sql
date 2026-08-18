-- Audit/analytics trail for MIRA-API's natural-language query service.
-- Table shapes were driven by MIRA-API/src/mira_api/audit/outcomes.py (the
-- closed Outcome taxonomy) and nlq/validator.py -- this is the one place
-- that taxonomy is allowed to be duplicated as a CHECK constraint, since a
-- cross-repo foreign key isn't possible. Keep the two lists in sync by hand;
-- MIRA-API's own contract test (B.2) is what catches drift.
create schema if not exists analytics;

create table if not exists analytics.query_log (
    id bigserial primary key,
    created_at timestamptz not null default now(),
    subject_key text not null,
    question_text text not null,
    response_text text,
    model_response_raw jsonb,
    outcome text not null check (outcome in (
        'OK', 'OK_ZERO_ROWS', 'OK_DEGRADED_NARRATIVE',
        'OUT_OF_SCOPE', 'REJECTED_ENTITY_NOT_FOUND', 'REJECTED_ENTITY_AMBIGUOUS',
        'REJECTED_SQL_PARSE', 'REJECTED_SQL_NOT_SELECT', 'REJECTED_SQL_RELATION',
        'REJECTED_SQL_FUNCTION', 'REJECTED_SQL_COST',
        'FAILED_DB_TIMEOUT', 'FAILED_DB_ERROR', 'FAILED_LLM_ERROR',
        'THROTTLED_QUOTA', 'THROTTLED_BUDGET'
    )),
    attempt_count int not null default 1,
    total_latency_ms int,
    prompt_version text,
    app_version text,
    model_used text
);

-- Development environments may already have the earlier table shape.
alter table analytics.query_log
    add column if not exists response_text text;
alter table analytics.query_log
    add column if not exists model_response_raw jsonb;

drop table if exists analytics.query_feedback;
drop table if exists analytics.response_cache;

create index if not exists idx_query_log_created_at on analytics.query_log (created_at);
create index if not exists idx_query_log_outcome on analytics.query_log (outcome);
create index if not exists idx_query_log_subject on analytics.query_log (subject_key, created_at);

-- One row per SQL-generation attempt within a query_log turn (the model may
-- retry after the validator rejects a query). See validator.py's docstring:
-- the rejection rate here is described as "the fastest regression detector
-- the service has".
create table if not exists analytics.query_attempt (
    id bigserial primary key,
    query_log_id bigint not null references analytics.query_log(id),
    attempt_number int not null,
    generated_sql text,
    outcome text not null check (outcome in (
        'OK', 'OK_ZERO_ROWS', 'OK_DEGRADED_NARRATIVE',
        'OUT_OF_SCOPE', 'REJECTED_ENTITY_NOT_FOUND', 'REJECTED_ENTITY_AMBIGUOUS',
        'REJECTED_SQL_PARSE', 'REJECTED_SQL_NOT_SELECT', 'REJECTED_SQL_RELATION',
        'REJECTED_SQL_FUNCTION', 'REJECTED_SQL_COST',
        'FAILED_DB_TIMEOUT', 'FAILED_DB_ERROR', 'FAILED_LLM_ERROR',
        'THROTTLED_QUOTA', 'THROTTLED_BUDGET'
    )),
    rejection_rule text,
    rejection_detail text,
    row_count int,
    latency_ms int,
    created_at timestamptz not null default now(),
    unique (query_log_id, attempt_number)
);

create index if not exists idx_query_attempt_outcome on analytics.query_attempt (outcome);

-- Tracks both per-subject quota (subject_key = token or IP-prefix) and the
-- global budget circuit breaker (subject_key = '__global__'), so the two
-- limits described in MIRA-API's config.py share one table instead of two.
create table if not exists analytics.quota_counters (
    subject_key text not null,
    period_type text not null check (period_type in ('DAY', 'MONTH')),
    period_key text not null,
    query_count int not null default 0,
    spent_usd numeric not null default 0,
    updated_at timestamptz not null default now(),
    primary key (subject_key, period_type, period_key)
);

-- The backlog view: questions the service declined to answer at all (not a
-- failure -- the system deciding not to execute something it shouldn't).
-- This is the raw material v1's catalog-free design will eventually mine to
-- build a real query catalog (see MIRA-API README, "toda pregunta
-- contestable...").
create or replace view analytics.v_unanswered as
select *
from analytics.query_log
where outcome in ('OUT_OF_SCOPE', 'REJECTED_ENTITY_NOT_FOUND');

grant usage on schema analytics to mira_logger;
grant select, insert, update on all tables in schema analytics to mira_logger;
grant select on analytics.v_unanswered to mira_logger;
grant usage, select on all sequences in schema analytics to mira_logger;
alter default privileges in schema analytics grant select, insert, update on tables to mira_logger;
alter default privileges in schema analytics grant usage, select on sequences to mira_logger;
