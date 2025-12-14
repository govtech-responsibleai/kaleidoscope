"use client";

import React, { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import {
  ArrowBack as ArrowBackIcon,
  ArrowForward as ArrowForwardIcon,
} from "@mui/icons-material";
import { Answer, Annotation } from "@/lib/types";
import { annotationApi } from "@/lib/api";

interface AnnotationFormProps {
  answer: Answer | null;
  onPrev: () => void;
  onNext: () => void;
  prevDisabled: boolean;
  nextDisabled: boolean;
  onAnnotationSaved: () => void;
}

export default function AnnotationForm({
  answer,
  onPrev,
  onNext,
  prevDisabled,
  nextDisabled,
  onAnnotationSaved,
}: AnnotationFormProps) {
  const [label, setLabel] = useState<boolean | null>(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [existingAnnotation, setExistingAnnotation] = useState<Annotation | null>(null);
  const [loadingAnnotation, setLoadingAnnotation] = useState(false);

  // Fetch existing annotation when answer changes
  useEffect(() => {
    if (!answer) {
      setLabel(null);
      setNotes("");
      setExistingAnnotation(null);
      return;
    }

    const fetchAnnotation = async () => {
      setLoadingAnnotation(true);
      try {
        const response = await annotationApi.getByAnswer(answer.id);
        const annotation = response.data;
        setExistingAnnotation(annotation);
        setLabel(annotation.label);
        setNotes(annotation.notes || "");
      } catch (error) {
        // No annotation exists yet
        setExistingAnnotation(null);
        setLabel(null);
        setNotes("");
      } finally {
        setLoadingAnnotation(false);
      }
    };

    fetchAnnotation();
  }, [answer]);

  const handleSave = async () => {
    if (!answer || label === null) return;

    setSaving(true);
    try {
      if (existingAnnotation) {
        // Update existing annotation
        await annotationApi.update(existingAnnotation.id, {
          answer_id: answer.id,
          label,
          notes: notes.trim() || undefined,
        });
      } else {
        // Create new annotation
        await annotationApi.create({
          answer_id: answer.id,
          label,
          notes: notes.trim() || undefined,
        });
      }
      onAnnotationSaved();
    } catch (error) {
      console.error("Failed to save annotation:", error);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (existingAnnotation) {
      setLabel(existingAnnotation.label);
      setNotes(existingAnnotation.notes || "");
    } else {
      setLabel(null);
      setNotes("");
    }
  };

  if (!answer) {
    return (
      <Paper variant="outlined" sx={{ px: 3, py: 2, height: "100%", display: "flex", flexDirection: "column" }}>
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <Typography variant="body1" color="text.secondary" align="center">
            Select a response to annotate.
          </Typography>
        </Box>
      </Paper>
    );
  }

  // Check if answer is not yet generated or not selected for annotation
  if (!answer.answer_content) {
    return (
      <Paper variant="outlined" sx={{ px: 3, py: 2, height: "100%", display: "flex", flexDirection: "column" }}>
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <Typography variant="body1" color="text.secondary" align="center">
            Answer generation in progress. Check back later.
          </Typography>
        </Box>
      </Paper>
    );
  }

  if (!answer.is_selected_for_annotation) {
    return (
      <Paper variant="outlined" sx={{ px: 3, py: 2, height: "100%", display: "flex", flexDirection: "column" }}>
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          {/* <Typography variant="body1" color="text.secondary" align="center">
            Add this response to the annotation set to enable labeling.
          </Typography> */}
          <Alert severity="info">
            Add this response to the annotation set to enable labeling.
          </Alert>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ px: 3, py: 2, height: "100%", display: "flex", flexDirection: "column" }}>
      <Stack spacing={2} sx={{ flex: 1 }}>
        <Typography variant="h6">Your Annotations</Typography>

        <Box>
          <RadioGroup
            row
            value={label === null ? "" : label ? "accurate" : "inaccurate"}
            onChange={(event) => setLabel(event.target.value === "accurate")}
          >
            <FormControlLabel value="accurate" control={<Radio />} label="Accurate" />
            <FormControlLabel value="inaccurate" control={<Radio />} label="Inaccurate" />
          </RadioGroup>

          <TextField
            label="Notes"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            multiline
            minRows={3}
            fullWidth
            sx={{ mt: 2 }}
            placeholder="Optional notes about your annotation"
          />

          <Stack direction="row" sx={{ mt: 2 }} justifyContent="space-between">
            <Button
              startIcon={<ArrowBackIcon fontSize="small" />}
              onClick={onPrev}
              disabled={prevDisabled}
              variant="outlined"
              size="small"
              sx={{ "& .MuiButton-startIcon": { margin: "0px" }, minWidth: 0 }}
            />

            <Stack direction="row" spacing={2}>
              <Button variant="contained" onClick={handleSave} disabled={label === null || saving || loadingAnnotation}>
                {saving ? "Saving..." : "Save Annotation"}
              </Button>
              <Button variant="text" onClick={handleReset} disabled={saving || loadingAnnotation}>
                Reset
              </Button>
            </Stack>

            <Button
              endIcon={<ArrowForwardIcon fontSize="small" />}
              onClick={onNext}
              disabled={nextDisabled}
              variant="outlined"
              size="small"
              sx={{ "& .MuiButton-endIcon": { margin: "0px" }, minWidth: 0 }}
            />
          </Stack>
        </Box>
      </Stack>
    </Paper>
  );
}
