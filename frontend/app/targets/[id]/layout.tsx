"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  CircularProgress,
  Button,
} from "@mui/material";
import { ArrowForward as ArrowForwardIcon } from "@mui/icons-material";
import { useRouter, useParams, usePathname } from "next/navigation";
import { targetApi } from "@/lib/api";
import { TargetResponse, TargetStats } from "@/lib/types";

interface TargetLayoutProps {
  children: React.ReactNode;
}


export default function TargetLayout({ children }: TargetLayoutProps) {
  const router = useRouter();
  const params = useParams();
  const pathname = usePathname();
  const targetId = parseInt(params.id as string);

  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);

  // Determine active tab based on pathname
  const getActiveTab = () => {
    if (pathname.includes("/annotation")) return "annotation";
    if (pathname.includes("/scoring")) return "scoring";
    if (pathname.includes("/report")) return "report";
    if (pathname.includes("/questions")) return "questions";
    if (pathname.includes("/metrics")) return "metrics";
    return "overview";
  };

  const activeTab = getActiveTab();

  const fetchData = async () => {
    try {
      const [targetRes, statsRes] = await Promise.all([
        targetApi.get(targetId),
        targetApi.getStats(targetId),
      ]);
      setTarget(targetRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error("Failed to fetch target data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [targetId]);

  const getNextStepInfo = () => {
    switch (activeTab) {
      case "overview":
        return null;
      case "questions":
        return { label: "Next: Annotate", path: `/targets/${targetId}/annotation` };
      case "annotation":
        return { label: "Next: Score", path: `/targets/${targetId}/scoring` };
      case "scoring":
        return { label: "Next: View Report", path: `/targets/${targetId}/report` };
      case "report":
        return null;
      default:
        return null;
    }
  };

  const nextStepInfo = getNextStepInfo();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
        <CircularProgress />
      </Box>
    );
  }

  if (!target || !stats) {
    return (
      <Box>
        <Typography variant="h6">Target not found</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={400}>
          <Box component="span" sx={{ color: "text.secondary" }}>Targets</Box>
          <Box component="span" sx={{ color: "text.secondary", mx: 2 }}>/</Box>
          {target.name}
        </Typography>
        {nextStepInfo && (
          <Button
            variant="contained"
            endIcon={<ArrowForwardIcon />}
            onClick={() => router.push(nextStepInfo.path)}
          >
            {nextStepInfo.label}
          </Button>
        )}
      </Box>

      {children}
    </Box>
  );
}
