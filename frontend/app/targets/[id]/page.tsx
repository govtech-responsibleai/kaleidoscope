"use client";

import React, { useEffect, useState } from "react";
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
import ConnectorConfigFields, { validateEndpointConfig } from "@/components/overview/ConnectorConfigFields";

export default function TargetOverview() {
  const params = useParams();
  const targetId = parseInt(params.id as string);

  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [documentRefreshKey, setDocumentRefreshKey] = useState(0);
  const [editForm, setEditForm] = useState<TargetUpdate>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [updateLoading, setUpdateLoading] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [hasWebContext, setHasWebContext] = useState<boolean | null>(null);
  const [connectorTypes, setConnectorTypes] = useState<string[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Fetch connector types once on mount (they don't change at runtime)
  useEffect(() => {
    targetApi.getConnectorTypes()
      .then((res) => setConnectorTypes(res.data))
      .catch(() => setConnectorTypes(["http"]));
  }, []);

  const fetchData = async () => {
    try {
      const [targetRes, statsRes] = await Promise.all([
        targetApi.get(targetId),
        targetApi.getStats(targetId),
      ]);
      setTarget(targetRes.data);
      setStats(statsRes.data);
      webSearchApi.listDocuments(targetId).then((res) => {
        const webDocs = res.data as any[];
        setHasWebContext(webDocs.length > 0 && webDocs.some((d: any) => d.results?.results?.length > 0));
      }).catch(() => setHasWebContext(false));
      setEditForm({
        name: targetRes.data.name,
        agency: targetRes.data.agency || "",
        purpose: targetRes.data.purpose || "",
        target_users: targetRes.data.target_users || "",
        api_endpoint: targetRes.data.api_endpoint || "",
        endpoint_type: targetRes.data.endpoint_type || "http",
        endpoint_config: targetRes.data.endpoint_config || {},
      });
      setHasChanges(false);
    } catch (error) {
      console.error("Failed to fetch target data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [targetId]);

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
    const endpointType = editForm.endpoint_type || "http";
    const configError = validateEndpointConfig(endpointType, editForm.endpoint_config || {});
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
                const webDocs = res.data as any[];
                setHasWebContext(webDocs.length > 0 && webDocs.some((d: any) => d.results?.results?.length > 0));
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

  const endpointType = editForm.endpoint_type || "http";
  const config = editForm.endpoint_config || {};

  return (
    <Box>
      <Box sx={{ display: "flex", gap: 4, flexDirection: { xs: "column", md: "row" }, height: "calc(100vh - 250px)" }}>
        <Box sx={{ flex: { md: "0 0 55%" }, pl: 2 }}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" fontWeight={600}>
              Target Details
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
              Created: {new Date(target.created_at).toLocaleDateString()} | Updated: {target.updated_at ? new Date(target.updated_at).toLocaleDateString() : "--"}
            </Typography>
          </Box>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
            <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
              <Typography variant="subtitle1" color="text.secondary" sx={{ minWidth: "120px" }}>
                Agency:
              </Typography>
              <TextField
                fullWidth
                value={editForm.agency || ""}
                onChange={(e) => handleFormChange("agency", e.target.value)}
                size="small"
              />
            </Box>
            <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
              <Typography variant="subtitle1" color="text.secondary" sx={{ minWidth: "120px", pt: 1 }}>
                Purpose:
              </Typography>
              <TextField
                fullWidth
                multiline
                rows={5}
                value={editForm.purpose || ""}
                onChange={(e) => handleFormChange("purpose", e.target.value)}
                size="small"
              />
            </Box>
            <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
              <Typography variant="subtitle1" color="text.secondary" sx={{ minWidth: "120px", pt: 1 }}>
                Target Users:
              </Typography>
              <TextField
                fullWidth
                multiline
                rows={3}
                value={editForm.target_users || ""}
                onChange={(e) => handleFormChange("target_users", e.target.value)}
                size="small"
              />
            </Box>

            <Paper variant="outlined" sx={{ p: 2, bgcolor: "grey.50", display: "flex", flexDirection: "column", gap: 2.5 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Endpoint Configuration
              </Typography>

              <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
                <Typography variant="subtitle1" color="text.secondary" sx={{ minWidth: "120px" }}>
                  Type:
                </Typography>
                <TextField
                  select
                  fullWidth
                  value={endpointType}
                  onChange={handleEndpointTypeChange}
                  disabled={connectorTypes.length <= 1}
                  size="small"
                >
                  {connectorTypes.map((t) => (
                    <MenuItem key={t} value={t}>{t}</MenuItem>
                  ))}
                </TextField>
              </Box>
              <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
                <Typography variant="subtitle1" color="text.secondary" sx={{ minWidth: "120px" }}>
                  API Endpoint:
                </Typography>
                <TextField
                  fullWidth
                  value={editForm.api_endpoint || ""}
                  onChange={(e) => handleFormChange("api_endpoint", e.target.value)}
                  size="small"
                  placeholder="https://api.example.com/v1/chat/completions"
                />
              </Box>

              <ConnectorConfigFields
                endpointType={endpointType}
                config={config}
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
              />
            </Paper>

            {updateError && (
              <Typography variant="body2" color="error">{updateError}</Typography>
            )}

            <Button
              variant="outlined"
              onClick={handleUpdate}
              disabled={!hasChanges || updateLoading}
              sx={{ mt: 1, alignSelf: "flex-end" }}
            >
              {updateLoading ? <CircularProgress size={24} /> : "Update"}
            </Button>
          </Box>
        </Box>

        <Divider orientation="vertical" flexItem sx={{ display: { xs: "none", md: "block" } }} />

        <Box sx={{ flex: { md: "0 0 calc(45% - 64px)" }, display: "flex", flexDirection: "column", maxHeight: "100%", gap: 1 }}>
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
