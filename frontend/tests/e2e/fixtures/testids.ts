export const TESTIDS = {
  // SnapshotHeader
  SNAPSHOT_SELECT: "snapshot-select",

  // QAJobControl
  QA_JOB_CONTROL_BUTTON: "qa-job-control-button",

  // QAList
  QA_LIST: "qa-list",

  // Scoring page — JudgeStrip
  JUDGE_LIST: "judge-list",
  JUDGE_ADD_BUTTON: "judge-add-button",

  // Scoring page — gauge
  SCORE_GAUGE: "score-gauge",

  // Scoring page — ResultsTable
  RESULTS_TABLE: "results-table",
  RESULTS_TABLE_ROW_TOGGLE: "results-table-row-toggle",

  // Report page
  SUMMARY_CARD: (label: string) => `summary-card-${label.toLowerCase().replace(/\s+/g, "-")}`,
  SNAPSHOT_SCORE_CHART: "snapshot-score-chart",

  // GenerateEvalsModal — choose_mode step
  GENERATE_EVALS_CARD_GENERATE: "generate-evals-card-generate",
  GENERATE_EVALS_CARD_UPLOAD: "generate-evals-card-upload",

  // GenerateEvalsModal — configure_questions step
  GENERATION_MODEL_SELECTOR: "generation-model-selector",

  // Rubrics page
  RUBRIC_CUSTOM_ADD: "rubric-custom-add",
  RUBRIC_PRESET_ADD: "rubric-preset-add",
  PRESET_RUBRIC_DIALOG: "preset-rubric-dialog",
  PRESET_RUBRIC_CARD: (slug: string) => `preset-rubric-card-${slug}`,
} as const;
