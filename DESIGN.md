# DESIGN

## Approach
The **Flang IR Tracer** visualises the complete multi‑stage compilation pipeline of the Flang Fortran compiler:

1. **Parse Tree** – raw syntactic representation.
2. **Decorated Parse Tree** – after syntax‑directed analysis.
3. **FIR (Fortran IR)** – language‑independent intermediate representation.
4. **HLFIR (High‑level FIR)** – enriched with type and shape information.
5. **LLVM IR** – final low‑level representation fed to the optimiser.
6. **Memory Usage** – peak RSS captured for each stage.

The pipeline is driven by `flang_tracer/driver.py`, which invokes the Flang binary for each optimisation level and parses the textual dumps via regex‑based hooks. The collected data is streamed over a WebSocket to the browser where **D3.js** visualises a hierarchical trace and **Chart.js** displays performance and memory charts.

## Alternatives Considered
| Alternative | Description | Reason for Rejection |
|-------------|--------------|----------------------|
| Use existing LLVM opt‑viewer | Show only LLVM IR; does not expose FIR/HLFIR. | Lacks the multi‑stage view required for Fortran developers. |
| Extend Godbolt | Add custom panels for FIR/HLFIR. | Requires upstream changes and does not integrate memory metrics. |
| Static HTML report generation | Generate a single static page after compilation. | Loses interactivity and real‑time performance charting. |

The chosen architecture preserves **interactivity**, supports **dynamic memory metrics**, and stays **self‑contained** without external service dependencies.
