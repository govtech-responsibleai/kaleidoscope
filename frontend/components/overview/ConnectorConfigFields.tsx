"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  IconChevronDown,
  IconChevronUp,
  IconEye,
  IconEyeOff,
  IconFlask2,
  IconPlayerPlay,
  IconPlus,
  IconX,
} from "@tabler/icons-react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Collapse,
  IconButton,
  InputAdornment,
  Link,
  MenuItem,
  TextField,
  Typography,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import { EndpointConfig, HttpAuthPreset, ManagedHttpAuthConfig, ProbeResponse } from "@/lib/types";
import { targetApi } from "@/lib/api";
import { groupColors } from "@/lib/theme";
import { actionIconProps, compactActionIconProps } from "@/lib/iconStyles";

/**
 * Walk a parsed JSON body and emit a flat list of leaf paths matching the
 * dot-notation convention used by the backend _extract_by_path helper
 * (list indices are written as integers, e.g. "choices.0.message.content").
 * Only primitive leaves (string/number/boolean/null) are emitted so each row
 * can become a click-target for "this is the field I want".
 */
export function flattenPaths(
  obj: unknown,
  prefix = "",
): { path: string; value: string }[] {
  if (obj === null || obj === undefined) {
    return prefix ? [{ path: prefix, value: String(obj) }] : [];
  }
  if (typeof obj !== "object") {
    return [{ path: prefix, value: String(obj) }];
  }
  if (Array.isArray(obj)) {
    return obj.flatMap((item, idx) =>
      flattenPaths(item, prefix ? `${prefix}.${idx}` : String(idx)),
    );
  }
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    flattenPaths(v, prefix ? `${prefix}.${k}` : k),
  );
}

const BODY_TEMPLATE_PLACEHOLDER = `{"message":"{{prompt}}"}`;

const MONOSPACE_INPUT = { sx: { fontFamily: "monospace", fontSize: "0.85rem" } } as const;
const JSON_EDITOR_LINE_HEIGHT = "1.5rem";
const HTTP_AUTH_PRESETS: { value: HttpAuthPreset; label: string; preview: string }[] = [
  { value: "bearer", label: "Authorization: Bearer", preview: "" },
  { value: "x-api-key", label: "X-API-Key", preview: "" },
  { value: "api-key", label: "api-key", preview: "" },
];

type KeyValueRow = {
  id: string;
  key: string;
  value: string;
};

function createRow(key = "", value = ""): KeyValueRow {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    key,
    value,
  };
}

function getHeadersObject(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, entryValue]) => [key, String(entryValue ?? "")]),
  );
}

function headersToRows(value: unknown): KeyValueRow[] {
  return Object.entries(getHeadersObject(value)).map(([key, entryValue]) => createRow(key, entryValue));
}

function metadataToRows(
  metadataFields: unknown,
  responseModelPath: unknown,
): KeyValueRow[] {
  const rows: KeyValueRow[] = [];
  const metadata = getHeadersObject(metadataFields);
  const modelPath = typeof responseModelPath === "string" ? responseModelPath : "";

  if (modelPath || Object.prototype.hasOwnProperty.call(metadata, "model")) {
    rows.push(createRow("model", modelPath || metadata.model || ""));
    delete metadata.model;
  }

  rows.push(
    ...Object.entries(metadata).map(([key, value]) => createRow(key, value)),
  );

  return rows.length > 0 ? rows : [createRow("model", "")];
}

function rowsToHeaders(rows: KeyValueRow[]): Record<string, string> {
  return rows.reduce<Record<string, string>>((acc, row) => {
    if (!row.key.trim()) {
      return acc;
    }
    acc[row.key] = row.value;
    return acc;
  }, {});
}

function jsonDisplayValue(value: unknown): string {
  if (typeof value === "object" && value !== null) return JSON.stringify(value, null, 2);
  return (value as string) || "";
}

function getManagedAuthConfig(value: unknown): ManagedHttpAuthConfig | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  return value as ManagedHttpAuthConfig;
}

export function isValidJson(value: string): boolean {
  if (!value.trim()) return true;
  try {
    JSON.parse(value);
    return true;
  } catch {
    return false;
  }
}

