"""Diagrama de fluxos (estilo Sankey) da transição de votos 1º -> 2º turno, a partir dos fluxos nacionais.

Faixas claras: eleitores que mantêm a situação; faixas escuras: os que mudam, na cor do destino.
Espessura proporcional ao número de eleitores.

Com uma UF como terceiro argumento, desenha só aquele estado (a matriz da UF do modelo), em milhares de eleitores, com
corte proporcional ao do Brasil (0,5 mi de 158,7 mi ≈ 0,32% do eleitorado).

Uso:  python -X utf8 -E -P grafico_fluxos.py saida/ [secao|municipio] [UF]
"""
import os, sys, textwrap
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Rectangle

OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
NIVEL = sys.argv[2] if len(sys.argv) > 2 else "secao"
PREF, OBS = {"secao": ("transicao_secao", "seções eleitorais"), "municipio": ("transicao_uf", "municípios")}[NIVEL]
UF = sys.argv[3].upper() if len(sys.argv) > 3 else None
NOME_UF = {"AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia", "CE": "Ceará",
           "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MG": "Minas Gerais",
           "MS": "Mato Grosso do Sul", "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco",
           "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia",
           "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
           "TO": "Tocantins", "ZZ": "Exterior"}
# unidade dos rótulos: milhões no Brasil, milhares num estado
DIV, SUF, ND = (1e3, "mil", 0) if UF else (1e6, "mi", 1)

ESQ = ["Lula", "Brancos", "Nulos", "Abstenção", "Outros", "Flávio"]   # ordem dos blocos do 1º turno
DIR = ["Lula", "Brancos", "Nulos", "Abstenção", "Flávio"]             # ordem dos blocos do 2º turno
NOME = {"Lula": "LULA", "Flávio": "FLÁVIO", "Outros": "OUTROS CANDIDATOS", "Brancos": "BRANCOS",
        "Nulos": "NULOS", "Abstenção": "ABSTENÇÃO"}
# Lula em vermelho e Flávio em azul, como nos gráficos por estado; nulos em marrom para não confundir com Lula
COR = {"Lula": "#c0392b", "Flávio": "#1d4e89", "Outros": "#8e5fbf", "Brancos": "#9a9a9a",
       "Nulos": "#8c5a3c", "Abstenção": "#2e9a3a"}
MANTEM = {"Lula": "mantêm Lula", "Flávio": "mantêm Flávio", "Brancos": "seguem branco",
          "Nulos": "seguem nulo", "Abstenção": "continuam sem votar"}
MUDA = {"Lula": "→ Lula", "Flávio": "→ Flávio", "Brancos": "→ branco", "Nulos": "→ nulo",
        "Abstenção": "passam a faltar"}
INK, MUTED = "#1f2328", "#6b7280"
# mudanças abaixo de 0,5 mi não são desenhadas (poluiriam o gráfico); ficam listadas no rodapé.
# Quem mantém a situação é sempre desenhado.
# O espaço deles continua reservado nos blocos, para a altura de cada bloco seguir proporcional ao total.
MIN_DESENHO = MIN_ROTULO = 0.5e6
MIN_LISTA = 0.1e6   # no rodapé, os omitidos abaixo disso entram só na soma
def un(v, nd=None):
    return f"{br(v / DIV, ND if nd is None else nd)}"

def br(x, nd=1):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def tinta(cor, a):
    c = np.array(matplotlib.colors.to_rgb(cor))
    return tuple(1 - a * (1 - c))   # mistura com branco

def faixa(ax, x0, y0a, y0b, x1, y1a, y1b, **kw):
    """faixa entre o segmento vertical [y0a, y0b] em x0 e [y1a, y1b] em x1, com bordas em curva de Bézier"""
    xm = (x0 + x1) / 2
    v = [(x0, y0a), (xm, y0a), (xm, y1a), (x1, y1a), (x1, y1b), (xm, y1b), (xm, y0b), (x0, y0b), (x0, y0a)]
    c = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.LINETO, Path.CURVE4, Path.CURVE4, Path.CURVE4,
         Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(v, c), lw=0, **kw))

