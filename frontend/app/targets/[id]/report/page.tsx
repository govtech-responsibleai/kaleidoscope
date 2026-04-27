"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  IconDownload,
  IconMessageQuestion,
  IconRobotFace,
  IconScreenshot,
  IconUser,
} from "@tabler/icons-react";
import { useParams } from "next/navigation";
import { orderRubricsForDisplay } from "@/app/targets/[id]/rubrics";
import { targetApi, snapshotApi, judgeApi, metricsApi, targetRubricApi } from "@/lib/api";
import { TargetResponse, TargetStats, SnapshotMetric, Snapshot, TargetRubricResponse } from "@/lib/types";
import SnapshotScoreChart, {
  type SnapshotScoreSeriesPoint,
} from "@/components/overview/SnapshotAccuracyChart";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import { actionIconProps, statIconProps } from "@/lib/styles";

type RubricSeriesDefinition = {
  key: string;
  label: string;
  color: string;
  rubricId: number;
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
  const [downloading, setDownloading] = useState(false);
  const [selectedSeriesKeys, setSelectedSeriesKeys] = useState<string[]>([]);
  const [seriesMenuAnchor, setSeriesMenuAnchor] = useState<null | HTMLElement>(null);
  const previousSeriesKeysRef = useRef<string[]>([]);

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

  const rubricSeriesDefinitions = useMemo<RubricSeriesDefinition[]>(() => {
    return orderRubricsForDisplay(rubrics).map((rubric, index) => ({
      key: `rubric-${rubric.id}`,
      label: rubric.name,
      color: metricColors[index % metricColors.length],
      rubricId: rubric.id,
    }));
  }, [metricColors, rubrics]);

  const selectedSeries = useMemo(
    () =>
      selectedSeriesKeys
        .map((key) => rubricSeriesDefinitions.find((definition) => definition.key === key))
        .filter((definition): definition is RubricSeriesDefinition => Boolean(definition)),
    [rubricSeriesDefinitions, selectedSeriesKeys]
  );

  const fetchData = useCallback(async () => {
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
      setSnapshotMetrics((metricsRes.data.rubrics ?? []).flatMap((rubricGroup) => rubricGroup.snapshots));
      setRubrics(rubricsRes.data ?? []);

      const judgeResponses = await Promise.all(
        (rubricsRes.data ?? []).map((rubric) => judgeApi.getForRubric(rubric.id, targetId))
      );
      const uniqueJudgeIds = new Set<number>();
      judgeResponses.forEach((response) => {
        response.data.forEach((judge) => uniqueJudgeIds.add(judge.id));
      });
      setJudgeCount(uniqueJudgeIds.size);

    } catch (error) {
      console.error("Failed to fetch target data:", error);
    } finally {
      setLoading(false);
      setMetricsLoading(false);
    }
  }, [targetId]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  useEffect(() => {
    const seriesKeys = rubricSeriesDefinitions.map((definition) => definition.key);

    setSelectedSeriesKeys((current) => {
      const previousSeriesKeys = previousSeriesKeysRef.current;
      const validKeys = current.filter((key) => seriesKeys.includes(key));
      const hadFullPreviousSelection =
        previousSeriesKeys.length > 0 &&
        previousSeriesKeys.every((key) => current.includes(key));
      const hasNewSeriesKeys = seriesKeys.some((key) => !previousSeriesKeys.includes(key));

      let next: string[];
      if (validKeys.length === 0 && seriesKeys.length > 0) {
        next = seriesKeys;
      } else if (hadFullPreviousSelection && hasNewSeriesKeys) {
        next = seriesKeys;
      } else {
        next = validKeys;
      }

      previousSeriesKeysRef.current = seriesKeys;

      if (next.length === current.length && next.every((k, i) => k === current[i])) {
        return current;
      }
      return next;
    });
  }, [rubricSeriesDefinitions]);

  const sortedSnapshots = useMemo(
    () => [...snapshots].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
    [snapshots]
  );

  const chartData = useMemo<SnapshotScoreSeriesPoint[]>(() => {
    return sortedSnapshots.map((snapshot) => ({
      snapshotId: snapshot.id,
      snapshotName: snapshot.name,
      series: selectedSeries.map((definition) => {
        const metric = snapshotMetrics.find(
          (entry) => entry.snapshot_id === snapshot.id && entry.rubric_id === definition.rubricId
        ) ?? null;

        return {
          key: definition.key,
          label: definition.label,
          color: definition.color,
          value: metric?.aggregated_score ?? null,
          totalAnswers: metric?.total_answers ?? null,
        };
      }),
    }));
  }, [selectedSeries, snapshotMetrics, sortedSnapshots]);

  const toggleSeries = (key: string) => {
    setSelectedSeriesKeys((current) => {
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
          <Typography variant="h5" fontWeight={700}>
            Report
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 780 }}>
            Executive overview of evaluation coverage, snapshot performance, and judge-backed reliability signals.
          </Typography>
        </Box>

        <Tooltip title={downloading ? "Generating PDF..." : "Download as PDF"}>
          <span>
            <Button
              variant="contained"
              startIcon={
                downloading ? <CircularProgress size={20} color="inherit" /> : <IconDownload {...actionIconProps} />
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
                      Rubric Scores Across Snapshots
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      Compare rubric-level aggregate scores across every available snapshot in one grouped chart.
                    </Typography>
                  </Box>

                  <Button
                    variant="outlined"
                    endIcon={<IconChevronDown {...actionIconProps} />}
                    onClick={(event) => setSeriesMenuAnchor(event.currentTarget)}
                    sx={{ minWidth: { xs: "100%", sm: 220 }, justifyContent: "space-between", flexShrink: 0 }}
                  >
                    {selectedSeries.length === rubricSeriesDefinitions.length
                      ? `All rubrics (${selectedSeries.length})`
                      : selectedSeries.map((series) => series.label).join(" • ")}
                  </Button>

                  <Menu
                    anchorEl={seriesMenuAnchor}
                    open={Boolean(seriesMenuAnchor)}
                    onClose={() => setSeriesMenuAnchor(null)}
                  >
                    {rubricSeriesDefinitions.map((series) => (
                      <MenuItem key={series.key} onClick={() => toggleSeries(series.key)}>
                        <Checkbox checked={selectedSeriesKeys.includes(series.key)} />
                        <ListItemText
                          primary={series.label}
                          secondary={
                            selectedSeriesKeys.includes(series.key)
                              ? `Order ${selectedSeriesKeys.indexOf(series.key) + 1}`
                              : undefined
                          }
                        />
                      </MenuItem>
                    ))}
                  </Menu>
                </Stack>

                <SnapshotScoreChart
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
