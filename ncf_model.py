"""NCF replication script for File No. 4-927 comment. Run: python3 ncf_model.py
Needs numpy, scipy, matplotlib. Figure 3D also reads real_pool_state.csv and
tick_liquidity_net.csv (Attachment E) from the same folder.
Hypothetical AMM models (Figures 2, 3, 3A, 5, 6A) are not market data. Figures 3B, 3C
and 5A plot values published by others (sources in the comments below). Figure 3D is
computed from pool state read from Ethereum (Attachments D and E)."""
import csv, math, collections, os
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import brentq
plt.rcParams.update({"font.family":"Liberation Sans","font.size":10,
                     "axes.spines.top":False,"axes.spines.right":False})
NAVY,RED,GRAY,GREEN,GOLD="#1f3a5f","#b03a2e","#7f8c8d","#2e7d5b","#c9a227"
FEE=0.003; CAP=2_000_000.0
SIZES=[100,1000,10000,100000]
OUT="figs/"; os.makedirs(OUT,exist_ok=True)
def save(fig,name,**kw): fig.tight_layout(**kw); fig.savefig(OUT+name,dpi=200,bbox_inches="tight"); plt.close(fig)
 
# ---------- constant-product model ----------
def cp_buy(d,x=1e6,y=1e6):
    de=d*(1-FEE); return y*de/(x+de)
def cp_sell_tokens(u,x=1e6,y=1e6):
    ue=u*(1-FEE); return x*ue/(y+ue)
# ---------- single-range concentrated-liquidity model ----------
def cl_params(w):
    pa,pb=1-w,1+w; L=CAP/(2-1/np.sqrt(pb)-np.sqrt(pa)); return L,pa,pb
def cl_buy(d,w):
    L,pa,pb=cl_params(w); de=d*(1-FEE); cap=L*(np.sqrt(pb)-1)
    if de<=cap:
        sp=1+de/L; return L*(1-1/sp),1.0,d
    return L*(1-1/np.sqrt(pb)),cap/(1-FEE)/d,cap/(1-FEE)
def cl_sell(d,w):
    L,pa,pb=cl_params(w); ue=d*(1-FEE); cap=L*(1/np.sqrt(pa)-1)
    if ue<=cap:
        isp=1+ue/L; return L*(1-1/isp),1.0,d
    return L*(1-np.sqrt(pa)),cap/(1-FEE)/d,cap/(1-FEE)
def shortfall_buy(d,w=None):
    if w is None: return (1-cp_buy(d)/d)*100,1.0
    out,fill,paid=cl_buy(d,w); return (1-out/paid)*100,fill
def shortfall_sell(d,w=None):
    if w is None: return (1-cp_sell_tokens(d)/d)*100,1.0
    out,fill,sold=cl_sell(d,w); return (1-out/sold)*100,fill
def roundtrip(d):
    o=cp_buy(d); xs=1e6+d; ys=1e6-o; ue=o*(1-FEE); return xs*ue/(ys+ue)
def stale_profit(g):
    P=1+g
    def marg(dx):
        de=dx*(1-FEE); xs=1e6+de; ys=1e6*1e6/xs; return (xs/ys)/(1-FEE)
    if P<=marg(0): return 0.0
    dx=brentq(lambda v: marg(v)-P,0,5e7); return cp_buy(dx)*P-dx
gaps=[0.5,1,2,5,10,20]; stale=[stale_profit(g/100) for g in gaps]
T1,T2=3_022_668,1_207_978                    # Order n.72 tier-average daily volumes (shares)
cap1,cap2=0.0025*T1,0.025*T2
RANGES=[("full_range_cp",None),("range_pm50",0.5),("range_pm20",0.2),("range_pm5",0.05),("range_pm1",0.01)]
 
# ---------- results table (Attachment A) ----------
rows=[["model","size_usd","buy_shortfall_pct","buy_fill","sell_shortfall_pct","sell_fill"]]
for name,w in RANGES:
    for s in SIZES:
        b=shortfall_buy(s,w); se=shortfall_sell(s,w)
        rows.append([name,s,round(float(b[0]),6),round(float(b[1]),4),round(float(se[0]),6),round(float(se[1]),4)])
csv.writer(open("ncf_model_results.csv","w",newline="")).writerows(rows)
 
