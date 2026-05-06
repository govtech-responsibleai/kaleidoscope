"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useParams } from "next/navigation";
import {
  IconChevronDown,
  IconCircleCheck,
  IconCircleCheckFilled,
  IconDeviceFloppy,
  IconHelpCircle,
  IconPlus,
  IconTrash,
} from "@tabler/icons-react";
import {
  Box,
  Typography,
  TextField,
  Divider,
  Button,
  IconButton,
  CircularProgress,
  Tooltip,
  Chip,
  Stack,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  Dialog,
  DialogActions,
  DialogTitle,
  DialogContent,
  Card,
  CardActionArea,
  CardContent,
} from "@mui/material";
import {
  IconChecklist,
  IconHeartHandshake,
  IconCut,
} from "@tabler/icons-react";
import { metricsApi, qaJobApi, snapshotApi, targetRubricApi } from "@/lib/api";
import { groupColors } from "@/lib/theme";
import { JobStatus, PremadeRubricTemplate, TargetRubricResponse, RubricOption } from "@/lib/types";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import { actionIconProps, compactActionIconProps, statusIconProps } from "@/lib/styles";
import { TESTIDS } from "@/tests/ui-integration/fixtures/testids";

export default function RubricsPage() {
  const params = useParams();
  const targetId = Number(params.id);

  const [rubrics, setRubrics] = useState<TargetRubricResponse[]>([]);
  const [savedRubrics, setSavedRubrics] = useState<Record<number, TargetRubricResponse>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Set<number>>(new Set());
  const [saveErrors, setSaveErrors] = useState<Record<number, string>>({});
  const [rubricToDelete, setRubricToDelete] = useState<TargetRubricResponse | null>(null);
  const [pendingSaveRubric, setPendingSaveRubric] = useState<TargetRubricResponse | null>(null);
  const [premadeDialogOpen, setPremadeDialogOpen] = useState(false);
  const [premadeTemplates, setPremadeTemplates] = useState<PremadeRubricTemplate[]>([]);
  const [premadeLoading, setPremadeLoading] = useState(false);
  const [addingPremade, setAddingPremade] = useState<string | null>(null);
  const [rubricUsageById, setRubricUsageById] = useState<Record<number, boolean>>({});
  const [rubricRunningById, setRubricRunningById] = useState<Record<number, boolean>>({});

  useEffect(() => {
    let cancelled = false;

    const loadPageData = async () => {
      setLoading(true);
      try {
        const [rubricsRes, snapshotsRes, metricsRes] = await Promise.all([
          targetRubricApi.list(targetId),
          snapshotApi.list(targetId),
          metricsApi.getSnapshotMetrics(targetId),
        ]);
        if (cancelled) return;

        setRubrics(rubricsRes.data);
        const saved: Record<number, TargetRubricResponse> = {};
        rubricsRes.data.forEach((r) => { saved[r.id] = r; });
        setSavedRubrics(saved);

        const usageById: Record<number, boolean> = {};
        const runningById: Record<number, boolean> = {};

        (metricsRes.data.rubrics ?? []).flatMap((rubricGroup) => rubricGroup.snapshots).forEach((metric) => {
          if (metric.rubric_id == null) return;
          const hasMetricData = (
            metric.total_answers > 0
            || metric.pending_count > 0
            || metric.edited_count > 0
            || metric.accurate_count > 0
            || metric.inaccurate_count > 0
            || metric.aligned_judges.length > 0
            || metric.judge_alignment_range !== null
          );
          if (hasMetricData) {
            usageById[metric.rubric_id] = true;
          }
        });

        const qaJobResponses = await Promise.all(
          snapshotsRes.data.map((snapshot) => qaJobApi.list(snapshot.id).catch(() => ({ data: [] })))
        );
        if (cancelled) return;

        qaJobResponses.forEach((response) => {
          response.data.forEach((job) => {
            const rubricIds = (job.rubric_specs ?? []).map((spec) => spec.rubric_id);
            rubricIds.forEach((rubricId) => {
              usageById[rubricId] = true;
              if (job.status === JobStatus.RUNNING) {
                runningById[rubricId] = true;
              }
            });
          });
        });

        setRubricUsageById(usageById);
        setRubricRunningById(runningById);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadPageData();
    return () => {
      cancelled = true;
    };
  }, [targetId]);

  const isFixed = (rubric: TargetRubricResponse) => rubric.group === "fixed";
  const isPremade = (rubric: TargetRubricResponse) => rubric.group === "preset";
  const isDraft = (rubricId: number) => rubricId < 0;

  const isDirty = (rubric: TargetRubricResponse) => {
    if (isDraft(rubric.id)) return true;
    const saved = savedRubrics[rubric.id];
    if (!saved) return true;
    return rubric.name !== saved.name
      || rubric.criteria !== saved.criteria
      || rubric.best_option !== saved.best_option
      || JSON.stringify(rubric.options) !== JSON.stringify(saved.options);
  };

  const addRubric = () => {
    const tempId = -Date.now();
    const placeholder: TargetRubricResponse = {
      id: tempId, target_id: targetId, name: "", criteria: "",
      options: [], best_option: null, position: 0,
      judge_prompt: null, group: "custom", scoring_mode: "response_level",
      created_at: "", updated_at: "",
    };
    setRubrics((prev) => [...prev, placeholder]);
  };

  const openPremadeDialog = async () => {
    setPremadeDialogOpen(true);
    setPremadeLoading(true);
    try {
      const res = await targetRubricApi.listPremade(targetId);
      setPremadeTemplates(res.data);
    } catch {
      setPremadeTemplates([]);
    } finally {
      setPremadeLoading(false);
    }
  };

  const addPremadeRubric = async (template: PremadeRubricTemplate) => {
    setAddingPremade(template.name);
    try {
      const res = await targetRubricApi.create(targetId, {
        name: template.name,
        criteria: template.criteria,
        options: template.options,
        best_option: template.best_option,
        group: "preset",
      });
      setRubrics((prev) => [...prev, res.data]);
      setSavedRubrics((prev) => ({ ...prev, [res.data.id]: res.data }));
      setPremadeTemplates((prev) => prev.filter((item) => item.name !== template.name));
      setPremadeDialogOpen(false);
    } catch {
      // Keep existing page-level error handling simple for now.
    } finally {
      setAddingPremade(null);
    }
  };

  const updateField = (rubricId: number, patch: Partial<TargetRubricResponse>) => {
    setRubrics((prev) => prev.map((r) => (r.id === rubricId ? { ...r, ...patch } : r)));
  };

  const updateOptionField = (
    rubricId: number,
    index: number,
    field: keyof RubricOption,
    value: string
  ) => {
    setRubrics((prev) => prev.map((r) => {
      if (r.id !== rubricId) return r;
      const updated = r.options.map((o, i) => (i === index ? { ...o, [field]: value } : o));
      return { ...r, options: updated };
    }));
  };

  const addOption = (rubricId: number) => {
    setRubrics((prev) => prev.map((r) =>
      r.id === rubricId ? { ...r, options: [...r.options, { option: "", description: "" }] } : r
    ));
  };

  const removeOption = (rubricId: number, index: number) => {
    setRubrics((prev) => prev.map((r) => {
      if (r.id !== rubricId) return r;
      const removed = r.options[index];
      const updated = r.options.filter((_, i) => i !== index);
      return {
        ...r,
        options: updated,
        best_option: r.best_option === removed.option ? null : r.best_option,
      };
    }));
  };

  const setBestOption = (rubricId: number, optionName: string) => {
    updateField(rubricId, { best_option: optionName });
  };

  const saveRubric = async (rubric: TargetRubricResponse) => {
    setSaving((prev) => new Set(prev).add(rubric.id));
    setSaveErrors((prev) => { const next = { ...prev }; delete next[rubric.id]; return next; });
    try {
      if (isDraft(rubric.id)) {
        const res = await targetRubricApi.create(targetId, {
          name: rubric.name,
          criteria: rubric.criteria,
          options: rubric.options,
          best_option: rubric.best_option,
        });
        setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? res.data : r)));
        setSavedRubrics((prev) => ({ ...prev, [res.data.id]: res.data }));
      } else {
        const res = await targetRubricApi.update(targetId, rubric.id, {
          name: rubric.name,
          criteria: rubric.criteria,
          options: rubric.options,
          best_option: rubric.best_option,
        });
        setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? res.data : r)));
        setSavedRubrics((prev) => ({ ...prev, [res.data.id]: res.data }));
      }
    } catch {
      setSaveErrors((prev) => ({ ...prev, [rubric.id]: "Failed to save rubric. Please try again." }));
    } finally {
      setSaving((prev) => { const next = new Set(prev); next.delete(rubric.id); return next; });
    }
  };

  const rubricHasBoundData = (rubric: TargetRubricResponse) =>
    !isDraft(rubric.id) && Boolean(rubricUsageById[rubric.id]);

  const rubricHasRunningJobs = (rubric: TargetRubricResponse) =>
    !isDraft(rubric.id) && Boolean(rubricRunningById[rubric.id]);

  const semanticEditTouchesPersistedData = (rubric: TargetRubricResponse) => {
    if (isDraft(rubric.id)) {
      return false;
    }
    const saved = savedRubrics[rubric.id];
    if (!saved) {
      return false;
    }
    return (
      rubric.name !== saved.name
      || rubric.criteria !== saved.criteria
      || rubric.best_option !== saved.best_option
      || JSON.stringify(rubric.options) !== JSON.stringify(saved.options)
    );
  };

  const handleSave = (rubric: TargetRubricResponse) => {
    if (rubricHasRunningJobs(rubric)) {
      setSaveErrors((prev) => ({
        ...prev,
        [rubric.id]: "Wait for related evaluations to finish before editing this rubric.",
      }));
      return;
    }
    if (rubricHasBoundData(rubric) && semanticEditTouchesPersistedData(rubric)) {
      setPendingSaveRubric(rubric);
      return;
    }
    void saveRubric(rubric);
  };

  const getRubricErrors = (rubric: TargetRubricResponse): string[] => {
    const errors: string[] = [];
    if (!rubric.name.trim()) errors.push("Enter a rubric name");
    if (!rubric.criteria.trim()) errors.push("Enter evaluation criteria");
    const nonEmptyOptions = rubric.options.filter((o) => o.option.trim() !== "");
    if (nonEmptyOptions.length < 2) errors.push("Add at least 2 non-empty options");
    const optionNames = nonEmptyOptions.map((o) => o.option.trim().toLowerCase());
    if (new Set(optionNames).size !== optionNames.length) errors.push("Remove duplicate option names");
    if (!rubric.best_option || !rubric.options.some((o) => o.option === rubric.best_option))
      errors.push("Select an ideal outcome");
    return errors;
  };

  const handleConfirmDelete = async () => {
    if (!rubricToDelete) return;
    if (rubricHasRunningJobs(rubricToDelete)) {
      setSaveErrors((prev) => ({
        ...prev,
        [rubricToDelete.id]: "Wait for related evaluations to finish before deleting this rubric.",
      }));
      throw new Error("rubric-running");
    }
    try {
      if (!isDraft(rubricToDelete.id)) {
        await targetRubricApi.delete(targetId, rubricToDelete.id);
      }
      setRubrics((prev) => prev.filter((r) => r.id !== rubricToDelete.id));
    } catch {
      setSaveErrors((prev) => ({ ...prev, [rubricToDelete.id]: "Failed to delete rubric. Please try again." }));
    }
  };

  const fixedRubrics = rubrics.filter((r) => isFixed(r));
  const premadeRubrics = rubrics.filter((r) => isPremade(r));
  const customRubrics = rubrics.filter((r) => r.group === "custom");
  const totalRubricCount = fixedRubrics.length + premadeRubrics.length + customRubrics.length;
  const premadeIconMap: Record<string, ReactNode> = {
    empathy: <IconHeartHandshake size={36} stroke={1.8} color="currentColor" />,
    verbosity: <IconCut size={36} stroke={1.8} color="currentColor" />,
  };
  const defaultPremadeIcon = <IconChecklist size={36} stroke={1.8} color="currentColor" />;

  const renderOptionsReadonly = (options: RubricOption[], bestOption: string | null) => (
    <>
      <Box sx={{ display: "flex", gap: 1.5, mb: 1, alignItems: "center" }}>
        <Box sx={{ width: 100, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Tooltip title="The positive option is the ideal outcome. Scores measure how often judges choose this option." placement="top" arrow>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, cursor: "help" }}>
              <Typography variant="caption" fontWeight={600} color="text.secondary">Ideal outcome</Typography>
              <IconHelpCircle size={14} stroke={2} color="currentColor" />
            </Box>
          </Tooltip>
        </Box>
        <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ width: 140, flexShrink: 0 }}>Label</Typography>
        <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ flex: 1 }}>Description</Typography>
      </Box>
      {options.map(({ option, description }) => (
        <Box key={option} sx={{ display: "flex", gap: 1.5, mb: 1.5, alignItems: "center" }}>
          <Box sx={{ width: 100, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            {option === bestOption
              ? <IconCircleCheckFilled size={24} stroke={1.8} color="#2e7d32" />
              : <IconCircleCheck size={24} stroke={1.8} color="currentColor" />
            }
          </Box>
          <TextField value={option} disabled size="small" sx={{ width: 140, flexShrink: 0 }} />
          <TextField value={description} disabled size="small" fullWidth multiline />
        </Box>
      ))}
    </>
  );

  const groupSubtitles: Record<string, string> = {
    Fixed:  "Built-in rubrics applied to every evaluation. Cannot be removed.",
    Preset: "Curated rubric templates. Add from the library and customise.",
    Custom: "Rubrics you define. Full control over criteria and options.",
  };

  const renderGroupHeader = (title: string, count: number, onAdd: (() => void) | null, accent?: string, addTestId?: string) => (
    <Box>
      <Stack direction="row" alignItems="center" gap={1.5}>
        <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: accent ?? "primary.main", flexShrink: 0 }} />
        <Typography
          variant="subtitle2"
          fontWeight={700}
          sx={{ textTransform: "uppercase", letterSpacing: 0.6 }}
        >
          {title}
        </Typography>
        <Chip label={count} size="small" sx={{ height: 18, fontSize: "0.65rem", "& .MuiChip-label": { px: 0.75 }, ...(accent ? { bgcolor: accent, color: "#fff" } : {}) }} />
        <Box sx={{ flex: 1 }} />
        {onAdd && (
          <Tooltip title={`Add ${title.toLowerCase()} rubric`} arrow>
            <IconButton
              size="small"
              data-testid={addTestId}
              onClick={onAdd}
              sx={{
                border: "1px solid",
                borderColor: accent ?? "primary.main",
                color: accent ?? "primary.main",
                "&:hover": { bgcolor: accent ?? "primary.main", color: "#fff" },
              }}
            >
              <IconPlus {...compactActionIconProps} />
            </IconButton>
          </Tooltip>
        )}
      </Stack>
      {groupSubtitles[title] && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5, ml: 2.5 }}>
          {groupSubtitles[title]}
        </Typography>
      )}
    </Box>
  );

  const renderEmptyState = (message: string) => (
    <Typography variant="body2" color="text.secondary" sx={{ py: 2, px: 1, fontStyle: "italic" }}>
      {message}
    </Typography>
  );

  const summarySx = {
    minHeight: 48,
    flexDirection: "row-reverse",
    "& .MuiAccordionSummary-expandIconWrapper": { mr: 1 },
    "& .MuiAccordionSummary-content": { alignItems: "center" },
  };

  const groupTint: Record<keyof typeof groupColors, string> = {
    fixed:  "rgba(92, 107, 192, 0.06)",
    preset: "rgba(38, 166, 154, 0.06)",
    custom: "rgba(255, 167, 38, 0.06)",
  };

  const groupSectionSx = (group: keyof typeof groupColors) => ({
    bgcolor: groupTint[group],
    borderRadius: 2,
    p: 2,
    mb: 3,
  });

  const destructiveRubricDescription =
    "This deletes all data related to this rubric, including annotations, overrides, judge outputs, and derived scoring state. Create a new rubric instead if you need to preserve the existing data.";

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>Rubric Library</Typography>
      <Alert severity="info" variant="outlined" sx={{ mb: 3 }}>
        <strong>{totalRubricCount} rubric{totalRubricCount !== 1 ? "s" : ""} defined.</strong>{" "}
        Rubrics defined here are used by annotators and LLM judges to score responses.
        Your score = % of times judges pick the ideal outcome.
      </Alert>

      {/* FIXED group */}
      <Box sx={groupSectionSx("fixed")}>
        <Box sx={{ mb: 2 }}>{renderGroupHeader("Fixed", fixedRubrics.length, null, groupColors.fixed.border)}</Box>
        {fixedRubrics.map((rubric) => (
          <Accordion key={rubric.id} variant="outlined" disableGutters>
            <AccordionSummary expandIcon={<IconChevronDown {...actionIconProps} />} sx={summarySx}>
              <Typography fontWeight={600} sx={{ flex: 1 }}>{rubric.name}</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0 }}>
              <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                Criteria
              </Typography>
              <TextField value={rubric.criteria} fullWidth disabled multiline size="small" sx={{ mb: 2 }} />
              <Divider sx={{ mb: 2 }} />
              {renderOptionsReadonly(rubric.options, rubric.best_option)}
            </AccordionDetails>
          </Accordion>
        ))}
      </Box>

      {/* PRESET group */}
      <Box sx={groupSectionSx("preset")}>
        <Box sx={{ mb: 2 }}>{renderGroupHeader("Preset", premadeRubrics.length, openPremadeDialog, groupColors.preset.border, TESTIDS.RUBRIC_PRESET_ADD)}</Box>
        {premadeRubrics.length === 0 ? (
          renderEmptyState("No preset rubrics added yet. Click + to browse templates.")
        ) : (
          premadeRubrics.map((rubric) => (
            <Accordion key={rubric.id} variant="outlined" disableGutters sx={{ mb: 1 }}>
              <AccordionSummary expandIcon={<IconChevronDown {...actionIconProps} />} sx={summarySx}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 2, flex: 1 }}>
                  <Typography fontWeight={600} sx={{ flex: 1 }}>{rubric.name}</Typography>
                  {rubricHasRunningJobs(rubric) && (
                    <Chip label="Jobs running" size="small" color="error" variant="outlined" />
                  )}
                </Box>
                <Tooltip
                  title={rubricHasRunningJobs(rubric) ? "Wait for related evaluations to finish before deleting this rubric." : "Remove preset rubric"}
                  arrow
                >
                  <span>
                    <IconButton
                      component="div"
                      size="small"
                      disabled={rubricHasRunningJobs(rubric)}
                      onClick={(e) => { e.stopPropagation(); setRubricToDelete(rubric); }}
                    >
                      <IconTrash {...compactActionIconProps} />
                    </IconButton>
                  </span>
                </Tooltip>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 0 }}>
                <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                  Criteria
                </Typography>
                <TextField value={rubric.criteria} fullWidth disabled multiline size="small" sx={{ mb: 2 }} />
                <Divider sx={{ mb: 2 }} />
                {renderOptionsReadonly(rubric.options, rubric.best_option)}
              </AccordionDetails>
            </Accordion>
          ))
        )}
      </Box>

      {/* CUSTOM group */}
      <Box sx={groupSectionSx("custom")}>
        <Box sx={{ mb: 2 }}>{renderGroupHeader("Custom", customRubrics.length, addRubric, groupColors.custom.border, TESTIDS.RUBRIC_CUSTOM_ADD)}</Box>
        {loading ? (
          <CircularProgress size={24} />
        ) : customRubrics.length === 0 ? (
          renderEmptyState("No custom rubrics yet. Click + to add one.")
        ) : (
          customRubrics.map((rubric) => {
            const draft = isDraft(rubric.id);
            const dirty = isDirty(rubric);
            const errors = getRubricErrors(rubric);
            const isSaving = saving.has(rubric.id);
            const saveError = saveErrors[rubric.id];
            const hasRunningJobs = rubricHasRunningJobs(rubric);
            return (
              <Accordion
                key={rubric.id}
                variant="outlined"
                disableGutters
                defaultExpanded={draft}
                sx={{ mb: 1, ...(draft && { borderStyle: "dashed" }) }}
              >
                <AccordionSummary expandIcon={<IconChevronDown {...actionIconProps} />} sx={summarySx}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1, flex: 1 }}>
                    <TextField
                      value={rubric.name}
                      placeholder="Untitled rubric"
                      variant="standard"
                      size="small"
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateField(rubric.id, { name: e.target.value })}
                      slotProps={{
                        input: { style: { fontWeight: 600, fontSize: "1rem" } },
                      }}
                      sx={{
                        flexGrow: 1,
                        "& .MuiInput-underline:before": { borderBottom: "none" },
                        "& .MuiInput-underline:hover:before": { borderBottom: "1px solid rgba(0,0,0,0.3) !important" },
                      }}
                    />
                    {dirty && !draft && <Chip label="Unsaved" size="small" color="warning" variant="outlined" />}
                    {hasRunningJobs && <Chip label="Jobs running" size="small" color="error" variant="outlined" />}
                  </Box>
                  <Tooltip
                    title={hasRunningJobs ? "Wait for related evaluations to finish before deleting this rubric." : "Delete rubric"}
                    arrow
                  >
                    <span>
                      <IconButton
                        component="div"
                        size="small"
                        disabled={hasRunningJobs}
                        onClick={(e) => { e.stopPropagation(); setRubricToDelete(rubric); }}
                      >
                        <IconTrash {...compactActionIconProps} />
                      </IconButton>
                    </span>
                  </Tooltip>
                </AccordionSummary>
                <AccordionDetails sx={{ pt: 0 }}>
                  <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                    Criteria
                  </Typography>
                  <TextField
                    value={rubric.criteria}
                    placeholder="Describe your evaluation criteria"
                    fullWidth
                    multiline
                    minRows={3}
                    size="small"
                    onChange={(e) => updateField(rubric.id, { criteria: e.target.value })}
                    sx={{ mb: 2 }}
                  />

                  <Divider sx={{ mb: 2 }} />

                  <Box sx={{ display: "flex", gap: 1.5, mb: 1, alignItems: "center" }}>
                    <Box sx={{ width: 100, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Tooltip title="The positive option is the ideal outcome. Scores measure how often judges choose this option." placement="top" arrow>
                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, cursor: "help" }}>
                          <Typography variant="caption" fontWeight={600} color="text.secondary">Ideal outcome</Typography>
                          <IconHelpCircle size={14} stroke={2} color="currentColor" />
                        </Box>
                      </Tooltip>
                    </Box>
                    <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ width: 140, flexShrink: 0 }}>Label</Typography>
                    <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ flex: 1 }}>Description</Typography>
                    <Box sx={{ width: 32, flexShrink: 0 }} />
                  </Box>

                  {rubric.options.map((opt, i) => {
                    const isPositive = rubric.best_option === opt.option && opt.option !== "";
                    return (
                      <Box key={i} sx={{ display: "flex", gap: 1.5, mb: 1.5, alignItems: "center" }}>
                        <Box
                          sx={{ width: 100, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}
                          onClick={() => { if (opt.option) setBestOption(rubric.id, opt.option); }}
                        >
                          {isPositive
                            ? <IconCircleCheckFilled size={24} stroke={1.8} color="#2e7d32" />
                            : <IconCircleCheck size={24} stroke={1.8} color="currentColor" />
                          }
                        </Box>
                        <TextField
                          placeholder="Option"
                          value={opt.option}
                          size="small"
                          sx={{ width: 140, flexShrink: 0 }}
                          onChange={(e) => updateOptionField(rubric.id, i, "option", e.target.value)}
                        />
                        <TextField
                          placeholder="Description"
                          value={opt.description}
                          size="small"
                          fullWidth
                          multiline
                          onChange={(e) => updateOptionField(rubric.id, i, "description", e.target.value)}
                        />
                        <IconButton size="small" onClick={() => removeOption(rubric.id, i)}>
                          <IconTrash {...compactActionIconProps} />
                        </IconButton>
                      </Box>
                    );
                  })}

                  <Button startIcon={<IconPlus {...actionIconProps} />} size="small" sx={{ mt: 0.5 }} onClick={() => addOption(rubric.id)}>
                    Add Option
                  </Button>

                  {(dirty || saveError) && (
                    <Box sx={{ mt: 2, display: "flex", alignItems: "center", gap: 1.5 }}>
                      <Box sx={{ flex: 1, display: "flex", alignItems: "center", gap: 1 }}>
                        {dirty && errors.length > 0 && (
                          <Typography variant="caption" color="error">
                            {errors.join(", ")}
                          </Typography>
                        )}
                        {saveError && (
                          <Typography variant="caption" color="error">
                            {saveError}
                          </Typography>
                        )}
                      </Box>
                      {dirty && (
                        <Tooltip title={hasRunningJobs ? "Wait for related evaluations to finish before editing this rubric." : (errors.length > 0 ? errors.join(", ") : "")}>
                          <span>
                            <Button
                              variant="contained"
                              size="small"
                              startIcon={isSaving ? <CircularProgress size={16} color="inherit" /> : <IconDeviceFloppy {...statusIconProps} />}
                              disabled={errors.length > 0 || isSaving || hasRunningJobs}
                              onClick={() => handleSave(rubric)}
                            >
                              {isSaving ? "Generating judge prompt..." : "Save"}
                            </Button>
                          </span>
                        </Tooltip>
                      )}
                    </Box>
                  )}
                </AccordionDetails>
              </Accordion>
            );
          })
        )}
      </Box>

      <ConfirmDeleteDialog
        open={rubricToDelete !== null}
        onClose={() => setRubricToDelete(null)}
        onConfirm={handleConfirmDelete}
        title={rubricToDelete?.group === "preset" ? "Remove Preset Rubric" : "Delete Rubric"}
        itemName={rubricToDelete?.name || "this rubric"}
        destructive={Boolean(rubricToDelete && rubricHasBoundData(rubricToDelete))}
        description={rubricToDelete && rubricHasBoundData(rubricToDelete) ? destructiveRubricDescription : undefined}
      />

      <Dialog open={pendingSaveRubric !== null} onClose={() => setPendingSaveRubric(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Save Rubric and Reset Related Data</DialogTitle>
        <DialogContent>
          <Alert severity="error" sx={{ mb: 2 }}>
            Saving this rubric will delete all data related to it.
          </Alert>
          <Typography variant="body1">
            Save changes to{" "}
            <strong>{pendingSaveRubric?.name || "this rubric"}</strong>?
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            {destructiveRubricDescription}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingSaveRubric(null)}>
            Cancel
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={!pendingSaveRubric || saving.has(pendingSaveRubric.id)}
            startIcon={
              pendingSaveRubric && saving.has(pendingSaveRubric.id)
                ? <CircularProgress size={16} color="inherit" />
                : <IconDeviceFloppy {...actionIconProps} />
            }
            onClick={async () => {
              if (!pendingSaveRubric) return;
              await saveRubric(pendingSaveRubric);
              setPendingSaveRubric(null);
            }}
          >
            {pendingSaveRubric && saving.has(pendingSaveRubric.id) ? "Saving..." : "Save"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog data-testid={TESTIDS.PRESET_RUBRIC_DIALOG} open={premadeDialogOpen} onClose={() => setPremadeDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Preset Rubric</DialogTitle>
        <DialogContent>
          {premadeLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress size={24} />
            </Box>
          ) : premadeTemplates.length === 0 ? (
            <Typography color="text.secondary" sx={{ py: 2 }}>
              All preset rubrics have already been added to this target.
            </Typography>
          ) : (
            <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", pt: 1, justifyContent: "center" }}>
              {premadeTemplates.map((template) => {
                const templateKey = template.name.trim().toLowerCase();
                return (
                  <Card
                    key={template.name}
                    data-testid={TESTIDS.PRESET_RUBRIC_CARD(templateKey)}
                    variant="outlined"
                    sx={{ flex: "1 1 180px", maxWidth: 220, position: "relative" }}
                  >
                    <CardActionArea
                      onClick={() => addPremadeRubric(template)}
                      disabled={addingPremade !== null}
                      sx={{ p: 2, textAlign: "center" }}
                    >
                      {addingPremade === template.name && (
                        <Box sx={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)" }}>
                          <CircularProgress size={24} />
                        </Box>
                      )}
                      <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
                        <Box sx={{ mb: 1, color: "text.secondary", opacity: addingPremade === template.name ? 0.3 : 1 }}>
                          {premadeIconMap[templateKey] ?? defaultPremadeIcon}
                        </Box>
                        <Typography
                          fontWeight={600}
                          sx={{ mb: 0.5, opacity: addingPremade === template.name ? 0.3 : 1 }}
                        >
                          {template.name}
                        </Typography>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{
                            display: "-webkit-box",
                            WebkitLineClamp: 3,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                            opacity: addingPremade === template.name ? 0.3 : 1,
                          }}
                        >
                          {template.criteria}
                        </Typography>
                      </CardContent>
                    </CardActionArea>
                  </Card>
                );
              })}
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}
