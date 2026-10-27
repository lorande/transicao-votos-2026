"""Modelo de transição 1º -> 2º turno estimado por estado, agregado para o Brasil.

Mesma metodologia de transicao.py (mínimos quadrados com restrições sobre os municípios, ponderado
pelo eleitorado), mas com uma matriz por UF. Como há UFs com poucos municípios (DF tem 1, RR 15, AP 16),
cada matriz estadual é puxada para a matriz da sua região com peso LAM, medido em "municípios médios"
da UF: em UFs grandes o puxão é desprezível; no DF a matriz fica igual à do Centro-Oeste.

O resultado nacional soma os fluxos estimados em cada UF, ou seja, cada matriz estadual entra
ponderada pelo eleitorado de cada grupo do 1º turno naquela UF.

Com nivel = secao, as observações passam a ser as seções eleitorais (saida/transicao_secoes.csv.gz, gerado por
secao_base.py) e o bootstrap reamostra zonas eleitorais inteiras dentro de cada UF, já que seções da mesma zona
votam de forma parecida. O modelo (matriz por UF, puxão para a região com peso LAM) é o mesmo; LAM passa a ser
medido em "seções médias", então o puxão fica desprezível.

Uso:  python -X utf8 -E -P transicao_uf.py saida/ [n_bootstrap] [lam] [municipio|secao]
Requer saida/transicao_municipios.csv (gerado por transicao.py) ou saida/transicao_secoes.csv.gz.
"""
import sys, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transicao as T

OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
NBOOT = int(sys.argv[2]) if len(sys.argv) > 2 else 200
LAM = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
NIVEL = sys.argv[4] if len(sys.argv) > 4 else "municipio"
# arquivo de entrada, prefixo dos arquivos de saída e nome das observações em cada nível
CFG = {"municipio": ("transicao_municipios.csv", "transicao_uf", "transicao_origem", "municípios"),
       "secao": ("transicao_secoes.csv.gz", "transicao_secao", "transicao_secao_origem", "seções")}[NIVEL]
BASE, PREF, PREF_ORIG, OBS = CFG
G1, G2 = T.G1, T.G2

def fluxo(X1, Y2, P):
    # escala para que o 2º turno estimado da UF some o eleitorado do 2º turno
    return X1.sum(0)[:, None] * P * (Y2.sum() / X1.sum())

def modelo_uf(d, lam, rng=None, P0s=None):
    if rng is not None and "cluster" in d:   # bootstrap por seção: reamostra zonas inteiras dentro de cada UF
        partes = []
        for _, g in d.groupby("uf"):
            grupos = [x for _, x in g.groupby("cluster")]
            partes += [grupos[k] for k in rng.integers(0, len(grupos), len(grupos))]
        d = pd.concat(partes)
    elif rng is not None:   # bootstrap: reamostra municípios dentro de cada UF
        d = pd.concat([g.iloc[rng.integers(0, len(g), len(g))] for _, g in d.groupby("uf")])
    prior = {}
    for r, g in d.groupby("regiao"):
        X, Y, w, _, _ = T.matrizes(g)
        prior[r] = T.ajusta(X, Y, w)
    res = {}
    for u, g in d.groupby("uf"):
        X, Y, w, X1, Y2 = T.matrizes(g)
        reg = g.regiao.iloc[0]
        P = T.ajusta(X, Y, w, None if P0s is None else P0s[u], prior=prior[reg], lam=max(lam, 1e-3))
        res[u] = (P, fluxo(X1, Y2, P), reg, len(X))
    return res

def nacional(res):
    F = sum(f for _, f, _, _ in res.values())
    return pd.DataFrame(F, index=G1, columns=G2)

def pct(flux):
    return flux.div(flux.sum(axis=1), axis=0) * 100

def r2_uf(d, res):
    out = {}
    for u, g in d.groupby("uf"):
        X, Y, w, _, _ = T.matrizes(g)
        if len(X) < 3:
            continue
        pred = X @ res[u][0]
        ybar = (Y * w[:, None]).sum(0) / w.sum()
        out[u] = 1 - (w[:, None] * (Y - pred) ** 2).sum(0) / (w[:, None] * (Y - ybar) ** 2).sum(0)
    return pd.DataFrame(out, index=G2).T

CELULAS = [("Outros", "Lula"), ("Outros", "Flávio"), ("Brancos", "Lula"), ("Nulos", "Lula"), ("Abstenção", "Lula")]

