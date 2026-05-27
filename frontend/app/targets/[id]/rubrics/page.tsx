"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  IconCheck,
  IconCircleCheck,
  IconCircleCheckFilled,
  IconCode,
  IconCopy,
  IconCut,
  IconDeviceFloppy,
  IconHeartHandshake,
  IconHelpCircle,
  IconPencil,
  IconPlus,
  IconTrash,
  IconX,
} from "@tabler/icons-react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { metricsApi, qaJobApi, snapshotApi, targetRubricApi } from "@/lib/api";
import { JobStatus, PremadeRubricTemplate, RubricOption, TargetRubricResponse } from "@/lib/types";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";
import PromptEditorDynamic from "@/components/shared/PromptEditorDynamic";
import { actionIconProps, compactActionIconProps, statusIconProps } from "@/lib/styles";
import { TESTIDS } from "@/tests/ui-integration/fixtures/testids";

type TablerIcon = typeof IconCircleCheck;

const PRESET_ICONS: Record<string, TablerIcon> = {
  empathy: IconHeartHandshake,
  verbosity: IconCut,
};

const getPresetIcon = (name: string) =>
  PRESET_ICONS[name.trim().toLowerCase()] ?? IconCircleCheck;

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
  const [pendingPromptSaveRubric, setPendingPromptSaveRubric] = useState<TargetRubricResponse | null>(null);
  const [premadeTemplates, setPremadeTemplates] = useState<PremadeRubricTemplate[]>([]);
  const [addingPremade, setAddingPremade] = useState<string | null>(null);
  const [rubricUsageById, setRubricUsageById] = useState<Record<number, boolean>>({});
  const [rubricRunningById, setRubricRunningById] = useState<Record<number, boolean>>({});
  const [promptViewRubric, setPromptViewRubric] = useState<TargetRubricResponse | null>(null);
  const [editingRubricId, setEditingRubricId] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const [editedPrompt, setEditedPrompt] = useState("");
  const [promptSaving, setPromptSaving] = useState(false);
  const [promptError, setPromptError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadPageData = async () => {
      setLoading(true);
      try {
        const [rubricsRes, snapshotsRes, metricsRes, premadeRes] = await Promise.all([
          targetRubricApi.list(targetId),
          snapshotApi.list(targetId),
          metricsApi.getSnapshotMetrics(targetId),
          targetRubricApi.listPremade(targetId).catch(() => ({ data: [] as PremadeRubricTemplate[] })),
        ]);
        if (cancelled) return;

        setRubrics(rubricsRes.data);
        const saved: Record<number, TargetRubricResponse> = {};
        rubricsRes.data.forEach((r) => { saved[r.id] = r; });
        setSavedRubrics(saved);
        setPremadeTemplates(premadeRes.data);

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

  useEffect(() => {
    setEditedPrompt(promptViewRubric?.judge_prompt ?? "");
    setPromptError(null);
  }, [promptViewRubric?.id, promptViewRubric?.judge_prompt]);

  const isPromptDirty = editedPrompt !== (promptViewRubric?.judge_prompt ?? "");

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
    setEditingRubricId(tempId);
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
    } catch {
      // Keep the sidebar intact for retry.
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
        best_option: r.best_option === removed?.option ? null : r.best_option,
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
        setEditingRubricId(null);
      } else {
        const res = await targetRubricApi.update(targetId, rubric.id, {
          name: rubric.name,
          criteria: rubric.criteria,
          options: rubric.options,
          best_option: rubric.best_option,
        });
        setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? res.data : r)));
        setSavedRubrics((prev) => ({ ...prev, [res.data.id]: res.data }));
        setEditingRubricId(null);
      }
    } catch {
      setSaveErrors((prev) => ({ ...prev, [rubric.id]: "Failed to save rubric. Please try again." }));
    } finally {
      setSaving((prev) => { const next = new Set(prev); next.delete(rubric.id); return next; });
    }
  };

  const savePrompt = async () => {
    if (!promptViewRubric) return;
    setPromptSaving(true);
    setPromptError(null);
    try {
      const res = await targetRubricApi.update(targetId, promptViewRubric.id, { judge_prompt: editedPrompt });
      setRubrics((prev) => prev.map((r) => r.id === res.data.id ? res.data : r));
      setSavedRubrics((prev) => ({ ...prev, [res.data.id]: res.data }));
      setPromptViewRubric(null);
      setCopied(false);
    } catch {
      setPromptError("Failed to save judge prompt.");
    } finally {
      setPromptSaving(false);
    }
  };

  const rubricHasBoundData = (rubric: TargetRubricResponse) =>
    !isDraft(rubric.id) && Boolean(rubricUsageById[rubric.id]);

  const rubricHasRunningJobs = (rubric: TargetRubricResponse) =>
    !isDraft(rubric.id) && Boolean(rubricRunningById[rubric.id]);

  const semanticEditTouchesPersistedData = (rubric: TargetRubricResponse) => {
    if (isDraft(rubric.id)) return false;
    const saved = savedRubrics[rubric.id];
    if (!saved) return false;
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

  const handlePromptSave = () => {
    if (!promptViewRubric) return;
    if (rubricHasRunningJobs(promptViewRubric)) {
      setPromptError("Wait for related evaluations to finish before editing this rubric.");
      return;
    }
    if (rubricHasBoundData(promptViewRubric)) {
      setPendingPromptSaveRubric(promptViewRubric);
      return;
    }
    void savePrompt();
  };

  const handleCancelEdit = (rubricId: number) => {
    if (isDraft(rubricId)) {
      setRubrics((prev) => prev.filter((r) => r.id !== rubricId));
    } else {
      const saved = savedRubrics[rubricId];
      if (saved) {
        setRubrics((prev) => prev.map((r) => (r.id === rubricId ? saved : r)));
      }
    }
    setEditingRubricId(null);
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
      if (editingRubricId === rubricToDelete.id) setEditingRubricId(null);
    } catch {
      setSaveErrors((prev) => ({ ...prev, [rubricToDelete.id]: "Failed to delete rubric. Please try again." }));
    }
  };

  const totalRubricCount = rubrics.length;
  const destructiveRubricDescription =
    "This deletes all data related to this rubric, including annotations, overrides, judge outputs, and derived scoring state. Create a new rubric instead if you need to preserve the existing data.";
  const pendingDestructiveSaveRubric = pendingSaveRubric ?? pendingPromptSaveRubric;
  const destructiveSaveInFlight = pendingSaveRubric
    ? saving.has(pendingSaveRubric.id)
    : promptSaving;

  const iconBoxSx = {
    alignItems: "center",
    bgcolor: "action.hover",
    borderRadius: 1.5,
    color: "text.secondary",
    display: "flex",
    flexShrink: 0,
    height: 32,
    justifyContent: "center",
    width: 32,
  } as const;

  const rubricRowSx = {
    alignItems: "center",
    bgcolor: "background.paper",
    border: "1px solid",
    borderColor: "divider",
    borderRadius: "10px",
    display: "flex",
    gap: 1.5,
    mb: 1,
    px: 1.5,
    py: 1.25,
    transition: "border-color 0.15s, box-shadow 0.15s, background-color 0.15s",
    "&:hover": {
      borderColor: "grey.300",
      bgcolor: "rgba(29, 39, 102, 0.015)",
    },
  };

  const presetSidebarRowSx = {
    alignItems: "center",
    display: "flex",
    gap: 1.5,
    px: 0.5,
    py: 0.75,
  } as const;

  const renderPresetRow = (rubric: TargetRubricResponse) => {
    const hasRunning = rubricHasRunningJobs(rubric);
    const PresetIcon = getPresetIcon(rubric.name);
    return (
      <Box
        key={rubric.id}
        sx={{
          ...rubricRowSx,
        }}
      >
        <Box sx={iconBoxSx}>
          <PresetIcon size={18} stroke={1.8} />
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
            <Typography variant="body2" fontWeight={600}>{rubric.name}</Typography>
            <Chip label="Preset" size="small" variant="outlined" sx={{ height: 20, fontSize: 10, borderColor: "grey.300", color: "text.secondary" }} />
            {hasRunning && <Typography variant="caption" color="text.disabled" fontStyle="italic">running</Typography>}
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {rubric.criteria}
          </Typography>
        </Box>
        <Tooltip title={hasRunning ? "Wait for related evaluations to finish before removing this rubric." : "Remove preset"}>
          <span>
            <IconButton
              size="small"
              disabled={hasRunning}
              onClick={() => setRubricToDelete(rubric)}
              sx={{ color: "text.secondary", opacity: 0.45, "&:hover": { opacity: 1, color: "error.main" } }}
            >
              <IconTrash {...compactActionIconProps} />
            </IconButton>
          </span>
        </Tooltip>
      </Box>
    );
  };

  const renderCustomCollapsedRow = (rubric: TargetRubricResponse) => {
    const dirty = isDirty(rubric);
    const draft = isDraft(rubric.id);
    const hasRunning = rubricHasRunningJobs(rubric);
    const isSaving = saving.has(rubric.id);
    return (
      <Box
        key={rubric.id}
        sx={{
          ...rubricRowSx,
          borderColor: draft ? "primary.light" : "divider",
          borderStyle: draft ? "dashed" : "solid",
          boxShadow: draft ? "0 0 0 3px rgba(72,97,182,0.08)" : "none",
        }}
      >
        <Box sx={iconBoxSx}>
          {isSaving ? <CircularProgress size={16} /> : <IconPencil size={18} stroke={1.8} />}
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {dirty && !draft && (
              <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: "warning.main", flexShrink: 0 }} aria-label="Unsaved changes" />
            )}
            <Typography variant="body2" fontWeight={600} color={rubric.name ? "text.primary" : "text.disabled"} noWrap>
              {rubric.name || "Untitled rubric"}
            </Typography>
            {isSaving && <Typography variant="caption" color="text.disabled" fontStyle="italic">Saving…</Typography>}
            {hasRunning && !isSaving && <Typography variant="caption" color="text.disabled" fontStyle="italic">running</Typography>}
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {rubric.criteria || "No criteria set"}
          </Typography>
        </Box>
        <Tooltip title="Edit">
          <IconButton
            size="small"
            onClick={() => setEditingRubricId(rubric.id)}
            sx={{ color: "text.secondary", opacity: 0.45, "&:hover": { opacity: 1 } }}
          >
            <IconPencil {...compactActionIconProps} />
          </IconButton>
        </Tooltip>
        <Tooltip title={hasRunning ? "Wait for related evaluations to finish before deleting this rubric." : "Delete"}>
          <span>
            <IconButton
              size="small"
              disabled={hasRunning}
              onClick={() => setRubricToDelete(rubric)}
              sx={{ color: "text.secondary", opacity: 0.45, "&:hover": { opacity: 1, color: "error.main" } }}
            >
              <IconTrash {...compactActionIconProps} />
            </IconButton>
          </span>
        </Tooltip>
      </Box>
    );
  };

  const renderCustomEditingRow = (rubric: TargetRubricResponse) => {
    const draft = isDraft(rubric.id);
    const dirty = isDirty(rubric);
    const errors = getRubricErrors(rubric);
    const isSaving = saving.has(rubric.id);
    const saveError = saveErrors[rubric.id];
    const hasRunning = rubricHasRunningJobs(rubric);
    return (
      <Box
        key={rubric.id}
        sx={{
          bgcolor: "background.paper",
          border: "1px solid",
          borderColor: "primary.light",
          borderRadius: "10px",
          boxShadow: "0 0 0 3px rgba(72,97,182,0.08)",
          mb: 1,
          overflow: "hidden",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, px: 1.5, py: 1.25, borderBottom: "1px solid", borderColor: "divider" }}>
          <Box sx={iconBoxSx}>
            {isSaving ? <CircularProgress size={16} /> : <IconPencil size={18} stroke={1.8} />}
          </Box>
          <TextField
            value={rubric.name}
            placeholder="Untitled rubric"
            variant="standard"
            size="small"
            onChange={(e) => updateField(rubric.id, { name: e.target.value })}
            slotProps={{ input: { style: { fontWeight: 600, fontSize: "0.95rem" } } }}
            sx={{
              flex: 1,
              "& .MuiInput-underline:before": { borderBottom: "none" },
              "& .MuiInput-underline:hover:before": { borderBottom: "1px solid rgba(0,0,0,0.3) !important" },
            }}
          />
          <Button
            size="small"
            variant="text"
            startIcon={<IconX size={16} stroke={2} />}
            onClick={() => handleCancelEdit(rubric.id)}
            disabled={isSaving}
            sx={{ flexShrink: 0, color: "text.secondary" }}
          >
            Cancel
          </Button>
          <Tooltip title={
            hasRunning
              ? "Wait for related evaluations to finish before editing this rubric."
              : errors.length > 0 ? errors.join(", ") : ""
          }>
            <span>
              <Button
                variant="contained"
                size="small"
                startIcon={isSaving ? <CircularProgress size={14} color="inherit" /> : <IconDeviceFloppy {...statusIconProps} />}
                disabled={errors.length > 0 || isSaving || hasRunning || !dirty}
                onClick={() => handleSave(rubric)}
                sx={{ flexShrink: 0 }}
              >
                {isSaving ? "Saving…" : "Save"}
              </Button>
            </span>
          </Tooltip>
        </Box>

        <Box sx={{ px: 2, py: 1.5 }}>
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

          <Box sx={{ display: { xs: "none", sm: "grid" }, gridTemplateColumns: "110px 140px minmax(0, 1fr) 32px", gap: 1.5, mb: 1, alignItems: "center" }}>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Tooltip title="The positive option is the ideal outcome. Scores measure how often judges choose this option." placement="top" arrow>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, cursor: "help" }}>
                  <Typography variant="caption" fontWeight={600} color="text.secondary">Ideal outcome</Typography>
                  <IconHelpCircle size={14} stroke={2} color="currentColor" />
                </Box>
              </Tooltip>
            </Box>
            <Typography variant="caption" fontWeight={600} color="text.secondary">Label</Typography>
            <Typography variant="caption" fontWeight={600} color="text.secondary">Description</Typography>
            <Box />
          </Box>

          {rubric.options.map((opt, i) => {
            const isPositive = rubric.best_option === opt.option && opt.option !== "";
            return (
              <Box
                key={i}
                sx={{
                  alignItems: { xs: "stretch", sm: "center" },
                  display: "grid",
                  gap: 1.5,
                  gridTemplateColumns: { xs: "1fr 32px", sm: "110px 140px minmax(0, 1fr) 32px" },
                  mb: 1.5,
                }}
              >
                <Box
                  sx={{
                    alignItems: "center",
                    cursor: opt.option ? "pointer" : "default",
                    display: "flex",
                    gap: 1,
                    gridColumn: { xs: "1 / 3", sm: "auto" },
                    justifyContent: { xs: "flex-start", sm: "center" },
                  }}
                  onClick={() => { if (opt.option) setBestOption(rubric.id, opt.option); }}
                >
                  {isPositive
                    ? <IconCircleCheckFilled size={24} stroke={1.8} color="var(--mui-palette-success-main)" />
                    : <IconCircleCheck size={24} stroke={1.8} color="currentColor" />
                  }
                  <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "block", sm: "none" } }}>
                    Ideal outcome
                  </Typography>
                </Box>
                <TextField
                  placeholder="Option"
                  value={opt.option}
                  size="small"
                  sx={{ minWidth: 0 }}
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
                <IconButton size="small" onClick={() => removeOption(rubric.id, i)} sx={{ alignSelf: { xs: "center", sm: "center" } }}>
                  <IconTrash {...compactActionIconProps} />
                </IconButton>
              </Box>
            );
          })}

          <Button startIcon={<IconPlus {...actionIconProps} />} size="small" sx={{ mt: 0.5 }} onClick={() => addOption(rubric.id)}>
            Add Option
          </Button>

          <Divider sx={{ my: 2 }} />

          <Box sx={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <Typography component="label" sx={{ fontSize: "0.9rem", fontWeight: 600, mb: "2px" }}>
              Prompt Template
            </Typography>
            <Box sx={{ position: "relative", borderRadius: "5px", border: "1px solid", borderColor: "divider", backgroundColor: "#fafbff", overflow: "hidden" }}>
              <Box sx={{ px: 1.5, py: 1.5, fontFamily: "var(--font-jetbrains-mono), monospace", fontSize: "12px", lineHeight: 1.6, color: "text.secondary", whiteSpace: "pre-wrap", maxHeight: "4.8em", overflow: "hidden" }}>
                {rubric.judge_prompt
                  ? rubric.judge_prompt.split("\n").slice(0, 3).join("\n")
                  : "No prompt template configured"}
              </Box>
              <Box sx={{ position: "absolute", bottom: 24, left: 0, right: 0, height: "24px", background: "linear-gradient(transparent, #fafbff)", pointerEvents: "none" }} />
              <Box sx={{ display: "flex", justifyContent: "flex-end", px: 1, py: 0.5, borderTop: "1px solid", borderColor: "divider", backgroundColor: "#f5f6fc" }}>
                <Button
                  size="small"
                  startIcon={<IconCode size={14} />}
                  disabled={draft || !rubric.judge_prompt}
                  onClick={() => setPromptViewRubric(rubric)}
                  sx={{ textTransform: "none", fontSize: "0.75rem", fontWeight: 500, color: "text.secondary", "&:hover": { color: "primary.main" } }}
                >
                  Customize prompt
                </Button>
              </Box>
            </Box>
          </Box>

          {(saveError || (dirty && errors.length > 0)) && (
            <Box sx={{ mt: 1.5 }}>
              {saveError && <Typography variant="caption" color="error" sx={{ display: "block" }}>{saveError}</Typography>}
              {dirty && errors.length > 0 && <Typography variant="caption" color="error" sx={{ display: "block" }}>{errors.join(", ")}</Typography>}
            </Box>
          )}
        </Box>
      </Box>
    );
  };

  const renderCriterionRow = (rubric: TargetRubricResponse) => {
    if (isPremade(rubric)) return renderPresetRow(rubric);
    if (editingRubricId === rubric.id) return renderCustomEditingRow(rubric);
    return renderCustomCollapsedRow(rubric);
  };

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight={700}>
          Rubric Library
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontStyle: "italic" }}>
          {totalRubricCount} rubric{totalRubricCount !== 1 ? "s" : ""} defined. Rubrics are used by annotators and LLM judges to score responses.
        </Typography>
      </Box>

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress size={24} />
        </Box>
      ) : (
        <Box
          sx={{
            alignItems: "flex-start",
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            gap: 4,
          }}
        >
          <Box sx={{ flex: { md: "0 0 58%" }, minWidth: 0, width: { xs: "100%", md: "auto" } }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
              Active Criteria
            </Typography>
            {rubrics.length === 0 ? (
              <Box sx={{ border: "1px dashed", borderColor: "grey.300", borderRadius: "10px", p: 4, textAlign: "center" }}>
                <Typography variant="body2" color="text.secondary">
                  No rubrics yet. Add a preset from the right or create a custom criterion.
                </Typography>
              </Box>
            ) : (
              <Box sx={{ "& > *:last-child": { mb: 0 } }}>
                {rubrics.map((rubric) => renderCriterionRow(rubric))}
              </Box>
            )}
          </Box>

          <Divider
            orientation="vertical"
            flexItem
            sx={{ display: { xs: "none", md: "block" } }}
          />

          <Box sx={{ display: "flex", flex: 1, flexDirection: "column", gap: 3, minWidth: 0, width: { xs: "100%", md: "auto" } }}>
            <Box>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>
                Presets
              </Typography>
              <Box data-testid={TESTIDS.PRESET_RUBRIC_DIALOG}>
                {rubrics.filter(isPremade).map((rubric) => {
                  const PresetIcon = getPresetIcon(rubric.name);
                  return (
                    <Box key={`added-${rubric.id}`} sx={{ ...presetSidebarRowSx, opacity: 0.5 }}>
                      <Box sx={iconBoxSx}>
                        <PresetIcon size={18} stroke={1.8} />
                      </Box>
                      <Typography variant="body2" fontWeight={500} sx={{ flex: 1, minWidth: 0 }} noWrap>{rubric.name}</Typography>
                      <Chip label="Added" size="small" sx={{ height: 18, fontSize: 10, bgcolor: "grey.100", color: "text.secondary" }} />
                    </Box>
                  );
                })}

                {/* Empty states */}
                {premadeTemplates.length === 0 && rubrics.filter(isPremade).length === 0 && (
                  <Typography variant="caption" color="text.secondary" fontStyle="italic">No preset rubrics available.</Typography>
                )}
                {premadeTemplates.length === 0 && rubrics.filter(isPremade).length > 0 && (
                  <Typography variant="caption" color="text.secondary" fontStyle="italic" sx={{ display: "block", mt: 0.5 }}>
                    All preset rubrics have already been added to this target.
                  </Typography>
                )}

                {premadeTemplates.map((template) => {
                  const slug = template.name.trim().toLowerCase();
                  const isAdding = addingPremade === template.name;
                  const PresetIcon = getPresetIcon(template.name);
                  return (
                    <Box
                      key={template.name}
                      data-testid={TESTIDS.PRESET_RUBRIC_CARD(slug)}
                      onClick={() => { if (!addingPremade) void addPremadeRubric(template); }}
                      sx={{
                        ...presetSidebarRowSx,
                        cursor: addingPremade ? "default" : "pointer",
                        borderRadius: 1,
                        "&:hover": addingPremade ? {} : { bgcolor: "rgba(29, 39, 102, 0.04)" },
                        opacity: addingPremade && !isAdding ? 0.5 : 1,
                      }}
                    >
                      <Box sx={iconBoxSx}>
                        {isAdding ? <CircularProgress size={16} /> : <PresetIcon size={18} stroke={1.8} />}
                      </Box>
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="body2" fontWeight={600} noWrap>{template.name}</Typography>
                        <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block" }}>
                          {template.criteria.length > 60 ? `${template.criteria.substring(0, 60)}…` : template.criteria}
                        </Typography>
                      </Box>
                      <IconButton size="small" color="primary" disabled={!!addingPremade} sx={{ flexShrink: 0 }}>
                        <IconPlus size={16} stroke={2} />
                      </IconButton>
                    </Box>
                  );
                })}
              </Box>
            </Box>

            <Box>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>
                Custom
              </Typography>
              <Button
                data-testid={TESTIDS.RUBRIC_CUSTOM_ADD}
                variant="outlined"
                startIcon={<IconPlus {...actionIconProps} />}
                fullWidth
                onClick={addRubric}
                sx={{ justifyContent: "flex-start" }}
              >
                Create custom criterion
              </Button>
            </Box>
          </Box>
        </Box>
      )}

      <ConfirmDeleteDialog
        open={rubricToDelete !== null}
        onClose={() => setRubricToDelete(null)}
        onConfirm={handleConfirmDelete}
        title={rubricToDelete?.group === "preset" ? "Remove Preset Rubric" : "Delete Rubric"}
        itemName={rubricToDelete?.name || "this rubric"}
        destructive={Boolean(rubricToDelete && rubricHasBoundData(rubricToDelete))}
        description={rubricToDelete && rubricHasBoundData(rubricToDelete) ? destructiveRubricDescription : undefined}
      />

      <Dialog
        open={pendingDestructiveSaveRubric !== null}
        onClose={() => {
          setPendingSaveRubric(null);
          setPendingPromptSaveRubric(null);
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Save Rubric and Reset Related Data</DialogTitle>
        <DialogContent>
          <Alert severity="error" sx={{ mb: 2 }}>
            Saving this rubric will delete all data related to it.
          </Alert>
          <Typography variant="body1">
            Save changes to <strong>{pendingDestructiveSaveRubric?.name || "this rubric"}</strong>?
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            {destructiveRubricDescription}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setPendingSaveRubric(null);
              setPendingPromptSaveRubric(null);
            }}
          >
            Cancel
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={!pendingDestructiveSaveRubric || destructiveSaveInFlight}
            startIcon={
              destructiveSaveInFlight
                ? <CircularProgress size={16} color="inherit" />
                : <IconDeviceFloppy {...actionIconProps} />
            }
            onClick={async () => {
              if (pendingSaveRubric) {
                await saveRubric(pendingSaveRubric);
                setPendingSaveRubric(null);
                return;
              }
              if (pendingPromptSaveRubric) {
                await savePrompt();
                setPendingPromptSaveRubric(null);
              }
            }}
          >
            {destructiveSaveInFlight ? "Saving..." : "Save"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={!!promptViewRubric}
        onClose={() => {
          if (isPromptDirty && !window.confirm("You have unsaved changes. Discard them?")) return;
          setPromptViewRubric(null);
          setCopied(false);
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ display: "flex", alignItems: "center" }}>
          <Box sx={{ flex: 1 }}>{promptViewRubric?.name}: Judge Prompt</Box>
          <Tooltip
            title={promptViewRubric?.scoring_mode === "claim_based"
              ? "Claim-level: evaluates individual claims extracted from the answer separately."
              : "Response-level: evaluates the entire answer holistically in a single pass."}
            arrow
          >
            <Chip
              label={promptViewRubric?.scoring_mode === "claim_based" ? "Claim-level" : "Response-level"}
              size="small"
              variant="outlined"
              icon={<IconHelpCircle size={14} />}
              sx={{
                px: 1,
                ...(promptViewRubric?.scoring_mode === "claim_based"
                  ? { borderColor: "warning.main", color: "warning.dark" }
                  : { borderColor: "primary.main", color: "primary.main" }),
              }}
            />
          </Tooltip>
        </DialogTitle>
        <DialogContent>
          {promptError && <Alert severity="error" sx={{ mb: 2 }}>{promptError}</Alert>}
          <Box sx={{ height: 400, "& .cm-editor": { pointerEvents: "auto" } }}>
            <PromptEditorDynamic
              value={editedPrompt}
              onChange={(val) => setEditedPrompt(val)}
              disabled={promptSaving}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button
            startIcon={copied ? <IconCheck {...statusIconProps} /> : <IconCopy {...statusIconProps} />}
            color={copied ? "success" : "primary"}
            disabled={promptSaving}
            onClick={async () => {
              await navigator.clipboard.writeText(editedPrompt);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}
          >
            {copied ? "Copied!" : "Copy prompt"}
          </Button>
          <Box sx={{ flex: 1 }} />
          <Button
            disabled={promptSaving}
            onClick={() => {
              if (isPromptDirty && !window.confirm("You have unsaved changes. Discard them?")) return;
              setPromptViewRubric(null);
              setCopied(false);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={!isPromptDirty || promptSaving}
            onClick={handlePromptSave}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
