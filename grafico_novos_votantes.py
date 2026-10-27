"""Ganho de votos de cada candidato x eleitores "novos" em candidato, por seção eleitoral.

Para cada seção:
  x = votos em candidato no 2º turno (Lula + Flávio) - votos em candidato no 1º turno (Lula + Flávio + Outros)
    = aumento do comparecimento + queda de brancos e nulos
  y = votos do candidato no 2º turno - votos no 1º turno

O gráfico mostra a média de y para cada valor de x (x é inteiro), com o tamanho do ponto proporcional ao número
de seções; só aparecem valores de x com pelo menos MIN_SECOES seções. A reta y = a·x + b e o r são calculados
sobre todas as seções (para x inteiro, a reta das médias ponderadas pelo número de seções é a mesma).

Com modo = sem_outros, y passa a ser o ganho menos a parcela estimada que veio de outros candidatos:
  y = ganho - (fração Outros -> candidato na matriz do estado, modelo sobre seções) x votos em Outros no 1º turno
Sobra o ganho que não é transferência de outros candidatos. Como conferência sem depender da matriz, também
imprime a regressão múltipla ganho ~ x + votos em Outros.

Uso:  python -X utf8 -E -P grafico_novos_votantes.py saida/ [bruto|sem_outros]
"""
import os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
MODO = sys.argv[2] if len(sys.argv) > 2 else "bruto"
MIN_SECOES = 30
INK, MUTED, GRID = "#1f2328", "#6b7280", "#e5e7eb"
COR = {"Lula": "#c0392b", "Flávio": "#1d4e89"}

def br(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def main():
    s = pd.read_csv(os.path.join(OUT, "transicao_secoes.csv.gz"))
    x = (s.Lula_2 + s["Flávio_2"]) - (s.Lula_1 + s["Flávio_1"] + s.Outros_1)
    ys = {"Lula": s.Lula_2 - s.Lula_1, "Flávio": s["Flávio_2"] - s["Flávio_1"]}
    multipla = {}
    if MODO == "sem_outros":
        m = pd.read_csv(os.path.join(OUT, "transicao_secao_matrizes.csv")).query("de == 'Outros'")
        for nome in ys:
            frac = s.uf.map(m[m.para == nome].set_index("uf").pct / 100)
            # conferência independente da matriz: regressão múltipla ganho ~ x + Outros
            A = np.column_stack([x, s.Outros_1, np.ones(len(s))])
            c = np.linalg.lstsq(A, ys[nome], rcond=None)[0]
            multipla[nome] = c
            print(f"{nome}: regressão múltipla  ganho = {c[0]:.4f}·x + {c[1]:.4f}·Outros + {c[2]:.4f}  "
                  f"| fração Outros→{nome} média ponderada da matriz = {(frac * s.Outros_1).sum() / s.Outros_1.sum():.4f}")
            ys[nome] = ys[nome] - frac * s.Outros_1

    fig, axs = plt.subplots(1, 2, figsize=(15, 6.2))
    linhas = []
    for ax, (nome, y) in zip(axs, ys.items()):
        a, b = np.polyfit(x, y, 1)
        r = np.corrcoef(x, y)[0, 1]
        g = pd.DataFrame({"x": x, "y": y}).groupby("x").y.agg(["mean", "size"])
        mostra = g[g["size"] >= MIN_SECOES]
        cobre = mostra["size"].sum() / len(s)
        ax.scatter(mostra.index, mostra["mean"], s=4 + 60 * np.sqrt(mostra["size"] / mostra["size"].max()),
                   color=COR[nome], alpha=.75, edgecolors="white", linewidths=.4, zorder=3)
        xs = np.array([mostra.index.min(), mostra.index.max()])
        ax.plot(xs, a * xs + b, color=COR[nome], ls="--", lw=1.4, zorder=4)
        ax.axhline(0, color="#9ca3af", lw=.8); ax.axvline(0, color="#9ca3af", lw=.8)
        sinal = "+" if b >= 0 else "−"
        caixa = f"y = {br(a, 3)}·x {sinal} {br(abs(b), 2)}\nr = {br(r, 2)}   (r² = {br(r * r, 2)})\n{br(len(s), 0)} seções"
        ax.text(.03, .96, caixa, transform=ax.transAxes, va="top", fontsize=10.5, color=INK,
                bbox=dict(facecolor="white", edgecolor=GRID, pad=5))
        titulo = "ganho sem a parcela de Outros" if MODO == "sem_outros" else "ganho"
        ax.set_title(f"{nome}: {titulo} × eleitores \"novos\"", loc="left", fontsize=12.5,
                     weight="bold", color=INK)
        ax.set_xlabel("Novos votantes em candidato na seção\n(aumento de comparecimento + queda de brancos/nulos)",
                      color=INK)
        ax.set_ylabel(("Votos ganhos, sem a parcela de Outros" if MODO == "sem_outros" else
                       "Votos ganhos do 1º para o 2º turno") + "\n(média das seções)", color=INK)
        ax.grid(color=GRID, lw=.6); ax.set_axisbelow(True)
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
        linhas.append((nome, a, b, r, cobre, mostra.index.min(), mostra.index.max()))
    # mesma escala vertical nos dois painéis, para comparar as inclinações
    lo = min(a.get_ylim()[0] for a in axs); hi = max(a.get_ylim()[1] for a in axs)
    for a in axs: a.set_ylim(lo, hi)
    n, _, _, _, cobre, x0, x1 = linhas[0]
    fig.text(.01, .01, f"Cada ponto é a média das seções com aquele valor de x; tamanho proporcional ao número de seções. "
             f"Só aparecem valores de x com pelo menos {MIN_SECOES} seções (de {int(x0)} a {int(x1)}; "
             f"{br(100 * cobre, 1)}% das seções).\nReta e r calculados sobre todas as seções. "
             + ("Parcela de Outros = fração Outros → candidato da matriz do estado (modelo sobre seções) × votos em "
                "Outros na seção no 1º turno. " if MODO == "sem_outros" else "")
             + "Fonte: TSE, dados abertos por seção.", fontsize=8.5, color=MUTED)
    plt.tight_layout(rect=(0, .055, 1, 1))
    plt.savefig(os.path.join(OUT, "novos_votantes.png" if MODO == "bruto" else "novos_votantes_sem_outros.png"),
                dpi=130)
    for nome, a, b, r, *_ in linhas:
        print(f"{nome}: y = {a:.4f}·x + {b:.4f}  r = {r:.4f}  r² = {r * r:.4f}")
    tab = pd.DataFrame([{"candidato": nome, "a": a, "b": b, "r": r, "secoes": len(s),
                         "mult_x": multipla.get(nome, [np.nan] * 3)[0], "mult_outros": multipla.get(nome, [np.nan] * 3)[1],
                         "mult_const": multipla.get(nome, [np.nan] * 3)[2]} for nome, a, b, r, *_ in linhas])
    tab.round(4).to_csv(os.path.join(OUT, f"novos_votantes_{MODO}.csv"), index=False, encoding="utf-8-sig")
    print("x: média", round(x.mean(), 2), "| mediana", x.median(), "| p1-p99", x.quantile([.01, .99]).tolist())

if __name__ == "__main__":
    main()
