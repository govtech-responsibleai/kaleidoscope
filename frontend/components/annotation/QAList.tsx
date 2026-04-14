"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  LinearProgress,
  List,
  Paper,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  ArrowBack as ArrowBackIcon,
  ArrowForward as ArrowForwardIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from "@mui/icons-material";
import { Answer, QAJob, QuestionResponse, QAMap, JobStatus, PersonaResponse, TargetRubricResponse } from "@/lib/types";

import { answerApi, personaApi } from "@/lib/api";
import { groupColors } from "@/lib/theme";
import QAItem from "./QAItem";
import QAContent from "./QAContent";
import AnnotationForm from "./AnnotationForm";

type FilterMode = "all" | "selected";

interface QAListProps {
  targetId: number;
  snapshotId: number | null;
  approvedQuestions: QuestionResponse[];
  questionsLoading: boolean;
  questionError: string | null;
  qaJobs: QAJob[];
  qaMap: QAMap;
  setQaMap: React.Dispatch<React.SetStateAction<QAMap>>;
  rubrics: TargetRubricResponse[];
  initialQuestionId?: number | null;
}

export default function QAList({
  targetId,
  snapshotId,
  approvedQuestions,
  questionsLoading,
  questionError,
  qaJobs,
  qaMap,
  setQaMap,
  rubrics,
  initialQuestionId,
}: QAListProps) {
  const [personaMap, setPersonaMap] = useState<Record<number, PersonaResponse>>({});
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [activeQuestionId, setActiveQuestionId] = useState<number | null>(null);

  const [savedSelections, setSavedSelections] = useState<Set<number>>(new Set()); // Saved set of selections
  const [draftSelections, setDraftSelections] = useState<Set<number>>(new Set()); // Draft set of selections
  const [selectionDirty, setSelectionDirty] = useState(false); // Whether there is mismatch between Saved and Draft selections
  const [activeTab, setActiveTabRaw] = useState(0);
  const [criteriaOpen, setCriteriaOpen] = useState(false);
  const setActiveTab = useCallback((tab: number) => {
    setActiveTabRaw(tab);
  }, []);
  const [fullyAnnotatedIds, setFullyAnnotatedIds] = useState<Set<number>>(new Set());

  const activeRubricId = useMemo(() => {
    if (activeTab === 0) return null;
    const rubric = rubrics[activeTab - 1];
    return rubric?.id ?? null;
  }, [activeTab, rubrics]);

  const activeRubricLabel = useMemo(() => {
    if (activeTab === 0) return "Accuracy";
    return rubrics[activeTab - 1]?.name ?? "Accuracy";
  }, [activeTab, rubrics]);

  const handleCompletenessChanged = useCallback(
    (answerId: number, isComplete: boolean) => {
      setFullyAnnotatedIds((prev) => {
        const had = prev.has(answerId);
        if (isComplete === had) return prev;
        const next = new Set(prev);
        if (isComplete) next.add(answerId); else next.delete(answerId);
        return next;
      });
    },
    []
  );

  // Load personas
  useEffect(() => {
    let cancelled = false;
    const loadPersonas = async () => {
      try {
        const personasRes = await personaApi.list(targetId);
        if (cancelled) return;

        // Build persona map
        const pMap: Record<number, PersonaResponse> = {};
        personasRes.data.forEach((persona: PersonaResponse) => {
          pMap[persona.id] = persona;
        });
        setPersonaMap(pMap);
      } catch (err) {
        if (!cancelled) {
          console.error("Failed to load personas:", err);
        }
      }
    };

    loadPersonas();

    return () => {
      cancelled = true;
    };
  }, [targetId]);

  useEffect(() => {
    setActiveQuestionId((current) => {
      if (approvedQuestions.length === 0) return null;
      if (current && approvedQuestions.some((question) => question.id === current)) {
        return current;
      }
      return approvedQuestions[0]?.id ?? null;
    });
  }, [approvedQuestions]);

  useEffect(() => {
    setActiveTab(0);
  }, [activeQuestionId]);

  // Get saved selections from qaMap
  useEffect(() => {
    const set = new Set<number>();
    Object.values(qaMap).forEach((entry) => {
      if (entry.answer?.is_selected_for_annotation) {
        set.add(entry.answer.id);
      }
    });
    setSavedSelections(set);
  }, [qaMap]);

  // When savedSelections are updated, update draftSelections too
  useEffect(() => {
    if (!selectionDirty) {
      setDraftSelections(new Set(savedSelections));
    }
  }, [savedSelections, selectionDirty]);

  // Extract just the question and answer from qaMap 
  const questionAnswerMap = useMemo(() => {
    const map: Record<number, Answer | null> = {};
    Object.entries(qaMap).forEach(([questionId, entry]) => {
      map[Number(questionId)] = entry.answer ?? null;
    });
    return map;
  }, [qaMap]);

  const answerIndex = useMemo(() => {
    const index = new Map<number, number>();
    Object.entries(qaMap).forEach(([questionId, entry]) => {
      if (entry.answer) {
        index.set(entry.answer.id, Number(questionId));
      }
    });
    return index;
  }, [qaMap]);

  const initialQuestionHandled = useRef(false);

  const jobByQuestion = useMemo(() => {
    const map: Record<number, QAJob | null> = {};
    qaJobs.forEach((job) => {
      map[job.question_id] = job;
    });
    return map;
  }, [qaJobs]);

  // Order questions
  const orderedQuestions = useMemo(() => {
    const withIndex = approvedQuestions.map((q, idx) => ({ question: q, order: idx }));

    return withIndex
      .sort((a, b) => {
        const aAnswer = questionAnswerMap[a.question.id];
        const bAnswer = questionAnswerMap[b.question.id];
        const aSelected = aAnswer ? aAnswer.is_selected_for_annotation : false;
        const bSelected = bAnswer ? bAnswer.is_selected_for_annotation : false;

        if (aSelected !== bSelected) {
          return aSelected ? -1 : 1;
        }
        return a.order - b.order;
      })
      .map((item) => item.question);
  }, [approvedQuestions, questionAnswerMap, savedSelections]);

  // Change displayedQuestions based on filterMode
  const displayedQuestions = useMemo(() => {
    if (filterMode === "selected") {
      return orderedQuestions.filter((question) => {
        const answer = questionAnswerMap[question.id];
        return answer ? savedSelections.has(answer.id) : false;
      });
    }
    return orderedQuestions;
  }, [filterMode, orderedQuestions, questionAnswerMap, savedSelections]);

  // Set initial active question from URL param once questions are loaded
  useEffect(() => {
    if (initialQuestionId && !initialQuestionHandled.current && displayedQuestions.length > 0) {
      if (displayedQuestions.some((q) => q.id === initialQuestionId)) {
        setActiveQuestionId(initialQuestionId);
        initialQuestionHandled.current = true;
      }
    }
  }, [initialQuestionId, displayedQuestions]);

  useEffect(() => {
    if (displayedQuestions.length === 0) {
      setActiveQuestionId(null);
      return;
    }

    // Don't override if we're still waiting to apply initialQuestionId
    if (initialQuestionId && !initialQuestionHandled.current) {
      return;
    }

    if (
      !activeQuestionId ||
      !displayedQuestions.some((question) => question.id === activeQuestionId)
    ) {
      setActiveQuestionId(displayedQuestions[0].id);
    }
  }, [displayedQuestions, activeQuestionId]);

  // Functions for annotation form navigation
  const currentIndex = displayedQuestions.findIndex(
    (question) => question.id === activeQuestionId
  );
  const prevDisabled = currentIndex <= 0;
  const nextDisabled =
    currentIndex === -1 || currentIndex >= displayedQuestions.length - 1;

  const handlePrev = () => {
    if (prevDisabled) return;
    setActiveQuestionId(displayedQuestions[currentIndex - 1].id);
  };

  const handleNext = () => {
    if (nextDisabled) return;
    setActiveQuestionId(displayedQuestions[currentIndex + 1].id);
  };

  // Functions for selection
  const handleToggleSelection = (answerId: number) => {
    setDraftSelections((prev) => {
      const next = new Set(prev);
      if (next.has(answerId)) {
        next.delete(answerId);
      } else {
        next.add(answerId);
      }
      return next;
    });
    setSelectionDirty(true);
  };

  const handleSaveSelection = async () => {
    if (!snapshotId) {
      return;
    }
    const toSelect = Array.from(draftSelections).filter(
      (id) => !savedSelections.has(id)
    );
    const toUnselect = Array.from(savedSelections).filter(
      (id) => !draftSelections.has(id)
    );
    const selections = [
      ...toSelect.map((answerId) => ({
        answer_id: answerId,
        is_selected: true,
      })),
      ...toUnselect.map((answerId) => ({
        answer_id: answerId,
        is_selected: false,
      })),
    ];

    // If no change in selections, do nothing.
    if (selections.length === 0) {
      setSelectionDirty(false);
      return;
    }

    if (!snapshotId) {
      return;
    }

    // Update selections
    try {
      await answerApi.bulkSelection(snapshotId, { selections }); // Update selections in DB

      setQaMap((prev) => {
        const next: QAMap = { ...prev };

        toSelect.forEach((answerId) => {
          const questionId = answerIndex.get(answerId);
          if (questionId === undefined) return;
          const entry = next[questionId];
          if (!entry?.answer) return;
          next[questionId] = {
            ...entry,
            answer: {
              ...entry.answer,
              is_selected_for_annotation: true,
            },
          };
        });

        toUnselect.forEach((answerId) => {
          const questionId = answerIndex.get(answerId);
          if (questionId === undefined) return;
          const entry = next[questionId];
          if (!entry?.answer) return;
          next[questionId] = {
            ...entry,
            answer: {
              ...entry.answer,
              is_selected_for_annotation: false,
            },
          };
        });

        return next;
      });

      setSelectionDirty(false);
    } catch (err) {
      console.error("Failed to save selection:", err);
    } 
  };

  const handleAnnotationSaved = () => {
    if (!activeAnswer) return;
    setQaMap((prev) => {
      const entry = prev[activeAnswer.question_id];
      if (!entry?.answer) return prev;
      return {
        ...prev,
        [activeAnswer.question_id]: {
          ...entry,
          answer: {
            ...entry.answer,
            has_annotation: true,
          },
        },
      };
    });
  };

  const activeQuestion = approvedQuestions.find((q) => q.id === activeQuestionId) || null;
  const activePersona = activeQuestion?.persona_id ? personaMap[activeQuestion.persona_id] ?? null : null;
  const activeAnswer = activeQuestion
    ? questionAnswerMap[activeQuestion.id] ?? null
    : null;
  const activeEntry = activeQuestion ? qaMap[activeQuestion.id] : undefined;
  const activeJob = activeQuestion ? jobByQuestion[activeQuestion.id] ?? null : null;

  const annotatedCount = useMemo(() => {
    return Object.values(qaMap).filter(
      (entry) => entry.answer && fullyAnnotatedIds.has(entry.answer.id)
    ).length;
  }, [qaMap, fullyAnnotatedIds]);

  // Check if all jobs are completed
  const allJobsCompleted = useMemo(() => {
    if (qaJobs.length === 0) return false;
    return qaJobs.every((job) => job.status === JobStatus.COMPLETED);
  }, [qaJobs]);


  const handleFilterChange = (
    _event: React.MouseEvent<HTMLElement>,
    newFilter: FilterMode | null
  ) => {
    if (newFilter) {
      setFilterMode(newFilter);
    }
  };

  if (!snapshotId) {
    return (
      <Paper variant="outlined" sx={{ p: 3, mt: 3 }}>
        <Typography variant="body1" color="text.secondary" align="center">
          Choose a snapshot to begin annotation.
        </Typography>
      </Paper>
    );
  }

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: { xs: "column", md: "row" },
        gap: 3,
        alignItems: "flex-start",
      }}
    >
      <Box
        sx={{
          width: { md: "25%" },
          display: "flex",
          flexDirection: "column",
          position: { md: "sticky" },
          top: { md: 24 },
          maxHeight: { md: "calc(100vh - 48px)" },
          minHeight: 0,
        }}
      >
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          sx={{ mt:1, mb: 1, flexShrink: 0 }}
        >
          <Typography variant="h5">Question List</Typography>
          <Tooltip title="Toggle between all answers or selected only">
            <ToggleButtonGroup
              size="small"
              exclusive
              value={filterMode}
              onChange={handleFilterChange}
              sx={{
                backgroundColor: "grey.100",
                borderRadius: 999,
                p: 0.25,
                "& .MuiToggleButtonGroup-grouped": {
                  border: "none",
                  borderRadius: 999,
                  textTransform: "none",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  px: 1.5,
                  py: 0.5,
                  color: "text.secondary",
                },
                "& .Mui-selected": {
                  backgroundColor: "common.white",
                  color: "text.primary",
                  boxShadow: (theme) => theme.shadows[1],
                },
                "& .MuiToggleButtonGroup-grouped:not(:first-of-type)": {
                  marginLeft: 0.5,
                },
              }}
            >
              <ToggleButton value="all">All</ToggleButton>
              <ToggleButton value="selected">Selected</ToggleButton>
            </ToggleButtonGroup>
          </Tooltip>
        </Stack>

        <Paper variant="outlined" sx={{ mt: 2, mb: 2, p: 1.5, flexShrink: 0 }}>
          <Stack spacing={1}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="caption" fontWeight={600}>
                Annotation Progress
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {annotatedCount} of {savedSelections.size} annotated
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={savedSelections.size > 0 ? (annotatedCount / savedSelections.size) * 100 : 0}
              sx={{ height: 6, borderRadius: 1 }}
            />
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="caption" color="text.secondary">
                {draftSelections.size} question{draftSelections.size === 1 ? "" : "s"} in annotation set
              </Typography>
              <Button
                variant="outlined"
                size="small"
                disabled={!selectionDirty}
                onClick={handleSaveSelection}
              >
                Save Selection
              </Button>
            </Stack>
          </Stack>
        </Paper>


        <Box sx={{ overflowY: "auto", flexGrow: 1 }}>
          {questionsLoading ? (
            <Box sx={{ py: 4, textAlign: "center" }}>
              <CircularProgress size={24} />
            </Box>
          ) : questionError ? (
            <Alert severity="error">{questionError}</Alert>
          ) : displayedQuestions.length === 0 ? (
            <Box sx={{ py: 4, textAlign: "center" }}>
              <Typography variant="body2" color="text.secondary">
                {filterMode === "selected"
                  ? "No answers selected for annotation."
                  : "No questions available for this target."}
              </Typography>
            </Box>
          ) : (
            <List disablePadding>
              {displayedQuestions.map((question) => {
                const answer = questionAnswerMap[question.id];
                return (
                  <QAItem
                    key={question.id}
                    question={question}
                    answer={answer}
                    job={jobByQuestion[question.id] ?? null}
                    isActive={question.id === activeQuestionId}
                    isChecked={answer ? draftSelections.has(answer.id) : false}
                    onToggleSelection={() =>
                      answer ? handleToggleSelection(answer.id) : undefined
                    }
                    onSelect={() => setActiveQuestionId(question.id)}
                  />
                );
              })}
            </List>
          )}
        </Box>
      </Box>

      <Paper
        variant="outlined"
        sx={{
          width: { md: "75%" },
          bgcolor: "rgb(0, 0, 0, 0.01)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Shared header: Q nav + question text */}
        <Stack
          direction="row"
          spacing={1.5}
          alignItems="center"
          sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: "divider" }}
        >
          <Typography variant="body2" fontWeight={700} sx={{ whiteSpace: "nowrap" }}>
            {activeQuestion ? `Q${activeQuestion.id}` : "—"}
          </Typography>
          <Typography
            variant="body2"
            color="text.disabled"
            sx={{
              flex: 1,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {activeQuestion?.text ?? ""}
          </Typography>
          <Stack direction="row" spacing={0.5}>
            <Button
              startIcon={<ArrowBackIcon fontSize="small" />}
              onClick={handlePrev}
              disabled={prevDisabled}
              variant="outlined"
              size="small"
              sx={{ "& .MuiButton-startIcon": { margin: 0, padding: "3px 0" }, minWidth: 0 }}
            />
            <Button
              endIcon={<ArrowForwardIcon fontSize="small" />}
              onClick={handleNext}
              disabled={nextDisabled}
              variant="outlined"
              size="small"
              sx={{ "& .MuiButton-endIcon": { margin: 0, padding: "3px 0" }, minWidth: 0 }}
            />
          </Stack>
        </Stack>

        {/* Rubric tabs — shared across both panels */}
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center" sx={{ px: 2, py: 1, borderBottom: 1, borderColor: criteriaOpen ? "transparent" : "divider", transition: "border-color 0.3s" }}>
          <Chip
            label="Accuracy"
            onClick={() => setActiveTab(0)}
            variant={activeTab === 0 ? "filled" : "outlined"}
            sx={{
              fontWeight: 600, fontSize: "0.8rem", height: 32,
              ...(activeTab === 0
                ? { bgcolor: groupColors.fixed.border, color: "#fff", borderColor: "transparent", "&:hover": { bgcolor: groupColors.fixed.border, opacity: 0.9 } }
                : { borderColor: "divider", "&:hover": { bgcolor: groupColors.fixed.bg } }),
            }}
          />
          {rubrics.map((r, i) => {
            const accent = r.template_key ? groupColors.preset.border : groupColors.custom.border;
            return (
              <Chip
                key={r.id}
                label={r.name}
                onClick={() => setActiveTab(i + 1)}
                variant={activeTab === i + 1 ? "filled" : "outlined"}
                sx={{
                  fontWeight: 600, fontSize: "0.8rem", height: 32,
                  ...(activeTab === i + 1
                    ? { bgcolor: accent, color: "#fff", borderColor: "transparent", "&:hover": { bgcolor: accent, opacity: 0.9 } }
                    : { borderColor: "divider", "&:hover": { bgcolor: r.template_key ? groupColors.preset.bg : groupColors.custom.bg } }),
                }}
              />
            );
          })}
          <Box sx={{ flex: 1 }} />
          <Button
            variant="text"
            size="small"
            color="primary"
            endIcon={criteriaOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            onClick={() => setCriteriaOpen((prev) => !prev)}
            sx={{ textTransform: "none", fontSize: "0.75rem", whiteSpace: "nowrap" }}
          >
            {criteriaOpen ? "less" : "more"}
          </Button>
        </Stack>
        <Collapse in={criteriaOpen}>
          <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: "divider" }}>
            <Box sx={{ pl: 1, borderLeft: "2px solid", borderColor: "divider" }}>
              {activeTab === 0 ? (
                <>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                    Is the response factually accurate based on the knowledge base?
                  </Typography>
                  <Stack spacing={0.25}>
                    <Typography variant="caption" color="text.secondary">
                      <Box component="span" fontWeight={700}>Accurate</Box> — reflects the source information
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      <Box component="span" fontWeight={700}>Inaccurate</Box> — contains factual errors or omissions
                    </Typography>
                  </Stack>
                </>
              ) : rubrics[activeTab - 1] ? (
                <>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                    {rubrics[activeTab - 1].criteria || <em>No criteria defined.</em>}
                  </Typography>
                  {rubrics[activeTab - 1].options.length > 0 && (
                    <Stack spacing={0.25}>
                      {rubrics[activeTab - 1].options.map((opt) => (
                        <Typography key={opt.option} variant="caption" color="text.secondary">
                          <Box component="span" fontWeight={700}>{opt.option}</Box> — {opt.description}
                        </Typography>
                      ))}
                    </Stack>
                  )}
                </>
              ) : null}
            </Box>
          </Box>
        </Collapse>

        {/* Two-column body: Judge View | Your Annotations */}
        <Box
          sx={{
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            flex: 1,
            minHeight: 0,
          }}
        >
          {/* Left: Judge View */}
          <Box sx={{ flex: 1, minWidth: 0, borderRight: { md: 1 }, borderColor: { md: "divider" } }}>
            <QAContent
              targetId={targetId}
              question={activeQuestion}
              persona={activePersona}
              qaEntry={activeEntry}
              job={activeJob}
              rubrics={rubrics}
              activeTab={activeTab}
              onActiveTabChange={setActiveTab}
            />
          </Box>

          {/* Right: Your Annotations */}
          <Box
            sx={{
              width: { md: "32%" },
              flexShrink: 0,
              position: { md: "sticky" },
              top: { md: 0 },
              alignSelf: "flex-start",
              px: 2,
              py: 1.5,
            }}
          >
            <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mb: 1.5 }}>
              <Typography variant="overline" color="text.secondary" sx={{ letterSpacing: 1 }}>
                Your Annotations
              </Typography>
              <Tooltip title="Your annotations are used to measure how well the AI judge agrees with your judgement." placement="left" arrow>
                <Typography variant="caption" color="text.disabled" sx={{ cursor: "help", lineHeight: 1 }}>ⓘ</Typography>
              </Tooltip>
            </Stack>
            <AnnotationForm
              answer={activeAnswer}
              onAnnotationSaved={handleAnnotationSaved}
              rubrics={rubrics}
              activeRubricId={activeRubricId}
              onCompletenessChanged={handleCompletenessChanged}
            />
          </Box>
        </Box>
      </Paper>
    </Box>
  );
}
