/**
 * API client for the Kaleidoscope backend
 */

import axios from "axios";
import {
  TargetCreate,
  TargetResponse,
  TargetUpdate,
  TargetStats,
  PersonaResponse,
  PersonaUpdate,
  QuestionResponse,
  QuestionUpdate,
  JobCreate,
  JobResponse,
  JobStats,
  KBDocumentResponse,
  KBDocumentListResponse,
  KBDocumentTextResponse,
  KBCompiledTextResponse,
  Snapshot,
  SnapshotCreate,
  SnapshotUpdate,
  SnapshotStats,
  Answer,
  AnswerListResponse,
  AnswerScore,
  AnswerClaimsWithScoresResponse,
  BulkSelectionRequest,
  Annotation,
  AnnotationCreate,
  AnnotationBulkCreate,
  AnnotationCompletionStatus,
  JudgeConfig,
  JudgeCreate,
  JudgeUpdate,
  JudgeModelOption,
  QAJob,
  QAJobStartRequest,
  JudgeAlignment,
  JudgeAccuracy,
  ResultRow,
  SnapshotResultsResponse,
} from "./types";

// API base URL - can be configured via environment variable
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Target endpoints
export const targetApi = {
  create: (data: TargetCreate) =>
    api.post<TargetResponse>("/targets", data),

  list: () =>
    api.get<TargetResponse[]>("/targets"),

  get: (id: number) =>
    api.get<TargetResponse>(`/targets/${id}`),

  update: (id: number, data: TargetUpdate) =>
    api.put<TargetResponse>(`/targets/${id}`, data),

  delete: (id: number) =>
    api.delete(`/targets/${id}`),

  getStats: (id: number) =>
    api.get<TargetStats>(`/targets/${id}/stats`),
};

// Job endpoints
export const jobApi = {
  createPersonaJob: (targetId: number, data: JobCreate) =>
    api.post<JobResponse>(`/jobs/personas`, { ...data, target_id: targetId }),

  createQuestionJob: (targetId: number, data: JobCreate) =>
    api.post<JobResponse>(`/jobs/questions`, { ...data, target_id: targetId }),

  list: (targetId: number) =>
    api.get<JobResponse[]>(`/jobs`, { params: { target_id: targetId } }),

  get: (jobId: number) =>
    api.get<JobResponse>(`/jobs/${jobId}`),

  getStats: (jobId: number) =>
    api.get<JobStats>(`/jobs/${jobId}/stats`),

  getPersonas: (jobId: number) =>
    api.get<PersonaResponse[]>(`/jobs/${jobId}/personas`),

  getQuestions: (jobId: number) =>
    api.get<QuestionResponse[]>(`/jobs/${jobId}/questions`),
};

// Persona endpoints
export const personaApi = {
  list: (targetId: number) =>
    api.get<PersonaResponse[]>(`/targets/${targetId}/personas`),

  get: (personaId: number) =>
    api.get<PersonaResponse>(`/personas/${personaId}`),

  update: (personaId: number, data: PersonaUpdate) =>
    api.put<PersonaResponse>(`/personas/${personaId}`, data),

  approve: (personaId: number) =>
    api.post<PersonaResponse>(`/personas/${personaId}/approve`),

  reject: (personaId: number, reason?: string) =>
    api.post<PersonaResponse>(`/personas/${personaId}/reject`, { reason }),

  bulkApprove: (personaIds: number[]) =>
    api.post("/personas/bulk-approve", { persona_ids: personaIds }),
};

// Question endpoints
export const questionApi = {
  listByTarget: (targetId: number) =>
    api.get<QuestionResponse[]>(`/targets/${targetId}/questions`),

  listByPersona: (personaId: number) =>
    api.get<QuestionResponse[]>(`/personas/${personaId}/questions`),

  get: (questionId: number) =>
    api.get<QuestionResponse>(`/questions/${questionId}`),

  update: (questionId: number, data: QuestionUpdate) =>
    api.put<QuestionResponse>(`/questions/${questionId}`, data),

  approve: (questionId: number) =>
    api.post<QuestionResponse>(`/questions/${questionId}/approve`),

  reject: (questionId: number, reason?: string) =>
    api.post<QuestionResponse>(`/questions/${questionId}/reject`, { reason }),

  delete: (questionId: number) =>
    api.post<QuestionResponse>(`/questions/${questionId}/reject`),

  bulkApprove: (questionIds: number[]) =>
    api.post("/questions/bulk-approve", { question_ids: questionIds }),

  findSimilar: (data: import("./types").SimilarQuestionsRequest) =>
    api.post<import("./types").SimilarQuestionsResponse>("/questions/similar", data),
};

