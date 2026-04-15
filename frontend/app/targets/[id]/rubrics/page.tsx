"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Box,
  Typography,
  TextField,
  Divider,
  Button,
  IconButton,
  CircularProgress,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  Card,
  CardActionArea,
  CardContent,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
  Add as AddIcon,
  DeleteOutline as DeleteOutlineIcon,
  CheckCircle as CheckCircleIcon,
  CheckCircleOutline as CheckCircleOutlineIcon,
  HelpOutline as HelpOutlineIcon,
  Save as SaveIcon,
  FavoriteBorder as FavoriteBorderIcon,
  ContentCut as ContentCutIcon,
  ChecklistRtl as ChecklistRtlIcon,
} from "@mui/icons-material";
import { targetRubricApi } from "@/lib/api";
import { groupColors } from "@/lib/theme";
import {
  TargetRubricResponse,
  RubricOption,
  PremadeRubricTemplate,
} from "@/lib/types";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";

const accuracyOptions = [
  { option: "Accurate", description: "All claims are supported by the provided context." },
  { option: "Inaccurate", description: "One or more claims are not supported or hallucinated." },
];

const ACCURACY_CRITERIA =
  "Are the claims in the response supported by the provided context, or do they contain hallucinations?";

export default function RubricsPage() {
  const params = useParams();
  const targetId = Number(params.id);

  const [rubrics, setRubrics] = useState<TargetRubricResponse[]>([]);
  const [savedRubrics, setSavedRubrics] = useState<Record<number, TargetRubricResponse>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Set<number>>(new Set());
  const [saveErrors, setSaveErrors] = useState<Record<number, string>>({});
  const [rubricToDelete, setRubricToDelete] = useState<TargetRubricResponse | null>(null);

  const [premadeDialogOpen, setPremadeDialogOpen] = useState(false);
  const [premadeTemplates, setPremadeTemplates] = useState<PremadeRubricTemplate[]>([]);
  const [premadeLoading, setPremadeLoading] = useState(false);
  const [addingPremade, setAddingPremade] = useState<string | null>(null);

  useEffect(() => {
    targetRubricApi.list(targetId).then((res) => {
      setRubrics(res.data);
      const saved: Record<number, TargetRubricResponse> = {};
      res.data.forEach((r) => { saved[r.id] = r; });
      setSavedRubrics(saved);
      setLoading(false);
    });
  }, [targetId]);

  const isPremade = (rubric: TargetRubricResponse) => !!rubric.template_key;
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
      options: [], best_option: null, position: 0, category: "default",
      judge_prompt: null, template_key: null,
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
    setAddingPremade(template.key);
    try {
      const res = await targetRubricApi.create(targetId, {
        name: template.name,
        criteria: template.criteria,
        options: template.options,
        best_option: template.best_option,
        template_key: template.key,
      });
      setRubrics((prev) => [...prev, res.data]);
      setSavedRubrics((prev) => ({ ...prev, [res.data.id]: res.data }));
      setPremadeTemplates((prev) => prev.filter((t) => t.key !== template.key));
    } catch {
      // dialog will close
    } finally {
      setAddingPremade(null);
      setPremadeDialogOpen(false);
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

  const handleSave = async (rubric: TargetRubricResponse) => {
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
    try {
      if (!isDraft(rubricToDelete.id)) {
        await targetRubricApi.delete(targetId, rubricToDelete.id);
      }
      setRubrics((prev) => prev.filter((r) => r.id !== rubricToDelete.id));
    } catch {
      setSaveErrors((prev) => ({ ...prev, [rubricToDelete.id]: "Failed to delete rubric. Please try again." }));
    }
  };

  const premadeRubrics = rubrics.filter((r) => isPremade(r));
  const customRubrics = rubrics.filter((r) => !isPremade(r));
  const totalRubricCount = 1 + premadeRubrics.length + customRubrics.length;

  const premadeIconMap: Record<string, React.ReactElement> = {
    empathy: <FavoriteBorderIcon sx={{ fontSize: 36, color: "text.secondary" }} />,
    verbosity: <ContentCutIcon sx={{ fontSize: 36, color: "text.secondary" }} />,
  };
  const defaultPremadeIcon = <ChecklistRtlIcon sx={{ fontSize: 36, color: "text.secondary" }} />;

  const renderOptionsReadonly = (options: RubricOption[], bestOption: string | null) => (
    <>
      <Box sx={{ display: "flex", gap: 1.5, mb: 1, alignItems: "center" }}>
        <Box sx={{ width: 100, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Tooltip title="The positive option is the ideal outcome. Scores measure how often judges choose this option." placement="top" arrow>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, cursor: "help" }}>
              <Typography variant="caption" fontWeight={600} color="text.secondary">Ideal outcome</Typography>
              <HelpOutlineIcon sx={{ fontSize: 14, color: "text.disabled" }} />
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
              ? <CheckCircleIcon sx={{ fontSize: 24, color: "success.main" }} />
              : <CheckCircleOutlineIcon sx={{ fontSize: 24, color: "text.disabled" }} />
            }
          </Box>
          <TextField value={option} disabled size="small" sx={{ width: 140, flexShrink: 0 }} />
          <TextField value={description} disabled size="small" fullWidth multiline />
        </Box>
      ))}
    </>
  );

  const renderGroupHeader = (title: string, count: number, onAdd: (() => void) | null, accent?: string) => (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
      <Typography
        variant="subtitle2"
        fontWeight={700}
        sx={{ textTransform: "uppercase", letterSpacing: 0.6 }}
      >
        {title}
      </Typography>
      <Chip label={count} size="small" sx={accent ? { bgcolor: accent, color: "#fff" } : undefined} />
      <Box sx={{ flex: 1 }} />
      {onAdd && (
        <Tooltip title={`Add ${title.toLowerCase()} rubric`} arrow>
          <IconButton
            size="small"
            onClick={onAdd}
            sx={{
              border: "1px solid",
              borderColor: accent ?? "primary.main",
              color: accent ?? "primary.main",
              "&:hover": { bgcolor: accent ?? "primary.main", color: "#fff" },
            }}
          >
            <AddIcon fontSize="small" />
          </IconButton>
        </Tooltip>
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

  const getGroupSx = (group: keyof typeof groupColors) => ({
    bgcolor: groupColors[group].bg,
    borderLeft: "4px solid",
    borderColor: groupColors[group].border,
    borderRadius: 2,
    p: 2,
    mb: 3,
  });

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>Rubric Library</Typography>
      <Alert severity="info" variant="outlined" sx={{ mb: 3 }}>
        <strong>{totalRubricCount} rubric{totalRubricCount !== 1 ? "s" : ""} defined.</strong>{" "}
        Rubrics defined here are used by annotators and LLM judges to score responses.
        Your score = % of times judges pick the ideal outcome.
      </Alert>

      {/* FIXED group */}
      <Box sx={getGroupSx("fixed")}>
        <Box sx={{ mb: 2 }}>{renderGroupHeader("Fixed", 1, null, groupColors.fixed.border)}</Box>
        <Accordion variant="outlined" disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={summarySx}>
            <Typography fontWeight={600} sx={{ flex: 1 }}>Accuracy</Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
              Criteria
            </Typography>
            <TextField value={ACCURACY_CRITERIA} fullWidth disabled multiline size="small" sx={{ mb: 2 }} />
            <Divider sx={{ mb: 2 }} />
            {renderOptionsReadonly(accuracyOptions, "Accurate")}
          </AccordionDetails>
        </Accordion>
      </Box>

      {/* PRESET group */}
      <Box sx={getGroupSx("preset")}>
        <Box sx={{ mb: 2 }}>{renderGroupHeader("Preset", premadeRubrics.length, openPremadeDialog, groupColors.preset.border)}</Box>
        {premadeRubrics.length === 0 ? (
          renderEmptyState("No preset rubrics added yet. Click + to browse templates.")
        ) : (
          premadeRubrics.map((rubric) => (
            <Accordion key={rubric.id} variant="outlined" disableGutters sx={{ mb: 1 }}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={summarySx}>
                <Typography fontWeight={600} sx={{ flex: 1 }}>{rubric.name}</Typography>
                <Tooltip title="Delete rubric" arrow>
                  <IconButton
                    component="div"
                    size="small"
                    onClick={(e) => { e.stopPropagation(); setRubricToDelete(rubric); }}
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
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
      <Box sx={getGroupSx("custom")}>
        <Box sx={{ mb: 2 }}>{renderGroupHeader("Custom", customRubrics.length, addRubric, groupColors.custom.border)}</Box>
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
            return (
              <Accordion
                key={rubric.id}
                variant="outlined"
                disableGutters
                defaultExpanded={draft}
                sx={{ mb: 1, ...(draft && { borderStyle: "dashed" }) }}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={summarySx}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1, flex: 1 }}>
                    <TextField
                      value={rubric.name}
                      placeholder="Untitled rubric"
                      variant="standard"
                      size="small"
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => updateField(rubric.id, { name: e.target.value })}
                      slotProps={{
                        input: { style: { fontWeight: 600, fontSize: "0.95rem" } },
                      }}
                      sx={{
                        flexGrow: 1,
                        "& .MuiInput-underline:before": { borderBottom: "none" },
                        "& .MuiInput-underline:hover:before": { borderBottom: "1px solid rgba(0,0,0,0.3) !important" },
                      }}
                    />
                    {dirty && !draft && <Chip label="Unsaved" size="small" color="warning" variant="outlined" />}
                  </Box>
                  <Tooltip title="Delete rubric" arrow>
                    <IconButton
                      component="div"
                      size="small"
                      onClick={(e) => { e.stopPropagation(); setRubricToDelete(rubric); }}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
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
                          <HelpOutlineIcon sx={{ fontSize: 14, color: "text.disabled" }} />
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
                            ? <CheckCircleIcon sx={{ fontSize: 24, color: "success.main" }} />
                            : <CheckCircleOutlineIcon sx={{ fontSize: 24, color: "text.disabled" }} />
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
                          <DeleteOutlineIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    );
                  })}

                  <Button startIcon={<AddIcon />} size="small" sx={{ mt: 0.5 }} onClick={() => addOption(rubric.id)}>
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
                        <Tooltip title={errors.length > 0 ? errors.join(", ") : ""}>
                          <span>
                            <Button
                              variant="contained"
                              size="small"
                              startIcon={isSaving ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />}
                              disabled={errors.length > 0 || isSaving}
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

      {/* Preset rubric selection dialog */}
      <Dialog open={premadeDialogOpen} onClose={() => setPremadeDialogOpen(false)} maxWidth="sm" fullWidth>
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
              {premadeTemplates.map((template) => (
                <Card
                  key={template.key}
                  variant="outlined"
                  sx={{ flex: "1 1 180px", maxWidth: 220, position: "relative" }}
                >
                  <CardActionArea
                    onClick={() => addPremadeRubric(template)}
                    disabled={addingPremade !== null}
                    sx={{ p: 2, textAlign: "center" }}
                  >
                    {addingPremade === template.key && (
                      <Box sx={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)" }}>
                        <CircularProgress size={24} />
                      </Box>
                    )}
                    <Box sx={{ mb: 1, opacity: addingPremade === template.key ? 0.3 : 1 }}>
                      {premadeIconMap[template.key] ?? defaultPremadeIcon}
                    </Box>
                    <Typography
                      fontWeight={600}
                      sx={{ mb: 0.5, opacity: addingPremade === template.key ? 0.3 : 1 }}
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
                        opacity: addingPremade === template.key ? 0.3 : 1,
                      }}
                    >
                      {template.criteria}
                    </Typography>
                  </CardActionArea>
                </Card>
              ))}
            </Box>
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDeleteDialog
        open={rubricToDelete !== null}
        onClose={() => setRubricToDelete(null)}
        onConfirm={handleConfirmDelete}
        title="Delete Rubric"
        itemName={rubricToDelete?.name || "this rubric"}
      />
    </Box>
  );
}
