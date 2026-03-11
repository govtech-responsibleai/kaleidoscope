"use client";

import { useState } from "react";
import { personaApi } from "@/lib/api";
import { PersonaResponse, PersonaUpdate } from "@/lib/types";

interface PersonaEditState {
  editingPersonaId: number | null;
  editedTitle: string;
  editedInfo: string;
  editedStyle: string;
  editedUseCase: string;
  savingPersonaId: number | null;
}

const initialState: PersonaEditState = {
  editingPersonaId: null,
  editedTitle: "",
  editedInfo: "",
  editedStyle: "",
  editedUseCase: "",
  savingPersonaId: null,
};

interface UsePersonaEditOptions {
  onSaved?: (personaId: number, updated: PersonaResponse) => void;
  onError?: (message: string) => void;
}

export function usePersonaEdit(options: UsePersonaEditOptions = {}) {
  const [state, setState] = useState<PersonaEditState>(initialState);

  const startEdit = (persona: PersonaResponse) => {
    setState({
      editingPersonaId: persona.id,
      editedTitle: persona.title,
      editedInfo: persona.info || "",
      editedStyle: persona.style || "",
      editedUseCase: persona.use_case || "",
      savingPersonaId: null,
    });
  };

  const cancelEdit = () => {
    setState(initialState);
  };

  const saveEdit = async (personaId: number, personas: PersonaResponse[]) => {
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
        options.onSaved?.(personaId, response.data);
      } else {
        options.onSaved?.(personaId, persona);
      }
      setState(initialState);
    } catch (err) {
      console.error("Failed to update persona:", err);
      options.onError?.("Failed to update persona. Please try again.");
    } finally {
      setState((prev) => ({ ...prev, savingPersonaId: null }));
    }
  };

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
