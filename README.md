# LIKWID roofline

![an example Roofline plot](https://github.com/ohm314/likwid-roofline/blob/21872c49c5f959e23e0d250e143d1048cde22b69/example_roofline.png)

A very simple utility to draw roofline plots from [LIKWID](https://github.com/RRZE-HPC/likwid) profiling data.

I suggest following this workflow:

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

## Caveats

* While the code does read in double-precision peaks and regions, they are not properly handled in
  the plotting function
* Some of the limits in the plotting function are hard-coded for simplicity sake, if you find you're
  missing some data points in the plot, you may want to check the x- and y-axis limits.
* I assume the performance data was collected with the LIKWID metric groups from around version
  5.4.1 and on an Intel architecture, the metric names might differ in other versions or hardware
  platforms
* This code is not thoroughly tested. It works for me and I hope it's useful to someone else out
  there, but I can't guarantee it. I'm happy to take suggestions for improvement and fixes!

## Thanks

I'd like to shout out big thank you to the tireless work of the open source community and in particular 
to the authors of LIKWID!

## License

Copyright (c) 2025 Omar Awile
Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
