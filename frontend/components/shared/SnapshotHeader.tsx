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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
} from "@mui/material";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import DeleteIcon from "@mui/icons-material/Delete";
import { Snapshot } from "@/lib/types";
import CreateSnapshotDialog from "./CreateSnapshotDialog";
import { snapshotApi } from "@/lib/api";

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
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [snapshotToDelete, setSnapshotToDelete] = useState<Snapshot | null>(null);
  const [deleting, setDeleting] = useState(false);

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

  const handleDeleteConfirm = async () => {
    if (!snapshotToDelete) return;

    setDeleting(true);
    try {
      await snapshotApi.delete(snapshotToDelete.id);

      // If the deleted snapshot was selected, select another one
      if (selectedSnapshotId === snapshotToDelete.id) {
        const remaining = sortedSnapshots.filter(s => s.id !== snapshotToDelete.id);
        if (remaining.length > 0) {
          onSelectSnapshot(remaining[0].id);
        } else {
          onSelectSnapshot(0); // No snapshots left
        }
      }

      // Refresh snapshots list
      onSnapshotCreated(snapshotToDelete); // Reuse this callback to trigger refresh
    } catch (error) {
      console.error("Failed to delete snapshot:", error);
      alert("Failed to delete snapshot. Please try again.");
    } finally {
      setDeleting(false);
      setDeleteDialogOpen(false);
      setSnapshotToDelete(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setSnapshotToDelete(null);
  };

  const hasSnapshots = snapshots.length > 0;
  const selectValue =
    selectedSnapshotId && hasSnapshots ? selectedSnapshotId.toString() : "";

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
        sx={{ mb: 3 }}
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
                      <DeleteIcon fontSize="small" />
                    </IconButton>
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
          existingSnapshots={snapshots}
          onClose={() => setCreateDialogOpen(false)}
          onSuccess={handleCreateSuccess}
        />

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Delete Snapshot?</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to delete the snapshot "{snapshotToDelete?.name}"? This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDeleteCancel} disabled={deleting}>
              Cancel
            </Button>
            <Button onClick={handleDeleteConfirm} color="error" variant="contained" disabled={deleting}>
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogActions>
        </Dialog>
    </>
  );
}
