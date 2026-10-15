#!/usr/bin/env python3
import os
import sys
import re
import json
import csv
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed

WARMUP = 25000000
SIM = 25000000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACES = {t: os.path.join(BASE_DIR, 'traces', f'{t}.gz') for t in ['Trace1', 'Trace2', 'Trace3']}

RESULTS_DIR = os.path.join(BASE_DIR, 'results')
LOGS_DIR = os.path.join(RESULTS_DIR, 'raw_logs')

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def parse_champsim_log(text):
    data = {}
    
    # IPC and cycles
    m = re.search(r'CPU 0 cumulative IPC:\s+([0-9.]+)\s+instructions:\s+(\d+)\s+cycles:\s+(\d+)', text)
    if not m:
        m = re.search(r'Finished CPU 0 instructions:\s+(\d+)\s+cycles:\s+(\d+)\s+cumulative IPC:\s+([0-9.]+)', text)
        if m:
            data['instructions'] = int(m.group(1))
            data['cycles'] = int(m.group(2))
            data['ipc'] = float(m.group(3))
    else:
        data['ipc'] = float(m.group(1))
        data['instructions'] = int(m.group(2))
        data['cycles'] = int(m.group(3))

    # L1D Load
    m = re.search(r'L1D LOAD\s+ACCESS:\s+(\d+)\s+HIT:\s+(\d+)\s+MISS:\s+(\d+).*?MPKI:\s+([0-9.]+)', text)
    if m:
        data['l1d_load_access'] = int(m.group(1))
        data['l1d_load_hit'] = int(m.group(2))
        data['l1d_load_miss'] = int(m.group(3))
        data['l1d_load_mpki'] = float(m.group(4))

    # L1D Prefetch Accuracy
    m = re.search(r'L1D USEFUL LOAD PREFETCHES:\s+(\d+).*?ACCURACY:\s+([0-9.]+|nan)', text)
    if m:
        data['l1d_pref_useful'] = int(m.group(1))
        data['l1d_pref_accuracy'] = 0.0 if m.group(2) == 'nan' else float(m.group(2))

    # L1D Prefetch Requested / Issued
    m = re.search(r'L1D PREFETCH\s+REQUESTED:\s+(\d+)\s+ISSUED:\s+(\d+)\s+USEFUL:\s+(\d+)\s+USELESS:\s+(\d+)', text)
    if m:
        data['l1d_pref_requested'] = int(m.group(1))
        data['l1d_pref_issued'] = int(m.group(2))
        data['l1d_pref_useful_total'] = int(m.group(3))
        data['l1d_pref_useless'] = int(m.group(4))

    # SPP specific stats
    m = re.search(r'Calculated Accuracy:\s+([0-9.]+)\s+%', text)
    if m:
        data['spp_calculated_accuracy'] = float(m.group(1))

    # L2C Load
    m = re.search(r'L2C LOAD\s+ACCESS:\s+(\d+)\s+HIT:\s+(\d+)\s+MISS:\s+(\d+).*?MPKI:\s+([0-9.]+)', text)
    if m:
        data['l2c_load_access'] = int(m.group(1))
        data['l2c_load_hit'] = int(m.group(2))
        data['l2c_load_miss'] = int(m.group(3))
        data['l2c_load_mpki'] = float(m.group(4))

    m = re.search(r'L2C DATA LOAD MPKI:\s+([0-9.]+)', text)
    if m:
        data['l2c_data_load_mpki'] = float(m.group(1))

    m = re.search(r'L2C INSTRUCTION LOAD MPKI:\s+([0-9.]+)', text)
    if m:
        data['l2c_instr_load_mpki'] = float(m.group(1))

    # L2C Prefetch Accuracy
    m = re.search(r'L2C USEFUL LOAD PREFETCHES:\s+(\d+).*?ACCURACY:\s+([0-9.]+|nan)', text)
    if m:
        data['l2c_pref_useful'] = int(m.group(1))
        data['l2c_pref_accuracy'] = 0.0 if m.group(2) == 'nan' else float(m.group(2))

    return data

def run_single_simulation(job):
    name, bin_path, trace_name, trace_path, env_vars = job
    log_file = os.path.join(LOGS_DIR, f"{name}_{trace_name}.log")
    
    # Check if already completed and valid
    if os.path.exists(log_file) and os.path.getsize(log_file) > 1000:
        with open(log_file, 'r') as f:
            content = f.read()
        if "cumulative IPC" in content:
            parsed = parse_champsim_log(content)
            if 'ipc' in parsed:
                print(f"[REUSED CACHED] {name} on {trace_name}: IPC = {parsed['ipc']:.4f}")
                return name, trace_name, parsed

    cmd = [
        bin_path,
        "-warmup_instructions", str(WARMUP),
        "-simulation_instructions", str(SIM),
        "-traces", trace_path
    ]
    
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
        
    print(f"[STARTING] {name} on {trace_name}...")
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, timeout=1200)
        output = proc.stdout
        with open(log_file, 'w') as f:
            f.write(output)
            
        parsed = parse_champsim_log(output)
        ipc = parsed.get('ipc', 0.0)
        print(f"[COMPLETED] {name} on {trace_name}: IPC = {ipc:.4f}")
        return name, trace_name, parsed
    except Exception as e:
        print(f"[ERROR] Failed {name} on {trace_name}: {e}")
        return name, trace_name, {}

