import re

class IRStats:
    @staticmethod
    def count_ops(text: str, stage: str) -> dict:
        ops = {
            "load": 0,
            "store": 0,
            "arithmetic": 0,
            "memory": 0,
            "control": 0,
            "calls": 0,
            "total": 0
        }
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip().lower()
            if not line or line.startswith(';') or line.startswith('!'):
                continue
                
            ops["total"] += 1
            
            if stage == "llvm_ir":
                if 'load ' in line: ops["load"] += 1
                if 'store ' in line: ops["store"] += 1
                if 'icmp ' in line or 'fcmp ' in line or 'add ' in line or 'sub ' in line or 'mul ' in line: ops["arithmetic"] += 1
                if 'alloca ' in line: ops["memory"] += 1
                if 'br ' in line or 'ret ' in line: ops["control"] += 1
                if 'call ' in line: ops["calls"] += 1
            elif stage in ["fir", "hlfir"]:
                if 'fir.load' in line or 'hlfir.load' in line: ops["load"] += 1
                if 'fir.store' in line or 'hlfir.assign' in line: ops["store"] += 1
                if 'arith.' in line or 'math.' in line: ops["arithmetic"] += 1
                if 'fir.alloca' in line or 'fir.allocmem' in line: ops["memory"] += 1
                if 'fir.br' in line or 'fir.cond_br' in line: ops["control"] += 1
                if 'fir.call' in line or 'hlfir.call' in line: ops["calls"] += 1
                
        return ops
