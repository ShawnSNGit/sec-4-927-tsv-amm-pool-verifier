"""Arithmetic for Section 9.2 of Attachment F (SRIS-1): the cost to a
constant-product pool of a jump in the reference price (Equation 7), and the
turnover needed to cover the continuous-time term of Equation 8.
No market data are used. Every input below is an assumption, not an estimate.
Python 3 standard library only."""
from math import sqrt

POOL_VALUE = 2_000_000                 # dollars; same capital as Figure 3 (assumed)
FEE = 0.003                            # 0.30 percent fee tier (assumed)
JUMPS = [0.25, 0.50, 1.00, -0.30, -0.50]   # jump J in the reference price (assumed)
SIGMAS = [0.40, 0.60, 0.80]            # annual volatility of the reference (assumed)


def psi(j):
    """Equation 7: fraction of pool value lost to arbitrage after a jump J."""
    return (sqrt(1.0 + j) - 1.0) ** 2 / 2.0


print("%-8s %-10s %-12s %-10s" % ("J", "Psi(J)", "dollars", "J^2/8"))
for j in JUMPS:
    print("%+.2f    %8.3f%%  %11s  %8.3f%%" % (
        j, 100 * psi(j), "{:,.0f}".format(psi(j) * POOL_VALUE), 100 * j * j / 8))

print()
print("%-8s %-12s %-30s" % ("sigma", "sigma^2/8", "turnover needed (x pool/yr)"))
for s in SIGMAS:
    lvr = s * s / 8.0
    print("%.2f     %8.3f%%    %8.1f" % (s, 100 * lvr, lvr / FEE))
