"use client";

import React from "react";
import { Box, Card, CardContent, Typography } from "@mui/material";
import {
  IconSparkles,
  IconUserPlus,
  IconUsersGroup,
} from "@tabler/icons-react";

interface PersonaSelectProps {
  onGenerateAI: () => void;
  onSampleRandom: () => void;
  onAddManual: () => void;
}

const baseCardSx = {
  width: 200,
  cursor: "pointer",
  boxShadow: "none",
  border: "1px solid #E0E0E0",
  transition: "transform 0.2s ease",
  "&:hover": { transform: "translateY(-4px)" },
  "& .card-icon svg": { transition: "stroke 0.3s ease" },
};

export default function PersonaSelect({
  onGenerateAI,
  onSampleRandom,
  onAddManual,
}: PersonaSelectProps) {
  return (
    <Box display="flex" gap={2} flexWrap="wrap" justifyContent="center">
      <svg width="0" height="0" style={{ position: "absolute" }}>
        <defs>
          <linearGradient id="pg-primary" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0d1433" />
            <stop offset="100%" stopColor="#7b9dff" />
          </linearGradient>
          <linearGradient id="pg-secondary" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#6b0024" />
            <stop offset="100%" stopColor="#ff6b9d" />
          </linearGradient>
          <linearGradient id="pg-info" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#003060" />
            <stop offset="100%" stopColor="#80d8ff" />
          </linearGradient>
        </defs>
      </svg>
      <Card sx={{ ...baseCardSx, "&:hover .card-icon svg": { stroke: "url(#pg-primary) #1976d2" } }} onClick={onGenerateAI}>
        <CardContent sx={{ textAlign: "center", py: 3 }}>
          <Box className="card-icon" sx={{ color: "primary.main", mb: 1, display: "flex", justifyContent: "center" }}>
            <IconSparkles size={40} stroke={1.8} />
          </Box>
          <Typography variant="subtitle1" fontWeight={600}>
            Generate with AI
          </Typography>
          <Typography variant="body2" color="text.secondary">
            AI creates personas from your target context
          </Typography>
        </CardContent>
      </Card>
      <Card sx={{ ...baseCardSx, "&:hover .card-icon svg": { stroke: "url(#pg-secondary) #dc004e" } }} onClick={onSampleRandom}>
        <CardContent sx={{ textAlign: "center", py: 3 }}>
          <Box className="card-icon" sx={{ color: "secondary.main", mb: 1, display: "flex", justifyContent: "center" }}>
            <IconUsersGroup size={40} stroke={1.8} />
          </Box>
          <Typography variant="subtitle1" fontWeight={600}>
            Random Personas
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Sample from Nemotron dataset
          </Typography>
        </CardContent>
      </Card>
      <Card sx={{ ...baseCardSx, "&:hover .card-icon svg": { stroke: "url(#pg-info) #0288d1" } }} onClick={onAddManual}>
        <CardContent sx={{ textAlign: "center", py: 3 }}>
          <Box className="card-icon" sx={{ color: "info.main", mb: 1, display: "flex", justifyContent: "center" }}>
            <IconUserPlus size={40} stroke={1.8} />
          </Box>
          <Typography variant="subtitle1" fontWeight={600}>
            Add Manually
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Define a persona yourself
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
