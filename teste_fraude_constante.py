"""Teste da hipótese: em cada urna, K votos de brancos/nulos/abstenção foram convertidos em votos para o Lula no
2º turno (K = 10 na hipótese testada).

Ideia: mudanças de comportamento do eleitor crescem, em média, proporcionalmente ao tamanho da seção (N eleitores).
Um acréscimo fixo por urna não: ele vale K/N por eleitor — muito mais em seções pequenas. Então, por seção:

    y / N = α + c · (1/N) + controles + erro

y = ganho do Lula entre os turnos (e, como contraprova, ganho do Flávio, queda de brancos+nulos, queda da abstenção).
c estima o número fixo de votos por urna. Sob a hipótese, c ≈ +K para o ganho do Lula e c ≈ +K para a queda de
brancos+nulos+abstenção; sem fraude, c ≈ 0.

Para tirar o efeito de seções pequenas serem de lugares diferentes, a comparação é feita dentro do mesmo local de
votação (efeito fixo de local), com controles da composição da seção no 1º turno. Erro-padrão agrupado por local.
Calibração: injeta a fraude nos dados reais e refaz o teste, para mostrar o que ele acusaria.

Uso:  python -X utf8 -E -P teste_fraude_constante.py saida/ [K]
"""
import os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "saida")
K = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
INK, MUTED, GRID = "#1f2328", "#6b7280", "#e5e7eb"

