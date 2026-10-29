"""Teste de estresse da regressão ganho ~ x + Outros, por seção eleitoral.

Identidade: ganho_Lula + ganho_Flávio = x + Outros_1 em toda seção. Logo os coeficientes das duas regressões somam
1 (x e Outros) e 0 (intercepto e demais controles): basta estimar a do Lula. Também se reporta a forma equivalente
para a diferença Lula − Flávio (coeficiente = 2·coef_Lula − 1).

Especificações:
  base        ganho_L = a·x + c·Outros + k
  peso        idem, ponderado pelo eleitorado
  EF UF       idem, com efeito fixo de UF
  x separado  x dividido em queda da abstenção (dA) e queda de brancos+nulos (dBN)
  força       + votos de Lula e de Flávio no 1º turno
  candidatos  Outros separados por candidato (lê dados_secao/votacao_secao_2026_BR.zip)
  regiões     base, separada por região
Erros-padrão agrupados por zona eleitoral (zona × município).

Uso:  python -X utf8 -E -P estresse_regressao.py saida/
"""
import os, sys, zipfile
import numpy as np, pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "saida")
CHAVE = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]

def outros_por_candidato():
    """votos de cada outro candidato por seção no 1º turno (os 4 maiores + demais)"""
    cache = os.path.join(OUT, "outros_por_candidato_secao.csv.gz")
    rotulo = {"Neto": "Zema", "Santos": "Renan Santos"}   # nome de urna, em vez do último sobrenome
    if os.path.exists(cache):
        return pd.read_csv(cache).rename(columns=rotulo)
    z = zipfile.ZipFile(os.path.join(AQUI, "dados_secao", "votacao_secao_2026_BR.zip"))
    partes, nomes = [], {}
    cols = ["NR_TURNO", "DS_CARGO"] + CHAVE + ["NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS"]
    for ch in pd.read_csv(z.open("votacao_secao_2026_BR.csv"), sep=";", encoding="latin-1", usecols=cols,
                          chunksize=2_000_000):
        ch = ch[(ch.NR_TURNO == 1) & (ch.DS_CARGO.str.strip().str.upper() == "PRESIDENTE")
                & ~ch.NR_VOTAVEL.isin([13, 22, 95, 96])]
        nomes.update(ch.drop_duplicates("NR_VOTAVEL").set_index("NR_VOTAVEL").NM_VOTAVEL.to_dict())
        partes.append(ch.groupby(CHAVE + ["NR_VOTAVEL"]).QT_VOTOS.sum())
    v = pd.concat(partes).groupby(level=list(range(5))).sum().unstack("NR_VOTAVEL", fill_value=0)
    top = v.sum().nlargest(4).index
    out = v[top].copy()
    out.columns = [nomes[n].split()[-1].title() if n in nomes else str(n) for n in top]
    out["Demais"] = v.drop(columns=top).sum(axis=1)
    out = out.reset_index().rename(columns={"SG_UF": "uf", "CD_MUNICIPIO": "cd"})
    out.to_csv(cache, index=False)
    print("outros candidatos separados:", {nomes.get(n, n): int(v[n].sum()) for n in top})
    return out.rename(columns=rotulo)

def ols(d, y, xs, peso=None, ef=None, cluster="cluster"):
    """MQO com efeito fixo opcional (por desvio da média do grupo) e erro-padrão agrupado"""
    Y, X = d[y].astype(float), d[xs].astype(float)
    w = d[peso].astype(float) if peso else pd.Series(1.0, index=d.index)
    if ef:
        mw = lambda s: (s * w).groupby(d[ef]).transform("sum") / w.groupby(d[ef]).transform("sum")
        Y = Y - mw(Y); X = X.apply(mw).rsub(X)
    else:
        X = X.assign(const=1.0)
    Xa, Ya, sw = X.to_numpy(), Y.to_numpy(), np.sqrt(w.to_numpy())
    XtX = (Xa * sw[:, None] ** 2).T @ Xa
    b = np.linalg.solve(XtX, (Xa * sw[:, None] ** 2).T @ Ya)
    u = Ya - Xa @ b
    S = pd.DataFrame(Xa * (w.to_numpy() * u)[:, None]).groupby(d[cluster].to_numpy()).sum().to_numpy()
    inv = np.linalg.inv(XtX)
    se = np.sqrt(np.diag(inv @ (S.T @ S) @ inv))
    r2 = 1 - (w * u ** 2).sum() / (w * (Ya - np.average(Ya, weights=w)) ** 2).sum()
    return pd.DataFrame({"coef": b, "ep": se}, index=X.columns), r2

