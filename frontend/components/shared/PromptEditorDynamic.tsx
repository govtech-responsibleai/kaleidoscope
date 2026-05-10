"use client";

import dynamic from "next/dynamic";
import { Box, CircularProgress } from "@mui/material";

const PromptEditor = dynamic(() => import("./PromptEditor"), {
  ssr: false,
  loading: () => (
    <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
      <CircularProgress size={24} />
    </Box>
  ),
});

export default PromptEditor;
