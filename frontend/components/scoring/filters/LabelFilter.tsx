"use client";

import React from "react";
import {
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Stack,
  Typography,
} from "@mui/material";
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  FilterList as FilterListIcon,
} from "@mui/icons-material";

export type LabelFilterValue = "all" | "accurate" | "inaccurate";

interface LabelFilterProps {
  value: LabelFilterValue;
  onChange: (value: LabelFilterValue) => void;
}

export default function LabelFilter({ value, onChange }: LabelFilterProps) {
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);

  const handleSelect = (newValue: LabelFilterValue) => {
    onChange(newValue);
    setAnchorEl(null);
  };

  return (
    <>
      <Stack direction="row" alignItems="center" spacing={0.5}>
        <Typography variant="body2" fontWeight={600}>
          Label
        </Typography>
        <IconButton
          size="small"
          onClick={(e) => setAnchorEl(e.currentTarget)}
          sx={{
            p: 0.25,
            color: value !== "all" ? "primary.main" : "action.active",
          }}
        >
          <FilterListIcon fontSize="small" />
        </IconButton>
      </Stack>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        <MenuItem selected={value === "all"} onClick={() => handleSelect("all")}>
          All
        </MenuItem>
        <MenuItem selected={value === "accurate"} onClick={() => handleSelect("accurate")}>
          <ListItemIcon>
            <CheckCircleIcon fontSize="small" color="success" />
          </ListItemIcon>
          Accurate
        </MenuItem>
        <MenuItem selected={value === "inaccurate"} onClick={() => handleSelect("inaccurate")}>
          <ListItemIcon>
            <CancelIcon fontSize="small" color="error" />
          </ListItemIcon>
          Inaccurate
        </MenuItem>
      </Menu>
    </>
  );
}
