"use client";

import { useEffect, useState } from "react";
import {
  Alert,
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
import { alpha } from "@mui/material/styles";
import { IconCheck, IconPencil, IconRestore, IconX } from "@tabler/icons-react";
import axios from "axios";
import { answerApi, getApiErrorMessage } from "@/lib/api";
import { compactActionIconProps } from "@/lib/styles";

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

const chipColorToCss: Record<string, string> = {
  success: "#2e7d32",
  error: "#d32f2f",
  primary: "#1d2766",
  secondary: "#dc004e",
  warning: "#ed6c02",
  info: "#0288d1",
  default: "#9e9e9e",
};

const resolveColor = (color: ChipProps["color"]): string =>
  chipColorToCss[color ?? "default"] ?? chipColorToCss.default;

const labelSelectMenuProps = {
  PaperProps: {
    sx: {
      boxShadow: "0 4px 16px rgba(0, 0, 0, 0.06)",
    },
  },
  MenuListProps: {
    sx: { py: 0.5, px: 0.5 },
  },
};

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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setSelectedValue(currentValue);
  }, [currentValue]);

  useEffect(() => {
    setSelectedValue(currentValue);
    setIsEditMode(false);
    setErrorMessage(null);
  }, [rubricId, currentValue]);

  const handleSave = async () => {
    if (!selectedValue) return;
    if (selectedValue === currentValue) {
      setErrorMessage(null);
      setIsEditMode(false);
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    try {
      await answerApi.updateLabelOverride(answerId, rubricId, {
        edited_value: selectedValue,
      });
      setIsEditMode(false);
      onLabelChange?.();
    } catch (err) {
      setErrorMessage(getApiErrorMessage(err, "Failed to save. Please try again."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    setIsSaving(true);
    setErrorMessage(null);
    try {
      await answerApi.deleteLabelOverride(answerId, rubricId);
      setIsEditMode(false);
      onLabelChange?.();
    } catch (err: unknown) {
      const httpStatus = axios.isAxiosError(err) ? err.response?.status : undefined;
      if (httpStatus !== 404) {
        setErrorMessage(getApiErrorMessage(err, "Failed to reset. Please try again."));
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
    setErrorMessage(null);
    setIsEditMode(false);
  };

  if (!isEditable) {
    return <Chip label={displayLabel} color={chipColor} size="small" />;
  }

  if (isEditMode) {
    return (
      <Stack spacing={0.5}>
        <Stack direction="row" alignItems="center" spacing={0.5}>
          <FormControl size="small" sx={{ flex: 1, minWidth: 0 }}>
            <Select
              value={selectedValue}
              onChange={(event) => setSelectedValue(event.target.value)}
              MenuProps={labelSelectMenuProps}
              renderValue={(selected) => {
                const option = getOptionMeta(options, selected, displayLabel, chipColor);
                const css = resolveColor(option.color);
                return (
                  <Box display="flex" alignItems="center" gap={0.75} overflow="hidden" height="100%">
                    <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: css, flexShrink: 0 }} />
                    <Typography fontSize={12} fontWeight={600} noWrap>{option.label}</Typography>
                  </Box>
                );
              }}
            >
              {options.map((option) => {
                const css = resolveColor(option.color);
                return (
                  <MenuItem
                    key={option.value}
                    value={option.value}
                    sx={{
                      py: 0.5,
                      px: 1,
                      minHeight: "unset",
                      "&:hover": { bgcolor: alpha(css, 0.08) },
                      "&.Mui-selected": { bgcolor: alpha(css, 0.12) },
                      "&.Mui-selected:hover": { bgcolor: alpha(css, 0.12) },
                    }}
                  >
                    <Box display="flex" alignItems="center" gap={0.75}>
                      <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: css, flexShrink: 0 }} />
                      <Typography fontSize={12} fontWeight={600} lineHeight={1}>{option.label}</Typography>
                    </Box>
                  </MenuItem>
                );
              })}
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
        {errorMessage && (
          <Alert severity="error" sx={{ py: 0, "& .MuiAlert-message": { py: 0.25 } }}>
            {errorMessage}
          </Alert>
        )}
      </Stack>
    );
  }

  const readOption = getOptionMeta(options, selectedValue, displayLabel, chipColor);

  return (
    <Stack spacing={0.5}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box display="flex" alignItems="center" gap={0.5}>
          <Chip label={readOption.label} color={readOption.color} size="small" />
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
            <IconButton
              size="small"
              onClick={() => {
                setErrorMessage(null);
                setIsEditMode(true);
              }}
              sx={{ p: 0.25 }}
            >
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
      {errorMessage && (
        <Alert severity="error" sx={{ py: 0, "& .MuiAlert-message": { py: 0.25 } }}>
          {errorMessage}
        </Alert>
      )}
    </Stack>
  );
}
