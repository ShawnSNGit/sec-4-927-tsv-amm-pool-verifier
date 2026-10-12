"""Unit tests for the corrected SRIS-1 specification (Attachment F, Sections 4 to 5).
 
Pure Python 3 plus numpy. No random numbers are used, so every run gives the same output.
Run: python3 sris_tests.py
"""
import math
import numpy as np
 
FEE = 0.003
 
 
# ---------------------------------------------------------------- choice model
def mnl(V, mu):
    """Multinomial logit probabilities (Equation 2)."""
    z = np.asarray(V, dtype=float) / mu
    z -= z.max()                      # numerical stability
    e = np.exp(z)
    return e / e.sum()
 
 
def nested_logit(V, nests, lam, mu):
    """Two-level nested logit. nests: list of index lists; lam: scale per nest."""
    V = np.asarray(V, dtype=float)
    D = []
    for g, idx in enumerate(nests):
        D.append(np.exp(V[idx] / (lam[g] * mu)).sum())
    D = np.array(D)
    Pg = D ** np.array(lam) / (D ** np.array(lam)).sum()
    P = np.zeros(len(V))
    for g, idx in enumerate(nests):
        P[idx] = np.exp(V[idx] / (lam[g] * mu)) / D[g] * Pg[g]
    return P
 
 
def test_logit_sums_to_one():
    P = mnl([-0.1074, -0.0774, 0.0], 0.05)
    assert abs(P.sum() - 1) < 1e-12
    return f"logit probabilities sum to {P.sum():.12f}"
 
 
def test_identical_venues_equal_shares():
    P = mnl([1.0, 1.0, 1.0, 1.0], 0.05)
    assert np.allclose(P, 0.25)
    return f"four identical venues -> shares {P.round(4).tolist()}"
 
 
def test_wealth_and_constant_taste_cancel():
    """w_i and a venue-invariant delta_i add the same constant to every V_iv, so P_iv is unchanged."""
    V = np.array([-0.1074, -0.0774, 0.0])
    P0 = mnl(V, 0.05)
    P1 = mnl(V + 123456.78, 0.05)
    assert np.allclose(P0, P1, atol=1e-12)
    return "adding a venue-invariant constant leaves P_iv unchanged (max diff %.2e)" % np.abs(P0 - P1).max()
 
 
def test_nested_reduces_to_mnl():
    V = [0.2, 0.1, -0.1, 0.0]
    Pn = nested_logit(V, [[0, 3], [1, 2]], [1.0, 1.0], 0.05)
    Pm = mnl(V, 0.05)
    assert np.allclose(Pn, Pm)
    return "nested logit with lambda = 1 equals multinomial logit (max diff %.2e)" % np.abs(Pn - Pm).max()
 
 
def test_iia_and_nesting():
    """Cloning a TSV under MNL takes share from every venue in proportion (IIA). Under nested logit
    with lambda_1 < 1 the clone takes proportionally more from the TSV nest."""
    base = [0.0, 0.0, 0.0]                       # incumbent, outside option, TSV A
    clone = base + [0.0]                         # add TSV B identical to A
    P0 = mnl(base, 0.05)
    P1 = mnl(clone, 0.05)
    iia_ratio_0 = P0[0] / P0[1]
    iia_ratio_1 = P1[0] / P1[1]
    assert abs(iia_ratio_0 - iia_ratio_1) < 1e-12
    Pn0 = nested_logit(base, [[0, 1], [2]], [1.0, 0.5], 0.05)
    Pn1 = nested_logit(clone, [[0, 1], [2, 3]], [1.0, 0.5], 0.05)
    loss_incumbent_mnl = P0[0] - P1[0]
    loss_incumbent_nl = Pn0[0] - Pn1[0]
    assert loss_incumbent_nl < loss_incumbent_mnl
    return ("IIA ratio incumbent/outside unchanged under MNL (%.4f vs %.4f); "
            "incumbent share lost to a clone: MNL %.4f, nested (lambda_TSV=0.5) %.4f"
            % (iia_ratio_0, iia_ratio_1, loss_incumbent_mnl, loss_incumbent_nl))
 
 
# ---------------------------------------------------------------- risk treatment
def gamma_cara(p, z, rho):
    """Exact CARA certainty-equivalent cost of a Bernoulli loss of size z with probability p."""
    if rho == 0:
        return p * z
    return math.log(1 - p + p * math.exp(rho * z)) / rho
 
 
