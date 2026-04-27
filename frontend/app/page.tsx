"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Box,
  Typography,
  Button,
  Card,
  CircularProgress,
  IconButton,
  Tooltip,
} from "@mui/material";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import { providerApi, targetApi } from "@/lib/api";
import { ProviderSetupResponse, TargetResponse } from "@/lib/types";
import CreateTargetModal from "@/components/overview/CreateTargetModal";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import { actionIconProps, compactActionIconProps } from "@/lib/styles";

interface TargetTheme {
  primary: string;
  secondary: string;
  gradient: string;
  light: string;
}

function hashString(str: string): number {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

function hslToHex(h: number, s: number, l: number): string {
  const a = s / 100;
  const b = l / 100;
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = b - a * Math.min(b, 1 - b) * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function getTargetTheme(name: string): TargetTheme {
  const hash = hashString(name.toLowerCase().trim());
  const hue = 180 + (hash % 150);
  const primary = hslToHex(hue, 65, 45);
  const secondary = hslToHex(hue, 60, 60);
  const gradientStart = hslToHex(hue, 70, 38);
  const gradientEnd = hslToHex(hue, 55, 58);
  const light = hslToHex(hue, 40, 96);

  return {
    primary,
    secondary,
    gradient: `linear-gradient(135deg, ${gradientStart} 0%, ${gradientEnd} 100%)`,
    light,
  };
}

export default function Home() {
  const router = useRouter();
  const [targets, setTargets] = useState<TargetResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [targetToDelete, setTargetToDelete] = useState<TargetResponse | null>(null);
  const [providerSetup, setProviderSetup] = useState<ProviderSetupResponse | null>(null);

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

  useEffect(() => {
    let isMounted = true;
    providerApi.getSetup()
      .then((response) => {
        if (isMounted) {
          setProviderSetup(response.data);
        }
      })
      .catch((error) => {
        console.error("Failed to load provider setup:", error);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleTargetClick = (targetId: number) => {
    router.push(`/targets/${targetId}`);
  };

  const handleDeleteClick = (event: React.MouseEvent, target: TargetResponse) => {
    event.stopPropagation(); // Prevent card click
    setTargetToDelete(target);
    setDeleteDialogOpen(true);
  };

  const hasValidModels = (providerSetup?.valid_models.length || 0) > 0;
  const shouldDisableNewTarget = providerSetup !== null && !hasValidModels;
  const newTargetTooltip = "Add an API key on the Providers page first.";


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
        <Tooltip disableHoverListener={!shouldDisableNewTarget} title={newTargetTooltip}>
          <span tabIndex={shouldDisableNewTarget ? 0 : -1}>
            <Button
              disabled={shouldDisableNewTarget}
              variant="contained"
              startIcon={<IconPlus {...actionIconProps} />}
              onClick={() => setCreateModalOpen(true)}
            >
              New Target
            </Button>
          </span>
        </Tooltip>
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
          <Tooltip disableHoverListener={!shouldDisableNewTarget} title={newTargetTooltip}>
            <span tabIndex={shouldDisableNewTarget ? 0 : -1}>
              <Button
                disabled={shouldDisableNewTarget}
                variant="contained"
                size="large"
                onClick={() => setCreateModalOpen(true)}
              >
                Get Started
              </Button>
            </span>
          </Tooltip>
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
                  position: "relative",
                  borderRadius: "10px",
                  border: "1px solid #E0E0E0",
                  overflow: "hidden",
                  boxShadow: "none",
                  "&::before": {
                    content: '""',
                    position: "absolute",
                    zIndex: 2,
                    inset: 0,
                    borderStyle: "solid",
                    borderWidth: "1px",
                    borderColor: theme.primary,
                    borderRadius: "10px",
                    opacity: 0,
                    transition: "opacity 0.2s ease",
                    pointerEvents: "none",
                  },
                  "&:hover::before": {
                    opacity: 1,
                    transition: "opacity 0.75s ease",
                  },
                  "&::after": {
                    content: '""',
                    position: "absolute",
                    zIndex: 1,
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: "50%",
                    background: `linear-gradient(to top, ${theme.light}, transparent)`,
                    opacity: 0,
                    transition: "opacity 0.25s ease",
                    pointerEvents: "none",
                  },
                  "&:hover::after": {
                    opacity: 0.5,
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
