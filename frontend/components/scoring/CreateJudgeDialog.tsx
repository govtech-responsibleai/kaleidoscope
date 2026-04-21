"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  CircularProgress,
  Alert,
  MenuItem,
  Typography,
} from "@mui/material";
import {
  JudgeConfig,
  JudgeCreate,
  JudgeModelOption,
  JudgeUpdate,
} from "@/lib/types";
import { judgeApi } from "@/lib/api";
import { getModelIcon } from "@/lib/modelIcons";

const resolveTemperatureValue = (value: unknown): number | null => {
  if (typeof value === "number" && !isNaN(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = parseFloat(value);
    return isNaN(parsed) ? null : parsed;
  }
  return null;
};

interface CreateJudgeDialogProps {
  open: boolean;
  targetId: number;
  rubricId?: number | null;
  mode: "create" | "edit" | "duplicate";
  judge?: JudgeConfig | null;
  defaultPromptTemplate?: string;
  metricLabel?: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CreateJudgeDialog({
  open,
  targetId,
  rubricId,
  mode,
  judge,
  defaultPromptTemplate,
  metricLabel,
  onClose,
  onSuccess,
}: CreateJudgeDialogProps) {
  const [name, setName] = useState("");
  const [modelName, setModelName] = useState("");
  const [temperature, setTemperature] = useState("0.7");
  const [promptTemplate, setPromptTemplate] = useState("");
  const [baselinePromptTemplate, setBaselinePromptTemplate] = useState("");
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<JudgeModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const promptEditedRef = useRef(false);
  const previousModeRef = useRef<CreateJudgeDialogProps["mode"] | null>(null);

  useEffect(() => {
    let isMounted = true;
    const loadModels = async () => {
      try {
        const { data } = await judgeApi.listAvailableModels();
        if (!isMounted) {
          return;
        }
        setAvailableModels(data);
        setModelsError(null);
      } catch (err) {
        console.error("Failed to load available models:", err);
        if (isMounted) {
          setModelsError("Unable to load available models.");
        }
      } finally {
        if (isMounted) {
          setModelsLoading(false);
        }
      }
    };
    loadModels();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const fetchBaselinePrompt = async () => {
      if (!rubricId) {
        if (isMounted) {
          setBaselinePromptTemplate("");
        }
        return;
      }
      try {
        const { data } = await judgeApi.getBaseline(rubricId);
        if (isMounted) {
          setBaselinePromptTemplate(data.prompt_template || "");
        }
      } catch (err) {
        console.error("Failed to load baseline judge prompt:", err);
      }
    };

    fetchBaselinePrompt();

    return () => {
      isMounted = false;
    };
  }, [rubricId]);

  useEffect(() => {
    if (open) {
      if (mode === "edit" && judge) {
        const existingParams = judge.params || {};
        setName(judge.name);
        setModelName(judge.model_name);
        setParams(existingParams);
        const tempValue =
          resolveTemperatureValue(judge.temperature) ??
          resolveTemperatureValue(existingParams?.temperature) ??
          0.7;
        setTemperature(tempValue.toString());
        setPromptTemplate(judge.prompt_template || "");
        promptEditedRef.current = true;
      } else if (mode === "duplicate" && judge) {
        const existingParams = judge.params || {};
        setName(`${judge.name} (Copy)`);
        setModelName(judge.model_name);
        setParams(existingParams);
        const tempValue =
          resolveTemperatureValue(judge.temperature) ??
          resolveTemperatureValue(existingParams?.temperature) ??
          0.7;
        setTemperature(tempValue.toString());
        setPromptTemplate(judge.prompt_template || "");
        promptEditedRef.current = true;
      } else {
        setName("Custom Judge");
        setModelName(availableModels[0]?.value || "");
        setTemperature("1.0");
        setParams({});
        if (previousModeRef.current !== "create") {
          promptEditedRef.current = false;
        }
        if (!promptEditedRef.current) {
          setPromptTemplate(defaultPromptTemplate || baselinePromptTemplate || "");
        }
      }
      setError(null);
    } else {
      promptEditedRef.current = false;
      setParams({});
    }

    previousModeRef.current = mode;
  }, [open, mode, judge, baselinePromptTemplate, availableModels, defaultPromptTemplate]);

  useEffect(() => {
    if (
      open &&
      mode === "create" &&
      !judge &&
      !modelName &&
      availableModels.length > 0
    ) {
      setModelName(availableModels[0].value);
    }
  }, [availableModels, modelName, open, mode, judge]);

  const handlePromptTemplateChange = (value: string) => {
    promptEditedRef.current = true;
    setPromptTemplate(value);
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError("Judge name is required");
      return;
    }

    if (!modelName.trim()) {
      setError("Model name is required");
      return;
    }

    const temp = parseFloat(temperature);
    if (isNaN(temp) || temp < 0 || temp > 2) {
      setError("Temperature must be between 0 and 2");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const updatedParams = { ...(params || {}), temperature: temp };
      const selectedModel = availableModels.find((m) => m.value === modelName);
      const modelLabel = selectedModel?.label || modelName;

      if (mode === "edit" && judge) {
        const data: JudgeUpdate = {
          name: name.trim(),
          model_name: modelName.trim(),
          model_label: modelLabel,
          params: updatedParams,
          prompt_template: promptTemplate.trim() || undefined,
        };
        await judgeApi.update(judge.id, data);
      } else {
        const data: JudgeCreate = {
          target_id: targetId,
          rubric_id: rubricId ?? undefined,
          name: name.trim(),
          model_name: modelName.trim(),
          model_label: modelLabel,
          params: updatedParams,
          prompt_template: promptTemplate.trim() || undefined,
        };
        await judgeApi.create(data);
      }
      onSuccess();
    } catch (err) {
      console.error("Failed to save judge:", err);
      setError("Failed to save judge configuration. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  const getDialogTitle = () => {
    switch (mode) {
      case "create":
        return metricLabel ? `Create ${metricLabel} Judge` : "Create New Judge";
      case "edit":
        return "Edit Judge";
      case "duplicate":
        return "Duplicate Judge";
      default:
        return "Judge Configuration";
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{getDialogTitle()}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
          {error && (
            <Alert severity="error" onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <TextField
            label="Judge Name"
            required
            fullWidth
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={loading}
            placeholder="e.g., Custom Judge 1"
          />

          <TextField
            select
            label="Model Name"
            required
            fullWidth
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            disabled={loading || modelsLoading || availableModels.length === 0}
            slotProps={{
              select: {
                renderValue: (value) => {
                  const strValue = value as string;
                  const model = availableModels.find((m) => m.value === strValue);
                  const icon = getModelIcon(strValue);
                  return (
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      {icon && (
                        <Box
                          component="img"
                          src={icon}
                          alt=""
                          sx={{ width: 16, height: 16 }}
                        />
                      )}
                      {model?.label || strValue}
                    </Box>
                  );
                },
              },
            }}
          >
            {availableModels.length === 0 ? (
              <MenuItem value="" disabled>
                {modelsLoading
                  ? "Loading models..."
                  : modelsError || "No models available"}
              </MenuItem>
            ) : (
              availableModels.map((model) => (
                <MenuItem key={model.value} value={model.value} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  {getModelIcon(model.value) && (
                    <Box
                      component="img"
                      src={getModelIcon(model.value)!}
                      alt=""
                      sx={{ width: 16, height: 16 }}
                    />
                  )}
                  {model.label}
                </MenuItem>
              ))
            )}
          </TextField>

          <TextField
            label="Prompt Template"
            required
            fullWidth
            multiline
            rows={6}
            value={promptTemplate}
            onChange={(e) => handlePromptTemplateChange(e.target.value)}
            disabled={loading}
            placeholder="Optional custom prompt template for this judge"
            helperText="Defaults to the same template used by the primary judge—feel free to extend or edit."
          />

          <Typography variant="h6" sx={{ mt: 2 }}>
            Custom Parameters
          </Typography>

          <TextField
            label="Temperature"
            required
            fullWidth
            type="number"
            inputProps={{ min: 0, max: 2, step: 0.1 }}
            value={temperature}
            onChange={(e) => setTemperature(e.target.value)}
            disabled={loading}
            helperText="Value between 0 and 2"
          />
          
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading || !name.trim() || !modelName.trim()}
        >
          {loading ? <CircularProgress size={24} /> : mode === "edit" ? "Save" : "Create"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
