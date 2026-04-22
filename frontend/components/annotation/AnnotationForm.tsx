"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  CircularProgress,
  Link,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { Answer, AnswerAnnotation, TargetRubricResponse } from "@/lib/types";
import { annotationApi } from "@/lib/api";
import { groupColors } from "@/lib/theme";
import { orderRubricsForDisplay } from "@/lib/rubrics";

const toggleSx = {
  "& .MuiToggleButton-root": {
    py: 1.25,
    fontSize: "0.85rem",
    fontWeight: 600,
    textTransform: "none",
    border: "1px solid",
    borderColor: "divider",
    flex: 1,
    transition: "all 0.15s",
  },
};

interface NoteFieldProps {
  value: string;
  onChange: (val: string) => void;
  onBlur: (val: string) => void;
  disabled?: boolean;
}

function NoteField({ value, onChange, onBlur, disabled }: NoteFieldProps) {
  const [open, setOpen] = useState(false);
  const hasContent = value.length > 0;

  if (!open && !hasContent) {
    return (
      <Link
        component="button"
        variant="caption"
        underline="hover"
        color="text.secondary"
        onClick={() => setOpen(true)}
        sx={{ mt: 0.5, display: "inline-block" }}
      >
        + Add note
      </Link>
    );
  }

  return (
    <TextField
      autoFocus={!hasContent}
      multiline
      minRows={1}
      maxRows={4}
      fullWidth
      size="small"
      placeholder="Add a note..."
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onBlur={(e) => {
        onBlur(e.target.value);
        if (e.target.value.length === 0) setOpen(false);
      }}
      disabled={disabled}
      sx={{ mt: 0.75, "& .MuiOutlinedInput-root": { borderRadius: 1.5 } }}
    />
  );
}

interface RubricRowProps {
  rubric: TargetRubricResponse;
  value: string | null;
  onChange: (val: string) => void;
  saving: boolean;
  notes: string;
  onNotesChange: (val: string) => void;
  onNotesSave: (val: string) => void;
}

function getOptionColor(opt: string, rubric: TargetRubricResponse): { main: string; dark: string } {
  const bestOption = rubric.best_option || rubric.options?.[0]?.option || "";
  if (opt === bestOption) return { main: "success.main", dark: "success.dark" };
  if (rubric.options.length <= 2) return { main: "error.main", dark: "error.dark" };
  return { main: "text.secondary", dark: "text.primary" };
}

function RubricRow({ rubric, value, onChange, saving, notes, onNotesChange, onNotesSave }: RubricRowProps) {
  return (
    <Box>
      <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: "block", mb: 0.75 }}>
        {rubric.name}
      </Typography>
      {rubric.options.length === 0 ? (
        <Typography variant="caption" color="text.disabled" fontStyle="italic">
          No options defined for this rubric.
        </Typography>
      ) : (
        <ToggleButtonGroup
          exclusive
          fullWidth
          value={value ?? ""}
          onChange={(_, val) => {
            if (val !== null) onChange(val);
          }}
          sx={toggleSx}
        >
          {rubric.options.map((opt) => {
            const color = getOptionColor(opt.option, rubric);
            return (
              <ToggleButton
                key={opt.option}
                value={opt.option}
                disabled={saving}
                sx={{
                  "&.Mui-selected": {
                    bgcolor: color.main,
                    color: "white",
                    borderColor: color.main,
                    "&:hover": { bgcolor: color.dark },
                  },
                }}
              >
                {opt.option}
              </ToggleButton>
            );
          })}
        </ToggleButtonGroup>
      )}
      <NoteField value={notes} onChange={onNotesChange} onBlur={onNotesSave} />
    </Box>
  );
}

interface AnnotationFormProps {
  answer: Answer | null;
  onAnnotationSaved: () => void;
  rubrics: TargetRubricResponse[];
  activeRubricId?: number | null;
  onCompletenessChanged?: (answerId: number, isFullyAnnotated: boolean) => void;
}

