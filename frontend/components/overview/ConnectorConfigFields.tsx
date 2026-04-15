"use client";

import React, { useCallback, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  TextField,
  MenuItem,
  Collapse,
  Link,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from "@mui/icons-material";
import { EndpointConfig } from "@/lib/types";
import { targetApi } from "@/lib/api";

const BODY_TEMPLATE_PLACEHOLDER = `{
  "model": "gpt-4",
  "messages": [{ "role": "user", "content": "{{prompt}}" }]
}`;

const MONOSPACE_INPUT = { sx: { fontFamily: "monospace", fontSize: "0.85rem" } } as const;

export function isValidJson(value: string): boolean {
  if (!value.trim()) return true;
  try {
    JSON.parse(value);
    return true;
  } catch {
    return false;
  }
}

/**
 * Check that all JSON-typed config fields are valid before submit.
 * Returns an error message string, or null if valid.
 */
export function validateEndpointConfig(endpointType: string, config: EndpointConfig): string | null {
  if (endpointType === "http") {
    if (typeof config.headers === "string" && !isValidJson(config.headers)) {
      return "Headers must be valid JSON";
    }
    if (typeof config.body_template === "string" && !isValidJson(config.body_template as string)) {
      return "Body template must be valid JSON";
    }
  }
  return null;
}

interface ConnectorConfigFieldsProps {
  endpointType: string;
  config: EndpointConfig;
  apiEndpoint?: string;
  onConfigField: (field: string, value: unknown) => void;
  onConfigReplace?: (config: EndpointConfig) => void;
  showAdvanced: boolean;
  onToggleAdvanced: () => void;
  disabled?: boolean;
  onJsonError?: (message: string) => void;
  /** "modal" uses TextField labels; "form" uses side-by-side label + field rows */
  variant?: "modal" | "form";
}

export default function ConnectorConfigFields({
  endpointType,
  config,
  apiEndpoint,
  onConfigField,
  onConfigReplace,
  showAdvanced,
  onToggleAdvanced,
  disabled = false,
  onJsonError,
  variant = "modal",
}: ConnectorConfigFieldsProps) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; content?: string; error?: string } | null>(null);
  const [preset, setPreset] = useState<"openai" | "custom">("custom");

  const applyPreset = useCallback((which: "openai" | "custom") => {
    setPreset(which);
    if (which === "openai") {
      onConfigField("response_content_path", "choices.0.message.content");
      onConfigField("body_template", { model: "gpt-4", messages: [{ role: "user", content: "{{prompt}}" }] });
      onConfigField("response_model_path", "model");
      onConfigField("response_tokens_path", "usage");
    } else {
      onConfigField("response_content_path", "");
      onConfigField("body_template", undefined);
      onConfigField("response_model_path", "");
      onConfigField("response_tokens_path", "");
    }
  }, [onConfigField]);

  const handleConfigFieldWithPresetReset = useCallback((field: string, value: unknown) => {
    if (preset === "openai") setPreset("custom");
    onConfigField(field, value);
  }, [preset, onConfigField]);

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await targetApi.testConnection({
        endpoint_type: endpointType,
        api_endpoint: apiEndpoint || "",
        endpoint_config: config,
      });
      setTestResult(res.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Connection test failed";
      setTestResult({ success: false, error: message });
    } finally {
      setTesting(false);
    }
  };
  const jsonFieldOnChange = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    try {
      onConfigField(field, JSON.parse(e.target.value));
    } catch {
      onConfigField(field, e.target.value);
    }
  };

  const jsonFieldOnBlur = (label: string) => (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (e.target.value && !isValidJson(e.target.value)) {
      onJsonError?.(`${label} must be valid JSON`);
    }
  };

  const jsonDisplayValue = (value: unknown): string => {
    if (typeof value === "object" && value !== null) return JSON.stringify(value, null, 2);
    return (value as string) || "";
  };

  const isForm = variant === "form";

  const wrapField = (label: string, children: React.ReactNode, multiline = false) => {
    if (!isForm) return children;
    return (
      <Box sx={{ display: "flex", gap: 2, alignItems: multiline ? "flex-start" : "center" }}>
        <Typography variant="subtitle1" color="text.secondary" sx={{ minWidth: "120px", ...(multiline && { pt: 1 }) }}>
          {label}:
        </Typography>
        {children}
      </Box>
    );
  };

  const renderHttpConfig = () => (
    <>
      <Box sx={{ ...(isForm && { pl: "136px" }) }}>
        <ToggleButtonGroup
          value={preset}
          exclusive
          onChange={(_, value) => { if (value) applyPreset(value); }}
          size="small"
        >
          <ToggleButton value="openai">OpenAI-compatible</ToggleButton>
          <ToggleButton value="custom">Custom</ToggleButton>
        </ToggleButtonGroup>
      </Box>
      {wrapField("Response Path",
        <TextField
          {...(!isForm && { label: "Response Content Path", required: true })}
          fullWidth
          value={config.response_content_path || ""}
          onChange={(e) => handleConfigFieldWithPresetReset("response_content_path", e.target.value)}
          disabled={disabled}
          placeholder="choices.0.message.content"
          helperText="Dot-notation path to extract answer text"
          size="small"
        />
      )}
      {isForm ? (
        <Box sx={{ pl: "136px" }}>
          <AdvancedToggle showAdvanced={showAdvanced} onToggle={onToggleAdvanced} />
        </Box>
      ) : (
        <AdvancedToggle showAdvanced={showAdvanced} onToggle={onToggleAdvanced} sx={{ alignSelf: "flex-start" }} />
      )}
      <Collapse in={showAdvanced} timeout={300}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: isForm ? 2.5 : 2, pt: isForm ? 0 : 1 }}>
          {wrapField("Method",
            <TextField
              {...(!isForm && { label: "Method" })}
              select
              fullWidth
              value={config.method || "POST"}
              onChange={(e) => onConfigField("method", e.target.value)}
              disabled={disabled}
              size="small"
            >
              {["POST", "GET", "PUT", "PATCH"].map((m) => (
                <MenuItem key={m} value={m}>{m}</MenuItem>
              ))}
            </TextField>
          )}
          {wrapField("Headers",
            <TextField
              {...(!isForm && { label: "Headers (JSON)" })}
              fullWidth
              multiline
              rows={3}
              value={jsonDisplayValue(config.headers)}
              onChange={jsonFieldOnChange("headers")}
              onBlur={jsonFieldOnBlur("Headers")}
              disabled={disabled}
              placeholder='{"Authorization": "Bearer sk-..."}'
              slotProps={{ input: MONOSPACE_INPUT }}
              size="small"
            />,
            true,
          )}
          {wrapField("Body Template",
            <TextField
              {...(!isForm && { label: "Body Template (JSON)" })}
              fullWidth
              multiline
              rows={4}
              value={jsonDisplayValue(config.body_template)}
              onChange={(e) => { if (preset === "openai") setPreset("custom"); jsonFieldOnChange("body_template")(e); }}
              onBlur={jsonFieldOnBlur("Body template")}
              disabled={disabled}
              placeholder={BODY_TEMPLATE_PLACEHOLDER}
              helperText="Use {{prompt}} as a placeholder for the input text"
              slotProps={{ input: MONOSPACE_INPUT }}
              size="small"
            />,
            true,
          )}
          {wrapField("Timeout",
            <TextField
              {...(!isForm && { label: "Timeout (seconds)" })}
              type="number"
              fullWidth
              value={config.timeout ?? ""}
              onChange={(e) => onConfigField("timeout", e.target.value ? Number(e.target.value) : undefined)}
              disabled={disabled}
              placeholder="60"
              size="small"
            />
          )}
          {wrapField("Model Path",
            <TextField
              {...(!isForm && { label: "Response Model Path" })}
              fullWidth
              value={config.response_model_path || ""}
              onChange={(e) => handleConfigFieldWithPresetReset("response_model_path", e.target.value)}
              disabled={disabled}
              placeholder="model"
              {...(!isForm && { helperText: "Dot-notation path to extract model name, e.g. model" })}
              size="small"
            />
          )}
          {wrapField("Tokens Path",
            <TextField
              {...(!isForm && { label: "Response Tokens Path" })}
              fullWidth
              value={config.response_tokens_path || ""}
              onChange={(e) => handleConfigFieldWithPresetReset("response_tokens_path", e.target.value)}
              disabled={disabled}
              placeholder="usage"
              {...(!isForm && { helperText: "Dot-notation path to extract token usage, e.g. usage" })}
              size="small"
            />
          )}
        </Box>
      </Collapse>
    </>
  );

  const renderAibotsConfig = () =>
    wrapField("API Key",
      <TextField
        {...(!isForm && { label: "API Key", required: true })}
        fullWidth
        type="password"
        value={config.api_key || ""}
        onChange={(e) => onConfigField("api_key", e.target.value)}
        disabled={disabled}
        size="small"
      />
    );

  const renderGenericConfig = () =>
    wrapField("Config",
      <TextField
        {...(!isForm && { label: "Endpoint Config (JSON)" })}
        fullWidth
        multiline
        rows={5}
        value={Object.keys(config).length > 0 ? JSON.stringify(config, null, 2) : ""}
        onChange={(e) => {
          try {
            onConfigReplace?.(JSON.parse(e.target.value));
          } catch {
            // allow typing — validated on blur
          }
        }}
        onBlur={jsonFieldOnBlur("Endpoint config")}
        disabled={disabled}
        placeholder="{}"
        slotProps={{ input: MONOSPACE_INPUT }}
        size="small"
      />,
      true,
    );

  const renderTestButton = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1, ...(isForm && { pl: "136px" }) }}>
      <Box>
        <Button
          variant="outlined"
          size="small"
          onClick={handleTestConnection}
          disabled={disabled || testing || !apiEndpoint}
        >
          {testing ? <><CircularProgress size={16} sx={{ mr: 1 }} /> Testing...</> : "Test Connection"}
        </Button>
      </Box>
      {testResult && (
        <Alert severity={testResult.success ? "success" : "error"} onClose={() => setTestResult(null)}>
          {testResult.success
            ? `Connected successfully${testResult.content ? `: ${testResult.content.slice(0, 100)}${testResult.content.length > 100 ? "…" : ""}` : ""}`
            : testResult.error}
        </Alert>
      )}
    </Box>
  );

  let configFields: React.ReactNode;
  switch (endpointType) {
    case "http":
      configFields = renderHttpConfig();
      break;
    case "aibots":
      configFields = renderAibotsConfig();
      break;
    default:
      configFields = renderGenericConfig();
      break;
  }

  return (
    <>
      {configFields}
      {renderTestButton()}
    </>
  );
}

function AdvancedToggle({
  showAdvanced,
  onToggle,
  sx,
}: {
  showAdvanced: boolean;
  onToggle: () => void;
  sx?: Record<string, unknown>;
}) {
  return (
    <Box sx={sx}>
      <Link
        component="button"
        variant="body2"
        onClick={onToggle}
        sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
      >
        {showAdvanced ? "Advanced Configuration" : "Optional: method, headers, body template, timeout"}
        {showAdvanced ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
      </Link>
      {!showAdvanced && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.25 }}>
          Defaults to POST with {`{"prompt": "{{prompt}}"}`} body
        </Typography>
      )}
    </Box>
  );
}
