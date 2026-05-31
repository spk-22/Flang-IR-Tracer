import re
from typing import List, Optional
from flang_tracer import SourceRange, Fragment

class ParseTreeNode:
    def __init__(self, line_text: str):
        # Match indentation (spaces and |)
        match = re.match(r"^([ |]*)(\w+.*)$", line_text)
        if match:
            self.indent = len(match.group(1))
            self.content = match.group(2)
        else:
            self.indent = 0
            self.content = line_text
        self.children: List['ParseTreeNode'] = []

    def __repr__(self):
        return f"Node({self.content}, children={len(self.children)})"

class ParseTreeParser:
    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.root = self._parse_tree()

    def _parse_tree(self) -> Optional[ParseTreeNode]:
        lines = self.raw_text.splitlines()
        # Skip header
        lines = [l for l in lines if not l.startswith("=======")]
        if not lines:
            return None

        stack: List[ParseTreeNode] = []
        root = None

        for line in lines:
            if not line.strip():
                continue
            node = ParseTreeNode(line)
            
            while stack and stack[-1].indent >= node.indent:
                stack.pop()
            
            if stack:
                stack[-1].children.append(node)
            else:
                if root is None:
                    root = node
            stack.append(node)
        
        return root

    def extract_fragment(self, source_range: SourceRange) -> Fragment:
        # Read the file to get target source lines
        target_text = ""
        try:
            with open(source_range.file, "r") as f:
                lines = f.readlines()
            target_lines = [lines[i].strip() for i in range(source_range.start_line - 1, min(len(lines), source_range.end_line))]
            target_text = "".join(target_lines).replace(" ", "").lower()
            # Strip comments
            if "!" in target_text:
                target_text = target_text.split("!")[0]
        except Exception:
            pass

        # Find a node whose content matches the target text
        matched_nodes = []
        
        def clean_content(c: str) -> str:
            # e.g., AssignmentStmt = 'sum=0_4' -> sum=0
            # Remove kind suffix _4, _8, etc.
            c_clean = c.replace(" ", "").lower()
            c_clean = re.sub(r'_[0-9]+', '', c_clean)
            c_clean = re.sub(r"['\"]", "", c_clean)
            if '=' in c_clean:
                parts = c_clean.split('=', 1)
                # Keep statement representation after '='
                if len(parts) > 1 and any(x in parts[0] for x in ["stmt", "construct", "decl", "expr"]):
                    return parts[1]
            return c_clean

        def dfs(node: ParseTreeNode):
            if not node:
                return
            node_clean = clean_content(node.content)
            if target_text and node_clean and (target_text in node_clean or node_clean in target_text) and len(node_clean) > 2:
                matched_nodes.append(node)
            for child in node.children:
                dfs(child)

        if self.root:
            dfs(self.root)

        if matched_nodes:
            # Render the matched subtree
            def render_subtree(n: ParseTreeNode, indent_level: int = 0) -> List[str]:
                lines = ["  " * indent_level + n.content]
                for child in n.children:
                    lines.extend(render_subtree(child, indent_level + 1))
                return lines
            
            # Select the first matched node
            best_node = matched_nodes[0]
            subtree_text = "\n".join(render_subtree(best_node))
            return Fragment(
                stage="parse_tree",
                source_range=source_range,
                raw_text=subtree_text
            )

        return Fragment(
            stage="parse_tree",
            source_range=source_range,
            raw_text=self.raw_text
        )

