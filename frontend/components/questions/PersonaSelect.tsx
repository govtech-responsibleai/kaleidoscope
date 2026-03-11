"use client";

import React from "react";
import { Box, Card, CardContent, Typography } from "@mui/material";
import {
  AutoAwesome as AutoAwesomeIcon,
  Groups as GroupsIcon,
  PersonAdd as PersonAddIcon,
} from "@mui/icons-material";

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
          <AutoAwesomeIcon sx={{ fontSize: 40, color: "primary.main", mb: 1 }} />
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
          <GroupsIcon sx={{ fontSize: 40, color: "secondary.main", mb: 1 }} />
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
          <PersonAddIcon sx={{ fontSize: 40, color: "info.main", mb: 1 }} />
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
