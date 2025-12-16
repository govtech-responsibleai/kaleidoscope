"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  List,
  Paper,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import { Answer, QAJob, QuestionResponse, QAMap } from "@/lib/types";
import { answerApi, questionApi } from "@/lib/api";
import QAItem from "./QAItem";
import QAContent from "./QAContent";
import AnnotationForm from "./AnnotationForm";

type FilterMode = "all" | "selected";

interface QAListProps {
  targetId: number;
  snapshotId: number | null;
  qaJobs: QAJob[];
  qaMap: QAMap;
  setQaMap: React.Dispatch<React.SetStateAction<QAMap>>;
  onQuestionIdsChange?: (ids: number[]) => void;
}

export default function QAList({
  targetId,
  snapshotId,
  qaJobs,
  qaMap,
  setQaMap,
  onQuestionIdsChange,
}: QAListProps) {
  const [approvedQuestions, setApprovedQuestions] = useState<QuestionResponse[]>([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [questionError, setQuestionError] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [activeQuestionId, setActiveQuestionId] = useState<number | null>(null);

  const [savedSelections, setSavedSelections] = useState<Set<number>>(new Set()); // Saved set of selections
  const [draftSelections, setDraftSelections] = useState<Set<number>>(new Set()); // Draft set of selections
  const [selectionDirty, setSelectionDirty] = useState(false); // Whether there is mismatch between Saved and Draft selections

  // Load questions
  useEffect(() => {
    let cancelled = false;
    const loadQuestions = async () => {
      setQuestionsLoading(true);
      try {
        const response = await questionApi.listByTarget(targetId);
        if (cancelled) return;
        const approvedQuestions = response.data.filter((question) => question.status === "approved");
        setApprovedQuestions(approvedQuestions);
        onQuestionIdsChange?.(approvedQuestions.map((q) => q.id));
        setActiveQuestionId(approvedQuestions[0]?.id ?? null);
      } catch (err) {
        if (!cancelled) {
          console.error("Failed to load questions:", err);
          setQuestionError("Failed to load questions.");
        }
      } finally {
        if (!cancelled) {
          setQuestionsLoading(false);
        }
      }
    };

    loadQuestions();

    return () => {
      cancelled = true;
    };
  }, [targetId, onQuestionIdsChange]);

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

  const jobByQuestionId = useMemo(() => {
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

  useEffect(() => {
    if (displayedQuestions.length === 0) {
      setActiveQuestionId(null);
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

    // Update selections
    try {
      await answerApi.bulkSelection({ selections }); // Update selections in DB

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
  const activeAnswer = activeQuestion
    ? questionAnswerMap[activeQuestion.id] ?? null
    : null;
  const activeEntry = activeQuestion ? qaMap[activeQuestion.id] : undefined;
  const activeJob = activeQuestion ? jobByQuestionId[activeQuestion.id] ?? null : null;

  const annotatedCount = useMemo(() => {
    return Object.values(qaMap).filter((entry) => entry.answer?.has_annotation).length;
  }, [qaMap]);


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
        alignItems: "stretch",
      }}
    >
      <Paper
        variant="outlined"
        sx={{
          px: 3,
          py: 2,
          flexBasis: { md: "30%" },
          display: "flex",
          flexDirection: "column",
        }}
      >
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          sx={{ mt:1, mb: 1 }}
        >
          <Typography variant="h6">Questions & Responses</Typography>
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

        <Stack direction="row" alignItems="center" justifyContent={"space-between"} spacing={1} sx={{ mt: 2, mb: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Annotated: {annotatedCount} / {savedSelections.size}
          </Typography>

          <Divider flexItem orientation="vertical" sx={{ mx: 1 }} />
          
          <Typography variant="caption" color="text.secondary">
            Selected: {draftSelections.size}
          </Typography>

          <Divider flexItem orientation="vertical" sx={{ mx: 1 }} />
          
          <Button
            variant="outlined"
            size="small"
            disabled={!selectionDirty}
            onClick={handleSaveSelection}
          >
            Save Selection
          </Button>
        </Stack>


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
                    job={jobByQuestionId[question.id] ?? null}
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
      </Paper>

      <Box
        sx={{
          flexBasis: { md: "70%" },
          flexGrow: 1,
          minWidth: 0,
        }}
      >
        <Stack spacing={3}>
          <AnnotationForm
            answer={activeAnswer}
            onPrev={handlePrev}
            onNext={handleNext}
            prevDisabled={prevDisabled}
            nextDisabled={nextDisabled}
            onAnnotationSaved={handleAnnotationSaved}
          />
          <QAContent
            question={activeQuestion}
            qaEntry={activeEntry}
            job={activeJob}
          />
        </Stack>
      </Box>
    </Box>
  );
}
