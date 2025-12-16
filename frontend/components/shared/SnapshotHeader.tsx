"use client";

import React, { useState } from "react";
import {
  Box,
  FormControl,
  MenuItem,
  Select,
  SelectChangeEvent,
  Stack,
} from "@mui/material";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import { Snapshot } from "@/lib/types";
import CreateSnapshotDialog from "./CreateSnapshotDialog";

interface SnapshotHeaderProps {
  targetId: number;
  snapshots: Snapshot[];
  selectedSnapshotId: number | null;
  onSelectSnapshot: (snapshotId: number) => void;
  onSnapshotCreated: (snapshot: Snapshot) => void;
  loading?: boolean;
}

export default function SnapshotHeader({
  targetId,
  snapshots,
  selectedSnapshotId,
  onSelectSnapshot,
  onSnapshotCreated,
  loading = false,
}: SnapshotHeaderProps) {
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const handleSnapshotChange = (event: SelectChangeEvent<string>) => {
    const value = event.target.value;

    // Check if "create" option was selected
    if (value === "create") {
      setCreateDialogOpen(true);
      return;
    }

    // Otherwise, treat as snapshot ID
    onSelectSnapshot(Number(value));
  };

  const handleCreateSuccess = (snapshot: Snapshot) => {
    setCreateDialogOpen(false);
    onSelectSnapshot(snapshot.id);
    onSnapshotCreated(snapshot);
  };

  const hasSnapshots = snapshots.length > 0;
  const selectValue =
    selectedSnapshotId && hasSnapshots ? selectedSnapshotId.toString() : "";

  return (
    <>
      <Stack
        direction="row"
        spacing={2}
        alignItems="flex-end"
        justifyContent="space-between"
        sx={{ mb: 3 }}
      >
        <Box sx={{ width: "100%" }}>
          <FormControl fullWidth size="small">
            <Select
              value={selectValue}
              onChange={handleSnapshotChange}
              displayEmpty
              disabled={loading}
            >
              {hasSnapshots ? (
                snapshots.map((snapshot) => (
                  <MenuItem key={snapshot.id} value={snapshot.id.toString()}>
                    {snapshot.name}
                  </MenuItem>
                ))
              ) : (
                <MenuItem value="" disabled>
                  No snapshots yet
                </MenuItem>
              )}
              <MenuItem value="create">
                <AddCircleOutlineIcon fontSize="small" sx={{ mr: 1 }} />
                Create snapshot
              </MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Stack>
        <CreateSnapshotDialog
          open={createDialogOpen}
          targetId={targetId}
          onClose={() => setCreateDialogOpen(false)}
          onSuccess={handleCreateSuccess}
        />
    </>
  );
}
