#!/usr/bin/env python3
"""
likwid-roofline

Copyright (c) 2025 Omar Awile
Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
"""
import argparse
import os
import yaml

from roofline import (
    extract_kernel_performance,
    roofline_plot,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a roofline plot from LIKWID CSV metrics."
    )
    parser.add_argument(
        "metrics_yaml",
        help="YAML file with roofline peak metrics (flops_metrics and mem_metrics).",
    )
    parser.add_argument(
        "-f",
        "--flops",
        required=True,
        help="Path to LIKWID CSV file containing FLOPs metrics.",
    )
    parser.add_argument(
        "-m",
        "--mem",
        required=True,
        help="Path to LIKWID CSV file containing memory (bytes) metrics.",
    )
    parser.add_argument(
        "-w",
        "--workload",
        required=True,
        type=str,
        help="Name of workload to use in plot title",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="roofline.png",
        help="Output file path for the generated roofline plot (default: roofline.png).",
    )
    return parser.parse_args()


def _normalize_unit_to_gflops(value, unit):
    if unit is None:
        return float(value)
    u = str(unit).strip().lower()
    # Accept common variants
    if u in ("mflops", "mf/s", "mflo/s", "mflop/s"):
        factor = 0.001
    elif u in ("gflops", "gf/s", "gflo/s", "gflop/s"):
        factor = 1.0
    elif u in ("tflops", "tf/s", "tflo/s", "tflop/s"):
        factor = 1_000.0
    elif u in ("pflops", "pf/s", "pflo/s", "pflop/s"):
        factor = 1_000_000.0
    else:
        # Fallback: assume value is already GFLOPS
        factor = 1.0
    return float(value) * factor


def _normalize_unit_to_gbps(value, unit):
    if unit is None:
        return float(value)
    u = str(unit).strip().lower()
    if u in ("mb/s", "mbytes/s", "mbyte/s", "mbs"):
        factor = 0.001
    elif u in ("gb/s", "gbytes/s", "gbyte/s", "gbs"):
        factor = 1.0
    elif u in ("tb/s", "tbytes/s", "tbyte/s", "tbs"):
        factor = 1_000.0
    elif u in ("pb/s", "pbytes/s", "pbyte/s", "pbs"):
        factor = 1_000_000.0
    else:
        # Fallback: assume value is already GB/s
        factor = 1.0
    return float(value) * factor


def parse_metrics_yaml(filepath):
    with open(filepath, "r") as f:
        data = yaml.safe_load(f) or {}

    system_name = data.get("system_name", "") or ""
    # Expect top-level keys: flops_metrics and mem_metrics
    flops = data.get("flops_metrics", {}) or {}
    mem = data.get("mem_metrics", {}) or {}

    # Normalize into a dictionary keyed by short metric names with normalized units
    norm_flops = {}
    for key, meta in flops.items():
        metric_name = (meta or {}).get("metric-name", key)
        value = (meta or {}).get("value", 0.0)
        unit = (meta or {}).get("unit", "GFLOPS")
        norm_flops[key] = {
            "metric-name": metric_name,
            "value": _normalize_unit_to_gflops(value, unit),
            "unit": "GFLOPS",
        }

    norm_mem = {}
    for key, meta in mem.items():
        metric_name = (meta or {}).get("metric-name", key)
        value = (meta or {}).get("value", 0.0)
        unit = (meta or {}).get("unit", "GB/s")
        norm_mem[key] = {
            "metric-name": metric_name,
            "value": _normalize_unit_to_gbps(value, unit),
            "unit": "GB/s",
        }

    return {
        "system_name": system_name,
        "flops_metrics": norm_flops,
        "mem_metrics": norm_mem,
    }


def main():
    args = parse_args()

    # Load metrics from YAML and normalize units
    metrics = parse_metrics_yaml(args.metrics_yaml)

    # Parse input CSVs into DataFrames
    roof_df = extract_kernel_performance(args.flps, args.mem)

    # Drop rows missing required fields for plotting
    required_cols = ["FLOP/Byte", "SP [GFLOP/s]", "Runtime [s]"]
    roof_df = roof_df.dropna(subset=[c for c in required_cols if c in roof_df])

    # Ensure index starts at 1 to match roofline_plot's label indexing
    roof_df = roof_df.reset_index(drop=True)
    roof_df.index = roof_df.index + 1

    title = f"{args.workload} on {metrics.get('system_name', '')}"

    # Generate and save the roofline plot using metrics from YAML
    fig = roofline_plot(
        roof_df,
        metrics=metrics,
        title=title,
        caption=None,
    )
    # Save figure to file if requested (default: "roofline.png")
    if args.output:
        fig.savefig(args.output, dpi=150, bbox_inches="tight")
        print(f"Saved roofline plot to {args.output}")
    else:
        fig.display()


if __name__ == "__main__":
    main()
