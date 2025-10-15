import csv
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from adjustText import adjust_text


def extract_flops_from_likwid_csv(filepath):
    # Collect all regions and stats of interest
    results = {}
    
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        current_region = None
        current_table = None
        for row in reader:
            if row and row[0].startswith('TABLE'):
                # Table header: figure out the current region & table type
                current_region = row[1].replace('Region ', '').strip()
                current_table = row[2].strip()
            elif current_table == 'Group 1 Raw STAT' and row and row[0] in [
                    'RETIRED_SSE_AVX_FLOPS_ALL_SP_SCALAR STAT',
                    'RETIRED_SSE_AVX_FLOPS_ALL_SP_PACKED STAT']:
                # Parse raw STAT relevant statistics for region
                sum_value = float(row[2])   # assuming the third column is Sum
                results.setdefault(current_region, {}).setdefault('SP FLOPs', 0)
                results[current_region]['SP FLOPs'] += sum_value
            elif current_table == 'Group 1 Metric STAT' and row and row[0] == 'SP [MFLOP/s] STAT':
                # Parse Metric STAT (Sum is in second col)
                sum_value = float(row[1])/1000.
                results.setdefault(current_region, {})['SP [GFLOP/s]'] = sum_value
            elif current_table == 'Group 1 Metric STAT' and row and row[0] =='Runtime (RDTSC) [s] STAT':
                # Parse Metric STAT of runtime (Sum is in second col)
                sum_value = float(row[1])
                results.setdefault(current_region, {})['Runtime [s]'] = sum_value
    
    # Now results is a dict: region -> {raw_sum, mflops_sum}
    flops = pd.DataFrame.from_dict(results, orient='index')
    flops.reset_index(inplace=True)
    flops.rename(columns={'index': 'region'}, inplace=True)
    return flops


def extract_mem_from_likwid_csv(filepath):
    # Collect all regions and stats of interest
    results = {}
    
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        current_region = None
        current_table = None
        for row in reader:
            if row and row[0].startswith('TABLE'):
                # Table header: figure out the current region & table type
                current_region = row[1].replace('Region ', '').strip()
                current_table = row[2].strip()
            elif current_table == 'Group 1 Raw STAT' and row and row[0] == 'CAS_CMD_ANY STAT':
                # Parse raw STAT relevant statistics for region
                sum_value = float(row[2])*64.0   # assuming the third column is Sum
                results.setdefault(current_region, {}).setdefault('Bytes', 0)
                results[current_region]['Bytes'] += sum_value
    
    # Now results is a dict: region -> {raw_sum, mflops_sum}
    mem = pd.DataFrame.from_dict(results, orient='index')
    mem.reset_index(inplace=True)
    mem.rename(columns={'index': 'region'}, inplace=True)
    return mem


# update to save the figure into a file instead of showing it, ai!
def roofline_plot(roofline_df, peak_bandwidth, peak_gflops, peak_l3_bandwidth, title, caption=None):

    # Roofline function
    def roofline_l3(ai):
        return np.minimum(peak_gflops, peak_l3_bandwidth * ai)
    def roofline(ai):
        return np.minimum(peak_gflops, peak_bandwidth * ai)
    
    # X range for roofline plot
    xmin = min(roofline_df["FLOP/Byte"].min(), 0.01)
    xmax_l3 = max(roofline_df["FLOP/Byte"].max(), peak_gflops / peak_l3_bandwidth * 10)
    xmax = max(roofline_df["FLOP/Byte"].max(), peak_gflops / peak_bandwidth * 10)
    ai_vals_l3 = np.logspace(np.log10(xmin), np.log10(xmax_l3), 200)
    ai_vals = np.logspace(np.log10(xmin), np.log10(xmax), 200)
    
    # Plot roofline
    fig, ax = plt.subplots(figsize=(10,7))
    ax.plot(ai_vals_l3, roofline_l3(ai_vals_l3), label="Roofline", color="blue", linewidth=2)
    ax.plot(ai_vals, roofline(ai_vals), label="Roofline", color="red", linewidth=2)
    
    # Plot ceiling lines
    ax.hlines(peak_gflops, xmin, xmax, colors="gray", linestyles="dashed", label=f"Peak FLOPS ({peak_gflops} GFLOPS/s)")
    ax.text(peak_gflops/peak_l3_bandwidth, peak_gflops*1.1, f'{peak_gflops:.0f} GFLOP/s peak SP', ha="center", color="gray")
    
    ax.vlines(peak_gflops/peak_l3_bandwidth, ymin=0.1, ymax=peak_gflops, colors="gray", linestyles="dotted")
    ax.vlines(peak_gflops/peak_bandwidth, ymin=0.1, ymax=peak_gflops, colors="gray", linestyles="dotted")
    #plt.hlines(peak_bandwidth * xmin, xmin, peak_gflops/peak_bandwidth, color="gray", linestyle="dotted")
    #plt.text(xmin*1.5, peak_bandwidth*xmin*1.1, "Memory Bound", ha="left", color="gray")

    
    region_labels = []
    # Plot measured data points
    ax.scatter(roofline_df["FLOP/Byte"], roofline_df["SP [GFLOP/s]"], s=roofline_df["Runtime [s]"], color="green", label="Measured Regions")
    for region, row in roofline_df.iterrows():
        region_str = roofline_df.iloc[region-1]['region']
        lbl = ax.text(row["FLOP/Byte"]*1.1, row["SP [GFLOP/s]"]*1.1, region_str, fontsize=9, ha="left", va="bottom")
        region_labels.append(lbl)

    
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim([xmin, xmax])
    ax.set_ylim([0.1, peak_gflops*1.5])

    xy_pix1 = ax.transData.transform((ai_vals_l3[10], roofline_l3(ai_vals_l3[10])))
    xy_pix2 = ax.transData.transform((ai_vals_l3[11], roofline_l3(ai_vals_l3[11])))
    dx_pix = xy_pix2[0] - xy_pix1[0]
    dy_pix = xy_pix2[1] - xy_pix1[1]
    text_rot = np.degrees(np.arctan2(dy_pix, dx_pix))
    ax.text(ai_vals_l3[10], roofline_l3(ai_vals_l3[10]), f'{peak_l3_bandwidth:.0f} GB/s L3 Bandwidth', 
             ha="left", va="bottom", rotation=text_rot, rotation_mode='anchor', color="gray")
    ax.text(ai_vals[10], roofline(ai_vals[10]), f'{peak_bandwidth:.0f} GB/s DDR Bandwidth', 
             ha="left", va="bottom", rotation=text_rot, rotation_mode='anchor', color="gray")

    adjust_text(region_labels, target_x=roofline_df["FLOP/Byte"], target_y=roofline_df["SP [GFLOP/s]"])
    
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: '{:g}'.format(y)))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: '{:g}'.format(y)))
    
    ax.set_xlabel('Arithmetic Intensity (FLOPs/Byte)')
    ax.set_ylabel('Performance (GFLOPS/s)')
    ax.set_title(f'Roofline Plot: {title}')
    if caption:
        fig.text(0.0, -0.01, caption, wrap=True, ha='left', va='top', fontsize=12)
    #plt.legend(loc="lower right")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)
    #fig.tight_layout()
    return fig
