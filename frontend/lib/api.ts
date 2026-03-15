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
  SnapshotMetricsResponse,
  ConfusionMatrix,
  AnswerLabelOverride,
  AnswerLabelOverrideCreate,
  UserResponse,
  CreateUserRequest,
  TargetRubricCreate,
  TargetRubricUpdate,
  TargetRubricResponse,
  AnswerRubricLabel,
  AnswerRubricLabelUpsert,
  RubricAnswerScore,
} from "./types";

// API base URL - can be configured via environment variable
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to all requests
api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirect to login on 401 (expired/invalid token)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const hasToken = typeof window !== "undefined" && !!localStorage.getItem("token");
    const isAuthEndpoint = error.config?.url?.includes("/auth/login");
    if (error.response?.status === 401 && hasToken && !isAuthEndpoint) {
      localStorage.removeItem("token");
      localStorage.removeItem("username");
      localStorage.removeItem("is_admin");
      sessionStorage.setItem("session_expired", "true");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Auth endpoints
export const authApi = {
  login: async (username: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);
    const response = await api.post<{
      access_token: string;
      token_type: string;
      is_admin: boolean;
      username: string;
    }>(
      "/auth/login",
      formData,
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    );
    localStorage.setItem("token", response.data.access_token);
    localStorage.setItem("username", username);
    localStorage.setItem("is_admin", String(response.data.is_admin));
    return response.data;
  },

  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    localStorage.removeItem("is_admin");
  },

  isLoggedIn: () => {
    return typeof window !== "undefined" && !!localStorage.getItem("token");
  },

  getUsername: () => {
    return typeof window !== "undefined" ? localStorage.getItem("username") : null;
  },

  isAdmin: () => {
    return typeof window !== "undefined" && localStorage.getItem("is_admin") === "true";
  },
};

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

  exportQuestions: (id: number, format: "csv" | "json" = "json") =>
    api.get(`/targets/${id}/questions/export`, {
      params: { format },
      responseType: "blob",
    }),

  exportPersonas: (id: number, format: "csv" | "json" = "json") =>
    api.get(`/targets/${id}/personas/export`, {
      params: { format },
      responseType: "blob",
    }),
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

  sampleNemotron: (targetId: number, n: number) =>
    api.post<PersonaResponse[]>("/personas/sample-nemotron", { target_id: targetId, n }),
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

  upload: (targetId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post<{ message: string; count: number; target_id: number }>(
      `/questions/upload?target_id=${targetId}`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
  },

  listApprovedWithoutAnswers: (snapshotId: number, judgeId: number) =>
    api.get<QuestionResponse[]>(`/snapshots/${snapshotId}/questions/approved/without-answers`, {
      params: { judge_id: judgeId },
    }),

  listApprovedWithoutScores: (snapshotId: number, judgeId: number) =>
    api.get<QuestionResponse[]>(`/snapshots/${snapshotId}/questions/approved/without-scores`, {
      params: { judge_id: judgeId },
    }),

  listApprovedWithoutRubricScores: (snapshotId: number, judgeId: number, rubricId: number) =>
    api.get<QuestionResponse[]>(`/snapshots/${snapshotId}/questions/approved/without-rubric-scores`, {
      params: { judge_id: judgeId, rubric_id: rubricId },
    }),
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

  bulkSelection: (snapshotId: number, data: BulkSelectionRequest) =>
    api.post(`/snapshots/${snapshotId}/answers/bulk-selection`, data),

  selectDefault: (snapshotId: number) =>
    api.post(`/snapshots/${snapshotId}/answers/select-default`),

  // Label override methods
  getLabelOverride: (answerId: number) =>
    api.get<AnswerLabelOverride>(`/answers/${answerId}/label-override`),

  updateLabelOverride: (answerId: number, data: AnswerLabelOverrideCreate) =>
    api.put<AnswerLabelOverride>(`/answers/${answerId}/label-override`, data),

  deleteLabelOverride: (answerId: number) =>
    api.delete(`/answers/${answerId}/label-override`),
};

// Annotation endpoints
export const annotationApi = {
  create: (data: AnnotationCreate) =>
    api.post<Annotation>("/annotations", data),

  bulkCreate: (data: AnnotationBulkCreate) =>
    api.post<Annotation[]>("/annotations/bulk", data),

  listBySnapshot: (snapshotId: number) =>
    api.get<{ annotations: Annotation[]; total: number }>(`/snapshots/${snapshotId}/annotations`),

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

  getRubricLabels: (answerId: number) =>
    api.get<AnswerRubricLabel[]>(`/answers/${answerId}/rubric-labels`),

  upsertRubricLabel: (answerId: number, rubricId: number, data: AnswerRubricLabelUpsert) =>
    api.put<AnswerRubricLabel>(`/answers/${answerId}/rubric-labels/${rubricId}`, data),
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

  getByCategory: (category: string) =>
    api.get<JudgeConfig[]>(`/judges/by-category/${category}`),
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

  listByJudge: (snapshotId: number, judgeId: number) =>
    api.get<QAJob[]>(`/snapshots/${snapshotId}/judges/${judgeId}/qa-jobs`),

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

  exportCSV: (snapshotId: number, format: "csv" | "json" = "csv") =>
    api.get(`/targets/snapshots/${snapshotId}/export`, {
      params: { format },
      responseType: "blob",
    }),

  exportJSON: (snapshotId: number) =>
    api.get(`/targets/snapshots/${snapshotId}/export`, {
      params: { format: "json", include_evaluators: true },
    }),

  getSnapshotMetrics: (targetId: number) =>
    api.get<SnapshotMetricsResponse>(`/targets/${targetId}/snapshot-metrics`),

  getConfusionMatrix: (targetId: number, snapshotId?: number) =>
    api.get<ConfusionMatrix>(`/targets/${targetId}/confusion-matrix`, {
      params: snapshotId ? { snapshot_id: snapshotId } : undefined,
    }),
};

// Admin endpoints
export const adminApi = {
  listUsers: () =>
    api.get<UserResponse[]>("/auth/admin/users"),

  createUser: (data: CreateUserRequest) =>
    api.post<{ message: string; username: string }>("/auth/admin/create-user-jwt", data),

  deleteUser: (username: string) =>
    api.delete<{ message: string }>(`/auth/admin/delete-user-jwt/${username}`),
};

// Rubric QA Job endpoints
export const rubricQAJobApi = {
  start: (snapshotId: number, data: { judge_id: number; question_ids: number[]; rubric_id: number }) =>
    api.post<QAJob[]>(`/snapshots/${snapshotId}/rubric-qa-jobs/start`, data),
};

// Rubric score endpoints
export const rubricScoreApi = {
  getForAnswer: (answerId: number, rubricId: number) =>
    api.get<RubricAnswerScore[]>(`/answers/${answerId}/rubric-scores`, {
      params: { rubric_id: rubricId },
    }),
};

export const targetRubricApi = {
  list: (targetId: number) =>
    api.get<TargetRubricResponse[]>(`/targets/${targetId}/rubrics`),

  create: (targetId: number, data: TargetRubricCreate) =>
    api.post<TargetRubricResponse>(`/targets/${targetId}/rubrics`, data),

  update: (targetId: number, rubricId: number, data: TargetRubricUpdate) =>
    api.put<TargetRubricResponse>(`/targets/${targetId}/rubrics/${rubricId}`, data),

  delete: (targetId: number, rubricId: number) =>
    api.delete(`/targets/${targetId}/rubrics/${rubricId}`),
};

export default api;