def bezier(t, x0, y0, x1, y1):
    xm = (x0 + x1) / 2
    p = [(x0, y0), (xm, y0), (xm, y1), (x1, y1)]
    b = [(1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3]
    return sum(w * q[0] for w, q in zip(b, p)), sum(w * q[1] for w, q in zip(b, p))

def main():
    global MIN_DESENHO, MIN_ROTULO, MIN_LISTA
    if UF:
        m = pd.read_csv(os.path.join(OUT, f"{PREF}_matrizes.csv")).query("uf == @UF")
        F = m.pivot(index="de", columns="para", values="eleitores").loc[ESQ, DIR[:]]
        escala = F.to_numpy().sum() / pd.read_csv(os.path.join(OUT, f"{PREF}_fluxos_brasil.csv"), index_col=0).to_numpy().sum()
        MIN_DESENHO = MIN_ROTULO = 0.5e6 * escala; MIN_LISTA = 0.1e6 * escala
    else:
        F = pd.read_csv(os.path.join(OUT, f"{PREF}_fluxos_brasil.csv"), index_col=0)
    tot1, tot2 = F.sum(axis=1), F.sum(axis=0)
    total = tot1.sum()
    gap = 0.035 * total
    X0, X1, LARG = 0.0, 1.0, 0.012

    # Posição dos blocos. Cada grupo presente nos dois turnos ganha uma faixa horizontal: quem mantém a situação
    # fica na mesma altura nos dois lados (faixa reta). Os fluxos para grupos de cima saem acima dessa faixa e
    # os para grupos de baixo saem abaixo; na direita, idem para as entradas. Outros só existe no 1º turno e
    # ocupa uma faixa própria, só à esquerda. Cada bloco segue com altura proporcional ao total do grupo.
    pos = {k: i for i, k in enumerate(ESQ)}
    pe, pd_, cortes, y = {}, {}, {}, 0.0
    for k in ESQ:
        if k not in DIR:
            pe[k] = (y, y - tot1[k])
            c = y
            for b in DIR:
                cortes[(k, b, "e")] = c; c -= F.loc[k, b]
            y -= tot1[k] + gap
            continue
        sobe_e = [b for b in DIR if b != k and pos[b] < pos[k]]; desce_e = [b for b in DIR if b != k and pos[b] > pos[k]]
        sobe_d = [a for a in ESQ if a != k and pos[a] < pos[k]]; desce_d = [a for a in ESQ if a != k and pos[a] > pos[k]]
        acima_e, abaixo_e = F.loc[k, sobe_e].sum(), F.loc[k, desce_e].sum()
        acima_d, abaixo_d = F.loc[sobe_d, k].sum(), F.loc[desce_d, k].sum()
        reta = y - max(acima_e, acima_d)          # topo da faixa de quem mantém
        fim = reta - F.loc[k, k]
        pe[k] = (reta + acima_e, fim - abaixo_e)
        pd_[k] = (reta + acima_d, fim - abaixo_d)
        c = pe[k][0]
        for b in sobe_e + [k] + desce_e:
            cortes[(k, b, "e")] = c; c -= F.loc[k, b]
        c = pd_[k][0]
        for a in sobe_d + [k] + desce_d:
            cortes[(a, k, "d")] = c; c -= F.loc[a, k]
        y = fim - max(abaixo_e, abaixo_d) - gap
    altura = -(y + gap)
    desloca = lambda p: {k: (t + altura, b + altura) for k, (t, b) in p.items()}
    pe, pd_ = desloca(pe), desloca(pd_)
    cortes = {k: v + altura for k, v in cortes.items()}

    fig, ax = plt.subplots(figsize=(16, 10.5))
    ax.set_xlim(-0.33, 1.33); ax.set_ylim(-0.04 * altura, altura * 1.13); ax.axis("off")

    # desenha primeiro os que mantêm (claros, ao fundo, sempre), depois os que mudam (só a partir de MIN_DESENHO)
    fluxos = [(a, b) for a in ESQ for b in DIR if a == b or F.loc[a, b] >= MIN_DESENHO]
    fluxos.sort(key=lambda ab: (ab[0] != ab[1], -F.loc[ab]))
    rotulos = []
    for a, b in fluxos:
        v = F.loc[a, b]
        y0, y1 = cortes[(a, b, "e")], cortes[(a, b, "d")]
        mesmo = a == b
        faixa(ax, X0 + LARG, y0, y0 - v, X1, y1, y1 - v,
              facecolor=tinta(COR[b], .18) if mesmo else COR[b], alpha=1 if mesmo else .62, zorder=1 if mesmo else 2)
        if mesmo or v >= MIN_ROTULO:
            rotulos.append((a, b, v, y0 - v / 2, y1 - v / 2))

    # rótulos: os que mantêm no meio da faixa; os que mudam ao longo da curva, sem encostar uns nos outros
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    ocupado = []
    for a, b, v, ym0, ym1 in sorted(rotulos, key=lambda r: (r[0] != r[1], -r[2])):
        mesmo = a == b
        txt = f"{un(v)} {MANTEM[b]}" if mesmo else f"{un(v)} {MUDA[b]}"
        for t in ([.5] if mesmo else [.5, .38, .62, .28, .72, .2, .8]):
            x, y = bezier(t, X0 + LARG, ym0, X1, ym1)
            el = ax.text(x, y, txt, ha="center", va="center", zorder=5,
                         fontsize=12 if mesmo else 10.5, weight="normal" if mesmo else "bold",
                         color=COR[b] if mesmo else matplotlib.colors.to_hex(np.array(matplotlib.colors.to_rgb(COR[b])) * .8),
                         bbox=dict(facecolor=tinta(COR[b], .12) if mesmo else "white", edgecolor="none",
                                   pad=2.5 if mesmo else 1.2, alpha=.92))
            bb = el.get_window_extent(rend).expanded(1.04, 1.25)
            if not any(bb.overlaps(o) for o in ocupado):
                ocupado.append(bb); break
            el.remove()

    # blocos e textos das colunas; rótulos de blocos pequenos e vizinhos são afastados até não se tocarem,
    # com um traço ligando o rótulo ao bloco quando ele sai do lugar
    def afasta(pos, h):
        ks = list(pos)                      # de cima para baixo
        y = {k: (pos[k][0] + pos[k][1]) / 2 for k in ks}
        for _ in range(50):
            for a, b in zip(ks, ks[1:]):
                falta = h - (y[a] - y[b])
                if falta > 0:
                    y[a] += falta / 2; y[b] -= falta / 2
        return y

    ye = afasta(pe, .085 * altura)
    for k, (yt, yb) in pe.items():
        ax.add_patch(Rectangle((X0, yb), LARG, yt - yb, color=COR[k], zorder=3))
        yc, yl = (yt + yb) / 2, ye[k]
        if abs(yl - yc) > .005 * altura:
            ax.plot([X0 - .004, X0 - .016], [yc, yl], color=MUTED, lw=.8)
        ax.text(X0 - .02, yl + .004 * altura, NOME[k], ha="right", va="bottom", fontsize=12, weight="bold", color=INK)
        ax.text(X0 - .02, yl + .002 * altura, f"{un(tot1[k])} {SUF}", ha="right", va="top", fontsize=19,
                weight="bold", color=COR[k])
    yd = afasta(pd_, .12 * altura)
    for k, (yt, yb) in pd_.items():
        ax.add_patch(Rectangle((X1, yb), LARG, yt - yb, color=COR[k], zorder=3))
        yc, yl = (yt + yb) / 2, yd[k]
        if abs(yl - yc) > .005 * altura:
            ax.plot([X1 + LARG + .004, X1 + LARG + .016], [yc, yl], color=MUTED, lw=.8)
        saldo = tot2[k] - tot1[k]
        ax.text(X1 + LARG + .02, yl + .03 * altura, NOME[k], ha="left", va="bottom", fontsize=12, weight="bold", color=INK)
        ax.text(X1 + LARG + .02, yl + .028 * altura, f"{un(tot2[k])} {SUF}", ha="left", va="top", fontsize=19,
                weight="bold", color=COR[k])
        ax.text(X1 + LARG + .02, yl - .022 * altura, f"{'+' if saldo > 0 else '−'}{un(abs(saldo))} {SUF} no saldo",
                ha="left", va="top", fontsize=11, color=COR[k])

    topo = altura * 1.1
    ax.text(-0.33, topo, "1º TURNO", fontsize=17, weight="bold", color=INK, va="bottom")
    ax.text(-0.33, topo, "Resultado oficial" + (f" — {NOME_UF.get(UF, UF)}" if UF else ""), fontsize=11, color=MUTED, va="top")
    ax.text(1.33, topo, "2º TURNO", fontsize=17, weight="bold", color=INK, va="bottom", ha="right")
    ax.text(1.33, topo, "Estimado pelo modelo", fontsize=11, color=MUTED, va="top", ha="right")
    ax.add_patch(Rectangle((.3, topo + .003 * altura), .025, .012 * altura, color="#d9d9d9", transform=ax.transData))
    ax.text(.333, topo + .009 * altura, "Mantêm a situação", fontsize=11, color=INK, va="center")
    ax.add_patch(Rectangle((.53, topo + .003 * altura), .025, .012 * altura, color="#7a7a7a"))
    ax.text(.563, topo + .009 * altura, "Mudam de situação", fontsize=11, color=INK, va="center")
    ax.text(.5, topo - .012 * altura, "Espessura das faixas proporcional ao número de eleitores", fontsize=10,
            color=MUTED, va="top", ha="center")
    # rodapé: fluxos omitidos do desenho, do maior para o menor
    DESTINO = {"Lula": "Lula", "Flávio": "Flávio", "Brancos": "branco", "Nulos": "nulo", "Abstenção": "abstenção"}
    omit = sorted(((F.loc[a, b], a, b) for a in ESQ for b in DIR if a != b and F.loc[a, b] < MIN_DESENHO), reverse=True)
    itens = [f"{a} {'seguem ' + DESTINO[b] if a == b else '→ ' + DESTINO[b]} {un(v, None if UF else 2)}"
             for v, a, b in omit if v >= MIN_LISTA]
    resto = [v for v, a, b in omit if v < MIN_LISTA]
    lista = " · ".join(itens) + (f" · demais {len(resto)} fluxos somam {un(sum(resto), None if UF else 2)}" if resto else "")
    fig.text(.012, .1, f"Mudanças menores que {un(MIN_DESENHO)} {SUF}, não desenhadas (em {SUF}):", fontsize=10,
             color=INK, weight="bold", va="top")
    fig.text(.012, .078, textwrap.fill(lista, 190), fontsize=10, color=INK, va="top", linespacing=1.5)
    fig.text(.012, .01, (f"Em milhares de eleitores. Matriz de transição de {NOME_UF.get(UF, UF)} estimada por inferência "
             f"ecológica sobre {OBS}. Fonte: TSE." if UF else f"Em milhões de eleitores. Matriz de transição estimada por "
             f"inferência ecológica (uma matriz por estado, sobre {OBS}), somada para o Brasil. Fonte: TSE."),
             fontsize=9, color=MUTED)
    plt.subplots_adjust(left=.01, right=.99, top=.99, bottom=.12)
    plt.savefig(os.path.join(OUT, f"{PREF}_fluxos{'_' + UF.lower() if UF else ''}.png"), dpi=130)

if __name__ == "__main__":
    main()
