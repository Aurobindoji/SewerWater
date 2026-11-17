"""design._Paths (numpy, 17-Nov-2026) gives what design._path_table (the plain loop it replaced in the design rounds)
gives: random networks with loops, equal heads, fixed pipes, junctions without a head and two sources."""
import random

from water_app import design


def _case(seed):
    rnd = random.Random(seed)
    n = rnd.randint(5, 120)
    nodes = {f"N{i}": {} for i in range(n)}
    srcs = rnd.sample(list(nodes), 2 if n > 10 else 1)
    for s in srcs:
        nodes[s]["head"] = 100.0
    pipes = {}
    ids = list(nodes)
    for i in range(1, n):                                    # a tree, then a few loops and a parallel pipe
        pipes[f"P{i}"] = {"a": ids[rnd.randrange(i)], "b": ids[i]}
    for k in range(rnd.randint(0, n // 4)):
        a, b = rnd.sample(ids, 2)
        pipes[f"L{k}"] = {"a": a, "b": b}
    if n > 3:
        p = rnd.choice(list(pipes))
        pipes["PAR"] = dict(pipes[p])
    for p in pipes.values():
        p["fixed"] = rnd.random() < 0.15
    net = {"nodes": nodes, "pipes": pipes}
    levels = [rnd.choice([50.0, 60.0, 70.0, 80.0, 90.0]) for _ in ids]      # few values: many equal heads
    head = {nm: (100.0 if nm in srcs else levels[i]) for i, nm in enumerate(ids) if rnd.random() > 0.05 or nm in srcs}
    hl = {p: rnd.choice([1.0, 2.0, 3.0, rnd.random()]) for p in pipes}
    return net, {"head": head, "hl_per_km": hl}, set(srcs)


def test_paths_match_the_loop():
    for seed in range(300):
        net, res, fixed = _case(seed)
        adj = {n: [] for n in net["nodes"]}
        for pid, p in net["pipes"].items():
            adj[p["a"]].append((pid, p["b"]))
            adj[p["b"]].append((pid, p["a"]))
        want = design._path_table(net, res, adj, fixed)
        got = design._Paths(net, adj, fixed).table(res, list(res["head"]))
        assert got == want, seed