# ---------- Figure 1: funding ----------
fig,ax=plt.subplots(figsize=(6.2,2.9))
ax.pie([100],colors=[GREEN],startangle=90,wedgeprops=dict(width=0.38,edgecolor="white"))
ax.text(0,0,"100%\nself-funded",ha="center",va="center",fontsize=11,fontweight="bold")
ax.legend([plt.Rectangle((0,0),1,1,color=GREEN)]+[plt.Rectangle((0,0),1,1,color="#dddddd")]*4,
  ["Author's own time and resources: 100%","TSVs, tokenizers, liquidity providers: 0%","Other industry or trade groups: 0%","Government or grants: 0%","Any other third party: 0%"],
  loc="center left",bbox_to_anchor=(1.0,0.5),frameon=False,fontsize=8.5)
ax.set_title("Funding of this comment (author's disclosure)",loc="left",fontweight="bold",fontsize=11)
save(fig,"fig1.png",)
 
# ---------- Figure 2: round trip vs one way ----------
ow=[shortfall_sell(s)[0] for s in SIZES]; rt=[(1-roundtrip(s)/s)*100 for s in SIZES]
fig,ax=plt.subplots(figsize=(6.2,3.5)); x=np.arange(4); w=0.38
b1=ax.bar(x-w/2,rt,w,color=GRAY,label="Round-trip shortfall (buy, then sell back)")
b2=ax.bar(x+w/2,ow,w,color=RED,label="One-way exit cost")
for b in list(b1)+list(b2): ax.text(b.get_x()+b.get_width()/2,b.get_height()+0.12,f"{b.get_height():.2f}%",ha="center",fontsize=8.5)
ax.set_xticks(x); ax.set_xticklabels(["$100","$1,000","$10,000","$100,000"]); ax.set_ylim(0,11.2)
ax.set_xlabel("Order size"); ax.set_ylabel("Cost to trader (%)"); ax.legend(frameon=False,loc="upper left",fontsize=8.5)
ax.set_title("Round-trip tests hide one-way exit cost",loc="left",fontweight="bold",fontsize=11)
save(fig,"fig2.png")
 
# ---------- Figure 3: concentrated liquidity ----------
ds=np.logspace(2,6.7,200)
fig,(a1,a2)=plt.subplots(1,2,figsize=(6.4,3.3))
for name,w_,c in [("Full range",None,NAVY),("±50%",0.5,GREEN),("±20%",0.2,GOLD),("±5%",0.05,RED),("±1%",0.01,GRAY)]:
    a1.plot(ds,[shortfall_buy(d,w_)[0] for d in ds],color=c,lw=1.8,label=name)
    a2.plot(ds,[shortfall_buy(d,w_)[1]*100 for d in ds],color=c,lw=1.8)
for a in (a1,a2): a.set_xscale("log"); a.set_xlabel("Order size (USD)"); a.grid(alpha=.25)
a1.set_ylabel("Shortfall on filled part (%)"); a2.set_ylabel("Fraction of order filled (%)")
a1.set_ylim(0,20); a2.set_ylim(0,105); a1.legend(frameon=False,title="Liquidity range",title_fontsize=8,fontsize=8)
fig.suptitle("Same $2M of capital, different liquidity design",x=0.01,ha="left",fontweight="bold",fontsize=11)
save(fig,"fig3.png")
 
# ---------- Figure 3A: shortfall by range, one line per order size ----------
labs=["Full","±50%","±20%","±5%","±1%"]
fig,ax=plt.subplots(figsize=(6.4,3.4))
for s,c in zip(SIZES,[GRAY,GOLD,GREEN,RED]):
    ax.plot(labs,[shortfall_buy(s,w_)[0] for _,w_ in RANGES],marker="o",color=c,lw=1.8,label=f"${s:,}")
ax.set_ylabel("Shortfall on filled part (%)"); ax.set_xlabel("Liquidity range of the single position (same $2M of capital)")
ax.legend(frameon=False,title="Order size",title_fontsize=8,fontsize=8)
ax.set_title("Depth depends on range: shortfall by order size",loc="left",fontweight="bold",fontsize=11)
save(fig,"fig3a.png")
 
