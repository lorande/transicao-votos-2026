"""Teste 3 — Modelo de efeitos fixos por zona eleitoral para a variação de votos de cada candidato, por seção.

    ΔVotos_c,i = α_c,zona(i) + β1·ΔComparecimento_i + β2·QuedaBrancos_i + β3·QuedaNulos_i + β4·Outros1T_i + e_i
    ΔComparecimento = comparecimento 2º turno − 1º turno;  QuedaBrancos = brancos 1º − 2º;  QuedaNulos = nulos 1º − 2º

Identidade: ΔLula + ΔAdv = ΔComparecimento + QuedaBrancos + QuedaNulos + Outros1T em toda seção; logo os β do Lula e
do adversário somam 1 e os interceptos de zona somam 0 — a equação do adversário é o espelho da do Lula.
Estimado para 2026 (Lula × Flávio) e, como calibração, 2022 (Lula × Bolsonaro). Erro-padrão agrupado por zona.

Diagnósticos: distribuição dos interceptos de zona; β estimado zona a zona (zonas com >= 50 seções); resíduos.

Uso:  python -X utf8 -E -P fe_modelo.py saida/
"""
import os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
XS = ["dComp", "qBrancos", "qNulos", "Outros1"]
NOME = {"dComp": "β1 ΔComparecimento", "qBrancos": "β2 Queda de brancos", "qNulos": "β3 Queda de nulos",
        "Outros1": "β4 Outros no 1º turno"}
ADV = {2022: "Bolsonaro", 2026: "Flávio"}

def br(x, nd=3):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def secoes(ano):
    v = pd.read_csv(os.path.join(OUT, f"votacao_{ano}.csv.gz"), dtype={"cd": str})
    k = ["uf", "cd", "NR_ZONA", "NR_SECAO"]
    a, b = v[v.NR_TURNO == 1].set_index(k), v[v.NR_TURNO == 2].set_index(k)
    d = a.join(b, lsuffix="1", rsuffix="2", how="inner").reset_index()
    d = d[(d.Comp1 > 0) & (d.Comp2 > 0)].copy()
    d["zona"] = d.uf + "-" + d.NR_ZONA.astype(str)
    d["dLula"], d["dAdv"] = d.Lula2 - d.Lula1, d.Adv2 - d.Adv1
    d["dComp"], d["qBrancos"], d["qNulos"], d["Outros1"] = d.Comp2 - d.Comp1, d.Brancos1 - d.Brancos2, d.Nulos1 - d.Nulos2, d.Outros1
    ident = (d.dLula + d.dAdv - d.dComp - d.qBrancos - d.qNulos - d.Outros1).abs().max()
    return d, ident

def fe(d, y):
    g = d.zona
    Y = d[y] - d.groupby("zona")[y].transform("mean")
    X = d[XS] - d.groupby("zona")[XS].transform("mean")
    Xa, Ya = X.to_numpy(float), Y.to_numpy(float)
    XtX = Xa.T @ Xa
    b = np.linalg.solve(XtX, Xa.T @ Ya)
    u = Ya - Xa @ b
    Sg = pd.DataFrame(Xa * u[:, None]).groupby(g.to_numpy()).sum().to_numpy()
    inv = np.linalg.inv(XtX)
    ep = np.sqrt(np.diag(inv @ (Sg.T @ Sg) @ inv))
    r2w = 1 - (u ** 2).sum() / (Ya ** 2).sum()
    alfa = d.groupby("zona")[y].mean() - d.groupby("zona")[XS].mean() @ b
    res = pd.Series(u, index=d.index)
    return pd.DataFrame({"coef": b, "ep": ep}, index=XS), r2w, alfa, res

def por_zona(d, y, minimo=50):
    out = {}
    for z, g in d.groupby("zona"):
        if len(g) < minimo:
            continue
        X = np.column_stack([g[XS].to_numpy(float), np.ones(len(g))])
        b = np.linalg.lstsq(X, g[y].to_numpy(float), rcond=None)[0]
        out[z] = b[:4]
    return pd.DataFrame(out, index=XS).T

