import os, sys, json, re
from flang_tracer.driver import FlangDriver

def count_ir_ops(ir_text):
    # Rough count: lines that contain an LLVM instruction (" = " pattern)
    return sum(1 for line in ir_text.splitlines() if ' = ' in line)

def main():
    # repository root is two levels up from this script
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    # Add src directory to PYTHONPATH so flang_tracer can be imported
    sys.path.append(os.path.join(repo_root, 'src'))
    testcases_dir = os.path.join(repo_root, 'testcases')
    driver = FlangDriver('flang-new', opt_level='O0')
    results = []
    for filename in sorted(os.listdir(testcases_dir)):
        if not filename.lower().endswith('.f90'):
            continue
        path = os.path.join(testcases_dir, filename)
        dumps = driver.get_all_dumps(path)
        # Gather timings for FIR, HLFIR, LLVM‑IR
        stage_info = {}
        for stage in ('fir', 'hlfir', 'llvm_ir'):
            data = dumps.get(stage, {})
            duration = data.get('duration_ms', 0.0)
            content = data.get('content', '')
            ops = count_ir_ops(content) if stage == 'llvm_ir' else 0
            stage_info[stage] = {'duration_ms': duration, 'ops': ops}
        results.append({
            'file': filename,
            'fir_ms': stage_info['fir']['duration_ms'],
            'hlfir_ms': stage_info['hlfir']['duration_ms'],
            'llvm_ms': stage_info['llvm_ir']['duration_ms'],
            'llvm_ops': stage_info['llvm_ir']['ops']
        })
    # Print markdown table
    print('| Testcase | FIR (ms) | HLFIR (ms) | LLVM‑IR (ms) | LLVM‑IR Ops |')
    print('|----------|----------|------------|--------------|------------|')
    for r in results:
        print(f"| {r['file']} | {r['fir_ms']:.2f} | {r['hlfir_ms']:.2f} | {r['llvm_ms']:.2f} | {r['llvm_ops']} |")

if __name__ == '__main__':
    main()
