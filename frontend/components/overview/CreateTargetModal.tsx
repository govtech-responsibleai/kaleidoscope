"use client";

import React, { useEffect, useState, useRef } from "react";
import {
  IconBook2,
  IconSettings2,
  IconX,
} from "@tabler/icons-react";
import {
  Dialog,
  Button,
  TextField,
  Box,
  CircularProgress,
  Typography,
  Paper,
  Alert,
  MenuItem,
  IconButton,
} from "@mui/material";
import { targetApi, kbDocumentApi, webSearchApi } from "@/lib/api";
import { TargetCreate } from "@/lib/types";
import ConnectorConfigFields, { getHttpUrlError, validateEndpointConfig } from "./ConnectorConfigFields";
import PendingDocumentsPanel from "./PendingDocumentsPanel";
import { compactActionIconProps, sectionIconProps } from "@/lib/iconStyles";

interface CreateTargetModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const INITIAL_FORM_DATA: TargetCreate = {
  name: "",
  agency: "",
  purpose: "",
  target_users: "",
  api_endpoint: "",
  endpoint_type: "",
  endpoint_config: {},
};

const CREATE_TARGET_STEPS = [
  {
    eyebrow: "Step 1",
    title: "Target setup",
    description: "Add product context and confirm the endpoint configuration.",
    icon: IconSettings2,
  },
  {
    eyebrow: "Step 2",
    title: "Knowledge Base",
    description: "Upload grounding documents before you finish creating the target.",
    icon: IconBook2,
  },
];

