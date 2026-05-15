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
  Checkbox,
  FormControlLabel,
  CircularProgress,
  Alert,
  MenuItem,
  Typography,
} from "@mui/material";
import { IconCode, IconArrowLeft } from "@tabler/icons-react";
import {
  JudgeConfig,
  JudgeCreate,
  JudgeModelOption,
  JudgeUpdate,
} from "@/lib/types";
import { getApiErrorMessage, judgeApi } from "@/lib/api";
import { getModelIcon } from "@/lib/modelIcons";
import PromptEditor from "@/components/shared/PromptEditorDynamic";
import LanguageSelect from "@/components/shared/LanguageSelect";
import { TESTIDS } from "@/tests/ui-integration/fixtures/testids";

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
  const [judgeLanguage, setJudgeLanguage] = useState("");
  const [languageAware, setLanguageAware] = useState(false);
  const [languageOutput, setLanguageOutput] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<JudgeModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const promptEditedRef = useRef(false);
  const previousModeRef = useRef<CreateJudgeDialogProps["mode"] | null>(null);

  useEffect(() => {
    let isMounted = true;
    const loadModels = async () => {
      try {
        const { data } = await judgeApi.listAvailableModels();
        if (!isMounted) return;
        setAvailableModels(data);
        setModelsError(null);
      } catch (err) {
        console.error("Failed to load available models:", err);
        if (isMounted) {
          setModelsError(getApiErrorMessage(err, "Unable to load available models."));
        }
      } finally {
        if (isMounted) setModelsLoading(false);
      }
    };
    loadModels();
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const fetchBaselinePrompt = async () => {
      if (!rubricId) {
        if (isMounted) setBaselinePromptTemplate("");
        return;
      }
      try {
        const { data } = await judgeApi.getBaseline(rubricId);
        if (isMounted) setBaselinePromptTemplate(data.prompt_template || "");
      } catch (err) {
        console.error("Failed to load baseline judge prompt:", err);
      }
    };
    fetchBaselinePrompt();
    return () => { isMounted = false; };
  }, [rubricId]);

  useEffect(() => {
    if (open) {
      if (mode === "edit" && judge) {
        const existingParams = judge.params || {};
        setName(judge.name);
        setModelName(judge.model_name);
        setParams(existingParams);
        setJudgeLanguage(
          typeof existingParams.language === "string" ? existingParams.language : ""
        );
        setLanguageAware(!!existingParams.language_aware);
        setLanguageOutput(!!existingParams.language_output);
        const tempValue =
          resolveTemperatureValue(judge.temperature) ??
          resolveTemperatureValue(existingParams?.temperature) ??
          0.7;
        setTemperature(tempValue.toString());
        setPromptTemplate(judge.prompt_template || "");
        promptEditedRef.current = true;
        setShowPromptEditor(!!judge.prompt_template);
      } else if (mode === "duplicate" && judge) {
        const existingParams = judge.params || {};
        setName(`${judge.name} (Copy)`);
        setModelName(judge.model_name);
        setParams(existingParams);
        setJudgeLanguage(
          typeof existingParams.language === "string" ? existingParams.language : ""
        );
        setLanguageAware(!!existingParams.language_aware);
        setLanguageOutput(!!existingParams.language_output);
        const tempValue =
          resolveTemperatureValue(judge.temperature) ??
          resolveTemperatureValue(existingParams?.temperature) ??
          0.7;
        setTemperature(tempValue.toString());
        setPromptTemplate(judge.prompt_template || "");
        promptEditedRef.current = true;
        setShowPromptEditor(!!judge.prompt_template);
      } else {
        setName("Custom Judge");
        setModelName(availableModels[0]?.value || "");
        setTemperature("1.0");
        setParams({});
        setJudgeLanguage("");
        setLanguageAware(false);
        setLanguageOutput(false);
        setShowPromptEditor(false);
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
      setShowPromptEditor(false);
      setParams({});
      setJudgeLanguage("");
      setLanguageAware(false);
      setLanguageOutput(false);
    }
    previousModeRef.current = mode;
  }, [open, mode, judge, baselinePromptTemplate, availableModels, defaultPromptTemplate]);

  useEffect(() => {
    if (open && mode === "create" && !judge && !modelName && availableModels.length > 0) {
      setModelName(availableModels[0].value);
    }
  }, [availableModels, modelName, open, mode, judge]);

  const handlePromptTemplateChange = (value: string) => {
    promptEditedRef.current = true;
    setPromptTemplate(value);
  };

  const handleSubmit = async () => {
    if (!name.trim()) { setError("Judge name is required"); return; }
    if (!modelName.trim()) { setError("Model name is required"); return; }
    const temp = parseFloat(temperature);
    if (isNaN(temp) || temp < 0 || temp > 2) {
      setError("Temperature must be between 0 and 2");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const trimmedLanguage = judgeLanguage.trim();
      const updatedParams = {
        ...(params || {}),
        temperature: temp,
        language: trimmedLanguage || null,
        language_aware: !!trimmedLanguage && languageAware,
        language_output: !!trimmedLanguage && languageOutput,
      };
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
    if (!loading) onClose();
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

  const promptPreviewLines = promptTemplate
    ? promptTemplate.split("\n").slice(0, 3).join("\n")
    : "";

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth={showPromptEditor ? "lg" : "sm"}
      fullWidth
      sx={{
        "& .MuiDialog-paper": {
          transition: "max-width 0.3s ease-in-out",
          ...(showPromptEditor && { height: "80vh" }),
        },
      }}
    >
      <DialogTitle>{getDialogTitle()}</DialogTitle>
      <DialogContent sx={{ ...(showPromptEditor && { overflow: "hidden", display: "flex", flexDirection: "column" }) }}>
        <Box
          sx={{
            display: "flex",
            gap: 3,
            mt: 1,
            flexDirection: showPromptEditor ? "row" : "column",
            ...(showPromptEditor && { flex: 1, minHeight: 0 }),
          }}
        >
          {/* Left / main column: config fields */}
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              gap: 2,
              flex: showPromptEditor ? "0 0 300px" : "1 1 auto",
              minWidth: 0,
              ...(showPromptEditor && { overflowY: "auto" }),
            }}
          >
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
                    const icon = getModelIcon(strValue, model?.logo_path);
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
                    {getModelIcon(model.value, model.logo_path) && (
                      <Box
                        component="img"
                        src={getModelIcon(model.value, model.logo_path)!}
                        alt=""
                        sx={{ width: 16, height: 16 }}
                      />
                    )}
                    {model.label}
                  </MenuItem>
                ))
              )}
            </TextField>

            {/* Prompt preview box */}
            <Box sx={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <Typography
                component="label"
                sx={{ fontSize: "0.9rem", fontWeight: 600, mb: "2px" }}
              >
                Prompt Template
              </Typography>
              <Box
                sx={{
                  position: "relative",
                  borderRadius: "5px",
                  border: "1px solid",
                  borderColor: "divider",
                  backgroundColor: "#fafbff",
                  overflow: "hidden",
                }}
              >
                <Box
                  sx={{
                    px: 1.5,
                    py: 1.5,
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "12px",
                    lineHeight: 1.6,
                    color: "text.secondary",
                    whiteSpace: "pre-wrap",
                    maxHeight: "4.8em",
                    overflow: "hidden",
                  }}
                >
                  {promptPreviewLines || "No prompt template configured"}
                </Box>
                {/* Fade overlay */}
                <Box
                  sx={{
                    position: "absolute",
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: "24px",
                    background: "linear-gradient(transparent, #fafbff)",
                    pointerEvents: "none",
                  }}
                />
                {/* Customize button */}
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "flex-end",
                    px: 1,
                    py: 0.5,
                    borderTop: "1px solid",
                    borderColor: "divider",
                    backgroundColor: "#f5f6fc",
                  }}
                >
                  <Button
                    size="small"
                    onClick={() => setShowPromptEditor(true)}
                    disabled={showPromptEditor}
                    startIcon={<IconCode size={14} />}
                    sx={{
                      textTransform: "none",
                      fontSize: "0.75rem",
                      fontWeight: 500,
                      color: showPromptEditor ? "text.disabled" : "text.secondary",
                      "&:hover": {
                        color: "primary.main",
                      },
                    }}
                  >
                    Customize prompt
                  </Button>
                </Box>
              </Box>
            </Box>

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

            {/* Language settings — optional, two independent toggles */}
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
              <Typography
                component="label"
                sx={{ fontSize: "0.9rem", fontWeight: 600 }}
              >
                Language (optional)
              </Typography>
              <LanguageSelect
                value={judgeLanguage}
                onChange={setJudgeLanguage}
                allowEmpty
                emptyLabel="Not set"
                label="Judge language"
                disabled={loading}
                testId={TESTIDS.JUDGE_LANGUAGE_SELECTOR}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    size="small"
                    checked={languageAware}
                    onChange={(e) => setLanguageAware(e.target.checked)}
                    disabled={loading || !judgeLanguage}
                    inputProps={
                      {
                        "data-testid": TESTIDS.JUDGE_LANGUAGE_AWARE_TOGGLE,
                      } as React.InputHTMLAttributes<HTMLInputElement>
                    }
                  />
                }
                label={
                  <Typography variant="body2">
                    Tell the judge the question &amp; answer are in this language
                  </Typography>
                }
              />
              <FormControlLabel
                control={
                  <Checkbox
                    size="small"
                    checked={languageOutput}
                    onChange={(e) => setLanguageOutput(e.target.checked)}
                    disabled={loading || !judgeLanguage}
                    inputProps={
                      {
                        "data-testid": TESTIDS.JUDGE_LANGUAGE_OUTPUT_TOGGLE,
                      } as React.InputHTMLAttributes<HTMLInputElement>
                    }
                  />
                }
                label={
                  <Typography variant="body2">
                    Have the judge write its explanations in this language
                  </Typography>
                }
              />
            </Box>
          </Box>

          {/* Right column: full prompt editor */}
          {showPromptEditor && (
            <Box
              sx={{
                flex: "1 1 auto",
                minWidth: 0,
                minHeight: 0,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                animation: "slideInRight 0.25s ease-out",
                "@keyframes slideInRight": {
                  from: { opacity: 0, transform: "translateX(12px)" },
                  to: { opacity: 1, transform: "translateX(0)" },
                },
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
                <Button
                  size="small"
                  onClick={() => setShowPromptEditor(false)}
                  startIcon={<IconArrowLeft size={16} />}
                  sx={{
                    minWidth: "auto",
                    textTransform: "none",
                    fontSize: "0.8rem",
                    color: "text.secondary",
                    "&:hover": { color: "text.primary" },
                  }}
                >
                  Back
                </Button>
              </Box>
              <PromptEditor
                value={promptTemplate}
                onChange={handlePromptTemplateChange}
                disabled={loading}
                placeholder="Enter your custom prompt template here..."
              />
            </Box>
          )}
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
