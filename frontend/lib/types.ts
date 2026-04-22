/**
 * TypeScript types matching the backend API models
 */

// Enums
export enum Status {
  PENDING = "pending",
  APPROVED = "approved",
  REJECTED = "rejected",
  EDITED = "edited",
}

export enum JobType {
  PERSONA_GENERATION = "persona_generation",
  QUESTION_GENERATION = "question_generation",
}

export enum JobStatus {
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
  PAUSED = "paused",
}

export type HttpAuthPreset = "bearer" | "x-api-key" | "api-key";

export interface ManagedHttpAuthConfig {
  preset?: HttpAuthPreset;
  masked_value?: string;
  is_configured?: boolean;
  secret_value?: string;
  clear_secret?: boolean;
}

// Job progress tracking for multiple jobs
export interface JobProgress {
  completed: number;
  running: number;
  paused: number;
  failed: number;
  total: number;
}

// Target types -- endpoint_type is a dynamic string from the backend registry
export interface EndpointConfig {
  api_key?: string;
  response_content_path?: string;
  headers?: Record<string, string>;
  auth?: ManagedHttpAuthConfig;
  body_template?: Record<string, unknown>;
  method?: string;
  timeout?: number;
  response_model_path?: string;
  metadata_fields?: Record<string, string>;
  [key: string]: unknown;
}

export interface TargetBase {
  name: string;
  agency?: string;
  purpose?: string;
  target_users?: string;
  api_endpoint?: string;
  endpoint_type?: string;
  endpoint_config?: EndpointConfig;
}

export type TargetCreate = TargetBase;

export interface TargetUpdate {
  name?: string;
  agency?: string;
  purpose?: string;
  target_users?: string;
  api_endpoint?: string;
  endpoint_type?: string;
  endpoint_config?: EndpointConfig;
}

export interface TargetResponse extends TargetBase {
  id: number;
  user_id?: number;
  owner_username?: string;
  created_at: string;
  updated_at: string;
}

export interface TestConnectionRequest {
  target_id?: number;
  endpoint_type: string;
  api_endpoint: string;
  endpoint_config: EndpointConfig;
}

export interface TestConnectionResponse {
  success: boolean;
  content?: string;
  model?: string;
  error?: string;
}

export interface ProbeRequest {
  target_id?: number;
  endpoint_type: string;
  api_endpoint: string;
  endpoint_config: EndpointConfig;
  prompt?: string;
}

export interface ProbeResponse {
  success: boolean;
  status_code?: number;
  raw_body?: unknown;
  headers?: Record<string, string>;
  error?: string;
}

export interface TargetStats {
  personas: Record<string, number>;
  questions: Record<string, number>;
  total_cost: number;
}

// Persona types
export interface PersonaBase {
  title: string;
  info?: string;
  style?: string;
  use_case?: string;
}

export interface PersonaCreate {
  target_id: number;
  title: string;
  info?: string;
  style?: string;
  use_case?: string;
}

export interface PersonaUpdate {
  title?: string;
  info?: string;
  style?: string;
  use_case?: string;
}

export type PersonaSource = "generated" | "nemotron";

export interface PersonaResponse extends PersonaBase {
  id: number;
  source: PersonaSource;
  job_id: number | null;
  target_id: number;
  status: Status;
  created_at: string;
  updated_at: string;
}

// Question types
export enum QuestionType {
  TYPICAL = "typical",
  EDGE = "edge",
}

export enum QuestionScope {
  IN_KB = "in_kb",
  OUT_KB = "out_kb",
}

export enum InputStyle {
  BRIEF = "brief",
  REGULAR = "regular",
  DETAILED = "detailed",
}

export interface QuestionBase {
  text: string;
  type: QuestionType | null;
  scope: QuestionScope | null;
  input_style?: InputStyle | null;
}

export interface QuestionUpdate {
  text?: string;
  type?: QuestionType | null;
  scope?: QuestionScope | null;
  input_style?: InputStyle | null;
}

