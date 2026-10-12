"""NCF addendum figures for File No. 4-927 comment (Figures A-C).
Run: python3 ncf_addendum_figs.py   (needs numpy, matplotlib)
Figure B is model output (Milionis et al. 2022 no-fee LVR rate), not market data.
Inputs taken from the Order: n.72 tier-average daily volumes; sec. II.F caps."""
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family": ["Liberation Sans", "DejaVu Sans"], "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})
NAVY, RED, GRAY, GREEN = "#1f3a5f", "#b03a2e", "#7f8c8d", "#2e7d5b"
 
# ---------- Figure A: disclosure follows dislocation ----------
st = [("1792", "Panic of 1792", "Buttonwood Agreement (May 17, 1792)"),
      ("1929-34", "Crash of 1929", "Securities Act (1933); Exchange Act (1934)"),
      ("1967-75", "Back-office 'paperwork crisis'", "1975 Amendments: sec. 11A and sec. 17A"),
      ("1987-88", "Oct. 19, 1987 market break", "Market-wide circuit breakers (1988)"),
      ("2010-12", "May 6, 2010 flash event", "Single-stock breakers, then LULD Plan"),
      ("2015", "Aug. 24, 2015 ETP dislocation", "Staff research note (Dec. 2015)"),
      ("2021-24", "Early-2021 settlement stress", "T+1 adopted 2023; effective May 28, 2024"),
      ("2026-31", "Sept. 17, 2026 Innovation Exemption", "Measure it: II.M data, section IX report")]
fig, ax = plt.subplots(figsize=(6.6, 4.0))
n = len(st); ax.set_xlim(0, 10); ax.set_ylim(-0.6, n + 0.9); ax.axis("off")
ax.text(0.1, n + 0.25, "Year", fontsize=8.5, fontweight="bold", color=GRAY)
ax.text(1.6, n + 0.25, "Market event", fontsize=8.5, fontweight="bold", color=RED)
ax.text(6.0, n + 0.25, "Rule or response", fontsize=8.5, fontweight="bold", color=NAVY)
ax.plot([0.1, 9.9], [n + 0.05, n + 0.05], color=GRAY, lw=0.8)
for i, (yr, ev, resp) in enumerate(st):
    y = n - 0.7 - i
    last = i == n - 1
    c = GREEN if last else NAVY
    if last:
        ax.axhspan(y - 0.42, y + 0.42, color="#e6f2ec", zorder=0)
    ax.text(0.1, y, yr, fontsize=8.5, fontweight="bold", color=c, va="center")
    ax.text(1.6, y, ev, fontsize=8.2, color=GREEN if last else RED, va="center")
    ax.annotate("", xy=(5.85, y), xytext=(5.45, y), arrowprops=dict(arrowstyle="->", color=GRAY, lw=1))
    ax.text(6.0, y, resp, fontsize=8.2, color=c, va="center")
ax.set_title("U.S. market-structure rules have repeatedly followed market stress",
             loc="left", fontweight="bold", fontsize=10.5)
fig.tight_layout(); fig.savefig("figA.png", dpi=200); plt.close()
 
# ---------- Figure B: fee income cap vs LVR ----------
FEE = 0.003; DAYS = 252
T1 = 3_022_668; CAP1 = 0.0025 * T1           # Order n.72, sec. II.F
PRICE = 100.0                                 # assumption, as in Figure 6
cap_usd_year = CAP1 * PRICE * DAYS
sig = np.array([0.20, 0.40, 0.60, 0.80, 1.00])
breakeven = (sig ** 2 / 8) / FEE              # annual volume / TVL needed (no-fee LVR rate)
fig, ax = plt.subplots(figsize=(6.4, 3.3))
bars = ax.bar([f"{int(s*100)}%" for s in sig], breakeven, color=NAVY, width=0.55)
for b, v in zip(bars, breakeven):
    ax.text(b.get_x() + b.get_width() / 2, v + 2.5, f"{v:.1f}x", ha="center", fontsize=8.5,
            bbox=dict(facecolor="white", edgecolor="none", pad=0.8))
handles = []
for tvl, col, lab in [(2e6, GREEN, "$2M"), (10e6, "#c9a227", "$10M"), (50e6, RED, "$50M")]:
    t = cap_usd_year / tvl
    h = ax.axhline(t, color=col, lw=1.4, ls="--", label=f"Tier 1 cap ceiling, {lab} pool value: {t:.1f}x")
    handles.append(h)
ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=7.6)
ax.set_ylim(0, 105)
ax.set_xlabel("Annualized volatility of the underlying stock (sigma)")
ax.set_ylabel("Annual volume / pool value")
ax.set_title("Fee income needed to offset LVR vs. what the Tier 1 cap allows", loc="left",
             fontweight="bold", fontsize=10.5)
fig.tight_layout(); fig.savefig("figB.png", dpi=200); plt.close()
print("cap USD/yr", round(cap_usd_year), [round(cap_usd_year / x, 2) for x in (2e6, 10e6, 50e6)],
      [round(float(b), 2) for b in breakeven])
 
# ---------- Figure C: record-date entitlement (T+1) ----------
fig, ax = plt.subplots(figsize=(6.6, 3.3))
ax.set_xlim(0, 10); ax.set_ylim(-0.8, 4.6); ax.axis("off")
ax.plot([0.4, 9.6], [2.3, 2.3], color=GRAY, lw=2)
ax.axvspan(5.2, 9.6, ymin=0.30, ymax=0.70, color="#f3e3e1", zorder=0)
ax.text(7.4, 3.55, "Ex-date = record date (T+1)", ha="center", fontsize=8.5, color=RED, fontweight="bold")
ax.text(2.7, 3.55, "Day before ex-date", ha="center", fontsize=8.5, color=NAVY, fontweight="bold")
ax.plot([5.2, 5.2], [1.5, 3.2], color=RED, lw=1.4, ls="--")
ax.text(5.2, 1.25, "Entitlement cut-off:\nlast block before the\nex-date begins", ha="center", va="top", fontsize=7.6, color=RED)
ax.plot([8.6, 8.6], [1.5, 3.2], color=GRAY, lw=1.4, ls=":")
ax.text(8.6, 1.25, "4:00 p.m. snapshot\n(the wrong cut-off)", ha="center", va="top", fontsize=7.6, color=GRAY)
ax.scatter([2.4], [2.3], s=70, color=GREEN, zorder=3)
ax.text(2.4, 2.65, "Buyer A buys\n(entitled)", ha="center", fontsize=7.8, color=GREEN)
ax.scatter([6.4], [2.3], s=70, color=RED, zorder=3)
ax.text(6.4, 2.65, "Buyer B buys on-chain\n(NOT entitled)", ha="center", fontsize=7.8, color=RED)
ax.text(5.0, -0.3, "On-chain settlement is instant, so Buyer B appears as a holder in the 4:00 p.m. snapshot.\nOnly the trade-date convention separates A from B.",
        ha="center", fontsize=7.6, color="#333333")
ax.set_title("Why the entitlement cut-off must follow the ex-date, not the closing bell", loc="left",
             fontweight="bold", fontsize=10.5)
fig.tight_layout(); fig.savefig("figC.png", dpi=200); plt.close()
 
