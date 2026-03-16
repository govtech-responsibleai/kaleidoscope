"use client";

import { useEffect, useState, useMemo, useRef, useCallback } from "react";
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
  IconButton,
  Card,
  CardContent,
  Divider,
  Alert,
  TextField,
  Tooltip,
  Tabs,
  Tab,
} from "@mui/material";
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Edit as EditIcon,
  Save as SaveIcon,
  Add as AddIcon,
} from "@mui/icons-material";
import { TableHeaderFilter, type FilterOption } from "@/components/shared";
import { useParams } from "next/navigation";
import { targetApi, questionApi, personaApi, jobApi } from "@/lib/api";
import { TargetResponse, QuestionResponse, PersonaResponse, JobStatus, QuestionType, QuestionScope, QuestionUpdate } from "@/lib/types";
import { JOB_POLLING_INTERVAL } from "@/lib/constants";
import GenerateEvalsModal from "@/components/GenerateEvalsModal";
import PersonaTable from "@/components/questions/PersonaTable";
import AddPersonasDialog from "@/components/questions/AddPersonasDialog";

export default function QuestionsPage() {
  const params = useParams();
  const targetId = parseInt(params.id as string);

  const [activeTab, setActiveTab] = useState(0);
  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [questions, setQuestions] = useState<QuestionResponse[]>([]);
  const [personas, setPersonas] = useState<PersonaResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [addPersonasOpen, setAddPersonasOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [jobStatus, setJobStatus] = useState<"running" | "finding_similar" | "ready_for_review" | null>(null);
  const [newQuestions, setNewQuestions] = useState<QuestionResponse[]>([]);
  const [similarQuestionsMap, setSimilarQuestionsMap] = useState<Record<number, QuestionResponse[]>>({});
  const [processingQuestionId, setProcessingQuestionId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bulkApproving, setBulkApproving] = useState(false);

  // Edit mode state
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [editedText, setEditedText] = useState("");
  const [editedType, setEditedType] = useState<QuestionType | null>(QuestionType.TYPICAL);
  const [editedScope, setEditedScope] = useState<QuestionScope | null>(QuestionScope.IN_KB);

  // Filter states
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<number[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>(["typical", "edge"]);
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["in_kb", "out_kb"]);

  // Ref to avoid stale closure in polling useEffect
  const questionsRef = useRef<QuestionResponse[]>([]);

  const buildSimilarMap = useCallback(async (
    newQs: QuestionResponse[],
    allQuestions: QuestionResponse[]
  ): Promise<Record<number, QuestionResponse[]>> => {
    const similarMap: Record<number, QuestionResponse[]> = {};
    if (newQs.length === 0) return similarMap;

    try {
      const similarRes = await questionApi.findSimilar({
        target_id: targetId,
        question_ids: newQs.map(q => q.id),
        similarity_threshold: 0.7,
      });

      for (const result of similarRes.data.results) {
        const similarQuestionIds = result.similar_questions.map(sq => sq.question_id);
        similarMap[result.query_question_id] = allQuestions.filter(q =>
          q.status === "approved" && similarQuestionIds.includes(q.id)
        );
      }
    } catch (error) {
      console.error("Failed to find similar questions:", error);
      newQs.forEach(q => { similarMap[q.id] = []; });
    }

    return similarMap;
  }, [targetId]);

  const fetchData = async () => {
    try {
      const [targetRes, questionsRes, personasRes] = await Promise.all([
        targetApi.get(targetId),
        questionApi.listByTarget(targetId),
        personaApi.list(targetId),
      ]);

      setTarget(targetRes.data);
      setQuestions(questionsRes.data);
      questionsRef.current = questionsRes.data;
      setPersonas(personasRes.data);
      return questionsRes.data;
    } catch (error) {
      console.error("Failed to fetch data:", error);
      return [];
    } finally {
      setLoading(false);
    }
  };

  const loadPendingQuestionsForReview = async (allQuestions: QuestionResponse[]) => {
    const pendingQuestions = allQuestions.filter(q => q.status === "pending");
    if (pendingQuestions.length === 0) return;

    setNewQuestions(pendingQuestions);
    setJobStatus("finding_similar");

    const similarMap = await buildSimilarMap(pendingQuestions, allQuestions);
    setSimilarQuestionsMap(similarMap);
    setJobStatus("ready_for_review");
  };

  useEffect(() => {
    const initialize = async () => {
      const freshQuestions = await fetchData();
      // On initial load, check for pending questions and load them for review
      if (freshQuestions && freshQuestions.length > 0 && !activeJobId && !jobStatus) {
        const pendingQuestions = freshQuestions.filter(q => q.status === "pending");
        if (pendingQuestions.length > 0) {
          await loadPendingQuestionsForReview(freshQuestions);
        }
      }
    };
    initialize();
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

          const jobQuestionsRes = await jobApi.getQuestions(activeJobId);
          const newQs = jobQuestionsRes.data;
          setNewQuestions(newQs);

          const similarMap = await buildSimilarMap(newQs, questionsRef.current);
          setSimilarQuestionsMap(similarMap);
          setJobStatus("ready_for_review");
          setActiveJobId(null);

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
  }, [activeJobId, buildSimilarMap]);

  // Get only approved questions
  const approvedQuestions = useMemo(() => {
    return questions.filter((question) => question.status === "approved");
  }, [questions]);

  // Apply filters to approved questions
  const filteredQuestions = useMemo(() => {
    return approvedQuestions.filter((question) => {
      // For persona filter: show questions with no persona when all personas are selected OR when no personas exist
      const allPersonasSelected = selectedPersonaIds.length === personas.length;
      const personaMatch =
        selectedPersonaIds.length === 0 ||
        allPersonasSelected ||
        (question.persona_id !== null && selectedPersonaIds.includes(question.persona_id));

      const typeMatch = question.type ? selectedTypes.includes(question.type) : selectedTypes.length === 2; // Show NA if both filters selected
      const scopeMatch = question.scope ? selectedScopes.includes(question.scope) : selectedScopes.length === 2; // Show NA if both filters selected
      return personaMatch && typeMatch && scopeMatch;
    });
  }, [approvedQuestions, selectedPersonaIds, selectedTypes, selectedScopes, personas.length]);

  // Filter options for table header filters
  const personaFilterOptions: FilterOption<number>[] = useMemo(() => {
    return personas.map((p) => ({ value: p.id, label: p.title }));
  }, [personas]);

  const typeFilterOptions: FilterOption<string>[] = useMemo(() => [
    { value: "typical", label: "Typical" },
    { value: "edge", label: "Edge" },
  ], []);

  const scopeFilterOptions: FilterOption<string>[] = useMemo(() => [
    { value: "in_kb", label: "In KB" },
    { value: "out_kb", label: "Out KB" },
  ], []);

  const handleReviewQuestion = async (questionId: number, action: "approve" | "reject") => {
    setProcessingQuestionId(questionId);
    try {
      if (action === "approve") {
        await questionApi.approve(questionId);
      } else {
        await questionApi.reject(questionId);
      }
      const updatedNewQuestions = newQuestions.filter(q => q.id !== questionId);
      setNewQuestions(updatedNewQuestions);

      if (updatedNewQuestions.length === 0) {
        setJobStatus(null);
        setSimilarQuestionsMap({});
        await fetchData();
      }
    } catch (error) {
      console.error(`Failed to ${action} question:`, error);
      setError(`Failed to ${action} question. Please try again.`);
    } finally {
      setProcessingQuestionId(null);
    }
  };

  const handleBulkApprove = async () => {
    setBulkApproving(true);
    try {
      await questionApi.bulkApprove(newQuestions.map(q => q.id));
      setNewQuestions([]);
      setJobStatus(null);
      setSimilarQuestionsMap({});
      await fetchData();
    } catch (error) {
      console.error("Failed to bulk approve questions:", error);
      setError("Failed to approve all questions. Please try again.");
    } finally {
      setBulkApproving(false);
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
      setError("Failed to update question. Please try again.");
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

  const triggerDownload = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const handleExportQuestions = async () => {
    try {
      const [questionsRes, personasRes] = await Promise.all([
        targetApi.exportQuestions(targetId, "json"),
        targetApi.exportPersonas(targetId, "json"),
      ]);
      triggerDownload(questionsRes.data, `questions_target_${targetId}.json`);
      triggerDownload(personasRes.data, `personas_target_${targetId}.json`);
    } catch (error) {
      console.error("Failed to export:", error);
      setError("Failed to export data. Please try again.");
    }
  };

  const handleDeleteQuestion = async (questionId: number) => {
    try {
      await questionApi.delete(questionId);
      fetchData();
    } catch (error) {
      console.error("Failed to delete question:", error);
    }
  };

  const getPersonaTitle = (personaId: number | null) => {
    if (personaId === null) return "NA";
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
      <Tabs
        value={activeTab}
        onChange={(_, newValue) => setActiveTab(newValue)}
        sx={{ mb: 3, borderBottom: 1, borderColor: "divider" }}
      >
        <Tab label="Questions" />
        <Tab label="Manage Personas" />
      </Tabs>

      {activeTab === 1 && (
        personas.length === 0 ? (
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            minHeight="30vh"
            gap={2}
            sx={{ maxWidth: 500, mx: "auto", textAlign: "center" }}
          >
            <Typography variant="h5" fontWeight={600}>
              No personas yet
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Personas define the types of users that will interact with your
              chatbot. Add some to get started.
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setAddPersonasOpen(true)}
            >
              Add Personas
            </Button>
          </Box>
        ) : (
          <Box>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="body2" color="text.secondary">
                {personas.length} persona{personas.length !== 1 ? "s" : ""} total
                {" | "}
                {personas.filter((p) => p.status === "approved").length} approved
              </Typography>
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={() => setAddPersonasOpen(true)}
                size="small"
              >
                Add Personas
              </Button>
            </Box>
            <PersonaTable
              personas={personas}
              onPersonasChanged={fetchData}
              onError={setError}
            />
          </Box>
        )
      )}

      <AddPersonasDialog
        open={addPersonasOpen}
        onClose={() => setAddPersonasOpen(false)}
        targetId={targetId}
        onPersonasAdded={fetchData}
      />

      {activeTab === 0 && <>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Job Status Section */}
      {jobStatus && (
        <Card variant="outlined" sx={{ mb: 3, backgroundColor: "grey.100" }}>
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
                <Box display="flex" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                  <Alert severity="info" sx={{ flex: 1, mr: 2 }}>
                    Questions generated. Scroll down to accept or reject.
                  </Alert>
                  {newQuestions.length > 1 && (
                    <Button
                      variant="contained"
                      color="success"
                      startIcon={bulkApproving ? <CircularProgress size={20} color="inherit" /> : <CheckCircleIcon />}
                      onClick={handleBulkApprove}
                      disabled={bulkApproving || processingQuestionId !== null}
                    >
                      Approve All ({newQuestions.length})
                    </Button>
                  )}
                </Box>

                {newQuestions.map((newQ) => {
                  const isEditing = editingQuestionId === newQ.id;
                  return (
                  <Card key={newQ.id} sx={{ mb: 2, border: "2px solid", borderColor: "primary.main" }}>
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
                                    value={editedType ?? ""}
                                    onChange={(e) => setEditedType(!e.target.value ? null : e.target.value as QuestionType)}
                                    label="Type"
                                  >
                                    <MenuItem value="">NA</MenuItem>
                                    <MenuItem value={QuestionType.TYPICAL}>Typical</MenuItem>
                                    <MenuItem value={QuestionType.EDGE}>Edge</MenuItem>
                                  </Select>
                                </FormControl>
                                <FormControl sx={{ minWidth: 150 }}>
                                  <InputLabel id={`edit-scope-${newQ.id}`}>Scope</InputLabel>
                                  <Select
                                    labelId={`edit-scope-${newQ.id}`}
                                    value={editedScope ?? ""}
                                    onChange={(e) => setEditedScope(!e.target.value ? null : e.target.value as QuestionScope)}
                                    label="Scope"
                                  >
                                    <MenuItem value="">NA</MenuItem>
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
                                <Chip
                                  label={newQ.type || "NA"}
                                  size="small"
                                  color={newQ.type === "edge" ? "warning" : "default"}
                                />
                                <Chip
                                  label={newQ.scope ? (newQ.scope === "in_kb" ? "In KB" : "Out KB") : "NA"}
                                  size="small"
                                  color={newQ.scope === "in_kb" ? "success" : newQ.scope === "out_kb" ? "info" : "default"}
                                />
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
                                onClick={() => handleReviewQuestion(newQ.id, "approve")}
                                disabled={processingQuestionId !== null}
                              >
                                {processingQuestionId === newQ.id ? <CircularProgress size={20} /> : "Approve"}
                              </Button>
                              <Button
                                variant="outlined"
                                color="error"
                                startIcon={<CancelIcon />}
                                onClick={() => handleReviewQuestion(newQ.id, "reject")}
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
                            <Box key={similarQ.id} sx={{ pl: 2, py: 1, backgroundColor: "grey.50", borderRadius: 1, mb: 1 }}>
                              <Typography variant="body2" color="text.secondary">
                                {similarQ.text}
                              </Typography>
                              <Box display="flex" gap={1} mt={0.5}>
                                <Chip label={getPersonaTitle(similarQ.persona_id)} size="small" variant="outlined" />
                                <Chip label={similarQ.type || "NA"} size="small" variant="outlined" />
                                <Chip
                                  label={similarQ.scope ? (similarQ.scope === "in_kb" ? "In KB" : "Out KB") : "NA"}
                                  size="small"
                                  variant="outlined"
                                />
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
          {/* Generate More Button + Download */}
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Button
              variant="outlined"
              onClick={() => setGenerateModalOpen(true)}
            >
              Add Questions
            </Button>
            <Tooltip title="Download questions & personas">
              <span>
                <IconButton
                  onClick={handleExportQuestions}
                  disabled={loading || !hasQuestions}
                  sx={{
                    bgcolor: "secondary.main",
                    color: "white",
                    borderRadius: 1,
                    "&:hover": { bgcolor: "secondary.dark" },
                    "&.Mui-disabled": { bgcolor: "action.disabledBackground", color: "action.disabled" },
                  }}
                >
                  <DownloadIcon />
                </IconButton>
              </span>
            </Tooltip>
          </Box>

          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 70 }}>ID</TableCell>
                  <TableCell>Question</TableCell>
                  <TableCell align="center" sx={{ width: 160 }}>
                    <TableHeaderFilter
                      label="Persona"
                      options={personaFilterOptions}
                      value={selectedPersonaIds}
                      onChange={setSelectedPersonaIds}
                      allSelectedLabel="All Personas"
                    />
                  </TableCell>
                  <TableCell align="center" sx={{ width: 120 }}>
                    <TableHeaderFilter
                      label="Type"
                      options={typeFilterOptions}
                      value={selectedTypes}
                      onChange={setSelectedTypes}
                      allSelectedLabel="All Types"
                    />
                  </TableCell>
                  <TableCell align="center" sx={{ width: 120 }}>
                    <TableHeaderFilter
                      label="Scope"
                      options={scopeFilterOptions}
                      value={selectedScopes}
                      onChange={setSelectedScopes}
                      allSelectedLabel="All Scopes"
                    />
                  </TableCell>
                  <TableCell align="center" width={50}></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredQuestions.map((question) => (
                  <TableRow key={question.id}>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary" fontWeight={600}>{question.id}</Typography>
                    </TableCell>
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
                        label={question.type || "NA"}
                        size="small"
                        color={question.type === "edge" ? "warning" : "default"}
                        variant={question.type === "edge" ? "filled" : "outlined"}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={question.scope ? (question.scope === "in_kb" ? "In KB" : "Out KB") : "NA"}
                        size="small"
                        color={question.scope === "in_kb" ? "success" : question.scope === "out_kb" ? "info" : "default"}
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

      </>}

      <GenerateEvalsModal
        open={generateModalOpen}
        onClose={() => setGenerateModalOpen(false)}
        targetId={targetId}
        onSuccess={fetchData}
        onJobLaunched={handleJobLaunched}
        onQuestionsUploaded={async () => {
          const freshQuestions = await fetchData();
          if (freshQuestions) {
            await loadPendingQuestionsForReview(freshQuestions);
          }
        }}
      />
    </Box>
  );
}