// KB Document endpoints
export const kbDocumentApi = {
  upload: (targetId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post<KBDocumentResponse>(
      `/targets/${targetId}/knowledge-base/upload`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
  },

  list: (targetId: number) =>
    api.get<KBDocumentListResponse>(`/targets/${targetId}/knowledge-base/documents`),

  getCompiledText: (targetId: number) =>
    api.get<KBCompiledTextResponse>(`/targets/${targetId}/knowledge-base/text`),

  getDocument: (documentId: number) =>
    api.get<KBDocumentTextResponse>(`/knowledge-base/documents/${documentId}`),

  delete: (documentId: number) =>
    api.delete(`/knowledge-base/documents/${documentId}`),
};

// Snapshot endpoints
export const snapshotApi = {
  create: (data: SnapshotCreate) =>
    api.post<Snapshot>("/snapshots", data),

  list: (targetId: number) =>
    api.get<Snapshot[]>(`targets/${targetId}/snapshots`),

  get: (snapshotId: number) =>
    api.get<Snapshot>(`/snapshots/${snapshotId}`),


  update: (snapshotId: number, data: SnapshotUpdate) =>
    api.put<Snapshot>(`/snapshots/${snapshotId}`, data),

  delete: (snapshotId: number) =>
    api.delete(`/snapshots/${snapshotId}`),

  getStats: (snapshotId: number) =>
    api.get<SnapshotStats>(`/snapshots/${snapshotId}/stats`),
};

// Answer endpoints
export const answerApi = {
  list: (snapshotId: number, selectedOnly?: boolean) =>
    api.get<AnswerListResponse>(`/snapshots/${snapshotId}/answers`),

  get: (answerId: number) =>
    api.get<Answer>(`/answers/${answerId}`),

  getScores: (answerId: number, judgeId: number) =>
    api.get<AnswerScore>(`/answers/${answerId}/scores/${judgeId}`),

  getClaims: (answerId: number, judgeId: number) =>
    api.get<AnswerClaimsWithScoresResponse>(`/answers/${answerId}/claims`, {
      params: { judge_id: judgeId },
    }),

  updateSelection: (answerId: number, isSelected: boolean) =>
    api.put(`/answers/${answerId}/selection`, { is_selected_for_annotation: isSelected }),

  bulkSelection: (data: BulkSelectionRequest) =>
    api.post("/answers/bulk-selection", data),

  selectDefault: (snapshotId: number) =>
    api.post(`/snapshots/${snapshotId}/answers/select-default`),
};

// Annotation endpoints
export const annotationApi = {
  create: (data: AnnotationCreate) =>
    api.post<Annotation>("/annotations", data),

  bulkCreate: (data: AnnotationBulkCreate) =>
    api.post<Annotation[]>("/annotations/bulk", data),

  listBySnapshot: (snapshotId: number) =>
    api.get<Annotation[]>(`/snapshots/${snapshotId}/annotations`),

  getByAnswer: (answerId: number) =>
    api.get<Annotation>(`/answers/${answerId}/annotations`),

  get: (annotationId: number) =>
    api.get<Annotation>(`/annotations/${annotationId}`),

  update: (annotationId: number, data: Partial<AnnotationCreate>) =>
    api.put<Annotation>(`/annotations/${annotationId}`, data),

  delete: (annotationId: number) =>
    api.delete(`/annotations/${annotationId}`),

  getCompletionStatus: (snapshotId: number) =>
    api.get<AnnotationCompletionStatus>(`/snapshots/${snapshotId}/annotations/completion-status`),
};

// Judge endpoints
export const judgeApi = {
  create: (data: JudgeCreate) =>
    api.post<JudgeConfig>("/judges", data),

  list: (targetId?: number) =>
    api.get<JudgeConfig[]>("/judges", {
      params: targetId ? { target_id: targetId } : undefined,
    }),

  get: (judgeId: number) =>
    api.get<JudgeConfig>(`/judges/${judgeId}`),

  update: (judgeId: number, data: JudgeUpdate) =>
    api.put<JudgeConfig>(`/judges/${judgeId}`, data),

  delete: (judgeId: number) =>
    api.delete(`/judges/${judgeId}`),

  getBaseline: () =>
    api.get<JudgeConfig>("/judges/baseline"),

  seedDefaults: () =>
    api.post<JudgeConfig[]>("/judges/seed"),

  listAvailableModels: () =>
    api.get<JudgeModelOption[]>("/judges/available-models"),
};

// QA Job endpoints
export const qaJobApi = {
  start: (snapshotId: number, data: QAJobStartRequest) =>
    api.post<QAJob[]>(`/snapshots/${snapshotId}/qa-jobs/start`, {
      snapshot_id: snapshotId,
      ...data,
    }),

  pause: (jobIds: number[]) =>
    api.post<QAJob[]>('/qa-jobs/pause', { job_ids: jobIds }),

  list: (snapshotId: number) =>
    api.get<QAJob[]>(`/snapshots/${snapshotId}/qa-jobs`),

  get: (jobId: number) =>
    api.get<QAJob>(`/qa-jobs/${jobId}`),
};

// Metrics endpoints
export const metricsApi = {
  getAlignment: (snapshotId: number, judgeId: number) =>
    api.get<JudgeAlignment>(`/snapshots/${snapshotId}/judges/${judgeId}/alignment`),

  getAccuracy: (snapshotId: number, judgeId: number) =>
    api.get<JudgeAccuracy>(`/snapshots/${snapshotId}/judges/${judgeId}/accuracy`),

  getResults: (snapshotId: number) =>
    api.get<SnapshotResultsResponse>(`/snapshots/${snapshotId}/results`),

  exportCSV: (snapshotId: number) =>
    api.post(`/snapshots/${snapshotId}/export`, undefined, {
      responseType: "blob",
    }),
};

export default api;
