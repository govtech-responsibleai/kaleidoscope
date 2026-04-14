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
import { Answer, Annotation, RubricAnnotation, TargetRubricResponse } from "@/lib/types";
import { annotationApi } from "@/lib/api";
import { groupColors } from "@/lib/theme";

// Shared toggle styles
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

interface AccuracyRowProps {
  value: boolean | null;
  onChange: (val: boolean) => void;
  saving: boolean;
  notes: string;
  onNotesChange: (val: string) => void;
  onNotesSave: (val: string) => void;
  notesDisabled?: boolean;
}

function AccuracyRow({ value, onChange, saving, notes, onNotesChange, onNotesSave, notesDisabled }: AccuracyRowProps) {
  return (
    <Box>
      <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: "block", mb: 0.75 }}>
        Accuracy
      </Typography>
      <ToggleButtonGroup
        exclusive
        fullWidth
        value={value === null ? "" : value ? "accurate" : "inaccurate"}
        onChange={(_, val) => { if (val !== null) onChange(val === "accurate"); }}
        sx={{
          ...toggleSx,
          "& .MuiToggleButton-root.Mui-selected[value='accurate']": {
            bgcolor: "success.main", color: "white", borderColor: "success.main",
            "&:hover": { bgcolor: "success.dark" },
          },
          "& .MuiToggleButton-root.Mui-selected[value='inaccurate']": {
            bgcolor: "error.main", color: "white", borderColor: "error.main",
            "&:hover": { bgcolor: "error.dark" },
          },
        }}
      >
        <ToggleButton value="accurate" disabled={saving}>Accurate</ToggleButton>
        <ToggleButton value="inaccurate" disabled={saving}>Inaccurate</ToggleButton>
      </ToggleButtonGroup>
      <NoteField value={notes} onChange={onNotesChange} onBlur={onNotesSave} disabled={notesDisabled} />
    </Box>
  );
}

interface CustomRubricRowProps {
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
  // If only 2 options, the non-positive is red; otherwise blue
  if (rubric.options.length <= 2) return { main: "error.main", dark: "error.dark" };
  return { main: "text.secondary", dark: "text.primary" };
}

