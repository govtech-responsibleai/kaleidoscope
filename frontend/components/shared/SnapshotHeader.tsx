"use client";

import React, { useState } from "react";
import {
  Box,
  FormControl,
  MenuItem,
  Select,
  SelectChangeEvent,
  Stack,
  IconButton,
} from "@mui/material";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { Snapshot } from "@/lib/types";
import CreateSnapshotDialog from "./CreateSnapshotDialog";
import ConfirmDeleteDialog from "./ConfirmDeleteDialog";
import { snapshotApi } from "@/lib/api";
import { actionIconProps, compactActionIconProps } from "@/lib/styles";

interface SnapshotHeaderProps {
  targetId: number;
  snapshots: Snapshot[];
  selectedSnapshotId: number | null;
  onSelectSnapshot: (snapshotId: number | null) => void;
  onSnapshotCreated: (snapshot: Snapshot) => void;
  onSnapshotDeleted?: () => void;
  loading?: boolean;
}

export default function SnapshotHeader({
  targetId,
  snapshots,
  selectedSnapshotId,
  onSelectSnapshot,
  onSnapshotCreated,
  onSnapshotDeleted,
  loading = false,
}: SnapshotHeaderProps) {
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [snapshotToDelete, setSnapshotToDelete] = useState<Snapshot | null>(null);

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

  const handleDeleteClick = (snapshot: Snapshot, event: React.MouseEvent) => {
    event.stopPropagation();
    setSnapshotToDelete(snapshot);
    setDeleteDialogOpen(true);
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setSnapshotToDelete(null);
  };

  const hasSnapshots = snapshots.length > 0;
  const selectValue =
    selectedSnapshotId !== null && hasSnapshots ? selectedSnapshotId.toString() : "";

  // Sort snapshots by created_at descending (most recent first)
  const sortedSnapshots = [...snapshots].sort((a, b) =>
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <>
      <Stack
        direction="row"
        spacing={2}
        alignItems="flex-end"
        justifyContent="space-between"
        mb={2}
      >
        <Box sx={{ width: "100%" }}>
          <FormControl fullWidth size="small">
            <Select
              value={selectValue}
              onChange={handleSnapshotChange}
              displayEmpty
              disabled={loading}
              renderValue={(value) => {
                if (!value) return <em>No snapshots yet</em>;
                const snapshot = snapshots.find(s => s.id.toString() === value);
                return snapshot?.name || "";
              }}
            >
              {hasSnapshots ? (
                sortedSnapshots.map((snapshot) => (
                  <MenuItem
                    key={snapshot.id}
                    value={snapshot.id.toString()}
                    sx={{ display: "flex", justifyContent: "space-between", pr: 1 }}
                  >
                    <span>{snapshot.name}</span>
                    <IconButton
                      size="small"
                      onClick={(e) => handleDeleteClick(snapshot, e)}
                      sx={{ ml: 2, opacity: 0.6, "&:hover": { opacity: 1, color: "error.main" } }}
                    >
                      <IconTrash {...compactActionIconProps} />
                    </IconButton>
                  </MenuItem>
                ))
              ) : (
                <MenuItem value="" disabled>
                  No snapshots yet
                </MenuItem>
              )}
              <MenuItem value="create">
                <IconPlus {...actionIconProps} style={{ marginRight: 8 }} />
                Create snapshot
              </MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Stack>
        <CreateSnapshotDialog
          open={createDialogOpen}
          targetId={targetId}
          existingSnapshots={snapshots}
          onClose={() => setCreateDialogOpen(false)}
          onSuccess={handleCreateSuccess}
        />

        <ConfirmDeleteDialog
          open={deleteDialogOpen}
          onClose={handleDeleteCancel}
          onConfirm={async () => {
            if (!snapshotToDelete) return;
            await snapshotApi.delete(snapshotToDelete.id);

            // Select the most recent remaining snapshot
            if (selectedSnapshotId === snapshotToDelete.id) {
              const remaining = sortedSnapshots.filter(s => s.id !== snapshotToDelete.id);
              if (remaining.length > 0) {
                onSelectSnapshot(remaining[0].id);
              } else {
                onSelectSnapshot(null);
              }
            }

            onSnapshotDeleted?.();
            setSnapshotToDelete(null);
          }}
          title="Delete Snapshot?"
          itemName={snapshotToDelete?.name}
        />
    </>
  );
}
