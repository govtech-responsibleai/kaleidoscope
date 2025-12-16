"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  MenuItem,
  Select,
  Stack,
  Typography,
  useTheme
} from "@mui/material";
import * as d3 from "d3";
import { SnapshotMetric } from "@/lib/types";

interface SnapshotAccuracyChartProps {
  data: SnapshotMetric[];
  loading: boolean;
}

export default function SnapshotAccuracyChart({
  data,
  loading,
}: SnapshotAccuracyChartProps) {
  const theme = useTheme();
  const svgRef = useRef<SVGSVGElement>(null);
  const [metric, setMetric] = useState<string>("accuracy");

  useEffect(() => {
    if (!svgRef.current || data.length === 0 || loading) return;

    // Clear previous chart
    d3.select(svgRef.current).selectAll("*").remove();

    // Chart dimensions
    const margin = { top: 20, right: 30, bottom: 60, left: 60 };
    const containerWidth = svgRef.current.clientWidth || 600;
    const containerHeight = 250;
    const width = containerWidth - margin.left - margin.right;
    const height = containerHeight - margin.top - margin.bottom;

    // Create SVG
    const svg = d3
      .select(svgRef.current)
      .attr("width", containerWidth)
      .attr("height", containerHeight)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Scales
    const x = d3
      .scaleBand()
      .domain(data.map((d) => d.snapshot_name))
      .range([0, width])
      .padding(0.3);

    const y = d3
      .scaleLinear()
      .domain([0, 1]) // 0-100% range
      .range([height, 0]);

    // X-axis
    svg
      .append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .attr("transform", "rotate(-45)")
      .style("text-anchor", "end")
      .style("font-size", "12px");

    // Y-axis with percentage formatting
    svg
      .append("g")
      .call(
        d3
          .axisLeft(y)
          .tickFormat((d) => `${(Number(d) * 100).toFixed(0)}%`)
      )
      .style("font-size", "12px");

    // Y-axis label
    svg
      .append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", 0 - margin.left)
      .attr("x", 0 - height / 2)
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .style("font-size", "14px")
      .style("fill", "#666")
      .text("Accuracy (%)");

    // Tooltip
    const tooltip = d3
      .select("body")
      .append("div")
      .style("position", "absolute")
      .style("background", "rgba(0, 0, 0, 0.8)")
      .style("color", "#fff")
      .style("padding", "8px 12px")
      .style("border-radius", "4px")
      .style("font-size", "12px")
      .style("pointer-events", "none")
      .style("opacity", 0)
      .style("z-index", 10000);

    // Bars
    svg
      .selectAll(".bar")
      .data(data)
      .enter()
      .append("rect")
      .attr("class", "bar")
      .attr("x", (d) => x(d.snapshot_name) || 0)
      .attr("y", (d) => y(d.aggregated_accuracy))
      .attr("width", x.bandwidth())
      .attr("height", (d) => height - y(d.aggregated_accuracy))
      .attr("fill", theme.palette.primary.main)
      .attr("rx", 4)
      .on("mouseover", (event, d) => {
        tooltip.transition().duration(200).style("opacity", 1);
        tooltip
          .html(
            `
            <strong>${d.snapshot_name}</strong><br/>
            Accuracy: ${(d.aggregated_accuracy * 100).toFixed(1)}%<br/>
            Total Answers: ${d.total_answers}
          `
          )
          .style("left", event.pageX + 10 + "px")
          .style("top", event.pageY - 28 + "px");

        d3.select(event.currentTarget).attr("fill", "#1565c0");
      })
      .on("mouseout", (event) => {
        tooltip.transition().duration(200).style("opacity", 0);
        d3.select(event.currentTarget).attr("fill", "#1976d2");
      });

    // Cleanup tooltip on component unmount
    return () => {
      tooltip.remove();
    };
  }, [data, loading]);

  return (
    <Card variant="outlined" sx={{ width: "65%", height: "100%" }}>
      <CardContent>
        <Stack direction="row" alignContent="center" justifyContent="space-between">
          <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
            Target Performance over Snapshots
          </Typography>
          <Select
            value={metric}
            onChange={(e) => {
              setMetric(e.target.value);
            }}
            size="small"
            disabled={data.length === 0}
          >
            <MenuItem value={"accuracy"}>Accuracy</MenuItem>
          </Select>
        </Stack>

        {loading ? (
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            minHeight="150px"
          >
            <CircularProgress />
          </Box>
        ) : data.length === 0 ? (
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            minHeight="150px"
          >
            <Typography variant="body2" color="text.secondary">
              No snapshots available
            </Typography>
          </Box>
        ) : (
          <svg ref={svgRef} style={{ width: "100%" }} />
        )}
      </CardContent>
    </Card>
  );
}
