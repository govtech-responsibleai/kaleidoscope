"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  CircularProgress,
  Tabs,
  Tab,
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
    if (pathname.includes("/annotation")) {
      return "annotation";
    }
    if (pathname.includes("/scoring")) {
      return "scoring";
    }
    if (pathname.includes("/questions")) {
      return "questions";
    }
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

  const handleTabChange = (_event: React.SyntheticEvent, newValue: string) => {
    if (newValue === "overview") {
      router.push(`/targets/${targetId}`);
    } else if (newValue === "questions") {
      router.push(`/targets/${targetId}/questions`);
    } else if (newValue === "annotation") {
      router.push(`/targets/${targetId}/annotation`);
    } else if (newValue === "scoring") {
      router.push(`/targets/${targetId}/scoring`);
    }
  };

  const getNextStepInfo = () => {
    switch (activeTab) {
      case "overview":
        return { label: "Next: Generate Questions", path: `/targets/${targetId}/questions` };
      case "questions":
        return { label: "Next: Annotate", path: `/targets/${targetId}/annotation` };
      case "annotation":
        return { label: "Next: Score", path: `/targets/${targetId}/scoring` };
      case "scoring":
        return null; // Last step
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
      <Typography variant="h4" component="h1" fontWeight={600} gutterBottom mb={1}>
        {target.name}
      </Typography>

      <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 3, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Overview" value="overview" />
          <Tab label="Questions" value="questions" />
          <Tab label="Annotations" value="annotation" />
          <Tab label="Scoring" value="scoring" />
        </Tabs>
        {nextStepInfo && (
          <Button
            variant="contained"
            endIcon={<ArrowForwardIcon />}
            onClick={() => router.push(nextStepInfo.path)}
            sx={{ mb: -1 }}
          >
            {nextStepInfo.label}
          </Button>
        )}
      </Box>

      {children}
    </Box>
  );
}
