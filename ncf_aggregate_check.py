"""NCF aggregate check for File No. 4-927 comment (Figures 7 to 9; Attachment F,
section 6.2). Run: python3 ncf_aggregate_check.py   (standard library only)
Inputs from the Order: n.72 tier-average daily volumes; section II.F limits.
Block times are approximate protocol parameters, not measurements. The share
price ($100) and the 252 trading days are the author's assumptions.
Hypothetical arithmetic only; not market data."""
T1, T2 = 3_022_668, 1_207_978        # tier-average daily volume (Order n.72)
c1, c2 = 0.0025, 0.025               # per-symbol limits (Order section II.F)
N1, N2 = 75, 250                     # maximum symbols (Order section II.F)

# Figure 7: blocks or slots in the ten-minute window (600 seconds)
for chain, secs in (("Ethereum", 12), ("Base", 2), ("Solana", 0.4)):
    print("blocks in ten minutes", chain, round(600 / secs))

# Figure 8 and Attachment F section 6.2: aggregate share A_s = M x c_s
for m in (1, 4, 10, 20):
    print("M =", m, "Tier 1 %g%%" % (100 * c1 * m), "Tier 2 %g%%" % (100 * c2 * m))

# Figure 9: maximum shares per day for one TSV, and a dollar scale
s1, s2 = N1 * c1 * T1, N2 * c2 * T2
print("shares/day", int(s1 + 0.5), int(s2 + 0.5), "Tier 2 share %.1f%%" % (100 * s2 / (s1 + s2)),
      "ratio %.1f" % (s2 / s1))
print("dollars/day at $100: %.1f million" % ((s1 + s2) * 100 / 1e6))
print("dollars/yr at $100, 252 days: %.1f billion" % ((s1 + s2) * 100 * 252 / 1e9))