export interface QuestionResponse extends QuestionBase {
  id: number;
  job_id: number | null;
  persona_id: number | null;
  target_id: number;
  status: Status;
  created_at: string;
  updated_at: string;
}

export interface QuestionListResponse {
  items: QuestionResponse[];
  total: number;
  skip: number;
  limit: number;
}

export interface SimilarQuestionsRequest {
  target_id: number;
  question_ids: number[];
  similarity_threshold?: number;
}

export interface SimilarQuestion {
  question_id: number;
  similarity_score: number;
}

export interface QuerySimilarQuestions {
  query_question_id: number;
  similar_questions: SimilarQuestion[];
}

export interface SimilarQuestionsResponse {
  results: QuerySimilarQuestions[];
}

// Job types
export interface JobCreate {
  count_requested: number;
  model_used?: string;
  persona_ids?: number[];
  input_style?: InputStyle;
}

export interface JobResponse {
  id: number;
  target_id: number;
  type: JobType;
  persona_id?: number;
  count_requested: number;
  model_used: string;
  generation_prompt?: string;
  status: JobStatus;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost: number;
  created_at: string;
  updated_at: string;
}

export interface JobStats {
  total_generated: number;
  by_status: Record<string, number>;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost: number;
}

// KB Document types
export interface KBDocumentBase {
  filename: string;
  content_type: string;
  file_size: number;
  page_count?: number;
}

export interface KBDocumentResponse extends KBDocumentBase {
  id: number;
  target_id: number;
  sequence_order: number;
  created_at: string;
  updated_at: string;
}

export interface KBDocumentTextResponse {
  id: number;
  filename: string;
  processed_text: string;
}

export interface KBDocumentListResponse {
  documents: KBDocumentResponse[];
  total_count: number;
  total_size_bytes: number;
}

export interface KBCompiledTextResponse {
  target_id: number;
  compiled_text: string;
  document_count: number;
  total_size_bytes: number;
  documents: Array<{ id: number; filename: string; size: number }>;
}

// Snapshot types
export interface SnapshotCreate {
  target_id: number;
  name: string;
  description?: string;
}

export interface SnapshotUpdate {
  name?: string;
  description?: string;
}

export interface Snapshot {
  id: number;
  target_id: number;
  name: string;
  description?: string;
  answer_count: number;
  selected_for_annotation_count: number;
  annotated_count: number;
  created_at: string;
  updated_at: string;
}

export interface SnapshotStats {
  total_answers: number;
  selected_count: number;
  annotated_count: number;
}

// QAJob types
export enum QAJobStageEnum {
  STARTING = "starting",
  GENERATING_ANSWERS = "generating_answers",
  PROCESSING_ANSWERS = "processing_answers",
  SCORING_ANSWERS = "scoring_answers",
  COMPLETED = "completed",
}

export interface RubricSpec {
  rubric_id: number;
  judge_id: number;
}

export type RubricSpecMap = Record<number, RubricSpec>;

export interface QAJob {
  id: number;
  snapshot_id: number;
  question_id: number;
  answer_id: number | null;
  judge_id: number | null;
  rubric_specs: RubricSpec[] | null;
  type: string;
  status: JobStatus;
  stage: QAJobStageEnum;
  error_message: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost: number;
  rubric_statuses?: QARubricStatus[];
  created_at: string;
  updated_at: string;
}

export interface QAJobStartRequest {
  judge_id: number;
  question_ids: number[];
  job_ids?: number[]
}

export interface UnifiedQAJobStartRequest {
  question_ids: number[];
  rubric_specs?: RubricSpec[];
  job_ids?: number[];
}

// Answer types
export interface AnswerClaim {
  id: number;
  answer_id: number;
  claim_text: string;
  claim_index: number;
  checkworthy: boolean;
  created_at?: string;
  checked_at?: string;
}

export interface Answer {
  id: number;
  snapshot_id: number;
  question_id: number;
  chat_id?: string | null;
  message_id?: string | null;
  answer_content: string;
  model?: string | null;
  guardrails?: unknown;
  rag_citations?: Array<Record<string, unknown>> | null;
  is_selected_for_annotation: boolean;
  question_text?: string | null;
  has_annotation?: boolean;
  claims?: AnswerClaim[];
  created_at: string;
}

