#!/usr/bin/env python3
"""Draw every plot used in Summary.pdf from results/all_results.json.

Run run_all_experiments.py first. Plots are written to plots/.
The "Mean" group of a speedup plot is the geometric mean, all other metrics with the
arithmetic mean.
"""
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BASE_DIR, 'results', 'all_results.json')
PLOTS_DIR = os.path.join(BASE_DIR, 'plots')

TRACES = ['Trace1', 'Trace2', 'Trace3']
THRESHOLDS = ['0.15', '0.20', '0.25', '0.30', '0.35']
DYN = 'dyn_irrip_0.15'          # chosen threshold, used for Task 2B comparison and Task 3

# One fixed colour per configuration, used in every figure.
STYLE = {
    'baseline':      ('Baseline (no pref., LRU)', '#9a9a96'),
    'ip_stride':     ('IP-stride',                '#2a78d6'),
    'spp':           ('SPP',                      '#eb6834'),
    'irrip':         ('I-RRIP',                   '#2a78d6'),
    DYN:             ('Dynamic I-RRIP',           '#1baf7a'),
    'spp_dyn_irrip': ('SPP + Dynamic I-RRIP',     '#eda100'),
}
TRACE_COLORS = ['#2a78d6', '#eb6834', '#1baf7a']
INK = '#3d3d3a'
MUTED = '#8a8984'

plt.rcParams.update({
    'font.size': 8,
    'axes.edgecolor': '#c9c8c2',
    'axes.labelcolor': INK,
    'axes.titlesize': 9,
    'axes.titlecolor': INK,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.color': INK,
    'ytick.color': MUTED,
    'grid.color': '#e6e5e0',
    'grid.linewidth': 0.6,
    'legend.frameon': False,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
})


def metric(res, cfg, key):
    return [res[cfg][t].get(key, 0.0) for t in TRACES]


def with_mean(vals, geo=False):
    vals = list(vals)
    mean = float(np.exp(np.mean(np.log(vals)))) if geo else float(np.mean(vals))
    return vals + [mean]


def bars(ax, res, cfgs, key, title, ylabel, geo=False, ref=None, fmt='{:.2f}'):
    """Grouped bars: one group per trace plus a mean group; the mean group is
    labelled with its values so the headline numbers can be read directly."""
    groups = ['Trace 1', 'Trace 2', 'Trace 3', 'Mean']
    x = np.arange(len(groups))
    w = 0.8 / len(cfgs)
    for i, cfg in enumerate(cfgs):
        label, color = STYLE[cfg]
        vals = with_mean(metric(res, cfg, key), geo)
        pos = x - 0.4 + w * (i + 0.5)
        ax.bar(pos, vals, w, color=color, edgecolor='white', linewidth=0.8, label=label, zorder=2)
        ax.annotate(fmt.format(vals[-1]), (pos[-1], vals[-1]), xytext=(0, 2),
                    textcoords='offset points', ha='center', va='bottom',
                    fontsize=6, color=INK, rotation=90)
    if ref is not None:
        ax.axhline(ref, color=MUTED, linewidth=0.8, linestyle='--', zorder=1)
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis='y', zorder=0)
    ax.margins(y=0.18)


def speedup_axis(ax):
    # speedups are within a few percent of 1.0, so zoom in around it
    tops = [p.get_height() for p in ax.patches]
    ax.set_ylim(min(0.98, min(tops) - 0.005), max(tops) + 0.012)


def save(fig, name, handles_from):
    h, l = handles_from.get_legend_handles_labels()
    fig.legend(h, l, loc='upper center', ncol=len(l), bbox_to_anchor=(0.5, 1.04))
    fig.savefig(os.path.join(PLOTS_DIR, name))
    plt.close(fig)


