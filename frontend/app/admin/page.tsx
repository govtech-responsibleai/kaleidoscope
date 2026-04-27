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
  IconCheck,
  IconCopy,
  IconDice5,
  IconEye,
  IconEyeOff,
  IconTrash,
  IconUserPlus,
} from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import { adminApi, authApi, getApiErrorMessage } from "@/lib/api";
import { UserResponse } from "@/lib/types";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import { actionIconProps, compactActionIconProps, statusIconProps } from "@/lib/styles";

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
  const [createdCreds, setCreatedCreds] = useState<{ username: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const generatePassword = () => {
    const chars = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*";
    const password = Array.from(crypto.getRandomValues(new Uint8Array(14)))
      .map((b) => chars[b % chars.length])
      .join("");
    setNewPassword(password);
    setShowPassword(true);
  };

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
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to load users"));
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
      setCreatedCreds({ username: newUsername, password: newPassword });
      await fetchUsers();
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create user"));
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
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to delete user"));
    }
  };

  const handleCloseCreate = () => {
    setCreateOpen(false);
    setCreateError(null);
    setNewUsername("");
    setNewPassword("");
    setNewIsAdmin(false);
    setShowPassword(false);
    setCreatedCreds(null);
    setCopied(false);
  };

  const handleCopyCreds = async () => {
    if (!createdCreds) return;
    const text = `Username: ${createdCreds.username}\nPassword: ${createdCreds.password}`;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
          startIcon={<IconUserPlus {...actionIconProps} />}
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
                            startIcon={<IconTrash {...compactActionIconProps} />}
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
                        startIcon={<IconTrash {...compactActionIconProps} />}
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
        <DialogTitle>{createdCreds ? "User Created" : "Create User"}</DialogTitle>
        <DialogContent>
          {createdCreds ? (
            <Box>
              <Alert severity="success" sx={{ mb: 2 }}>
                User <strong>{createdCreds.username}</strong> created successfully.
              </Alert>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Copy these credentials now — the password cannot be retrieved later.
              </Typography>
              <Paper
                variant="outlined"
                sx={{ p: 2, fontFamily: "monospace", fontSize: 14, bgcolor: "grey.50" }}
              >
                <Box>Username: {createdCreds.username}</Box>
                <Box>Password: {createdCreds.password}</Box>
              </Paper>
              <Button
                startIcon={copied ? <IconCheck {...statusIconProps} /> : <IconCopy {...actionIconProps} />}
                onClick={handleCopyCreds}
                sx={{ mt: 1.5 }}
                color={copied ? "success" : "primary"}
              >
                {copied ? "Copied!" : "Copy credentials"}
              </Button>
            </Box>
          ) : (
            <>
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
                        <Tooltip title="Generate password" arrow>
                          <IconButton
                            onClick={generatePassword}
                            edge="end"
                            size="small"
                            tabIndex={-1}
                          >
                            <IconDice5 {...compactActionIconProps} />
                          </IconButton>
                        </Tooltip>
                        <IconButton
                          onClick={() => setShowPassword(!showPassword)}
                          edge="end"
                          size="small"
                          tabIndex={-1}
                        >
                          {showPassword ? (
                            <IconEyeOff {...compactActionIconProps} />
                          ) : (
                            <IconEye {...compactActionIconProps} />
                          )}
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
            </>
          )}
        </DialogContent>
        <DialogActions>
          {createdCreds ? (
            <Button variant="contained" onClick={handleCloseCreate}>
              Done
            </Button>
          ) : (
            <>
              <Button onClick={handleCloseCreate}>Cancel</Button>
              <Button
                variant="contained"
                onClick={handleCreate}
                disabled={creating || !newUsername || !newPassword}
              >
                {creating ? "Creating..." : "Create"}
              </Button>
            </>
          )}
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
