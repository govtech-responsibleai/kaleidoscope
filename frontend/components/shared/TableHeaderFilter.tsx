"use client";

import React from "react";
import {
  Box,
  Checkbox,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
} from "@mui/material";
import { IconFilter2 } from "@tabler/icons-react";
import { actionIconProps } from "@/lib/iconStyles";
import { compactActionButtonSx } from "@/lib/uiStyles";

export interface FilterOption<T> {
  value: T;
  label: string;
  icon?: React.ReactNode;
}

interface TableHeaderFilterProps<T> {
  label: string;
  options: FilterOption<T>[];
  value: T[];
  onChange: (value: T[]) => void;
  allSelectedLabel?: string;
  renderSelected?: (selected: T[]) => string;
}

export default function TableHeaderFilter<T extends string | number>({
  label,
  options,
  value,
  onChange,
  allSelectedLabel = "All",
}: TableHeaderFilterProps<T>) {
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);

  const isActive = value.length > 0 && value.length < options.length;

  const handleToggle = (optionValue: T) => {
    const newValue = value.includes(optionValue)
      ? value.filter((v) => v !== optionValue)
      : [...value, optionValue];
    onChange(newValue);
  };

  const handleSelectAll = () => {
    if (value.length === options.length) {
      onChange([]);
    } else {
      onChange(options.map((o) => o.value));
    }
  };

  return (
    <>
      <Stack direction="row" alignItems="center" spacing={0.5} justifyContent="flex-start">
        <Box component="span" sx={{ fontWeight: 600 }}>
          {label}
        </Box>
        <IconButton
          size="small"
          onClick={(e) => setAnchorEl(e.currentTarget)}
          sx={{
            ...compactActionButtonSx,
            color: isActive ? "primary.main" : "action.active",
          }}
        >
          <IconFilter2 {...actionIconProps} />
        </IconButton>
      </Stack>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        <MenuItem onClick={handleSelectAll}>
          <Checkbox
            checked={value.length === options.length}
            indeterminate={value.length > 0 && value.length < options.length}
            size="small"
          />
          <ListItemText primary={allSelectedLabel} />
        </MenuItem>

        {options.map((option) => (
          <MenuItem key={String(option.value)} onClick={() => handleToggle(option.value)}>
            <Checkbox checked={value.includes(option.value)} size="small" />
            {option.icon && <ListItemIcon sx={{ minWidth: 32 }}>{option.icon}</ListItemIcon>}
            <ListItemText primary={option.label} />
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
