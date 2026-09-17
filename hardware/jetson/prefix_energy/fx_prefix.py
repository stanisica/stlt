"""Head-submodule extraction for STLT split points.

A split at index k puts FX nodes 0..k on the satellite. The head submodule
returned here executes exactly those nodes and outputs the cut producers, i.e.
the activations a ground-side node still consumes. This is the same cut
definition as GRAVARA/dagcut.py (D_cut), so the measured prefix corresponds
one-to-one with the W(l), D(l) pair recorded in TORCHFX_TABLE.json.
"""

from __future__ import annotations

import copy

import torch

MODELS = ["squeezenet1_1", "swin_v2_t", "efficientnet_b4", "resnet50", "densenet169"]

_FAR = 1 << 30  # sentinel index for the fx output node (always ground side)


def build_traced(model_name, input_shape=(1, 3, 224, 224), weights=None):
    """symbolic_trace + ShapeProp, matching GRAVARA/dagcut.build_graph_fx."""
    import torchvision.models as tvm
    from torch.fx import symbolic_trace
    from torch.fx.passes.shape_prop import ShapeProp

    model = getattr(tvm, model_name)(weights=weights)
    model.eval()
    gm = symbolic_trace(model)
    ShapeProp(gm).propagate(torch.randn(*input_shape))
    return gm


def indexed_nodes(gm):
    """Compute nodes in graph order; the fx output node is excluded."""
    return [n for n in gm.graph.nodes if n.op != "output"]


def is_weight(node):
    return node.op == "get_attr"


def node_shape(node):
    tm = node.meta.get("tensor_meta", None)
    if tm is None:
        return None
    if hasattr(tm, "shape"):
        return tuple(tm.shape)
    return None


def valid_split_indices(gm):
    """Indices carrying a real activation, i.e. meaningful split points."""
    return [
        k
        for k, n in enumerate(indexed_nodes(gm))
        if not is_weight(n) and node_shape(n) is not None
    ]


def cut_producer_indices(gm, k):
    """Head nodes at or before k whose output is read on the ground side."""
    seq = indexed_nodes(gm)
    idx = {n: i for i, n in enumerate(seq)}
    out = []
    for i in range(k + 1):
        p = seq[i]
        if is_weight(p):
            continue
        if any(idx.get(u, _FAR) > k for u in p.users):
            out.append(i)
    return out


def prefix_module(gm, k):
    """Return (head GraphModule, cut producer indices) for a split at index k.

    The head is a standalone GraphModule holding nodes 0..k. Its output is the
    tuple of cut producers, so nothing downstream of the split is executed.
    """
    head = copy.deepcopy(gm)
    seq = indexed_nodes(head)
    idx = {n: i for i, n in enumerate(seq)}

    outs = [
        n
        for i, n in enumerate(seq[: k + 1])
        if not is_weight(n) and any(idx.get(u, _FAR) > k for u in n.users)
    ]
    if not outs:
        # Full model: the last node feeds only the fx output node.
        outs = [seq[k]]

    output_node = next(n for n in head.graph.nodes if n.op == "output")
    output_node.args = (tuple(outs),)

    for n in reversed(seq[k + 1 :]):
        head.graph.erase_node(n)

    head.graph.lint()
    head.recompile()
    head.eval()
    return head, [idx[n] for n in outs]


def cumulative_flops(gm, input_shape=(1, 3, 224, 224)):
    """Cumulative FLOPs W(k) per node index, matching GRAVARA/dagcut.

    fvcore counts multiply-accumulates; the paper convention is
    W_GFLOPs = 2 * MACs. This returns raw MACs; callers apply the factor.
    """
    from fvcore.nn import FlopCountAnalysis

    fca = FlopCountAnalysis(gm, torch.randn(*input_shape))
    fca.unsupported_ops_warnings(False)
    fca.uncalled_modules_warnings(False)
    by_mod = fca.by_module()

    out, run = [], 0
    for n in indexed_nodes(gm):
        if n.op == "call_module":
            run += by_mod.get(str(n.target), 0)
        out.append(run)
    return out


def d_cut_bits(gm, k, dtype_bits=32, spatial_scale=1.0):
    """Deduplicated DAG cut size in bits for a split at index k.

    spatial_scale rescales cuts whose activation carries spatial dimensions
    (4D NCHW tensors), so a graph shape-propagated at a small resolution can
    report the cut size at a larger operating resolution without running the
    expensive high-resolution ShapeProp. Feature-map area scales exactly with
    input pixel count; resolution-invariant cuts (e.g. post-pool [N, C] logits)
    are left unscaled.
    """
    seq = indexed_nodes(gm)
    total = 0
    for i in cut_producer_indices(gm, k):
        shape = node_shape(seq[i])
        if shape is None:
            continue
        n = 1
        for d in shape:
            n *= int(d)
        bits = n * dtype_bits
        if spatial_scale != 1.0 and len(shape) >= 4:
            bits = int(round(bits * spatial_scale))
        total += bits
    return total


def lower_hull_idx(W, D):
    """ANODA candidate set: lower convex hull of (W, D), Andrew monotone chain."""
    order = sorted(range(len(W)), key=lambda i: (W[i], D[i]))

    def cross(o, a, b):
        return (W[a] - W[o]) * (D[b] - D[o]) - (D[a] - D[o]) * (W[b] - W[o])

    h = []
    for i in order:
        while len(h) >= 2 and cross(h[-2], h[-1], i) <= 0:
            h.pop()
        h.append(i)
    return sorted(h)