# config name -> (L1D prefetcher, L2C replacement, binary suffix) for build_champsim.sh
BUILDS = {
    'baseline':      ('no',       'lru',       'baseline'),
    'ip_stride':     ('ip_stride', 'lru',      'ip_stride'),
    'spp':           ('spp',      'lru',       'spp'),
    'irrip':         ('no',       'irrip',     'irrip'),
    'dyn_irrip':     ('no',       'dyn_irrip', 'dyn_irrip'),
    'spp_dyn_irrip': ('spp',      'dyn_irrip', 'spp_dyn_irrip'),
}

def binary(build):
    """Path of the ChampSim binary for a build, building it if it is missing."""
    pref, repl, suffix = BUILDS[build]
    path = os.path.join(BASE_DIR, 'bin',
        f"hashed_perceptron-no-{pref}-no-no-no-no-no-lru-lru-lru-{repl}-lru-lru-lru-lru-1core-{suffix}")
    if not os.path.exists(path):
        print(f"[BUILD] {build}")
        subprocess.run(['./build_champsim.sh', pref, repl, suffix], cwd=BASE_DIR, check=True,
                       stdout=subprocess.DEVNULL)
    return path

def main():
    jobs = []
    bins = {b: binary(b) for b in BUILDS}

    # Task 1: baseline, IP-stride and SPP
    for cfg in ['baseline', 'ip_stride', 'spp']:
        for t_name, t_path in TRACES.items():
            jobs.append((cfg, bins[cfg], t_name, t_path, None))

    # Task 2A: I-RRIP
    for t_name, t_path in TRACES.items():
        jobs.append(('irrip', bins['irrip'], t_name, t_path, None))

    # Task 2B: dynamic I-RRIP, sensitivity study over 5 thresholds
    for thresh in ['0.15', '0.20', '0.25', '0.30', '0.35']:
        for t_name, t_path in TRACES.items():
            jobs.append((f'dyn_irrip_{thresh}', bins['dyn_irrip'], t_name, t_path, {'IRRIP_THRESH': thresh}))

    # Task 3: SPP + dynamic I-RRIP
    for t_name, t_path in TRACES.items():
        jobs.append(('spp_dyn_irrip', bins['spp_dyn_irrip'], t_name, t_path, {'IRRIP_THRESH': '0.25'}))

    print(f"Total jobs to execute: {len(jobs)}")
    
    results = {}
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(run_single_simulation, job): job for job in jobs}
        for future in as_completed(futures):
            name, trace_name, data = future.result()
            if name not in results:
                results[name] = {}
            results[name][trace_name] = data
            
    # Compute relative metrics: Speedup and L1D Coverage
    for name in results:
        for t_name in TRACES:
            base_data = results.get('baseline', {}).get(t_name, {})
            curr_data = results[name].get(t_name, {})
            
            if 'ipc' in curr_data and 'ipc' in base_data and base_data['ipc'] > 0:
                curr_data['speedup'] = curr_data['ipc'] / base_data['ipc']
            else:
                curr_data['speedup'] = 1.0
                
            if 'l1d_load_miss' in curr_data and 'l1d_load_miss' in base_data and base_data['l1d_load_miss'] > 0:
                miss_base = base_data['l1d_load_miss']
                miss_curr = curr_data['l1d_load_miss']
                curr_data['l1d_coverage'] = ((miss_base - miss_curr) / float(miss_base)) * 100.0
            else:
                curr_data['l1d_coverage'] = 0.0

    # Save results to JSON
    json_path = os.path.join(RESULTS_DIR, 'all_results.json')
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Saved complete results to {json_path}")
    
    # Save results to CSV
    csv_path = os.path.join(RESULTS_DIR, 'all_results.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Configuration', 'Trace', 'IPC', 'Speedup',
            'L1D_Load_MPKI', 'L1D_Pref_Accuracy', 'L1D_Coverage',
            'L2C_Load_MPKI', 'L2C_Instr_MPKI', 'L2C_Data_MPKI', 'Cycles'
        ])
        for name in results:
            for t_name in sorted(TRACES.keys()):
                d = results[name].get(t_name, {})
                writer.writerow([
                    name, t_name,
                    f"{d.get('ipc', 0.0):.4f}",
                    f"{d.get('speedup', 1.0):.4f}",
                    f"{d.get('l1d_load_mpki', 0.0):.2f}",
                    f"{d.get('l1d_pref_accuracy', 0.0):.2f}",
                    f"{d.get('l1d_coverage', 0.0):.2f}",
                    f"{d.get('l2c_load_mpki', 0.0):.2f}",
                    f"{d.get('l2c_instr_load_mpki', 0.0):.2f}",
                    f"{d.get('l2c_data_load_mpki', 0.0):.2f}",
                    d.get('cycles', 0)
                ])
    print(f"Saved complete results to {csv_path}")

if __name__ == '__main__':
    main()

