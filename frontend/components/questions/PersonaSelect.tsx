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

const cardSx = {
  width: 200,
  cursor: "pointer",
  transition: "all 0.2s",
  "&:hover": { transform: "translateY(-4px)", boxShadow: 4 },
};

export default function PersonaSelect({
  onGenerateAI,
  onSampleRandom,
  onAddManual,
}: PersonaSelectProps) {
  return (
    <Box display="flex" gap={2} flexWrap="wrap" justifyContent="center">
      <Card sx={cardSx} onClick={onGenerateAI}>
        <CardContent sx={{ textAlign: "center", py: 3 }}>
          <Box sx={{ color: "primary.main", mb: 1, display: "flex", justifyContent: "center" }}>
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
      <Card sx={cardSx} onClick={onSampleRandom}>
        <CardContent sx={{ textAlign: "center", py: 3 }}>
          <Box sx={{ color: "secondary.main", mb: 1, display: "flex", justifyContent: "center" }}>
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
      <Card sx={cardSx} onClick={onAddManual}>
        <CardContent sx={{ textAlign: "center", py: 3 }}>
          <Box sx={{ color: "info.main", mb: 1, display: "flex", justifyContent: "center" }}>
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
