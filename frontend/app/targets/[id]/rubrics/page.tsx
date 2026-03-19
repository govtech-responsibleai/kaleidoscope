"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Alert,
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
} from "@mui/material";
import {
  EditOutlined as EditOutlinedIcon,
  Add as AddIcon,
  DeleteOutline as DeleteOutlineIcon,
  CheckCircle as CheckCircleIcon,
  CheckCircleOutline as CheckCircleOutlineIcon,
  HelpOutline as HelpOutlineIcon,
} from "@mui/icons-material";
import { targetRubricApi } from "@/lib/api";
import { TargetRubricResponse, RubricOption } from "@/lib/types";
import ConfirmDeleteDialog from "@/components/shared/ConfirmDeleteDialog";

const accuracyOptions = [
  { option: "Accurate", description: "All claims are supported by the provided context." },
  { option: "Inaccurate", description: "One or more claims are not supported or hallucinated." },
];

export default function RubricsPage() {
  const params = useParams();
  const targetId = Number(params.id);

  const [rubrics, setRubrics] = useState<TargetRubricResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [rubricToDelete, setRubricToDelete] = useState<TargetRubricResponse | null>(null);
  const [touchedRubrics, setTouchedRubrics] = useState<Set<number>>(new Set());

  useEffect(() => {
    targetRubricApi.list(targetId).then((res) => {
      setRubrics(res.data);
      setLoading(false);
    });
  }, [targetId]);

  const addRubric = async () => {
    // Optimistic: show placeholder immediately, replace with real data after API responds
    const tempId = -Date.now();
    const placeholder: TargetRubricResponse = {
      id: tempId, target_id: targetId, name: "", criteria: "",
      options: [], best_option: null, position: 0, category: "default",
      created_at: "", updated_at: "",
    };
    setRubrics((prev) => [...prev, placeholder]);
    const res = await targetRubricApi.create(targetId, {
      name: "",
      criteria: "",
      options: [],
    });
    setRubrics((prev) => prev.map((r) => (r.id === tempId ? res.data : r)));
  };

  const removeRubric = async (rubricId: number) => {
    await targetRubricApi.delete(targetId, rubricId);
    setRubrics((prev) => prev.filter((r) => r.id !== rubricId));
  };

  const saveName = async (rubric: TargetRubricResponse, name: string) => {
    if (name === rubric.name) return;
    const res = await targetRubricApi.update(targetId, rubric.id, { name });
    setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? res.data : r)));
  };

  const saveCriteria = async (rubric: TargetRubricResponse, criteria: string) => {
    if (criteria === rubric.criteria) return;
    const res = await targetRubricApi.update(targetId, rubric.id, { criteria });
    setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? res.data : r)));
  };

  const saveOptions = async (rubric: TargetRubricResponse, options: RubricOption[]) => {
    const res = await targetRubricApi.update(targetId, rubric.id, { options });
    setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? res.data : r)));
  };

  const updateOptionField = (
    rubric: TargetRubricResponse,
    index: number,
    field: keyof RubricOption,
    value: string
  ) => {
    const updated = rubric.options.map((o, i) => (i === index ? { ...o, [field]: value } : o));
    setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? { ...r, options: updated } : r)));
  };

  const addOption = async (rubric: TargetRubricResponse) => {
    const updated = [...rubric.options, { option: "", description: "" }];
    const res = await targetRubricApi.update(targetId, rubric.id, { options: updated });
    setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? res.data : r)));
  };

  const removeOption = async (rubric: TargetRubricResponse, index: number) => {
    const removed = rubric.options[index];
    const updated = rubric.options.filter((_, i) => i !== index);
    const patch: { options: RubricOption[]; best_option?: string | null } = { options: updated };
    if (rubric.best_option === removed.option) {
      patch.best_option = null;
    }
    const res = await targetRubricApi.update(targetId, rubric.id, patch);
    setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? res.data : r)));
  };

  const saveBestOption = async (rubric: TargetRubricResponse, optionName: string) => {
    const res = await targetRubricApi.update(targetId, rubric.id, { best_option: optionName });
    setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? res.data : r)));
  };

  const getRubricErrors = (rubric: TargetRubricResponse): string[] => {
    const errors: string[] = [];
    if (rubric.options.length < 2) errors.push("Add at least 2 options");
    if (!rubric.best_option || !rubric.options.some((o) => o.option === rubric.best_option))
      errors.push("Select an ideal outcome");
    return errors;
  };

  const markTouched = (rubricId: number) => {
    setTouchedRubrics((prev) => new Set(prev).add(rubricId));
  };

  const handleConfirmDelete = async () => {
    if (!rubricToDelete) return;
    await targetRubricApi.delete(targetId, rubricToDelete.id);
    setRubrics((prev) => prev.filter((r) => r.id !== rubricToDelete.id));
  };

  return (
    <Box>
      <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
        Default Rubrics
      </Typography>

      {/* Static Accuracy rubric */}
      <Card variant="outlined" sx={{ pointerEvents: "none", mb: 2 }}>
        <CardContent>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} color="text.disabled">
              Accuracy
            </Typography>
          </Box>

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

          {accuracyOptions.map(({ option, description }) => (
            <Box key={option} sx={{ display: "flex", gap: 1.5, mb: 1.5, alignItems: "center" }}>
              <Box sx={{ width: 100, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {option === "Accurate"
                  ? <CheckCircleIcon sx={{ fontSize: 24, color: "success.main" }} />
                  : <CheckCircleOutlineIcon sx={{ fontSize: 24, color: "text.disabled" }} />
                }
              </Box>
              <TextField value={option} disabled size="small" sx={{ width: 140, flexShrink: 0 }} />
              <TextField value={description} disabled size="small" fullWidth />
            </Box>
          ))}
        </CardContent>
      </Card>

      {/* Custom rubrics section */}
      <Typography variant="h6" fontWeight={600} sx={{ mt: 3, mb: 2 }}>
        Custom Rubrics
      </Typography>

      {loading ? (
        <CircularProgress size={24} />
      ) : (
        <>
          {rubrics.map((rubric) => {
            const errors = getRubricErrors(rubric);
            const showErrors = touchedRubrics.has(rubric.id) && errors.length > 0;
            return (
            <Card
              key={rubric.id}
              variant="outlined"
              sx={{ mb: 2, ...(showErrors && { borderColor: "error.main" }) }}
              onBlur={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                  markTouched(rubric.id);
                }
              }}
            >
              <CardContent>
                {showErrors && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    Incomplete rubric: {errors.join(" and ").toLowerCase()} to use in scoring.
                  </Alert>
                )}
                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
                  <TextField
                    defaultValue={rubric.name}
                    placeholder="Enter rubric name..."
                    variant="standard"
                    size="small"
                    onBlur={(e) => saveName(rubric, e.target.value)}
                    inputProps={{ style: { fontWeight: 600, fontSize: "1rem" } }}
                    sx={{ flexGrow: 1, mr: 1 }}
                  />
                  <IconButton size="small" onClick={() => setRubricToDelete(rubric)}>
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Box>

                <Typography variant="caption" fontWeight={600} color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
                  Criteria
                </Typography>
                <TextField
                  defaultValue={rubric.criteria}
                  placeholder="Describe your evaluation criteria"
                  fullWidth
                  multiline
                  size="small"
                  onBlur={(e) => saveCriteria(rubric, e.target.value)}
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
                        onClick={() => { if (opt.option) saveBestOption(rubric, opt.option); }}
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
                        onChange={(e) => updateOptionField(rubric, i, "option", e.target.value)}
                        onBlur={() => saveOptions(rubric, rubric.options)}
                      />
                      <TextField
                        placeholder="Description"
                        value={opt.description}
                        size="small"
                        fullWidth
                        multiline
                        onChange={(e) => updateOptionField(rubric, i, "description", e.target.value)}
                        onBlur={() => saveOptions(rubric, rubric.options)}
                      />
                      <IconButton size="small" onClick={() => removeOption(rubric, i)}>
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  );
                })}

                <Button startIcon={<AddIcon />} size="small" sx={{ mt: 0.5 }} onClick={() => addOption(rubric)}>
                  Add Option
                </Button>
              </CardContent>
            </Card>
            );
          })}

          <Button variant="outlined" startIcon={<AddIcon />} onClick={addRubric} sx={{ mt: 1 }}>
            Add Rubric
          </Button>
        </>
      )}

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
