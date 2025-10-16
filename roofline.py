"""
likwid-roofline

Copyright (c) 2025 Omar Awile
Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
"""
import csv
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from adjustText import adjust_text


def extract_flops_from_likwid_csv(filepath):
    # Collect all regions and stats of interest
    results = {}

    with open(filepath, "r") as f:
        reader = csv.reader(f)
        current_region = None
        current_table = None
        for row in reader:
            if row and row[0].startswith("TABLE"):
                # Table header: figure out the current region & table type
                current_region = row[1].replace("Region ", "").strip()
                current_table = row[2].strip()
            elif (
                current_table == "Group 1 Raw STAT"
                and row
                and row[0]
                in [
                    "RETIRED_SSE_AVX_FLOPS_ALL_SP_SCALAR STAT",
                    "RETIRED_SSE_AVX_FLOPS_ALL_SP_PACKED STAT",
                ]
            ):
                # Parse raw STAT relevant statistics for region
                sum_value = float(row[2])  # assuming the third column is Sum
                results.setdefault(current_region, {}).setdefault("SP FLOPs", 0)
                results[current_region]["SP FLOPs"] += sum_value
            elif (
                current_table == "Group 1 Raw STAT"
                and row
                and row[0]
                in [
                    "RETIRED_SSE_AVX_FLOPS_ALL_DP_SCALAR STAT",
                    "RETIRED_SSE_AVX_FLOPS_ALL_DP_PACKED STAT",
                ]
            ):
                # Parse raw STAT relevant statistics for region
                sum_value = float(row[2])  # assuming the third column is Sum
                results.setdefault(current_region, {}).setdefault("DP FLOPs", 0)
                results[current_region]["DP FLOPs"] += sum_value
            elif (
                current_table == "Group 1 Metric STAT"
                and row
                and row[0] == "SP [MFLOP/s] STAT"
            ):
                # Parse Metric STAT (Sum is in second col)
                sum_value = float(row[1]) / 1000.0
                results.setdefault(current_region, {})["SP [GFLOP/s]"] = sum_value
            elif (
                current_table == "Group 1 Metric STAT"
                and row
                and row[0] == "DP [MFLOP/s] STAT"
            ):
                # Parse Metric STAT (Sum is in second col)
                sum_value = float(row[1]) / 1000.0
                results.setdefault(current_region, {})["DP [GFLOP/s]"] = sum_value
            elif (
                current_table == "Group 1 Metric STAT"
                and row
                and row[0] == "Runtime (RDTSC) [s] STAT"
            ):
                # Parse Metric STAT of runtime (Sum is in second col)
                sum_value = float(row[1])
                results.setdefault(current_region, {})["Runtime [s]"] = sum_value

    # Now results is a dict: region -> {raw_sum, mflops_sum}
    flops = pd.DataFrame.from_dict(results, orient="index")
    flops.reset_index(inplace=True)
    flops.rename(columns={"index": "region"}, inplace=True)
    return flops


def extract_mem_from_likwid_csv(filepath):
    # Collect all regions and stats of interest
    results = {}

    with open(filepath, "r") as f:
        reader = csv.reader(f)
        current_region = None
        current_table = None
        for row in reader:
            if row and row[0].startswith("TABLE"):
                # Table header: figure out the current region & table type
                current_region = row[1].replace("Region ", "").strip()
                current_table = row[2].strip()
            elif (
                current_table == "Group 1 Raw STAT"
                and row
                and row[0] == "CAS_CMD_ANY STAT"
            ):
                # Parse raw STAT relevant statistics for region
                sum_value = float(row[2]) * 64.0  # assuming the third column is Sum
                results.setdefault(current_region, {}).setdefault("Bytes", 0)
                results[current_region]["Bytes"] += sum_value

    # Now results is a dict: region -> {raw_sum, mflops_sum}
    mem = pd.DataFrame.from_dict(results, orient="index")
    mem.reset_index(inplace=True)
    mem.rename(columns={"index": "region"}, inplace=True)
    return mem


def extract_kernel_performance(flops_csv, mem_csv):
    flops_df = extract_flops_from_likwid_csv(flops_csv)
    mem_df = extract_mem_from_likwid_csv(mem_csv)

    roof_df = flops_df.join(mem_df.set_index('region'), on='region')
    # Filter out kernels that are not interesting or will cause problems
    roof_df = roof_df[roof_df["SP FLOPs"] > 0]
    roof_df = roof_df[roof_df["Bytes"] > 0]

    roof_df['FLOP/Byte'] = roof_df['SP FLOPs']/roof_df['Bytes']
    return roof_df