export default function CreateTargetModal({
  open,
  onClose,
  onSuccess,
}: CreateTargetModalProps) {
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connectorTypes, setConnectorTypes] = useState<string[]>([]);
  const [connectorTypesError, setConnectorTypesError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const mountedRef = useRef(true);

  const [formData, setFormData] = useState<TargetCreate>(INITIAL_FORM_DATA);

  useEffect(() => {
    mountedRef.current = true;
    if (open) {
      setCurrentStep(0);
      setSelectedFiles([]);
      setUploadProgress(0);
      setUploadingFiles(false);
      setError(null);
      setShowAdvanced(false);
      setFormData(INITIAL_FORM_DATA);
      setConnectorTypes([]);
      setConnectorTypesError(null);
      targetApi.getConnectorTypes().then((res) => {
        if (!mountedRef.current) return;
        if (res.data.length === 0) {
          setConnectorTypes([]);
          setConnectorTypesError("No connector types are available in this deployment.");
          setFormData((prev) => ({ ...prev, endpoint_type: "" }));
          return;
        }
        setConnectorTypes(res.data);
        setFormData((prev) => ({
          ...prev,
          endpoint_type: prev.endpoint_type && res.data.includes(prev.endpoint_type)
            ? prev.endpoint_type
            : res.data[0],
        }));
      }).catch(() => {
        if (!mountedRef.current) return;
        setConnectorTypes([]);
        setConnectorTypesError("Failed to load available connector types. Reload and try again.");
        setFormData((prev) => ({ ...prev, endpoint_type: "" }));
      });
    }
    return () => { mountedRef.current = false; };
  }, [open]);

  const endpointType = formData.endpoint_type || "";

  const handleChange = (field: keyof TargetCreate) => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData({ ...formData, [field]: event.target.value });
  };

  const handleEndpointTypeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      endpoint_type: event.target.value,
      endpoint_config: {},
    });
    setShowAdvanced(false);
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const fileArray = Array.from(files);
      const supportedFiles = fileArray.filter((file) => {
        const ext = file.name.split(".").pop()?.toLowerCase();
        return ["pdf", "docx", "txt", "md"].includes(ext || "");
      });

      if (supportedFiles.length < fileArray.length) {
        setError("Some files were skipped. Only PDF, DOCX, TXT, and MD files are supported.");
      } else {
        setError(null);
      }

      setSelectedFiles((prev) => [...prev, ...supportedFiles]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const validateStepOne = (): string | null => {
    if (!formData.name.trim()) {
      return "Name is required.";
    }
    if (formData.api_endpoint && !endpointType) {
      return "Available connector types could not be loaded. Try again before saving this target.";
    }
    if (endpointType === "http" && apiEndpointError) {
      return apiEndpointError;
    }

    const configError = endpointType
      ? validateEndpointConfig(endpointType, formData.endpoint_config || {})
      : null;
    if (configError) {
      return configError;
    }

    return null;
  };

  const handleNext = () => {
    const validationError = validateStepOne();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setCurrentStep(1);
  };

  const handleSubmit = async () => {
    const validationError = validateStepOne();
    if (validationError) {
      setError(validationError);
      setCurrentStep(0);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const submitData: TargetCreate = {
        ...formData,
        endpoint_type: formData.api_endpoint ? formData.endpoint_type : undefined,
        endpoint_config: formData.api_endpoint ? formData.endpoint_config : undefined,
      };

      const targetResponse = await targetApi.create(submitData);
      const targetId = targetResponse.data.id;

      if (selectedFiles.length > 0) {
        setUploadingFiles(true);
        const totalFiles = selectedFiles.length;

        for (let i = 0; i < totalFiles; i++) {
          try {
            await kbDocumentApi.upload(targetId, selectedFiles[i]);
            setUploadProgress(((i + 1) / totalFiles) * 100);
          } catch (uploadError) {
            console.error(`Failed to upload ${selectedFiles[i].name}:`, uploadError);
            setError(`Failed to upload ${selectedFiles[i].name}. Other files uploaded successfully.`);
          }
        }
      }

      webSearchApi.trigger(targetId).catch((err) =>
        console.warn("Web search trigger failed:", err)
      );

      setFormData(INITIAL_FORM_DATA);
      setSelectedFiles([]);
      setUploadProgress(0);
      setUploadingFiles(false);
      setShowAdvanced(false);
      setCurrentStep(0);

      onSuccess();
      onClose();
    } catch (error) {
      console.error("Failed to create target:", error);
      setError("Failed to create target. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading && !uploadingFiles) {
      onClose();
    }
  };

  const config = formData.endpoint_config || {};
  const disabled = loading || uploadingFiles;
  const endpointConfigBlocked = Boolean(connectorTypesError);
  const connectorTypesReady = connectorTypes.length > 0;
  const apiEndpointError = endpointType === "http" ? getHttpUrlError(formData.api_endpoint) : null;

  const renderStepOne = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {connectorTypesError && (
        <Alert severity="error">
          {connectorTypesError}
        </Alert>
      )}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
          gap: 2,
        }}
      >
        <TextField
          label="Name"
          required
          fullWidth
          value={formData.name}
          onChange={handleChange("name")}
          disabled={disabled}
        />
        <TextField
          label="Agency"
          fullWidth
          value={formData.agency}
          onChange={handleChange("agency")}
          disabled={disabled}
        />
      </Box>
      <TextField
        label="Purpose"
        fullWidth
        multiline
        rows={2}
        value={formData.purpose}
        onChange={handleChange("purpose")}
        disabled={disabled}
      />
      <TextField
        label="Target Users"
        fullWidth
        value={formData.target_users}
        onChange={handleChange("target_users")}
        disabled={disabled}
      />

      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          Endpoint Configuration
        </Typography>
        <Paper variant="outlined" sx={{ p: 2, bgcolor: "grey.50", display: "flex", flexDirection: "column", gap: 2 }}>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
            <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
              Endpoint Type
            </Typography>

            <TextField
              select
              fullWidth
              value={endpointType}
              onChange={handleEndpointTypeChange}
              disabled={disabled || endpointConfigBlocked || !connectorTypesReady || connectorTypes.length <= 1}
              size="small"
            >
              {connectorTypes.map((t) => (
                <MenuItem key={t} value={t}>{t}</MenuItem>
              ))}
            </TextField>
          </Box>

          {endpointType === "http" ? (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
              <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                URL
              </Typography>
              <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
                <TextField
                  select
                  size="small"
                  value={String(config.method || "POST")}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      endpoint_config: { ...prev.endpoint_config, method: e.target.value },
                    }))
                  }
                  disabled={disabled}
                  sx={{ width: 110 }}
                >
                  {["POST", "GET", "PUT", "PATCH"].map((method) => (
                    <MenuItem key={method} value={method}>{method}</MenuItem>
                  ))}
                </TextField>
                <TextField
                  fullWidth
                  value={formData.api_endpoint}
                  onChange={handleChange("api_endpoint")}
                  disabled={disabled}
                  placeholder="https://api.example.com/v1/chat/completions"
                  size="small"
                  error={Boolean(apiEndpointError)}
                  helperText={apiEndpointError || "Enter a valid http:// or https:// endpoint URL."}
                />
              </Box>
            </Box>
          ) : (
            <TextField
              label="API Endpoint URL"
              fullWidth
              value={formData.api_endpoint}
              onChange={handleChange("api_endpoint")}
              disabled={disabled}
              placeholder="https://api.example.com/v1/chat/completions"
              size="small"
            />
          )}

          {endpointType ? (
            <ConnectorConfigFields
              endpointType={endpointType}
              config={config}
              apiEndpoint={formData.api_endpoint}
              targetId={undefined}
              onConfigField={(field, value) =>
                setFormData((prev) => ({
                  ...prev,
                  endpoint_config: { ...prev.endpoint_config, [field]: value },
                }))
              }
              onConfigReplace={(newConfig) =>
                setFormData((prev) => ({ ...prev, endpoint_config: newConfig }))
              }
              showAdvanced={showAdvanced}
              onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
              disabled={disabled || endpointConfigBlocked}
            />
          ) : (
            <Alert severity="warning">
              Load the available connector types before configuring an endpoint.
            </Alert>
          )}
        </Paper>
      </Box>
    </Box>
  );

  const renderStepTwo = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <Alert severity="info">
        Knowledge Base Documents improve question generation quality. Your evaluations will be grounded in these provided documents.
      </Alert>
      <PendingDocumentsPanel
        selectedFiles={selectedFiles}
        disabled={disabled}
        uploadingFiles={uploadingFiles}
        uploadProgress={uploadProgress}
        onFileSelect={handleFileSelect}
        onRemoveFile={handleRemoveFile}
      />
    </Box>
  );

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          height: { xs: "calc(100vh - 32px)", md: "min(860px, calc(100vh - 64px))" },
          display: "flex",
          flexDirection: { xs: "column", md: "row" },
          overflow: "hidden",
          position: "relative",
        },
      }}
    >
      <Box
        sx={{
          position: "absolute",
          top: 16,
          right: 16,
          zIndex: 1,
        }}
      >
        <IconButton
          onClick={handleClose}
          disabled={disabled}
          size="small"
          aria-label="Close create target dialog"
          sx={{
            "&:hover": {
              bgcolor: "transparent",
            },
          }}
        >
          <IconX {...compactActionIconProps} />
        </IconButton>
      </Box>

      <Box
        sx={{
          width: { xs: "100%", md: 290 },
          flexShrink: 0,
          px: { xs: 2.5, md: 3.5 },
          py: { xs: 3, md: 3.5 },
          bgcolor: "grey.100",
          borderRight: { xs: 0, md: 1 },
          borderBottom: { xs: 1, md: 0 },
          borderColor: "divider",
          display: "flex",
          flexDirection: "column",
          gap: 3,
        }}
      >
        <Box sx={{ pr: { xs: 5, md: 4 } }}>
          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
            Create new target application
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Configure your Target Application. Provide as much information as possible to enhance evaluation quality.
          </Typography>
        </Box>

        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
          {CREATE_TARGET_STEPS.map((step, index) => {
            const isActive = currentStep === index;
            const isComplete = currentStep > index;
            const StepIcon = step.icon;

            return (
              <Box
                key={step.title}
                sx={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 1.5,
                  px: 1.5,
                  py: 1.5,
                  borderRadius: 2.5,
                  border: 1,
                  borderColor: isActive ? "primary.main" : isComplete ? "primary.light" : "divider",
                  bgcolor: isActive ? "rgba(25, 118, 210, 0.08)" : isComplete ? "rgba(25, 118, 210, 0.04)" : "rgba(255, 255, 255, 0.66)",
                  boxShadow: isActive ? 2 : "none",
                  transition: "all 160ms ease",
                }}
              >
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: 2,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: isActive || isComplete ? "primary.contrastText" : "text.secondary",
                    bgcolor: isActive || isComplete ? "primary.main" : "grey.200",
                    flexShrink: 0,
                  }}
                >
                  <StepIcon {...sectionIconProps} />
                </Box>
                <Box sx={{ minWidth: 0 }}>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: "block", letterSpacing: 0.5, textTransform: "uppercase" }}
                  >
                    {step.eyebrow}
                  </Typography>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    {step.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.35 }}>
                    {step.description}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Box>
      </Box>

      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
          bgcolor: "background.paper",
        }}
      >
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            px: { xs: 2.5, md: 4 },
            py: { xs: 3, md: 4 },
            pt: { xs: 7, md: 4 },
          }}
        >
          <Box sx={{ width: "100%" }}>
            <Box sx={{ mb: 3 }}>
              <Typography variant="h5" sx={{ fontWeight: 700 }}>
                {CREATE_TARGET_STEPS[currentStep].title}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                {CREATE_TARGET_STEPS[currentStep].description}
              </Typography>
            </Box>

            {currentStep === 0 ? renderStepOne() : renderStepTwo()}
          </Box>
        </Box>

        <Box
          sx={{
            px: { xs: 2.5, md: 4 },
            pb: { xs: 3, md: 4 },
            pt: 2,
            display: "flex",
            justifyContent: currentStep === 0 ? "flex-end" : "space-between",
            alignItems: "center",
            gap: 2,
            bgcolor: "background.paper",
          }}
        >
          <Box
            sx={{
              width: "100%",
              display: "flex",
              justifyContent: currentStep === 0 ? "flex-end" : "space-between",
              alignItems: "center",
              gap: 2,
            }}
          >
            {currentStep === 1 && (
              <Button onClick={() => setCurrentStep(0)} disabled={disabled}>
                Back
              </Button>
            )}
            {currentStep === 0 ? (
              <Button
                onClick={handleNext}
                variant="contained"
                disabled={disabled || !formData.name || endpointConfigBlocked}
              >
                Next
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                variant="contained"
                disabled={disabled}
              >
                {disabled ? (
                  <CircularProgress size={24} />
                ) : selectedFiles.length > 0 ? (
                  "Create Target"
                ) : (
                  "Create Without Documents"
                )}
              </Button>
            )}
          </Box>
        </Box>
      </Box>
    </Dialog>
  );
}