export function getJsonError(value: string): string | null {
  if (!value.trim()) return null;
  try {
    JSON.parse(value);
    return null;
  } catch (error) {
    if (error instanceof Error && error.message) {
      return `Invalid JSON: ${error.message}`;
    }
    return "Invalid JSON.";
  }
}

export function getHttpUrlError(value?: string): string | null {
  if (!value?.trim()) return null;
  try {
    const parsed = new URL(value);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return "URL must start with http:// or https://.";
    }
    return null;
  } catch {
    return "Invalid URL format.";
  }
}

function getBodyTemplateError(value: string): string | null {
  const jsonError = getJsonError(value);
  if (jsonError) {
    return jsonError;
  }
  if (value.trim() && !value.includes("{{prompt}}")) {
    return 'Request body must include "{{prompt}}" so Kaleidoscope can inject the prompt.';
  }
  return null;
}

/**
 * Check that all JSON-typed config fields are valid before submit.
 * Returns an error message string, or null if valid.
 */
export function validateEndpointConfig(endpointType: string, config: EndpointConfig): string | null {
  if (endpointType === "http") {
    const auth = getManagedAuthConfig(config.auth);
    if (auth && !auth.clear_secret) {
      if (!auth.preset) {
        return "Choose an auth type or remove the auth configuration.";
      }
      if (!auth.is_configured && !String(auth.secret_value || "").trim()) {
        return "Enter an auth value or remove the auth configuration.";
      }
    }

    const bodyTemplateText =
      typeof config.body_template === "string"
        ? config.body_template
        : config.body_template
          ? JSON.stringify(config.body_template)
          : "";
    const bodyTemplateError = getBodyTemplateError(bodyTemplateText);
    if (bodyTemplateError) {
      return bodyTemplateError;
    }
  }
  return null;
}

interface ConnectorConfigFieldsProps {
  endpointType: string;
  config: EndpointConfig;
  targetId?: number;
  apiEndpoint?: string;
  onConfigField: (field: string, value: unknown) => void;
  onConfigReplace?: (config: EndpointConfig) => void;
  showAdvanced: boolean;
  onToggleAdvanced: () => void;
  disabled?: boolean;
  onJsonError?: (message: string) => void;
  /** "modal" uses TextField labels; "form" uses stacked labels above each field block */
  variant?: "modal" | "form";
}