def _bw_labels(ax, ai_vals, bw, label):
    xy_pix1 = ax.transData.transform((ai_vals[10], ai_vals[10] * bw))
    xy_pix2 = ax.transData.transform((ai_vals[11], ai_vals[11] * bw))
    dx_pix = xy_pix2[0] - xy_pix1[0]
    dy_pix = xy_pix2[1] - xy_pix1[1]
    text_rot = np.degrees(np.arctan2(dy_pix, dx_pix))
    ax.text(
        ai_vals[10],
        ai_vals[10] * bw,
        f"{bw:.0f} GB/s {label}",
        ha="left",
        va="bottom",
        rotation=text_rot,
        rotation_mode="anchor",
        color="gray",
    )


def roofline_plot(roofline_df, metrics, title, caption=None):
    # Derive peak metrics from the provided metrics dictionary
    system_name = (metrics or {}).get("system_name", "") or ""
    flops_metrics = (metrics or {}).get("flops_metrics", {}) or {}
    mem_metrics = (metrics or {}).get("mem_metrics", {}) or {}

    # Collect compute ceilings GFLOPS and memory bandwidths (GB/s)
    compute_ceilings = []
    for key, meta in flops_metrics.items():
        name = meta.get("metric-name", str(key))
        val = float(meta.get("value", 0.0))
        if val > 0:
            compute_ceilings.append((name, val))
    if not compute_ceilings:
        raise Error("No peak floating-point performance metric provied")

    memory_roofs = []
    for key, meta in mem_metrics.items():
        name = meta.get("metric-name", str(key))
        val = float(meta.get("value", 0.0))
        if val > 0:
            memory_roofs.append((name, val))
    if not memory_roofs:
        raise Error("No memory bandwidth metric provied")

    # Peak compute to cap memory roofs
    peak_compute = max(val for _, val in compute_ceilings)

    # X range for roofline plot
    # Determine arithmetic-intensity bounds from data and roofs
    if "FLOP/Byte" in roofline_df and not roofline_df["FLOP/Byte"].empty:
        data_xmin = max(min(roofline_df["FLOP/Byte"].min(), 0.01), 1e-4)
        data_xmax = max(roofline_df["FLOP/Byte"].max(), 10.0)
    else:
        data_xmin = 0.01
        data_xmax = 10.0

    min_bw = min(bw for _, bw in memory_roofs)
    roofs_xmax = peak_compute / max(min_bw, 1e-6) * 10.0

    xmin = min(data_xmin, 0.01)
    xmax = max(data_xmax, roofs_xmax)

    ai_vals = np.logspace(np.log10(xmin), np.log10(xmax), 400)

    # Plot roofline
    fig, ax = plt.subplots(figsize=(10, 7))

    # Plot each memory roof (slanted lines) capped by peak compute
    for name, bw in memory_roofs:
        y = np.minimum(peak_compute, bw * ai_vals)
        ax.plot(ai_vals, y, linewidth=2, label=f"{name} ({bw:.0f} GB/s)")

    # Plot compute ceilings (horizontal lines)
    for name, gflops in compute_ceilings:
        ax.hlines(
            gflops,
            xmin,
            xmax,
            colors="gray",
            linestyles="dashed",
            linewidth=1.5,
            label=f"{name} ({gflops:.0f} GFLOP/s)",
        )
        ax.text(
            1.0, gflops * 1.1, f"{gflops:.0f} GFLOP/s {name}", ha="left", color="gray"
        )

    # Plot measured data points
    region_labels = []
    if all(col in roofline_df for col in ["FLOP/Byte", "SP [GFLOP/s]", "Runtime [s]"]):
        ax.scatter(
            roofline_df["FLOP/Byte"],
            roofline_df["SP [GFLOP/s]"],
            s=roofline_df["Runtime [s]"],
            color="green",
            label="Measured Regions",
        )
        for region, row in roofline_df.iterrows():
            region_str = roofline_df.iloc[region - 1]["region"]
            lbl = ax.text(
                row["FLOP/Byte"] * 1.1,
                row["SP [GFLOP/s]"] * 1.1,
                region_str,
                fontsize=9,
                ha="left",
                va="bottom",
            )
            region_labels.append(lbl)

    # Axes scaling and limits
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim([xmin, xmax])
    ax.set_ylim([0.1, peak_compute * 1.5])

    # Improve label placement
    if region_labels:
        adjust_text(
            region_labels,
            target_x=roofline_df["FLOP/Byte"],
            target_y=roofline_df["SP [GFLOP/s]"],
        )

    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: "{:g}".format(y)))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: "{:g}".format(y)))

    for label, bw in memory_roofs:
        _bw_labels(ax, ai_vals, bw, label)

    ax.set_xlabel("Arithmetic Intensity (FLOPs/Byte)")
    ax.set_ylabel("Performance (GFLOPS/s)")
    ax.set_title(f"Roofline Plot: {title}")
    if caption:
        fig.text(0.0, -0.01, caption, wrap=True, ha="left", va="top", fontsize=12)

    ax.grid(True, which="both", linestyle="--", linewidth=0.5)

    return fig
