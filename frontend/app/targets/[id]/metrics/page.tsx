"use client";

import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Divider,
  Button,
  IconButton,
} from "@mui/material";
import { EditOutlined as EditOutlinedIcon, Add as AddIcon } from "@mui/icons-material";

const accuracyOptions = [
  {
    option: "Accurate",
    description: "The response accurately reflects the source information.",
  },
  {
    option: "Inaccurate",
    description: "The response contains factual errors or omissions.",
  },
];

export default function MetricsPage() {
  return (
    <Box>
      <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
        Default Metrics
      </Typography>

      <Card variant="outlined" sx={{ pointerEvents: "none" }}>
        <CardContent>
          {/* Card header */}
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} color="text.disabled">
              Accuracy
            </Typography>
            <IconButton size="small" disabled>
              <EditOutlinedIcon fontSize="small" />
            </IconButton>
          </Box>

          {/* Criteria */}
          <TextField
            label="Criteria"
            value="Is the response factually accurate based on the knowledge base?"
            fullWidth
            disabled
            multiline
            size="small"
            sx={{ mb: 2 }}
          />

          <Divider sx={{ mb: 2 }} />

          {/* Options */}
          {accuracyOptions.map(({ option, description }) => (
            <Box key={option} sx={{ display: "flex", gap: 1.5, mb: 1.5 }}>
              <TextField
                label="Option"
                value={option}
                disabled
                size="small"
                sx={{ width: 140, flexShrink: 0 }}
              />
              <TextField
                label="Description"
                value={description}
                disabled
                size="small"
                fullWidth
              />
            </Box>
          ))}

          {/* Add Option button */}
          <Button
            startIcon={<AddIcon />}
            disabled
            size="small"
            sx={{ mt: 0.5 }}
          >
            Add Option
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
}