export default function ConnectorConfigFields({
  endpointType,
  config,
  targetId,
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
  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<ProbeResponse | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [headerRows, setHeaderRows] = useState<KeyValueRow[]>(() => headersToRows(config.headers));
  const [metadataRows, setMetadataRows] = useState<KeyValueRow[]>(() =>
    metadataToRows(config.metadata_fields, config.response_model_path),
  );
  const [bodyTemplateText, setBodyTemplateText] = useState(() => jsonDisplayValue(config.body_template));
  const bodyTemplateInternalUpdateRef = useRef(false);
  const skipHeaderSyncRef = useRef(false);
  const skipMetadataSyncRef = useRef(false);

  useEffect(() => {
    if (skipHeaderSyncRef.current) {
      skipHeaderSyncRef.current = false;
      return;
    }
    setHeaderRows(headersToRows(config.headers));
  }, [config.headers, endpointType]);

  useEffect(() => {
    if (bodyTemplateInternalUpdateRef.current) {
      bodyTemplateInternalUpdateRef.current = false;
      return;
    }
    setBodyTemplateText(jsonDisplayValue(config.body_template));
  }, [config.body_template]);

  useEffect(() => {
    if (skipMetadataSyncRef.current) {
      skipMetadataSyncRef.current = false;
      return;
    }
    const nextRows = metadataToRows(config.metadata_fields, config.response_model_path);
    setMetadataRows((prev) =>
      nextRows.length === 1 &&
      nextRows[0].key === "model" &&
      nextRows[0].value === "" &&
      prev.length === 0
        ? prev
        : nextRows,
    );
  }, [config.metadata_fields, config.response_model_path, endpointType]);

  const handleConfigField = useCallback((field: string, value: unknown) => {
    onConfigField(field, value);
  }, [onConfigField]);

  const syncHeaders = useCallback((rows: KeyValueRow[]) => {
    const nextHeaders = rowsToHeaders(rows);
    onConfigField("headers", Object.keys(nextHeaders).length > 0 ? nextHeaders : undefined);
  }, [onConfigField]);

  const syncMetadata = useCallback((rows: KeyValueRow[]) => {
    const nextMetadata = rows.reduce<Record<string, string>>((acc, row) => {
      const key = row.key.trim();
      if (!key || key === "model") {
        return acc;
      }
      acc[key] = row.value;
      return acc;
    }, {});
    const modelRow = rows.find((row) => row.key.trim() === "model");
    const modelPath = modelRow?.value ?? "";

    onConfigField("response_model_path", modelPath.trim() ? modelPath : undefined);
    onConfigField("metadata_fields", Object.keys(nextMetadata).length > 0 ? nextMetadata : undefined);
  }, [onConfigField]);

  const handleProbe = async () => {
    setProbing(true);
    setProbeResult(null);
    try {
      const res = await targetApi.probe({
        target_id: targetId,
        endpoint_type: endpointType,
        api_endpoint: apiEndpoint || "",
        endpoint_config: config,
      });
      setProbeResult(res.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Probe failed";
      setProbeResult({ success: false, error: message });
    } finally {
      setProbing(false);
    }
  };

  const handlePickPath = (path: string) => {
    handleConfigField("response_content_path", path);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await targetApi.testConnection({
        target_id: targetId,
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

  const updateHeaderRows = (updater: (rows: KeyValueRow[]) => KeyValueRow[]) => {
    const next = updater(headerRows);
    skipHeaderSyncRef.current = true;
    setHeaderRows(next);
    syncHeaders(next);
  };

  const updateMetadataRows = (updater: (rows: KeyValueRow[]) => KeyValueRow[]) => {
    const next = updater(metadataRows);
    skipMetadataSyncRef.current = true;
    setMetadataRows(next);
    syncMetadata(next);
  };

  const handleBodyTemplateChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const next = e.target.value;
    setBodyTemplateText(next);
    bodyTemplateInternalUpdateRef.current = true;
    if (!next.trim()) {
      onConfigField("body_template", undefined);
      return;
    }
    try {
      onConfigField("body_template", JSON.parse(next));
    } catch {
      onConfigField("body_template", next);
    }
  };

  const handleBodyTemplateBlur = () => {
    const bodyTemplateError = getBodyTemplateError(bodyTemplateText);
    if (bodyTemplateError) {
      onJsonError?.(bodyTemplateError);
    }
  };

  const jsonFieldOnBlur = (label: string) => (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const jsonError = getJsonError(e.target.value);
    if (jsonError) {
      onJsonError?.(`${label}: ${jsonError}`);
    }
  };

  const isForm = variant === "form";
  const bodyTemplateError = endpointType === "http" ? getBodyTemplateError(bodyTemplateText) : null;
  const apiEndpointError = endpointType === "http" ? getHttpUrlError(apiEndpoint) : null;
  const authConfig = endpointType === "http" ? getManagedAuthConfig(config.auth) : undefined;
  const showManagedAuthEditor = Boolean(authConfig && !authConfig.clear_secret);
  const authPreset = authConfig?.preset || "bearer";
  const authMaskedValue = authConfig?.masked_value || "";
  const authSecretValue = typeof authConfig?.secret_value === "string" ? authConfig.secret_value : "";
  const authIsConfigured = Boolean(authConfig?.is_configured);

  const setAuthConfig = (next: ManagedHttpAuthConfig | undefined) => {
    onConfigField("auth", next);
  };

  const handleAddAuth = () => {
    setAuthConfig({
      preset: authPreset,
      secret_value: "",
      is_configured: authIsConfigured,
      masked_value: authMaskedValue,
    });
  };

  const handleAuthPresetChange = (preset: HttpAuthPreset) => {
    setAuthConfig({
      preset,
      secret_value: authSecretValue,
      is_configured: authIsConfigured,
      masked_value: authMaskedValue,
    });
  };

  const handleAuthSecretChange = (value: string) => {
    setAuthConfig({
      preset: authPreset,
      secret_value: value,
      is_configured: authIsConfigured,
      masked_value: authMaskedValue,
    });
  };

  const handleClearAuth = () => {
    setAuthConfig(
      authIsConfigured
        ? { preset: authPreset, clear_secret: true }
        : undefined,
    );
  };

  const renderAuthRow = () => (
    <Box sx={{ display: "flex", gap: 1, alignItems: "center", width: "100%" }}>
      <TextField
        select
        size="small"
        value={authPreset}
        onChange={(e) => handleAuthPresetChange(e.target.value as HttpAuthPreset)}
        disabled={disabled}
        sx={{
          flex: "0 0 35%",
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: alpha(groupColors.fixed.border, 0.32),
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: alpha(groupColors.fixed.border, 0.48),
          },
        }}
      >
        {HTTP_AUTH_PRESETS.map((preset) => (
          <MenuItem key={preset.value} value={preset.value}>
            {preset.label}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        size="small"
        type={showAuthToken ? "text" : "password"}
        placeholder={authIsConfigured ? authMaskedValue || "Saved secret" : "Enter token"}
        value={authSecretValue}
        onChange={(e) => handleAuthSecretChange(e.target.value)}
        disabled={disabled}
        slotProps={{
          input: {
            endAdornment: (
              <InputAdornment position="end">
                <IconButton size="small" onClick={() => setShowAuthToken((v) => !v)} edge="end" tabIndex={-1}>
                  {showAuthToken ? <IconEyeOff size={16} stroke={2} /> : <IconEye size={16} stroke={2} />}
                </IconButton>
              </InputAdornment>
            ),
          },
        }}
        sx={{
          flex: "1 1 65%",
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: alpha(groupColors.fixed.border, 0.32),
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: alpha(groupColors.fixed.border, 0.48),
          },
        }}
      />
      <IconButton
        size="small"
        onClick={handleClearAuth}
        disabled={disabled}
        sx={{ color: "secondary.main" }}
      >
        <IconX {...compactActionIconProps} />
      </IconButton>
    </Box>
  );

  const renderHeaderRow = (row: KeyValueRow) => (
    <Box key={row.id} sx={{ display: "flex", gap: 1, alignItems: "center", width: "100%" }}>
      <TextField
        size="small"
        placeholder="Name"
        value={row.key}
        onChange={(e) => updateHeaderRows((rows) => rows.map((item) => (
          item.id === row.id ? { ...item, key: e.target.value } : item
        )))}
        disabled={disabled}
        sx={{
          flex: "0 0 35%",
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: alpha(groupColors.preset.border, 0.28),
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: alpha(groupColors.preset.border, 0.42),
          },
        }}
      />
      <TextField
        size="small"
        placeholder="Value"
        value={row.value}
        onChange={(e) => updateHeaderRows((rows) => rows.map((item) => (
          item.id === row.id ? { ...item, value: e.target.value } : item
        )))}
        disabled={disabled}
        sx={{
          flex: "1 1 65%",
          "& .MuiOutlinedInput-notchedOutline": {
            borderColor: alpha(groupColors.preset.border, 0.28),
          },
          "&:hover .MuiOutlinedInput-notchedOutline": {
            borderColor: alpha(groupColors.preset.border, 0.42),
          },
        }}
      />
      <IconButton
        size="small"
        onClick={() => updateHeaderRows((rows) => rows.filter((item) => item.id !== row.id))}
        disabled={disabled}
        sx={{ color: "info.main" }}
      >
        <IconX {...compactActionIconProps} />
      </IconButton>
    </Box>
  );

  const wrapField = (label: string, children: React.ReactNode) => {
    if (!isForm) return children;
    return (
      <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75, width: "100%" }}>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ fontWeight: 600 }}
        >
          {label}
        </Typography>
        {children}
      </Box>
    );
  };

  const renderHttpConfig = () => (
    <>
      {isForm ? (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75, width: "100%" }}>
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
            Headers
          </Typography>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1, width: "100%" }}>
            {showManagedAuthEditor && renderAuthRow()}
            {headerRows.map(renderHeaderRow)}
            <Box sx={{ display: "flex", gap: 1 }}>
                <Button
                  size="small"
                  startIcon={<IconPlus {...actionIconProps} />}
                  onClick={() => updateHeaderRows((rows) => [...rows, createRow()])}
                disabled={disabled}
                variant="outlined"
                sx={{
                  borderColor: alpha(groupColors.preset.border, 0.42),
                  color: groupColors.preset.border,
                }}
              >
                Add Header
              </Button>
                <Button
                  size="small"
                  startIcon={<IconPlus {...actionIconProps} />}
                  onClick={handleAddAuth}
                disabled={disabled || showManagedAuthEditor}
                variant="outlined"
                sx={{
                  borderColor: alpha(groupColors.fixed.border, 0.48),
                  color: groupColors.fixed.border,
                }}
              >
                Add Auth
              </Button>
            </Box>
          </Box>
        </Box>
      ) : wrapField("Headers",
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1, width: "100%" }}>
          {showManagedAuthEditor && renderAuthRow()}
          {headerRows.map(renderHeaderRow)}
          <Box sx={{ display: "flex", gap: 1 }}>
            <Button
              size="small"
              startIcon={<IconPlus {...actionIconProps} />}
              onClick={() => updateHeaderRows((rows) => [...rows, createRow()])}
              disabled={disabled}
              variant="outlined"
              sx={{
                borderColor: alpha(groupColors.preset.border, 0.42),
                color: groupColors.preset.border,
              }}
            >
              Add Header
            </Button>
            <Button
              size="small"
              startIcon={<IconPlus {...actionIconProps} />}
              onClick={handleAddAuth}
              disabled={disabled || showManagedAuthEditor}
              variant="outlined"
              sx={{
                borderColor: alpha(groupColors.fixed.border, 0.48),
                color: groupColors.fixed.border,
              }}
            >
              Add Auth
            </Button>
          </Box>
        </Box>,
      )}
      {wrapField("Body Template",
        <Box sx={{ width: "100%" }}>
          {!isForm && (
            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600, mb: 0.75 }}>
              Body Template
            </Typography>
          )}
          <Box
            sx={{
              display: "flex",
              border: "1px solid",
              borderColor: bodyTemplateError ? "error.main" : "divider",
              borderRadius: 1,
              overflow: "hidden",
              bgcolor: disabled ? "action.disabledBackground" : "background.paper",
            }}
          >
            <Box
              sx={{
                px: 1.25,
                py: 1,
                bgcolor: "action.hover",
                borderRight: "1px solid",
                borderColor: bodyTemplateError ? "error.main" : "divider",
                color: "text.secondary",
                fontFamily: "monospace",
                fontSize: "0.8rem",
                lineHeight: JSON_EDITOR_LINE_HEIGHT,
                textAlign: "right",
                userSelect: "none",
                minWidth: "44px",
              }}
            >
              {Array.from({ length: Math.max(4, bodyTemplateText.split("\n").length) }, (_, index) => (
                <Box key={index}>{index + 1}</Box>
              ))}
            </Box>
            <Box
              component="textarea"
              value={bodyTemplateText}
              onChange={handleBodyTemplateChange}
              onBlur={handleBodyTemplateBlur}
              disabled={disabled}
              placeholder={BODY_TEMPLATE_PLACEHOLDER}
              spellCheck={false}
              sx={{
                flex: 1,
                border: 0,
                outline: 0,
                resize: "vertical",
                minHeight: "132px",
                px: 1.5,
                py: 1,
                fontFamily: "monospace",
                fontSize: "0.85rem",
                lineHeight: JSON_EDITOR_LINE_HEIGHT,
                bgcolor: "transparent",
                color: "text.primary",
                "&::placeholder": {
                  color: "text.disabled",
                  opacity: 1,
                },
              }}
            />
          </Box>
          <Typography
            variant="caption"
            color={bodyTemplateError ? "error" : "text.secondary"}
            sx={{ mt: 0.5, display: "block" }}
          >
            {bodyTemplateError || 'Use `{{prompt}}` as a placeholder for the input text.'}
          </Typography>
        </Box>,
      )}
      {renderProbePanel()}
      {wrapField("Response Path",
        <TextField
          {...(!isForm && { label: "Response Content Path", required: true })}
          fullWidth
          value={config.response_content_path || ""}
          onChange={(e) => handleConfigField("response_content_path", e.target.value)}
          disabled={disabled}
          placeholder="choices.0.message.content"
          helperText={probeResult?.success ? "Dot-notation path to extract answer text — click a row in the probe result above to fill" : ""}
          size="small"
        />,
      )}
      {wrapField("Retrieved Context Path",
        <TextField
          {...(!isForm && { label: "Retrieved Context Path" })}
          fullWidth
          value={String(config.retrieved_context_path || "")}
          onChange={(e) => handleConfigField("retrieved_context_path", e.target.value)}
          disabled={disabled}
          placeholder="rag.chunks"
          helperText="Dot-notation path to the retrieved context chunks used for Accuracy evaluation. Point this to the relevant JSON subtree in the response."
          size="small"
        />
      )}
      {isForm ? (
        <Box>
          <AdvancedToggle showAdvanced={showAdvanced} onToggle={onToggleAdvanced} />
        </Box>
      ) : (
        <AdvancedToggle showAdvanced={showAdvanced} onToggle={onToggleAdvanced} sx={{ alignSelf: "flex-start" }} />
      )}
      <Collapse in={showAdvanced} timeout={300}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: isForm ? 2.5 : 2, pt: isForm ? 0 : 1 }}>
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
          {/* Metadata fields — arbitrary key/path pairs */}
          {(() => {
            return (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
                {!isForm && (
                  <Typography variant="caption" color="text.secondary">
                    Metadata fields — extra values to log from the response. `model` is recommended and can be changed or removed.
                  </Typography>
                )}
                {metadataRows.map((row) => (
                  <Box key={row.id} sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                    <TextField
                      size="small"
                      placeholder="label"
                      value={row.key}
                      onChange={(e) => updateMetadataRows((rows) => rows.map((item) => (
                        item.id === row.id ? { ...item, key: e.target.value } : item
                      )))}
                      disabled={disabled}
                      sx={{ flex: "0 0 140px" }}
                      slotProps={{ input: MONOSPACE_INPUT }}
                    />
                    <TextField
                      size="small"
                      placeholder="dot.notation.path"
                      value={row.value}
                      onChange={(e) => updateMetadataRows((rows) => rows.map((item) => (
                        item.id === row.id ? { ...item, value: e.target.value } : item
                      )))}
                      disabled={disabled}
                      fullWidth
                      slotProps={{ input: MONOSPACE_INPUT }}
                    />
                    <IconButton
                      size="small"
                      onClick={() => updateMetadataRows((rows) => rows.filter((item) => item.id !== row.id))}
                      disabled={disabled}
                    >
                      <IconX {...compactActionIconProps} />
                    </IconButton>
                  </Box>
                ))}
                <Box>
                  <Button
                    size="small"
                    startIcon={<IconPlus {...actionIconProps} />}
                    onClick={() => updateMetadataRows((rows) => [
                      ...rows,
                      createRow(`field${rows.length + 1}`, ""),
                    ])}
                    disabled={disabled}
                    sx={{ mt: 0.5 }}
                  >
                    Add field
                  </Button>
                </Box>
              </Box>
            );
          })()}
        </Box>
      </Collapse>
    </>
  );

  const renderProbePanel = () => {
    const paths = probeResult?.success && probeResult.raw_body !== undefined
      ? flattenPaths(probeResult.raw_body)
      : [];
    return (
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <Box>
          <Button
            variant="contained"
            startIcon={!probing ? <IconFlask2 {...actionIconProps} /> : undefined}
            size="small"
            onClick={handleProbe}
            disabled={disabled || probing || !apiEndpoint || Boolean(apiEndpointError) || Boolean(bodyTemplateError)}
            color="secondary"
          >
            {probing ? <><CircularProgress size={16} sx={{ mr: 1 }} /> Probing...</> : "Probe Endpoint"}
          </Button>
          <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
            Send a request and inspect the raw response before picking a path.
          </Typography>
        </Box>
        {probeResult && !probeResult.success && (
          <Alert severity="error" onClose={() => setProbeResult(null)}>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {probeResult.status_code ? `HTTP ${probeResult.status_code}` : "Probe failed"}
              {probeResult.error ? ` — ${probeResult.error}` : ""}
            </Typography>
            {probeResult.raw_body !== undefined && probeResult.raw_body !== null && (
              <Box
                component="pre"
                sx={{
                  mt: 1,
                  p: 1,
                  bgcolor: "rgba(0,0,0,0.04)",
                  fontFamily: "monospace",
                  fontSize: "0.75rem",
                  maxHeight: 200,
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {typeof probeResult.raw_body === "string"
                  ? probeResult.raw_body
                  : JSON.stringify(probeResult.raw_body, null, 2)}
              </Box>
            )}
          </Alert>
        )}
        {probeResult && probeResult.success && (
          <Alert severity="success" onClose={() => setProbeResult(null)} sx={{ "& .MuiAlert-message": { width: "100%" } }}>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              Got {probeResult.status_code ?? 200} response. Click a field to set it as the response content path.
            </Typography>
            <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 0.25, maxHeight: 240, overflow: "auto" }}>
              {paths.length === 0 && (
                <Typography variant="caption" color="text.secondary">No primitive fields detected in response.</Typography>
              )}
              {paths.map(({ path, value }) => {
                const selected = config.response_content_path === path;
                return (
                  <Box
                    key={path}
                    onClick={() => handlePickPath(path)}
                    sx={{
                      display: "flex",
                      gap: 1,
                      p: 0.5,
                      borderRadius: 0.5,
                      cursor: "pointer",
                      bgcolor: selected ? "primary.light" : "transparent",
                      color: selected ? "primary.contrastText" : "inherit",
                      "&:hover": { bgcolor: selected ? "primary.light" : "action.hover" },
                      fontFamily: "monospace",
                      fontSize: "0.75rem",
                    }}
                  >
                    <Box sx={{ minWidth: "40%", fontWeight: 500, wordBreak: "break-all" }}>{path}</Box>
                    <Box sx={{ flex: 1, color: selected ? "primary.contrastText" : "text.secondary", wordBreak: "break-word" }}>
                      {value.length > 80 ? `${value.slice(0, 80)}…` : value}
                    </Box>
                  </Box>
                );
              })}
            </Box>
            <Box sx={{ mt: 1 }}>
              <Link component="button" variant="caption" onClick={() => setShowRawJson((v) => !v)}>
                {showRawJson ? "Hide raw JSON" : "Show raw JSON"}
              </Link>
            </Box>
            <Collapse in={showRawJson} timeout={200}>
              <Box
                component="pre"
                sx={{
                  mt: 1,
                  p: 1,
                  bgcolor: "rgba(0,0,0,0.04)",
                  fontFamily: "monospace",
                  fontSize: "0.7rem",
                  maxHeight: 300,
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {typeof probeResult.raw_body === "string"
                  ? probeResult.raw_body
                  : JSON.stringify(probeResult.raw_body, null, 2)}
              </Box>
            </Collapse>
          </Alert>
        )}
      </Box>
    );
  };

  const renderAibotsConfig = () =>
    wrapField("API Key",
      <TextField
        {...(!isForm && { label: "API Key", required: true })}
        fullWidth
        type={showApiKey ? "text" : "password"}
        value={config.api_key || ""}
        onChange={(e) => onConfigField("api_key", e.target.value)}
        disabled={disabled}
        size="small"
        slotProps={{
          input: {
            endAdornment: (
              <InputAdornment position="end">
                <IconButton size="small" onClick={() => setShowApiKey((v) => !v)} edge="end" tabIndex={-1}>
                  {showApiKey ? <IconEyeOff size={16} stroke={2} /> : <IconEye size={16} stroke={2} />}
                </IconButton>
              </InputAdornment>
            ),
          },
        }}
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
    );

  const renderTestButton = () => (
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <Box>
          <Button
            variant="contained"
            startIcon={!testing ? <IconPlayerPlay {...actionIconProps} /> : undefined}
            size="small"
            onClick={handleTestConnection}
            disabled={disabled || testing || !apiEndpoint || Boolean(apiEndpointError) || Boolean(bodyTemplateError)}
            color="primary"
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
        {showAdvanced ? "Advanced Configuration" : "Optional: timeout and metadata fields"}
        {showAdvanced ? <IconChevronUp {...compactActionIconProps} /> : <IconChevronDown {...compactActionIconProps} />}
      </Link>
    </Box>
  );
}
