"use client";

import React, { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { Answer, Annotation } from "@/lib/types";
import { annotationApi } from "@/lib/api";

interface AnnotationFormProps {
  answer: Answer | null;
  onAnnotationSaved: () => void;
  showHelperAlert?: boolean;
  onDismissHelperAlert?: () => void;
}

export default function AnnotationForm({
  answer,
  onAnnotationSaved,
  showHelperAlert = false,
  onDismissHelperAlert,
}: AnnotationFormProps) {
  const [label, setLabel] = useState<boolean | null>(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [existingAnnotation, setExistingAnnotation] = useState<Annotation | null>(null);
  const [loadingAnnotation, setLoadingAnnotation] = useState(false);
  const [showSaveSuccess, setShowSaveSuccess] = useState(false);

  // Fetch existing annotation when answer changes
  useEffect(() => {
    if (!answer) {
      setLabel(null);
      setNotes("");
      setExistingAnnotation(null);
      setShowSaveSuccess(false);
      return;
    }

    const fetchAnnotation = async () => {
      setLoadingAnnotation(true);
      setShowSaveSuccess(false);
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

      // Show success message briefly
      setShowSaveSuccess(true);
      setTimeout(() => {
        setShowSaveSuccess(false);
      }, 3000);
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
    setShowSaveSuccess(false);
  };

  // Check if current form state has changes compared to saved annotation
  const hasUnsavedChanges = () => {
    if (!existingAnnotation) {
      // No existing annotation, so any selection is a change
      return label !== null;
    }

    // Compare current state with existing annotation
    const labelChanged = label !== existingAnnotation.label;
    const notesChanged = (notes.trim() || "") !== (existingAnnotation.notes || "");

    return labelChanged || notesChanged;
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

  // Check if answer is not yet generated or not selected for annotation
  if (!answer.answer_content) {
    return (
      <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <Typography variant="body1" color="text.secondary" align="center">
            Answer generation in progress. Check back later.
          </Typography>
        </Box>
      </Box>
    );
  }

  if (!answer.is_selected_for_annotation) {
    return (
      <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column" }}>
          {/* <Typography variant="body1" color="text.secondary" align="center">
            Add this response to the annotation set to enable labeling.
          </Typography> */}
          <Alert severity="info">
            Add this response to the annotation set to enable labeling.
          </Alert>
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Stack spacing={2} sx={{ flex: 1 }}>
        <Typography variant="h5">Your Annotations</Typography>

        {showHelperAlert && (
          <Alert
            severity="info"
            onClose={onDismissHelperAlert}
          >
            Ready to annotate! Select whether the answer is accurate, then click Save. You may hover over the highlighted text and review the baseline judge's evaluation below for assistance.
          </Alert>
        )}

        <Box>
          <RadioGroup
            row
            value={label === null ? "" : label ? "accurate" : "inaccurate"}
            onChange={(event) => {
              setLabel(event.target.value === "accurate");
              setShowSaveSuccess(false);
            }}
          >
            <FormControlLabel value="accurate" control={<Radio />} label="Accurate" />
            <FormControlLabel value="inaccurate" control={<Radio />} label="Inaccurate" />
          </RadioGroup>

          <TextField
            label="Notes"
            value={notes}
            onChange={(event) => {
              setNotes(event.target.value);
              setShowSaveSuccess(false);
            }}
            multiline
            minRows={3}
            fullWidth
            sx={{ mt: 2 }}
            placeholder="Optional notes about your annotation"
          />

          <Stack direction="row" spacing={2} alignItems="center" justifyContent="center" sx={{ mt: 2 }}>
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={label === null || saving || loadingAnnotation || !hasUnsavedChanges()}
            >
              {saving ? "Saving..." : "Save Annotation"}
            </Button>
            <Button variant="text" onClick={handleReset} disabled={saving || loadingAnnotation}>
              Reset
            </Button>
            {showSaveSuccess && (
              <Typography variant="body2" color="success.main" sx={{ fontWeight: 600 }}>
                Saved
              </Typography>
            )}
          </Stack>
        </Box>
      </Stack>
    </Box>
  );
}
