"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Checkbox,
  Alert,
  InputAdornment,
  Tooltip,
} from "@mui/material";
import {
  PersonAddAlt1 as PersonAddIcon,
  DeleteOutline as DeleteIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from "@mui/icons-material";
import { useRouter } from "next/navigation";
import { adminApi, authApi } from "@/lib/api";
import { UserResponse } from "@/lib/types";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";

export default function AdminPage() {
  const router = useRouter();
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const currentUsername = authApi.getUsername();

  // Create user dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newIsAdmin, setNewIsAdmin] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  // Delete dialog
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<UserResponse | null>(null);

  useEffect(() => {
    if (!authApi.isAdmin()) {
      router.replace("/");
      return;
    }
    fetchUsers();
  }, [router]);

  const fetchUsers = async () => {
    try {
      const response = await adminApi.listUsers();
      setUsers(response.data);
      setError(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    setCreateError(null);
    setCreating(true);
    try {
      await adminApi.createUser({
        username: newUsername,
        password: newPassword,
        is_admin: newIsAdmin,
      });
      setCreateOpen(false);
      setNewUsername("");
      setNewPassword("");
      setNewIsAdmin(false);
      setShowPassword(false);
      await fetchUsers();
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || "Failed to create user");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!userToDelete) return;
    try {
      await adminApi.deleteUser(userToDelete.username);
      setDeleteOpen(false);
      setUserToDelete(null);
      await fetchUsers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to delete user");
    }
  };

  const handleCloseCreate = () => {
    setCreateOpen(false);
    setCreateError(null);
    setNewUsername("");
    setNewPassword("");
    setNewIsAdmin(false);
    setShowPassword(false);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={600}>
            User Management
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {users.length} {users.length === 1 ? "user" : "users"} registered
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<PersonAddIcon />}
          onClick={() => setCreateOpen(true)}
        >
          Create User
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper} variant="outlined">
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Username</TableCell>
              <TableCell>Role</TableCell>
              <TableCell align="right">Targets</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="right" sx={{ width: 100 }}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((user, index) => {
              const isCurrentUser = user.username === currentUsername;
              return (
                <TableRow
                  key={user.id}
                  sx={{
                    backgroundColor: index % 2 === 1 ? "rgba(0,0,0,0.015)" : "transparent",
                    "&:hover": { backgroundColor: "rgba(0,0,0,0.04)" },
                    transition: "background-color 0.15s",
                  }}
                >
                  <TableCell>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <Typography variant="body2" fontWeight={600}>
                        {user.username}
                      </Typography>
                      {isCurrentUser && (
                        <Typography variant="caption" color="text.disabled" sx={{ fontStyle: "italic" }}>
                          (you)
                        </Typography>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    {user.is_admin ? (
                      <Chip label="Admin" color="primary" size="small" />
                    ) : (
                      <Chip label="User" variant="outlined" size="small" />
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" color={user.target_count > 0 ? "text.primary" : "text.disabled"}>
                      {user.target_count}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {new Date(user.created_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    {isCurrentUser ? (
                      <Tooltip title="Cannot delete yourself" arrow>
                        <span>
                          <Button
                            size="small"
                            color="inherit"
                            disabled
                            startIcon={<DeleteIcon fontSize="small" />}
                            sx={{ textTransform: "none", color: "text.disabled" }}
                          >
                            Delete
                          </Button>
                        </span>
                      </Tooltip>
                    ) : (
                      <Button
                        size="small"
                        color="error"
                        startIcon={<DeleteIcon fontSize="small" />}
                        onClick={() => {
                          setUserToDelete(user);
                          setDeleteOpen(true);
                        }}
                        sx={{
                          textTransform: "none",
                          opacity: 0.7,
                          "&:hover": { opacity: 1 },
                        }}
                      >
                        Delete
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
            {users.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography color="text.secondary" sx={{ py: 3 }}>
                    No users found
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create User Dialog */}
      <Dialog open={createOpen} onClose={handleCloseCreate} maxWidth="xs" fullWidth>
        <DialogTitle>Create User</DialogTitle>
        <DialogContent>
          {createError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {createError}
            </Alert>
          )}
          <TextField
            autoFocus
            label="Username"
            fullWidth
            margin="normal"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
          />
          <TextField
            label="Password"
            type={showPassword ? "text" : "password"}
            fullWidth
            margin="normal"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            slotProps={{
              input: {
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                      size="small"
                      tabIndex={-1}
                    >
                      {showPassword ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
                    </IconButton>
                  </InputAdornment>
                ),
              },
            }}
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={newIsAdmin}
                onChange={(e) => setNewIsAdmin(e.target.checked)}
              />
            }
            label="Admin privileges"
            sx={{ mt: 1, ml: -0.25 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseCreate}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={creating || !newUsername || !newPassword}
          >
            {creating ? "Creating..." : "Create"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation */}
      <ConfirmDeleteDialog
        open={deleteOpen}
        onClose={() => {
          setDeleteOpen(false);
          setUserToDelete(null);
        }}
        onConfirm={handleDelete}
        title="Delete User"
        itemName={userToDelete?.username}
        description="This will permanently delete this user and cascade-delete all their targets and associated data."
        destructive
      />
    </Box>
  );
}
