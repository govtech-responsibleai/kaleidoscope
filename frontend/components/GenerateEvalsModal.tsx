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
  Grid,
  CircularProgress,
  IconButton,
  Alert,
  Stepper,
  Step,
  StepLabel,
} from "@mui/material";
import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
} from "@mui/icons-material";
import { jobApi, personaApi } from "@/lib/api";
import { PersonaResponse, JobStatus } from "@/lib/types";
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
  const [step, setStep] = useState(0); // 0: Generate Personas, 1: Confirm & Generate Questions
  const [personas, setPersonas] = useState<PersonaResponse[]>([]);
  const [rejectedPersonaIds, setRejectedPersonaIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const steps = ["Select Personas", "Generate Questions"];

  // Generate initial personas when modal opens
  useEffect(() => {
    if (open && personas.length === 0) {
      generatePersonas();
    }
  }, [open]);

  const generatePersonas = async (count = DEFAULT_PERSONA_COUNT) => {
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
    setStep(0);
    setPersonas([]);
    setRejectedPersonaIds(new Set());
    setLoading(false);
    setGeneratingQuestions(false);
    setError(null);
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

      <Stepper activeStep={step} sx={{ px: 3, pb: 2 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {step === 0 && (
          <>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="body2" color="text.secondary">
                Select personas to generate questions for ({selectedCount} selected)
              </Typography>
              <Button
                startIcon={<RefreshIcon />}
                onClick={() => generatePersonas()}
                disabled={loading}
                size="small"
              >
                Generate More
              </Button>
            </Box>

            {loading && personas.length === 0 ? (
              <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" py={4} gap={2}>
                <CircularProgress />
                <Typography variant="body2" color="text.secondary">
                  Generating personas, please wait...
                </Typography>
              </Box>
            ) : (
              <Grid container spacing={2}>
                {personas.map((persona) => {
                  const isRejected = rejectedPersonaIds.has(persona.id);
                  return (
                    <Grid item xs={12} sm={6} key={persona.id}>
                      <Card
                        sx={{
                          border: isRejected ? "2px solid #f44336" : "2px solid #4caf50",
                          opacity: isRejected ? 0.5 : 1,
                          transition: "all 0.2s",
                        }}
                      >
                        <CardContent>
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
                        </CardContent>
                        <CardActions>
                          <Button
                            size="small"
                            color={isRejected ? "success" : "error"}
                            onClick={() => handleRejectPersona(persona.id)}
                          >
                            {isRejected ? "Include" : "Reject"}
                          </Button>
                        </CardActions>
                      </Card>
                    </Grid>
                  );
                })}
              </Grid>
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