def test_gamma_limits_and_expansion():
    p, z = 0.02, 1000.0
    assert abs(gamma_cara(p, z, 0.0) - p * z) < 1e-12
    assert abs(gamma_cara(p, z, 1e-9) - p * z) < 1e-5            # rho -> 0 gives expected loss
    # small rho z: second-order mean-variance expansion is accurate
    rho = 0.0002                                                  # rho z = 0.2
    exact = gamma_cara(p, z, rho)
    mv = p * z + 0.5 * rho * p * (1 - p) * z * z
    err_small = abs(exact - mv) / exact
    assert err_small < 0.01
    # large rho z: the expansion understates the premium for a rare large loss
    rho = 0.005                                                   # rho z = 5
    exact_big = gamma_cara(p, z, rho)
    mv_big = p * z + 0.5 * rho * p * (1 - p) * z * z
    assert exact_big > mv_big
    return ("rho*z=0.2: exact %.4f vs mean-variance %.4f (rel. error %.3f%%); "
            "rho*z=5: exact %.4f vs mean-variance %.4f (mean-variance understates by %.1f%%)" %
            (gamma_cara(p, z, 0.0002), p * z + 0.5 * 0.0002 * p * (1 - p) * z * z, 100 * err_small,
             exact_big, mv_big, 100 * (exact_big - mv_big) / exact_big))
 
 
# ---------------------------------------------------------------- belief link
def logit(x):
    return math.log(x / (1 - x))
 
 
def expit(x):
    return 1 / (1 + math.exp(-x))
 
 
def p_hat(p_true, p_prior, omega):
    """Perceived probability: log-odds weighted average of the investor's prior and the true probability."""
    return expit((1 - omega) * logit(p_prior) + omega * logit(p_true))
 
 
def test_belief_link():
    pt, p0 = 0.02, 0.005
    assert abs(p_hat(pt, p0, 0.0) - p0) < 1e-12
    assert abs(p_hat(pt, p0, 1.0) - pt) < 1e-12
    mid = p_hat(pt, p0, 0.5)
    assert p0 < mid < pt
    # supervision-only rule: true p falls, omega unchanged
    base = p_hat(0.02, p0, 0.0)
    sup = p_hat(0.012, p0, 0.0)
    assert abs(base - sup) < 1e-12        # an uninformed investor does not notice
    # disclosure-only rule: omega rises, true p unchanged
    disc = p_hat(0.02, p0, 0.6)
    assert disc > base
    return ("omega=0 -> %.4f (prior), omega=1 -> %.4f (truth), omega=0.5 -> %.4f; "
            "supervision-only change leaves an uninformed investor at %.4f; "
            "disclosure-only change moves it to %.4f"
            % (p_hat(pt, p0, 0.0), p_hat(pt, p0, 1.0), mid, sup, disc))
 
 
# ---------------------------------------------------------------- AMM execution
def cp_buy(d, x=1e6, y=1e6, fee=FEE):
    """Constant-product pool: pay d of the paired asset, receive tokens (fee taken from the input)."""
    de = d * (1 - fee)
    return y * de / (x + de)
 
 
def test_cp_closed_form():
    d = 100_000.0
    out = cp_buy(d)
    premium = d / out - 1
    shortfall = 1 - out / d
    # net-of-fee impact I and the exact identity: premium = (f + I) / (1 - f)
    I = (d * (1 - FEE) / out) - 1
    assert abs(premium - (FEE + I) / (1 - FEE)) < 1e-12
    # invariant check: product of reserves is unchanged by the net input
    x1, y1 = 1e6 + d * (1 - FEE), 1e6 - out
    assert abs(x1 * y1 - 1e12) < 1e-3
    assert abs(premium - 0.10303) < 1e-4 and abs(shortfall - 0.0934) < 1e-4
    return ("$100,000 buy: premium %.4f%%, shortfall %.4f%% (letter: 10.3%% and 9.34%%); "
            "(f+I)/(1-f) identity holds; "
            "reserve product preserved" % (100 * premium, 100 * shortfall))
 
 
def test_v3_single_range_matches_virtual_reserves():
    L, P0, f = 5.0e6, 1.0, FEE
    dy = 1000.0
    sp0 = math.sqrt(P0)
    sp1 = sp0 + dy * (1 - f) / L
    x_out = L * (1 / sp0 - 1 / sp1)
    yv0, xv0 = L * sp0, L / sp0                  # virtual reserves
    yv1 = yv0 + dy * (1 - f)
    xv1 = L * L / yv1
    assert abs((xv0 - xv1) - x_out) < 1e-9
    diff = abs((xv0 - xv1) - x_out)
    return "single-range Equation 4 equals the virtual-reserve swap (diff %.2e)" % diff
 
 
def test_zero_cost_identical_venues():
    """With zero fee and effectively infinite depth, execution cost is zero and venues tie."""
    assert abs(cp_buy(100.0, 1e15, 1e15, 0.0) / 100.0 - 1.0) < 1e-9
    P = mnl([0.0 - 0.0] * 3, 0.05)
    assert np.allclose(P, 1 / 3)
    return "zero-fee, near-infinite-depth pool executes at the reference price; venues tie at 1/3"
 
 
# ---------------------------------------------------------------- LVR jump formula
def psi(J):
    return (math.sqrt(1 + J) - 1) ** 2 / 2
 
 
