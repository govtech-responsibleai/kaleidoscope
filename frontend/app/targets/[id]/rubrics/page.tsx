"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Divider,
  Button,
  IconButton,
  CircularProgress,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  List,
  ListItemButton,
  ListItemText,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
  Add as AddIcon,
  DeleteOutline as DeleteOutlineIcon,
  CheckCircle as CheckCircleIcon,
  CheckCircleOutline as CheckCircleOutlineIcon,
  HelpOutline as HelpOutlineIcon,
  Save as SaveIcon,
} from "@mui/icons-material";
import { targetRubricApi } from "@/lib/api";
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

export default function RubricsPage() {
  const params = useParams();
  const targetId = Number(params.id);

  const [rubrics, setRubrics] = useState<TargetRubricResponse[]>([]);
  const [savedRubrics, setSavedRubrics] = useState<Record<number, TargetRubricResponse>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Set<number>>(new Set());
  const [saveErrors, setSaveErrors] = useState<Record<number, string>>({});
  const [rubricToDelete, setRubricToDelete] = useState<TargetRubricResponse | null>(null);

  // Pre-made rubric dialog state
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
      // Remove added template from available list
      setPremadeTemplates((prev) => prev.filter((t) => t.key !== template.key));
    } catch {
      // Could show error, but dialog will close
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

  // Split rubrics into premade and custom
  const premadeRubrics = rubrics.filter((r) => isPremade(r));
  const customRubrics = rubrics.filter((r) => !isPremade(r));

  const renderOptionsReadonly = (options: RubricOption[], bestOption: string | null) => (
    <>
      {/* Column headers */}
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

  return (
    <Box>
      {/* Accuracy rubric — always present, read-only */}
      <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
        Accuracy
      </Typography>

      <Card variant="outlined" sx={{ pointerEvents: "none", mb: 2 }}>
        <CardContent>
          <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
            Criteria
          </Typography>
          <TextField
            value="Are the claims in the response supported by the provided context, or do they contain hallucinations?"
            fullWidth
            disabled
            multiline
            size="small"
            sx={{ mb: 2 }}
          />
          <Divider sx={{ mb: 2 }} />
          {renderOptionsReadonly(accuracyOptions, "Accurate")}
        </CardContent>
      </Card>

      {/* Pre-made rubrics section */}
      {premadeRubrics.length > 0 && (
        <>
          <Typography variant="h6" fontWeight={600} sx={{ mt: 3, mb: 1 }}>
            Pre-made Rubrics
          </Typography>

          {premadeRubrics.map((rubric) => (
            <Accordion key={rubric.id} variant="outlined" disableGutters sx={{ mb: 1 }}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 48 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, flex: 1, mr: 1 }}>
                  <Typography fontWeight={600}>{rubric.name}</Typography>
                  <Chip label="Pre-made" size="small" color="info" variant="outlined" />
                </Box>
                <IconButton
                  component="div"
                  size="small"
                  onClick={(e) => { e.stopPropagation(); setRubricToDelete(rubric); }}
                  sx={{ mr: 1 }}
                >
                  <DeleteOutlineIcon fontSize="small" />
                </IconButton>
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
        </>
      )}

      {/* Custom rubrics section */}
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mt: 3, mb: 2 }}>
        <Typography variant="h6" fontWeight={600}>
          Custom Rubrics
        </Typography>
        <Button variant="outlined" size="small" onClick={openPremadeDialog}>
          Add Pre-made Rubric
        </Button>
      </Box>

      {loading ? (
        <CircularProgress size={24} />
      ) : (
        <>
          {customRubrics.map((rubric) => {
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
                <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: 48 }}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1, flex: 1, mr: 1 }}>
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
                  <IconButton
                    component="div"
                    size="small"
                    onClick={(e) => { e.stopPropagation(); setRubricToDelete(rubric); }}
                    sx={{ mr: 1 }}
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
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
                    size="small"
                    onChange={(e) => updateField(rubric.id, { criteria: e.target.value })}
                    sx={{ mb: 2 }}
                  />

                  <Divider sx={{ mb: 2 }} />

                  {/* Column headers */}
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

                  {dirty && (
                    <Box sx={{ mt: 2, display: "flex", alignItems: "center", gap: 1.5 }}>
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
                      {errors.length > 0 && (
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
                  )}
                </AccordionDetails>
              </Accordion>
            );
          })}

          <Button variant="outlined" startIcon={<AddIcon />} onClick={addRubric} sx={{ mt: 1 }}>
            Add Rubric
          </Button>
        </>
      )}

      {/* Pre-made rubric selection dialog */}
      <Dialog open={premadeDialogOpen} onClose={() => setPremadeDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Pre-made Rubric</DialogTitle>
        <DialogContent>
          {premadeLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress size={24} />
            </Box>
          ) : premadeTemplates.length === 0 ? (
            <Typography color="text.secondary" sx={{ py: 2 }}>
              All pre-made rubrics have already been added to this target.
            </Typography>
          ) : (
            <List disablePadding>
              {premadeTemplates.map((template) => (
                <ListItemButton
                  key={template.key}
                  onClick={() => addPremadeRubric(template)}
                  disabled={addingPremade !== null}
                  sx={{ borderRadius: 1, mb: 0.5 }}
                >
                  <ListItemText
                    primary={
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <Typography fontWeight={600}>{template.name}</Typography>
                        {addingPremade === template.key && <CircularProgress size={16} />}
                      </Box>
                    }
                    secondary={template.criteria}
                    secondaryTypographyProps={{ noWrap: true }}
                  />
                </ListItemButton>
              ))}
            </List>
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