def task1(res):
    cfgs = ['ip_stride', 'spp']
    specs = [
        ('task1_speedup.png', 'speedup', 'Speedup over baseline', 'IPC / baseline IPC', True, 1.0, '{:.3f}'),
        ('task1_accuracy.png', 'l1d_pref_accuracy', 'L1D prefetch accuracy', 'Accuracy (%)', False, None, '{:.1f}'),
        ('task1_coverage.png', 'l1d_coverage', 'L1D prefetch coverage', 'Coverage (%)', False, None, '{:.1f}'),
    ]
    for name, key, title, ylabel, geo, ref, fmt in specs:
        fig, ax = plt.subplots(figsize=(5.2, 2.6))
        bars(ax, res, cfgs, key, title, ylabel, geo, ref, fmt)
        if key == 'speedup':
            speedup_axis(ax)
        save(fig, name, ax)
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    bars(ax, res, ['baseline'] + cfgs, 'l1d_load_mpki', 'L1D load MPKI (lower is better)', 'MPKI')
    save(fig, 'task1_mpki.png', ax)


def l2_panels(res, cfgs, name):
    """Speedup plus the three L2 MPKI numbers asked for in Task 2."""
    fig, axes = plt.subplots(1, 4, figsize=(10, 2.6))
    bars(axes[0], res, [c for c in cfgs if c != 'baseline'], 'speedup',
         'Speedup', 'IPC / baseline IPC', geo=True, ref=1.0, fmt='{:.3f}')
    speedup_axis(axes[0])
    bars(axes[1], res, cfgs, 'l2c_load_mpki', 'L2C load MPKI', 'MPKI')
    bars(axes[2], res, cfgs, 'l2c_instr_load_mpki', 'L2C instruction load MPKI', 'MPKI')
    bars(axes[3], res, cfgs, 'l2c_data_load_mpki', 'L2C data load MPKI', 'MPKI')
    fig.tight_layout(w_pad=1.5)
    save(fig, name, axes[1])


def task2b_sensitivity(res):
    th = [float(t) for t in THRESHOLDS]
    keys = [('speedup', 'Speedup'), ('l2c_load_mpki', 'L2C load MPKI'),
            ('l2c_instr_load_mpki', 'L2C instruction load MPKI'),
            ('l2c_data_load_mpki', 'L2C data load MPKI')]
    fig, axes = plt.subplots(1, 4, figsize=(10, 2.5))
    for ax, (key, title) in zip(axes, keys):
        for t, color in zip(TRACES, TRACE_COLORS):
            ys = [res[f'dyn_irrip_{v}'][t][key] for v in THRESHOLDS]
            ax.plot(th, ys, color=color, linewidth=2, marker='o', markersize=4, label=t.replace('Trace', 'Trace '))
        ax.set_title(title)
        ax.set_xlabel('Decision threshold')
        ax.set_xticks(th)
        ax.grid(zorder=0)
    axes[0].set_ylabel('IPC / baseline IPC')
    fig.tight_layout(w_pad=1.5)
    save(fig, 'task2b_sensitivity.png', axes[0])


def task3(res):
    l2_panels(res, ['baseline', 'spp', DYN, 'spp_dyn_irrip'], 'task3_l2.png')

    fig, axes = plt.subplots(1, 3, figsize=(10, 2.6))
    bars(axes[0], res, ['baseline', 'spp', DYN, 'spp_dyn_irrip'], 'l1d_load_mpki', 'L1D load MPKI', 'MPKI')
    bars(axes[1], res, ['spp', 'spp_dyn_irrip'], 'l1d_pref_accuracy', 'L1D prefetch accuracy', 'Accuracy (%)', fmt='{:.1f}')
    bars(axes[2], res, ['spp', 'spp_dyn_irrip'], 'l1d_coverage', 'L1D prefetch coverage', 'Coverage (%)', fmt='{:.1f}')
    fig.tight_layout(w_pad=1.5)
    save(fig, 'task3_l1d.png', axes[0])


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    with open(RESULTS) as f:
        res = json.load(f)
    task1(res)
    l2_panels(res, ['baseline', 'irrip'], 'task2a.png')
    l2_panels(res, ['baseline', 'irrip', DYN], 'task2b_compare.png')
    task2b_sensitivity(res)
    task3(res)
    print('plots written to', PLOTS_DIR)


if __name__ == '__main__':
    main()
