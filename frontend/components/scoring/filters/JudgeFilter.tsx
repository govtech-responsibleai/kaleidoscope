"use client";

import React from "react";
import {
  Button,
  Checkbox,
  ListItemText,
  Menu,
  MenuItem,
} from "@mui/material";
import { IconFilter2 } from "@tabler/icons-react";
import { actionIconProps } from "@/lib/iconStyles";
import { JudgeConfig } from "@/lib/types";

interface JudgeFilterProps {
  judges: JudgeConfig[];
  selectedJudgeIds: Set<number>;
  onSelectionChange: (selectedIds: Set<number>) => void;
}

export default function JudgeFilter({
  judges,
  selectedJudgeIds,
  onSelectionChange,
}: JudgeFilterProps) {
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);

  const isFilterActive = selectedJudgeIds.size < judges.length;

  const handleToggle = (judgeId: number) => {
    const next = new Set(selectedJudgeIds);
    if (next.has(judgeId)) {
      next.delete(judgeId);
    } else {
      next.add(judgeId);
    }
    onSelectionChange(next);
  };

  return (
    <>
      <Button
        variant="outlined"
        endIcon={<IconFilter2 {...actionIconProps} />}
        onClick={(e) => setAnchorEl(e.currentTarget)}
        color={isFilterActive ? "primary" : "inherit"}
        disableRipple
        size="small"
        sx={{ px: 1.5, height: "40px", fontWeight: 400, borderColor: "rgba(0, 0, 0, 0.2)", }}
      >
        Judges ({selectedJudgeIds.size}/{judges.length})
      </Button>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        {judges.map((judge) => (
          <MenuItem
            key={judge.id}
            selected={selectedJudgeIds.has(judge.id)}
            onClick={() => handleToggle(judge.id)}
          >
            <Checkbox checked={selectedJudgeIds.has(judge.id)} />
            <ListItemText primary={judge.name} />
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
