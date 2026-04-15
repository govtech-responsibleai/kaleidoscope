"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  CircularProgress,
} from "@mui/material";
import { useParams } from "next/navigation";
import { targetApi } from "@/lib/api";
import { TargetResponse, TargetStats } from "@/lib/types";

interface TargetLayoutProps {
  children: React.ReactNode;
}


export default function TargetLayout({ children }: TargetLayoutProps) {
  const params = useParams();
  const targetId = parseInt(params.id as string);

  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);

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
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={400}>
          <Box component="span" sx={{ color: "text.secondary" }}>Targets</Box>
          <Box component="span" sx={{ color: "text.secondary", mx: 2 }}>/</Box>
          {target.name}
        </Typography>
      </Box>

      {children}
    </Box>
  );
}