function CustomRubricRow({ rubric, value, onChange, saving, notes, onNotesChange, onNotesSave }: CustomRubricRowProps) {
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
          onChange={(_, val) => { if (val !== null) onChange(val); }}
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
  const [accuracyLabel, setAccuracyLabel] = useState<boolean | null>(null);
  const [existingAnnotation, setExistingAnnotation] = useState<Annotation | null>(null);
  // Map rubricId → selected option string
  const [rubricLabels, setRubricLabels] = useState<Record<number, string>>({});
  const [accuracyNotes, setAccuracyNotes] = useState("");
  const [rubricNotes, setRubricNotes] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [savingRubric, setSavingRubric] = useState<number | "accuracy" | null>(null);

  const accuracyRowRef = useRef<HTMLDivElement>(null);
  const rubricRowRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const annotatableRubrics = useMemo(
    () => rubrics.filter((r) => r.options.length >= 2 && !!r.best_option),
    [rubrics]
  );

  const isFullyAnnotated = useMemo(
    () =>
      accuracyLabel !== null &&
      annotatableRubrics.every((r) => rubricLabels[r.id] !== undefined),
    [accuracyLabel, rubricLabels, annotatableRubrics]
  );

  useEffect(() => {
    if (answer && onCompletenessChanged) {
      onCompletenessChanged(answer.id, isFullyAnnotated);
    }
  }, [answer?.id, isFullyAnnotated, onCompletenessChanged]);

  useEffect(() => {
    if (activeRubricId === undefined) return;
    const el =
      activeRubricId === null
        ? accuracyRowRef.current
        : rubricRowRefs.current[activeRubricId];
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
      setAccuracyLabel(null);
      setExistingAnnotation(null);
      setRubricLabels({});
      setAccuracyNotes("");
      setRubricNotes({});
      return;
    }

    const fetchAll = async () => {
      setLoading(true);
      try {
        const [annotationRes, rubricRes] = await Promise.allSettled([
          annotationApi.getByAnswer(answer.id),
          annotationApi.getRubricAnnotations(answer.id),
        ]);

        if (annotationRes.status === "fulfilled") {
          setExistingAnnotation(annotationRes.value.data);
          setAccuracyLabel(annotationRes.value.data.label);
          setAccuracyNotes(annotationRes.value.data.notes ?? "");
        } else {
          setExistingAnnotation(null);
          setAccuracyLabel(null);
          setAccuracyNotes("");
        }

        if (rubricRes.status === "fulfilled") {
          const labelMap: Record<number, string> = {};
          const notesMap: Record<number, string> = {};
          rubricRes.value.data.forEach((rl: RubricAnnotation) => {
            labelMap[rl.rubric_id] = rl.option_value;
            notesMap[rl.rubric_id] = rl.notes ?? "";
          });
          setRubricLabels(labelMap);
          setRubricNotes(notesMap);
        } else {
          setRubricLabels({});
          setRubricNotes({});
        }
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
  }, [answer?.id]);

  const handleAccuracyChange = async (val: boolean) => {
    if (!answer) return;
    setAccuracyLabel(val);
    setSavingRubric("accuracy");
    try {
      if (existingAnnotation) {
        await annotationApi.update(existingAnnotation.id, { answer_id: answer.id, label: val });
      } else {
        const res = await annotationApi.create({ answer_id: answer.id, label: val });
        setExistingAnnotation(res.data);
      }
      onAnnotationSaved();
    } catch (err) {
      console.error("Failed to save accuracy annotation:", err);
    } finally {
      setSavingRubric(null);
    }
  };

  const handleAccuracyNotesSave = async (value: string) => {
    if (!answer || !existingAnnotation) return;
    if (value === (existingAnnotation.notes ?? "")) return;
    try {
      await annotationApi.update(existingAnnotation.id, { answer_id: answer.id, label: accuracyLabel!, notes: value });
      setExistingAnnotation((prev) => prev ? { ...prev, notes: value } : prev);
    } catch (err) {
      console.error("Failed to save accuracy notes:", err);
    }
  };

  const handleRubricNotesSave = async (rubricId: number, value: string) => {
    if (!answer) return;
    const currentOption = rubricLabels[rubricId];
    if (!currentOption) return;
    try {
      await annotationApi.upsertRubricAnnotation(answer.id, rubricId, { option_value: currentOption, notes: value });
    } catch (err) {
      console.error("Failed to save rubric notes:", err);
    }
  };

  const handleRubricChange = async (rubricId: number, optionValue: string) => {
    if (!answer) return;
    setRubricLabels((prev) => ({ ...prev, [rubricId]: optionValue }));
    setSavingRubric(rubricId);
    try {
      await annotationApi.upsertRubricAnnotation(answer.id, rubricId, { option_value: optionValue });
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
            <Box
              ref={accuracyRowRef}
              sx={{
                pl: 1.5,
                borderLeft: activeRubricId === null ? "3px solid" : "3px solid transparent",
                borderColor: activeRubricId === null ? groupColors.fixed.border : "transparent",
                transition: "border-color 0.2s",
              }}
            >
              <AccuracyRow
                value={accuracyLabel}
                onChange={handleAccuracyChange}
                saving={savingRubric === "accuracy"}
                notes={accuracyNotes}
                onNotesChange={setAccuracyNotes}
                onNotesSave={handleAccuracyNotesSave}
                notesDisabled={!existingAnnotation}
              />
            </Box>
            {annotatableRubrics.map((rubric) => (
              <Box
                key={rubric.id}
                ref={setRubricRowRef(rubric.id)}
                sx={{
                  pl: 1.5,
                  borderLeft: activeRubricId === rubric.id ? "3px solid" : "3px solid transparent",
                  borderColor: activeRubricId === rubric.id
                    ? (rubric.template_key ? groupColors.preset.border : groupColors.custom.border)
                    : "transparent",
                  transition: "border-color 0.2s",
                }}
              >
                <CustomRubricRow
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
