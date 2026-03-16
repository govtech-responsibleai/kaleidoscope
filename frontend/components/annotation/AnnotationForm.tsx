"use client";

import React, { useEffect, useState } from "react";
import {
  Alert,
  Box,
  CircularProgress,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import { Answer, Annotation, AnswerRubricLabel, TargetRubricResponse } from "@/lib/types";
import { annotationApi } from "@/lib/api";

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

interface AccuracyRowProps {
  value: boolean | null;
  onChange: (val: boolean) => void;
  saving: boolean;
}

function AccuracyRow({ value, onChange, saving }: AccuracyRowProps) {
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
    </Box>
  );
}

interface CustomRubricRowProps {
  rubric: TargetRubricResponse;
  value: string | null;
  onChange: (val: string) => void;
  saving: boolean;
}

function getOptionColor(opt: string, rubric: TargetRubricResponse): { main: string; dark: string } {
  const bestOption = rubric.best_option || rubric.options?.[0]?.option || "";
  if (opt === bestOption) return { main: "success.main", dark: "success.dark" };
  // If only 2 options, the non-positive is red; otherwise blue
  if (rubric.options.length <= 2) return { main: "error.main", dark: "error.dark" };
  return { main: "primary.main", dark: "primary.dark" };
}

function CustomRubricRow({ rubric, value, onChange, saving }: CustomRubricRowProps) {
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
    </Box>
  );
}

interface AnnotationFormProps {
  answer: Answer | null;
  onAnnotationSaved: () => void;
  showHelperAlert?: boolean;
  onDismissHelperAlert?: () => void;
  rubrics: TargetRubricResponse[];
}

export default function AnnotationForm({
  answer,
  onAnnotationSaved,
  showHelperAlert = false,
  onDismissHelperAlert,
  rubrics,
}: AnnotationFormProps) {
  const [accuracyLabel, setAccuracyLabel] = useState<boolean | null>(null);
  const [existingAnnotation, setExistingAnnotation] = useState<Annotation | null>(null);
  // Map rubricId → selected option string
  const [rubricLabels, setRubricLabels] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [loading, setLoading] = useState(false);
  const [savingRubric, setSavingRubric] = useState<number | "accuracy" | null>(null);

  useEffect(() => {
    if (!answer) {
      setAccuracyLabel(null);
      setExistingAnnotation(null);
      setRubricLabels({});
      setNotes("");
      return;
    }

    const fetchAll = async () => {
      setLoading(true);
      try {
        const [annotationRes, rubricRes] = await Promise.allSettled([
          annotationApi.getByAnswer(answer.id),
          annotationApi.getRubricLabels(answer.id),
        ]);

        if (annotationRes.status === "fulfilled") {
          setExistingAnnotation(annotationRes.value.data);
          setAccuracyLabel(annotationRes.value.data.label);
          setNotes(annotationRes.value.data.notes ?? "");
        } else {
          setExistingAnnotation(null);
          setAccuracyLabel(null);
          setNotes("");
        }

        if (rubricRes.status === "fulfilled") {
          const map: Record<number, string> = {};
          rubricRes.value.data.forEach((rl: AnswerRubricLabel) => {
            map[rl.rubric_id] = rl.option_value;
          });
          setRubricLabels(map);
        } else {
          setRubricLabels({});
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

  const handleNotesSave = async (value: string) => {
    if (!answer || !existingAnnotation) return;
    if (value === (existingAnnotation.notes ?? "")) return;
    setSavingNotes(true);
    try {
      await annotationApi.update(existingAnnotation.id, { answer_id: answer.id, label: accuracyLabel!, notes: value });
      setExistingAnnotation((prev) => prev ? { ...prev, notes: value } : prev);
    } catch (err) {
      console.error("Failed to save notes:", err);
    } finally {
      setSavingNotes(false);
    }
  };

  const handleRubricChange = async (rubricId: number, optionValue: string) => {
    if (!answer) return;
    setRubricLabels((prev) => ({ ...prev, [rubricId]: optionValue }));
    setSavingRubric(rubricId);
    try {
      await annotationApi.upsertRubricLabel(answer.id, rubricId, { option_value: optionValue });
    } catch (err) {
      console.error("Failed to save rubric label:", err);
    } finally {
      setSavingRubric(null);
    }
  };

  if (!answer) {
    return (
      <Box sx={{ px: 3, py: 2, height: "100%", display: "flex", flexDirection: "column" }}>
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <Typography variant="body1" color="text.secondary" align="center">
            Select a response to annotate.
          </Typography>
        </Box>
      </Box>
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
        <Typography variant="h5">Annotations</Typography>

        {showHelperAlert && (
          <Alert severity="info" onClose={onDismissHelperAlert}>
            Ready to annotate! Toggle a label for each rubric below.
          </Alert>
        )}

        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
            <CircularProgress size={24} />
          </Box>
        ) : (
          <Stack spacing={2.5} divider={<Box sx={{ borderBottom: 1, borderColor: "divider" }} />}>
            <AccuracyRow
              value={accuracyLabel}
              onChange={handleAccuracyChange}
              saving={savingRubric === "accuracy"}
            />
            {rubrics.map((rubric) => (
              <CustomRubricRow
                key={rubric.id}
                rubric={rubric}
                value={rubricLabels[rubric.id] ?? null}
                onChange={(val) => handleRubricChange(rubric.id, val)}
                saving={savingRubric === rubric.id}
              />
            ))}

            <Box>
              <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: "block", mb: 0.75 }}>
                Comments
              </Typography>
              <TextField
                multiline
                minRows={2}
                maxRows={6}
                fullWidth
                size="small"
                placeholder="Add notes about this annotation..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                onBlur={(e) => handleNotesSave(e.target.value)}
                disabled={!existingAnnotation || savingNotes}
                helperText={!existingAnnotation ? "Set an accuracy label first to enable comments." : undefined}
              />
            </Box>
          </Stack>
        )}
      </Stack>
    </Box>
  );
}