export default function AnnotationForm({
  answer,
  onAnnotationSaved,
  rubrics,
  activeRubricId,
  onCompletenessChanged,
}: AnnotationFormProps) {
  const [rubricLabels, setRubricLabels] = useState<Record<number, string>>({});
  const [rubricNotes, setRubricNotes] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [savingRubric, setSavingRubric] = useState<number | null>(null);

  const rubricRowRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const annotatableRubrics = useMemo(
    () => orderRubricsForDisplay(rubrics).filter((rubric) => rubric.options.length >= 2 && !!rubric.best_option),
    [rubrics]
  );

  const isFullyAnnotated = useMemo(
    () => annotatableRubrics.every((rubric) => rubricLabels[rubric.id] !== undefined),
    [annotatableRubrics, rubricLabels]
  );

  useEffect(() => {
    if (answer && onCompletenessChanged) {
      onCompletenessChanged(answer.id, isFullyAnnotated);
    }
  }, [answer?.id, isFullyAnnotated, onCompletenessChanged]);

  useEffect(() => {
    if (activeRubricId === undefined || activeRubricId === null) return;
    const el = rubricRowRefs.current[activeRubricId];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [activeRubricId]);

  const setRubricRowRef = useCallback(
    (rubricId: number) => (el: HTMLDivElement | null) => {
      rubricRowRefs.current[rubricId] = el;
    },
    []
  );

  useEffect(() => {
    if (!answer) {
      setRubricLabels({});
      setRubricNotes({});
      return;
    }

    const fetchAnnotations = async () => {
      setLoading(true);
      try {
        const response = await annotationApi.listByAnswer(answer.id);
        const labelMap: Record<number, string> = {};
        const notesMap: Record<number, string> = {};
        response.data.forEach((annotation: AnswerAnnotation) => {
          labelMap[annotation.rubric_id] = annotation.option_value;
          notesMap[annotation.rubric_id] = annotation.notes ?? "";
        });
        setRubricLabels(labelMap);
        setRubricNotes(notesMap);
      } catch {
        setRubricLabels({});
        setRubricNotes({});
      } finally {
        setLoading(false);
      }
    };

    void fetchAnnotations();
  }, [answer?.id]);

  const handleRubricNotesSave = async (rubricId: number, value: string) => {
    if (!answer) return;
    const currentOption = rubricLabels[rubricId];
    if (!currentOption) return;
    try {
      await annotationApi.upsertByAnswerAndRubric(answer.id, rubricId, {
        option_value: currentOption,
        notes: value,
      });
    } catch (err) {
      console.error("Failed to save rubric notes:", err);
    }
  };

  const handleRubricChange = async (rubricId: number, optionValue: string) => {
    if (!answer) return;
    setRubricLabels((prev) => ({ ...prev, [rubricId]: optionValue }));
    setSavingRubric(rubricId);
    try {
      await annotationApi.upsertByAnswerAndRubric(answer.id, rubricId, { option_value: optionValue });
      onAnnotationSaved();
    } catch (err) {
      console.error("Failed to save rubric label:", err);
    } finally {
      setSavingRubric(null);
    }
  };

  if (!answer) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        Waiting for answer to be generated.
      </Typography>
    );
  }

  if (!answer.answer_content) {
    return (
      <Box sx={{ height: "100%", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <Typography variant="body1" color="text.secondary" align="center">
          Answer generation in progress.
        </Typography>
      </Box>
    );
  }

  if (!answer.is_selected_for_annotation) {
    return (
      <Box sx={{ height: "100%" }}>
        <Alert severity="info">Add this response to the annotation set to enable labeling.</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Stack spacing={2.5} sx={{ flex: 1 }}>
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
            <CircularProgress size={24} />
          </Box>
        ) : (
          <Stack spacing={2.5} divider={<Box sx={{ borderBottom: 1, borderColor: "divider" }} />}>
            {annotatableRubrics.map((rubric) => (
              <Box
                key={rubric.id}
                ref={setRubricRowRef(rubric.id)}
                sx={{
                  pl: 1.5,
                  borderLeft: activeRubricId === rubric.id ? "3px solid" : "3px solid transparent",
                  borderColor: activeRubricId === rubric.id
                    ? rubric.group === "fixed"
                      ? groupColors.fixed.border
                      : rubric.group === "preset"
                        ? groupColors.preset.border
                        : groupColors.custom.border
                    : "transparent",
                  transition: "border-color 0.2s",
                }}
              >
                <RubricRow
                  rubric={rubric}
                  value={rubricLabels[rubric.id] ?? null}
                  onChange={(val) => handleRubricChange(rubric.id, val)}
                  saving={savingRubric === rubric.id}
                  notes={rubricNotes[rubric.id] ?? ""}
                  onNotesChange={(val) => setRubricNotes((prev) => ({ ...prev, [rubric.id]: val }))}
                  onNotesSave={(val) => handleRubricNotesSave(rubric.id, val)}
                />
              </Box>
            ))}
          </Stack>
        )}
      </Stack>
    </Box>
  );
}
