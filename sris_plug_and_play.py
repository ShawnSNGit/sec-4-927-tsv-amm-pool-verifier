"""Plug-and-play scoring of one rule with SRIS-1 (Attachment F), run on the
pool state filed in Attachment E. Pure Python 3, standard library only.

What is real: the pool state (TSLAx/USDC 0.30% Uniswap V3, Ethereum mainnet
block 26112406) and the execution cost walked from it (Equations 4 and 5).
What is a placeholder: every entry of PLACEHOLDER below. They are not
estimates. Replace them with the priors in Appendix A and rerun.
Network fees and any trade outside the filed state are ignored.
"""
import math

# ---- Real input: filed pool state (same as Appendix C) --------------------
DEC0, DEC1, FEE = 18, 6, 0.003
TICK, L_ACTIVE = -216076, 668915148720368
UP_TICKS = [(-216060, -656236551294490), (-214140, -10099418942072),
            (887220, -2579178483806)]


def sqrtp(tick):
    return 1.0001 ** (tick / 2.0)


def price(sp):
    return sp * sp * 10 ** (DEC0 - DEC1)


def buy(usdc):
    """Spend usdc USDC (fee taken from input), walk ticks upward."""
    rem = usdc * 10 ** DEC1 * (1 - FEE)
    sp, liq, out = sqrtp(TICK), float(L_ACTIVE), 0.0
    for tk, net in UP_TICKS:
        nxt = sqrtp(tk)
        need = liq * (nxt - sp)
        if rem <= need:
            new = sp + rem / liq
            out += liq * (1 / sp - 1 / new)
            break
        out += liq * (1 / sp - 1 / nxt)
        rem -= need
        sp, liq = nxt, liq + net
    return out / 10 ** DEC0


P0 = price(sqrtp(TICK))


def exec_cost_per_dollar(q):
    """Equation 5 with g_v = d_v = 0: realized premium to the start price,
    fee included, for a purchase of q USDC."""
    return q / buy(q) / P0 - 1


# ---- Placeholders (NOT estimates): edit these and rerun ---------------------
PLACEHOLDER = dict(
    q=10.0,        # order size in USDC; also the position s_i
    B=0.05,        # B_iv, value of access, USD
    C=0.00,        # C_iv, explicit cost beyond the pool fee, USD
    rho=0.0,       # rho_i, risk aversion (Var(X) set to 0 below)
    var_X=0.0,     # Var(X_iv), Equation 6 inputs are uncalibrated
    tau0=0.02,     # tau_iv before the rule, access friction, USD
    d_tau=0.01,    # extra friction from the rule's identity checks, USD
    ell=0.50,      # l_i, loss given a protection failure, share of position
    p0=0.020,      # p^0_{e,v}, failure probability with no rule, event e
    eps=0.40,      # epsilon_{e,k}, effectiveness of condition k against e
    c_k=1.0,       # c_k(R), compliance intensity of condition k, in [0, 1]
    mu=0.05,       # mu, taste-shock scale in Equation 2
    N=1000,        # N_i, people represented by this synthetic investor
)


def score(rule_on, pp=PLACEHOLDER):
    q = pp["q"]
    EX = exec_cost_per_dollar(q) * q                    # E[X_iv], USD
    p = pp["p0"] * (1 - pp["eps"] * pp["c_k"]) if rule_on else pp["p0"]  # Eq 11
    tau = pp["tau0"] + (pp["d_tau"] if rule_on else 0.0)
    prot = p * pp["ell"] * q                            # p ell s, USD
    V = (pp["B"] - pp["C"] - EX - 0.5 * pp["rho"] * pp["var_X"]
         - prot - tau)                                   # Eq 1, w and delta drop out
    P = math.exp(V / pp["mu"]) / (math.exp(V / pp["mu"]) + 1.0)  # Eq 2, outside option V0 = 0
    H = pp["N"] * P * p * pp["ell"] * q                 # Eq 12, one venue, one event
    return dict(EX=EX, p=p, tau=tau, prot=prot, V=V, P=P, H=H)


if __name__ == "__main__":
    print("pool-implied price: %.4f USDC per TSLAx" % P0)
    print("order of $%.0f: premium %.2f%%, E[X] = $%.4f" % (
        PLACEHOLDER["q"], 100 * exec_cost_per_dollar(PLACEHOLDER["q"]),
        exec_cost_per_dollar(PLACEHOLDER["q"]) * PLACEHOLDER["q"]))
    a, b = score(False), score(True)
    print("%-34s %12s %12s %12s" % ("", "no rule", "rule", "change"))
    for k, lab in (("p", "true failure probability p"),
                   ("prot", "p*ell*s, USD"), ("tau", "tau, USD"),
                   ("V", "utility V (USD, w and delta out)"),
                   ("P", "probability of using the TSV"),
                   ("H", "expected harm H, USD")):
        print("%-34s %12.4f %12.4f %12.4f" % (lab, a[k], b[k], b[k] - a[k]))
