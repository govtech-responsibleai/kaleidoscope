import type {
  TargetResponse,
  TargetStats,
  Snapshot,
  SnapshotStats,
  TargetRubricResponse,
  PremadeRubricTemplate,
  JudgeConfig,
  JudgeModelOption,
  PersonaResponse,
  QuestionResponse,
  QuestionListResponse,
  Answer,
  AnswerListResponse,
  QAJob,
  JobResponse,
  ScoringStatusResponse,
  ScoringRubricsResponse,
  ScoringResultsResponse,
  SnapshotMetricsResponse,
  ProviderSetupResponse,
} from "@/lib/types";
import { Status, JobStatus, JobType, QAJobStageEnum } from "@/lib/types";

const NOW = "2026-04-28T12:00:00Z";

export const TARGET_ID = 1;
export const SNAPSHOT_ID = 10;
export const RUBRIC_ID = 100;
export const JUDGE_ID = 200;

export const target: TargetResponse = {
  id: TARGET_ID,
  name: "Test Target",
  agency: "Test Agency",
  purpose: "Testing purposes",
  target_users: "QA engineers",
  api_endpoint: "https://example.com/api",
  endpoint_type: "openai",
  created_at: NOW,
  updated_at: NOW,
};

export const targetStats: TargetStats = {
  personas: { approved: 2 },
  questions: { approved: 5 },
  total_cost: 0.05,
};

export const snapshot: Snapshot = {
  id: SNAPSHOT_ID,
  target_id: TARGET_ID,
  name: "Snapshot 1",
  answer_count: 5,
  selected_for_annotation_count: 5,
  annotated_count: 5,
  created_at: NOW,
  updated_at: NOW,
};

export const snapshotStats: SnapshotStats = {
  total_answers: 5,
  selected_count: 5,
  annotated_count: 5,
};

export const accuracyRubric: TargetRubricResponse = {
  id: RUBRIC_ID,
  target_id: TARGET_ID,
  name: "Accuracy",
  criteria: "Is the answer factually correct?",
  options: [
    { option: "correct", description: "Fully correct" },
    { option: "incorrect", description: "Contains errors" },
  ],
  best_option: "correct",
  position: 0,
  judge_prompt: null,
  group: "fixed",
  scoring_mode: "response_level",
  created_at: NOW,
  updated_at: NOW,
};

export const premadeTemplate: PremadeRubricTemplate = {
  name: "Completeness",
  criteria: "Does the answer cover all aspects of the question?",
  options: [
    { option: "complete", description: "Fully covers all aspects" },
    { option: "partial", description: "Covers some aspects" },
    { option: "incomplete", description: "Missing key aspects" },
  ],
  best_option: "complete",
  recommended_model_provider: "openai",
  recommended_model_name: "gpt-4o",
  group: "preset",
};

export const judge: JudgeConfig = {
  id: JUDGE_ID,
  target_id: TARGET_ID,
  rubric_id: RUBRIC_ID,
  name: "GPT-4o Judge",
  model_name: "openai/gpt-4o",
  model_label: "GPT-4o",
  temperature: 0.7,
  is_baseline: true,
  is_editable: false,
  params: {},
  created_at: NOW,
  updated_at: NOW,
};

export const judgeModelOption: JudgeModelOption = {
  value: "openai/gpt-4o",
  label: "GPT-4o",
  provider_key: "openai",
  provider_name: "OpenAI",
  logo_path: "/logos/openai.svg",
};

export const persona: PersonaResponse = {
  id: 1,
  target_id: TARGET_ID,
  title: "Power User",
  info: "A user who uses the product extensively",
  style: "direct",
  use_case: "daily workflows",
  source: "generated",
  job_id: null,
  status: Status.APPROVED,
  created_at: NOW,
  updated_at: NOW,
};

export const question: QuestionResponse = {
  id: 1,
  target_id: TARGET_ID,
  text: "What is the refund policy?",
  type: null,
  scope: null,
  persona_id: null,
  job_id: null,
  status: Status.APPROVED,
  created_at: NOW,
  updated_at: NOW,
};

export const questionListResponse: QuestionListResponse = {
  items: [question],
  total: 1,
  skip: 0,
  limit: 50,
};

export const answer: Answer = {
  id: 1,
  snapshot_id: SNAPSHOT_ID,
  question_id: question.id,
  answer_content: "Our refund policy allows returns within 30 days.",
  is_selected_for_annotation: true,
  has_annotation: true,
  created_at: NOW,
};

export const answerListResponse: AnswerListResponse = {
  answers: [answer],
  total: 1,
};

