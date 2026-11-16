import type { JudgeReliabilityStatus, VerdictStatus } from "@/lib/types";

export interface GateSettings {
  reliability_threshold: number;
  min_calibration_samples: number;
  recommended_calibration_samples: number;
}

/** Fallback when a contract is not loaded yet; mirrors the backend defaults. */
export const DEFAULT_GATE: GateSettings = {
  reliability_threshold: 0.5,
  min_calibration_samples: 20,
  recommended_calibration_samples: 30,
};

const pct = (value: number) => `${(value * 100).toFixed(0)}%`;

/** One-line status text for a judge's reliability, e.g. "Not calibrated — 12 of 20 labels". */
export function judgeReliabilityText(
  status: JudgeReliabilityStatus | null,
  reliability: number | null,
  sampleCount: number,
  gate: GateSettings,
  calibrationCount = 0
): string {
  switch (status) {
    case "aligned":
      return `✓ ${pct(reliability ?? 0)} reliability (n=${sampleCount})`;
    case "unreliable":
      return `✗ ${pct(reliability ?? 0)} reliability (n=${sampleCount}) — excluded`;
    case "insufficient_calibration":
      return reliability != null
        ? `Not calibrated — ${sampleCount} of ${gate.min_calibration_samples} labels (${pct(reliability)} so far)`
        : `Not calibrated — ${sampleCount} of ${gate.min_calibration_samples} labels`;
    case "not_calibrated":
      return calibrationCount > 0
        ? `Not calibrated — this judge has not scored the ${calibrationCount} labelled responses yet`
        : `Not calibrated — 0 of ${gate.min_calibration_samples} labels`;
    default:
      return "--% reliability";
  }
}

export function judgeReliabilityTooltip(gate: GateSettings): string {
  return `Macro-F1 agreement between this judge and your annotations. A judge joins the aggregate when it reaches ${pct(
    gate.reliability_threshold
  )} on at least ${gate.min_calibration_samples} labelled responses (${gate.recommended_calibration_samples}+ recommended).`;
}

/**
 * Why an aggregate is withheld; empty string when it is ready.
 *
 * `flags.hasUnreliableJudge` and `flags.hasCalibratingJudge` distinguish the ways
 * `no_aligned_judge` happens: a judge was measured and fell short (its annotations
 * disagree), another is still working through its labels, or no judge has cleared
 * the threshold yet.
 */
export function verdictWithheldText(
  status: VerdictStatus,
  calibrationCount: number,
  gate: GateSettings,
  flags: { hasUnreliableJudge?: boolean; hasCalibratingJudge?: boolean } = {}
): string {
  const { hasUnreliableJudge = false, hasCalibratingJudge = false } = flags;
  switch (status) {
    case "not_calibrated":
      return `Not calibrated — annotate at least ${gate.min_calibration_samples} responses to enable automated scoring`;
    case "insufficient_calibration":
      return calibrationCount >= gate.min_calibration_samples
        ? `Not calibrated — judges have not yet scored enough of the ${calibrationCount} labelled responses`
        : `Not calibrated — ${calibrationCount} of ${gate.min_calibration_samples} labels`;
    case "no_aligned_judge":
      if (hasUnreliableJudge && hasCalibratingJudge) {
        return "Withheld — a judge failed calibration and another is still calibrating";
      }
      return hasUnreliableJudge
        ? "Withheld — no judge matches your annotations. Human review required for this rubric"
        : "Withheld — no judge meets the reliability threshold yet";
    default:
      return "";
  }
}
