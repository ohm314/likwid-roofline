# LIKWID roofline

A very simple utility to draw roofline plots from LIKWID profiling data.

We suggest following general workflow:

1. Setup likwid, make sure it is able to collect FLOPS and memory operations
2. Instrument your target workload with the LIKWID region marker API for all the kernels you think are
   relevant to your analysis
3. Build your code linking against the likwid marker library
4. Run your code once with the FLOPS and once with the MEM metric group, e.g.

```sh
likwid-perfctr -O -o roofline_data_flops.csv -m -g FLOPS_SP ./my_workload
likwid-perfctr -O -o roofline_data_mem.csv -m -g MEM ./my_workload
```

5. Benchmark your system to obtain memory bandwidth and peak FLOPS (for the desired precision). You
   can use benchmarks such as [STREAM](https://github.com/jeffhammond/STREAM) and
[cpufp](https://github.com/pigirons/cpufp) for this.
6. Prepare roofline metrics description file for your system (see `roofline_metrics_example.yaml`)
7. Now setup and run the plotting tool:

```sh
git clone https://github.com/ohm314/likwid-roofline && cd likwid-roofline
uv sync
uv run main.py roofline_metrics.yaml -f flops.csv -m mem.csv -w "my workload"
```
