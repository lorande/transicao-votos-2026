"""Interceptos de zona do modelo de efeitos fixos (fe_modelo.py): por região, por UF e agrupamento (k-means).

Intercepto da zona = ganho médio do Lula por seção na zona que os quatro regressores (ΔComparecimento, queda de
brancos, queda de nulos, Outros no 1º turno) não explicam, com os β globais. O do adversário é o mesmo com sinal
trocado. Também: relação com a força do Lula na zona no 1º turno, e k-means das zonas sobre (intercepto, β1..β4
estimados zona a zona), comparando os grupos com as regiões.

Uso:  python -X utf8 -E -P fe_interceptos.py saida/
"""
import os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fe_modelo as M

OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
M.OUT = OUT
REG = {"N": "AC AP AM PA RO RR TO", "NE": "AL BA CE MA PB PE PI RN SE", "CO": "DF GO MT MS",
       "SE": "ES MG RJ SP", "S": "PR RS SC", "Exterior": "ZZ"}
REG_DE = {u: r for r, us in REG.items() for u in us.split()}
ORDEM = ["NE", "N", "CO", "SE", "S", "Exterior"]
COR = {"NE": "#c0392b", "N": "#2a9d8f", "CO": "#e9a23b", "SE": "#1d4e89", "S": "#7b2d8e", "Exterior": "#6b7280"}

