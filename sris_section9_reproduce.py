"""Reproduce the Section 9 worked example of SRIS-1 (Attachment F) from the
pool state filed in Attachment E. Pure Python 3, standard library only.

Pool: TSLAx/USDC 0.30% Uniswap V3, Ethereum mainnet block 26112406.
token0 = TSLAx (18 decimals), token1 = USDC (6 decimals). A purchase of TSLAx
with USDC raises sqrt(P), where P is raw token1 per raw token0.
Network fees and any trade outside the filed state are ignored.
"""
import math

DEC0, DEC1 = 18, 6
FEE = 0.003
TICK = -216076                     # current_tick, Attachment E
L_ACTIVE = 668915148720368         # active_liquidity, Attachment E
# initialized ticks above the current tick and their liquidityNet (Attachment E)
UP_TICKS = [(-216060, -656236551294490), (-214140, -10099418942072),
            (887220, -2579178483806)]
LOWER_EDGE = -216120               # initialized tick below, liquidityNet +656236551294490


def sqrtp(tick):
    return 1.0001 ** (tick / 2.0)


def usdc_per_tsla(sp):             # human price from raw sqrt price
    return sp * sp * 10 ** (DEC0 - DEC1)


def buy(usdc):
    """Spend `usdc` USDC (fee taken from input) and walk ticks upward."""
    remaining = usdc * 10 ** DEC1 * (1 - FEE)       # raw USDC after fee
    sp, liq = sqrtp(TICK), float(L_ACTIVE)
    tsla_out = 0.0
    for tk, net in UP_TICKS:
        sp_next = sqrtp(tk)
        need = liq * (sp_next - sp)                  # raw USDC to reach next tick
        if remaining <= need:
            sp_new = sp + remaining / liq
            tsla_out += liq * (1 / sp - 1 / sp_new)
            sp = sp_new
            remaining = 0
            break
        tsla_out += liq * (1 / sp - 1 / sp_next)
        remaining -= need
        sp, liq = sp_next, liq + net                 # cross tick
    return tsla_out / 10 ** DEC0, sp


p0 = usdc_per_tsla(sqrtp(TICK))
print("pool-implied price at current tick: %.4f" % p0)
print("active range lower edge: %.4f" % usdc_per_tsla(sqrtp(LOWER_EDGE)))
print("active range upper edge: %.4f" % usdc_per_tsla(sqrtp(-216060)))
need_net = L_ACTIVE * (sqrtp(-216060) - sqrtp(TICK)) / 10 ** DEC1
print("USDC needed to reach upper edge (excluding fee): %.2f" % need_net)
print("USDC needed to reach upper edge (including fee): %.2f" % (need_net / (1 - FEE)))
print("TSLAx needed to reach lower edge (excluding fee): %.4f" % (
    L_ACTIVE * (1 / sqrtp(LOWER_EDGE) - 1 / sqrtp(TICK)) / 10 ** DEC0))
print("liquidity above upper edge / active: %.1f%%" %
      (100 * (L_ACTIVE - 656236551294490) / L_ACTIVE))
print()
print("%8s %12s %10s %12s" % ("USDC", "avg price", "premium", "pool move"))
for usd in (1, 5, 10, 25, 50, 100):
    out, sp = buy(usd)
    avg = usd / out
    print("%8d %12.4f %9.2f%% %11.2f%%" %
          (usd, avg, 100 * (avg / p0 - 1), 100 * (usdc_per_tsla(sp) / p0 - 1)))


def size_within(max_premium):
    """Largest USDC purchase whose premium to the starting price stays at or
    below max_premium (bisection; premium rises with order size)."""
    lo, hi = 1.0, 60.0
    for _ in range(60):
        mid = (lo + hi) / 2
        out, _sp = buy(mid)
        if mid / out / p0 - 1 <= max_premium:
            lo = mid
        else:
            hi = mid
    return lo


print()
print("largest purchase within 50 bp of starting price: $%.2f" % size_within(0.005))
print("largest purchase within 100 bp of starting price: $%.2f" % size_within(0.010))
