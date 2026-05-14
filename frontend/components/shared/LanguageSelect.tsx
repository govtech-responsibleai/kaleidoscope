"use client";

import React, { useState } from "react";
import {
  Box,
  Button,
  Checkbox,
  Chip,
  ListSubheader,
  MenuItem,
  TextField,
  Typography,
} from "@mui/material";
import type { SxProps, Theme } from "@mui/material/styles";

/** Globally representative languages, surfaced first for quick access. */
const PRIORITY_LANGUAGES = [
  "English",
  "Mandarin Chinese",
  "Hindi",
  "Spanish",
  "Arabic",
  "French",
  "Portuguese",
];

/**
 * The remaining widely-used languages that current LLMs handle well, listed
 * alphabetically after the priority languages.
 */
const ADDITIONAL_LANGUAGES = [
  "Afrikaans",
  "Amharic",
  "Bengali",
  "Bulgarian",
  "Burmese",
  "Catalan",
  "Croatian",
  "Czech",
  "Danish",
  "Dutch",
  "Estonian",
  "Filipino (Tagalog)",
  "Finnish",
  "German",
  "Greek",
  "Gujarati",
  "Hausa",
  "Hebrew",
  "Hungarian",
  "Icelandic",
  "Indonesian",
  "Italian",
  "Japanese",
  "Kannada",
  "Khmer",
  "Korean",
  "Lao",
  "Latvian",
  "Lithuanian",
  "Malay",
  "Malayalam",
  "Marathi",
  "Nepali",
  "Norwegian",
  "Persian (Farsi)",
  "Polish",
  "Punjabi",
  "Romanian",
  "Russian",
  "Serbian",
  "Sinhala",
  "Slovak",
  "Swahili",
  "Swedish",
  "Tamil",
  "Telugu",
  "Thai",
  "Turkish",
  "Ukrainian",
  "Urdu",
  "Vietnamese",
  "Yoruba",
  "Zulu",
];

/** Full list of selectable languages — priority languages first, then alphabetical. */
export const LANGUAGES = [...PRIORITY_LANGUAGES, ...ADDITIONAL_LANGUAGES];

const EMPTY_VALUE = "__none__";

interface CommonProps {
  label?: string;
  size?: "small" | "medium";
  disabled?: boolean;
  helperText?: string;
  sx?: SxProps<Theme>;
  testId?: string;
}

interface SingleProps extends CommonProps {
  multiple?: false;
  value: string;
  onChange: (value: string) => void;
  /** When true, shows a "(none)" option so the language can be left unset. */
  allowEmpty?: boolean;
  emptyLabel?: string;
}

interface MultiProps extends CommonProps {
  multiple: true;
  value: string[];
  onChange: (value: string[]) => void;
}

export type LanguageSelectProps = SingleProps | MultiProps;

const MENU_PROPS = { PaperProps: { sx: { maxHeight: 360 } } };

/**
 * Language picker backed by a single scrollable list of ~60 well-supported
 * languages (priority languages first, then alphabetical).
 *
 * - Single mode: `value`/`onChange` are plain strings (used by the judge dialog);
 *   the menu closes automatically on selection.
 * - Multi mode: `value`/`onChange` are string arrays rendered as chips (used by
 *   the generate-evals modal). Because a multi-select stays open between picks,
 *   the menu carries a sticky footer with an explicit "Done" button to dismiss it.
 */
export default function LanguageSelect(props: LanguageSelectProps) {
  const {
    label = "Language",
    size = "small",
    disabled = false,
    helperText,
    sx,
    testId,
  } = props;

  // Controlled open state so the sticky-footer "Done" button can close the menu.
  const [open, setOpen] = useState(false);

  if (props.multiple) {
    const { value, onChange } = props;
    // Keep any already-selected value not in the canonical list still selectable.
    const extras = value.filter((v) => !LANGUAGES.includes(v));
    const options = [...extras, ...LANGUAGES];

    return (
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1, ...sx }}>
        <TextField
          select
          label={label}
          size={size}
          disabled={disabled}
          helperText={helperText}
          value={value}
          SelectProps={{
            multiple: true,
            open,
            onOpen: () => setOpen(true),
            onClose: () => setOpen(false),
            MenuProps: MENU_PROPS,
            renderValue: (selected) => (
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                {(selected as string[]).map((lang) => (
                  <Chip
                    key={lang}
                    label={lang}
                    size="small"
                    onDelete={() => onChange(value.filter((v) => v !== lang))}
                    onMouseDown={(e) => e.stopPropagation()}
                  />
                ))}
              </Box>
            ),
          }}
          onChange={(e) => onChange(e.target.value as unknown as string[])}
          inputProps={testId ? { "data-testid": testId } : undefined}
        >
          {options.map((lang) => (
            <MenuItem key={lang} value={lang}>
              <Checkbox checked={value.includes(lang)} size="small" />
              {lang}
            </MenuItem>
          ))}
          {/* Sticky footer: ListSubheader is ignored by Select's option logic,
              so it's a safe place to host the dismiss affordance. */}
          <ListSubheader
            onClick={(e) => e.stopPropagation()}
            sx={{
              position: "sticky",
              bottom: 0,
              top: "auto",
              bgcolor: "background.paper",
              borderTop: "1px solid",
              borderColor: "divider",
              lineHeight: 1.5,
              py: 0.5,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {value.length === 0 ? "None selected" : `${value.length} selected`}
              </Typography>
              <Button size="small" onClick={() => setOpen(false)}>
                Done
              </Button>
            </Box>
          </ListSubheader>
        </TextField>
      </Box>
    );
  }

  // Single-select mode — the menu closes automatically on selection.
  const { value, onChange, allowEmpty = false, emptyLabel = "(none)" } = props;
  const options = value && !LANGUAGES.includes(value) ? [value, ...LANGUAGES] : LANGUAGES;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1, ...sx }}>
      <TextField
        select
        label={label}
        size={size}
        disabled={disabled}
        helperText={helperText}
        value={value || (allowEmpty ? EMPTY_VALUE : "")}
        onChange={(e) => {
          const next = e.target.value;
          onChange(next === EMPTY_VALUE ? "" : next);
        }}
        SelectProps={{ MenuProps: MENU_PROPS }}
        inputProps={testId ? { "data-testid": testId } : undefined}
      >
        {allowEmpty && <MenuItem value={EMPTY_VALUE}>{emptyLabel}</MenuItem>}
        {options.map((lang) => (
          <MenuItem key={lang} value={lang}>
            {lang}
          </MenuItem>
        ))}
      </TextField>
    </Box>
  );
}
