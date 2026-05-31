
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
