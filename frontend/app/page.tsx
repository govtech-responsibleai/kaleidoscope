"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Box,
  Typography,
  Button,
  Card,
  CircularProgress,
  IconButton,
} from "@mui/material";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import { targetApi } from "@/lib/api";
import { TargetResponse } from "@/lib/types";
import CreateTargetModal from "@/components/overview/CreateTargetModal";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import { getTargetTheme } from "@/lib/targetTheme";
import { actionIconProps, compactActionIconProps } from "@/lib/iconStyles";

export default function Home() {
  const router = useRouter();
  const [targets, setTargets] = useState<TargetResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [targetToDelete, setTargetToDelete] = useState<TargetResponse | null>(null);

  const fetchTargets = useCallback(async () => {
    try {
      const response = await targetApi.list();
      setTargets(response.data);
      setLoading(false);
    } catch (error: unknown) {
      if (
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        typeof (error as { response?: { status?: number } }).response?.status === "number" &&
        (error as { response?: { status?: number } }).response?.status === 401
      ) {
        return; // interceptor handles redirect, keep spinner
      }
      console.error("Failed to fetch targets:", error);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchTargets();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchTargets]);

  const handleTargetClick = (targetId: number) => {
    router.push(`/targets/${targetId}`);
  };

  const handleDeleteClick = (event: React.MouseEvent, target: TargetResponse) => {
    event.stopPropagation(); // Prevent card click
    setTargetToDelete(target);
    setDeleteDialogOpen(true);
  };


  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="50vh"
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={4}
      >
        <Typography variant="h4" component="h1" fontWeight={600}>
          Target Applications
        </Typography>
        <Button
          variant="contained"
          startIcon={<IconPlus {...actionIconProps} />}
          onClick={() => setCreateModalOpen(true)}
        >
          New Target
        </Button>
      </Box>

      {targets.length === 0 ? (
        <Box
          display="flex"
          flexDirection="column"
          alignItems="center"
          justifyContent="center"
          minHeight="40vh"
          gap={2}
        >
          <Typography variant="h6" color="text.secondary">
            No target applications found
          </Typography>
          <Button
            variant="contained"
            size="large"
            onClick={() => setCreateModalOpen(true)}
          >
            Get Started
          </Button>
        </Box>
      ) : (
        <Box
          display="grid"
          gap={3}
          sx={{
            gridTemplateColumns: {
              xs: "repeat(1, minmax(0, 1fr))",
              sm: "repeat(2, minmax(0, 1fr))",
              md: "repeat(4, minmax(0, 1fr))",
            },
          }}
        >
          {targets.map((target) => {
            const theme = getTargetTheme(target.name);
            const createdDate = new Date(target.created_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            });
            return (
              <Card
                key={target.id}
                sx={{
                  minWidth: 0,
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  cursor: "pointer",
                  borderRadius: "10px",
                  overflow: "hidden",
                  transition: "transform 0.2s, box-shadow 0.2s",
                  "&:hover": {
                    transform: "translateY(-2px)",
                    boxShadow: 3,
                  },
                }}
                onClick={() => handleTargetClick(target.id)}
              >
                {/* Gradient accent line */}
                <Box
                  sx={{
                    height: 4,
                    background: theme.gradient,
                  }}
                />

                {/* Card body */}
                <Box sx={{ p: 2, flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                  <Typography
                    variant="h6"
                    component="h2"
                    fontWeight={600}
                    sx={{
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      mb: 0.25,
                    }}
                  >
                    {target.name}
                  </Typography>

                  {(target.agency || target.owner_username) && (
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.5, minWidth: 0 }}>
                      {target.agency && (
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {target.agency}
                        </Typography>
                      )}
                      {target.agency && target.owner_username && (
                        <Typography variant="body2" color="text.disabled">·</Typography>
                      )}
                      {target.owner_username && (
                        <Typography
                          variant="caption"
                          color="text.disabled"
                          sx={{ whiteSpace: "nowrap" }}
                        >
                          {target.owner_username}
                        </Typography>
                      )}
                    </Box>
                  )}

                  {target.purpose && (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                        mb: 1,
                      }}
                    >
                      {target.purpose}
                    </Typography>
                  )}

                  {/* Footer row */}
                  <Box
                    sx={{
                      mt: "auto",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <Typography variant="caption" color="text.disabled">
                      {createdDate}
                    </Typography>
                    <IconButton
                      size="small"
                      onClick={(e) => handleDeleteClick(e, target)}
                      sx={{
                        opacity: 0.5,
                        "&:hover": { opacity: 1, color: "error.main" },
                      }}
                    >
                      <IconTrash {...compactActionIconProps} />
                    </IconButton>
                  </Box>
                </Box>
              </Card>
            );
          })}
        </Box>
      )}

      <CreateTargetModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={fetchTargets}
      />

      <ConfirmDeleteDialog
        open={deleteDialogOpen}
        onClose={() => {
          setDeleteDialogOpen(false);
          setTargetToDelete(null);
        }}
        onConfirm={async () => {
          if (!targetToDelete) return;
          await targetApi.delete(targetToDelete.id);
          await fetchTargets();
          setTargetToDelete(null);
        }}
        title="Delete Target Application"
        itemName={targetToDelete?.name}
        description="This will permanently delete all associated data including personas, questions, knowledge base documents, and statistics."
        destructive
      />
    </Box>
  );
}
