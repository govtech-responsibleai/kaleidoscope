"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import {
  IconChevronDown,
  IconFileTypePdf,
  IconMessageQuestion,
  IconRobotFace,
  IconScreenshot,
  IconUser,
} from "@tabler/icons-react";
import { useParams } from "next/navigation";
import { targetApi, snapshotApi, judgeApi, metricsApi, targetRubricApi } from "@/lib/api";
import { TargetResponse, TargetStats, SnapshotMetric, Snapshot, TargetRubricResponse } from "@/lib/types";
import SnapshotAccuracyChart, {
  type SnapshotMetricSeriesPoint,
} from "@/components/overview/SnapshotAccuracyChart";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import { actionIconProps, statIconProps } from "@/lib/iconStyles";

type MetricDefinition = {
  key: string;
  label: string;
  color: string;
  rubricId: number | null;
};

const detailCardSx = {
  borderColor: "grey.200",
  bgcolor: "background.paper",
} as const;

export default function TargetReport() {
  const params = useParams();
  const theme = useTheme();
  const targetId = parseInt(params.id as string, 10);
  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [judgeCount, setJudgeCount] = useState(0);
  const [snapshotMetrics, setSnapshotMetrics] = useState<SnapshotMetric[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [rubrics, setRubrics] = useState<TargetRubricResponse[]>([]);
  const [allRubricMetrics, setAllRubricMetrics] = useState<SnapshotMetric[]>([]);
  const [downloading, setDownloading] = useState(false);
  const [selectedMetricKeys, setSelectedMetricKeys] = useState<string[]>([]);
  const [metricMenuAnchor, setMetricMenuAnchor] = useState<null | HTMLElement>(null);
  const previousMetricKeysRef = useRef<string[]>([]);

  const metricColors = useMemo(
    () => [
      theme.palette.primary.main,
      theme.palette.secondary.main,
      theme.palette.success.main,
      theme.palette.warning.main,
      theme.palette.info.main,
      theme.palette.error.main,
    ],
    [theme]
  );

  const metricDefinitions = useMemo<MetricDefinition[]>(() => {
    const rubricDefinitions = rubrics.map((rubric, index) => ({
      key: `rubric-${rubric.id}`,
      label: rubric.name,
      color: metricColors[(index + 1) % metricColors.length],
      rubricId: rubric.id,
    }));

    return [
      {
        key: "accuracy",
        label: "Accuracy",
        color: metricColors[0],
        rubricId: null,
      },
      ...rubricDefinitions,
    ];
  }, [metricColors, rubrics]);

  const selectedMetrics = useMemo(
    () =>
      selectedMetricKeys
        .map((key) => metricDefinitions.find((definition) => definition.key === key))
        .filter((definition): definition is MetricDefinition => Boolean(definition)),
    [metricDefinitions, selectedMetricKeys]
  );

  const fetchData = async () => {
    try {
      const [targetRes, statsRes, snapshotsRes, metricsRes, rubricsRes] = await Promise.all([
        targetApi.get(targetId),
        targetApi.getStats(targetId),
        snapshotApi.list(targetId),
        metricsApi.getSnapshotMetrics(targetId),
        targetRubricApi.list(targetId),
      ]);
      setTarget(targetRes.data);
      setStats(statsRes.data);
      setSnapshots(snapshotsRes.data);
      setSnapshotMetrics(metricsRes.data ?? []);
      setRubrics(rubricsRes.data ?? []);

      const judgeResponses = await Promise.all(
        (rubricsRes.data ?? []).map((rubric) => judgeApi.getForRubric(rubric.id, targetId))
      );
      const uniqueJudgeIds = new Set<number>();
      judgeResponses.forEach((response) => {
        response.data.forEach((judge) => uniqueJudgeIds.add(judge.id));
      });
      setJudgeCount(uniqueJudgeIds.size);

      try {
        const rubricMetricsRes = await metricsApi.getAllRubricSnapshotMetrics(targetId);
        setAllRubricMetrics(rubricMetricsRes.data ?? []);
      } catch {
        setAllRubricMetrics([]);
      }

    } catch (error) {
      console.error("Failed to fetch target data:", error);
    } finally {
      setLoading(false);
      setMetricsLoading(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, [targetId]);

  useEffect(() => {
    const metricKeys = metricDefinitions.map((definition) => definition.key);

    setSelectedMetricKeys((current) => {
      const previousMetricKeys = previousMetricKeysRef.current;
      const validKeys = current.filter((key) => metricKeys.includes(key));
      const hadFullPreviousSelection =
        previousMetricKeys.length > 0 &&
        previousMetricKeys.every((key) => current.includes(key));
      const hasNewMetricKeys = metricKeys.some((key) => !previousMetricKeys.includes(key));

      let next: string[];
      if (validKeys.length === 0 && metricKeys.length > 0) {
        next = metricKeys;
      } else if (hadFullPreviousSelection && hasNewMetricKeys) {
        next = metricKeys;
      } else {
        next = validKeys;
      }

      previousMetricKeysRef.current = metricKeys;

      if (next.length === current.length && next.every((k, i) => k === current[i])) {
        return current;
      }
      return next;
    });
  }, [metricDefinitions]);

  const sortedSnapshots = useMemo(
    () => [...snapshots].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
    [snapshots]
  );

  const chartData = useMemo<SnapshotMetricSeriesPoint[]>(() => {
    return sortedSnapshots.map((snapshot) => ({
      snapshotId: snapshot.id,
      snapshotName: snapshot.name,
      metrics: selectedMetrics.map((definition) => {
        const metric =
          definition.rubricId === null
            ? snapshotMetrics.find((entry) => entry.snapshot_id === snapshot.id) ?? null
            : allRubricMetrics.find(
                (entry) => entry.snapshot_id === snapshot.id && entry.rubric_id === definition.rubricId
              ) ?? null;

        return {
          key: definition.key,
          label: definition.label,
          color: definition.color,
          value: metric?.aggregated_accuracy ?? null,
          totalAnswers: metric?.total_answers ?? null,
        };
      }),
    }));
  }, [allRubricMetrics, selectedMetrics, snapshotMetrics, sortedSnapshots]);

  const toggleMetric = (key: string) => {
    setSelectedMetricKeys((current) => {
      if (current.includes(key)) {
        if (current.length === 1) return current;
        return current.filter((value) => value !== key);
      }
      return [...current, key];
    });
  };

  const handleDownloadReport = async () => {
    setDownloading(true);
    try {
      const element = document.getElementById("report-content");
      if (!element) throw new Error("Report content not found");

      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: "#ffffff",
      });

      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF("p", "mm", "a4");
      const margin = 10;
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const contentWidth = pageWidth - margin * 2;
      const contentHeight = (canvas.height * contentWidth) / canvas.width;

      let heightLeft = contentHeight;
      let position = margin;

      pdf.addImage(imgData, "PNG", margin, position, contentWidth, contentHeight);
      heightLeft -= pageHeight - margin * 2;

      while (heightLeft > 0) {
        position = -(contentHeight - heightLeft) + margin;
        pdf.addPage();
        pdf.addImage(imgData, "PNG", margin, position, contentWidth, contentHeight);
        heightLeft -= pageHeight - margin * 2;
      }

      pdf.save(`${target?.name || "target"}_report_${new Date().toISOString().split("T")[0]}.pdf`);
    } catch (error) {
      console.error("Failed to generate report:", error);
      alert("Failed to generate report. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="30vh">
        <CircularProgress />
      </Box>
    );
  }

  if (!target || !stats) {
    return null;
  }

  const approvedPersonas = stats.personas.approved || 0;
  const approvedQuestions = stats.questions.approved || 0;

  return (
    <Box>
      <Stack
        direction={{ xs: "column", lg: "row" }}
        spacing={2}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", lg: "center" }}
        sx={{ mb: 3 }}
      >
        <Box>
          <Typography variant="overline" sx={{ color: "primary.main", fontWeight: 800, letterSpacing: 1.2 }}>
            Report Dashboard
          </Typography>
          <Typography variant="h4" fontWeight={700} sx={{ mt: 0.5 }}>
            {target.name}
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mt: 1, maxWidth: 780 }}>
            Executive overview of evaluation coverage, snapshot performance, and judge-backed reliability signals.
          </Typography>
        </Box>

        <Tooltip title={downloading ? "Generating PDF..." : "Export PDF report"}>
          <span>
            <Button
              variant="contained"
              startIcon={
                downloading ? <CircularProgress size={20} color="inherit" /> : <IconFileTypePdf {...actionIconProps} />
              }
              onClick={handleDownloadReport}
              disabled={downloading || loading}
              sx={{ 
                bgcolor: "secondary.main",
                minWidth: 120 
              }}
            >
              {downloading ? "Generating..." : "Export PDF"}
            </Button>
          </span>
        </Tooltip>
      </Stack>

      <Box id="report-content">

        <Card variant="outlined" sx={{
            borderColor: "grey.200",
            mb: 3
          }}
        >
          <CardContent sx={{ p: 3 }}>
            <Stack spacing={3}>
              <Box
                sx={{
                  display: "grid",
                  gap: 2,
                }}
              >
                <Box>
                  <Typography variant="h6" fontWeight={700}>
                    Target Summary
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                    Last updated {new Date(target.updated_at).toLocaleDateString()}
                  </Typography>
                </Box>
                <Box
                  sx={{
                    display: "grid",
                    gap: 1,
                    gridTemplateColumns: "auto 1fr",
                    alignItems: "start",
                  }}
                >
                  <Typography variant="body2" color="text.secondary">Agency</Typography>
                  <Typography variant="body2">{target.agency || "N/A"}</Typography>
                  <Typography variant="body2" color="text.secondary">Purpose</Typography>
                  <Typography variant="body2">{target.purpose || "N/A"}</Typography>
                  <Typography variant="body2" color="text.secondary">Target Users</Typography>
                  <Typography variant="body2">{target.target_users || "N/A"}</Typography>
                  <Typography variant="body2" color="text.secondary">API Endpoint</Typography>
                  <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
                    {target.api_endpoint || "N/A"}
                  </Typography>
                </Box>
              </Box>
            </Stack>
          </CardContent>
        </Card>
        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", md: "repeat(4, minmax(0, 1fr))" },
            mb: 3,
          }}
        >
          <SummaryCard
            icon={<IconUser {...statIconProps} />}
            label="Approved Personas"
            value={approvedPersonas}
            helper="Personas available for evaluation design"
          />
          <SummaryCard
            icon={<IconMessageQuestion {...statIconProps} />}
            label="Approved Questions"
            value={approvedQuestions}
            helper="Approved evaluation prompts in rotation"
          />
          <SummaryCard
            icon={<IconScreenshot {...statIconProps} />}
            label="Snapshots"
            value={snapshots.length}
            helper="Snapshots included in cross-run comparison"
          />
          <SummaryCard
            icon={<IconRobotFace {...statIconProps} />}
            label="Judges"
            value={judgeCount}
            helper="Configured evaluators across this target"
          />
        </Box>

          <Card variant="outlined" sx={detailCardSx}>
            <CardContent sx={{ p: 3 }}>
              <Stack spacing={3}>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ xs: "flex-start", sm: "center" }} justifyContent="space-between">
                  <Box>
                    <Typography variant="h6" fontWeight={700}>
                      Metrics Across Snapshots
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      Compare the selected metrics across every available snapshot in one grouped chart.
                    </Typography>
                  </Box>

                  <Button
                    variant="outlined"
                    endIcon={<IconChevronDown {...actionIconProps} />}
                    onClick={(event) => setMetricMenuAnchor(event.currentTarget)}
                    sx={{ minWidth: { xs: "100%", sm: 220 }, justifyContent: "space-between", flexShrink: 0 }}
                  >
                    {selectedMetrics.length === metricDefinitions.length
                      ? `All metrics (${selectedMetrics.length})`
                      : selectedMetrics.map((metric) => metric.label).join(" • ")}
                  </Button>

                  <Menu
                    anchorEl={metricMenuAnchor}
                    open={Boolean(metricMenuAnchor)}
                    onClose={() => setMetricMenuAnchor(null)}
                  >
                    {metricDefinitions.map((metric) => (
                      <MenuItem key={metric.key} onClick={() => toggleMetric(metric.key)}>
                        <Checkbox checked={selectedMetricKeys.includes(metric.key)} />
                        <ListItemText
                          primary={metric.label}
                          secondary={
                            selectedMetricKeys.includes(metric.key)
                              ? `Order ${selectedMetricKeys.indexOf(metric.key) + 1}`
                              : undefined
                          }
                        />
                      </MenuItem>
                    ))}
                  </Menu>
                </Stack>

                {/*
                  Previous report design kept a snapshot breakdown selector and a horizontal
                  gauge row here. It is intentionally commented out rather than deleted so
                  the older layout can be restored if product direction changes again.

                  <Divider />

                  <Box>
                    <Typography variant="subtitle2" fontWeight={700}>
                      Snapshot Breakdown
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
                      {selectedSnapshot
                        ? `Showing ${selectedSnapshot.name} across ${selectedMetrics.length || 0} selected metric${selectedMetrics.length === 1 ? "" : "s"}.`
                        : "Select one snapshot to inspect the current metric breakdown."}
                    </Typography>

                    <SnapshotHeader
                      targetId={targetId}
                      snapshots={snapshots}
                      selectedSnapshotId={selectedSnapshotId}
                      onSelectSnapshot={updateSnapshotSelection}
                      onSnapshotCreated={handleSnapshotCreated}
                      onSnapshotDeleted={handleSnapshotCreated}
                      loading={loading}
                    />
                  </Box>

                  <Box
                    sx={{
                      overflowX: "auto",
                      pb: 1,
                    }}
                  >
                    <Stack direction="row" spacing={2} sx={{ width: "max-content", minWidth: "100%" }}>
                      {selectedSnapshotMetrics.map(({ definition, metric }) => (
                        <Card
                          key={definition.key}
                          variant="outlined"
                          sx={{
                            borderColor: "grey.200",
                            minWidth: { xs: 260, md: 300 },
                            flexShrink: 0,
                          }}
                        >
                          <CardContent>
                            <SnapshotAccuracyCard
                              snapshotMetric={metric}
                              loading={false}
                              emptyMessage={`No ${definition.label.toLowerCase()} data for this snapshot`}
                              showWarningBox={definition.rubricId === null}
                              title={definition.label}
                              gaugeLabel={definition.gaugeLabel}
                            />
                          </CardContent>
                        </Card>
                      ))}
                    </Stack>
                  </Box>
                */}

                <SnapshotAccuracyChart
                  data={chartData}
                  loading={metricsLoading}
                />
              </Stack>
            </CardContent>
          </Card>

      </Box>
    </Box>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  helper,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  helper: string;
}) {
  return (
    <Card variant="outlined" sx={detailCardSx}>
      <CardContent sx={{ p: 2.5 }}>
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1.25} alignItems="center">
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: 2,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                bgcolor: "grey.100",
                color: "primary.main",
              }}
            >
              {icon}
            </Box>
            <Typography variant="subtitle2" color="text.secondary" fontWeight={700}>
              {label}
            </Typography>
          </Stack>

          <Typography variant="h3" fontWeight={700}>
            {value}
          </Typography>

          <Typography variant="body2" color="text.secondary">
            {helper}
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
}