def test_psi_against_direct_pool_value():
    for J in (0.5, 1.0, -0.5, 0.05, -0.1):
        k = 0.25
        pool_value = 2 * math.sqrt(k * (1 + J))
        rebalanced = 0.5 * (1 + J) + 0.5
        assert abs((rebalanced - pool_value) - psi(J)) < 1e-12
    small = psi(0.01) / (0.01 ** 2 / 8)
    assert abs(small - 1) < 0.01
    dbl, half = psi(1.0), psi(-0.5)
    assert abs(2_000_000 * dbl - 171573) < 1.0
    return ("Psi(J) equals rebalanced value minus pool value for J in {0.5, 1, -0.5, 0.05, -0.1}; "
            "Psi(0.01)/(J^2/8) = %.4f; doubling costs %.4f%% ($%.0f on $2M), halving %.4f%%"
            % (small, 100 * dbl, 2_000_000 * dbl, 100 * half))
 
 
# ---------------------------------------------------------------- Attachment E pool (Uniswap V3)
DEC0, DEC1 = 18, 6
TICK = -216076
L_ACTIVE = 668915148720368
UP_TICKS = [(-216060, -656236551294490), (-214140, -10099418942072), (887220, -2579178483806)]
 
 
def sqrtp(tick):
    return 1.0001 ** (tick / 2.0)
 
 
def buy_pool(usdc):
    remaining = usdc * 10 ** DEC1 * (1 - FEE)
    sp, liq, out = sqrtp(TICK), float(L_ACTIVE), 0.0
    for tk, net in UP_TICKS:
        sp_next = sqrtp(tk)
        need = liq * (sp_next - sp)
        if remaining <= need:
            sp_new = sp + remaining / liq
            out += liq * (1 / sp - 1 / sp_new)
            remaining = 0
            break
        out += liq * (1 / sp - 1 / sp_next)
        remaining -= need
        sp, liq = sp_next, liq + net
    return out / 10 ** DEC0
 
 
def test_attachment_e_premiums():
    p0 = sqrtp(TICK) ** 2 * 10 ** (DEC0 - DEC1)
    res = {}
    for usd in (10, 25, 50, 100):
        out = buy_pool(usd)
        res[usd] = 100 * ((usd / out) / p0 - 1)
    assert abs(res[10] - 0.37) < 0.01 and abs(res[25] - 3.43) < 0.01
    assert abs(res[50] - 15.79) < 0.01 and abs(res[100] - 68.77) < 0.01
    return ("start price %.4f USDC/TSLAx; premiums $10: %.2f%%, $25: %.2f%%, $50: %.2f%%, $100: %.2f%% "
            "(letter: 0.37, 3.43, 15.79, 68.77)" % (p0, res[10], res[25], res[50], res[100]))
 
 
# ---------------------------------------------------------------- equilibrium
def test_fixed_point_existence():
    """Illustrative scalar supply map (placeholders, not estimates): T(x) = Kbar * logistic((pi(x) - h)/s).
    pi rises with depth through lower impact, then falls as turnover per dollar of capital dilutes."""
    Kbar, h, s = 100.0, 0.02, 0.01
 
    def pi(x):
        return 0.12 * x / (1 + x) * (1 / (1 + 0.02 * x)) - 0.03
 
    def T(x):
        return Kbar / (1 + math.exp(-(pi(x) - h) / s))
 
    grid = np.linspace(0.0, Kbar, 20001)
    g = np.array([T(x) - x for x in grid])
    assert g[0] > 0 and g[-1] < 0     # T maps [0, Kbar] into itself: a fixed point exists
    roots = [float(grid[i]) for i in range(len(grid) - 1) if g[i] * g[i + 1] < 0]
 
    def damped(x0, theta=0.5, n=2000):
        x = x0
        for _ in range(n):
            x = (1 - theta) * x + theta * T(x)
        return x
 
    sols = sorted({round(damped(x0), 4) for x0 in (0.0, 5.0, 50.0, 100.0)})
    return ("illustrative scalar map: T(0) > 0 and T(Kbar) < Kbar guarantee a fixed point; "
            "sign changes on grid at %s; damped iteration from four starts ends at %s" % (
        [round(r, 3) for r in roots], sols))
 
 
TESTS = [
    test_logit_sums_to_one, test_identical_venues_equal_shares, test_wealth_and_constant_taste_cancel,
    test_nested_reduces_to_mnl, test_iia_and_nesting, test_gamma_limits_and_expansion, test_belief_link,
    test_cp_closed_form, test_v3_single_range_matches_virtual_reserves, test_zero_cost_identical_venues,
    test_psi_against_direct_pool_value, test_attachment_e_premiums, test_fixed_point_existence,
]
 
if __name__ == "__main__":
    passed = 0
    for t in TESTS:
        try:
            msg = t()
            print("PASS", t.__name__, "-", msg)
            passed += 1
        except AssertionError as e:
            print("FAIL", t.__name__, e)
    print("\n%d of %d tests passed" % (passed, len(TESTS)))
