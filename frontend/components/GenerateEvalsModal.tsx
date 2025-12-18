"use client";

import React, { useState, useEffect } from "react";
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
} from "@mui/material";
import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
  Edit as EditIcon,
  Save as SaveIcon,
} from "@mui/icons-material";
import { jobApi, personaApi } from "@/lib/api";
import { PersonaResponse, JobStatus, PersonaUpdate } from "@/lib/types";
import { DEFAULT_PERSONA_COUNT, JOB_POLLING_INTERVAL } from "@/lib/constants";

interface GenerateEvalsModalProps {
  open: boolean;
  onClose: () => void;
  targetId: number;
  onSuccess: () => void;
  onJobLaunched?: (jobId: number) => void;
}

export default function GenerateEvalsModal({
  open,
  onClose,
  targetId,
  onSuccess,
  onJobLaunched,
}: GenerateEvalsModalProps) {
  const [step, setStep] = useState(-1); // -1: Initial, 0: Select Personas, 1: Generate Questions
  const [personas, setPersonas] = useState<PersonaResponse[]>([]);
  const [rejectedPersonaIds, setRejectedPersonaIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Edit mode state
  const [editingPersonaId, setEditingPersonaId] = useState<number | null>(null);
  const [editedTitle, setEditedTitle] = useState("");
  const [editedInfo, setEditedInfo] = useState("");
  const [editedStyle, setEditedStyle] = useState("");
  const [editedUseCase, setEditedUseCase] = useState("");
  const [savingPersonaId, setSavingPersonaId] = useState<number | null>(null);

  const generatePersonas = async (count = DEFAULT_PERSONA_COUNT) => {
    setStep(0); // Move to step 0 when starting generation
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

  const handleClose = () => {
    setStep(-1);
    setPersonas([]);
    setRejectedPersonaIds(new Set());
    setLoading(false);
    setGeneratingQuestions(false);
    setError(null);
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
            py={6}
            gap={3}
          >
            <Typography variant="h5" fontWeight={600} textAlign="center">
              Generate Personas
            </Typography>
            <Typography variant="body1" color="text.secondary" textAlign="center" sx={{ maxWidth: 500 }}>
              Personas represent different types of users who might interact with your system.
              Generate personas first to create targeted evaluation questions.
            </Typography>
            <Button
              variant="contained"
              size="large"
              onClick={() => generatePersonas()}
              sx={{ mt: 2 }}
            >
              Generate
            </Button>
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
              <Box display="flex" justifyContent="space-between" alignItems="center" mt={2}>
                <Button
                  startIcon={<RefreshIcon />}
                  onClick={() => generatePersonas()}
                  disabled={loading}
                  size="small"
                  variant="outlined"
                >
                  Generate More
                </Button>
              </Box>
            </Box>

            {loading && personas.length === 0 ? (
              <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" py={4} gap={2}>
                <CircularProgress />
                <Typography variant="body2" color="text.secondary">
                  Generating personas, please wait...
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
                        border: isRejected ? "2px solid #f44336" : "2px solid #4caf50",
                        opacity: isRejected ? 0.5 : 1,
                        transition: "all 0.2s",
                      }}
                    >
                      <CardContent>
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
                            <Typography variant="h6" gutterBottom>
                              {persona.title}
                            </Typography>
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
    </Dialog>
  );
}