export interface AnswerListResponse {
  answers: Answer[];
  total: number;
}

export interface AnswerClaimScore {
  id: number;
  answer_score_id: number;
  claim_id: number;
  label: boolean;
  explanation: string;
}

export interface AnswerScore {
  id: number;
  answer_id: number;
  judge_id: number;
  overall_label: string;
  explanation?: string;
  claim_scores?: AnswerClaimScore[];
  created_at: string;
}

export interface AnswerWithClaims extends Answer {
  claims: AnswerClaim[];
}

export interface AnswerClaimsWithScoresResponse {
  answer_id: number;
  claims: (AnswerClaim & { score?: AnswerClaimScore })[];
}

export interface BulkSelectionRequest {
  selections: { answer_id: number; is_selected: boolean }[];
}

export interface AnnotationCompletionStatus {
  selected_ids: number[];
  selected_and_annotated_ids: number[];
  is_complete: boolean;
  completion_percentage: number;
}

// Judge types
export interface JudgeModelOption {
  value: string;
  label: string;
}

export interface JudgeConfig {
  id: number;
  target_id?: number | null;
  rubric_id?: number | null;
  name: string;
  model_name: string;
  model_label?: string;
  temperature?: number;
  is_baseline: boolean;
  is_editable: boolean;
  params: Record<string, unknown>;
  prompt_template?: string;
  created_at: string;
  updated_at: string;
}

export interface RubricAnswerScore {
  id: number;
  answer_id: number;
  rubric_id: number;
  judge_id: number;
  overall_label: string;
  explanation: string;
  created_at: string;
}

export type RubricVerdictState =
  | "no_judge_configured"
  | "awaiting_answer"
  | "pending_evaluation"
  | "job_failed"
  | "success";

export interface QARubricScore {
  judge_id: number;
  value: string;
  explanation: string;
  created_at: string;
}

export interface QARubricStatus {
  rubric_id: number;
  rubric_name: string;
  group: "fixed" | "preset" | "custom";
  state: RubricVerdictState;
  message: string;
  judge_id: number | null;
  judge_name: string | null;
  score: QARubricScore | null;
}

export interface JudgeCreate {
  target_id: number;
  rubric_id?: number | null;
  name: string;
  model_name: string;
  model_label?: string;
  params?: Record<string, unknown>;
  prompt_template?: string;
}

export interface JudgeUpdate {
  name?: string;
  model_name?: string;
  model_label?: string;
  rubric_id?: number | null;
  params?: Record<string, unknown>;
  prompt_template?: string;
}

// Metrics types
export interface JudgeAlignment {
  judge_id: number;
  snapshot_id: number;
  f1: number;
  precision: number;
  recall: number;
  accuracy: number;
  sample_count: number;
}

export interface JudgeAccuracy {
  judge_id: number;
  snapshot_id: number;
  accuracy: number;
  accurate_count: number;
  total_answers: number;
}

export type AggregationMethod =
  | "majority"
  | "majority_tied"
  | "no_aligned_judge"
  | "override"
  | "pending";

export interface AggregatedScore {
  answer_id: number;
  method: AggregationMethod;
  label: string | null;
  is_edited: boolean;
  metadata: string[];
  aligned_judge_count?: number;
}

// Answer Label Override types
export interface AnswerLabelOverride {
  id: number;
  answer_id: number;
  rubric_id: number;
  edited_value: string;
  edited_at: string;
}

export interface AnswerLabelOverrideCreate {
  edited_value: string;
}

export interface ResultRow {
  rubric_id: number;
  rubric_name: string;
  group: "fixed" | "preset" | "custom";
  question_id: number;
  question_text: string | null;
  question_type: string | null;
  question_scope: string | null;
  answer_id: number;
  answer_content: string;
  aggregated_score: AggregatedScore;
  human_label: string | null;
  human_notes: string | null;
}

export interface SnapshotResultsResponse {
  snapshot_id: number;
  results: ResultRow[];
}

