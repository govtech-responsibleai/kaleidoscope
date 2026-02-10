"use client";

import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Card,
  CardContent,
  CardActions,
  CircularProgress,
  IconButton,
  Alert,
  TextField,
  Chip,
  Collapse,
} from "@mui/material";
import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
  Edit as EditIcon,
  Save as SaveIcon,
  Upload as UploadIcon,
  AutoAwesome as AutoAwesomeIcon,
  Groups as GroupsIcon,
} from "@mui/icons-material";
import { jobApi, personaApi, questionApi } from "@/lib/api";
import { PersonaResponse, JobStatus, PersonaUpdate } from "@/lib/types";
import { DEFAULT_PERSONA_COUNT, JOB_POLLING_INTERVAL } from "@/lib/constants";

interface GenerateEvalsModalProps {
  open: boolean;
  onClose: () => void;
  targetId: number;
  onSuccess: () => void;
  onJobLaunched?: (jobId: number) => void;
  onQuestionsUploaded?: () => Promise<void>;
}

export default function GenerateEvalsModal({
  open,
  onClose,
  targetId,
  onSuccess,
  onJobLaunched,
  onQuestionsUploaded,
}: GenerateEvalsModalProps) {
  const [step, setStep] = useState(-1); // -1: Choose mode, 0: Select Personas, 1: Generate Questions, 2: Upload file
  const [selectedMode, setSelectedMode] = useState<"generate" | null>(null);
  const [personaSource, setPersonaSource] = useState<"ai" | "general" | null>(null);
  const [personas, setPersonas] = useState<PersonaResponse[]>([]);
  const [rejectedPersonaIds, setRejectedPersonaIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Upload mode state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Edit mode state
  const [editingPersonaId, setEditingPersonaId] = useState<number | null>(null);
  const [editedTitle, setEditedTitle] = useState("");
  const [editedInfo, setEditedInfo] = useState("");
  const [editedStyle, setEditedStyle] = useState("");
  const [editedUseCase, setEditedUseCase] = useState("");
  const [savingPersonaId, setSavingPersonaId] = useState<number | null>(null);

  const generatePersonas = async (count = DEFAULT_PERSONA_COUNT) => {
    setStep(0);
    setPersonaSource("ai");
    setLoading(true);
    setError(null);
    try {
      const jobResponse = await jobApi.createPersonaJob(targetId, {
        count_requested: count,
      });

      // Poll for completion
      const jobId = jobResponse.data.id;
      let completed = false;

      while (!completed) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const statusResponse = await jobApi.get(jobId);

        if (statusResponse.data.status === JobStatus.COMPLETED) {
          completed = true;
          const personasResponse = await jobApi.getPersonas(jobId);
          setPersonas(prev => [...prev, ...personasResponse.data]);
        } else if (statusResponse.data.status === JobStatus.FAILED) {
          throw new Error("Persona generation failed");
        }
      }
    } catch (error) {
      console.error("Failed to generate personas:", error);
      setError("Failed to generate personas. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const sampleNemotronPersonas = async (count = DEFAULT_PERSONA_COUNT) => {
    setStep(0);
    setPersonaSource("general");
    setLoading(true);
    setError(null);
    try {
      const response = await personaApi.sampleNemotron(targetId, count);
      setPersonas(prev => [...prev, ...response.data]);
    } catch (error) {
      console.error("Failed to sample Nemotron personas:", error);
      setError("Failed to sample general personas. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleRejectPersona = (personaId: number) => {
    setRejectedPersonaIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(personaId)) {
        newSet.delete(personaId);
      } else {
        newSet.add(personaId);
      }
      return newSet;
    });
  };

  const handleStartEdit = (persona: PersonaResponse) => {
    setEditingPersonaId(persona.id);
    setEditedTitle(persona.title);
    setEditedInfo(persona.info || "");
    setEditedStyle(persona.style || "");
    setEditedUseCase(persona.use_case || "");
  };

  const handleCancelEdit = () => {
    setEditingPersonaId(null);
    setEditedTitle("");
    setEditedInfo("");
    setEditedStyle("");
    setEditedUseCase("");
  };

  const handleSaveEdit = async (personaId: number) => {
    setSavingPersonaId(personaId);
    try {
      const persona = personas.find(p => p.id === personaId);
      if (!persona) return;

      const updates: PersonaUpdate = {};

      // Only include fields that have changed
      if (editedTitle !== persona.title) {
        updates.title = editedTitle;
      }
      if (editedInfo !== (persona.info || "")) {
        updates.info = editedInfo;
      }
      if (editedStyle !== (persona.style || "")) {
        updates.style = editedStyle;
      }
      if (editedUseCase !== (persona.use_case || "")) {
        updates.use_case = editedUseCase;
      }

      // Only call API if there are actual changes
      if (Object.keys(updates).length > 0) {
        const response = await personaApi.update(personaId, updates);

        // Update the persona in the local state
        setPersonas(personas.map(p =>
          p.id === personaId ? response.data : p
        ));
      }

      handleCancelEdit();
    } catch (error) {
      console.error("Failed to update persona:", error);
      setError("Failed to update persona. Please try again.");
    } finally {
      setSavingPersonaId(null);
    }
  };

  const handleGenerateQuestions = async () => {
    const selectedPersonaIds = personas
      .filter(p => !rejectedPersonaIds.has(p.id))
      .map(p => p.id);

    if (selectedPersonaIds.length === 0) {
      setError("Please select at least one persona");
      return;
    }

    setGeneratingQuestions(true);
    setError(null);

    try {
      // Approve selected personas
      await personaApi.bulkApprove(selectedPersonaIds);

      // Generate questions
      const jobResponse = await jobApi.createQuestionJob(targetId, {
        count_requested: 10,
        persona_ids: selectedPersonaIds,
      });

      // Pass the job ID to parent for polling
      if (onJobLaunched) {
        onJobLaunched(jobResponse.data.id);
      }

      // Close the modal immediately after launching the job
      handleClose();
    } catch (error) {
      console.error("Failed to generate questions:", error);
      setError("Failed to generate questions. Please try again.");
      setGeneratingQuestions(false);
    }
  };

  const handleFileUpload = async () => {
    if (!uploadFile) return;

    setUploading(true);
    setError(null);

    try {
      // Upload the file - backend creates questions with status=pending
      const uploadResponse = await questionApi.upload(targetId, uploadFile);

      // Close the dialog first
      handleClose();

      // Notify parent to load pending questions for review
      if (onQuestionsUploaded) {
        await onQuestionsUploaded();
      } else {
        // Fallback to old behavior if callback not provided
        onSuccess();
      }
    } catch (error) {
      console.error("Failed to upload questions:", error);
      setError("Failed to upload questions. Please check the file format and try again.");
      setUploading(false);
    }
  };

  const handleClose = () => {
    setStep(-1);
    setSelectedMode(null);
    setPersonaSource(null);
    setPersonas([]);
    setRejectedPersonaIds(new Set());
    setLoading(false);
    setGeneratingQuestions(false);
    setError(null);
    setUploadFile(null);
    setUploading(false);
    handleCancelEdit();
    onClose();
  };

  const selectedCount = personas.length - rejectedPersonaIds.size;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Generate Evaluations</Typography>
          <IconButton onClick={handleClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {step === -1 && (
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            py={4}
            gap={3}
          >
            <Typography variant="h5" fontWeight={600} textAlign="center">
              How would you like to add questions?
            </Typography>
            <Typography variant="body1" color="text.secondary" textAlign="center" sx={{ maxWidth: 500 }}>
              You can generate questions from scratch using AI, or upload a file with existing questions.
            </Typography>
            <Box display="flex" gap={3} mt={2} alignItems="flex-start">
              <Card
                sx={{
                  width: 250,
                  height: selectedMode === "generate" ? "auto" : "200px", 
                  cursor: "pointer",
                  transition: "all 0.2s",
                  border: selectedMode === "generate" ? "2px solid" : "2px solid transparent",
                  borderColor: selectedMode === "generate" ? "primary.main" : "transparent",
                  "&:hover": {
                    transform: "translateY(-4px)",
                    boxShadow: 4,
                  },
                }}
                onClick={() => setSelectedMode("generate")}
              >
                <CardContent sx={{ textAlign: "center", py: 4, height: "200px" }}>
                  <AutoAwesomeIcon sx={{ fontSize: 48, color: "primary.main", mb: 2 }} />
                  <Typography variant="h6" fontWeight={600} gutterBottom>
                    Generate from Scratch
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    AI will create personas and generate targeted questions
                  </Typography>
                </CardContent>
                <Collapse in={selectedMode === "generate"} timeout={300}>
                  <Box sx={{ px: 2, pb: 2, display: "flex", flexDirection: "column", gap: 1 }}>
                    <Button
                      variant="outlined"
                      startIcon={<AutoAwesomeIcon />}
                      onClick={(e) => {
                        e.stopPropagation();
                        generatePersonas();
                      }}
                      fullWidth
                    >
                      Generate with AI
                    </Button>
                    <Button
                      variant="outlined"
                      startIcon={<GroupsIcon />}
                      onClick={(e) => {
                        e.stopPropagation();
                        sampleNemotronPersonas();
                      }}
                      fullWidth
                    >
                      Get General Personas
                    </Button>
                  </Box>
                </Collapse>
              </Card>
              <Card
                sx={{
                  width: 250,
                  height: "200px",
                  cursor: selectedMode === "generate" ? "default" : "pointer",
                  transition: "all 0.2s",
                  opacity: selectedMode === "generate" ? 0.4 : 1,
                  pointerEvents: selectedMode === "generate" ? "none" : "auto",
                  "&:hover": {
                    transform: selectedMode === "generate" ? "none" : "translateY(-4px)",
                    boxShadow: selectedMode === "generate" ? 0 : 4,
                  },
                }}
                onClick={() => setStep(2)}
              >
                <CardContent sx={{ textAlign: "center", py: 4 }}>
                  <UploadIcon sx={{ fontSize: 48, color: "primary.main", mb: 2 }} />
                  <Typography variant="h6" fontWeight={600} gutterBottom>
                    Upload File
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Upload CSV, JSON, or Excel file with questions
                  </Typography>
                </CardContent>
              </Card>
            </Box>
          </Box>
        )}

        {step === 0 && (
          <>
            <Box mb={3}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Select Personas
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                Review the generated personas below and select those that best represent your target users.
                You can edit personas to better match your needs, or reject ones that don't apply.
              </Typography>
              <Box display="flex" gap={1} mt={2}>
                <Button
                  startIcon={loading && personaSource === "ai" ? <CircularProgress size={16} /> : <RefreshIcon />}
                  onClick={() => generatePersonas()}
                  disabled={loading}
                  size="small"
                  variant="outlined"
                >
                  {loading && personaSource === "ai" ? "Generating..." : "Generate More (AI)"}
                </Button>
                <Button
                  startIcon={loading && personaSource === "general" ? <CircularProgress size={16} /> : <GroupsIcon />}
                  onClick={() => sampleNemotronPersonas()}
                  disabled={loading}
                  size="small"
                  variant="outlined"
                >
                  {loading && personaSource === "general" ? "Sampling..." : "Get More (General)"}
                </Button>
              </Box>
            </Box>

            {loading && personas.length === 0 ? (
              <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" py={4} gap={2}>
                <CircularProgress />
                <Typography variant="body2" color="text.secondary">
                  {personaSource === "ai" ? "Generating personas with AI, please wait..." : "Sampling general personas, please wait..."}
                </Typography>
              </Box>
            ) : (
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: {
                    xs: "1fr",
                    sm: "repeat(2, 1fr)",
                  },
                  gap: 2,
                }}
              >
                {personas.map((persona) => {
                  const isRejected = rejectedPersonaIds.has(persona.id);
                  const isEditing = editingPersonaId === persona.id;
                  return (
                    <Card
                      key={persona.id}
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        border: isRejected ? "2px solid #f44336" : "2px solid #4caf50",
                        opacity: isRejected ? 0.5 : 1,
                        transition: "all 0.2s",
                      }}
                    >
                      <CardContent sx={{ flex: 1 }}>
                        {isEditing ? (
                          <Box display="flex" flexDirection="column" gap={2}>
                            <TextField
                              label="Title"
                              value={editedTitle}
                              onChange={(e) => setEditedTitle(e.target.value)}
                              fullWidth
                              required
                              size="small"
                            />
                            <TextField
                              label="Info"
                              value={editedInfo}
                              onChange={(e) => setEditedInfo(e.target.value)}
                              fullWidth
                              multiline
                              rows={2}
                              size="small"
                            />
                            <TextField
                              label="Style"
                              value={editedStyle}
                              onChange={(e) => setEditedStyle(e.target.value)}
                              fullWidth
                              size="small"
                            />
                            <TextField
                              label="Use Case"
                              value={editedUseCase}
                              onChange={(e) => setEditedUseCase(e.target.value)}
                              fullWidth
                              size="small"
                            />
                          </Box>
                        ) : (
                          <>
                            <Box display="flex" alignItems="center" gap={1} mb={1}>
                              <Typography variant="h6">
                                {persona.title}
                              </Typography>
                              {persona.source === "generated" && (
                                <Chip label="AI" size="small" color="primary" variant="outlined" />
                              )}
                              {persona.source === "nemotron" && (
                                <Chip label="General" size="small" color="secondary" variant="outlined" />
                              )}
                            </Box>
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                              {persona.info}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              <strong>Style:</strong> {persona.style}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              <strong>Use Case:</strong> {persona.use_case}
                            </Typography>
                          </>
                        )}
                      </CardContent>
                      <CardActions>
                        {isEditing ? (
                          <>
                            <Button
                              size="small"
                              color="primary"
                              startIcon={<SaveIcon />}
                              onClick={() => handleSaveEdit(persona.id)}
                              disabled={savingPersonaId === persona.id || !editedTitle.trim()}
                            >
                              {savingPersonaId === persona.id ? <CircularProgress size={16} /> : "Save"}
                            </Button>
                            <Button
                              size="small"
                              onClick={handleCancelEdit}
                              disabled={savingPersonaId === persona.id}
                            >
                              Cancel
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              size="small"
                              color="primary"
                              startIcon={<EditIcon />}
                              onClick={() => handleStartEdit(persona)}
                              disabled={savingPersonaId !== null || loading}
                            >
                              Edit
                            </Button>
                            <Button
                              size="small"
                              color={isRejected ? "success" : "error"}
                              onClick={() => handleRejectPersona(persona.id)}
                              disabled={savingPersonaId !== null}
                            >
                              {isRejected ? "Include" : "Reject"}
                            </Button>
                          </>
                        )}
                      </CardActions>
                    </Card>
                  );
                })}
              </Box>
            )}
          </>
        )}

        {step === 1 && (
          <Box display="flex" flexDirection="column" alignItems="center" py={4} gap={2}>
            <CircularProgress size={60} />
            <Typography variant="h6">Generating Questions...</Typography>
            <Typography variant="body2" color="text.secondary" textAlign="center">
              This may take a few moments. We're generating evaluation questions
              for your selected personas.
            </Typography>
          </Box>
        )}

        {step === 2 && (
          <Box py={3}>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Upload Questions File
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Upload a CSV, JSON, or Excel file containing your questions.
              The file must have a "question" field. Optional fields: id, persona, type, scope.
            </Typography>

            <Box
              sx={{
                border: "2px dashed",
                borderColor: uploadFile ? "primary.main" : "grey.300",
                borderRadius: 2,
                p: 4,
                textAlign: "center",
                backgroundColor: uploadFile ? "primary.50" : "grey.50",
                cursor: "pointer",
                transition: "all 0.2s",
                "&:hover": {
                  borderColor: "primary.main",
                  backgroundColor: "primary.50",
                },
              }}
              onClick={() => document.getElementById("file-upload-input")?.click()}
            >
              <input
                id="file-upload-input"
                type="file"
                accept=".csv,.json,.xlsx,.xls"
                style={{ display: "none" }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    setUploadFile(file);
                    setError(null);
                  }
                }}
              />
              <UploadIcon sx={{ fontSize: 48, color: uploadFile ? "primary.main" : "grey.400", mb: 1 }} />
              <Typography variant="body1" fontWeight={600} gutterBottom>
                {uploadFile ? uploadFile.name : "Click to select a file"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Supported formats: CSV, JSON, Excel (.xlsx, .xls)
              </Typography>
            </Box>

            {uploading && (
              <Box display="flex" alignItems="center" justifyContent="center" gap={2} mt={3}>
                <CircularProgress size={24} />
                <Typography variant="body2" color="text.secondary">
                  Uploading questions and checking for duplicates...
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>

      {step === 0 && (
        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={handleGenerateQuestions}
            variant="contained"
            disabled={loading || selectedCount === 0}
          >
            Generate Questions ({selectedCount} {selectedCount === 1 ? 'persona' : 'personas'})
          </Button>
        </DialogActions>
      )}

      {step === 2 && (
        <DialogActions>
          <Button onClick={() => setStep(-1)} disabled={uploading}>
            Back
          </Button>
          <Button
            onClick={handleFileUpload}
            variant="contained"
            disabled={!uploadFile || uploading}
            startIcon={uploading ? <CircularProgress size={20} /> : <UploadIcon />}
          >
            {uploading ? "Uploading..." : "Upload"}
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
}
