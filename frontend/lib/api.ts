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

export default api;