export interface AlignedJudge {
  judge_id: number;
  name: string;
  f1: number;
}

export interface SnapshotMetric {
  snapshot_id: number;
  snapshot_name: string;
  created_at: string;
  rubric_id?: number | null;
  rubric_name?: string | null;
  aggregated_score: number;
  total_answers: number;
  accurate_count: number;
  inaccurate_count: number;
  pending_count: number;
  edited_count: number;
  judge_alignment_range: { min: number; max: number } | null;
  aligned_judges: AlignedJudge[];
}

export interface JudgeScoreSummary {
  judge_id: number;
  name: string;
  reliability: number | null;
  accuracy: number | null;
  accurate_count: number;
  total_answers: number;
}

export interface JudgeRowResult {
  judge_id: number;
  name: string;
  value?: string | null;
}

export interface AggregatedRowResult {
  method: AggregationMethod;
  value?: string | null;
  baseline_value?: string | null;
  is_edited: boolean;
}

export interface ScoringRowResult {
  question_id: number;
  question_text: string | null;
  question_type: string | null;
  question_scope: string | null;
  answer_id: number;
  answer_content: string;
  aggregated_result: AggregatedRowResult;
  human_label?: string | null;
  judge_results: JudgeRowResult[];
}

export interface ScoringContract extends SnapshotMetric {
  rubric_id: number;
  rubric_name: string;
  group: "fixed" | "preset" | "custom";
  best_option?: string | null;
  judge_summaries: JudgeScoreSummary[];
  rows: ScoringRowResult[];
}

export interface SnapshotScoringContractsResponse {
  snapshot_id: number;
  rubrics: ScoringContract[];
}

export interface ScoringPendingCounts {
  unanswered_question_count: number;
  rubric_id: number;
  pending_counts: Record<string, number>;
}

export interface MetricsByRubric {
  rubric_id: number;
  rubric_name: string;
  group: "fixed" | "preset" | "custom";
  snapshots: SnapshotMetric[];
}

export interface SnapshotMetricsResponse {
  target_id: number;
  rubrics: MetricsByRubric[];
}

export interface ConfusionMatrix {
  matrix: {
    typical_in_kb: number;
    typical_out_kb: number;
    edge_in_kb: number;
    edge_out_kb: number;
  };
  total_inaccurate: number;
}

// Additional types for frontend use
/**
 * Aggregated QA data keyed by question id.
 * Each entry contains the progressively loaded artifacts
 * for a single question/answer pair.
 */
export interface QARecord {
  questionId: number;
  answer?: Answer;
  claims?: AnswerClaim[];
  claimScores?: AnswerClaimScore[];
  answerScore?: AnswerScore | null;
}

export type QAMap = Record<number, QARecord>;

// Answer annotation types
export interface AnswerAnnotationUpsert {
  option_value: string;
  notes?: string;
}

export interface AnswerAnnotation {
  id: number;
  answer_id: number;
  rubric_id: number;
  option_value: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// Rubric types
export interface RubricOption {
  option: string;
  description: string;
}

export interface TargetRubricCreate {
  name: string;
  criteria: string;
  options: RubricOption[];
  best_option?: string | null;
  group?: "fixed" | "preset" | "custom";
}

export interface TargetRubricUpdate {
  name?: string;
  criteria?: string;
  options?: RubricOption[];
  best_option?: string | null;
}

export interface TargetRubricResponse {
  id: number;
  target_id: number;
  name: string;
  criteria: string;
  options: RubricOption[];
  best_option: string | null;
  position: number;
  judge_prompt: string | null;
  group: "fixed" | "preset" | "custom";
  scoring_mode: "claim_based" | "response_level";
  created_at: string;
  updated_at: string;
}

export interface PremadeRubricTemplate {
  name: string;
  criteria: string;
  options: RubricOption[];
  best_option: string;
  recommended_model: string;
  group: "preset";
}

// Admin / User Management types
export interface UserResponse {
  id: number;
  username: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  target_count: number;
}

export interface CreateUserRequest {
  username: string;
  password: string;
  is_admin: boolean;
}
