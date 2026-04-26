"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import {
  Box,
  Typography,
  Button,
  CircularProgress,
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
  Tabs,
  Tab,
  TablePagination,
  Tooltip,
  useTheme,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import {
  IconCircleCheck,
  IconCircleX,
  IconDeviceFloppy,
  IconDownload,
  IconMessageQuestion,
  IconPencil,
  IconPlus,
  IconTrash,
  IconUsers,
} from "@tabler/icons-react";
import { TableHeaderFilter, type FilterOption } from "@/components/shared";
import { useParams } from "next/navigation";
import { targetApi, questionApi, personaApi, jobApi } from "@/lib/api";
import { TargetResponse, QuestionResponse, PersonaResponse, JobStatus, QuestionType, QuestionScope, Status } from "@/lib/types";
import { JOB_POLLING_INTERVAL } from "@/lib/constants";
import GenerateEvalsModal from "@/components/GenerateEvalsModal";
import PersonaTable from "@/components/questions/PersonaTable";
import AddPersonasModal from "@/components/questions/AddPersonasModal";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import { actionIconProps, compactActionIconProps } from "@/lib/iconStyles";
import {
  compactChipSx,
  getTableBodyRowSx,
  tableContainerSx,
  tableHeaderCellSx,
  tableHeaderRowSx,
  tabSx,
  tabsSx,
} from "@/lib/uiStyles";

const cardSx = {
  p: 2.5,
  borderRadius: 2,
  border: "1px solid",
  borderColor: "grey.200",
  bgcolor: "background.paper",
  display: "flex",
  flexDirection: "column",
} as const;

