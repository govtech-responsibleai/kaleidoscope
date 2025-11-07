"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  Grid,
  CircularProgress,
} from "@mui/material";
import { Add as AddIcon } from "@mui/icons-material";
import { useRouter } from "next/navigation";
import { targetApi } from "@/lib/api";
import { TargetResponse } from "@/lib/types";
import CreateTargetModal from "@/components/CreateTargetModal";

export default function Home() {
  const router = useRouter();
  const [targets, setTargets] = useState<TargetResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const fetchTargets = async () => {
    try {
      const response = await targetApi.list();
      setTargets(response.data);
    } catch (error) {
      console.error("Failed to fetch targets:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTargets();
  }, []);

  const handleTargetClick = (targetId: number) => {
    router.push(`/targets/${targetId}`);
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
          startIcon={<AddIcon />}
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
        <Grid container spacing={3}>
          {targets.map((target) => (
            <Grid item xs={12} sm={6} md={4} key={target.id}>
              <Card
                sx={{
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  cursor: "pointer",
                  transition: "all 0.2s",
                  "&:hover": {
                    transform: "translateY(-4px)",
                    boxShadow: 4,
                  },
                }}
                onClick={() => handleTargetClick(target.id)}
              >
                <CardContent sx={{ flexGrow: 1 }}>
                  <Typography variant="h6" component="h2" gutterBottom>
                    {target.name}
                  </Typography>
                  {target.agency && (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      gutterBottom
                    >
                      {target.agency}
                    </Typography>
                  )}
                  {target.purpose && (
                    <Typography variant="body2" color="text.secondary">
                      {target.purpose}
                    </Typography>
                  )}
                </CardContent>
                <CardActions>
                  <Button size="small" onClick={() => handleTargetClick(target.id)}>
                    View Details
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      <CreateTargetModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={fetchTargets}
      />
    </Box>
  );
}
