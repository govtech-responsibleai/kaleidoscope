"use client";

import React, { useState, useEffect, useMemo } from "react";
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
  CircularProgress,
  IconButton,
  Alert,
  TextField,
  MenuItem,
  Checkbox,
  Chip,
  Collapse,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import {
  Close as CloseIcon,
  Upload as UploadIcon,
  AutoAwesome as AutoAwesomeIcon,
  Groups as GroupsIcon,
  TextFields as TextFieldsIcon,
} from "@mui/icons-material";
import { jobApi, personaApi, questionApi } from "@/lib/api";
import { PersonaResponse, InputStyle } from "@/lib/types";
import { getSourceChip } from "@/lib/theme";
import { usePersonaGeneration } from "@/hooks/usePersonaGeneration";
import { usePersonaEdit } from "@/hooks/usePersonaEdit";
import PersonaSelect from "@/components/questions/PersonaSelect";
import PersonaReview from "@/components/questions/PersonaReview";
import PersonaManualAdd from "@/components/questions/PersonaManualAdd";

type ModalStep =
  | "choose_mode"
  | "upload_file"
  | "upload_manual"
  | "generate_personas"
  | "select_personas"
  | "generating";

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
  const [step, setStep] = useState<ModalStep>("choose_mode");
  const [selectedMode, setSelectedMode] = useState<"generate" | "upload" | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Persona generation (shared hook)
  const personaGen = usePersonaGeneration(targetId);

  // Persona edit (shared hook)
  const personaEdit = usePersonaEdit({
    onSaved: (personaId, updated) => personaGen.updatePersona(personaId, updated),
    onError: setError,
  });

  // Rejection tracking
  const [rejectedPersonaIds, setRejectedPersonaIds] = useState<Set<number>>(new Set());
  const [showPersonaManualAdd, setShowPersonaManualAdd] = useState(false);

  // Existing personas (for select_personas flow)
  const [existingPersonas, setExistingPersonas] = useState<PersonaResponse[]>([]);
  const [selectedExistingIds, setSelectedExistingIds] = useState<number[]>([]);

  // Generation config
  const [numQuestions, setNumQuestions] = useState(30);
  const [inputStyle, setInputStyle] = useState<InputStyle>(InputStyle.BRIEF);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);

  // Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // Manual type state
  const [manualQuestions, setManualQuestions] = useState("");

  const manualQuestionCount = useMemo(
    () => manualQuestions.split("\n").filter((l) => l.trim()).length,
    [manualQuestions]
  );

  // Fetch existing approved personas when entering select_personas flow
  useEffect(() => {
    if (step === "select_personas" && existingPersonas.length === 0) {
      personaApi.list(targetId).then((res) => {
        const approved = res.data.filter((p) => p.status === "approved");
        setExistingPersonas(approved);
        setSelectedExistingIds([]);
      });
    }
  }, [existingPersonas.length, step, targetId]);

  const handleToggleReject = (personaId: number) => {
    setRejectedPersonaIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(personaId)) newSet.delete(personaId);
      else newSet.add(personaId);
      return newSet;
    });
  };

  const handleGenerateQuestions = async () => {
    const newSelectedIds = personaGen.personas
      .filter((p) => !rejectedPersonaIds.has(p.id))
      .map((p) => p.id);
    const allSelectedIds = [...newSelectedIds, ...selectedExistingIds];

    if (allSelectedIds.length === 0) {
      setError("Please select at least one persona.");
      return;
    }

    if (numQuestions < allSelectedIds.length) {
      setError(
        `You selected ${allSelectedIds.length} personas but requested ${numQuestions} questions. Use at least ${allSelectedIds.length} questions or select fewer personas.`
      );
      return;
    }

    setGeneratingQuestions(true);
    setError(null);

    try {
      // Approve new selected personas
      if (newSelectedIds.length > 0) {
        await personaApi.bulkApprove(newSelectedIds);
      }

      // Reject new rejected personas in parallel
      if (rejectedPersonaIds.size > 0) {
        await Promise.all([...rejectedPersonaIds].map((id) => personaApi.reject(id)));
      }

      const jobResponse = await jobApi.createQuestionJob(targetId, {
        count_requested: numQuestions,
        persona_ids: allSelectedIds,
        input_style: inputStyle,
      });

      if (onJobLaunched) {
        onJobLaunched(jobResponse.data.id);
      }
      handleClose();
    } catch (err) {
      console.error("Failed to generate questions:", err);
      setError("Failed to generate questions. Please try again.");
      setGeneratingQuestions(false);
    }
  };

  const handleFileUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setError(null);
    try {
      await questionApi.upload(targetId, uploadFile);
      handleClose();
      if (onQuestionsUploaded) {
        await onQuestionsUploaded();
      } else {
        onSuccess();
      }
    } catch (err) {
      console.error("Failed to upload questions:", err);
      setError("Failed to upload questions. Please check the file format and try again.");
      setUploading(false);
    }
  };

  const handleManualSubmit = async () => {
    const lines = manualQuestions
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0);
    if (lines.length === 0) {
      setError("Please enter at least one question.");
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const jsonContent = JSON.stringify(lines.map((text) => ({ question: text })));
      const blob = new Blob([jsonContent], { type: "application/json" });
      const file = new File([blob], "manual_questions.json", { type: "application/json" });
      await questionApi.upload(targetId, file);
      handleClose();
      if (onQuestionsUploaded) {
        await onQuestionsUploaded();
      } else {
        onSuccess();
      }
    } catch (err) {
      console.error("Failed to submit questions:", err);
      setError("Failed to submit questions. Please try again.");
      setUploading(false);
    }
  };

  const handleClose = () => {
    onClose();
    setTimeout(() => {
      setStep("choose_mode");
      setSelectedMode(null);
      setError(null);
      personaGen.reset();
      personaEdit.reset();
      setRejectedPersonaIds(new Set());
      setShowPersonaManualAdd(false);
      setExistingPersonas([]);
      setSelectedExistingIds([]);
      setNumQuestions(30);
      setInputStyle(InputStyle.BRIEF);
      setGeneratingQuestions(false);
      setUploadFile(null);
      setUploading(false);
      setManualQuestions("");
    }, 200);
  };

  const combinedError = error || personaGen.error;
  const newSelectedCount = personaGen.personas.length - rejectedPersonaIds.size;
  const selectedPersonaCount = step === "select_personas" ? selectedExistingIds.length : newSelectedCount;
  const hasInsufficientQuestions = selectedPersonaCount > 0 && numQuestions < selectedPersonaCount;
  const countValidationMessage = hasInsufficientQuestions
    ? `You selected ${selectedPersonaCount} persona${selectedPersonaCount !== 1 ? "s" : ""} but requested ${numQuestions} question${numQuestions !== 1 ? "s" : ""}. Use at least ${selectedPersonaCount} question${selectedPersonaCount !== 1 ? "s" : ""} or select fewer personas.`
    : null;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">
            {step === "choose_mode" && "Add Questions"}
            {step === "upload_file" && "Upload Questions File"}
            {step === "upload_manual" && "Type Questions"}
            {step === "generate_personas" && "Generate New Personas"}
            {step === "select_personas" && "Use Existing Personas"}
            {step === "generating" && "Generating Questions..."}
          </Typography>
          <IconButton onClick={handleClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        {combinedError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {combinedError}
          </Alert>
        )}
        {countValidationMessage && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {countValidationMessage}
          </Alert>
        )}

        {/* Step: Choose mode */}
        {step === "choose_mode" && (
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            py={4}
            gap={3}
          >
            <Typography variant="body1" color="text.secondary" textAlign="center" sx={{ maxWidth: 500 }}>
              Generate questions from personas using AI, or upload your own.
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
                  opacity: selectedMode === "upload" ? 0.4 : 1,
                  pointerEvents: selectedMode === "upload" ? "none" : "auto",
                  "&:hover": {
                    transform: selectedMode === "upload" ? "none" : "translateY(-4px)",
                    boxShadow: selectedMode === "upload" ? 0 : 4,
                  },
                }}
                onClick={() => setSelectedMode("generate")}
              >
                <CardContent sx={{ textAlign: "center", py: 4, height: "200px" }}>
                  <AutoAwesomeIcon sx={{ fontSize: 48, color: "primary.main", mb: 2 }} />
                  <Typography variant="h6" fontWeight={600} gutterBottom>
                    Generate from Personas
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Select or create personas, then AI generates targeted questions
                  </Typography>
                </CardContent>
                <Collapse in={selectedMode === "generate"} timeout={300}>
                  <Box sx={{ px: 2, pb: 2, display: "flex", flexDirection: "column", gap: 1 }}>
                    <Button
                      variant="outlined"
                      startIcon={<AutoAwesomeIcon />}
                      onClick={(e) => { e.stopPropagation(); setStep("generate_personas"); }}
                      fullWidth
                    >
                      Generate New Personas
                    </Button>
                    <Button
                      variant="outlined"
                      startIcon={<GroupsIcon />}
                      onClick={(e) => { e.stopPropagation(); setStep("select_personas"); }}
                      fullWidth
                    >
                      Use Existing Personas
                    </Button>
                  </Box>
                </Collapse>
              </Card>
              <Card
                sx={{
                  width: 250,
                  height: selectedMode === "upload" ? "auto" : "200px",
                  cursor: "pointer",
                  transition: "all 0.2s",
                  border: selectedMode === "upload" ? "2px solid" : "2px solid transparent",
                  borderColor: selectedMode === "upload" ? "primary.main" : "transparent",
                  opacity: selectedMode === "generate" ? 0.4 : 1,
                  pointerEvents: selectedMode === "generate" ? "none" : "auto",
                  "&:hover": {
                    transform: selectedMode === "generate" ? "none" : "translateY(-4px)",
                    boxShadow: selectedMode === "generate" ? 0 : 4,
                  },
                }}
                onClick={() => setSelectedMode("upload")}
              >
                <CardContent sx={{ textAlign: "center", py: 4, height: "200px" }}>
                  <UploadIcon sx={{ fontSize: 48, color: "primary.main", mb: 2 }} />
                  <Typography variant="h6" fontWeight={600} gutterBottom>
                    Upload
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Upload a file or manually type your own questions
                  </Typography>
                </CardContent>
                <Collapse in={selectedMode === "upload"} timeout={300}>
                  <Box sx={{ px: 2, pb: 2, display: "flex", flexDirection: "column", gap: 1 }}>
                    <Button
                      variant="outlined"
                      startIcon={<UploadIcon />}
                      onClick={(e) => { e.stopPropagation(); setStep("upload_file"); }}
                      fullWidth
                    >
                      Upload File
                    </Button>
                    <Button
                      variant="outlined"
                      startIcon={<TextFieldsIcon />}
                      onClick={(e) => { e.stopPropagation(); setStep("upload_manual"); }}
                      fullWidth
                    >
                      Type Questions
                    </Button>
                  </Box>
                </Collapse>
              </Card>
            </Box>
          </Box>
        )}

        {/* Step: File upload */}
        {step === "upload_file" && (
          <Box py={3}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Upload a CSV, JSON, or Excel file containing your questions.
              The file must have a &quot;question&quot; field. Optional fields: id, persona, type, scope.
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

        {/* Step: Manually type questions */}
        {step === "upload_manual" && (
          <Box py={3}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Enter your questions below, one per line.
            </Typography>
            <TextField
              multiline
              rows={10}
              fullWidth
              placeholder={"What are the leave policies?\nHow do I submit a claim?\nWho do I contact for IT support?"}
              value={manualQuestions}
              onChange={(e) => setManualQuestions(e.target.value)}
            />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {manualQuestionCount} question{manualQuestionCount !== 1 ? "s" : ""}
            </Typography>
          </Box>
        )}

        {/* Step: Generate from Personas */}
        {step === "generate_personas" && (
          <>
            {/* Three-card persona selection */}
            {personaGen.personas.length === 0 && !showPersonaManualAdd && !personaGen.loading && (
              <Box mb={3}>
                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                  Add New Personas (optional)
                </Typography>
                <PersonaSelect
                  onGenerateAI={() => personaGen.generateWithAI()}
                  onSampleRandom={() => personaGen.sampleNemotron()}
                  onAddManual={() => setShowPersonaManualAdd(true)}
                />
              </Box>
            )}

            {/* Loading state */}
            {personaGen.loading && personaGen.personas.length === 0 && !showPersonaManualAdd && (
              <Box display="flex" flexDirection="column" alignItems="center" py={4} gap={2}>
                <CircularProgress />
                <Typography variant="body2" color="text.secondary">
                  {personaGen.source === "ai" ? "Generating personas with AI..." : "Sampling personas..."}
                </Typography>
              </Box>
            )}

            {/* Manual persona form */}
            {showPersonaManualAdd && personaGen.personas.length === 0 && (
              <Box mb={3}>
                <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                  Add Persona Manually
                </Typography>
                <PersonaManualAdd
                  onSubmit={async (data) => {
                    const result = await personaGen.addManualPersona(data);
                    if (result) setShowPersonaManualAdd(false);
                  }}
                  onBack={() => setShowPersonaManualAdd(false)}
                  loading={personaGen.loading}
                />
              </Box>
            )}

            {/* Persona review grid */}
            {personaGen.personas.length > 0 && (
              <Box mb={3}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="subtitle2" fontWeight={600}>
                    New Personas
                  </Typography>
                  <Button
                    size="small"
                    onClick={() =>
                      setRejectedPersonaIds(
                        rejectedPersonaIds.size === 0
                          ? new Set(personaGen.personas.map((p) => p.id))
                          : new Set()
                      )
                    }
                    sx={{ textTransform: "none", fontSize: "0.75rem", whiteSpace: "nowrap" }}
                  >
                    {rejectedPersonaIds.size === 0 ? "Deselect All" : "Select All"}
                  </Button>
                </Box>
                <Box display="flex" gap={1} mb={2}>
                  <Button
                    startIcon={personaGen.loading && personaGen.source === "ai" ? <CircularProgress size={16} /> : <AutoAwesomeIcon />}
                    onClick={() => personaGen.generateWithAI()}
                    disabled={personaGen.loading}
                    size="small"
                    variant="outlined"
                  >
                    {personaGen.loading && personaGen.source === "ai" ? "Generating..." : "More (AI)"}
                  </Button>
                  <Button
                    startIcon={personaGen.loading && personaGen.source === "general" ? <CircularProgress size={16} /> : <GroupsIcon />}
                    onClick={() => personaGen.sampleNemotron()}
                    disabled={personaGen.loading}
                    size="small"
                    variant="outlined"
                  >
                    {personaGen.loading && personaGen.source === "general" ? "Sampling..." : "More (Random)"}
                  </Button>
                </Box>
                <PersonaReview
                  personas={personaGen.personas}
                  rejectedIds={rejectedPersonaIds}
                  onToggleReject={handleToggleReject}
                  editingPersonaId={personaEdit.editingPersonaId}
                  editedTitle={personaEdit.editedTitle}
                  editedInfo={personaEdit.editedInfo}
                  editedStyle={personaEdit.editedStyle}
                  editedUseCase={personaEdit.editedUseCase}
                  savingPersonaId={personaEdit.savingPersonaId}
                  onSetEditedTitle={personaEdit.setEditedTitle}
                  onSetEditedInfo={personaEdit.setEditedInfo}
                  onSetEditedStyle={personaEdit.setEditedStyle}
                  onSetEditedUseCase={personaEdit.setEditedUseCase}
                  onStartEdit={personaEdit.startEdit}
                  onCancelEdit={personaEdit.cancelEdit}
                  onSaveEdit={(id) => personaEdit.saveEdit(id, personaGen.personas)}
                  disabled={personaGen.loading}
                />
              </Box>
            )}

            <Box sx={{ borderTop: 1, borderColor: "divider", pt: 3, mt: 1 }}>
              <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2 }}>
                Generation Settings
              </Typography>
              <Box display="flex" gap={2} alignItems="center">
                <TextField
                  label="Number of questions"
                  type="number"
                  value={numQuestions}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (!isNaN(val) && val > 0 && val <= 200) setNumQuestions(val);
                  }}
                  size="small"
                  sx={{ width: 180 }}
                  slotProps={{ htmlInput: { min: 1, max: 200 } }}
                />
                <TextField
                  select
                  label="Input Style"
                  size="small"
                  sx={{ width: 160 }}
                  value={inputStyle}
                  onChange={(e) => setInputStyle(e.target.value as InputStyle)}
                >
                  <MenuItem value={InputStyle.BRIEF}>Brief</MenuItem>
                  <MenuItem value={InputStyle.REGULAR}>Regular</MenuItem>
                  <MenuItem value={InputStyle.DETAILED}>Detailed</MenuItem>
                </TextField>
              </Box>
            </Box>
          </>
        )}

        {/* Step: Use Existing Personas */}
        {step === "select_personas" && (
          <>
            <Box mb={3}>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                <Typography variant="body2" color="text.secondary">
                  Select which existing personas to generate questions for.
                </Typography>
                <Button
                  size="small"
                  onClick={() =>
                    setSelectedExistingIds(
                      selectedExistingIds.length === existingPersonas.length
                        ? []
                        : existingPersonas.map((p) => p.id)
                    )
                  }
                  sx={{ textTransform: "none", fontSize: "0.75rem", whiteSpace: "nowrap" }}
                >
                  {selectedExistingIds.length === existingPersonas.length ? "Deselect All" : "Select All"}
                </Button>
              </Box>
              <Box sx={{ maxHeight: 400, overflow: "auto", display: "flex", flexDirection: "column", gap: 1 }}>
                {existingPersonas.map((p) => {
                  const selected = selectedExistingIds.includes(p.id);
                  return (
                    <Box
                      key={p.id}
                      onClick={() =>
                        setSelectedExistingIds((prev) =>
                          selected ? prev.filter((id) => id !== p.id) : [...prev, p.id]
                        )
                      }
                      sx={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 1.5,
                        p: 2,
                        borderRadius: 2,
                        border: "1px solid",
                        borderColor: selected ? "primary.light" : "grey.200",
                        bgcolor: selected ? alpha("#4861b6", 0.06) : "background.paper",
                        cursor: "pointer",
                        transition: "all 0.15s",
                        "&:hover": { borderColor: "primary.light", bgcolor: alpha("#4861b6", 0.03) },
                      }}
                    >
                      <Checkbox checked={selected} size="small" sx={{ mt: -0.5 }} />
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                          <Typography variant="body2" fontWeight={600}>{p.title}</Typography>
                          <Chip
                            label={getSourceChip(p.source).label}
                            size="small"
                            variant="outlined"
                            sx={{ height: 20, fontSize: 10, ...getSourceChip(p.source) }}
                          />
                        </Box>
                        {p.info && (
                          <Typography variant="body2" color="text.secondary" sx={{
                            display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", mb: 0.5,
                          }}>
                            {p.info}
                          </Typography>
                        )}
                        <Box display="flex" gap={2}>
                          {p.style && (
                            <Typography variant="caption" color="text.disabled">
                              <strong>Style:</strong> {p.style}
                            </Typography>
                          )}
                          {p.use_case && (
                            <Typography variant="caption" color="text.disabled">
                              <strong>Use case:</strong> {p.use_case}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            </Box>

            <Box sx={{ borderTop: 1, borderColor: "divider", pt: 3, mt: 1 }}>
              <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2 }}>
                Generation Settings
              </Typography>
              <Box display="flex" gap={2} alignItems="center">
                <TextField
                  label="Number of questions"
                  type="number"
                  value={numQuestions}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (!isNaN(val) && val > 0 && val <= 200) setNumQuestions(val);
                  }}
                  size="small"
                  sx={{ width: 180 }}
                  slotProps={{ htmlInput: { min: 1, max: 200 } }}
                />
                <TextField
                  select
                  label="Input Style"
                  size="small"
                  sx={{ width: 160 }}
                  value={inputStyle}
                  onChange={(e) => setInputStyle(e.target.value as InputStyle)}
                >
                  <MenuItem value={InputStyle.BRIEF}>Brief</MenuItem>
                  <MenuItem value={InputStyle.REGULAR}>Regular</MenuItem>
                  <MenuItem value={InputStyle.DETAILED}>Detailed</MenuItem>
                </TextField>
              </Box>
            </Box>
          </>
        )}
      </DialogContent>

      {/* Actions for generate_personas */}
      {step === "generate_personas" && (
        <DialogActions>
          <Button onClick={() => setStep("choose_mode")} disabled={personaGen.loading || generatingQuestions}>
            Back
          </Button>
          <Button
            onClick={handleGenerateQuestions}
            variant="contained"
            disabled={personaGen.loading || generatingQuestions || newSelectedCount === 0 || hasInsufficientQuestions}
            startIcon={generatingQuestions ? <CircularProgress size={20} /> : undefined}
          >
            {generatingQuestions
              ? "Launching..."
              : `Generate ${numQuestions} Questions (${newSelectedCount} persona${newSelectedCount !== 1 ? "s" : ""})`}
          </Button>
        </DialogActions>
      )}

      {/* Actions for select_personas */}
      {step === "select_personas" && (
        <DialogActions>
          <Button onClick={() => setStep("choose_mode")} disabled={generatingQuestions}>
            Back
          </Button>
          <Button
            onClick={handleGenerateQuestions}
            variant="contained"
            disabled={generatingQuestions || selectedExistingIds.length === 0 || hasInsufficientQuestions}
            startIcon={generatingQuestions ? <CircularProgress size={20} /> : undefined}
          >
            {generatingQuestions
              ? "Launching..."
              : `Generate ${numQuestions} Questions (${selectedExistingIds.length} persona${selectedExistingIds.length !== 1 ? "s" : ""})`}
          </Button>
        </DialogActions>
      )}

      {/* Actions for file upload */}
      {step === "upload_file" && (
        <DialogActions>
          <Button onClick={() => setStep("choose_mode")} disabled={uploading}>
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

      {/* Actions for manual type */}
      {step === "upload_manual" && (
        <DialogActions>
          <Button onClick={() => setStep("choose_mode")} disabled={uploading}>
            Back
          </Button>
          <Button
            onClick={handleManualSubmit}
            variant="contained"
            disabled={uploading || manualQuestionCount === 0}
            startIcon={uploading ? <CircularProgress size={20} /> : undefined}
          >
            {uploading
              ? "Submitting..."
              : `Submit ${manualQuestionCount} Question${manualQuestionCount !== 1 ? "s" : ""}`}
          </Button>
        </DialogActions>
      )}
    </Dialog>
  );
}
