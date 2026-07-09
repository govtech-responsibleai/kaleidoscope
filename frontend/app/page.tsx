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
          gap={2.5}
          sx={{
            gridTemplateColumns: {
              xs: "1fr",
              sm: "repeat(auto-fill, minmax(340px, 1fr))",
            },
          }}
        >
          {targets.map((target) => {
            const theme = getTargetTheme(target.name);
            const monogram = target.name.trim().charAt(0).toUpperCase() || "?";
            const createdDate = new Date(target.created_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            });
            return (
              <Card
                key={target.id}
                onClick={() => handleTargetClick(target.id)}
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  height: "100%",
                  p: 2.5,
                  cursor: "pointer",
                  borderRadius: "12px",
                  border: "1px solid",
                  borderColor: "grey.200",
                  boxShadow: "none",
                  transition: "border-color 0.2s cubic-bezier(0.22, 1, 0.36, 1), background-color 0.2s cubic-bezier(0.22, 1, 0.36, 1)",
                  "&:hover": {
                    borderColor: theme.primary,
                    backgroundColor: theme.light,
                  },
                  "&:hover .target-delete": {
                    opacity: 1,
                  },
                }}
              >
                {/* Header: monogram + name/meta */}
                <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.75, mb: 1.5 }}>
                  <Box
                    aria-hidden
                    sx={{
                      flexShrink: 0,
                      width: 52,
                      height: 52,
                      borderRadius: "12px",
                      background: theme.gradient,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#fff",
                      fontWeight: 700,
                      fontSize: "1.4rem",
                      lineHeight: 1,
                      userSelect: "none",
                    }}
                  >
                    {monogram}
                  </Box>
                  <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                    <Typography
                      variant="h6"
                      component="h2"
                      fontWeight={600}
                      sx={{
                        lineHeight: 1.3,
                        mb: 0.25,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {target.name}
                    </Typography>
                    {(target.agency || target.owner_username) && (
                      <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap", columnGap: 0.75 }}>
                        {target.agency && (
                          <Typography variant="body2" color="text.secondary">
                            {target.agency}
                          </Typography>
                        )}
                        {target.agency && target.owner_username && (
                          <Typography variant="body2" color="text.disabled">·</Typography>
                        )}
                        {target.owner_username && (
                          <Typography variant="body2" color="text.disabled">
                            {target.owner_username}
                          </Typography>
                        )}
                      </Box>
                    )}
                  </Box>
                </Box>

                {target.purpose && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                      lineHeight: 1.5,
                      mb: 2,
                    }}
                  >
                    {target.purpose}
                  </Typography>
                )}

                {/* Footer: date + delete */}
                <Box
                  sx={{
                    mt: "auto",
                    pt: 1.5,
                    borderTop: "1px solid",
                    borderColor: "grey.100",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <Typography variant="caption" color="text.disabled" sx={{ whiteSpace: "nowrap" }}>
                    {createdDate}
                  </Typography>
                  <IconButton
                    size="small"
                    className="target-delete"
                    aria-label={`Delete ${target.name}`}
                    onClick={(e) => handleDeleteClick(e, target)}
                    sx={{
                      opacity: { xs: 1, md: 0.35 },
                      transition: "opacity 0.15s ease, color 0.15s ease",
                      "&:hover": { opacity: 1, color: "error.main" },
                    }}
                  >
                    <IconTrash {...compactActionIconProps} />
                  </IconButton>
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