export default function QuestionsPage() {
  const params = useParams();
  const targetId = parseInt(params.id as string);
  const theme = useTheme();

  const [activeTab, setActiveTab] = useState(0);
  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [questions, setQuestions] = useState<QuestionResponse[]>([]);
  const [personas, setPersonas] = useState<PersonaResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [addPersonasOpen, setAddPersonasOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [jobStatus, setJobStatus] = useState<"running" | "finding_similar" | "ready_for_review" | null>(null);
  const [generationSummary, setGenerationSummary] = useState<string | null>(null);
  const [similarQuestionsMap, setSimilarQuestionsMap] = useState<Record<number, QuestionResponse[]>>({});
  const [processingQuestionId, setProcessingQuestionId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bulkApproving, setBulkApproving] = useState(false);
  const [questionToDelete, setQuestionToDelete] = useState<QuestionResponse | null>(null);

  // Edit mode state
  const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
  const [editedText, setEditedText] = useState("");
  const [editedType, setEditedType] = useState<QuestionType | null>(QuestionType.TYPICAL);
  const [editedScope, setEditedScope] = useState<QuestionScope | null>(QuestionScope.IN_KB);

  // Filter states
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<number[]>([]);
  const [selectedTypes, setSelectedTypes] = useState<string[]>(["typical", "edge"]);
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["in_kb", "out_kb"]);
  const [page, setPage] = useState(0);
  const rowsPerPage = 10;

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

  const fetchData = useCallback(async () => {
    try {
      const [targetRes, questionsRes, personasRes] = await Promise.all([
        targetApi.get(targetId),
        questionApi.listAllByTarget(targetId),
        personaApi.list(targetId),
      ]);

      setTarget(targetRes.data);
      setQuestions(questionsRes);
      setPersonas(personasRes.data);
      return questionsRes;
    } catch (error) {
      console.error("Failed to fetch data:", error);
      return [];
    } finally {
      setLoading(false);
    }
  }, [targetId]);

  const loadQuestionsForReview = useCallback(async (allQuestions: QuestionResponse[]) => {
    const reviewableQuestions = allQuestions.filter(
      (q) => q.status === Status.PENDING || q.status === Status.EDITED
    );
    if (reviewableQuestions.length === 0) {
      setJobStatus(null);
      setSimilarQuestionsMap({});
      return;
    }

    setJobStatus("finding_similar");

    const similarMap = await buildSimilarMap(reviewableQuestions, allQuestions);
    setSimilarQuestionsMap(similarMap);
    setJobStatus("ready_for_review");
  }, [buildSimilarMap]);

  useEffect(() => {
    const initialize = async () => {
      const freshQuestions = await fetchData();
      if (freshQuestions && freshQuestions.length > 0 && !activeJobId && !jobStatus) {
        const reviewableQuestions = freshQuestions.filter(
          (q) => q.status === Status.PENDING || q.status === Status.EDITED
        );
        if (reviewableQuestions.length > 0) {
          await loadQuestionsForReview(freshQuestions);
        }
      }
    };
    initialize();
  }, [targetId, activeJobId, jobStatus, fetchData, loadQuestionsForReview]);

  useEffect(() => {
    if (personas.length > 0) {
      const allPersonaIds = personas.map((p) => p.id);
      setSelectedPersonaIds((prev) => {
        if (prev.length === 0) {
          return allPersonaIds;
        }
        const newPersonaIds = allPersonaIds.filter(id => !prev.includes(id));
        return newPersonaIds.length > 0 ? [...prev, ...newPersonaIds] : prev;
      });
    }
  }, [personas]);

  useEffect(() => {
    if (!activeJobId) return;

    const interval = setInterval(async () => {
      try {
        const response = await jobApi.get(activeJobId);
        if (response.data.status === JobStatus.COMPLETED) {
          clearInterval(interval);
          setJobStatus("finding_similar");

          const jobQuestionsRes = await jobApi.getQuestions(activeJobId);
          const generatedCount = jobQuestionsRes.data.length;
          const requestedCount = response.data.count_requested;
          const freshQuestions = await fetchData();
          if (freshQuestions.length > 0) {
            await loadQuestionsForReview(freshQuestions);
          } else {
            setJobStatus(null);
          }
          setGenerationSummary(
            generatedCount < requestedCount
              ? `Generated ${generatedCount} of ${requestedCount} requested questions. Review the generated questions before continuing.`
              : null
          );
          setActiveJobId(null);
        } else if (response.data.status === JobStatus.FAILED) {
          clearInterval(interval);
          setActiveJobId(null);
          setJobStatus(null);
          setGenerationSummary(null);
          setError("Question generation failed. No questions were added.");
          console.error("Job failed:", activeJobId);
        }
      } catch (error) {
        console.error("Failed to check job status:", error);
      }
    }, JOB_POLLING_INTERVAL);

    return () => clearInterval(interval);
  }, [activeJobId, fetchData, loadQuestionsForReview]);

  const approvedQuestions = useMemo(() => {
    return questions.filter((question) => question.status === Status.APPROVED);
  }, [questions]);

  const reviewQuestions = useMemo(() => {
    return questions.filter(
      (question) => question.status === Status.PENDING || question.status === Status.EDITED
    );
  }, [questions]);

  const filteredQuestions = useMemo(() => {
    return approvedQuestions.filter((question) => {
      const allPersonasSelected = selectedPersonaIds.length === personas.length;
      const personaMatch =
        selectedPersonaIds.length === 0 ||
        allPersonasSelected ||
        (question.persona_id !== null && selectedPersonaIds.includes(question.persona_id));

      const typeMatch = question.type ? selectedTypes.includes(question.type) : selectedTypes.length === 2;
      const scopeMatch = question.scope ? selectedScopes.includes(question.scope) : selectedScopes.length === 2;
      return personaMatch && typeMatch && scopeMatch;
    });
  }, [approvedQuestions, selectedPersonaIds, selectedTypes, selectedScopes, personas.length]);

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

  const summaryStats = useMemo(() => {
    const approvedPersonaCount = personas.filter((p) => p.status === "approved").length;

    const personasWithQuestions = personas
      .map((p) => ({
        title: p.title,
        count: approvedQuestions.filter((q) => q.persona_id === p.id).length,
      }))
      .filter((p) => p.count > 0)
      .sort((a, b) => b.count - a.count);
    const perPersona = personasWithQuestions.slice(0, 5);
    const remainingPersonaCount = personasWithQuestions.length - perPersona.length;
    const maxPerPersona = Math.max(...perPersona.map((p) => p.count), 1);

    const typicalCount = approvedQuestions.filter((q) => q.type === "typical").length;
    const edgeCount = approvedQuestions.filter((q) => q.type === "edge").length;
    const inKbCount = approvedQuestions.filter((q) => q.scope === "in_kb").length;
    const outKbCount = approvedQuestions.filter((q) => q.scope === "out_kb").length;

    return { approvedPersonaCount, perPersona, remainingPersonaCount, maxPerPersona, typicalCount, edgeCount, inKbCount, outKbCount };
  }, [approvedQuestions, personas]);

  const handleReviewQuestion = async (questionId: number, action: "approve" | "reject") => {
    setProcessingQuestionId(questionId);
    try {
      const response = action === "approve"
        ? await questionApi.approve(questionId)
        : await questionApi.reject(questionId);

      setQuestions((prev) => prev.map((question) => (
        question.id === questionId ? response.data : question
      )));

      if (reviewQuestions.length === 1) {
        setJobStatus(null);
        setSimilarQuestionsMap({});
        setGenerationSummary(null);
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
      const reviewQuestionIds = reviewQuestions.map((question) => question.id);
      await questionApi.bulkApprove(reviewQuestionIds);
      setQuestions((prev) => prev.map((question) => (
        reviewQuestionIds.includes(question.id)
          ? { ...question, status: Status.APPROVED }
          : question
      )));
      setJobStatus(null);
      setSimilarQuestionsMap({});
      setGenerationSummary(null);
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
      const question = reviewQuestions.find(q => q.id === questionId);
      if (!question) return;

      const updates: {
        text?: string;
        type?: QuestionType | null;
        scope?: QuestionScope | null;
      } = {};

      if (editedText !== question.text) {
        updates.text = editedText;
      }
      if (editedType !== question.type) {
        updates.type = editedType;
      }
      if (editedScope !== question.scope) {
        updates.scope = editedScope;
      }

      if (Object.keys(updates).length > 0) {
        const response = await questionApi.update(questionId, updates);
        setQuestions((prev) => prev.map((q) => (
          q.id === questionId ? response.data : q
        )));
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
    setGenerationSummary(null);
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
      const res = await targetApi.exportQuestions(targetId, "json");
      triggerDownload(res.data, `questions_target_${targetId}.json`);
    } catch (error) {
      console.error("Failed to export questions:", error);
      setError("Failed to export questions. Please try again.");
    }
  };

  const handleExportPersonas = async () => {
    try {
      const res = await targetApi.exportPersonas(targetId, "json");
      triggerDownload(res.data, `personas_target_${targetId}.json`);
    } catch (error) {
      console.error("Failed to export personas:", error);
      setError("Failed to export personas. Please try again.");
    }
  };

  const handleDeleteConfirm = async () => {
    if (!questionToDelete) return;
    await questionApi.delete(questionToDelete.id);
    fetchData();
  };

  const getPersonaTitle = (personaId: number | null) => {
    if (personaId === null) return "NA";
    const persona = personas.find((p) => p.id === personaId);
    return persona?.title || "Unknown";
  };

  if (loading) {
    return (
      <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="30vh" gap={1}>
        <CircularProgress size={32} color="primary" />
        <Typography variant="body2" color="text.secondary">Loading...</Typography>
      </Box>
    );
  }

  if (!target) {
    return null;
  }

  const hasQuestions = approvedQuestions.length > 0;
  const maxPage = Math.max(0, Math.ceil(filteredQuestions.length / rowsPerPage) - 1);
  const currentPage = Math.min(page, maxPage);

  return (
    <Box>
      {/* ── Page Header ── */}
      <Box mb={3}>
        <Typography variant="h5" fontWeight={700}>Evaluation Set</Typography>
        <Typography variant="body2" color="text.secondary">
          Manage evaluation questions for this target
        </Typography>
      </Box>

      {/* ── Summary Cards ── */}
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr 2fr 2fr", gap: 2, mb: 3 }}>
        <Box sx={cardSx}>
          <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.5, color: "text.secondary", textTransform: "uppercase" }}>
            Total Questions
          </Typography>
          <Box sx={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
            <Typography variant="h3" fontWeight={700} sx={{ color: "primary.main" }}>{approvedQuestions.length}</Typography>
            <Typography variant="caption" sx={{ color: reviewQuestions.length > 0 ? "text.secondary" : "transparent", mt: 0.5 }}>
              {reviewQuestions.length > 0 ? `${reviewQuestions.length} pending review` : " "}
            </Typography>
          </Box>
        </Box>

        <Box sx={cardSx}>
          <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.5, color: "text.secondary", textTransform: "uppercase" }}>
            Personas
          </Typography>
          <Box sx={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
            <Typography variant="h3" fontWeight={700} sx={{ color: "primary.main" }}>{personas.length}</Typography>
            <Typography variant="caption" sx={{ color: "text.secondary", mt: 0.5 }}>
              {summaryStats.approvedPersonaCount} approved
            </Typography>
          </Box>
        </Box>

        <Box sx={cardSx}>
          <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.5, color: "text.secondary", textTransform: "uppercase", mb: 1 }}>
            Per Persona
          </Typography>
          {summaryStats.perPersona.length === 0 ? (
            <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>No data yet</Typography>
          ) : (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
              {summaryStats.perPersona.map((p) => (
                <Box key={p.title} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <Typography
                    sx={{
                      fontSize: 11,
                      color: "text.secondary",
                      minWidth: 72,
                      maxWidth: 72,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {p.title}
                  </Typography>
                  <Box sx={{ flex: 1, height: 6, bgcolor: "grey.200", borderRadius: 3, overflow: "hidden" }}>
                    <Box
                      sx={{
                        width: `${(p.count / summaryStats.maxPerPersona) * 100}%`,
                        height: "100%",
                        bgcolor: "primary.main",
                        borderRadius: 3,
                        transition: "width 0.3s",
                      }}
                    />
                  </Box>
                  <Typography sx={{ fontSize: 11, color: "text.secondary", minWidth: 16, textAlign: "right" }}>
                    {p.count}
                  </Typography>
                </Box>
              ))}
              {summaryStats.remainingPersonaCount > 0 && (
                <Typography sx={{ fontSize: 10, color: "text.disabled", mt: 0.5 }}>
                  +{summaryStats.remainingPersonaCount} more
                </Typography>
              )}
            </Box>
          )}
        </Box>

        <Box sx={cardSx}>
          <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.5, color: "text.secondary", textTransform: "uppercase", mb: 1 }}>
            Distribution
          </Typography>
          {approvedQuestions.length === 0 ? (
            <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>No data yet</Typography>
          ) : (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
              <Box>
                <Typography sx={{ fontSize: 11, color: "text.secondary", mb: 0.5, fontWeight: 600 }}>Type</Typography>
                <Box sx={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", bgcolor: "grey.200" }}>
                  <Box sx={{ width: `${(summaryStats.typicalCount / approvedQuestions.length) * 100}%`, bgcolor: "success.main", transition: "width 0.3s" }} />
                  <Box sx={{ width: `${(summaryStats.edgeCount / approvedQuestions.length) * 100}%`, bgcolor: "warning.main", transition: "width 0.3s" }} />
                </Box>
                <Box sx={{ display: "flex", mt: 0.25 }}>
                  {summaryStats.typicalCount > 0 && (
                    <Typography sx={{ fontSize: 10, color: "success.dark", fontWeight: 600, width: `${(summaryStats.typicalCount / approvedQuestions.length) * 100}%`, minWidth: "fit-content" }}>
                      Typical ({summaryStats.typicalCount})
                    </Typography>
                  )}
                  {summaryStats.edgeCount > 0 && (
                    <Typography sx={{ fontSize: 10, color: "warning.dark", fontWeight: 600, width: `${(summaryStats.edgeCount / approvedQuestions.length) * 100}%`, minWidth: "fit-content" }}>
                      Edge ({summaryStats.edgeCount})
                    </Typography>
                  )}
                </Box>
              </Box>
              <Box>
                <Typography sx={{ fontSize: 11, color: "text.secondary", mb: 0.5, fontWeight: 600 }}>Scope</Typography>
                {(() => {
                  const naCount = approvedQuestions.length - summaryStats.inKbCount - summaryStats.outKbCount;
                  const total = approvedQuestions.length;
                  return (
                    <>
                      <Box sx={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", bgcolor: "grey.200" }}>
                        <Box sx={{ width: `${(summaryStats.inKbCount / total) * 100}%`, bgcolor: "info.main", transition: "width 0.3s" }} />
                        <Box sx={{ width: `${(summaryStats.outKbCount / total) * 100}%`, bgcolor: "secondary.main", transition: "width 0.3s" }} />
                        <Box sx={{ width: `${(naCount / total) * 100}%`, bgcolor: "grey.400", transition: "width 0.3s" }} />
                      </Box>
                      <Box sx={{ display: "flex", mt: 0.25 }}>
                        {summaryStats.inKbCount > 0 && (
                          <Typography sx={{ fontSize: 10, color: "info.dark", fontWeight: 600, width: `${(summaryStats.inKbCount / total) * 100}%`, minWidth: "fit-content" }}>
                            In KB ({summaryStats.inKbCount})
                          </Typography>
                        )}
                        {summaryStats.outKbCount > 0 && (
                          <Typography sx={{ fontSize: 10, color: "secondary.dark", fontWeight: 600, width: `${(summaryStats.outKbCount / total) * 100}%`, minWidth: "fit-content" }}>
                            Out KB ({summaryStats.outKbCount})
                          </Typography>
                        )}
                        {naCount > 0 && (
                          <Typography sx={{ fontSize: 10, color: "text.disabled", fontWeight: 600, width: `${(naCount / total) * 100}%`, minWidth: "fit-content" }}>
                            NA ({naCount})
                          </Typography>
                        )}
                      </Box>
                    </>
                  );
                })()}
              </Box>
            </Box>
          )}
        </Box>
      </Box>

      {/* ── Tabs ── */}
      <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}>
        <Tabs
          value={activeTab}
          onChange={(_, newValue) => setActiveTab(newValue)}
          sx={tabsSx}
        >
          <Tab label="Evaluation Set" sx={tabSx} />
          <Tab label="Manage Personas" sx={tabSx} />
        </Tabs>
      </Box>

      {/* ── Personas Tab ── */}
      {activeTab === 1 && (
        personas.length === 0 ? (
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            minHeight="30vh"
            gap={2}
            sx={{
              maxWidth: 500,
              mx: "auto",
              textAlign: "center",
              border: "2px dashed",
              borderColor: "grey.300",
              borderRadius: 3,
              py: 8,
              px: 4,
              bgcolor: "grey.50",
            }}
          >
            <IconUsers size={48} stroke={1.75} color={theme.palette.grey[400]} />
            <Typography variant="h6" fontWeight={700}>
              No personas yet
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Personas define the types of users that will interact with your
              target application. Add some to get started.
            </Typography>
            <Button
              variant="contained"
              startIcon={<IconPlus {...actionIconProps} />}
              onClick={() => setAddPersonasOpen(true)}
            >
              Add Personas
            </Button>
          </Box>
        ) : (
          <Box sx={tableContainerSx}>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", px: 2, pt: 2, pb: 1 }}>
              <Typography variant="subtitle1" fontWeight={700} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                Personas
                <Chip label={personas.length} size="small" sx={{ height: 18, fontSize: "0.65rem", "& .MuiChip-label": { px: 0.75 } }} />
              </Typography>
              <Box display="flex" gap={1} alignItems="center">
                <Button
                  size="small"
                  startIcon={<IconPlus {...actionIconProps} />}
                  onClick={() => setAddPersonasOpen(true)}
                  sx={{
                    border: "1px solid",
                    borderColor: "primary.light",
                    color: "primary.light",
                    "&:hover": { bgcolor: "primary.light", color: "#fff" },
                  }}
                >
                  Add Personas
                </Button>
                <Tooltip title="Download as JSON">
                  <IconButton
                    size="small"
                    onClick={handleExportPersonas}
                    sx={{ bgcolor: "secondary.main", color: "white", borderRadius: 1, "&:hover": { bgcolor: "secondary.dark" } }}
                  >
                    <IconDownload {...actionIconProps} />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>
            <PersonaTable
              personas={personas}
              onPersonasChanged={fetchData}
              onError={setError}
            />
          </Box>
        )
      )}

      <AddPersonasModal
        open={addPersonasOpen}
        onClose={() => setAddPersonasOpen(false)}
        targetId={targetId}
        onPersonasAdded={fetchData}
      />

      {/* ── Questions Tab ── */}
      {activeTab === 0 && (
        <>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {/* Job Status Section */}
          {jobStatus && (
            <Card
              variant="outlined"
              sx={{
                mb: 3,
                background: `linear-gradient(135deg, ${alpha(theme.palette.primary.light, 0.06)}, ${alpha(theme.palette.primary.light, 0.02)})`,
                borderColor: alpha(theme.palette.primary.main, 0.15),
              }}
            >
              <CardContent>
                <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, color: "primary.main", textTransform: "uppercase", mb: 2 }}>
                  Generation Job
                </Typography>

                {(jobStatus === "running" || jobStatus === "finding_similar") && (
                  <Box display="flex" alignItems="center" gap={2}>
                    <CircularProgress size={24} color="primary" />
                    <Typography variant="body2" color="text.secondary">
                      Generating questions, please wait...
                    </Typography>
                  </Box>
                )}

                {jobStatus === "ready_for_review" && (
                  <>
                    <Box display="flex" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                      <Box sx={{ flex: 1, mr: 2 }}>
                        {generationSummary && (
                          <Alert severity="warning" sx={{ mb: 1 }}>
                            {generationSummary}
                          </Alert>
                        )}
                        <Alert severity="info">
                          Questions needing review are shown below. Approve or reject each one before continuing.
                        </Alert>
                      </Box>
                      {reviewQuestions.length > 1 && (
                        <Button
                          variant="contained"
                          color="success"
                          startIcon={bulkApproving ? <CircularProgress size={20} color="inherit" /> : <IconCircleCheck {...actionIconProps} />}
                          onClick={handleBulkApprove}
                          disabled={bulkApproving || processingQuestionId !== null}
                        >
                          Approve All ({reviewQuestions.length})
                        </Button>
                      )}
                    </Box>

                    {reviewQuestions.map((newQ) => {
                      const isEditing = editingQuestionId === newQ.id;
                      return (
                        <Card
                          key={newQ.id}
                          sx={{
                            mb: 2,
                            border: "1px solid",
                            borderColor: "grey.300",
                            borderTop: "3px solid",
                            borderTopColor: "primary.main",
                            borderRadius: 2,
                          }}
                        >
                          <CardContent>
                            <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                              <Box flex={1}>
                                <Typography
                                  sx={{
                                    fontSize: 10,
                                    fontWeight: 700,
                                    letterSpacing: 1,
                                    color: "primary.main",
                                    textTransform: "uppercase",
                                    mb: 1,
                                  }}
                                >
                                  New Question
                                </Typography>

                                {isEditing ? (
                                  <Box
                                    sx={{
                                      bgcolor: alpha(theme.palette.primary.light, 0.04),
                                      borderRadius: 1.5,
                                      p: 2,
                                      mb: 2,
                                    }}
                                  >
                                    <Box display="flex" flexDirection="column" gap={2}>
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
                                  </Box>
                                ) : (
                                  <>
                                    <Typography sx={{ fontSize: 15, lineHeight: 1.6, mb: 2 }}>
                                      {newQ.text}
                                    </Typography>
                                    <Box display="flex" gap={1} mt={1}>
                                      <Chip
                                        label={newQ.status === Status.EDITED ? "Edited" : "Pending"}
                                        size="small"
                                        sx={{
                                          ...compactChipSx,
                                          ...(newQ.status === Status.EDITED
                                            ? { bgcolor: alpha(theme.palette.info.main, 0.08), color: "info.main" }
                                            : { bgcolor: alpha(theme.palette.warning.main, 0.08), color: "warning.dark" }),
                                        }}
                                      />
                                      <Chip
                                        label={getPersonaTitle(newQ.persona_id)}
                                        size="small"
                                        sx={{ ...compactChipSx, fontWeight: 500, bgcolor: "grey.100", color: "text.secondary" }}
                                      />
                                      <Chip
                                        label={newQ.type || "NA"}
                                        size="small"
                                        variant="outlined"
                                        sx={{
                                          ...compactChipSx,
                                          ...(newQ.type === "edge"
                                            ? { bgcolor: alpha(theme.palette.warning.main, 0.1), color: "warning.dark", borderColor: alpha(theme.palette.warning.main, 0.3) }
                                            : newQ.type === "typical"
                                            ? { bgcolor: alpha(theme.palette.success.main, 0.1), color: "success.dark", borderColor: alpha(theme.palette.success.main, 0.3) }
                                            : { borderColor: "grey.300", color: "text.secondary" }),
                                        }}
                                      />
                                      <Chip
                                        label={newQ.scope ? (newQ.scope === "in_kb" ? "In KB" : "Out KB") : "NA"}
                                        size="small"
                                        variant="outlined"
                                        sx={{
                                          ...compactChipSx,
                                          ...(newQ.scope === "in_kb"
                                            ? { bgcolor: alpha(theme.palette.info.main, 0.1), color: "info.dark", borderColor: alpha(theme.palette.info.main, 0.3) }
                                            : newQ.scope === "out_kb"
                                            ? { bgcolor: alpha(theme.palette.secondary.main, 0.1), color: "secondary.dark", borderColor: alpha(theme.palette.secondary.main, 0.3) }
                                            : { borderColor: "grey.300", color: "text.secondary" }),
                                        }}
                                      />
                                    </Box>
                                  </>
                                )}
                              </Box>
                              <Box display="flex" gap={0.75}>
                                {isEditing ? (
                                  <>
                                    <Button
                                      variant="contained"
                                      size="small"
                                      startIcon={<IconDeviceFloppy {...actionIconProps} />}
                                      onClick={() => handleSaveEdit(newQ.id)}
                                      disabled={processingQuestionId === newQ.id || !editedText.trim()}
                                    >
                                      {processingQuestionId === newQ.id ? <CircularProgress size={20} /> : "Save"}
                                    </Button>
                                    <Button
                                      variant="outlined"
                                      size="small"
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
                                      size="small"
                                      startIcon={<IconPencil {...actionIconProps} />}
                                      onClick={() => handleStartEdit(newQ)}
                                      disabled={processingQuestionId !== null}
                                    >
                                      Edit
                                    </Button>
                                    <Button
                                      variant="contained"
                                      color="success"
                                      size="small"
                                      startIcon={<IconCircleCheck {...actionIconProps} />}
                                      onClick={() => handleReviewQuestion(newQ.id, "approve")}
                                      disabled={processingQuestionId !== null}
                                    >
                                      {processingQuestionId === newQ.id ? <CircularProgress size={20} /> : "Approve"}
                                    </Button>
                                    <Button
                                      variant="outlined"
                                      color="error"
                                      size="small"
                                      startIcon={<IconCircleX {...actionIconProps} />}
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

                    {reviewQuestions.length === 0 && (
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
              sx={{
                maxWidth: 600,
                mx: "auto",
                textAlign: "center",
                border: "2px dashed",
                borderColor: "grey.300",
                borderRadius: 3,
                py: 8,
                px: 4,
                bgcolor: "grey.50",
              }}
            >
              <IconMessageQuestion size={48} stroke={1.75} color={theme.palette.grey[400]} />
              <Typography variant="h6" fontWeight={700}>
                Start by generating evaluation questions
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 1 }}>
                Evaluation questions are used to systematically test how your target application responds across different scenarios. Generate them automatically, and edit them later.
              </Typography>
              <Button
                variant="contained"
                size="large"
                onClick={() => setGenerateModalOpen(true)}
              >
                Generate Questions
              </Button>
            </Box>
          ) : (<>
            <Box sx={tableContainerSx}>
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", px: 2, pt: 2, pb: 1 }}>
                <Typography variant="subtitle1" fontWeight={700} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                  Questions
                  <Chip label={filteredQuestions.length} size="small" sx={{ height: 18, fontSize: "0.65rem", "& .MuiChip-label": { px: 0.75 } }} />
                </Typography>
                <Box display="flex" gap={1} alignItems="center">
                  <Button
                    size="small"
                    startIcon={<IconPlus {...actionIconProps} />}
                    onClick={() => setGenerateModalOpen(true)}
                    sx={{
                      border: "1px solid",
                      borderColor: "primary.light",
                      color: "primary.light",
                      "&:hover": { bgcolor: "primary.light", color: "#fff" },
                    }}
                  >
                    Add Questions
                  </Button>
                  <Tooltip title="Download as JSON">
                    <IconButton
                      size="small"
                      onClick={handleExportQuestions}
                      sx={{ bgcolor: "secondary.main", color: "white", borderRadius: 1, "&:hover": { bgcolor: "secondary.dark" } }}
                    >
                      <IconDownload {...actionIconProps} />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow sx={tableHeaderRowSx}>
                      <TableCell sx={{ width: 70, ...tableHeaderCellSx }}>ID</TableCell>
                      <TableCell sx={tableHeaderCellSx}>Question</TableCell>
                      <TableCell sx={{ width: 220, ...tableHeaderCellSx }}>
                        <TableHeaderFilter
                          label="Persona"
                          options={personaFilterOptions}
                          value={selectedPersonaIds}
                          onChange={(ids) => { setSelectedPersonaIds(ids); setPage(0); }}
                          allSelectedLabel="All Personas"
                        />
                      </TableCell>
                      <TableCell sx={{ width: 110, ...tableHeaderCellSx }}>
                        <TableHeaderFilter
                          label="Type"
                          options={typeFilterOptions}
                          value={selectedTypes}
                          onChange={(types) => { setSelectedTypes(types); setPage(0); }}
                          allSelectedLabel="All Types"
                        />
                      </TableCell>
                      <TableCell sx={{ width: 110, ...tableHeaderCellSx }}>
                        <TableHeaderFilter
                          label="Scope"
                          options={scopeFilterOptions}
                          value={selectedScopes}
                          onChange={(scopes) => { setSelectedScopes(scopes); setPage(0); }}
                          allSelectedLabel="All Scopes"
                        />
                      </TableCell>
                      <TableCell sx={{ width: 50, py: 1.5 }} />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {filteredQuestions.slice(currentPage * rowsPerPage, currentPage * rowsPerPage + rowsPerPage).map((question) => (
                      <TableRow
                        key={question.id}
                        sx={getTableBodyRowSx(theme)}
                      >
                        <TableCell>
                          <Typography sx={{ fontFamily: "monospace", fontSize: 12, color: "text.secondary", fontWeight: 500 }}>
                            {question.id}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{question.text}</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="text.secondary">{getPersonaTitle(question.persona_id)}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={question.type || "NA"}
                            size="small"
                            variant="outlined"
                            sx={{
                              ...compactChipSx,
                              ...(question.type === "edge"
                                ? { bgcolor: alpha(theme.palette.warning.main, 0.1), color: "warning.dark", borderColor: alpha(theme.palette.warning.main, 0.3) }
                                : question.type === "typical"
                                ? { bgcolor: alpha(theme.palette.success.main, 0.1), color: "success.dark", borderColor: alpha(theme.palette.success.main, 0.3) }
                                : { borderColor: "grey.300", color: "text.secondary" }),
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={question.scope ? (question.scope === "in_kb" ? "In KB" : "Out KB") : "NA"}
                            size="small"
                            variant="outlined"
                            sx={{
                              ...compactChipSx,
                              ...(question.scope === "in_kb"
                                ? { bgcolor: alpha(theme.palette.info.main, 0.1), color: "info.dark", borderColor: alpha(theme.palette.info.main, 0.3) }
                                : question.scope === "out_kb"
                                ? { bgcolor: alpha(theme.palette.secondary.main, 0.1), color: "secondary.dark", borderColor: alpha(theme.palette.secondary.main, 0.3) }
                                : { borderColor: "grey.300", color: "text.secondary" }),
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <IconButton
                            size="small"
                            onClick={() => setQuestionToDelete(question)}
                            sx={{ opacity: 0.35, "&:hover": { opacity: 1, color: "error.main" } }}
                          >
                            <IconTrash {...compactActionIconProps} />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <TablePagination
                component="div"
                rowsPerPageOptions={[rowsPerPage]}
                rowsPerPage={rowsPerPage}
                count={filteredQuestions.length}
                page={currentPage}
                onPageChange={(_event, newPage) => setPage(newPage)}
              />
            </Box>
          </>)}
        </>
      )}

      {/* ── Dialogs ── */}
      <GenerateEvalsModal
        open={generateModalOpen}
        onClose={() => setGenerateModalOpen(false)}
        targetId={targetId}
        onSuccess={fetchData}
        onJobLaunched={handleJobLaunched}
        onQuestionsUploaded={async () => {
          const freshQuestions = await fetchData();
          if (freshQuestions) {
            await loadQuestionsForReview(freshQuestions);
          }
        }}
      />

      <ConfirmDeleteDialog
        open={!!questionToDelete}
        onClose={() => setQuestionToDelete(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete Question"
        itemName={
          questionToDelete?.text
            ? `"${questionToDelete.text.substring(0, 60)}${questionToDelete.text.length > 60 ? "..." : ""}"`
            : undefined
        }
        description="This will permanently remove this question from your evaluation set."
      />
    </Box>
  );
}