def main():
    d = pd.read_csv(os.path.join(OUT, BASE), dtype={"cd": str})
    if NIVEL == "secao":
        d["cluster"] = d.uf + "-" + d.cd + "-" + d.NR_ZONA.astype(str)
        print("zonas por UF:", d.groupby("uf").cluster.nunique().to_dict())
    tot2 = d[[f"{c}_2" for c in G2]].sum().to_numpy()

    res = modelo_uf(d, LAM)
    flux = nacional(res)
    print(f"lam = {LAM} (peso do puxão para a matriz regional, em {OBS} médios da UF)")
    print(f"{OBS} por UF:", {u: n for u, (_, _, _, n) in sorted(res.items())})

    # bootstrap
    rng = np.random.default_rng(42)
    P0s = {u: p for u, (p, _, _, _) in res.items()}
    bnac, buf = [], {u: [] for u in res}
    for b in range(NBOOT):
        rb = modelo_uf(d, LAM, rng, P0s)
        bnac.append(nacional(rb).to_numpy())
        for u, (P, _, _, _) in rb.items():
            buf[u].append(P)
    bnac = np.array(bnac)
    bp = bnac / bnac.sum(2, keepdims=True) * 100
    plo, phi = np.percentile(bp, 5, axis=0), np.percentile(bp, 95, axis=0)

    p = pct(flux)
    print("\nBRASIL (soma das 27 UFs + exterior), % de cada grupo do 1º turno [intervalo 90%]:")
    for i, a in enumerate(G1):
        print(f"  {a:14s}", "  ".join(f"{c}: {p.iloc[i, j]:5.1f} [{plo[i, j]:4.1f}-{phi[i, j]:4.1f}]" for j, c in enumerate(G2)))
    print("\nBRASIL, fluxos em milhões:"); print((flux / 1e6).round(2))
    print("\nconferência 2º turno estimado x real (milhões):")
    print(pd.DataFrame({"estimado": flux.sum(axis=0).to_numpy() / 1e6, "real": tot2 / 1e6}, index=G2).round(3))
    perdas = flux.loc["Lula"].sum() - flux.loc["Lula", "Lula"]
    print("\nganho do Lula por origem (milhões):",
          {g: round(flux.loc[g, "Lula"] / 1e6, 2) for g in G1 if g != "Lula"}, "| perdas:", round(perdas / 1e6, 2),
          "| líquido:", round((flux["Lula"].sum() - flux.loc["Lula"].sum()) / 1e6, 2))

    # comparação com o modelo por região e sensibilidade ao lam
    print("\nsensibilidade (Brasil, % da linha):")
    linhas = {}
    reg = T.modelo(d)
    linhas["por região"] = pct(sum(pd.DataFrame(f, index=G1, columns=G2) for _, f in reg.values()))
    for lam in (0, 2, 5, 20, 100):
        linhas[f"UF, lam={lam:g}"] = pct(nacional(modelo_uf(d, lam)))
    sens = pd.DataFrame({k: [v.loc[a, b] for a, b in CELULAS] for k, v in linhas.items()},
                        index=[f"{a} → {b}" for a, b in CELULAS])
    print(sens.round(1).to_string())
    sens.round(3).to_csv(os.path.join(OUT, f"{PREF}_sensibilidade.csv"), encoding="utf-8-sig")

    r2 = r2_uf(d, res)
    r2.round(4).to_csv(os.path.join(OUT, f"{PREF}_r2.csv"), encoding="utf-8-sig")
    print(f"\nR² dentro de cada UF ({OBS}), mediana entre UFs:", r2.median().round(3).to_dict())
    print("UFs com R² de Lula < 0,9:", r2[r2["Lula"] < .9]["Lula"].round(2).to_dict())

    # saídas
    flux.to_csv(os.path.join(OUT, f"{PREF}_fluxos_brasil.csv"), encoding="utf-8-sig")
    tab = []
    for u, (P, F, r, n) in sorted(res.items()):
        lo, hi = np.percentile(np.array(buf[u]), 5, axis=0), np.percentile(np.array(buf[u]), 95, axis=0)
        for i, a in enumerate(G1):
            for j, b in enumerate(G2):
                tab.append({"uf": u, "regiao": r, "municipios": n, "de": a, "para": b, "pct": 100 * P[i, j],
                            "pct_p5": 100 * lo[i, j], "pct_p95": 100 * hi[i, j], "eleitores": F[i, j]})
    tab = pd.DataFrame(tab)
    tab.round(3).to_csv(os.path.join(OUT, f"{PREF}_matrizes.csv"), index=False, encoding="utf-8-sig")
    T.OUT = OUT
    T.grafico(p, plo, phi, flux, arquivo=f"{PREF}.png",
              nota=f"Matriz por UF estimada sobre {OBS} (puxada à da região com peso de {LAM:g} {OBS}), somada para o Brasil.",
              titulo=f"Transição de votos para presidente, 1º → 2º turno 2026 (modelo por UF, {OBS})")
    br = pd.DataFrame([{"de": a, "para": c, "pct": p.iloc[i, j], "pct_p5": plo[i, j], "pct_p95": phi[i, j],
                        "eleitores": flux.iloc[i, j]} for i, a in enumerate(G1) for j, c in enumerate(G2)])
    br.round(3).to_csv(os.path.join(OUT, f"{PREF}_brasil.csv"), index=False, encoding="utf-8-sig")
    orig = tabela_origens(res, buf, flux, bnac)
    orig.round(3).to_csv(os.path.join(OUT, f"{PREF}_origens.csv"), index=False, encoding="utf-8-sig")
    global BR_CELULAS
    BR_CELULAS = br
    for o in ORIGENS:
        grafico_origem(orig, o)

