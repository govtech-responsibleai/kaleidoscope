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

// Job progress tracking for multiple jobs
export interface JobProgress {
  completed: number;
  running: number;
  paused: number;
  failed: number;
  total: number;
}

// Target types
export enum EndpointType {
  AIBOTS = "aibots",
}

export interface EndpointConfig {
  api_key?: string;
}

export interface TargetBase {
  name: string;
  agency?: string;
  purpose?: string;
  target_users?: string;
  api_endpoint?: string;
  endpoint_type?: EndpointType;
  endpoint_config?: EndpointConfig;
}

export interface TargetCreate extends TargetBase {}

export interface TargetUpdate {
  name?: string;
  agency?: string;
  purpose?: string;
  target_users?: string;
  api_endpoint?: string;
  endpoint_type?: EndpointType;
  endpoint_config?: EndpointConfig;
}

export interface TargetResponse extends TargetBase {
  id: number;
  user_id?: number;
  owner_username?: string;
  created_at: string;
  updated_at: string;
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

export interface QuestionBase {
  text: string;
  type: QuestionType | null;
  scope: QuestionScope | null;
}

export interface QuestionUpdate {
  text?: string;
  type?: QuestionType | null;
  scope?: QuestionScope | null;
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

export interface QAJob {
  id: number;
  snapshot_id: number;
  question_id: number;
  answer_id: number | null;
  judge_id: number;
  type: string;
  status: JobStatus;
  stage: QAJobStageEnum;
  error_message: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost: number;
  created_at: string;
  updated_at: string;
}

export interface QAJobStartRequest {
  judge_id: number;
  question_ids: number[];
  job_ids?: number[]
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
  overall_label: boolean;
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

// Annotation types
export interface AnnotationCreate {
  answer_id: number;
  label: boolean;
  notes?: string;
}

export interface AnnotationBulkCreate {
  annotations: AnnotationCreate[];
}

export interface Annotation {
  id: number;
  answer_id: number;
  label: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface AnnotationCompletionStatus {
  selected_ids: number[];
  selected_and_annotated_ids: number[];
  is_complete: boolean;
  completion_percentage: number;
}

// Judge types
export type JudgeType = "claim_based" | "response_level";

export interface JudgeModelOption {
  value: string;
  label: string;
}

export interface JudgeConfig {
  id: number;
  target_id: number;
  name: string;
  model_name: string;
  model_label?: string;
  temperature?: number;
  judge_type: JudgeType;
  is_baseline: boolean;
  is_editable: boolean;
  params: Record<string, any>;
  prompt_template?: string;
  created_at: string;
  updated_at: string;
}

export interface JudgeCreate {
  target_id: number;
  name: string;
  model_name: string;
  model_label?: string;
  judge_type: JudgeType;
  params?: Record<string, any>;
  prompt_template?: string;
}

export interface JudgeUpdate {
  name?: string;
  model_name?: string;
  model_label?: string;
  judge_type?: JudgeType;
  params?: Record<string, any>;
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
  | "override";

export interface AggregatedAccuracy {
  answer_id: number;
  method: AggregationMethod;
  label: boolean | null;
  is_edited: boolean;
  metadata: string[];
  aligned_judge_count: number;
}

// Answer Label Override types
export interface AnswerLabelOverride {
  id: number;
  answer_id: number;
  metric_name: string;
  edited_label: boolean;
  edited_at: string;
}

export interface AnswerLabelOverrideCreate {
  edited_label: boolean;
}

export interface ResultRow {
  question_id: number;
  question_text: string | null;
  question_type: string | null;
  question_scope: string | null;
  answer_id: number;
  answer_content: string;
  aggregated_accuracy: AggregatedAccuracy;
  human_label: boolean | null;
  human_notes: string | null;
}

export type SnapshotResultsResponse = ResultRow[];

export interface AlignedJudge {
  judge_id: number;
  name: string;
  f1: number;
}

export interface SnapshotMetric {
  snapshot_id: number;
  snapshot_name: string;
  created_at: string;
  aggregated_accuracy: number;
  total_answers: number;
  edited_count: number;
  judge_alignment_range: { min: number; max: number } | null;
  aligned_judges: AlignedJudge[];
}

export type SnapshotMetricsResponse = SnapshotMetric[];

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

// Rubric annotation label types
export interface AnswerRubricLabelUpsert {
  option_value: string;
}

export interface AnswerRubricLabel {
  id: number;
  answer_id: number;
  rubric_id: number;
  option_value: string;
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
}

export interface TargetRubricUpdate {
  name?: string;
  criteria?: string;
  options?: RubricOption[];
}

export type RubricCategory = "accuracy" | "voice" | "relevancy" | "default";

export interface TargetRubricResponse {
  id: number;
  target_id: number;
  name: string;
  criteria: string;
  options: RubricOption[];
  position: number;
  category: RubricCategory;
  created_at: string;
  updated_at: string;
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