def main():
    s = pd.read_csv(os.path.join(OUT, "transicao_secoes.csv.gz"), dtype={"cd": str})
    s["cluster"] = s.uf + "-" + s.cd + "-" + s.NR_ZONA.astype(str)
    s["x"] = (s.Lula_2 + s["Flávio_2"]) - (s.Lula_1 + s["Flávio_1"] + s.Outros_1)
    s["dA"] = s["Abstenção_1"] - s["Abstenção_2"]
    s["dBN"] = (s.Brancos_1 + s.Nulos_1) - (s.Brancos_2 + s.Nulos_2)
    s["gL"], s["gF"] = s.Lula_2 - s.Lula_1, s["Flávio_2"] - s["Flávio_1"]
    s["Outros"] = s.Outros_1
    s["Lula1"], s["Flavio1"] = s.Lula_1, s["Flávio_1"]
    print(f"seções: {len(s):,} | zonas (zona × município): {s.cluster.nunique():,}")
    print("identidade gL + gF = x + Outros, maior desvio:", int(((s.gL + s.gF) - (s.x + s.Outros)).abs().max()),
          "| x = dA + dBN, maior desvio:", int((s.x - s.dA - s.dBN).abs().max()),
          "(eleitorado igual nos dois turnos em", f"{100 * (s.eleitores_1 == s.eleitores_2).mean():.2f}% das seções)")

    print("\n1) MÉDIAS POR SEÇÃO")
    med = pd.DataFrame({
        "média": s[["eleitores_1", "Lula_1", "Flávio_1", "Outros_1", "Brancos_1", "Nulos_1", "Abstenção_1",
                    "Lula_2", "Flávio_2", "Brancos_2", "Nulos_2", "Abstenção_2", "x", "dA", "dBN", "gL", "gF"]].mean()})
    med["desvio-padrão"] = s[med.index].std()
    med["p10"], med["p50"], med["p90"] = (s[med.index].quantile(q) for q in (.1, .5, .9))
    print(med.round(2).to_string())

    linhas = []
    def guarda(nome, res, r2):
        t, r2v = res, r2
        linhas.append((nome, t, r2v))
        print(f"\n{nome}  (r² = {r2v:.3f})")
        print(t.assign(t=t.coef / t.ep, coef_diferenca=2 * t.coef - 1).round(4).to_string())

    print("\n2) REGRESSÕES DO GANHO DO LULA (Flávio = 1 − coef para x e Outros; −coef para o resto)")
    guarda("base", *ols(s, "gL", ["x", "Outros"]))
    guarda("peso = eleitorado", *ols(s, "gL", ["x", "Outros"], peso="eleitores_1"))
    guarda("efeito fixo de UF", *ols(s, "gL", ["x", "Outros"], ef="uf"))
    guarda("x separado", *ols(s, "gL", ["dA", "dBN", "Outros"]))
    guarda("x separado + EF UF", *ols(s, "gL", ["dA", "dBN", "Outros"], ef="uf"))
    guarda("+ força no 1º turno", *ols(s, "gL", ["x", "Outros", "Lula1", "Flavio1"]))
    guarda("+ força no 1º turno + EF UF", *ols(s, "gL", ["x", "Outros", "Lula1", "Flavio1"], ef="uf"))

    oc = outros_por_candidato()
    cand = [c for c in oc.columns if c not in ("uf", "cd", "NR_ZONA", "NR_SECAO")]
    s2 = s.merge(oc.assign(cd=oc.cd.astype(str)), on=["uf", "cd", "NR_ZONA", "NR_SECAO"], how="left")
    s2[cand] = s2[cand].fillna(0)
    print("\nconferência: soma dos outros candidatos = Outros_1, maior desvio:",
          int((s2[cand].sum(axis=1) - s2.Outros).abs().max()))
    guarda("Outros por candidato", *ols(s2, "gL", ["x"] + cand))
    guarda("Outros por candidato + EF UF", *ols(s2, "gL", ["x"] + cand, ef="uf"))
    guarda("Outros por candidato + força + EF UF", *ols(s2, "gL", ["x"] + cand + ["Lula1", "Flavio1"], ef="uf"))

    print("\n3) POR REGIÃO (base)")
    reg = []
    for r, g in s.groupby("regiao"):
        t, r2 = ols(g, "gL", ["x", "Outros"])
        reg.append({"região": r, "seções": len(g), "a_x": t.coef["x"], "c_Outros": t.coef["Outros"],
                    "k": t.coef["const"], "r2": r2, "x médio": g.x.mean(), "Outros médio": g.Outros.mean()})
    print(pd.DataFrame(reg).round(3).to_string(index=False))

    tab = pd.concat({n: t.assign(r2=r2) for n, t, r2 in linhas})
    tab.round(5).to_csv(os.path.join(OUT, "estresse_regressao.csv"), encoding="utf-8-sig")
    pd.DataFrame(reg).round(4).to_csv(os.path.join(OUT, "estresse_regressao_regioes.csv"), index=False,
                                      encoding="utf-8-sig")
    med.round(3).to_csv(os.path.join(OUT, "estresse_regressao_medias.csv"), encoding="utf-8-sig")

if __name__ == "__main__":
    main()
