"use client";

import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  CircularProgress,
  Divider,
  Stack,
  Typography,
} from "@mui/material";

import ConnectedModelsPanel from "@/components/providers/ConnectedModelsPanel";
import ProviderRow from "@/components/providers/ProviderRow";
import { getApiErrorMessage, providerApi } from "@/lib/api";
import { ProviderSetupResponse } from "@/lib/types";

export default function ProvidersPage() {
  const [setup, setSetup] = useState<ProviderSetupResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Record<string, string>>>({});
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({});

  const loadSetup = async () => {
    setLoading(true);
    try {
      const response = await providerApi.getSetup();
      setSetup(response.data);
      setError(null);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load provider setup."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSetup();
  }, []);

  const updateDraft = (scopeKey: string, fieldKey: string, value: string) => {
    setDrafts((prev) => ({
      ...prev,
      [scopeKey]: {
        ...(prev[scopeKey] || {}),
        [fieldKey]: value,
      },
    }));
  };

  const toggleExpanded = (key: string) => {
    setExpandedKeys((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const saveProvider = async (providerKey: string) => {
    const values = drafts[providerKey] || {};
    setSavingKey(providerKey);
    try {
      await providerApi.upsertProvider(providerKey, values);
      await loadSetup();
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to save provider credentials."));
    } finally {
      setSavingKey(null);
    }
  };

  const deleteProvider = async (providerKey: string) => {
    setSavingKey(providerKey);
    try {
      await providerApi.deleteProvider(providerKey);
      await loadSetup();
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to remove provider credentials."));
    } finally {
      setSavingKey(null);
    }
  };

  const saveService = async (serviceKey: string) => {
    const values = drafts[serviceKey] || {};
    setSavingKey(serviceKey);
    try {
      await providerApi.upsertService(serviceKey, values);
      await loadSetup();
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to save service credentials."));
    } finally {
      setSavingKey(null);
    }
  };

  const deleteService = async (serviceKey: string) => {
    setSavingKey(serviceKey);
    try {
      await providerApi.deleteService(serviceKey);
      await loadSetup();
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to remove service credentials."));
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" py={8}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Providers
        </Typography>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      {setup && (
        <Box
          sx={{
            display: "flex",
            gap: 4,
            flexDirection: { xs: "column", md: "row" },
            alignItems: "flex-start",
          }}
        >
          <Box sx={{ flex: { md: "0 0 58%" }, minWidth: 0 }}>
            <Stack spacing={3}>
              <Box>
                <Typography fontWeight={700} variant="h6">
                  Model Providers
                </Typography>
                <Typography color="text.secondary" variant="body2">
                  Connect your model providers via API keys.
                </Typography>
              </Box>
              <Stack spacing={1.5}>
                {setup.providers.map((provider) => (
                  <ProviderRow
                    key={provider.key}
                    drafts={drafts[provider.key] || {}}
                    entry={provider}
                    expanded={Boolean(expandedKeys[provider.key])}
                    onChange={(fieldKey, value) => updateDraft(provider.key, fieldKey, value)}
                    onDelete={() => void deleteProvider(provider.key)}
                    onSave={() => void saveProvider(provider.key)}
                    onToggle={() => toggleExpanded(provider.key)}
                    saving={savingKey === provider.key}
                  />
                ))}
              </Stack>

              <Box>
                <Typography fontWeight={700} variant="h6">
                  Services
                </Typography>
                <Typography color="text.secondary" variant="body2">
                  Add support tools like search separately from your model providers.
                </Typography>
              </Box>
              <Stack spacing={1.5}>
                {setup.services.map((service) => (
                  <ProviderRow
                    key={service.key}
                    drafts={drafts[service.key] || {}}
                    entry={service}
                    expanded={Boolean(expandedKeys[service.key])}
                    isService
                    onChange={(fieldKey, value) => updateDraft(service.key, fieldKey, value)}
                    onDelete={() => void deleteService(service.key)}
                    onSave={() => void saveService(service.key)}
                    onToggle={() => toggleExpanded(service.key)}
                    saving={savingKey === service.key}
                  />
                ))}
              </Stack>
            </Stack>
          </Box>

          <Divider
            orientation="vertical"
            flexItem
            sx={{ display: { xs: "none", md: "block" } }}
          />

          <Box sx={{ flex: 1, minWidth: 0 }}>
            <ConnectedModelsPanel
              defaults={setup.defaults}
              providers={setup.providers}
              validEmbeddingModels={setup.valid_embedding_models}
              validModels={setup.valid_models}
            />
          </Box>
        </Box>
      )}
    </Stack>
  );
}
