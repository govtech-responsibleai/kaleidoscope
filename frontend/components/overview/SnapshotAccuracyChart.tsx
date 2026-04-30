"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import * as d3 from "d3";

export interface SnapshotScoreSeriesValue {
  key: string;
  label: string;
  color: string;
  value: number | null;
  totalAnswers?: number | null;
}

export interface SnapshotScoreSeriesPoint {
  snapshotId: number;
  snapshotName: string;
  series: SnapshotScoreSeriesValue[];
}

interface SnapshotScoreChartProps {
  data: SnapshotScoreSeriesPoint[];
  loading: boolean;
  title?: string;
  "data-testid"?: string;
}

export default function SnapshotScoreChart({
  data,
  loading,
  title,
  "data-testid": testId,
}: SnapshotScoreChartProps) {
  const theme = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [availableWidth, setAvailableWidth] = useState(0);

  const legendItems = useMemo(() => data[0]?.series ?? [], [data]);
  const requiredChartWidth = useMemo(() => {
    const snapshotCount = Math.max(data.length, 1);
    const metricCount = Math.max(legendItems.length, 1);
    const groupWidth = Math.max(150, metricCount * 52);
    return Math.max(640, snapshotCount * groupWidth);
  }, [data.length, legendItems.length]);

  useEffect(() => {
    if (!containerRef.current) return;

    const updateWidth = () => {
      setAvailableWidth(containerRef.current?.clientWidth ?? 0);
    };

    updateWidth();

    const observer = new ResizeObserver(() => {
      updateWidth();
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [data.length, loading]);

  useEffect(() => {
    if (!svgRef.current || data.length === 0 || loading) return;

    d3.select(svgRef.current).selectAll("*").remove();

    const margin = { top: 28, right: 24, bottom: 72, left: 60 };
    const chartWidth = Math.max(availableWidth || 0, requiredChartWidth);
    const containerWidth = chartWidth || 700;
    const containerHeight = 360;
    const width = containerWidth - margin.left - margin.right;
    const height = containerHeight - margin.top - margin.bottom;

    const svg = d3
      .select(svgRef.current)
      .attr("width", containerWidth)
      .attr("height", containerHeight)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const x0 = d3
      .scaleBand()
      .domain(data.map((d) => d.snapshotName))
      .range([0, width])
      .padding(0.24);

    const metricKeys = legendItems.map((item) => item.key);
    const x1 = d3
      .scaleBand()
      .domain(metricKeys)
      .range([0, x0.bandwidth()])
      .padding(0.16);

    const y = d3.scaleLinear().domain([0, 1]).range([height, 0]);

    svg
      .append("g")
      .call(
        d3
          .axisLeft(y)
          .tickSize(-width)
          .tickFormat((d) => `${(Number(d) * 100).toFixed(0)}%`)
      )
      .call((g) => g.select(".domain").remove())
      .call((g) => g.selectAll(".tick line").attr("stroke", theme.palette.divider))
      .call((g) => g.selectAll(".tick text").attr("fill", theme.palette.text.secondary).style("font-size", "12px"));

    svg
      .append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(x0))
      .call((g) => g.select(".domain").attr("stroke", theme.palette.divider))
      .call((g) =>
        g
          .selectAll("text")
          .attr("transform", "rotate(-28)")
          .style("text-anchor", "end")
          .attr("fill", theme.palette.text.secondary)
          .style("font-size", "12px")
      );

    svg
      .append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", -44)
      .attr("x", -height / 2)
      .attr("fill", theme.palette.text.secondary)
      .style("text-anchor", "middle")
      .style("font-size", "12px")
      .text("Score");

    const tooltip = d3
      .select("body")
      .append("div")
      .style("position", "absolute")
      .style("background", "rgba(18, 22, 40, 0.94)")
      .style("color", "#fff")
      .style("padding", "10px 12px")
      .style("border-radius", "10px")
      .style("font-size", "12px")
      .style("line-height", "1.4")
      .style("pointer-events", "none")
      .style("opacity", 0)
      .style("z-index", 10000);

    const groups = svg
      .selectAll("g.snapshot-group")
      .data(data)
      .enter()
      .append("g")
      .attr("class", "snapshot-group")
      .attr("transform", (d) => `translate(${x0(d.snapshotName) ?? 0},0)`);

    groups
      .selectAll("rect.metric-bar")
      .data((d) => d.series.map((metric) => ({ ...metric, snapshotName: d.snapshotName })))
      .enter()
      .filter((d) => d.value !== null)
      .append("rect")
      .attr("class", "metric-bar")
      .attr("x", (d) => x1(d.key) ?? 0)
      .attr("y", (d) => y(d.value ?? 0))
      .attr("width", x1.bandwidth())
      .attr("height", (d) => height - y(d.value ?? 0))
      .attr("fill", (d) => d.color)
      .attr("rx", 6)
      .on("mouseover", (event, d) => {
        tooltip.transition().duration(150).style("opacity", 1);
        tooltip
          .html(
            `<strong>${d.snapshotName}</strong><br/>${d.label}: ${((d.value ?? 0) * 100).toFixed(1)}%${
              d.totalAnswers ? `<br/>Answers: ${d.totalAnswers}` : ""
            }`
          )
          .style("left", `${event.pageX + 12}px`)
          .style("top", `${event.pageY - 28}px`);
      })
      .on("mouseout", () => {
        tooltip.transition().duration(150).style("opacity", 0);
      });

    groups
      .selectAll("text.metric-empty")
      .data((d) => d.series.map((metric) => ({ ...metric })))
      .enter()
      .filter((d) => d.value === null)
      .append("text")
      .attr("x", (d) => (x1(d.key) ?? 0) + x1.bandwidth() / 2)
      .attr("y", height - 6)
      .attr("text-anchor", "middle")
      .attr("fill", theme.palette.text.disabled)
      .style("font-size", "11px")
      .text("—");

    return () => {
      tooltip.remove();
    };
  }, [availableWidth, data, loading, legendItems, requiredChartWidth, theme]);

  return (
    <Card
      data-testid={testId}
      variant="outlined"
      sx={{
        width: "100%",
        minHeight: 440,
        borderColor: "grey.200",
        bgcolor: "background.paper",
      }}
    >
      <CardContent sx={{ p: 3 }}>
        <Stack spacing={2}>
          {title && (
            <Box>
              <Typography variant="h5" fontWeight={700}>
                {title}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                Compare selected metrics across snapshots in one view.
              </Typography>
            </Box>
          )}

          {legendItems.length > 0 && (
            <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
              {legendItems.map((item) => (
                <Stack
                  key={item.key}
                  direction="row"
                  spacing={1}
                  alignItems="center"
                  sx={{
                    px: 1.25,
                    py: 0.75,
                    borderRadius: 999,
                    bgcolor: "grey.50",
                    border: "1px solid",
                    borderColor: "grey.200",
                  }}
                >
                  <Box
                    sx={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      bgcolor: item.color,
                    }}
                  />
                  <Typography variant="caption" fontWeight={700} color="text.secondary">
                    {item.label}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          )}

          {loading ? (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="220px">
              <CircularProgress />
            </Box>
          ) : data.length === 0 ? (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="220px">
              <Typography variant="body2" color="text.secondary">
                No snapshots available
              </Typography>
            </Box>
          ) : (
            <Box
              ref={containerRef}
              sx={{
                width: "100%",
                overflowX: "auto",
                overflowY: "hidden",
                pb: 1,
              }}
            >
              <Box sx={{ width: Math.max(availableWidth || 0, requiredChartWidth) }}>
                <svg
                  ref={svgRef}
                  style={{
                    width: Math.max(availableWidth || 0, requiredChartWidth),
                    height: "100%",
                    display: "block",
                  }}
                />
              </Box>
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