export const completedQAJob: QAJob = {
  id: 1,
  snapshot_id: SNAPSHOT_ID,
  question_id: question.id,
  answer_id: answer.id,
  judge_id: JUDGE_ID,
  rubric_specs: [{ rubric_id: RUBRIC_ID, judge_id: JUDGE_ID }],
  type: "qa",
  status: JobStatus.COMPLETED,
  stage: QAJobStageEnum.COMPLETED,
  error_message: null,
  prompt_tokens: 100,
  completion_tokens: 50,
  total_cost: 0.01,
  created_at: NOW,
  updated_at: NOW,
};

export const personaJob: JobResponse = {
  id: 99,
  target_id: TARGET_ID,
  type: JobType.PERSONA_GENERATION,
  count_requested: 3,
  model_used: "openai/gpt-4o",
  status: JobStatus.COMPLETED,
  prompt_tokens: 500,
  completion_tokens: 200,
  total_cost: 0.02,
  created_at: NOW,
  updated_at: NOW,
};

export const scoringStatusComplete: ScoringStatusResponse = {
  snapshot_id: SNAPSHOT_ID,
  selected_ids: [answer.id],
  selected_and_annotated_ids: [answer.id],
  is_complete: true,
  completion_percentage: 100,
  unanswered_question_count: 0,
};

export const scoringStatusIncomplete: ScoringStatusResponse = {
  snapshot_id: SNAPSHOT_ID,
  selected_ids: [answer.id],
  selected_and_annotated_ids: [],
  is_complete: false,
  completion_percentage: 0,
  unanswered_question_count: 0,
};

export const scoringRubricsResponse: ScoringRubricsResponse = {
  snapshot_id: SNAPSHOT_ID,
  rubrics: [
    {
      ...accuracyRubric,
      judges: [judge],
    },
  ],
};

export const scoringResultsResponse: ScoringResultsResponse = {
  snapshot_id: SNAPSHOT_ID,
  snapshot_name: "Snapshot 1",
  created_at: NOW,
  rubric_id: RUBRIC_ID,
  rubric_name: "Accuracy",
  group: "fixed",
  aggregated_score: 0.8,
  total_answers: 5,
  accurate_count: 4,
  inaccurate_count: 1,
  pending_count: 0,
  edited_count: 0,
  judge_alignment_range: { min: 0.75, max: 0.85 },
  aligned_judges: [{ judge_id: JUDGE_ID, name: judge.name, f1: 0.8 }],
  best_option: "correct",
  judge_summaries: [
    {
      judge_id: JUDGE_ID,
      name: judge.name,
      reliability: 0.8,
      accuracy: 0.8,
      accurate_count: 4,
      total_answers: 5,
    },
  ],
  rows: [
    {
      question_id: question.id,
      question_text: question.text,
      question_type: null,
      question_scope: null,
      answer_id: answer.id,
      answer_content: answer.answer_content,
      aggregated_result: {
        method: "majority",
        value: "correct",
        baseline_value: null,
        is_edited: false,
      },
      judge_results: [{ judge_id: JUDGE_ID, name: judge.name, value: "correct" }],
    },
  ],
  total_count: 1,
  page: 0,
  page_size: 50,
  pending_counts: {},
  persona_options: [],
};

export const snapshotMetricsResponse: SnapshotMetricsResponse = {
  target_id: TARGET_ID,
  rubrics: [
    {
      rubric_id: RUBRIC_ID,
      rubric_name: "Accuracy",
      group: "fixed",
      snapshots: [
        {
          snapshot_id: SNAPSHOT_ID,
          snapshot_name: "Snapshot 1",
          created_at: NOW,
          rubric_id: RUBRIC_ID,
          rubric_name: "Accuracy",
          aggregated_score: 0.8,
          total_answers: 5,
          accurate_count: 4,
          inaccurate_count: 1,
          pending_count: 0,
          edited_count: 0,
          judge_alignment_range: { min: 0.75, max: 0.85 },
          aligned_judges: [],
        },
      ],
    },
  ],
};

export const providerSetupResponse: ProviderSetupResponse = {
  providers: [
    {
      key: "openai",
      display_name: "OpenAI",
      logo_path: "/logos/openai.svg",
      is_valid: true,
      is_read_only: false,
      source: "shared",
      default_model: "gpt-4o",
      common_models: ["gpt-4o", "gpt-4o-mini"],
      embedding_models: [],
      credential_fields: [],
    },
  ],
  services: [],
  valid_models: [
    {
      value: "openai/gpt-4o",
      label: "GPT-4o",
      provider_key: "openai",
      provider_name: "OpenAI",
      logo_path: "/logos/openai.svg",
    },
  ],
  valid_embedding_models: [],
  defaults: {
    generation_default_model: "openai/gpt-4o",
    embedding_default_model: null,
    judge_default_models: ["openai/gpt-4o"],
    web_search_enabled: false,
  },
};
