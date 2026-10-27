"""Confere os resultados publicados em saida/ contra o próprio código e contra os totais oficiais.

1. Bases: os grupos de cada turno somam o eleitorado, e as bases por município e por seção têm os mesmos totais.
2. Para cada nível (município e seção): refaz o ajuste do modelo por UF do zero e compara com o CSV salvo.
3. Coerência interna: destinos somam 100%, painel agrupado = soma das células, Brasil = soma das UFs,
   2º turno estimado próximo do real.

Uso:  python -X utf8 -E -P validar.py
Termina com código 1 se alguma checagem falhar.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
AQUI = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(AQUI, "saida")
sys.argv = ["validar", S, "0"]
sys.path.insert(0, AQUI)
import numpy as np, pandas as pd
import transicao as T
import transicao_uf as U

G1, G2 = T.G1, T.G2
falhas = []

def checa(nome, valor, limite):
    ok = valor <= limite
    print(f"   {'ok   ' if ok else 'FALHA'} {nome}: {valor:,.4f} (limite {limite})")
    if not ok:
        falhas.append(nome)

print("1) bases")
mun = pd.read_csv(os.path.join(S, "transicao_municipios.csv"), dtype={"cd": str})
sec = pd.read_csv(os.path.join(S, "transicao_secoes.csv.gz"), dtype={"cd": str})
for nome, b in (("município", mun), ("seção", sec)):
    for t, g in ((1, G1), (2, G2)):
        dif = (b[[f"{c}_{t}" for c in g]].sum(axis=1) - b[f"eleitores_{t}"]).abs()
        print(f"   {nome}, {t}º turno: {len(b):,} linhas; {int((dif > 0).sum())} com grupos ≠ eleitorado "
              f"(maior diferença {int(dif.max())} eleitores)")
for t, g in ((1, G1), (2, G2)):
    for c in g + ["eleitores"]:
        a, s = int(mun[f"{c}_{t}"].sum()), int(sec[f"{c}_{t}"].sum())
        if a != s:
            print(f"   aviso: {c} no {t}º turno difere entre bases: município {a:,} × seção {s:,} ({s - a:+,})")
checa("Lula 2º turno, base por seção × resultado oficial (64.256.232)", abs(sec["Lula_2"].sum() - 64256232), 0)
checa("Flávio 2º turno, base por seção × resultado oficial (59.826.041)", abs(sec["Flávio_2"].sum() - 59826041), 0)

for nivel, base, pref in (("municipio", mun, "transicao_uf"), ("secao", sec, "transicao_secao")):
    print(f"\n2) modelo por UF sobre {nivel}: refaz o ajuste e compara com {pref}_matrizes.csv")
    mat = pd.read_csv(os.path.join(S, f"{pref}_matrizes.csv"))
    ori = pd.read_csv(os.path.join(S, f"{pref}_origens.csv"))
    brs = pd.read_csv(os.path.join(S, f"{pref}_brasil.csv"))
    flx = pd.read_csv(os.path.join(S, f"{pref}_fluxos_brasil.csv"), index_col=0)
    res = U.modelo_uf(base, 5.0)
    dif = max(abs(100 * P[i, j] - mat[(mat.uf == u) & (mat.de == a) & (mat.para == b)].pct.iloc[0])
              for u, (P, F, r, n) in res.items() for i, a in enumerate(G1) for j, b in enumerate(G2))
    checa("maior diferença numa célula de UF (pontos %)", dif, 0.05)
    checa("maior diferença nos fluxos nacionais (eleitores)", (U.nacional(res) - flx).abs().to_numpy().max(), 50)

    print(f"3) coerência interna ({nivel})")
    checa("destinos somam 100% (desvio máximo)", (ori.groupby(["uf", "de"]).pct.sum() - 100).abs().max(), 0.01)
    m = 0
    for dest, cols in U.DESTINOS.items():
        a = mat[mat.para.isin(cols)].groupby(["uf", "de"]).pct.sum()
        b = ori[(ori.para == dest) & (ori.uf != "BRASIL")].set_index(["uf", "de"]).pct
        m = max(m, (a - b.reindex(a.index)).abs().max())
        a = brs[brs.para.isin(cols)].groupby("de").pct.sum()
        b = ori[(ori.para == dest) & (ori.uf == "BRASIL")].set_index("de").pct
        m = max(m, (a - b).abs().max())
    checa("painel agrupado = soma das células (desvio máximo)", m, 0.01)
    soma = mat.groupby(["de", "para"]).eleitores.sum().unstack()[G2].loc[G1]
    checa("Brasil = soma dos fluxos das UFs (eleitores)", (soma - flx).abs().to_numpy().max(), 50)
    fora = ((ori.pct < ori.pct_p5 - 1e-6) | (ori.pct > ori.pct_p95 + 1e-6)).sum()
    print(f"   info  estimativas fora do próprio intervalo de 90%: {fora} de {len(ori)}")
    tot2 = base[[f"{c}_2" for c in G2]].sum().to_numpy()
    checa("2º turno estimado × real, maior diferença relativa (%)",
          (100 * np.abs(flx.sum(axis=0).to_numpy() - tot2) / tot2).max(), 5)

print("\nresultado:", "TUDO OK" if not falhas else f"{len(falhas)} FALHA(S): {falhas}")
sys.exit(1 if falhas else 0)
