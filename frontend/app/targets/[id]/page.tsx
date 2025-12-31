"use client";

import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  CircularProgress,
  Button,
  TextField,
  Divider,
} from "@mui/material";
import { useParams } from "next/navigation";
import { targetApi } from "@/lib/api";
import { TargetResponse, TargetStats, TargetUpdate, EndpointType } from "@/lib/types";
import DocumentList from "@/components/overview/DocumentList";

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

  const fetchData = async () => {
    try {
      const [targetRes, statsRes] = await Promise.all([
        targetApi.get(targetId),
        targetApi.getStats(targetId),
      ]);
      setTarget(targetRes.data);
      setStats(statsRes.data);
      // Initialize form with fetched data
      setEditForm({
        name: targetRes.data.name,
        agency: targetRes.data.agency || "",
        purpose: targetRes.data.purpose || "",
        target_users: targetRes.data.target_users || "",
        api_endpoint: targetRes.data.api_endpoint || "",
        endpoint_type: targetRes.data.endpoint_type || EndpointType.AIBOTS,
        endpoint_config: targetRes.data.endpoint_config || { api_key: "" },
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

  const handleFormChange = (field: keyof TargetUpdate, value: string) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const handleUpdate = async () => {
    setUpdateLoading(true);
    try {
      await targetApi.update(targetId, editForm);
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

  return (
    <Box>
      {/* Target Details and Knowledge Base Documents - Side by Side */}
      <Box sx={{ display: "flex", gap: 4, flexDirection: { xs: "column", md: "row" }, height: "calc(100vh - 250px)" }}>
        {/* Target Details Form */}
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
            <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
              <Typography variant="subtitle1" color="text.secondary" sx={{ minWidth: "120px" }}>
                API Endpoint:
              </Typography>
              <TextField
                fullWidth
                value={editForm.api_endpoint || ""}
                onChange={(e) => handleFormChange("api_endpoint", e.target.value)}
                size="small"
              />
            </Box>
            <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
              <Typography variant="subtitle1" color="text.secondary" sx={{ minWidth: "120px" }}>
                API Key:
              </Typography>
              <TextField
                fullWidth
                type="password"
                value={editForm.endpoint_config?.api_key || ""}
                onChange={(e) => handleFormChange("endpoint_config", { ...editForm.endpoint_config, api_key: e.target.value } as any)}
                size="small"
              />
            </Box>

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

        {/* Vertical Divider */}
        <Divider orientation="vertical" flexItem sx={{ display: { xs: "none", md: "block" } }} />

        {/* Knowledge Base Documents */}
        <Box sx={{ flex: { md: "0 0 calc(45% - 64px)" }, display: "flex", flexDirection: "column", maxHeight: "100%", overflow: "hidden" }}>
          <DocumentList
            key={documentRefreshKey}
            targetId={targetId}
            hideUploadButton={false}
            maxHeight="100%"
            onUploadEnd={fetchData}
          />
        </Box>
      </Box>

    </Box>
  );
}