# ---------- Figure 3B: published trade sizes against the model curve ----------
# Source: CoinMarketCap Research, "Tokenized Stocks: The Venue Landscape" (June 23, 2026):
# onchain (DEX) trades, 30 days: xStocks median $121, mean $230; Ondo median $92, mean $2,820.
ds=np.logspace(1.5,5.3,200)
fig,ax=plt.subplots(figsize=(6.4,3.7))
ax.plot(ds,[shortfall_sell(d)[0] for d in ds],color=NAVY,lw=2,label="Modeled one-way cost, $1M-per-side constant-product pool, 0.30% fee")
for t,x_,c,y,ls in [("Ondo median $92",92,GOLD,6.8,":"),("xStocks median $121",121,GREEN,8.2,":"),("xStocks mean $230",230,GREEN,9.4,"--"),("Ondo mean $2,820",2820,GOLD,9.4,"--")]:
    ax.axvline(x_,color=c,ls=ls,lw=1.4); ax.text(x_*1.08,y,t,fontsize=7.5,color=c,va="top")
for b in SIZES: ax.plot([b],[shortfall_sell(b)[0]],"o",color=RED,ms=5)
ax.set_xscale("log"); ax.set_xlim(50,2e5); ax.set_ylim(0,10)
ax.set_xlabel("Trade size (USD, log scale)"); ax.set_ylabel("Modeled one-way cost (%)")
ax.set_title("Real on-chain trade sizes against the proposed depth brackets",loc="left",fontweight="bold",fontsize=10.5)
ax.legend(frameon=False,fontsize=7.5,loc="upper center",bbox_to_anchor=(0.5,-0.2))
save(fig,"fig3b.png")
 
# ---------- Figure 3C: reported dislocations (as reported; not verified) ----------
# Sources: CoinMarketCap Research (June 23, 2026): AAPL token ~+12% intraday on Jul 3, 2025;
# AMZN token ~4x underlying off-hours on Jul 5, 2025. Ondo Finance blog: AAPL token ~15% premium.
fig,ax=plt.subplots(figsize=(6.2,3.0))
names=["AAPL token\n(Jul 3, 2025)\nintraday","AAPL token\n(per Ondo)\nat one point","AMZN token\n(Jul 5, 2025)\noff-hours"]
vals=[12,15,300]; b=ax.bar(names,vals,color=RED); ax.set_yscale("log"); ax.set_ylim(5,600)
for r,v,l in zip(b,vals,["+12%","about +15%","about 4x underlying\n(+300%)"]): ax.text(r.get_x()+r.get_width()/2,v*1.12,l,ha="center",fontsize=8.5)
ax.set_ylabel("Premium to underlying (%, log scale)")
ax.set_title("Reported price dislocations in tokenized stocks",loc="left",fontweight="bold",fontsize=11)
save(fig,"fig3c.png")
 
# ---------- Figure 4: ten-minute window ----------
fig,ax=plt.subplots(figsize=(6.2,2.4))
ax.barh(["Order allows (II.G)","FINRA Rule 6282(a)\n(off-exchange NMS)"],[600,10],color=[RED,NAVY])
ax.set_xscale("log"); ax.set_xlim(1,2500); ax.set_xlabel("Maximum delay before public report (seconds, log scale)")
ax.text(660,0,"600 s",va="center",fontsize=9); ax.text(11,1,"10 s",va="center",fontsize=9)
ax.set_title("The ten-minute window is 60 times the FINRA benchmark",loc="left",fontweight="bold",fontsize=11)
save(fig,"fig4.png")
 
# ---------- Figure 5: stale-pool profit ----------
fig,ax=plt.subplots(figsize=(6.2,3.2))
bars=ax.bar([f"{g}%" for g in gaps],stale,color=NAVY)
for b,v in zip(bars,stale): ax.text(b.get_x()+b.get_width()/2,v+max(stale)*0.015,f"${v:,.0f}",ha="center",fontsize=8.5)
ax.set_xlabel("Primary-market price move while the pool is stale"); ax.set_ylabel("Arbitrageur profit per event (USD)")
ax.set_title("What a late pause can cost liquidity providers",loc="left",fontweight="bold",fontsize=11)
save(fig,"fig5.png")
 
# ---------- Figure 5A: LULD halts on Aug. 24, 2015 ----------
# Source: Research Note: Equity Market Volatility on August 24, 2015, Staff of the Office of Analytics and Research, Division of Trading and Markets
# (Dec. 2015), Section V.B: 1,278 LULD halts, 1,058 in 327 ETPs and 220 in 144 non-ETPs.
fig,ax=plt.subplots(figsize=(6.2,2.8))
ax.barh(["Halts on Aug. 24, 2015"],[1058],color=NAVY); ax.barh(["Halts on Aug. 24, 2015"],[220],left=[1058],color=GRAY)
ax.text(529,0,"ETPs: 1,058 (327 ETPs)",color="white",ha="center",va="center",fontsize=9)
ax.text(1168,0,"220\nnon-ETP",color="white",ha="center",va="center",fontsize=9)
ax.set_xlim(0,1400); ax.set_xlabel("Limit Up-Limit Down trading halts, one trading day")
ax.set_title("1,278 LULD halts in a single trading day",loc="left",fontweight="bold",fontsize=10.5)
save(fig,"fig5a.png")
 
