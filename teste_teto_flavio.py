"""Teste: o achatamento do ganho do Flávio com os eleitores "novos" é geográfico (composição) ou não?

Variáveis por seção (iguais a grafico_novos_votantes.py, modo sem_outros):
  x = novos votantes em candidato (votos em candidato no 2º turno - votos em candidato no 1º turno)
  y = ganho do candidato menos a parcela estimada que veio de outros candidatos

Duas abordagens:
  1. Curva média de y por x dentro de cada quintil da força do Flávio no 1º turno (% do eleitorado da seção).
  2. Regressão de y em indicadoras de cada valor de x (curva livre) + efeito fixo de UF + % de Lula e de Flávio
     no 1º turno. Compara a curva com controles à curva sem controles (ambas relativas a x = 0).
O achatamento é medido pela razão entre a inclinação de x = 15 a 40 e a de x = 0 a 15 (1 = reta; perto de 0 = plana).

Uso:  python -X utf8 -E -P teste_teto_flavio.py saida/
"""
import os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
XMIN, XMAX = -30, 45          # faixa de x analisada (quase todas as seções; extremos têm poucas seções)
INK, MUTED, GRID = "#1f2328", "#6b7280", "#e5e7eb"
COR = {"Lula": "#c0392b", "Flávio": "#1d4e89"}