def main():
    res, zonas_beta, interc, resid = {}, {}, {}, {}
    for ano in (2022, 2026):
        d, ident = secoes(ano)
        print(f"\n=== {ano}: {len(d):,} seções, {d.zona.nunique():,} zonas | identidade, maior desvio: {int(ident)}")
        med = d[["dLula", "dAdv"] + XS].mean()
        print("  médias por seção:", {k: round(v, 2) for k, v in med.items()})
        for y, nome in (("dLula", "Lula"), ("dAdv", ADV[ano])):
            t, r2w, alfa, u = fe(d, y)
            res[(ano, nome)] = t.assign(r2_dentro=r2w)
            interc[(ano, nome)], resid[(ano, nome)] = alfa, u
            print(f"  {nome}: R² dentro da zona = {r2w:.3f}")
            print("   ", {NOME[k]: f"{br(t.coef[k])} ± {br(t.ep[k])}" for k in XS})
        zb = por_zona(d, "dLula")
        zonas_beta[ano] = zb
        print(f"  β por zona (Lula, {len(zb)} zonas com >= 50 seções): mediana",
              {k: br(zb[k].median()) for k in XS}, "| p5–p95",
              {k: f"{br(zb[k].quantile(.05), 2)}–{br(zb[k].quantile(.95), 2)}" for k in XS})
        fora = ((zb < -0.5) | (zb > 1.5)).any(axis=1)
        print(f"  zonas com algum β do Lula fora de [−0,5; 1,5]: {int(fora.sum())}")
        a = interc[(ano, "Lula")]
        za = (a - a.median()) / (1.4826 * (a - a.median()).abs().median())
        print(f"  interceptos de zona (Lula): mediana {br(a.median(), 2)}, p5–p95 {br(a.quantile(.05), 2)} a "
              f"{br(a.quantile(.95), 2)}; zonas a mais de 5 desvios robustos: {int((za.abs() > 5).sum())}")
        u = resid[(ano, "Lula")]
        print(f"  resíduos (Lula): desvio-padrão {br(u.std(), 2)}, curtose {br(u.kurt(), 2)}, "
              f"|resíduo| > 50 votos: {int((u.abs() > 50).sum())} seções")
        d[["uf", "cd", "NR_ZONA", "NR_SECAO"]].assign(residuo_Lula=u.round(2)).loc[u.abs() > 50] \
            .to_csv(os.path.join(OUT, f"fe_residuos_extremos_{ano}.csv"), index=False, encoding="utf-8-sig")

    tab = pd.concat(res).round(5)
    tab.to_csv(os.path.join(OUT, "fe_modelo.csv"), encoding="utf-8-sig")
    print("\nCOEFICIENTES (efeito fixo de zona):")
    print(tab.to_string())

    # gráficos
    fig, axs = plt.subplots(2, 3, figsize=(17, 9.5))
    cores = {2022: "#6b7280", 2026: "#c0392b"}
    ax = axs[0, 0]
    for k, ano in enumerate((2022, 2026)):
        for c, (nome, mk) in enumerate((("Lula", "o"), (ADV[ano], "s"))):
            t = res[(ano, nome)]
            ax.errorbar(t.coef, np.arange(4) + (k - .5) * .25 + c * .06, xerr=1.96 * t.ep, fmt=mk, color=cores[ano],
                        mfc="white" if c else cores[ano], capsize=2, label=f"{ano} {nome}")
    ax.set_yticks(range(4), [NOME[k] for k in XS]); ax.invert_yaxis(); ax.axvline(0, color="#9ca3af", lw=.8)
    ax.axvline(1, color="#9ca3af", lw=.8, ls=":"); ax.legend(frameon=False, fontsize=8)
    ax.set_title("Coeficientes globais (IC 95%)", loc="left", weight="bold")
    for j, k in enumerate(XS):
        ax = axs[(j + 1) // 3, (j + 1) % 3]
        for ano in (2022, 2026):
            ax.hist(zonas_beta[ano][k].clip(-1, 2), bins=np.linspace(-1, 2, 61), histtype="step", lw=1.6,
                    color=cores[ano], label=f"{ano} (global {br(res[(ano, 'Lula')].coef[k], 2)})", density=True)
        ax.axvline(0, color="#9ca3af", lw=.8); ax.axvline(1, color="#9ca3af", lw=.8, ls=":")
        ax.set_title(f"Lula, {NOME[k]}: estimado zona a zona", loc="left", weight="bold", fontsize=10.5)
        ax.legend(frameon=False, fontsize=8)
    ax = axs[1, 2]
    for ano in (2022, 2026):
        u = resid[(ano, "Lula")]
        ax.hist(u.clip(-60, 60), bins=120, histtype="step", lw=1.4, color=cores[ano], log=True, label=str(ano))
    ax.set_title("Resíduos do Lula por seção (votos)", loc="left", weight="bold", fontsize=10.5)
    ax.legend(frameon=False, fontsize=8)
    for a in axs.flat:
        for sp in ("top", "right"): a.spines[sp].set_visible(False)
    fig.text(.01, .005, "ΔVotos = efeito fixo da zona + β1·ΔComparecimento + β2·Queda de brancos + β3·Queda de nulos + "
             "β4·Outros 1T, por seção. Histogramas: β do Lula estimado separadamente em cada zona com >= 50 seções "
             "(cortado em −1 e 2). Os β do adversário são 1 − β do Lula.", fontsize=8.5, color="#6b7280")
    plt.tight_layout(rect=(0, .02, 1, 1))
    plt.savefig(os.path.join(OUT, "fe_modelo.png"), dpi=110)

if __name__ == "__main__":
    main()
