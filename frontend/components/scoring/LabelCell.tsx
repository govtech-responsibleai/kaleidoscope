"use client";

import { useState } from "react";
import {
  Box,
  Chip,
  ChipProps,
  FormControl,
  IconButton,
  MenuItem,
  Select,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import EditIcon from "@mui/icons-material/Edit";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import { AggregatedAccuracy } from "@/lib/types";
import { answerApi } from "@/lib/api";

interface LabelCellProps {
  answerId: number;
  aggregatedAccuracy: AggregatedAccuracy | undefined;
  chipLabel: string;
  chipColor: ChipProps["color"];
  helperText: string | null;
  onLabelChange?: () => void;
}

export default function LabelCell({
  answerId,
  aggregatedAccuracy,
  chipLabel,
  chipColor,
  helperText,
  onLabelChange,
}: LabelCellProps) {
  const [isEditMode, setIsEditMode] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState<string>(
    aggregatedAccuracy?.label === true
      ? "accurate"
      : aggregatedAccuracy?.label === false
      ? "inaccurate"
      : ""
  );
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    if (!selectedLabel) return;

    // Check if label actually changed
    const currentLabel = aggregatedAccuracy?.label;
    const newLabel = selectedLabel === "accurate";
    if (currentLabel === newLabel) {
      setIsEditMode(false);
      return;
    }

    setIsSaving(true);
    try {
      await answerApi.updateLabelOverride(answerId, {
        edited_label: newLabel,
      });
      setIsEditMode(false);
      onLabelChange?.();
    } catch (err) {
      console.error("Failed to save label:", err);
      alert("Failed to save. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    setIsSaving(true);
    try {
      await answerApi.deleteLabelOverride(answerId);
      setIsEditMode(false);
      onLabelChange?.();
    } catch (err: any) {
      // 404 is fine - means no override existed
      if (err?.response?.status !== 404) {
        console.error("Failed to reset label:", err);
        alert("Failed to reset. Please try again.");
      } else {
        setIsEditMode(false);
        onLabelChange?.();
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setSelectedLabel(
      aggregatedAccuracy?.label === true
        ? "accurate"
        : aggregatedAccuracy?.label === false
        ? "inaccurate"
        : ""
    );
    setIsEditMode(false);
  };

  if (isEditMode) {
    return (
      <Stack direction="row" alignItems="center" spacing={0.5}>
        <FormControl size="small" sx={{ flex: 1 }}>
          <Select
            value={selectedLabel}
            onChange={(e) => setSelectedLabel(e.target.value)}
            displayEmpty
            renderValue={(value) => {
              if (!value) return <Typography variant="body2" color="text.secondary">Select...</Typography>;
              return (
                <Chip
                  label={value === "accurate" ? "Accurate" : "Inaccurate"}
                  color={value === "accurate" ? "success" : "error"}
                  size="small"
                />
              );
            }}
          >
            <MenuItem value="" disabled>
              <Typography variant="body2" color="text.secondary">Select...</Typography>
            </MenuItem>
            <MenuItem value="accurate">
              <Chip label="Accurate" color="success" size="small" />
            </MenuItem>
            <MenuItem value="inaccurate">
              <Chip label="Inaccurate" color="error" size="small" />
            </MenuItem>
          </Select>
        </FormControl>
        <Tooltip title="Save">
          <span>
            <IconButton
              size="small"
              onClick={handleSave}
              disabled={isSaving || !selectedLabel}
              color="primary"
              sx={{ p: 0.25 }}
            >
              <CheckIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title="Cancel">
          <IconButton
            size="small"
            onClick={handleCancel}
            disabled={isSaving}
            sx={{ p: 0.25 }}
          >
            <CloseIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
      </Stack>
    );
  }

  return (
    <Stack spacing={0.5}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        {/* Left: Chip and edited text */}
        <Box display="flex" alignItems="center" gap={0.5}>
          <Chip label={chipLabel} color={chipColor} size="small" />
          {aggregatedAccuracy?.is_edited && (
            <Typography
              color="text.secondary"
              sx={{ fontStyle: "italic", fontSize: "0.7rem" }}
            >
              (edited)
            </Typography>
          )}
        </Box>

        {/* Right: Edit and reset icons */}
        <Box display="flex" alignItems="center" gap={0.5}>
          {aggregatedAccuracy?.is_edited && (
            <Tooltip title="Reset to evaluator suggestion">
              <IconButton
                size="small"
                onClick={handleReset}
                disabled={isSaving}
                sx={{ p: 0.25 }}
              >
                <RestartAltIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title="Edit suggested label">
            <IconButton
              size="small"
              onClick={() => setIsEditMode(true)}
              sx={{ p: 0.25 }}
            >
              <EditIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>
      </Stack>
      {helperText && (
        <Typography variant="caption" color="text.secondary">
          {helperText}
        </Typography>
      )}
    </Stack>
  );
}
