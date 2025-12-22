"use client";

import React, { useEffect, useState, useMemo } from "react";
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  OutlinedInput,
  Checkbox,
  ListItemText,
  IconButton,
  Card,
  CardContent,
  Divider,
  Alert,
  TextField,
} from "@mui/material";
import {
  FilterList as FilterIcon,
  Close as CloseIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Save as SaveIcon,
} from "@mui/icons-material";
import { useParams } from "next/navigation";
import { targetApi, questionApi, personaApi, jobApi } from "@/lib/api";
import { TargetResponse, QuestionResponse, PersonaResponse, JobStatus, QuestionType, QuestionScope, QuestionUpdate } from "@/lib/types";
import { JOB_POLLING_INTERVAL } from "@/lib/constants";
import GenerateEvalsModal from "@/components/GenerateEvalsModal";

export default function QuestionsPage() {
  const params = useParams();
  const targetId = parseInt(params.id as string);

  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [questions, setQuestions] = useState<QuestionResponse[]>([]);
  const [personas, setPersonas] = useState<PersonaResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [jobStatus, setJobStatus] = useState<"running" | "finding_similar" | "ready_for_review" | null>(null);
  const [newQuestions, setNewQuestions] = useState<QuestionResponse[]>([]);
  const [similarQuestionsMap, setSimilarQuestionsMap] = useState<Record<number, QuestionResponse[]>>({});
  const [processingQuestionId, setProcessingQuestionId] = useState<number | null>(null);

  // Edit mode state
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [editedText, setEditedText] = useState("");
  const [editedType, setEditedType] = useState<QuestionType>(QuestionType.TYPICAL);
  const [editedScope, setEditedScope] = useState<QuestionScope>(QuestionScope.IN_KB);

  // Filter states
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<number[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>(["typical", "edge"]);
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["in_kb", "out_kb"]);

  const fetchData = async () => {
    try {
      const [targetRes, questionsRes, personasRes] = await Promise.all([
        targetApi.get(targetId),
        questionApi.listByTarget(targetId),
        personaApi.list(targetId),
      ]);
      setTarget(targetRes.data);
      setQuestions(questionsRes.data);
      setPersonas(personasRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [targetId]);

  // Initialize persona filter when personas are loaded, and add new personas to selection
  useEffect(() => {
    if (personas.length > 0) {
      const allPersonaIds = personas.map((p) => p.id);
      if (selectedPersonaIds.length === 0) {
        setSelectedPersonaIds(allPersonaIds);
      } else {
        const newPersonaIds = allPersonaIds.filter(id => !selectedPersonaIds.includes(id));
        if (newPersonaIds.length > 0) {
          setSelectedPersonaIds([...selectedPersonaIds, ...newPersonaIds]);
        }
      }
    }
  }, [personas]);

  // Poll for active job completion and fetch similar questions
  useEffect(() => {
    if (!activeJobId) return;

    const interval = setInterval(async () => {
      try {
        const response = await jobApi.get(activeJobId);
        if (response.data.status === JobStatus.COMPLETED) {
          clearInterval(interval);
          setJobStatus("finding_similar");

          // Fetch new questions from the job
          const jobQuestionsRes = await jobApi.getQuestions(activeJobId);
          const newQs = jobQuestionsRes.data;
          setNewQuestions(newQs);

          // Find similar questions for all new questions in one request
          const similarMap: Record<number, QuestionResponse[]> = {};

          if (newQs.length > 0) {
            try {
              const similarRes = await questionApi.findSimilar({
                target_id: targetId,
                question_ids: newQs.map(q => q.id),
                similarity_threshold: 0.7,
              });

              // Process results for each query question
              for (const result of similarRes.data.results) {
                const similarQuestionIds = result.similar_questions.map(sq => sq.question_id);
                const similarFullQuestions = questions.filter(q => similarQuestionIds.includes(q.id));
                similarMap[result.query_question_id] = similarFullQuestions;
              }
            } catch (error) {
              console.error("Failed to find similar questions:", error);
              // Initialize empty arrays for all questions if the request fails
              newQs.forEach(q => {
                similarMap[q.id] = [];
              });
            }
          }

          setSimilarQuestionsMap(similarMap);
          setJobStatus("ready_for_review");
          setActiveJobId(null);

          // Refresh the main questions list
          fetchData();
        } else if (response.data.status === JobStatus.FAILED) {
          clearInterval(interval);
          setActiveJobId(null);
          setJobStatus(null);
          console.error("Job failed:", activeJobId);
        }
      } catch (error) {
        console.error("Failed to check job status:", error);
      }
    }, JOB_POLLING_INTERVAL);

    return () => clearInterval(interval);
  }, [activeJobId, questions]);

  // Get only approved questions
  const approvedQuestions = useMemo(() => {
    return questions.filter((question) => question.status === "approved");
  }, [questions]);

  // Apply filters to approved questions
  const filteredQuestions = useMemo(() => {
    return approvedQuestions.filter((question) => {
      const personaMatch = selectedPersonaIds.length === 0 || selectedPersonaIds.includes(question.persona_id);
      const typeMatch = selectedTypes.includes(question.type);
      const scopeMatch = selectedScopes.includes(question.scope);
      return personaMatch && typeMatch && scopeMatch;
    });
  }, [approvedQuestions, selectedPersonaIds, selectedTypes, selectedScopes]);


  const handleApproveNewQuestion = async (questionId: number) => {
    setProcessingQuestionId(questionId);
    try {
      await questionApi.approve(questionId);
      // Remove from new questions
      const updatedNewQuestions = newQuestions.filter(q => q.id !== questionId);
      setNewQuestions(updatedNewQuestions);

      // If all questions reviewed, close the job section
      if (updatedNewQuestions.length === 0) {
        setJobStatus(null);
        setSimilarQuestionsMap({});
      }

      // Refresh main questions list to include the newly approved question
      fetchData();
    } catch (error) {
      console.error("Failed to approve question:", error);
      alert("Failed to approve question. Please try again.");
    } finally {
      setProcessingQuestionId(null);
    }
  };

  const handleRejectNewQuestion = async (questionId: number) => {
    setProcessingQuestionId(questionId);
    try {
      await questionApi.reject(questionId);
      // Remove from new questions
      const updatedNewQuestions = newQuestions.filter(q => q.id !== questionId);
      setNewQuestions(updatedNewQuestions);

      // If all questions reviewed, close the job section
      if (updatedNewQuestions.length === 0) {
        setJobStatus(null);
        setSimilarQuestionsMap({});
      }
    } catch (error) {
      console.error("Failed to reject question:", error);
      alert("Failed to reject question. Please try again.");
    } finally {
      setProcessingQuestionId(null);
    }
  };

  const handleStartEdit = (question: QuestionResponse) => {
    setEditingQuestionId(question.id);
    setEditedText(question.text);
    setEditedType(question.type);
    setEditedScope(question.scope);
  };

  const handleCancelEdit = () => {
    setEditingQuestionId(null);
    setEditedText("");
    setEditedType(QuestionType.TYPICAL);
    setEditedScope(QuestionScope.IN_KB);
  };

  const handleSaveEdit = async (questionId: number) => {
    setProcessingQuestionId(questionId);
    try {
      const question = newQuestions.find(q => q.id === questionId);
      if (!question) return;

      const updates: QuestionUpdate = {};

      // Only include fields that have changed
      if (editedText !== question.text) {
        updates.text = editedText;
      }
      if (editedType !== question.type) {
        updates.type = editedType;
      }
      if (editedScope !== question.scope) {
        updates.scope = editedScope;
      }

      // Only call API if there are actual changes
      if (Object.keys(updates).length > 0) {
        await questionApi.update(questionId, updates);

        // Update the question in the local state
        setNewQuestions(newQuestions.map(q =>
          q.id === questionId
            ? { ...q, ...updates }
            : q
        ));
      }

      handleCancelEdit();
    } catch (error) {
      console.error("Failed to update question:", error);
      alert("Failed to update question. Please try again.");
    } finally {
      setProcessingQuestionId(null);
    }
  };

  const handleJobLaunched = (jobId: number) => {
    setActiveJobId(jobId);
    setJobStatus("running");
    setNewQuestions([]);
    setSimilarQuestionsMap({});
  };

  const handleDeleteQuestion = async (questionId: number) => {
    try {
      await questionApi.delete(questionId);
      fetchData();
    } catch (error) {
      console.error("Failed to delete question:", error);
    }
  };

  const getPersonaTitle = (personaId: number) => {
    const persona = personas.find((p) => p.id === personaId);
    return persona?.title || "Unknown";
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="30vh">
        <CircularProgress />
      </Box>
    );
  }

  if (!target) {
    return null;
  }

  const hasQuestions = questions.length > 0;

  return (
    <Box>
      {/* Job Status Section */}
      {jobStatus && (
        <Card variant="outlined" sx={{ mb: 3, backgroundColor: "#f5f5f5" }}>
          <CardContent>
            <Typography variant="h6" fontWeight={600} sx={{mb: 2}}>
              Generation Job
            </Typography>

            {(jobStatus === "running" || jobStatus === "finding_similar") && (
              <Box display="flex" alignItems="center" gap={2}>
                <CircularProgress size={24} />
                <Typography variant="body1">
                  Generating questions, please wait...
                </Typography>
              </Box>
            )}

            {jobStatus === "ready_for_review" && (
              <>
                <Alert severity="info" sx={{ mb: 2 }}>
                  Questions generated. Scroll down to accept or reject.
                </Alert>

                {newQuestions.map((newQ) => {
                  const isEditing = editingQuestionId === newQ.id;
                  return (
                  <Card key={newQ.id} sx={{ mb: 2, border: "2px solid #1976d2" }}>
                    <CardContent>
                      <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                        <Box flex={1}>
                          <Typography variant="subtitle1" fontWeight={600} sx={{mb: 2}}>
                            New Question
                          </Typography>

                          {isEditing ? (
                            <Box display="flex" flexDirection="column" gap={2} sx={{mb: 2}}>
                              <TextField
                                label="Question Text"
                                value={editedText}
                                onChange={(e) => setEditedText(e.target.value)}
                                multiline
                                rows={3}
                                fullWidth
                                required
                              />
                              <Box display="flex" gap={2}>
                                <FormControl sx={{ minWidth: 150 }}>
                                  <InputLabel id={`edit-type-${newQ.id}`}>Type</InputLabel>
                                  <Select
                                    labelId={`edit-type-${newQ.id}`}
                                    value={editedType}
                                    onChange={(e) => setEditedType(e.target.value as QuestionType)}
                                    label="Type"
                                  >
                                    <MenuItem value={QuestionType.TYPICAL}>Typical</MenuItem>
                                    <MenuItem value={QuestionType.EDGE}>Edge</MenuItem>
                                  </Select>
                                </FormControl>
                                <FormControl sx={{ minWidth: 150 }}>
                                  <InputLabel id={`edit-scope-${newQ.id}`}>Scope</InputLabel>
                                  <Select
                                    labelId={`edit-scope-${newQ.id}`}
                                    value={editedScope}
                                    onChange={(e) => setEditedScope(e.target.value as QuestionScope)}
                                    label="Scope"
                                  >
                                    <MenuItem value={QuestionScope.IN_KB}>In KB</MenuItem>
                                    <MenuItem value={QuestionScope.OUT_KB}>Out KB</MenuItem>
                                  </Select>
                                </FormControl>
                              </Box>
                            </Box>
                          ) : (
                            <>
                              <Typography variant="body1" sx={{mb: 2}}>
                                {newQ.text}
                              </Typography>
                              <Box display="flex" gap={1} mt={1}>
                                <Chip label={getPersonaTitle(newQ.persona_id)} size="small" />
                                <Chip label={newQ.type} size="small" color={newQ.type === "edge" ? "warning" : "default"} />
                                <Chip label={newQ.scope === "in_kb" ? "In KB" : "Out KB"} size="small" color={newQ.scope === "in_kb" ? "success" : "info"} />
                              </Box>
                            </>
                          )}
                        </Box>
                        <Box display="flex" gap={1}>
                          {isEditing ? (
                            <>
                              <Button
                                variant="contained"
                                color="primary"
                                startIcon={<SaveIcon />}
                                onClick={() => handleSaveEdit(newQ.id)}
                                disabled={processingQuestionId === newQ.id || !editedText.trim()}
                              >
                                {processingQuestionId === newQ.id ? <CircularProgress size={20} /> : "Save"}
                              </Button>
                              <Button
                                variant="outlined"
                                onClick={handleCancelEdit}
                                disabled={processingQuestionId === newQ.id}
                              >
                                Cancel
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button
                                variant="outlined"
                                color="primary"
                                startIcon={<EditIcon />}
                                onClick={() => handleStartEdit(newQ)}
                                disabled={processingQuestionId !== null}
                              >
                                Edit
                              </Button>
                              <Button
                                variant="contained"
                                color="success"
                                startIcon={<CheckCircleIcon />}
                                onClick={() => handleApproveNewQuestion(newQ.id)}
                                disabled={processingQuestionId !== null}
                              >
                                {processingQuestionId === newQ.id ? <CircularProgress size={20} /> : "Approve"}
                              </Button>
                              <Button
                                variant="outlined"
                                color="error"
                                startIcon={<CancelIcon />}
                                onClick={() => handleRejectNewQuestion(newQ.id)}
                                disabled={processingQuestionId !== null}
                              >
                                Reject
                              </Button>
                            </>
                          )}
                        </Box>
                      </Box>

                      {similarQuestionsMap[newQ.id] && similarQuestionsMap[newQ.id].length > 0 && (
                        <>
                          <Divider sx={{ my: 2 }} />
                          <Typography variant="subtitle2" color="text.secondary" sx={{mb: 2}}>
                            Similar Existing Questions ({similarQuestionsMap[newQ.id].length})
                          </Typography>
                          {similarQuestionsMap[newQ.id].map((similarQ) => (
                            <Box key={similarQ.id} sx={{ pl: 2, py: 1, backgroundColor: "#f9f9f9", borderRadius: 1, mb: 1 }}>
                              <Typography variant="body2" color="text.secondary">
                                {similarQ.text}
                              </Typography>
                              <Box display="flex" gap={1} mt={0.5}>
                                <Chip label={getPersonaTitle(similarQ.persona_id)} size="small" variant="outlined" />
                                <Chip label={similarQ.type} size="small" variant="outlined" />
                                <Chip label={similarQ.scope === "in_kb" ? "In KB" : "Out KB"} size="small" variant="outlined" />
                              </Box>
                            </Box>
                          ))}
                        </>
                      )}
                    </CardContent>
                  </Card>
                  );
                })}

                {newQuestions.length === 0 && (
                  <Typography variant="body1" color="text.secondary">
                    All questions have been reviewed.
                  </Typography>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {!hasQuestions ? (
        <Box
          display="flex"
          flexDirection="column"
          alignItems="center"
          justifyContent="center"
          minHeight="30vh"
          gap={2}
          sx={{ maxWidth: 600, mx: "auto", textAlign: "center" }}
        >
          <Typography variant="h5" fontWeight={600}>
            Start by generating evaluation questions
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 1 }}>
            Evaluation questions are used to systematically test how your chatbot responds across different scenarios. Generate them automatically, and edit them later.
          </Typography>
          <Button
            variant="contained"
            size="large"
            onClick={() => setGenerateModalOpen(true)}
          >
            Generate Questions
          </Button>
        </Box>
      ) : (
        <>
          {/* Generate More Button */}
          <Box display="flex" justifyContent="flex-start" mb={2}>
            <Button
              variant="outlined"
              onClick={() => setGenerateModalOpen(true)}
            >
              Generate More Evals
            </Button>
          </Box>

          {/* Filter Controls */}
          <Paper sx={{ p: 2, mb: 2 }} variant="outlined">
            <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
              <Box display="flex" alignItems="center" gap={1}>
                <FilterIcon color="action" />
                <Typography variant="subtitle2" color="text.secondary">
                  Filters:
                </Typography>
              </Box>

              {/* Persona Filter */}
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel id="persona-filter-label">Personas</InputLabel>
                <Select
                  labelId="persona-filter-label"
                  id="persona-filter"
                  multiple
                  value={selectedPersonaIds}
                  onChange={(e) => setSelectedPersonaIds(e.target.value as number[])}
                  input={<OutlinedInput label="Personas" />}
                  renderValue={(selected) =>
                    selected.length === personas.length
                      ? "All Personas"
                      : `${selected.length} selected`
                  }
                >
                  {personas.map((persona) => (
                    <MenuItem key={persona.id} value={persona.id}>
                      <Checkbox checked={selectedPersonaIds.includes(persona.id)} />
                      <ListItemText primary={persona.title} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Type Filter */}
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel id="type-filter-label">Type</InputLabel>
                <Select
                  labelId="type-filter-label"
                  id="type-filter"
                  multiple
                  value={selectedTypes}
                  onChange={(e) => setSelectedTypes(e.target.value as string[])}
                  input={<OutlinedInput label="Type" />}
                  renderValue={(selected) =>
                    selected.length === 2 ? "All Types" : selected.join(", ")
                  }
                >
                  <MenuItem value="typical">
                    <Checkbox checked={selectedTypes.includes("typical")} />
                    <ListItemText primary="Typical" />
                  </MenuItem>
                  <MenuItem value="edge">
                    <Checkbox checked={selectedTypes.includes("edge")} />
                    <ListItemText primary="Edge" />
                  </MenuItem>
                </Select>
              </FormControl>

              {/* Scope Filter */}
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel id="scope-filter-label">Scope</InputLabel>
                <Select
                  labelId="scope-filter-label"
                  id="scope-filter"
                  multiple
                  value={selectedScopes}
                  onChange={(e) => setSelectedScopes(e.target.value as string[])}
                  input={<OutlinedInput label="Scope" />}
                  renderValue={(selected) =>
                    selected.length === 2 ? "All Scopes" : selected.map(s => s === "in_kb" ? "In KB" : "Out KB").join(", ")
                  }
                >
                  <MenuItem value="in_kb">
                    <Checkbox checked={selectedScopes.includes("in_kb")} />
                    <ListItemText primary="In KB" />
                  </MenuItem>
                  <MenuItem value="out_kb">
                    <Checkbox checked={selectedScopes.includes("out_kb")} />
                    <ListItemText primary="Out KB" />
                  </MenuItem>
                </Select>
              </FormControl>

              {/* Result Count */}
              <Typography variant="body2" color="text.secondary" sx={{ ml: "auto" }}>
                Showing {filteredQuestions.length} of {approvedQuestions.length} questions
              </Typography>
            </Box>
          </Paper>

          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Question</TableCell>
                  <TableCell align="center">Persona</TableCell>
                  <TableCell align="center">Type</TableCell>
                  <TableCell align="center">Scope</TableCell>
                  <TableCell align="center" width={50}></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredQuestions.map((question) => (
                  <TableRow key={question.id}>
                    <TableCell>
                      <Typography>{question.text}</Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Typography fontWeight={600}>
                        {getPersonaTitle(question.persona_id)}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={question.type}
                        size="small"
                        color={question.type === "edge" ? "warning" : "default"}
                        variant={question.type === "edge" ? "filled" : "outlined"}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={question.scope === "in_kb" ? "In KB" : "Out KB"}
                        size="small"
                        color={question.scope === "in_kb" ? "success" : "info"}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        onClick={() => handleDeleteQuestion(question.id)}
                        sx={{ opacity: 0.5, "&:hover": { opacity: 1, color: "error.main" } }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      <GenerateEvalsModal
        open={generateModalOpen}
        onClose={() => setGenerateModalOpen(false)}
        targetId={targetId}
        onSuccess={fetchData}
        onJobLaunched={handleJobLaunched}
      />
    </Box>
  );
}