def br(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def dados():
    s = pd.read_csv(os.path.join(OUT, "transicao_secoes.csv.gz"))
    m = pd.read_csv(os.path.join(OUT, "transicao_secao_matrizes.csv")).query("de == 'Outros'")
    s["x"] = (s.Lula_2 + s["Flávio_2"]) - (s.Lula_1 + s["Flávio_1"] + s.Outros_1)
    for c in ("Lula", "Flávio"):
        frac = s.uf.map(m[m.para == c].set_index("uf").pct / 100)
        s[f"y_{c}"] = (s[f"{c}_2"] - s[f"{c}_1"]) - frac * s.Outros_1
        s[f"forca_{c}"] = 100 * s[f"{c}_1"] / s.eleitores_1.clip(lower=1)
    return s[(s.x >= XMIN) & (s.x <= XMAX) & (s.eleitores_1 > 0)].copy()

def curva_controlada(s, y):
    """coeficientes das indicadoras de x (ref. x = 0) numa regressão com efeito fixo de UF e força de Lula e Flávio.
    Monta X'X e X'y em blocos para não guardar a matriz inteira."""
    xs = [v for v in range(XMIN, XMAX + 1) if v != 0]
    ufs = sorted(s.uf.unique())[1:]               # primeira UF é a referência
    nomes = [f"x={v}" for v in xs] + [f"uf={u}" for u in ufs] + ["forca_Lula", "forca_Flávio", "const"]
    k = len(nomes)
    XtX, Xty = np.zeros((k, k)), np.zeros(k)
    ix = {v: i for i, v in enumerate(xs)}; iu = {u: len(xs) + i for i, u in enumerate(ufs)}
    for ini in range(0, len(s), 50_000):
        b = s.iloc[ini:ini + 50_000]
        X = np.zeros((len(b), k))
        r = np.arange(len(b))
        cx = b.x.map(ix); ok = cx.notna().to_numpy(); X[r[ok], cx[ok].astype(int)] = 1
        cu = b.uf.map(iu); ok = cu.notna().to_numpy(); X[r[ok], cu[ok].astype(int)] = 1
        X[:, -3], X[:, -2], X[:, -1] = b.forca_Lula, b["forca_Flávio"], 1
        XtX += X.T @ X; Xty += X.T @ b[y].to_numpy()
    coef = np.linalg.solve(XtX, Xty)
    curva = pd.Series([0.0] + list(coef[:len(xs)]), index=[0] + xs).sort_index()
    return curva, dict(zip(nomes[-3:], coef[-3:]))

def achatamento(curva):
    c = curva
    return ((c[40] - c[15]) / 25) / ((c[15] - c[0]) / 15)

def main():
    s = dados()
    print(f"seções analisadas: {len(s):,} ({XMIN} ≤ x ≤ {XMAX})")
    s["quintil"] = pd.qcut(s["forca_Flávio"], 5, labels=False)
    lim = s.groupby("quintil")["forca_Flávio"].agg(["min", "max"])
    fig, axs = plt.subplots(2, 2, figsize=(15, 11))
    tons = {c: [matplotlib.colors.to_hex(tuple(1 - a * (1 - np.array(matplotlib.colors.to_rgb(COR[c])))))
                for a in (.3, .45, .6, .8, 1)] for c in COR}
    resumo, integrais = [], []
    for i, cand in enumerate(("Flávio", "Lula")):
        y = f"y_{cand}"
        # 1) curvas por quintil da força do Flávio
        ax = axs[i, 0]
        for q, g in s.groupby("quintil"):
            m = g.groupby("x")[y].agg(["mean", "size"]); m = m[m["size"] >= 30]
            ax.plot(m.index, m["mean"], color=tons[cand][q], lw=2,
                    label=f"Flávio com {br(lim.loc[q, 'min'], 0)}–{br(lim.loc[q, 'max'], 0)}% do eleitorado")
            c = m["mean"]
            if {0, 15, 40} <= set(c.index):
                resumo.append((cand, f"quintil {q + 1}", achatamento(c - c[0])))
        ax.set_title(f"{cand}: curva dentro de cada faixa de força do Flávio no 1º turno", loc="left",
                     fontsize=11.5, weight="bold", color=INK)
        ax.legend(frameon=False, fontsize=8.5, loc="upper left")
        # 2) curva sem e com controles (relativas a x = 0)
        ax = axs[i, 1]
        bruta = s.groupby("x")[y].mean(); bruta = bruta - bruta[0]
        ctrl, outros = curva_controlada(s, y)
        ax.plot(bruta.index, bruta, color=COR[cand], lw=2, ls="--", label="sem controles")
        ax.plot(ctrl.index, ctrl, color=COR[cand], lw=2.5, label="com efeito fixo de UF + força de Lula e Flávio no 1º turno")
        resumo += [(cand, "sem controles", achatamento(bruta)), (cand, "com controles", achatamento(ctrl))]
        # integral das curvas relativas a x = 0, ponderada pelo número de seções: votos associados aos eleitores novos
        n = s.groupby("x").size()
        integrais.append({"candidato": cand, "sem_controles": (bruta * n).sum(), "com_controles": (ctrl * n).sum()})
        print(f"{cand}: coeficientes dos controles {{força Lula, força Flávio, const}} =",
              {k: round(v, 3) for k, v in outros.items()})
        ax.set_title(f"{cand}: curva sem e com controles (0 em x = 0)", loc="left", fontsize=11.5, weight="bold",
                     color=INK)
        ax.legend(frameon=False, fontsize=8.5, loc="upper left")
        for ax in axs[i]:
            ax.axhline(0, color="#9ca3af", lw=.8); ax.axvline(0, color="#9ca3af", lw=.8)
            for v in (15, 40):
                ax.axvline(v, color=GRID, lw=1, ls=":")
            ax.set_xlabel("Novos votantes em candidato na seção", color=INK)
            ax.set_ylabel("Ganho sem a parcela de Outros (média)", color=INK)
            ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
            for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    r = pd.DataFrame(resumo, columns=["candidato", "curva", "inclinação 15–40 ÷ inclinação 0–15"])
    print(r.round(2).to_string(index=False))
    r.round(4).to_csv(os.path.join(OUT, "teste_teto_flavio.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(integrais).round(1).to_csv(os.path.join(OUT, "teste_teto_flavio_integrais.csv"), index=False,
                                            encoding="utf-8-sig")
    # por faixa: inclinações (reta sobre as seções da faixa), eleitores novos e total de votos (integral da curva)
    faixas = []
    for q, g in s.groupby("quintil"):
        faixas.append({"faixa": q + 1, "forca_min": lim.loc[q, "min"], "forca_max": lim.loc[q, "max"], "secoes": len(g),
                       "x_medio": g.x.mean(), "pct_x_20_ou_mais": 100 * (g.x >= 20).mean(),
                       "inclinacao_Flávio": np.polyfit(g.x, g["y_Flávio"], 1)[0],
                       "inclinacao_Lula": np.polyfit(g.x, g["y_Lula"], 1)[0],
                       "votos_Flávio": g["y_Flávio"].sum(), "votos_Lula": g["y_Lula"].sum()})
    pd.DataFrame(faixas).round(4).to_csv(os.path.join(OUT, "teste_teto_flavio_faixas.csv"), index=False,
                                         encoding="utf-8-sig")
    # inclinação de x variando com a força do Flávio (interação), com efeito fixo de UF
    X = pd.get_dummies(s.uf, drop_first=True, dtype=float)
    X["x"], X["x_forca"], X["forca_F"], X["forca_L"], X["const"] = (s.x, s.x * s["forca_Flávio"], s["forca_Flávio"],
                                                                     s.forca_Lula, 1)
    c = dict(zip(X.columns, np.linalg.lstsq(X.to_numpy(), s["y_Flávio"].to_numpy(), rcond=None)[0]))
    pd.DataFrame([{"x": c["x"], "x_forca": c["x_forca"]}]).round(5).to_csv(
        os.path.join(OUT, "teste_teto_flavio_interacao.csv"), index=False, encoding="utf-8-sig")
    print(f"Flávio, inclinação de x = {c['x']:.4f} + {c['x_forca']:.5f}·força do Flávio (%)")
    fig.text(.01, .008, "Achatamento = inclinação da curva entre x = 15 e 40 dividida pela inclinação entre 0 e 15 "
             "(linhas pontilhadas): 1 = reta; perto de 0 = curva plana. Seções com x entre "
             f"{XMIN} e {XMAX}. Fonte: TSE, dados abertos por seção.", fontsize=8.5, color=MUTED)
    plt.tight_layout(rect=(0, .02, 1, 1))
    plt.savefig(os.path.join(OUT, "teste_teto_flavio.png"), dpi=120)

if __name__ == "__main__":
    main()