# ---------- Figure 6: volume caps ----------
fee1,fee2=cap1*100*FEE,cap2*100*FEE
fig,(a1,a2)=plt.subplots(1,2,figsize=(6.4,3.0))
bb=a1.bar(["Tier 1\n0.25%","Tier 2\n2.5%"],[cap1,cap2],color=[NAVY,GREEN]); a1.set_ylabel("Shares per day (tier-average stock)")
for b,v in zip(bb,[cap1,cap2]): a1.text(b.get_x()+b.get_width()/2,v+700,f"{v:,.0f}",ha="center",fontsize=8.5)
bf=a2.bar(["Tier 1","Tier 2"],[fee1,fee2],color=[NAVY,GREEN]); a2.set_ylabel("Pool fees to wash a day's cap ($)")
for b,v in zip(bf,[fee1,fee2]): a2.text(b.get_x()+b.get_width()/2,v+150,f"${v:,.0f}",ha="center",fontsize=8.5)
fig.suptitle("Volume caps are small, and cheap to wash (at an assumed $100 share)",x=0.01,ha="left",fontweight="bold",fontsize=10.5)
save(fig,"fig6.png")
 
# ---------- Figure 6A: wash cost by pool fee tier ----------
tiers=[0.0001,0.0005,0.003,0.01]; tl=["0.01%","0.05%","0.30%","1.00%"]
fig,ax=plt.subplots(figsize=(6.2,3.1)); x=np.arange(4); w=0.38
v1=[cap1*100*f for f in tiers]; v2=[cap2*100*f for f in tiers]
for bs,off,c,l in [(v1,-w/2,NAVY,"Tier 1 cap (about 7,557 shares)"),(v2,w/2,GREEN,"Tier 2 cap (about 30,199 shares)")]:
    bars=ax.bar(x+off,bs,w,color=c,label=l)
    for r in bars: ax.text(r.get_x()+r.get_width()/2,r.get_height()*1.1,f"${r.get_height():,.0f}",ha="center",fontsize=7.5)
ax.set_yscale("log"); ax.set_ylim(10,80000); ax.set_xticks(x); ax.set_xticklabels(tl)
ax.set_xlabel("Pool fee tier"); ax.set_ylabel("Pool fees to trade one day's cap ($)"); ax.legend(frameon=False,fontsize=8,loc="upper left")
ax.set_title("Cost to wash a day's cap, by pool fee (at an assumed $100 share)",loc="left",fontweight="bold",fontsize=10)
save(fig,"fig6a.png")
 
# ---------- Figure 3D: three real Ethereum pools (Attachments D and E) ----------
pools=list(csv.DictReader(open("real_pool_state.csv")))
tk=collections.defaultdict(list)
for r in csv.DictReader(open("tick_liquidity_net.csv")): tk[r["pool_address"]].append((int(r["tick"]),int(r["liquidity_net"])))
sq=lambda t: math.sqrt(1.0001**t)
TOKEN0_IS_STOCK={"0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6":True}   # TSLAx pool; the MSTRx pools have USDC as token0
def swap_up(t,cur,L,amt1,fee):          # token1 in, price up: returns (token1 used incl. fee, token0 out)
    rem=amt1*(1-fee); s=sq(cur); out0=used=0.0
    for tt,n in [x for x in t if x[0]>cur]+[(None,0)]:
        if L<=0: break
        sn=float("inf") if tt is None else sq(tt); need=float("inf") if tt is None else L*(sn-s)
        if rem>=need: out0+=L*(1/s-1/sn); used+=need; rem-=need; s=sn; L+=n
        else: s2=s+rem/L; out0+=L*(1/s-1/s2); used+=rem; rem=0; break
    return used/(1-fee),out0