BR_CELULAS = None   # matriz nacional célula a célula (transicao_uf_brasil.csv), para a decomposição no gráfico
ORDEM_REG = ["NE", "N", "CO", "SE", "S"]
NOME_REG = {"NE": "Nordeste", "N": "Norte", "CO": "Centro-Oeste", "SE": "Sudeste", "S": "Sul"}

# destinos agrupados: o terceiro soma brancos, nulos e abstenção do 2º turno
DESTINOS = {"Lula": ["Lula"], "Flávio": ["Flávio"], "Branco/Nulo/Abstenção": ["Brancos", "Nulos", "Abstenção"]}

def tabela_origens(res, buf, flux, bnac):
    """% de cada grupo do 1º turno indo para Lula, Flávio e Branco/Nulo/Abstenção, por UF e Brasil.
    O intervalo do destino agrupado sai das repetições do bootstrap (somar os p5/p95 das células seria errado)."""
    linhas = []
    for dest, cols in DESTINOS.items():
        j = [G2.index(c) for c in cols]
        for u, (P, F, r, n) in sorted(res.items()):
            B = np.array(buf[u])
            for i, a in enumerate(G1):
                bs = 100 * B[:, i, j].sum(-1)
                linhas.append({"uf": u, "regiao": r, "municipios": n, "de": a, "para": dest,
                               "pct": 100 * P[i, j].sum(), "pct_p5": np.percentile(bs, 5),
                               "pct_p95": np.percentile(bs, 95), "eleitores": F[i, j].sum()})
        for i, a in enumerate(G1):
            bs = 100 * bnac[:, i, j].sum(-1) / bnac[:, i, :].sum(-1)
            linhas.append({"uf": "BRASIL", "regiao": "", "municipios": 0, "de": a, "para": dest,
                           "pct": 100 * flux.iloc[i, j].sum() / flux.iloc[i].sum(), "pct_p5": np.percentile(bs, 5),
                           "pct_p95": np.percentile(bs, 95), "eleitores": flux.iloc[i, j].sum()})
    return pd.DataFrame(linhas)

ORIGENS = ["Outros", "Brancos", "Nulos", "Abstenção"]