def br(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def kmeans(X, k, rng, it=100):
    c = X[rng.choice(len(X), k, replace=False)]
    for _ in range(it):
        lab = ((X[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        novo = np.array([X[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
        if np.allclose(novo, c): break
        c = novo
    return lab, ((X - c[lab]) ** 2).sum()

def main():
    zonas = {}
    for ano in (2022, 2026):
        d, _ = M.secoes(ano)
        t, r2, alfa, _ = M.fe(d, "dLula")
        g = d.groupby("zona")
        z = pd.DataFrame({"intercepto": alfa, "secoes": g.size(), "uf": g.uf.first(),
                          "forca_Lula_1T": 100 * g.Lula1.sum() / g.Comp1.sum(),
                          "eleitores_medio": g.Comp1.mean()})
        z["regiao"] = z.uf.map(REG_DE)
        z["intercepto_pct"] = 100 * z.intercepto / z.eleitores_medio        # em % do comparecimento da seção
        zb = M.por_zona(d, "dLula")
        z = z.join(zb.add_prefix("beta_"))
        zonas[ano] = z
        print(f"\n=== {ano}: {len(z)} zonas | intercepto: mediana {br(z.intercepto.median())} votos/seção "
              f"({br(z.intercepto_pct.median())}% do comparecimento)")
        tab = z.groupby("regiao").agg(zonas=("intercepto", "size"), mediana=("intercepto", "median"),
                                      p10=("intercepto", lambda s: s.quantile(.1)),
                                      p90=("intercepto", lambda s: s.quantile(.9)),
                                      media_pond=("intercepto", lambda s: np.average(s, weights=z.loc[s.index, "secoes"])),
                                      forca_Lula_1T=("forca_Lula_1T", "median")).reindex(ORDEM)
        print(tab.round(2).to_string())
        # quanto da variação dos interceptos a região e a UF explicam; relação com a força do Lula no 1º turno
        for nivel in ("regiao", "uf"):
            r2n = 1 - ((z.intercepto - z.groupby(nivel).intercepto.transform("mean")) ** 2).sum() / \
                  ((z.intercepto - z.intercepto.mean()) ** 2).sum()
            print(f"  parte da variação dos interceptos explicada por {nivel}: {br(100 * r2n, 1)}%")
        a, b = np.polyfit(z.forca_Lula_1T, z.intercepto, 1)
        print(f"  intercepto = {br(a, 3)} × força do Lula no 1º turno (%) {'+' if b >= 0 else '−'} {br(abs(b))}  "
              f"(r = {br(np.corrcoef(z.forca_Lula_1T, z.intercepto)[0, 1])})")
        tab.assign(mediana_brasil=z.intercepto.median(), inclinacao_forca=a, constante_forca=b,
                   r_forca=np.corrcoef(z.forca_Lula_1T, z.intercepto)[0, 1]).round(4) \
            .to_csv(os.path.join(OUT, f"fe_interceptos_regioes_{ano}.csv"), encoding="utf-8-sig")
        z.round(4).to_csv(os.path.join(OUT, f"fe_interceptos_{ano}.csv"), encoding="utf-8-sig")

    # mesmas zonas nos dois anos
    j = zonas[2022][["intercepto"]].join(zonas[2026][["intercepto", "regiao"]], lsuffix="_2022", rsuffix="_2026",
                                          how="inner")
    print(f"\ncorrelação dos interceptos 2022 × 2026 nas mesmas zonas: {br(j.intercepto_2022.corr(j.intercepto_2026))}")

    # k-means sobre (intercepto, β1..β4) de 2026, padronizados
    z = zonas[2026].dropna(subset=[c for c in zonas[2026].columns if c.startswith("beta_")]).copy()
    feats = ["intercepto"] + [c for c in z.columns if c.startswith("beta_")]
    X = ((z[feats] - z[feats].median()) / (z[feats].quantile(.75) - z[feats].quantile(.25))).clip(-5, 5).to_numpy()
    rng = np.random.default_rng(0)
    print("\nk-means (2026, intercepto + β zona a zona, padronizados): inércia por k")
    inercia = {}
    for k in range(2, 8):
        inercia[k] = min(kmeans(X, k, rng)[1] for _ in range(10))
        print(f"  k = {k}: {br(inercia[k], 0)}")
    K = 4
    melhor = min((kmeans(X, K, rng) for _ in range(20)), key=lambda r: r[1])[0]
    z["grupo"] = melhor
    perfil = z.groupby("grupo")[feats + ["forca_Lula_1T"]].median()
    perfil["zonas"] = z.grupo.value_counts().sort_index()
    print(f"\nperfil dos {K} grupos (medianas):"); print(perfil.round(2).to_string())
    ct = pd.crosstab(z.grupo, z.regiao)[[r for r in ORDEM if r in z.regiao.unique()]]
    print("\nzonas por grupo × região:"); print(ct.to_string())
    print("\n% de cada região em cada grupo:"); print((100 * ct / ct.sum()).round(1).to_string())
    z[["uf", "regiao", "grupo"] + feats].to_csv(os.path.join(OUT, "fe_interceptos_grupos_2026.csv"), encoding="utf-8-sig")

    # gráficos
    fig = plt.figure(figsize=(17, 10.5))
    ax1 = fig.add_subplot(2, 2, 1)
    pos = np.arange(len(ORDEM))
    for k, (ano, desl) in enumerate(((2022, -.18), (2026, .18))):
        dados = [zonas[ano].query("regiao == @r").intercepto for r in ORDEM]
        bp = ax1.boxplot(dados, positions=pos + desl, widths=.32, patch_artist=True, showfliers=False)
        for b, r in zip(bp["boxes"], ORDEM):
            b.set_facecolor(COR[r] if ano == 2026 else "white"); b.set_edgecolor(COR[r]); b.set_alpha(.75)
    ax1.set_xticks(pos, ORDEM); ax1.axhline(0, color="#9ca3af", lw=.8)
    ax1.set_ylabel("intercepto da zona (votos do Lula por seção)")
    ax1.set_title("Interceptos por região: 2022 (vazado) × 2026 (cheio)", loc="left", weight="bold")
    ax2 = fig.add_subplot(2, 2, 2)
    z26 = zonas[2026]
    ufs = [u for r in ORDEM for u in sorted(z26.loc[z26.regiao == r, "uf"].unique())]
    bp = ax2.boxplot([z26.query("uf == @u").intercepto for u in ufs], patch_artist=True, showfliers=False, widths=.6)
    for b, u in zip(bp["boxes"], ufs):
        b.set_facecolor(COR[REG_DE[u]]); b.set_alpha(.7); b.set_edgecolor(COR[REG_DE[u]])
    ax2.set_xticks(range(1, len(ufs) + 1), ufs, fontsize=8); ax2.axhline(0, color="#9ca3af", lw=.8)
    ax2.set_title("Interceptos por UF, 2026 (cores = região)", loc="left", weight="bold")
    ax3 = fig.add_subplot(2, 2, 3)
    for r in ORDEM:
        s = z26[z26.regiao == r]
        ax3.scatter(s.forca_Lula_1T, s.intercepto, s=8, alpha=.5, color=COR[r], label=r)
    xx = np.linspace(z26.forca_Lula_1T.min(), z26.forca_Lula_1T.max(), 50)
    a, b = np.polyfit(z26.forca_Lula_1T, z26.intercepto, 1)
    ax3.plot(xx, a * xx + b, color="#1f2328", lw=1.5, ls="--")
    ax3.set_xlabel("Lula no 1º turno na zona (% do comparecimento)"); ax3.set_ylabel("intercepto da zona")
    ax3.set_title("2026: intercepto × força do Lula no 1º turno", loc="left", weight="bold")
    ax3.legend(frameon=False, fontsize=8, markerscale=2); ax3.axhline(0, color="#9ca3af", lw=.8)
    ax4 = fig.add_subplot(2, 2, 4)
    pct = (100 * ct / ct.sum()).T
    esq = np.zeros(len(pct))
    tons = ["#d9d9d9", "#9ca3af", "#4b5563", "#1f2328"][:K]
    for g in range(K):
        ax4.barh(pct.index, pct[g], left=esq, color=tons[g], label=f"grupo {g}: intercepto {br(perfil.loc[g, 'intercepto'], 1)},"
                 f" β2 {br(perfil.loc[g, 'beta_qBrancos'], 2)}, Lula 1T {br(perfil.loc[g, 'forca_Lula_1T'], 0)}%")
        esq += pct[g].to_numpy()
    ax4.invert_yaxis(); ax4.set_xlabel("% das zonas da região")
    ax4.set_title(f"k-means com {K} grupos (2026) × região", loc="left", weight="bold")
    ax4.legend(frameon=False, fontsize=7.5, loc="lower center", bbox_to_anchor=(.5, -.42), ncol=2)
    for ax in (ax1, ax2, ax3, ax4):
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fe_interceptos.png"), dpi=110)

if __name__ == "__main__":
    main()
