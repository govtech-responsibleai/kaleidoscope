"use client";

import React, { useState } from "react";
import {
  Box,
  TextField,
  Button,
  CircularProgress,
} from "@mui/material";
import { IconUserPlus } from "@tabler/icons-react";
import { actionIconProps } from "@/lib/iconStyles";

interface PersonaManualAddProps {
  onSubmit: (data: { title: string; info?: string; style?: string; use_case?: string }) => Promise<unknown>;
  onBack: () => void;
  loading?: boolean;
  size?: "small" | "medium";
}

export default function PersonaManualAdd({
  onSubmit,
  onBack,
  loading = false,
  size = "small",
}: PersonaManualAddProps) {
  const [title, setTitle] = useState("");
  const [info, setInfo] = useState("");
  const [style, setStyle] = useState("");
  const [useCase, setUseCase] = useState("");

  const handleSubmit = async () => {
    if (!title.trim()) return;
    await onSubmit({
      title: title.trim(),
      info: info.trim() || undefined,
      style: style.trim() || undefined,
      use_case: useCase.trim() || undefined,
    });
    setTitle("");
    setInfo("");
    setStyle("");
    setUseCase("");
  };

  return (
    <Box display="flex" flexDirection="column" gap={2}>
      <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth required placeholder="e.g. New Employee" size={size} />
      <TextField label="Background" value={info} onChange={(e) => setInfo(e.target.value)} fullWidth multiline rows={2} placeholder="e.g. Recently joined the company" size={size} />
      <TextField label="Communication Style" value={style} onChange={(e) => setStyle(e.target.value)} fullWidth placeholder="e.g. Casual, asks short questions" size={size} />
      <TextField label="Use Case" value={useCase} onChange={(e) => setUseCase(e.target.value)} fullWidth placeholder="e.g. Needs to understand leave policies" size={size} />
      <Box display="flex" gap={1}>
        <Button onClick={onBack} size="small">Back</Button>
        <Button
          variant="contained"
          size="small"
          onClick={handleSubmit}
          disabled={loading || !title.trim()}
          startIcon={loading ? <CircularProgress size={16} /> : <IconUserPlus {...actionIconProps} />}
        >
          {loading ? "Adding..." : "Add Persona"}
        </Button>
      </Box>
    </Box>
  );
}
