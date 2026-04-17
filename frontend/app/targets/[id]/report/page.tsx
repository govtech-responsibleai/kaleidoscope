"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  Divider,
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
  IconRobot,
  IconScreenshot,
  IconUser,
} from "@tabler/icons-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { targetApi, snapshotApi, judgeApi, metricsApi, targetRubricApi } from "@/lib/api";
import { TargetResponse, TargetStats, SnapshotMetric, ConfusionMatrix, Snapshot, TargetRubricResponse } from "@/lib/types";
import SnapshotAccuracyChart, {
  type SnapshotMetricSeriesPoint,
} from "@/components/overview/SnapshotAccuracyChart";
import SnapshotAccuracyCard from "@/components/shared/SnapshotAccuracyCard";
import ConfusionMatrixCard from "@/components/overview/ConfusionMatrixCard";
import SnapshotHeader from "@/components/shared/SnapshotHeader";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import { actionIconProps, statIconProps } from "@/lib/iconStyles";

type MetricDefinition = {
  key: string;
  label: string;
  gaugeLabel: string;
  color: string;
  rubricId: number | null;
};

const detailCardSx = {
  borderColor: "grey.200",
  bgcolor: "background.paper",
} as const;

export default function TargetReport() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const theme = useTheme();
  const targetId = parseInt(params.id as string, 10);

  const snapshotIdFromUrl = searchParams.get("snapshot");
  const [target, setTarget] = useState<TargetResponse | null>(null);
  const [stats, setStats] = useState<TargetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<number | null>(
    snapshotIdFromUrl ? Number(snapshotIdFromUrl) : null
  );
  const [judgeCount, setJudgeCount] = useState(0);
  const [snapshotMetrics, setSnapshotMetrics] = useState<SnapshotMetric[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [rubrics, setRubrics] = useState<TargetRubricResponse[]>([]);
  const [allRubricMetrics, setAllRubricMetrics] = useState<SnapshotMetric[]>([]);
  const [downloading, setDownloading] = useState(false);
  const [confusionMatrix, setConfusionMatrix] = useState<ConfusionMatrix | null>(null);
  const [confusionMatrixLoading, setConfusionMatrixLoading] = useState(true);
  const [selectedMetricKeys, setSelectedMetricKeys] = useState<string[]>(["accuracy"]);
  const [metricMenuAnchor, setMetricMenuAnchor] = useState<null | HTMLElement>(null);

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
      gaugeLabel: `% ${rubric.best_option || rubric.options?.[0]?.option || "best option"}`,
      color: metricColors[(index + 1) % metricColors.length],
      rubricId: rubric.id,
    }));

    return [
      {
        key: "accuracy",
        label: "Accuracy",
        gaugeLabel: "Aggregated Accuracy Score",
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

  const updateSnapshotSelection = (snapshotId: number | null) => {
    setSelectedSnapshotId(snapshotId);
    const newSearchParams = new URLSearchParams(searchParams.toString());
    if (snapshotId === null) {
      newSearchParams.delete("snapshot");
    } else {
      newSearchParams.set("snapshot", snapshotId.toString());
    }
    const query = newSearchParams.toString();
    router.push(`/targets/${targetId}/report${query ? `?${query}` : ""}`, { scroll: false });
  };

  const fetchData = async () => {
    try {
      const [targetRes, statsRes, snapshotsRes, judgesRes, metricsRes, rubricsRes] = await Promise.all([
        targetApi.get(targetId),
        targetApi.getStats(targetId),
        snapshotApi.list(targetId),
        judgeApi.list(targetId),
        metricsApi.getSnapshotMetrics(targetId),
        targetRubricApi.list(targetId),
      ]);
      setTarget(targetRes.data);
      setStats(statsRes.data);
      setSnapshots(snapshotsRes.data);
      setJudgeCount(judgesRes.data.length);
      setSnapshotMetrics(metricsRes.data ?? []);
      setRubrics(rubricsRes.data ?? []);

      try {
        const rubricMetricsRes = await metricsApi.getAllRubricSnapshotMetrics(targetId);
        setAllRubricMetrics(rubricMetricsRes.data ?? []);
      } catch {
        setAllRubricMetrics([]);
      }

      const hasSelectedSnapshot =
        selectedSnapshotId !== null && snapshotsRes.data.some((snapshot) => snapshot.id === selectedSnapshotId);
      if (!hasSelectedSnapshot) {
        if (snapshotsRes.data.length > 0) {
          const mostRecent = [...snapshotsRes.data].sort(
            (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          )[0];
          updateSnapshotSelection(mostRecent.id);
        } else if (selectedSnapshotId !== null) {
          updateSnapshotSelection(null);
        }
      }
    } catch (error) {
      console.error("Failed to fetch target data:", error);
    } finally {
      setLoading(false);
      setMetricsLoading(false);
    }
  };

  const fetchConfusionMatrix = async (snapshotId?: number) => {
    setConfusionMatrixLoading(true);
    try {
      const res = await metricsApi.getConfusionMatrix(targetId, snapshotId);
      setConfusionMatrix(res.data);
    } catch (error) {
      console.error("Failed to fetch confusion matrix:", error);
      setConfusionMatrix(null);
    } finally {
      setConfusionMatrixLoading(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, [targetId]);

  useEffect(() => {
    setSelectedMetricKeys((current) => {
      const validKeys = current.filter((key) => metricDefinitions.some((definition) => definition.key === key));
      return validKeys.length > 0 ? validKeys : ["accuracy"];
    });
  }, [metricDefinitions]);

  useEffect(() => {
    if (selectedSnapshotId) {
      void fetchConfusionMatrix(selectedSnapshotId);
    } else {
      setConfusionMatrix(null);
      setConfusionMatrixLoading(false);
    }
  }, [selectedSnapshotId]);

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

  const selectedSnapshotMetrics = useMemo(
    () =>
      selectedMetrics.map((definition) => ({
        definition,
        metric:
          definition.rubricId === null
            ? snapshotMetrics.find((entry) => entry.snapshot_id === selectedSnapshotId) ?? null
            : allRubricMetrics.find(
                (entry) => entry.snapshot_id === selectedSnapshotId && entry.rubric_id === definition.rubricId
              ) ?? null,
      })),
    [allRubricMetrics, selectedMetrics, selectedSnapshotId, snapshotMetrics]
  );

  const handleSnapshotCreated = async () => {
    await fetchData();
  };

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
  const selectedSnapshot = snapshots.find((snapshot) => snapshot.id === selectedSnapshotId) ?? null;

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
              sx={{ minWidth: 170 }}
            >
              {downloading ? "Generating..." : "Export PDF"}
            </Button>
          </span>
        </Tooltip>
      </Stack>

      <Box id="report-content">
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
            helper={selectedSnapshot ? `Active: ${selectedSnapshot.name}` : "No active snapshot"}
          />
          <SummaryCard
            icon={<IconRobot {...statIconProps} />}
            label="Judges"
            value={judgeCount}
            helper="Configured evaluators across this target"
          />
        </Box>

        <Box
          sx={{
            display: "grid",
            gap: 3,
            gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.9fr) minmax(320px, 0.95fr)" },
            alignItems: "start",
          }}
        >
          <Stack spacing={3}>
            <Card variant="outlined" sx={detailCardSx}>
              <CardContent sx={{ p: 3 }}>
                <Stack spacing={3}>
                  <Box
                    sx={{
                      display: "grid",
                      gap: 2,
                      gridTemplateColumns: { xs: "1fr", md: "1.2fr 1fr" },
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

                  <Divider />

                  <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ xs: "stretch", md: "center" }}>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="subtitle2" fontWeight={700}>
                        Compared Metrics
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        Select one or more metrics. Selection order controls grouped bar order.
                      </Typography>
                    </Box>

                    <Button
                      variant="outlined"
                      endIcon={<IconChevronDown {...actionIconProps} />}
                      onClick={(event) => setMetricMenuAnchor(event.currentTarget)}
                      sx={{ minWidth: 240, justifyContent: "space-between" }}
                    >
                      {selectedMetrics.map((metric) => metric.label).join(" • ")}
                    </Button>

                    <Menu
                      anchorEl={metricMenuAnchor}
                      open={Boolean(metricMenuAnchor)}
                      onClose={() => setMetricMenuAnchor(null)}
                    >
                      {metricDefinitions.map((metric) => (
                        <MenuItem key={metric.key} onClick={() => toggleMetric(metric.key)}>
                          <Checkbox checked={selectedMetricKeys.includes(metric.key)} />
                          <ListItemText primary={metric.label} secondary={selectedMetricKeys.includes(metric.key) ? `Order ${selectedMetricKeys.indexOf(metric.key) + 1}` : undefined} />
                        </MenuItem>
                      ))}
                    </Menu>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>

            <SnapshotAccuracyChart data={chartData} loading={metricsLoading} />
          </Stack>

          <Card variant="outlined" sx={detailCardSx}>
            <CardContent sx={{ p: 3 }}>
              <Stack spacing={3}>
                <Box>
                  <Typography variant="h6" fontWeight={700}>
                    Snapshot Detail
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    Keep one snapshot selected while comparing multiple metrics side by side.
                  </Typography>
                </Box>

                <SnapshotHeader
                  targetId={targetId}
                  snapshots={snapshots}
                  selectedSnapshotId={selectedSnapshotId}
                  onSelectSnapshot={updateSnapshotSelection}
                  onSnapshotCreated={handleSnapshotCreated}
                  onSnapshotDeleted={handleSnapshotCreated}
                  loading={loading}
                />

                <Box
                  sx={{
                    display: "grid",
                    gap: 2,
                    gridTemplateColumns: { xs: "1fr", md: "repeat(auto-fit, minmax(240px, 1fr))", xl: "1fr" },
                  }}
                >
                  {selectedSnapshotMetrics.map(({ definition, metric }) => (
                    <Card key={definition.key} variant="outlined" sx={{ borderColor: "grey.200" }}>
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
                </Box>

                <Divider />

                <ConfusionMatrixCard data={confusionMatrix} loading={confusionMatrixLoading} />
              </Stack>
            </CardContent>
          </Card>
        </Box>
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
