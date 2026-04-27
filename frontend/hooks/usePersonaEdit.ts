"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { personaApi } from "@/lib/api";
import { PersonaResponse, PersonaUpdate } from "@/lib/types";

interface PersonaEditState {
  editingPersonaId: number | null;
  editedTitle: string;
  editedInfo: string;
  editedStyle: string;
  editedUseCase: string;
  savingPersonaId: number | null;
  saveError: string | null;
}

const initialState: PersonaEditState = {
  editingPersonaId: null,
  editedTitle: "",
  editedInfo: "",
  editedStyle: "",
  editedUseCase: "",
  savingPersonaId: null,
  saveError: null,
};

interface UsePersonaEditOptions {
  onSaved?: (personaId: number, updated: PersonaResponse) => void;
  onError?: (message: string) => void;
}

export function usePersonaEdit(options: UsePersonaEditOptions = {}) {
  const [state, setState] = useState<PersonaEditState>(initialState);
  const onSavedRef = useRef(options.onSaved);
  const onErrorRef = useRef(options.onError);

  useEffect(() => {
    onSavedRef.current = options.onSaved;
    onErrorRef.current = options.onError;
  }, [options.onError, options.onSaved]);

  const startEdit = useCallback((persona: PersonaResponse) => {
    setState({
      editingPersonaId: persona.id,
      editedTitle: persona.title,
      editedInfo: persona.info || "",
      editedStyle: persona.style || "",
      editedUseCase: persona.use_case || "",
      savingPersonaId: null,
      saveError: null,
    });
  }, []);

  const cancelEdit = useCallback(() => {
    setState(initialState);
  }, []);

  const saveEdit = useCallback(async (personaId: number, personas: PersonaResponse[]) => {
    setState((prev) => ({ ...prev, savingPersonaId: personaId }));
    try {
      const persona = personas.find((p) => p.id === personaId);
      if (!persona) return;

      const updates: PersonaUpdate = {};
      if (state.editedTitle !== persona.title) updates.title = state.editedTitle;
      if (state.editedInfo !== (persona.info || "")) updates.info = state.editedInfo;
      if (state.editedStyle !== (persona.style || "")) updates.style = state.editedStyle;
      if (state.editedUseCase !== (persona.use_case || "")) updates.use_case = state.editedUseCase;

      if (Object.keys(updates).length > 0) {
        const response = await personaApi.update(personaId, updates);
        onSavedRef.current?.(personaId, response.data);
      } else {
        onSavedRef.current?.(personaId, persona);
      }
      setState(initialState);
    } catch (err) {
      console.error("Failed to update persona:", err);
      const message = "Failed to update persona. Please try again.";
      setState((prev) => ({ ...prev, saveError: message }));
      onErrorRef.current?.(message);
    } finally {
      setState((prev) => ({ ...prev, savingPersonaId: null }));
    }
  }, [state.editedInfo, state.editedStyle, state.editedTitle, state.editedUseCase]);

  return {
    ...state,
    setEditedTitle: (v: string) => setState((prev) => ({ ...prev, editedTitle: v })),
    setEditedInfo: (v: string) => setState((prev) => ({ ...prev, editedInfo: v })),
    setEditedStyle: (v: string) => setState((prev) => ({ ...prev, editedStyle: v })),
    setEditedUseCase: (v: string) => setState((prev) => ({ ...prev, editedUseCase: v })),
    startEdit,
    cancelEdit,
    saveEdit,
    reset: cancelEdit,
  };
}