def grafico_origem(orig, origem):
    """para um grupo do 1º turno, um painel por destino (Lula, Flávio, Branco/Nulo/Abstenção);
    uma linha por UF e, embaixo, o Brasil (soma dos fluxos das UFs e do exterior)"""
    INK, MUTED, GRID = "#1f2328", "#6b7280", "#e5e7eb"
    COR = {"Lula": "#c0392b", "Flávio": "#1d4e89", "Branco/Nulo/Abstenção": "#6b7280"}
    t = orig[(orig.de == origem) & ~orig.uf.isin(["ZZ", "BRASIL"])]
    # de cima para baixo: regiões na ordem de ORDEM_REG, UFs em ordem alfabética dentro de cada uma;
    # cada região ganha uma linha vazia acima, onde vai o nome dela
    ypos, rotulos_reg, yy = {}, {}, 2
    for r in reversed(ORDEM_REG):
        for u in sorted(T.REG[r].split(), reverse=True):
            ypos[u] = yy; yy += 1
        rotulos_reg[r] = yy; yy += 1
    ordem = list(ypos)
    fig, axs = plt.subplots(1, len(DESTINOS), figsize=(15, 9.5), sharey=True)
    for ax, dest in zip(axs, DESTINOS):
        cor = COR[dest]
        s = t[t.para == dest].set_index("uf").loc[ordem]
        y = np.array([ypos[u] for u in s.index])   # 0 fica para o Brasil, 1 é o respiro
        ax.hlines(y, s.pct_p5, s.pct_p95, color=cor, alpha=.35, lw=3)
        # ponto vazado só faz sentido no modelo por município (UF com poucas observações)
        pequenos = (s.municipios < 25).to_numpy() if NIVEL == "municipio" else np.zeros(len(s), bool)
        ax.scatter(s.pct[~pequenos], y[~pequenos], color=cor, s=30, zorder=3, edgecolors="white", linewidths=1)
        ax.scatter(s.pct[pequenos], y[pequenos], facecolors="white", edgecolors=cor, s=30, zorder=3, linewidths=1.6)
        b = orig[(orig.uf == "BRASIL") & (orig.de == origem) & (orig.para == dest)].iloc[0]
        ax.hlines(0, b.pct_p5, b.pct_p95, color=INK, alpha=.45, lw=4)
        ax.scatter([b.pct], [0], marker="D", color=INK, s=55, zorder=4, edgecolors="white", linewidths=1)
        el = f"{b.eleitores / 1e6:.2f} mi" if b.eleitores >= 1e5 else f"{b.eleitores / 1e3:.0f} mil"
        # o rótulo do Brasil vai para o lado com mais espaço
        dir_ = b.pct_p95 < 60
        ax.annotate(f"{b.pct:.1f}%  [{b.pct_p5:.1f}–{b.pct_p95:.1f}]  {el}",
                    (b.pct_p95 if dir_ else b.pct_p5, 0), xytext=(8 if dir_ else -8, 0), textcoords="offset points",
                    va="center", ha="left" if dir_ else "right", fontsize=9, color=INK, weight="bold")
        if len(DESTINOS[dest]) > 1 and BR_CELULAS is not None:
            # decomposição do destino agrupado, para conferir com a matriz nacional
            c = BR_CELULAS[BR_CELULAS.de == origem].set_index("para")
            ax.text(0, -.85, "= " + " + ".join(f"{x} {c.loc[x, 'pct']:.1f}%" for x in DESTINOS[dest]),
                    fontsize=8, color=MUTED, va="center", ha="left")
        ax.axhline(1, color=MUTED, lw=.8)
        for r, yr in rotulos_reg.items():
            if ax is axs[0]:
                ax.text(-2, yr, NOME_REG[r], fontsize=9, color=MUTED, weight="bold", va="center")
            ax.axhline(yr - .5, color=GRID, lw=.8)
        ax.set_xlim(-2, 102); ax.set_ylim(-1.4, yy - .4)
        ax.set_yticks(np.r_[0, y], ["BRASIL"] + list(s.index), color=INK)
        for lb in ax.get_yticklabels()[:1]:
            lb.set_fontweight("bold")
        ax.set_title(f"→ {dest}", color=INK, loc="left", fontsize=12)
        ax.grid(axis="x", color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter())
        for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    total = orig[(orig.uf == "BRASIL") & (orig.de == origem)].eleitores.sum()
    fig.suptitle(f"Para onde foram os eleitores de {origem} no 1º turno ({total / 1e6:.1f} mi), por estado "
                 f"(por região e UF; modelo sobre {OBS})", color=INK, x=.01, ha="left", fontsize=13)
    if NIVEL == "secao":
        nota = ("Ponto = estimativa; barra = intervalo de 90% do bootstrap (reamostrando zonas eleitorais). Os três "
                "painéis somam 100% em cada estado. Matriz de cada UF estimada sobre as seções eleitorais. "
                "BRASIL = soma dos fluxos das UFs e do exterior.")
    else:
        nota = ("Ponto = estimativa; barra = intervalo de 90% do bootstrap. Os três painéis somam 100% em cada "
                "estado. Ponto vazado: UF com menos de 25 municípios (mais puxada para a região; DF = Centro-Oeste). "
                "BRASIL = soma dos fluxos das UFs e do exterior.")
    fig.text(.01, .01, nota, fontsize=8, color=MUTED, wrap=True)
    plt.tight_layout(rect=(0, .03, 1, .96))
    nome = {"Outros": "outros", "Brancos": "brancos", "Nulos": "nulos", "Abstenção": "abstencao"}[origem]
    plt.savefig(os.path.join(OUT, f"{PREF_ORIG}_{nome}.png"), dpi=130)
    plt.close(fig)

if __name__ == "__main__":
    import matplotlib.ticker
    main()
