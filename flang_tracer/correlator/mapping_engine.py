import re
from typing import Dict, List, Any

class MappingEngine:
    def __init__(self, source_text: str, hlfir_text: str, fir_text: str, llvm_ir_text: str, start_line: int = 1):
        self.source_text = source_text
        self.hlfir_text = hlfir_text
        self.fir_text = fir_text
        self.llvm_ir_text = llvm_ir_text
        self.start_line = start_line
        
        self.hlfir_loc_map = self._parse_mlir_locs(hlfir_text)
        self.fir_loc_map = self._parse_mlir_locs(fir_text)
        self.llvm_dbg_map = self._parse_llvm_dbg(llvm_ir_text)

    def _parse_mlir_locs(self, fragment: str) -> Dict[str, int]:
        loc_map = {}
        if not fragment:
            return loc_map
        # Pattern: #loc12 = loc("file":16:5) or #loc12 = loc(fused["file":16:5])
        pattern = r'#loc(\d+)\s*=\s*loc\((?:"[^"]*")?:(\d+):\d+\)'
        for match in re.finditer(pattern, fragment):
            loc_map[match.group(1)] = int(match.group(2))
        
        # Fallback pattern if quotes/fused formats are different
        pattern_fallback = r'#loc(\d+)\s*=\s*loc\(.*:(\d+):(?:\d+)\)'
        for match in re.finditer(pattern_fallback, fragment):
            id_val = match.group(1)
            if id_val not in loc_map:
                loc_map[id_val] = int(match.group(2))
        return loc_map

    def _parse_llvm_dbg(self, fragment: str) -> Dict[str, int]:
        dbg_map = {}
        if not fragment:
            return dbg_map
        # Pattern: !22 = !DILocation(line: 16, column: 5, ...)
        pattern = r'^!(\d+)\s*=\s*!DILocation\(line:\s*(\d+)'
        for match in re.finditer(pattern, fragment, re.MULTILINE):
            dbg_map[match.group(1)] = int(match.group(2))
        return dbg_map

    def _get_instructions_for_lines(self, fragment: str, line_numbers: List[int], stage: str) -> List[str]:
        if not fragment:
            return []
        lines = fragment.split('\n')
        matched = []
        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue
            if stage in ('hlfir', 'fir'):
                loc_map = self.hlfir_loc_map if stage == 'hlfir' else self.fir_loc_map
                # Search for loc(#loc12)
                loc_match = re.search(r'loc\(#loc(\d+)\)', trimmed)
                if loc_match:
                    loc_id = loc_match.group(1)
                    source_line = loc_map.get(loc_id)
                    if source_line and source_line in line_numbers:
                        matched.append(trimmed)
            elif stage == 'llvm_ir':
                # Search for !dbg !22
                dbg_match = re.search(r'!dbg\s+!(\d+)', trimmed)
                if dbg_match:
                    dbg_id = dbg_match.group(1)
                    source_line = self.llvm_dbg_map.get(dbg_id)
                    if source_line and source_line in line_numbers:
                        matched.append(trimmed)
        return matched

    def generate_tables(self) -> Dict[str, List[Dict[str, Any]]]:
        rules = [
            {
                "id": "var_decl",
                "name": "Variable Declaration",
                "src_regex": r'^\s*(integer|real|type|logical|character|complex|double\s+precision)\b',
                "exclude_regex": None,
                "fallback_hlfir": r'.*hlfir\.declare.*',
                "fallback_fir": r'.*fir\.(alloca|declare).*',
                "fallback_llvm": r'.*alloca.*',
                "hlfir_rep": "hlfir.declare",
                "fir_rep": "fir.alloca, fir.declare",
                "llvm_rep": "alloca",
                "explanation": "Fortran variable declarations define typings and storage boundaries. Lowered to <code>hlfir.declare</code> in HLFIR to preserve high-level symbol and bounds info. FIR lowers this to stack allocation via <code>fir.alloca</code> and a <code>fir.declare</code> metadata tag. LLVM IR represents this using the hardware-level <code>alloca</code> instruction to reserve stack frame slots."
            },
            {
                "id": "assignment",
                "name": "Assignment (=)",
                "src_regex": r'=\s*[^=]',
                "exclude_regex": r'(do\s+concurrent|do\s+\w+\s*=|if\s*\(|where\s*\(|forall\s*\()',
                "fallback_hlfir": r'.*hlfir\.assign.*',
                "fallback_fir": r'.*fir\.store.*',
                "fallback_llvm": r'.*store.*',
                "hlfir_rep": "hlfir.assign",
                "fir_rep": "fir.store",
                "llvm_rep": "store",
                "explanation": "Source assignments write RHS values into LHS memory locations. HLFIR models this abstractly using <code>hlfir.assign</code> (which simplifies scalar or whole-array transfers). FIR decomposes this into explicit memory store sequences using <code>fir.store</code>. LLVM IR implements this using raw <code>store</code> instructions, directing hardware cache/RAM writes."
            },
            {
                "id": "mem_read",
                "name": "Memory Load / Read",
                "src_regex": r'[a-zA-Z_]\w*',
                "exclude_regex": r'^\s*(program|integer|real|type|logical|character|complex|double\s+precision|implicit|none|end|do|while|if|else|endif|forall|where|elsewhere|print|write|call|return|stop)\b',
                "fallback_hlfir": r'.*(fir\.load|hlfir\.designate).*',
                "fallback_fir": r'.*fir\.load.*',
                "fallback_llvm": r'.*load.*',
                "hlfir_rep": "hlfir.designate",
                "fir_rep": "fir.load",
                "llvm_rep": "load",
                "explanation": "Reading a variable's stored value from memory. HLFIR abstracts this using <code>hlfir.designate</code> for indexing or <code>fir.load</code> for scalar values. FIR requires explicit dereferencing using <code>fir.load</code>. LLVM IR implements this directly using the hardware <code>load</code> instruction to pull the value into an SSA virtual register."
            },
            {
                "id": "constants",
                "name": "Constants",
                "src_regex": r'\b(\d+(\.\d+)?(_\w+)?)\b',
                "exclude_regex": None,
                "fallback_hlfir": r'.*arith\.constant.*',
                "fallback_fir": r'.*arith\.constant.*',
                "fallback_llvm": r'.*load.*align|.*add.*i32.*',
                "hlfir_rep": "arith.constant",
                "fir_rep": "arith.constant",
                "llvm_rep": "immediate constant (e.g. i32 5)",
                "explanation": "Literal compile-time values. HLFIR and FIR represent these as SSA values generated by the <code>arith.constant</code> operation. LLVM IR completely lowers them into immediate/inline values directly inside hardware instructions (e.g. <code>i32 100</code> or <code>1.000000e+00</code>), meaning zero memory overhead at runtime."
            },
            {
                "id": "arithmetic",
                "name": "Arithmetic Operations",
                "src_regex": r'[\+\-\*\/]',
                "exclude_regex": None,
                "fallback_hlfir": r'.*arith\.(add|sub|mul|div)[if].*',
                "fallback_fir": r'.*arith\.(add|sub|mul|div)[if].*',
                "fallback_llvm": r'.*(add|fadd|sub|fsub|mul|fmul|sdiv|fdiv).*',
                "hlfir_rep": "arith.addi / arith.addf",
                "fir_rep": "arith.addi / arith.addf",
                "llvm_rep": "add / fadd",
                "explanation": "Mathematical operations. MLIR splits these into type-specific operations in the <code>arith</code> dialect (e.g. <code>arith.addi</code> for integer addition, <code>arith.addf</code> for floating-point). LLVM IR maps them directly to CPU-native arithmetic instructions (e.g., <code>add</code>, <code>fadd</code>, <code>sub</code>, <code>fsub</code>, <code>mul</code>, <code>fmul</code>, <code>sdiv</code>, <code>fdiv</code>)."
            },
            {
                "id": "comparison",
                "name": "Comparisons",
                "src_regex": r'(<|>|==|<=|>=|\/=|\.lt\.|\.gt\.|\.eq\.|\.ne\.|\.le\.|\.ge\.)',
                "exclude_regex": None,
                "fallback_hlfir": r'.*(arith\.cmpi|arith\.cmpf).*',
                "fallback_fir": r'.*(arith\.cmpi|arith\.cmpf).*',
                "fallback_llvm": r'.*(icmp|fcmp).*',
                "hlfir_rep": "arith.cmpi slt/sgt/eq",
                "fir_rep": "arith.cmpi slt/sgt/eq",
                "llvm_rep": "icmp slt/sgt/eq",
                "explanation": "Relational checks. MLIR handles this using <code>arith.cmpi</code> (integer comparisons) or <code>arith.cmpf</code> (floating-point comparisons) with predicate fields. LLVM IR compiles this into <code>icmp</code> or <code>fcmp</code>, which produces a 1-bit boolean register (<code>i1</code>) used to drive conditional jumps."
            },
            {
                "id": "if_else",
                "name": "If / Else",
                "src_regex": r'\b(if\s*\(|then|else|elsewhere|endif)\b',
                "exclude_regex": None,
                "fallback_hlfir": r'.*scf\.if.*',
                "fallback_fir": r'.*(cf\.cond_br|cf\.br).*',
                "fallback_llvm": r'.*(br\s+i1|br\s+label).*',
                "hlfir_rep": "scf.if / structured region",
                "fir_rep": "cf.cond_br, cf.br",
                "llvm_rep": "br i1 / basic blocks",
                "explanation": "Conditional control flow. HLFIR models branching cleanly using structured MLIR regions like <code>scf.if</code>. FIR lowers this structured block into explicit branchy Control Flow Graph (CFG) basic blocks using <code>cf.cond_br</code> and <code>cf.br</code>. LLVM IR lowers these to basic block labels and hardware-level conditional jumps (<code>br i1 %cond, label %true, label %false</code>)."
            },
            {
                "id": "do_loop",
                "name": "Do Loops / Do Concurrent",
                "src_regex": r'\b(do\s+\w+\s*=|do\s+concurrent)\b',
                "exclude_regex": None,
                "fallback_hlfir": r'.*(scf\.for|hlfir\.elemental|hlfir\.yield).*',
                "fallback_fir": r'.*(cf\.cond_br|cf\.br).*',
                "fallback_llvm": r'.*(br\s+i1|phi\s+).*',
                "hlfir_rep": "scf.for / hlfir.elemental",
                "fir_rep": "cf.br / CFG loop blocks",
                "llvm_rep": "br / phi nodes",
                "explanation": "Iterative execution loops. HLFIR preserves loops as structured, optimization-friendly <code>scf.for</code> operations or concurrency-aware <code>hlfir.elemental</code> structures. FIR lowers them into structured basic blocks with loop back-edges. LLVM IR implements loops via explicit branching, using <code>phi</code> nodes to merge and track loop-carried induction variables across iterations."
            },
            {
                "id": "while_loop",
                "name": "While Loops",
                "src_regex": r'\bdo\s+while\b',
                "exclude_regex": None,
                "fallback_hlfir": r'.*(hlfir\.while|scf\.while).*',
                "fallback_fir": r'.*(cf\.cond_br|cf\.br).*',
                "fallback_llvm": r'.*(br\s+i1|phi\s+).*',
                "hlfir_rep": "hlfir.while / scf.while",
                "fir_rep": "cf.br, cf.cond_br",
                "llvm_rep": "br / phi nodes",
                "explanation": "Condition-driven loops. HLFIR abstracts this using <code>hlfir.while</code> or <code>scf.while</code>. FIR eliminates the high-level loop structures, lowering them into loop header, body, and exit basic blocks. LLVM IR maps this to raw basic blocks with conditional branch instructions at the loop head and an unconditional back-edge jump."
            },
            {
                "id": "func_call",
                "name": "Function / Subroutine Calls",
                "src_regex": r'\b(call\s+\w+|\w+\s*\(.*\))',
                "exclude_regex": r'(integer|real|type|logical|character|complex|double\s+precision|if|do|where|forall)\b',
                "fallback_hlfir": r'.*(fir\.call|hlfir\.call).*',
                "fallback_fir": r'.*fir\.call.*',
                "fallback_llvm": r'.*call\s+.*',
                "hlfir_rep": "hlfir.call / fir.call",
                "fir_rep": "fir.call",
                "llvm_rep": "call",
                "explanation": "Invoking procedures or Fortran runtime library functions. MLIR tracks this with <code>fir.call</code> or <code>hlfir.call</code>. LLVM IR lowers this to the target architecture's standard <code>call</code> instruction. Note that arguments are passed by reference (as pointers/addresses) to comply with Fortran conventions."
            },
            {
                "id": "array_access",
                "name": "Array Access",
                "src_regex": r'[a-zA-Z_]\w*\s*\(.*\)',
                "exclude_regex": r'(integer|real|type|logical|character|complex|double\s+precision|if|do|where|forall|print|write)\b',
                "fallback_hlfir": r'.*hlfir\.designate.*',
                "fallback_fir": r'.*(fir\.coordinate_of|fir\.array_coor).*',
                "fallback_llvm": r'.*getelementptr.*',
                "hlfir_rep": "hlfir.designate",
                "fir_rep": "fir.coordinate_of / fir.array_coor",
                "llvm_rep": "getelementptr",
                "explanation": "Reading or writing array indices. HLFIR abstracts this elegantly using <code>hlfir.designate</code>, which holds type and shape descriptors. FIR lowers this to explicit index offset calculations via <code>fir.coordinate_of</code> or <code>fir.array_coor</code>. LLVM IR converts these to <code>getelementptr</code> (GEP) offset calculations based on struct stride and dimensions."
            },
            {
                "id": "mem_alloc",
                "name": "Memory Allocation",
                "src_regex": r'\b(allocate|deallocate)\b',
                "exclude_regex": None,
                "fallback_hlfir": r'.*(fir\.allocmem|hlfir\.declare).*',
                "fallback_fir": r'.*(fir\.allocmem|fir\.alloca).*',
                "fallback_llvm": r'.*(alloca|malloc|call.*_FortranAAlloc).*',
                "hlfir_rep": "hlfir.declare / fir.allocmem",
                "fir_rep": "fir.alloca / fir.allocmem",
                "llvm_rep": "alloca / malloc / runtime call",
                "explanation": "Dynamically allocating storage. Stack variables use MLIR's <code>fir.alloca</code> and LLVM's <code>alloca</code>. Dynamic or pointer allocations (e.g. Fortran <code>allocate</code>) are lowered to Flang's runtime memory manager, which allocates heap memory via <code>malloc</code>."
            },
            {
                "id": "branching",
                "name": "Branching",
                "src_regex": r'\b(goto|cycle|exit)\b',
                "exclude_regex": None,
                "fallback_hlfir": r'.*(cf\.br|cf\.cond_br).*',
                "fallback_fir": r'.*(cf\.br|cf\.cond_br).*',
                "fallback_llvm": r'.*br\s+label.*',
                "hlfir_rep": "structured region / cf.br",
                "fir_rep": "cf.br / cf.cond_br",
                "llvm_rep": "br label",
                "explanation": "Jumping to a specific point of execution. Low-level MLIR FIR structures this as basic-block control flow jumps (<code>cf.br</code>). LLVM IR maps these directly to native jump instructions (<code>br label %destination</code>)."
            },
            {
                "id": "return_exit",
                "name": "Return / Exit",
                "src_regex": r'\b(end\s+program|end\s+subroutine|end\s+function|return|stop)\b',
                "exclude_regex": None,
                "fallback_hlfir": r'.*(func\.return|fir\.unreachable).*',
                "fallback_fir": r'.*(func\.return|fir\.unreachable).*',
                "fallback_llvm": r'.*(ret\s|unreachable).*',
                "hlfir_rep": "func.return",
                "fir_rep": "func.return",
                "llvm_rep": "ret void / ret <type>",
                "explanation": "Returning control from a function or exiting a program. Low-level MLIR uses <code>func.return</code> to pass back results. LLVM IR lowers this directly to <code>ret void</code> or a typed return instruction (e.g., <code>ret i32 %result</code>), resetting the stack pointer."
            }
        ]

        cross_stage_mapping = []
        static_comparison_reference = []

        lines = self.source_text.split('\n')

        for rule in rules:
            line_numbers = []
            matched_src_lines = []

            for idx, l in enumerate(lines):
                line_num = idx + self.start_line
                if re.search(rule["src_regex"], l, re.IGNORECASE):
                    if rule["exclude_regex"] and re.search(rule["exclude_regex"], l, re.IGNORECASE):
                        continue
                    line_numbers.append(line_num)
                    matched_src_lines.append(l.strip())

            if line_numbers:
                # 1. Generate Cross-Stage Mapping Table row
                hlfir_lines = self._get_instructions_for_lines(self.hlfir_text, line_numbers, 'hlfir')
                fir_lines = self._get_instructions_for_lines(self.fir_text, line_numbers, 'fir')
                llvm_lines = self._get_instructions_for_lines(self.llvm_ir_text, line_numbers, 'llvm_ir')

                # Fallbacks
                if not hlfir_lines and self.hlfir_text:
                    hlfir_lines = [l.strip() for l in self.hlfir_text.split('\n') if re.search(rule["fallback_hlfir"], l)][:3]
                if not fir_lines and self.fir_text:
                    fir_lines = [l.strip() for l in self.fir_text.split('\n') if re.search(rule["fallback_fir"], l)][:3]
                if not llvm_lines and self.llvm_ir_text:
                    llvm_lines = [l.strip() for l in self.llvm_ir_text.split('\n') if re.search(rule["fallback_llvm"], l)][:3]

                cross_stage_mapping.append({
                    "construct_element": rule["name"],
                    "source_code": "\n".join(matched_src_lines),
                    "hlfir": "\n".join(hlfir_lines) if hlfir_lines else "-",
                    "fir": "\n".join(fir_lines) if fir_lines else "-",
                    "llvm_ir": "\n".join(llvm_lines) if llvm_lines else "-",
                    "explanation": rule["explanation"]
                })

                # 2. Generate Static IR Comparison Reference Table row dynamically!
                static_comparison_reference.append({
                    "fortran_construct": rule["name"],
                    "hlfir": rule["hlfir_rep"],
                    "fir": rule["fir_rep"],
                    "llvm_ir": rule["llvm_rep"]
                })

        return {
            "cross_stage_mapping": cross_stage_mapping,
            "static_comparison_reference": static_comparison_reference
        }
