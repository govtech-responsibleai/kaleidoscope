"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Box,
  Divider,
  Typography,
  CircularProgress,
  Button,
  TextField,
  Paper,
  MenuItem,
} from "@mui/material";
import { useParams } from "next/navigation";
import { targetApi, webSearchApi } from "@/lib/api";
import { TargetResponse, TargetStats, TargetUpdate } from "@/lib/types";
import DocumentList from "@/components/overview/DocumentList";
import ConnectorConfigFields, { getHttpUrlError, validateEndpointConfig } from "@/components/overview/ConnectorConfigFields";

interface WebDocumentSearchResult {
  results?: unknown[];
}

interface WebDocument {
  results?: WebDocumentSearchResult;
}

function DetailsField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
      <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
        {label}
      </Typography>
      {children}
    </Box>
  );
}

export default function TargetOverview() {
  const params = useParams();
  const targetId = parseInt(params.id as string);

  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [documentRefreshKey] = useState(0);
  const [editForm, setEditForm] = useState<TargetUpdate>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [updateLoading, setUpdateLoading] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [hasWebContext, setHasWebContext] = useState<boolean | null>(null);
  const [connectorTypes, setConnectorTypes] = useState<string[]>([]);
  const [connectorTypesError, setConnectorTypesError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Fetch connector types once on mount (they don't change at runtime)
  useEffect(() => {
    targetApi.getConnectorTypes()
      .then((res) => {
        setConnectorTypes(res.data);
        setConnectorTypesError(
          res.data.length === 0
            ? "No connector types are available in this deployment."
            : null,
        );
      })
      .catch(() => {
        setConnectorTypes([]);
        setConnectorTypesError("Failed to load available connector types. Reload before editing connector settings.");
      });
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const [targetRes, statsRes] = await Promise.all([
        targetApi.get(targetId),
        targetApi.getStats(targetId),
      ]);
      setTarget(targetRes.data);
      setStats(statsRes.data);
      webSearchApi.listDocuments(targetId).then((res) => {
        const webDocs = res.data as WebDocument[];
        setHasWebContext(webDocs.length > 0 && webDocs.some((d) => (d.results?.results?.length ?? 0) > 0));
      }).catch(() => setHasWebContext(false));
      setEditForm({
        name: targetRes.data.name,
        agency: targetRes.data.agency || "",
        purpose: targetRes.data.purpose || "",
        target_users: targetRes.data.target_users || "",
        api_endpoint: targetRes.data.api_endpoint || "",
        endpoint_type: targetRes.data.endpoint_type || "",
        endpoint_config: targetRes.data.endpoint_config || {},
      });
      setHasChanges(false);
    } catch (error) {
      console.error("Failed to fetch target data:", error);
    } finally {
      setLoading(false);
    }
  }, [targetId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleFormChange = (field: keyof TargetUpdate, value: unknown) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const handleEndpointTypeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEditForm((prev) => ({
      ...prev,
      endpoint_type: event.target.value,
      endpoint_config: {},
    }));
    setHasChanges(true);
    setShowAdvanced(false);
  };

  const handleUpdate = async () => {
    const currentEndpointType = editForm.endpoint_type || "";

    if (connectorTypesError) {
      setUpdateError("Available connector types could not be loaded. Reload before updating this target.");
      return;
    }
    if (currentEndpointType === "http" && apiEndpointError) {
      setUpdateError(apiEndpointError);
      return;
    }

    const configError = currentEndpointType
      ? validateEndpointConfig(currentEndpointType, editForm.endpoint_config || {})
      : null;
    if (configError) {
      setUpdateError(configError);
      return;
    }

    setUpdateLoading(true);
    setUpdateError(null);
    try {
      const webSearchFields: (keyof TargetUpdate)[] = ["name", "agency", "purpose", "target_users"];
      const relevantFieldChanged = target && webSearchFields.some(
        (field) => editForm[field] !== (target[field as keyof TargetResponse] || "")
      );

      await targetApi.update(targetId, editForm);

      if (relevantFieldChanged) {
        setHasWebContext(null);
        webSearchApi.trigger(targetId)
          .then(() => {
            setTimeout(() => {
              webSearchApi.listDocuments(targetId).then((res) => {
                const webDocs = res.data as WebDocument[];
                setHasWebContext(webDocs.length > 0 && webDocs.some((d) => (d.results?.results?.length ?? 0) > 0));
              }).catch(() => setHasWebContext(false));
            }, 5000);
          })
          .catch((err) => console.warn("Web search trigger failed:", err));
      }

      await fetchData();
    } catch (error) {
      console.error("Failed to update target:", error);
    } finally {
      setUpdateLoading(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="30vh">
        <CircularProgress />
      </Box>
    );
  }

  if (!target || !stats) {
    return null;
  }

  const endpointType = editForm.endpoint_type || "";
  const config = editForm.endpoint_config || {};
  const endpointTypeOptions = connectorTypes.length > 0
    ? connectorTypes
    : endpointType
      ? [endpointType]
      : [];
  const apiEndpointError = endpointType === "http" ? getHttpUrlError(editForm.api_endpoint) : null;

  return (
    <Box>
      <Box
        sx={{
          display: "flex",
          gap: 4,
          flexDirection: { xs: "column", md: "row" },
          alignItems: "stretch",
          minHeight: "calc(100vh - 250px)",
        }}
      >
        <Box
          sx={{
            flex: { md: "0 0 55%" },
            pl: 2,
            pb: 6,
          }}
        >
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" fontWeight={600}>
              Target Details
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
              Created: {new Date(target.created_at).toLocaleDateString()} | Updated: {target.updated_at ? new Date(target.updated_at).toLocaleDateString() : "--"}
            </Typography>
          </Box>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
            <DetailsField label="Agency">
              <TextField
                fullWidth
                value={editForm.agency || ""}
                onChange={(e) => handleFormChange("agency", e.target.value)}
                size="small"
              />
            </DetailsField>
            <DetailsField label="Purpose">
              <TextField
                fullWidth
                multiline
                rows={3}
                value={editForm.purpose || ""}
                onChange={(e) => handleFormChange("purpose", e.target.value)}
                size="small"
              />
            </DetailsField>
            <DetailsField label="Target Users">
              <TextField
                fullWidth
                multiline
                rows={2}
                value={editForm.target_users || ""}
                onChange={(e) => handleFormChange("target_users", e.target.value)}
                size="small"
              />
            </DetailsField>

            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                Endpoint Configuration
              </Typography>
              <Paper variant="outlined" sx={{ p: 2, bgcolor: "grey.50", display: "flex", flexDirection: "column", gap: 2.5 }}>
              {connectorTypesError && (
                <Typography variant="body2" color="error">
                  {connectorTypesError}
                </Typography>
              )}

                <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    Endpoint Type
                  </Typography>
                  <TextField
                    select
                    fullWidth
                    value={endpointType}
                    onChange={handleEndpointTypeChange}
                    disabled={Boolean(connectorTypesError) || endpointTypeOptions.length === 0}
                    size="small"
                  >
                    {endpointTypeOptions.map((t) => (
                      <MenuItem key={t} value={t}>{t}</MenuItem>
                    ))}
                  </TextField>
                </Box>
              {endpointType === "http" ? (
                <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    URL
                  </Typography>
                  <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start", width: "100%" }}>
                    <TextField
                      select
                      size="small"
                      value={String(config.method || "POST")}
                      onChange={(e) =>
                        handleFormChange("endpoint_config", {
                          ...config,
                          method: e.target.value,
                        })
                      }
                      sx={{ width: 110 }}
                    >
                      {["POST", "GET", "PUT", "PATCH"].map((method) => (
                        <MenuItem key={method} value={method}>{method}</MenuItem>
                      ))}
                    </TextField>
                    <TextField
                      fullWidth
                      value={editForm.api_endpoint || ""}
                      onChange={(e) => handleFormChange("api_endpoint", e.target.value)}
                      size="small"
                      placeholder="https://api.example.com/v1/chat/completions"
                      error={Boolean(apiEndpointError)}
                      helperText={apiEndpointError || "Enter a valid http:// or https:// endpoint URL."}
                    />
                  </Box>
                </Box>
              ) : (
                <DetailsField label="API Endpoint">
                  <TextField
                    fullWidth
                    value={editForm.api_endpoint || ""}
                    onChange={(e) => handleFormChange("api_endpoint", e.target.value)}
                    size="small"
                    placeholder="https://api.example.com/v1/chat/completions"
                  />
                </DetailsField>
              )}

              {endpointType ? (
                <ConnectorConfigFields
                  endpointType={endpointType}
                  config={config}
                  targetId={targetId}
                  apiEndpoint={editForm.api_endpoint}
                  onConfigField={(field, value) => {
                    setEditForm((prev) => ({
                      ...prev,
                      endpoint_config: { ...prev.endpoint_config, [field]: value },
                    }));
                    setHasChanges(true);
                  }}
                  onConfigReplace={(newConfig) => {
                    handleFormChange("endpoint_config", newConfig);
                  }}
                  showAdvanced={showAdvanced}
                  onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
                  onJsonError={setUpdateError}
                  variant="form"
                  disabled={Boolean(connectorTypesError)}
                />
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Load the available connector types before editing endpoint-specific settings.
                </Typography>
              )}
              </Paper>
            </Box>

            {updateError && (
              <Typography variant="body2" color="error">{updateError}</Typography>
            )}

            <Button
              variant="outlined"
              onClick={handleUpdate}
              disabled={!hasChanges || updateLoading || Boolean(connectorTypesError)}
              sx={{ mt: 1, alignSelf: "flex-end" }}
            >
              {updateLoading ? <CircularProgress size={24} /> : "Update"}
            </Button>
          </Box>
        </Box>

        <Divider
          orientation="vertical"
          flexItem
          sx={{
            display: { xs: "none", md: "block" },
            alignSelf: "stretch",
            my: 0,
          }}
        />

        <Box
          sx={{
            flex: { md: "0 0 calc(45% - 64px)" },
            display: "flex",
            flexDirection: "column",
            gap: 1,
          }}
        >
          <DocumentList
            key={documentRefreshKey}
            targetId={targetId}
            hideUploadButton={false}
            onUploadEnd={fetchData}
          />

          {hasWebContext !== null && (
            <Typography
              variant="caption"
              sx={{
                mt: 1,
                display: "flex",
                alignItems: "center",
                gap: 0.75,
                color: hasWebContext ? "success.main" : "text.disabled",
              }}
            >
              <Box
                component="span"
                sx={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  bgcolor: hasWebContext ? "success.main" : "text.disabled",
                  flexShrink: 0,
                }}
              />
              {hasWebContext ? "Additional web context retrieved." : "Additional web context not retrieved."}
            </Typography>
          )}
        </Box>
      </Box>
    </Box>
  );
}
