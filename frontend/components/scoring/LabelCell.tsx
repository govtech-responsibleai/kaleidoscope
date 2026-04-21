"use client";

import { useEffect, useMemo, useState } from "react";
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
import { IconCheck, IconPencil, IconRestore, IconX } from "@tabler/icons-react";
import axios from "axios";
import { answerApi, getApiErrorMessage } from "@/lib/api";
import { compactActionIconProps } from "@/lib/iconStyles";

export interface LabelCellOption {
  value: string;
  label: string;
  color: ChipProps["color"];
}

interface LabelCellProps {
  answerId: number;
  rubricId: number;
  value: string | null | undefined;
  baselineValue: string | null | undefined;
  displayLabel: string;
  chipColor: ChipProps["color"];
  helperText: string | null;
  options: LabelCellOption[];
  isEditable?: boolean;
  showEditedBadge?: boolean;
  resetTooltip?: string;
  editTooltip?: string;
  onLabelChange?: () => void;
}

const getOptionMeta = (
  options: LabelCellOption[],
  value: string | null | undefined,
  fallbackLabel: string,
  fallbackColor: ChipProps["color"],
): LabelCellOption => {
  if (!value) {
    return { value: "", label: fallbackLabel, color: fallbackColor };
  }
  return options.find((option) => option.value === value) ?? {
    value,
    label: fallbackLabel,
    color: fallbackColor,
  };
};

export default function LabelCell({
  answerId,
  rubricId,
  value,
  baselineValue,
  displayLabel,
  chipColor,
  helperText,
  options,
  isEditable = true,
  showEditedBadge = false,
  resetTooltip = "Reset to judge suggestion",
  editTooltip = "Edit suggested label",
  onLabelChange,
}: LabelCellProps) {
  const currentValue = value ?? "";
  const [isEditMode, setIsEditMode] = useState(false);
  const [selectedValue, setSelectedValue] = useState<string>(currentValue);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setSelectedValue(currentValue);
  }, [currentValue]);

  const selectedOption = useMemo(
    () => getOptionMeta(options, selectedValue || value, displayLabel, chipColor),
    [options, selectedValue, value, displayLabel, chipColor],
  );

  const handleSave = async () => {
    if (!selectedValue) return;
    if (selectedValue === currentValue) {
      setIsEditMode(false);
      return;
    }

    setIsSaving(true);
    try {
      await answerApi.updateLabelOverride(answerId, rubricId, {
        edited_value: selectedValue,
      });
      setIsEditMode(false);
      onLabelChange?.();
    } catch (err) {
      alert(getApiErrorMessage(err, "Failed to save. Please try again."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    setIsSaving(true);
    try {
      await answerApi.deleteLabelOverride(answerId, rubricId);
      setIsEditMode(false);
      onLabelChange?.();
    } catch (err: unknown) {
      const httpStatus = axios.isAxiosError(err) ? err.response?.status : undefined;
      if (httpStatus !== 404) {
        alert(getApiErrorMessage(err, "Failed to reset. Please try again."));
      } else {
        setIsEditMode(false);
        onLabelChange?.();
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setSelectedValue(currentValue);
    setIsEditMode(false);
  };

  if (!isEditable) {
    return <Chip label={displayLabel} color={chipColor} size="small" />;
  }

  if (isEditMode) {
    return (
      <Stack direction="row" alignItems="center" spacing={0.5}>
        <FormControl size="small" sx={{ flex: 1, minWidth: 0 }}>
          <Select
            value={selectedValue}
            onChange={(event) => setSelectedValue(event.target.value)}
            displayEmpty
            renderValue={(selected) => {
              if (!selected) {
                return <Typography variant="body2" color="text.secondary">Select...</Typography>;
              }
              const option = getOptionMeta(options, selected, displayLabel, chipColor);
              return <Chip label={option.label} color={option.color} size="small" />;
            }}
          >
            <MenuItem value="" disabled>
              <Typography variant="body2" color="text.secondary">Select...</Typography>
            </MenuItem>
            {options.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                <Chip label={option.label} color={option.color} size="small" />
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Tooltip title="Save">
          <span>
            <IconButton
              size="small"
              onClick={handleSave}
              disabled={isSaving || !selectedValue}
              color="primary"
              sx={{ p: 0.25 }}
            >
              <IconCheck {...compactActionIconProps} />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title="Cancel">
          <IconButton size="small" onClick={handleCancel} disabled={isSaving} sx={{ p: 0.25 }}>
            <IconX {...compactActionIconProps} />
          </IconButton>
        </Tooltip>
      </Stack>
    );
  }

  return (
    <Stack spacing={0.5}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box display="flex" alignItems="center" gap={0.5}>
          <Chip label={displayLabel} color={chipColor} size="small" />
          {showEditedBadge && (
            <Typography color="text.secondary" sx={{ fontStyle: "italic", fontSize: "0.7rem" }}>
              (edited)
            </Typography>
          )}
        </Box>
        <Box display="flex" alignItems="center" gap={0.5}>
          {showEditedBadge && baselineValue && (
            <Tooltip title={resetTooltip}>
              <IconButton size="small" onClick={handleReset} disabled={isSaving} sx={{ p: 0.25 }}>
                <IconRestore {...compactActionIconProps} />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title={editTooltip}>
            <IconButton size="small" onClick={() => setIsEditMode(true)} sx={{ p: 0.25 }}>
              <IconPencil {...compactActionIconProps} />
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