def swap_down(t,cur,L,amt0,fee):        # token0 in, price down: returns (token0 used incl. fee, token1 out)
    rem=amt0*(1-fee); s=sq(cur); out1=used=0.0
    for tt,n in [x for x in t if x[0]<=cur][::-1]+[(None,0)]:
        if L<=0: break
        sn=0.0 if tt is None else sq(tt); need=float("inf") if sn==0 else L*(1/sn-1/s)
        if rem>=need: out1+=L*(s-sn); used+=need; rem-=need; s=sn; L-=n
        else: s2=1/(1/s+rem/L); out1+=L*(s-s2); used+=rem; rem=0; break
    return used/(1-fee),out1
def pool_setup(r):
    t=sorted(tk[r["pool_address"]]); cur=int(r["current_tick"]); L=sum(n for tt,n in t if tt<=cur)
    assert L==int(r["active_liquidity"])
    tok0=TOKEN0_IS_STOCK.get(r["pool_address"],False); p=1.0001**cur
    price=p*1e12 if tok0 else 1e12/p           # USD per token (18 vs 6 decimals); start price from the current tick
    return t,cur,L,float(r["fee_tier"]),tok0,price
def real_sell(r,d):
    t,cur,L,fee,tok0,price=pool_setup(r); n=d/price
    used,got=swap_down(t,cur,L,n*1e18,fee) if tok0 else swap_up(t,cur,L,n*1e18,fee)
    sold=used/1e18; recv=got/1e6
    return (sold/n*100, (1-recv/(sold*price))*100 if sold>0 else float("nan"))
def real_buy(r,d):
    t,cur,L,fee,tok0,price=pool_setup(r)
    used,got=swap_up(t,cur,L,d*1e6,fee) if tok0 else swap_down(t,cur,L,d*1e6,fee)
    paid=used/1e6; tokens=got/1e18
    return (paid/d*100, (1-tokens*price/paid)*100 if paid>0 else float("nan"))
real_rows=[["pool","fee_tier","side","size_usd","fill_pct","shortfall_pct"]]
for r in pools:
    for s in SIZES:
        f,sf=real_sell(r,s); real_rows.append([r["pool_address"],r["fee_tier"],"sell",s,round(f,3),round(sf,2)])
        f,sf=real_buy(r,s);  real_rows.append([r["pool_address"],r["fee_tier"],"buy",s,round(f,3),round(sf,2)])
csv.writer(open("real_pool_depth_results.csv","w",newline="")).writerows(real_rows)
style={"TSLAx":(NAVY,"TSLAx 0.30%"),"MSTRx0.003":(RED,"MSTRx 0.30% (full range)"),"MSTRx0.01":(GOLD,"MSTRx 1.00%")}
sizes=np.logspace(1,5,60)
fig,(a1,a2)=plt.subplots(1,2,figsize=(6.6,3.9))
for r in pools:
    key="TSLAx" if r["token_symbol"]=="TSLAx" else ("MSTRx0.003" if float(r["fee_tier"])==0.003 else "MSTRx0.01")
    res=[real_sell(r,d) for d in sizes]; c,l=style[key]
    a1.plot(sizes,[x[1] for x in res],color=c,lw=1.8,label=l); a2.plot(sizes,[x[0] for x in res],color=c,lw=1.8)
a1.plot(sizes,[shortfall_sell(d)[0] for d in sizes],color=GRAY,lw=1.4,ls="--",label="Figure 2 model ($1M per side)")
for a in (a1,a2): a.set_xscale("log"); a.set_xlabel("Sell order size (USD, log scale)")
a1.set_ylabel("Shortfall on filled part (%)"); a2.set_ylabel("Fraction of order filled (%)"); a1.set_ylim(0,100); a2.set_ylim(0,105)
h,l=a1.get_legend_handles_labels(); fig.legend(h,l,frameon=False,fontsize=7.5,loc="lower center",ncol=2,bbox_to_anchor=(0.5,-0.02))
a2.text(12,92,"TSLAx 0.30% and MSTRx 0.30% overlap at 100%",fontsize=7,color="#555555")
fig.suptitle("Three real Ethereum pools: exit cost and fill, block 26112406",x=0.01,ha="left",fontweight="bold",fontsize=10.5)
save(fig,"fig3d.png",rect=(0,0.1,1,1))
 
if __name__=="__main__":
    for r in rows[1:]: print(r)
    print("stale",[round(v) for v in stale],"caps",round(cap1),round(cap2),"fees",round(fee1),round(fee2))
    for r in real_rows[1:]: print(r)
