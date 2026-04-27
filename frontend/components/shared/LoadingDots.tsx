"use client";

import { Box } from "@mui/material";

export default function LoadingDots() {
  return (
    <Box
      component="span"
      sx={{
        display: "inline-block",
        width: 4,
        height: 4,
        borderRadius: "50%",
        ml: 1.5,
        mb: "1px",
        verticalAlign: "middle",
        animation: "loadingDots 1.4s infinite linear alternate",
        "@keyframes loadingDots": {
          "0%":   { boxShadow: "7px 0 currentColor, -7px 0 color-mix(in srgb, currentColor 15%, transparent)", background: "currentColor" },
          "33%":  { boxShadow: "7px 0 currentColor, -7px 0 color-mix(in srgb, currentColor 15%, transparent)", background: "color-mix(in srgb, currentColor 15%, transparent)" },
          "66%":  { boxShadow: "7px 0 color-mix(in srgb, currentColor 15%, transparent), -7px 0 currentColor", background: "color-mix(in srgb, currentColor 15%, transparent)" },
          "100%": { boxShadow: "7px 0 color-mix(in srgb, currentColor 15%, transparent), -7px 0 currentColor", background: "currentColor" },
        },
      }}
    />
  );
}
