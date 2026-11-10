"""raise_to_fixed_outfalls (user decision 12-Oct-2026) against the the original scripts method plan_for_fixed_outfalls,
both followed by economise_sizes, on synthetic networks (flat and falling ground).

  - wherever the old method reaches the fixed level, the new one reaches it too, at equal or lower pipe cost;
  - the new result is never below the free design (old: all pipes 2600 mm and a LOWER outfall when it failed);
  - when the level cannot be reached it says so, and keeps the highest design found.
"""
import pytest

from sewer_app import design as nd
from sewer_app import pipeline

from synthetic import INP, synth

CASES = [(1, 0.0), (2, 0.0), (3, 0.002)]
RISES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.35, 0.60]
quiet = lambda s: None                                                  # noqa: E731


def setup(seed, slope):
    out = pipeline.run(synth(seed=seed, ground_slope=slope), INP, log=quiet)
    return out, (out["data"], out["ground"], out["rules"], out["catalog"][2])


def designed(method, args, fixed, xy):
    data, ground, R, sizes = args
    mm, r, lines = method(data, ground, R, sizes, fixed, quiet, xy)
    if mm:
        mm, r, _ = nd.economise_sizes(data, ground, R, sizes, fixed, mm, r, quiet, xy)
    return r, lines


@pytest.mark.parametrize("seed,slope", CASES)
def test_never_worse_than_old_method(seed, slope):
    out, args = setup(seed, slope)
    free = out["node_info"]["OUT"]["invert"]
    for rise in RISES:
        fixed = {"OUT": free + rise}
        old, _ = designed(nd.plan_for_fixed_outfalls, args, fixed, out["xy"])
        new, lines = designed(nd.raise_to_fixed_outfalls, args, fixed, out["xy"])
        inv_old, inv_new = old[2]["OUT"]["invert"], new[2]["OUT"]["invert"]
        assert inv_new >= free - 1e-9, (rise, "below the free design")
        if inv_old >= fixed["OUT"] - 0.001:
            assert inv_new >= fixed["OUT"] - 0.001, (rise, "old reached the level, new did not")
            assert nd.pipe_cost(new[0], args[3]) <= nd.pipe_cost(old[0], args[3]) + 1, (rise, "dearer than old")
        if inv_new < fixed["OUT"] - 0.001:
            assert any("NOT reachable" in ln for ln in lines)


def test_flat_case_reached_where_old_method_failed():
    """Flat ground, +0.25 m: the old method gave 2600 mm pipes everywhere (Rs 1182 lakh, outfall 0.67 m LOWER
    than the free design); about 38 lakh with a >= 500 mm main sewer reaches it."""
    out, args = setup(1, 0.0)
    fixed = {"OUT": out["node_info"]["OUT"]["invert"] + 0.25}
    old, _ = designed(nd.plan_for_fixed_outfalls, args, fixed, out["xy"])
    new, _ = designed(nd.raise_to_fixed_outfalls, args, fixed, out["xy"])
    assert old[2]["OUT"]["invert"] < fixed["OUT"] - 0.001
    assert new[2]["OUT"]["invert"] >= fixed["OUT"] - 0.001
    assert nd.priced_cost(new[0])[0] < 40e5