def br(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def carrega():
    s = pd.read_csv(os.path.join(OUT, "transicao_secoes.csv.gz"), dtype={"cd": str})
    info = pd.read_csv(os.path.join(OUT, "forense_info_secoes.csv.gz"), dtype={"cd": str},
                       usecols=["uf", "cd", "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO_2"])
    s = s.merge(info, on=["uf", "cd", "NR_ZONA", "NR_SECAO"], how="left")
    s["local"] = s.uf + "-" + s.cd + "-" + s.NR_ZONA.astype(str) + "-" + s.NR_LOCAL_VOTACAO_2.astype(str)
    s = s[(s.eleitores_1 >= 30) & (s.eleitores_1 == s.eleitores_2)].copy()   # mesmo eleitorado nos dois turnos
    return s

def variaveis(s, fraude=0.0):
    """y por seção; com fraude > 0, injeta a conversão: +fraude para o Lula, tirados de abstenção, brancos e nulos
    na proporção do que existe na seção no 2º turno (limitado ao disponível)"""
    d = pd.DataFrame(index=s.index)
    L2, A2, B2, N2 = (s[c].astype(float).copy() for c in ("Lula_2", "Abstenção_2", "Brancos_2", "Nulos_2"))
    if fraude:
        pool = A2 + B2 + N2
        k = np.minimum(fraude, pool)
        L2 = L2 + k
        for v in (A2, B2, N2):
            v -= k * v / pool.where(pool > 0, 1)
    N = s.eleitores_1.astype(float)
    d["N"] = N
    d["inv"] = 1 / N
    d["ganho_Lula"] = L2 - s.Lula_1
    d["ganho_Flávio"] = s["Flávio_2"] - s["Flávio_1"]
    d["queda_BNA"] = (s.Brancos_1 + s.Nulos_1 + s["Abstenção_1"]) - (B2 + N2 + A2)
    d["queda_BN"] = (s.Brancos_1 + s.Nulos_1) - (B2 + N2)
    d["queda_A"] = s["Abstenção_1"] - A2
    # controles: composição da seção no 1º turno (fração do eleitorado)
    for c in ("Lula_1", "Flávio_1", "Outros_1", "Brancos_1", "Nulos_1"):
        d["p_" + c] = s[c] / N
    d["local"] = s.local.to_numpy()
    return d

def estima(d, y, controles=True, ef=True):
    """c (votos fixos por urna) em y/N = α + c/N + controles, com efeito fixo de local; erro agrupado por local"""
    cols = ["inv"] + ([c for c in d.columns if c.startswith("p_")] if controles else [])
    Y = d[y] / d.N
    X = d[cols].copy()
    if ef:
        g = d["local"]
        Y = Y - Y.groupby(g).transform("mean")
        X = X - X.groupby(g).transform("mean")
    else:
        X["const"] = 1.0
    Xa, Ya = X.to_numpy(), Y.to_numpy()
    XtX = Xa.T @ Xa
    b = np.linalg.solve(XtX, Xa.T @ Ya)
    u = Ya - Xa @ b
    S = pd.DataFrame(Xa * u[:, None]).groupby(d["local"].to_numpy()).sum().to_numpy()
    inv = np.linalg.inv(XtX)
    ep = np.sqrt(np.diag(inv @ (S.T @ S) @ inv))
    return b[0], ep[0]

def main():
    s = carrega()
    multi = s.groupby("local").eleitores_1.transform(lambda v: v.nunique() > 1)
    print(f"seções: {len(s):,} (eleitorado igual nos dois turnos, >= 30 eleitores) | em locais com tamanhos diferentes: "
          f"{int(multi.sum()):,} | tamanho: p5 {s.eleitores_1.quantile(.05):.0f}, mediana {s.eleitores_1.median():.0f}, "
          f"p95 {s.eleitores_1.quantile(.95):.0f}")
    real, sim = variaveis(s), variaveis(s, K)
    linhas = []
    for y in ("ganho_Lula", "queda_BNA", "queda_BN", "queda_A", "ganho_Flávio"):
        for nome, kw in (("sem controles, sem efeito fixo", dict(controles=False, ef=False)),
                         ("efeito fixo de local", dict(controles=False, ef=True)),
                         ("efeito fixo de local + composição", dict(controles=True, ef=True))):
            c, ep = estima(real, y, **kw)
            cs, eps = estima(sim, y, **kw)
            linhas.append({"variável": y, "especificação": nome, "c_real": c, "ep_real": ep,
                           f"c_com_fraude_{K:g}": cs, "ep_sim": eps})
    r = pd.DataFrame(linhas)
    print(f"\nc = votos fixos por urna estimados (sob a hipótese: ≈ +{K:g} em ganho_Lula e queda_BNA; ≈ 0 em ganho_Flávio)")
    print(r.round(3).to_string(index=False))
    r.round(4).to_csv(os.path.join(OUT, "teste_fraude_constante.csv"), index=False, encoding="utf-8-sig")
    # limite superior: maior fraude constante compatível com os dados (IC 95% unilateral, especificação principal)
    c, ep = estima(real, "ganho_Lula")
    print(f"\nespecificação principal (efeito fixo de local + composição): c = {c:.3f} ± {ep:.3f}; "
          f"limite superior de 95%: {c + 1.645 * ep:.2f} votos por urna "
          f"(≈ {br((c + 1.645 * ep) * len(s) / 1e6, 2)} mi no Brasil)")

    # gráfico: ganho do Lula por 100 eleitores x tamanho da seção, dentro do local, real e com a fraude injetada
    fig, ax = plt.subplots(figsize=(11, 6))
    faixas = pd.qcut(s.eleitores_1, 20, duplicates="drop")
    for d, cor, rot in ((real, "#c0392b", "dados reais"), (sim, MUTED, f"com a fraude injetada (+{K:g} por urna)")):
        r100 = 100 * d.ganho_Lula / d.N
        dentro = r100 - r100.groupby(d.local).transform("mean")   # tira o efeito do local; centra em 0
        g = dentro.groupby(faixas, observed=True).agg(["mean", "sem"])
        xm = s.eleitores_1.groupby(faixas, observed=True).mean()
        ax.errorbar(xm, g["mean"], yerr=1.96 * g["sem"], fmt="o-", color=cor, capsize=2, label=rot, lw=1.5, ms=4)
    ax.set_xlabel("Eleitores na seção (média de cada uma de 20 faixas)", color=INK)
    ax.set_ylabel("Ganho do Lula por 100 eleitores, em relação\nàs outras seções do mesmo local", color=INK)
    ax.axhline(0, color="#9ca3af", lw=.8)
    ax.set_title("Se houvesse votos fixos por urna, as seções pequenas destoariam", loc="left", weight="bold", color=INK)
    ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True); ax.legend(frameon=False)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    fig.text(.01, .01, f"{br(len(s), 0)} seções com o mesmo eleitorado nos dois turnos. Cada ponto: média da faixa, "
             "depois de tirar a média do local de votação (IC 95%). Fonte: TSE, dados abertos por seção.",
             fontsize=8.5, color=MUTED)
    plt.tight_layout(rect=(0, .03, 1, 1))
    plt.savefig(os.path.join(OUT, "teste_fraude_constante.png"), dpi=120)

if __name__ == "__main__":
    main()
