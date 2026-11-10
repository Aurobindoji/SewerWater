"""economise_sizes redesigns only the part below the conduit it makes smaller (redesign_below).
It must give exactly what the the original scripts version gives, which redesigned the whole network every trial
(kept here as reference_economise)."""
import random

from sewer_app import design as nd
from sewer_app import pipeline

from synthetic import INP, synth


def reference_economise(data, ground, R, sizes, fixed, mmap, start, xy=None, max_trials=3000):
    """the original scripts sewer_design.economise_sizes (12-Oct-2026), unchanged apart from the log."""
    res0 = start[0]
    best_cost, depth_cap = nd.pipe_cost(res0, sizes), max(nd.max_depth(res0), R.max_depth or 0.0)
    ids = [z["id_mm"] for z in sizes if z["id_mm"] >= R.dmin - 0.5]

    def ok(r):
        res_, _, info_ = r
        if any(info_.get(o, {}).get("invert") is None or info_[o]["invert"] < f - 0.001 for o, f in fixed.items()):
            return False
        if nd.max_depth(res_) > depth_cap + 0.001:
            return False
        return not any("catalog size" in fl for d in res_.values() for fl in d["flags"])
    par = {d["from"]: (d["to"], d["length"]) for d in res0.values()}

    def dist(n):
        L = 0.0
        while n in par:
            n, l = par[n]
            L += l
        return L
    order = sorted(mmap, key=lambda lab: -dist(res0[lab]["from"]) if lab in res0 else 0)
    best, trials, improved = (dict(mmap), start), 0, True
    while improved and trials < max_trials:
        improved = False
        for lab in order:
            cur = best[0].get(lab)
            if cur is None:
                continue
            smaller = [d for d in ids if d < cur - 0.5]
            trial = dict(best[0])
            if smaller:
                trial[lab] = smaller[-1]
            else:
                trial.pop(lab)
            r = nd.design_network(data, ground, R, sizes, trial, xy)
            trials += 1
            c = nd.pipe_cost(r[0], sizes)
            if ok(r) and c < best_cost - 1:
                best, best_cost, improved = (trial, r), c, True
            if trials >= max_trials:
                break
    return best[0], best[1]


def same(a, b):
    ra, ia, na = a
    rb, ib, nb = b
    assert list(ra) == list(rb)
    for k in ra:
        x, y = ra[k], rb[k]
        assert (x["D"], x["up"], x["dn"], x["slope"], x["flags"], x["gov"]) == \
               (y["D"], y["up"], y["dn"], y["slope"], y["flags"], y["gov"]), k
    assert ia == ib
    assert na == nb


def test_redesign_below_equals_full_design():
    out = pipeline.run(synth(), INP, log=lambda s: None)
    data, ground, xy, R, sizes = out["data"], out["ground"], out["xy"], out["rules"], out["catalog"][2]
    plan = nd.Plan(data)
    base = nd.design_network(data, ground, R, sizes, {}, xy, plan=plan)
    rnd = random.Random(7)
    for lab in rnd.sample(sorted(base[0]), 25):
        mm = {lab: base[0][lab]["D"] + 200}
        same(nd.redesign_below(base, lab, plan, ground, R, sizes, mm, xy),
             nd.design_network(data, ground, R, sizes, mm, xy, plan=plan))


def test_economise_same_as_full_redesign():
    net = synth()
    out = pipeline.run(net, INP, log=lambda s: None)
    data, ground, xy, R, sizes = out["data"], out["ground"], out["xy"], out["rules"], out["catalog"][2]
    fixed = {"OUT": 96.35}                      # free design reaches 96.275: needs enlarged pipes
    mmap, start, _ = nd.plan_for_fixed_outfalls(data, ground, R, sizes, fixed, lambda s: None, xy)
    assert mmap and start[2]["OUT"]["invert"] >= 96.35 - 0.001
    m_new, r_new, lines = nd.economise_sizes(data, ground, R, sizes, fixed, mmap, start, lambda s: None, xy)
    m_ref, r_ref = reference_economise(data, ground, R, sizes, fixed, mmap, start, xy)
    assert m_new == m_ref
    same(r_new, r_ref)
    assert "size reductions kept" in lines[0] and " 0 size reductions" not in lines[0]
