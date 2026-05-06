"use client";

import { Box, Typography, useTheme } from "@mui/material";
import { TESTIDS } from "@/tests/ui-integration/fixtures/testids";

interface AccuracyGaugeProps {
  value: number | null; // 0 to 1, or null for no data
  size?: number;
  label?: string;
}

export default function ScoreGauge({
  value,
  size = 180,
  label = "Aggregated Score",
}: AccuracyGaugeProps) {
  const theme = useTheme();
  const hasValue = value !== null;
  const displayValue = hasValue ? value : 0;
  const percentage = hasValue ? (value * 100).toFixed(1) : "--";

  // SVG parameters for semi-circle gauge
  const strokeWidth = 20;
  const radius = (size - strokeWidth) / 2;
  const circumference = Math.PI * radius; // Half circle
  const progress = displayValue * circumference;

  // Center point
  const cy = size / 2 + 10; // Slight offset down for semi-circle

  // Color based on value
  const getColor = (val: number) => {
    if (val >= 0.7) return theme.palette.success.main;
    if (val >= 0.5) return theme.palette.warning.main;
    return theme.palette.error.main;
  };

  const gaugeColor = hasValue ? getColor(value) : theme.palette.text.disabled;
  const numericFontSize = percentage.length >= 5 ? Math.round(size * 0.22) : Math.round(size * 0.24);
  const percentFontSize = Math.round(numericFontSize * 0.48);

  return (
    <Box
      data-testid={TESTIDS.SCORE_GAUGE}
      sx={{
        position: "relative",
        width: "100%",
        maxWidth: size,
        aspectRatio: `${size} / ${size * 0.65}`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <svg
        viewBox={`0 0 ${size} ${size * 0.6}`}
        width="100%"
        height="auto"
        style={{ display: "block" }}
      >
        {/* Background arc */}
        <path
          d={`M ${strokeWidth / 2} ${cy} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${cy}`}
          fill="none"
          stroke={theme.palette.grey[200]}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />

        {/* Progress arc */}
        <path
          d={`M ${strokeWidth / 2} ${cy} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${cy}`}
          fill="none"
          stroke={gaugeColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          style={{
            transition: "stroke-dashoffset 0.5s ease-in-out",
          }}
        />

        {/* Gradient overlay for depth effect */}
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={gaugeColor} stopOpacity="0.8" />
            <stop offset="100%" stopColor={gaugeColor} stopOpacity="1" />
          </linearGradient>
        </defs>
      </svg>

      {/* Percentage text in center */}
      <Box
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -20%)",
          textAlign: "center",
        }}
      >
        <Typography
          fontWeight={700}
          sx={{
            color: gaugeColor,
            lineHeight: 1,
            fontSize: numericFontSize,
            letterSpacing: "-0.03em",
            whiteSpace: "nowrap",
          }}
        >
          {percentage}
          <Typography
            component="span"
            fontWeight={700}
            sx={{ color: gaugeColor, fontSize: percentFontSize }}
          >
            %
          </Typography>
        </Typography>
      </Box>

      {/* Label below */}
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          position: "absolute",
          bottom: 0,
          textAlign: "center",
        }}
      >
        {label}
      </Typography>
    </Box>
  );
}
