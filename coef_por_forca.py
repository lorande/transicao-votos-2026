"""Coeficientes de eleitores novos (x) e de Outros como função da força do Lula no 1º turno, por seção.

Modelo:  ganho_Lula = f(p)·x + g(p)·Outros + k,   p = votos do Lula no 1º turno / eleitorado da seção
(o do Flávio é 1 − f e 1 − g, com −k, pela identidade ganho_L + ganho_F = x + Outros)

  livre      f e g próprios de cada uma de 20 faixas de p, numa regressão só, com intercepto comum
  linear     f(p) = a·(1 + b·p)                     (igual a uma interação linear; mínimos quadrados comuns)
  logística  f(p) = 1 / (1 + exp(−(α + β·p)))       (mínimos quadrados não lineares; fica entre 0 e 1)

Uso:  python -X utf8 -E -P coef_por_forca.py saida/
"""
import os, sys
import numpy as np, pandas as pd
from scipy.optimize import least_squares
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
NFAIXAS = 20
INK, MUTED, GRID = "#1f2328", "#6b7280", "#e5e7eb"
COR = {"x": "#c0392b", "Outros": "#8e5fbf"}

def br(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def dados():
    s = pd.read_csv(os.path.join(OUT, "transicao_secoes.csv.gz"), dtype={"cd": str})
    s = s[s.eleitores_1 > 0].copy()
    s["x"] = (s.Lula_2 + s["Flávio_2"]) - (s.Lula_1 + s["Flávio_1"] + s.Outros_1)
    s["O"] = s.Outros_1
    s["g"] = s.Lula_2 - s.Lula_1
    s["p"] = s.Lula_1 / s.eleitores_1
    s["cluster"] = s.uf + "-" + s.cd + "-" + s.NR_ZONA.astype(str)
    return s

def r2(y, pred):
    return 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()

def livre(s):
    """uma regressão só: coeficientes de x e de Outros próprios de cada faixa de p e intercepto comum
    (o mesmo k das formas linear e logística, para a comparação ser justa)"""
    s["faixa"] = pd.qcut(s.p, NFAIXAS, labels=False)
    D = np.eye(NFAIXAS)[s.faixa.to_numpy()]
    X = np.column_stack([D * s.x.to_numpy()[:, None], D * s.O.to_numpy()[:, None], np.ones(len(s))])
    y = s.g.to_numpy(float)
    XtX = X.T @ X
    b = np.linalg.solve(XtX, X.T @ y)
    u = y - X @ b
    S = pd.DataFrame(X * u[:, None]).groupby(s.cluster.to_numpy()).sum().to_numpy()   # agrupado por zona
    inv = np.linalg.inv(XtX)
    ep = np.sqrt(np.diag(inv @ (S.T @ S) @ inv))
    g = s.groupby("faixa")
    return pd.DataFrame({"faixa": np.arange(1, NFAIXAS + 1), "p_medio": g.p.mean().to_numpy(),
                         "secoes": g.size().to_numpy(), "f_x": b[:NFAIXAS], "ep_x": ep[:NFAIXAS],
                         "g_Outros": b[NFAIXAS:2 * NFAIXAS], "ep_Outros": ep[NFAIXAS:2 * NFAIXAS],
                         "k_comum": b[-1]}), r2(pd.Series(y), X @ b)

def ajusta(s, forma):
    p, x, O, y = (s[c].to_numpy(float) for c in ("p", "x", "O", "g"))
    if forma == "linear":
        X = np.column_stack([x, x * p, O, O * p, np.ones(len(s))])
        c, *_ = np.linalg.lstsq(X, y, rcond=None)
        par = {"a_x": c[0], "b_x": c[1] / c[0], "a_O": c[2], "b_O": c[3] / c[2], "k": c[4]}
        f = lambda q: par["a_x"] * (1 + par["b_x"] * q)
        g = lambda q: par["a_O"] * (1 + par["b_O"] * q)
        return par, f, g, r2(y, X @ c)
    sig = lambda z: 1 / (1 + np.exp(-z))
    res = lambda t: sig(t[0] + t[1] * p) * x + sig(t[2] + t[3] * p) * O + t[4] - y
    t = least_squares(res, x0=[-0.5, 3, -0.5, 3, 0], method="lm").x
    par = {"alfa_x": t[0], "beta_x": t[1], "alfa_O": t[2], "beta_O": t[3], "k": t[4]}
    return par, (lambda q: sig(t[0] + t[1] * q)), (lambda q: sig(t[2] + t[3] * q)), r2(y, res(t) + y)

def main():
    s = dados()
    lv, r2_livre = livre(s)
    lin = ajusta(s, "linear"); logi = ajusta(s, "logistica")
    base = np.column_stack([s.x, s.O, np.ones(len(s))])
    r2_base = r2(s.g.to_numpy(), base @ np.linalg.lstsq(base, s.g.to_numpy(), rcond=None)[0])
    print(f"seções: {len(s):,} | % do Lula no 1º turno: média {100 * s.p.mean():.1f}%, p10 {100 * s.p.quantile(.1):.1f}%,"
          f" p90 {100 * s.p.quantile(.9):.1f}%")
    print(f"r²: coeficientes fixos {r2_base:.4f} | linear {lin[3]:.4f} | logística {logi[3]:.4f} | livre (20 faixas) {r2_livre:.4f}")
    print("linear:", {k: round(v, 4) for k, v in lin[0].items()})
    print("logística:", {k: round(v, 4) for k, v in logi[0].items()})
    print("\ncurva livre (20 faixas):")
    print(lv.assign(p_medio=100 * lv.p_medio).round(3).to_string(index=False))
    q = np.array([.1, .2, .3, .4, .5, .6])
    comp = pd.DataFrame({"% Lula": 100 * q, "x linear": lin[1](q), "x logística": logi[1](q),
                         "Outros linear": lin[2](q), "Outros logística": logi[2](q)})
    print("\ncoeficientes do Lula por % do Lula (o do Flávio é 1 − valor):"); print(comp.round(3).to_string(index=False))
    lv.round(4).to_csv(os.path.join(OUT, "coef_por_forca_faixas.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([{"forma": "linear", **lin[0], "r2": lin[3]}, {"forma": "logística", **logi[0], "r2": logi[3]}]) \
        .round(5).to_csv(os.path.join(OUT, "coef_por_forca_ajustes.csv"), index=False, encoding="utf-8-sig")

    fig, axs = plt.subplots(1, 2, figsize=(15, 6.2), sharey=True)
    grade = np.linspace(s.p.quantile(.005), s.p.quantile(.995), 200)
    for ax, (nome, col, ep, i) in zip(axs, [("Eleitores novos (x)", "f_x", "ep_x", 1),
                                            ("Votos em Outros no 1º turno", "g_Outros", "ep_Outros", 2)]):
        cor = COR["x" if i == 1 else "Outros"]
        ax.errorbar(100 * lv.p_medio, lv[col], yerr=1.645 * lv[ep], fmt="o", color=cor, ms=5, capsize=2,
                    label="livre: 20 faixas de % do Lula, intercepto comum (barra = IC 90%)", zorder=3)
        ax.plot(100 * grade, lin[i](grade), color=INK, lw=1.6, ls="--", label="linear  a·(1 + b·p)")
        ax.plot(100 * grade, logi[i](grade), color=cor, lw=2.2, label="logística  1 / (1 + e^−(α + β·p))")
        ax.axhline(.5, color="#9ca3af", lw=.8, ls=":")
        pl, pg = lin[0], logi[0]
        txt = (f"linear: {br(pl['a_x' if i == 1 else 'a_O'], 3)}·(1 + {br(pl['b_x' if i == 1 else 'b_O'], 2)}·p)\n"
               f"logística: α = {br(pg['alfa_x' if i == 1 else 'alfa_O'], 2)}, β = {br(pg['beta_x' if i == 1 else 'beta_O'], 2)}")
        ax.text(.98, .04, txt, transform=ax.transAxes, ha="right", va="bottom", fontsize=10, color=INK,
                bbox=dict(facecolor="white", edgecolor=GRID, pad=5))
        ax.set_title(f"{nome}: fração que foi para o Lula", loc="left", fontsize=12.5, weight="bold", color=INK)
        ax.set_xlabel("Lula no 1º turno (% do eleitorado da seção)", color=INK)
        ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
        ax.legend(frameon=False, fontsize=9, loc="upper left")
    axs[0].set_ylabel("Coeficiente do Lula (o do Flávio é 1 − valor)", color=INK)
    fig.text(.01, .01, f"ganho do Lula = f(p)·x + g(p)·Outros + k, por seção; p = votos do Lula no 1º turno ÷ eleitorado. "
             f"r²: coeficientes fixos {br(r2_base, 3)}; linear {br(lin[3], 3)}; logística {br(logi[3], 3)}; livre {br(r2_livre, 3)}. "
             f"{br(len(s), 0)} seções. Fonte: TSE.", fontsize=8.5, color=MUTED)
    plt.tight_layout(rect=(0, .03, 1, 1))
    plt.savefig(os.path.join(OUT, "coef_por_forca.png"), dpi=130)

if __name__ == "__main__":
    main()
