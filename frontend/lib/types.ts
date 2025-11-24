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

export interface PersonaResponse extends PersonaBase {
  id: number;
  job_id: number;
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
  type: QuestionType;
  scope: QuestionScope;
}

export interface QuestionUpdate {
  text?: string;
  type?: QuestionType;
  scope?: QuestionScope;
}

export interface QuestionResponse extends QuestionBase {
  id: number;
  job_id: number;
  persona_id: number;
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
