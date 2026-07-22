# -*- coding: utf-8 -*-
"""Relatório de Marketing (estilo Reportei) — Meta Ads + cruzamento com leads/vendas.
Puxa: visão geral, campanhas, criativos, evolução diária (Meta Graph API).
Cruza: leads (Leads2b, origem Instagram+Facebook) e vendas (origem Meta) do dados.json comercial.
"""
import os, io, sys, json, datetime as dt, requests
from urllib.request import urlopen, Request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# token/conta: env em produção; senão lê do fluxo n8n (prototipo)
TOKEN = os.environ.get("META_TOKEN")
ACC = os.environ.get("META_ACCOUNT")
if not TOKEN:
    wf = json.load(open(r"C:\Users\kennedy.drong\Downloads\_Meta Ads - Geografia - Histórico (One-shot)_.json", encoding="utf-8"))
    cfg = json.loads([n for n in wf["nodes"] if n["name"] == "Edit Fields"][0]["parameters"]["jsonOutput"])
    TOKEN = cfg["meta_token"]; ACC = cfg["accounts"][0]["id"]
GV = "https://graph.facebook.com/v25.0"
DIAS = int(os.environ.get("MKT_DIAS", "30"))
hoje = dt.date.today()
desde = hoje - dt.timedelta(days=DIAS - 1)
TR = {"since": desde.isoformat(), "until": hoje.isoformat()}

LEAD_TYPES = {"offsite_complete_registration_add_meta_leads", "onsite_web_lead",
              "onsite_conversion.lead_grouped", "leadgen_grouped", "lead"}
def _leads(actions):
    return sum(float(a["value"]) for a in (actions or []) if a["action_type"] in LEAD_TYPES)
def _f(x):
    try: return float(x)
    except: return 0.0

def insights(level, fields, extra=None):
    p = {"access_token": TOKEN, "level": level, "fields": fields,
         "time_range": json.dumps(TR), "limit": 500}
    if extra: p.update(extra)
    out, url = [], f"{GV}/{ACC}/insights"
    while url:
        d = requests.get(url, params=p, timeout=90).json() if url.endswith("/insights") else requests.get(url, timeout=90).json()
        out += d.get("data", [])
        url = (d.get("paging") or {}).get("next")
        p = None
    return out

print(f"[mkt] conta {ACC} · período {TR['since']}→{TR['until']}")

# ── visão geral (conta) ──
ov = insights("account", "spend,impressions,reach,clicks,ctr,cpc,cpm,frequency,inline_link_clicks,actions")
o = ov[0] if ov else {}
invest = _f(o.get("spend")); impr = _f(o.get("impressions")); reach = _f(o.get("reach"))
clicks = _f(o.get("clicks")); linkclicks = _f(o.get("inline_link_clicks"))
leads = _leads(o.get("actions"))
overview = {
    "invest": invest, "impressoes": impr, "alcance": reach, "cliques": clicks,
    "linkclicks": linkclicks, "ctr": _f(o.get("ctr")), "cpc": _f(o.get("cpc")),
    "cpm": _f(o.get("cpm")), "frequencia": _f(o.get("frequency")),
    "leads": leads, "cpl": invest / leads if leads else 0,
}

# ── evolução diária ──
serie = insights("account", "spend,actions", {"time_increment": 1})
evolucao = [{"d": s.get("date_start"), "invest": _f(s.get("spend")), "leads": _leads(s.get("actions"))}
            for s in sorted(serie, key=lambda x: x.get("date_start", ""))]

# ── campanhas ──
camps = insights("campaign", "campaign_name,objective,spend,impressions,clicks,ctr,cpm,reach,actions")
campanhas = []
for c in camps:
    lv = _leads(c.get("actions")); sp = _f(c.get("spend"))
    campanhas.append({"nome": c.get("campaign_name"), "objetivo": c.get("objective"),
        "invest": sp, "impressoes": _f(c.get("impressions")), "cliques": _f(c.get("clicks")),
        "ctr": _f(c.get("ctr")), "cpm": _f(c.get("cpm")), "leads": lv,
        "cpl": sp / lv if lv else 0})
campanhas.sort(key=lambda x: -x["invest"])

# ── criativos (ads) ──
ads = insights("ad", "ad_name,campaign_name,spend,impressions,clicks,ctr,cpm,actions")
criativos = []
for a in ads:
    lv = _leads(a.get("actions")); sp = _f(a.get("spend"))
    criativos.append({"nome": a.get("ad_name"), "campanha": a.get("campaign_name"),
        "invest": sp, "impressoes": _f(a.get("impressions")), "cliques": _f(a.get("clicks")),
        "ctr": _f(a.get("ctr")), "leads": lv, "cpl": sp / lv if lv else 0})
criativos.sort(key=lambda x: -x["invest"])

# ── cruzamento com CRM (leads/vendas origem Meta) ──
META_ORIG = {"instagram", "facebook"}
try:
    D = json.loads(urlopen(Request("https://raw.githubusercontent.com/kennedydrong-arch/dashboard-comercial-larafy/main/dados.json",
                                    headers={"User-Agent": "x"})).read())
    di = desde.isoformat()
    def inper(x): d = str(x.get("d") or "")[:10]; return d >= di
    leads_crm = [l for l in D["leads"] if str(l.get("o") or "").lower() in META_ORIG and inper(l)]
    vendas_meta = [v for v in D["vendas"] if str(v.get("o") or "").lower() in META_ORIG and inper(v)]
    fat = sum(_f(v.get("va")) for v in vendas_meta)
    cross = {"leadsCRM": len(leads_crm), "vendas": len(vendas_meta), "faturamento": fat,
             "cac": invest / len(vendas_meta) if vendas_meta else 0,
             "roas": fat / invest if invest else 0}
except Exception as e:
    print("[mkt] cruzamento falhou:", str(e)[:120]); cross = {}

M = {"periodo": TR, "dias": DIAS, "conta": "LaraTAX",
     "overview": overview, "evolucao": evolucao, "campanhas": campanhas,
     "criativos": criativos, "cross": cross,
     "geradoEm": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
json.dump(M, open(os.path.join(os.path.dirname(__file__), "mkt_metrics.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(f"[mkt] invest R${invest:,.0f} | leads {leads:.0f} | CPL R${overview['cpl']:.2f} | "
      f"campanhas {len(campanhas)} | criativos {len(criativos)} | cross {cross}")
