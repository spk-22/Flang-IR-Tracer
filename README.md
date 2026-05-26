# flang-ir-tracer

A multi-stage compilation pipeline tracer for Flang (Fortran) that visualizes parse tree, semantics, FIR, HLFIR, LLVM IR, and memory usage.

## Quick Start
```bash
./build.sh   # install dependencies and set up environment
./run.sh --serve   # launch the web UI at http://0.0.0.0:8000
```

You can also run a single file trace:
```bash
./run.sh path/to/file.f90 --line 5
```

## Repository Layout
```
flang-ir-tracer/
├─ README.md
├─ DESIGN.md
├─ IMPLEMENTATION.md
├─ EVALUATION.md
├─ build.sh
├─ run.sh
├─ src/          # source code (copied from enhance/flang_tracer)
├─ testcases/    # sample Fortran programs
└─ scripts/      # convenience scripts (if any)
```

## Documentation
- [Implementation Details](IMPLEMENTATION.md)
- [Evaluation Report](EVALUATION.md)
- Demo (video & screenshots – not included in this repo)

## License
MIT
