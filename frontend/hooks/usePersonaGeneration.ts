"use client";

import { useState, useRef, useCallback } from "react";
import { getApiErrorMessage, jobApi, personaApi } from "@/lib/api";
import { PersonaResponse, JobStatus } from "@/lib/types";
import { DEFAULT_PERSONA_COUNT } from "@/lib/constants";

export type PersonaSource = "ai" | "general" | null;

export function usePersonaGeneration(targetId: number) {
  const [personas, setPersonas] = useState<PersonaResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<PersonaSource>(null);
  const cancelledRef = useRef(false);

  const generateWithAI = useCallback(async (count = DEFAULT_PERSONA_COUNT, modelUsed?: string) => {
    setSource("ai");
    setLoading(true);
    setError(null);
    cancelledRef.current = false;
    try {
      const jobResponse = await jobApi.createPersonaJob(targetId, {
        count_requested: count,
        model_used: modelUsed,
      });
      const jobId = jobResponse.data.id;
      let completed = false;
      while (!completed) {
        if (cancelledRef.current) return;
        await new Promise((resolve) => setTimeout(resolve, 2000));
        if (cancelledRef.current) return;
        const statusResponse = await jobApi.get(jobId);
        if (statusResponse.data.status === JobStatus.COMPLETED) {
          completed = true;
          const personasResponse = await jobApi.getPersonas(jobId);
          if (!cancelledRef.current) {
            setPersonas((prev) => [...prev, ...personasResponse.data]);
          }
        } else if (statusResponse.data.status === JobStatus.FAILED) {
          throw new Error("Persona generation failed");
        }
      }
    } catch (err) {
      if (!cancelledRef.current) {
        console.error("Failed to generate personas:", err);
        setError(getApiErrorMessage(err, "Failed to generate personas. Please try again."));
      }
    } finally {
      if (!cancelledRef.current) {
        setLoading(false);
      }
    }
  }, [targetId]);

  const sampleNemotron = useCallback(async (count = DEFAULT_PERSONA_COUNT) => {
    setSource("general");
    setLoading(true);
    setError(null);
    try {
      const response = await personaApi.sampleNemotron(targetId, count);
      setPersonas((prev) => [...prev, ...response.data]);
    } catch (err) {
      console.error("Failed to sample personas:", err);
      setError("Failed to sample general personas. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [targetId]);

  const addManualPersona = useCallback(async (data: {
    title: string;
    info?: string;
    style?: string;
    use_case?: string;
  }) => {
    setLoading(true);
    setError(null);
    try {
      const response = await personaApi.create({
        target_id: targetId,
        title: data.title,
        info: data.info,
        style: data.style,
        use_case: data.use_case,
      });
      setPersonas((prev) => [...prev, response.data]);
      return response.data;
    } catch (err) {
      console.error("Failed to create persona:", err);
      setError("Failed to create persona. Please try again.");
      return null;
    } finally {
      setLoading(false);
    }
  }, [targetId]);

  const reset = useCallback(() => {
    cancelledRef.current = true;
    setPersonas([]);
    setLoading(false);
    setError(null);
    setSource(null);
  }, []);

  const updatePersona = useCallback((personaId: number, updated: PersonaResponse) => {
    setPersonas((prev) => prev.map((p) => (p.id === personaId ? updated : p)));
  }, []);

  return {
    personas,
    loading,
    error,
    source,
    setError,
    generateWithAI,
    sampleNemotron,
    addManualPersona,
    updatePersona,
    reset,
  };
}
