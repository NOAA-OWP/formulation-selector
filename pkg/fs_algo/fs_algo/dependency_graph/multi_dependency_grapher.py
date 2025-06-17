"""
Function Dependency Grapher
===========================

This script analyzes one or more Python files and builds a **function-level dependency graph** showing which
functions call which others — within the same file or across files.

Function definitions and calls are parsed using the `ast` module. The resulting graph is visualized both as:
- A static PNG file using `matplotlib` + `networkx`
- An interactive HTML file using `pyvis`

Each function is labeled as `filename:function_name` to support disambiguation across multiple files.

Usage
-----

Run this script from the command line:

.. code-block:: bash

    python dependency_grapher.py path/to/file1.py path/to/file2.py --html_output=output_graph.html

If `--html_output` is not provided:
- For a single input file: output defaults to `<filename>_dependency_graph.html`
- For multiple files: output defaults to `multi_dependency_graph.html`

The corresponding PNG will be saved alongside the HTML, with the same base name.

"""

import ast
import argparse
import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path
from pyvis.network import Network
import warnings

class MultiFileFunctionCallVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.calls = {}  # {caller_function: [callee1, callee2, ...]}
        self.current_function = None

    def visit_FunctionDef(self, node):
        # Use qualified name: "filename:function"
        self.current_function = f"{self.filename}:{node.name}"
        self.calls.setdefault(self.current_function, [])
        self.generic_visit(node)
        self.current_function = None

    def visit_Call(self, node):
        if self.current_function:
            called_func = None
            if isinstance(node.func, ast.Name):
                called_func = node.func.id
            elif isinstance(node.func, ast.Attribute):
                called_func = node.func.attr
            
            if called_func:
                # We only append callee name, but we will resolve across all files later
                self.calls[self.current_function].append(called_func)
        self.generic_visit(node)

def build_multi_file_dependency_graph(file_paths):
    # Parse all files and gather:
    # - All functions defined, with qualified names
    # - All calls from qualified caller to callee names (unqualified)
    
    all_calls = {}
    func_name_to_qualified = {}  # Map: function_name -> set of qualified names (multiple if repeated names)
    
    for fpath in file_paths:
        filename = Path(fpath).stem
        source = Path(fpath).read_text()
        tree = ast.parse(source)
        
        visitor = MultiFileFunctionCallVisitor(filename)
        visitor.visit(tree)
        
        # Merge calls for this file
        all_calls.update(visitor.calls)
        
        # Map function simple names to qualified names for resolution
        for qualified_func in visitor.calls.keys():
            # qualified_func = "filename:function"
            simple_name = qualified_func.split(":", 1)[1]
            func_name_to_qualified.setdefault(simple_name, set()).add(qualified_func)
    
    # Build edges: For each caller, map callee names to qualified funcs in all files if exist
    edges = []
    for caller, callees in all_calls.items():
        for callee in callees:
            if callee in func_name_to_qualified:
                for callee_qualified in func_name_to_qualified[callee]:
                    edges.append((caller, callee_qualified))
            else:
                # callee not defined in any analyzed file - could add external node or ignore
                # For now, ignore external calls or optionally add them as external nodes
                pass

    # Build graph
    G = nx.DiGraph()
    G.add_edges_from(edges)
    return G

def draw_graph(G, title="Function Dependency Graph", html_output="function_graph.html"):
    html_path = Path(html_output)
    png_output = html_path.with_suffix('.png')
    
    output_dir = html_path.parent
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        warnings.warn(f"Created output directory: {output_dir.resolve()}", UserWarning)

    plt.figure(figsize=(16, 12))

    try:
        from networkx.drawing.nx_agraph import graphviz_layout
        pos = graphviz_layout(G, prog='dot')
    except ImportError:
        print("pygraphviz not installed, using spring layout.")
        pos = nx.spring_layout(G, k=1.5, iterations=100)

    nx.draw(G, pos, with_labels=True, node_color="skyblue",
            node_size=2500, font_size=8, font_weight='bold', edge_color="gray")

    plt.title(title)
    plt.tight_layout()
    plt.savefig(png_output)
    print(f"Static graph saved to: {png_output.resolve()}")
    plt.show()

    net = Network(height="750px", width="100%", directed=True, notebook=False)
    net.barnes_hut()

    for node in G.nodes():
        net.add_node(node, label=node)

    for source, target in G.edges():
        net.add_edge(source, target)

    net.set_options("""
    var options = {
      "edges": {
        "arrows": {
          "to": {
            "enabled": true
          }
        },
        "smooth": false
      },
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "UD",
          "sortMethod": "hubsize"
        }
      },
      "physics": {
        "hierarchicalRepulsion": {
          "nodeDistance": 120
        },
        "minVelocity": 0.75
      }
    }
    """)
    
    net.show(html_output, notebook=False)
    print(f"Interactive graph saved to: {html_path.resolve()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate function dependency graph for one or more Python files.")
    parser.add_argument("file_paths", nargs="+", type=str, help="One or more Python file paths to analyze")
    parser.add_argument("--html_output", type=str, help="Filename for the interactive HTML output")

    args = parser.parse_args()

    # If multiple files, default output name can be "multi_dependency_graph.html"
    if args.html_output:
        html_output = args.html_output
    else:
        if len(args.file_paths) == 1:
            html_output = f"{Path(args.file_paths[0]).stem}_dependency_graph.html"
        else:
            html_output = "multi_dependency_graph.html"

    G = build_multi_file_dependency_graph(args.file_paths)
    draw_graph(G, title="Function Dependency Graph", html_output=html_output)
