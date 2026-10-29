"""Testes forenses por seção eleitoral (Presidente 2026). Estatística aponta anomalias, não fraude.

1. Impressão digital (Klimek et al., 2012): comparecimento x % dos votos válidos de cada candidato, nos dois turnos.
   Inserção de votos em nome de ausentes produz uma cauda em direção a comparecimento e votação próximos de 100%.
2. Seções extremas: comparecimento >= 95%; salto de comparecimento entre turnos muito acima das demais seções do
   mesmo local de votação (desvio robusto); para onde foram os votos nessas seções.
3. Resíduos do modelo de transição (matriz do estado, modelo sobre seções): voto real no 2º turno - previsto a partir
   do 1º. Concentração por modelo de urna, comparando seções do mesmo local de votação, e urnas trocadas entre turnos.

Uso:  python -X utf8 -E -P forense.py saida/
"""
import os, sys, zipfile
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "saida")
CHAVE = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
G1 = ["Lula", "Flávio", "Outros", "Brancos", "Nulos", "Abstenção"]
G2 = ["Lula", "Flávio", "Brancos", "Nulos", "Abstenção"]
INK, MUTED, GRID = "#1f2328", "#6b7280", "#e5e7eb"

def br(x, nd=1):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def info_secoes():
    """local de votação, modelo de urna e horário de recebimento do BU de cada seção, nos dois turnos"""
    cache = os.path.join(OUT, "forense_info_secoes.csv.gz")
    if os.path.exists(cache):
        return pd.read_csv(cache, dtype={"cd": str})
    z = zipfile.ZipFile(os.path.join(AQUI, "dados_secao", "detalhe_votacao_secao_2026.zip"))
    cols = ["NR_TURNO", "DS_CARGO"] + CHAVE + ["NR_LOCAL_VOTACAO", "DS_MODELO_URNA", "DT_RECEBIMENTO_BU_HOR_TSE",
                                               "DS_ORIGEM_VOTO", "QT_COMPARECIMENTO"]
    d = pd.read_csv(z.open("detalhe_votacao_secao_2026_BR.csv"), sep=";", encoding="latin-1", usecols=cols)
    d = d[d.DS_CARGO.str.strip().str.upper() == "PRESIDENTE"].drop(columns=["DS_CARGO", "QT_COMPARECIMENTO"])
    w = d.pivot_table(index=CHAVE, columns="NR_TURNO",
                      values=["NR_LOCAL_VOTACAO", "DS_MODELO_URNA", "DT_RECEBIMENTO_BU_HOR_TSE", "DS_ORIGEM_VOTO"],
                      aggfunc="first")
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    w = w.reset_index().rename(columns={"SG_UF": "uf", "CD_MUNICIPIO": "cd"})
    w["cd"] = w.cd.astype(str)
    w.to_csv(cache, index=False)
    return w

def base():
    s = pd.read_csv(os.path.join(OUT, "transicao_secoes.csv.gz"), dtype={"cd": str})
    s = s.merge(info_secoes(), on=["uf", "cd", "NR_ZONA", "NR_SECAO"], how="left")
    s["local"] = s.uf + "-" + s.cd + "-" + s.NR_ZONA.astype(str) + "-" + s.NR_LOCAL_VOTACAO_2.astype("Int64").astype(str)
    s["zona"] = s.uf + "-" + s.cd + "-" + s.NR_ZONA.astype(str)
    for t, g in ((1, G1), (2, G2)):
        e = s[f"eleitores_{t}"].clip(lower=1)
        s[f"comp_{t}"] = 100 * (1 - s[f"Abstenção_{t}"] / e)
        validos = s[f"Lula_{t}"] + s[f"Flávio_{t}"] + (s.Outros_1 if t == 1 else 0)
        for c in ("Lula", "Flávio"):
            s[f"pct{c}_{t}"] = 100 * s[f"{c}_{t}"] / validos.clip(lower=1)
    s["dcomp"] = s.comp_2 - s.comp_1
    return s

# ---------------------------------------------------------------- 1. impressão digital
def klimek(s):
    fig, axs = plt.subplots(2, 2, figsize=(13, 11), sharex=True, sharey=True)
    linhas = []
    ok = s[(s.eleitores_1 >= 50)]                      # tira seções minúsculas, que geram porcentagens extremas
    for i, t in enumerate((1, 2)):
        for j, c in enumerate(("Lula", "Flávio")):
            ax = axs[i, j]
            h = ax.hist2d(ok[f"comp_{t}"], ok[f"pct{c}_{t}"], bins=[np.arange(30, 100.5, 1), np.arange(0, 100.5, 1)],
                          norm=LogNorm(vmin=1), cmap="viridis")
            ax.set_title(f"{t}º turno — {c}", loc="left", fontsize=12, weight="bold", color=INK)
            ax.grid(color="white", lw=.3, alpha=.4)
            canto = ((ok[f"comp_{t}"] >= 95) & (ok[f"pct{c}_{t}"] >= 95)).sum()
            linhas.append({"turno": t, "candidato": c, "secoes_comp95_voto95": int(canto),
                           "corr_comparecimento_voto": ok[f"comp_{t}"].corr(ok[f"pct{c}_{t}"])})
    for ax in axs[1]: ax.set_xlabel("Comparecimento na seção (%)", color=INK)
    for ax in axs[:, 0]: ax.set_ylabel("% dos votos válidos do candidato", color=INK)
    fig.colorbar(h[3], ax=axs, shrink=.6, label="número de seções (escala log)")
    fig.suptitle("Impressão digital eleitoral: comparecimento × votação, por seção", x=.01, ha="left", fontsize=14,
                 color=INK)
    fig.text(.01, .01, f"{br(len(ok), 0)} seções com pelo menos 50 eleitores. Inserção de votos em nome de ausentes "
             "apareceria como uma mancha separada ou cauda no canto superior direito (comparecimento e votação ~100%).",
             fontsize=8.5, color=MUTED)
    plt.savefig(os.path.join(OUT, "forense_klimek.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)
    r = pd.DataFrame(linhas)
    print("\n1) IMPRESSÃO DIGITAL"); print(r.round(3).to_string(index=False))
    r.round(4).to_csv(os.path.join(OUT, "forense_klimek.csv"), index=False, encoding="utf-8-sig")
    return r

# ---------------------------------------------------------------- 2. seções extremas
def extremos(s):
    print("\n2) SEÇÕES EXTREMAS")
    for t in (1, 2):
        alta = s[(s[f"comp_{t}"] >= 95) & (s[f"eleitores_{t}"] >= 50)]
        print(f"  {t}º turno: {len(alta)} seções com comparecimento >= 95% (de {br(len(s), 0)}); "
              f"% Lula médio nelas {br(alta[f'pctLula_{t}'].mean())}% (Brasil {br(s[f'pctLula_{t}'].mean())}%)")
    # salto de comparecimento comparado às outras seções do mesmo local (mediana do local sem a própria seção)
    g = s.groupby("local")
    n = g.dcomp.transform("size")
    soma = g.dcomp.transform("sum")
    s["dcomp_vizinhas"] = (soma - s.dcomp) / (n - 1).replace(0, np.nan)        # média das outras seções do local
    s["desvio"] = s.dcomp - s.dcomp_vizinhas
    v = s[(n >= 4) & (s.eleitores_1 >= 50)].copy()
    mad = 1.4826 * (v.desvio - v.desvio.median()).abs().median()
    v["z"] = (v.desvio - v.desvio.median()) / mad
    print(f"  salto de comparecimento entre turnos: média {br(s.dcomp.mean(), 2)} pp; desvio em relação às vizinhas do "
          f"mesmo local: desvio-padrão robusto {br(mad, 2)} pp ({br(len(v), 0)} seções em locais com 4+ seções)")
    for lim in (4, 6, 8):
        print(f"  |z| >= {lim}: {int((v.z >= lim).sum())} acima, {int((v.z <= -lim).sum())} abaixo")
    # para onde foram os votos nas seções que mais subiram: ganho de cada candidato vs as vizinhas do local
    for c in ("Lula", "Flávio"):
        v[f"ganho_{c}"] = v[f"{c}_2"] - v[f"{c}_1"]
        gl = v.groupby("local")[f"ganho_{c}"]
        v[f"ganho_{c}_viz"] = (gl.transform("sum") - v[f"ganho_{c}"]) / (gl.transform("size") - 1)
    sobe = v[v.z >= 6]
    desce = v[v.z <= -6]
    print(f"  seções com salto >= 6 desvios acima das vizinhas: {len(sobe)}; abaixo: {len(desce)} "
          f"(se a distribuição fosse normal, ~0; caudas pesadas são comuns em dados reais)")
    for nome, x in (("acima", sobe), ("abaixo", desce)):
        if len(x):
            print(f"    {nome}: salto médio {br(x.dcomp.mean())} pp vs {br(x.dcomp_vizinhas.mean())} pp nas vizinhas; "
                  f"ganho Lula {br(x.ganho_Lula.mean())} vs {br(x.ganho_Lula_viz.mean())} nas vizinhas; "
                  f"ganho Flávio {br(x['ganho_Flávio'].mean())} vs {br(x['ganho_Flávio_viz'].mean())}; "
                  f"eleitores médios {br(x.eleitores_1.mean(), 0)}; votos extras líquidos Lula − Flávio no total: "
                  f"{br(((x.ganho_Lula - x.ganho_Lula_viz) - (x['ganho_Flávio'] - x['ganho_Flávio_viz'])).sum(), 0)}")
    print("  UFs das seções com salto >= 6 desvios acima:", sobe.uf.value_counts().head(8).to_dict())
    # quantos votos estão em jogo em todas as seções com |z| >= 4
    caud = v[v.z.abs() >= 4]
    liquido = ((caud.ganho_Lula - caud.ganho_Lula_viz) - (caud["ganho_Flávio"] - caud["ganho_Flávio_viz"])).sum()
    print(f"  todas as seções com |z| >= 4: {len(caud)}; efeito líquido na diferença Lula − Flávio em relação às vizinhas:"
          f" {br(liquido, 0)} votos (diferença final: 4.430.191)")
    cols = ["uf", "cd", "NR_ZONA", "NR_SECAO", "local", "eleitores_1", "comp_1", "comp_2", "dcomp", "dcomp_vizinhas",
            "z", "Lula_1", "Lula_2", "Flávio_1", "Flávio_2", "DS_MODELO_URNA_1", "DS_MODELO_URNA_2"]
    v.loc[v.z.abs() >= 6, cols].sort_values("z", ascending=False).round(2) \
        .to_csv(os.path.join(OUT, "forense_extremos.csv"), index=False, encoding="utf-8-sig")
    alta = {t: s[(s[f"comp_{t}"] >= 95) & (s[f"eleitores_{t}"] >= 50)] for t in (1, 2)}
    resumo = {"secoes": len(s), "comp95_t1": len(alta[1]), "comp95_t2": len(alta[2]),
              "pctLula_comp95_t2": alta[2].pctLula_2.mean(), "pctLula_brasil_t2": s.pctLula_2.mean(),
              "eleitores_mediana_comp95_t2": alta[2].eleitores_2.median(), "eleitores_mediana_brasil": s.eleitores_2.median(),
              "secoes_comparadas_local": len(v), "dp_robusto_desvio_pp": mad,
              "z4_acima": int((v.z >= 4).sum()), "z4_abaixo": int((v.z <= -4).sum()),
              "z6_acima": len(sobe), "z6_abaixo": len(desce), "secoes_z4": len(caud), "efeito_liquido_z4": liquido}
    pd.Series(resumo).to_csv(os.path.join(OUT, "forense_extremos_resumo.csv"), header=["valor"], encoding="utf-8-sig")
    # gráfico da distribuição do desvio
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.hist(v.z.clip(-15, 15), bins=np.arange(-15, 15.25, .25), color="#4b6584", log=True)
    from scipy.stats import norm
    xs = np.linspace(-15, 15, 400)
    ax.plot(xs, len(v) * .25 * norm.pdf(xs), color="#c0392b", lw=1.5, label="se fosse normal")
    ax.set_xlabel("Salto de comparecimento em relação às outras seções do mesmo local (desvios robustos; cortado em ±15)",
                  color=INK)
    ax.set_ylabel("Seções (escala log)", color=INK); ax.legend(frameon=False)
    ax.set_title("Salto de comparecimento entre turnos: cada seção contra as vizinhas do mesmo local", loc="left",
                 weight="bold", color=INK)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "forense_salto_comparecimento.png"), dpi=120); plt.close(fig)
    return v

# ---------------------------------------------------------------- 3. resíduos do modelo
def residuos(s):
    print("\n3) RESÍDUOS DO MODELO DE TRANSIÇÃO")
    m = pd.read_csv(os.path.join(OUT, "transicao_secao_matrizes.csv"))
    pred = {c: np.zeros(len(s)) for c in G2}
    for u, g in s.groupby("uf"):
        P = m[m.uf == u].pivot(index="de", columns="para", values="pct").loc[G1, G2].to_numpy() / 100
        X1 = g[[f"{c}_1" for c in G1]].to_numpy(float)
        Y = X1 @ P * (g.eleitores_2.to_numpy() / g.eleitores_1.clip(lower=1).to_numpy())[:, None]
        for k, c in enumerate(G2):
            pred[c][s.index.get_indexer(g.index)] = Y[:, k]
    s["res_Lula"] = s.Lula_2 - pred["Lula"]
    s["res_Flavio"] = s["Flávio_2"] - pred["Flávio"]
    s["res_dif"] = s.res_Lula - s.res_Flavio          # resíduo na diferença Lula − Flávio
    print(f"  resíduo na diferença Lula − Flávio por seção: média {br(s.res_dif.mean(), 2)}, desvio-padrão "
          f"{br(s.res_dif.std(), 1)} votos")
    # quanto da variância do resíduo é explicada pelo local e pela zona (agrupamento esperado: geografia)
    tot = s.res_dif.var()
    for nivel in ("zona", "local"):
        entre = s.groupby(nivel).res_dif.transform("mean").var()
        print(f"  parte da variância do resíduo entre {nivel}s: {br(100 * entre / tot)}%")
    # modelo de urna: bruto e dentro do mesmo local de votação
    s["modelo"] = s.DS_MODELO_URNA_2.fillna("?")
    print("  seções por modelo de urna (2º turno):", s.modelo.value_counts().to_dict())
    bruto = s.groupby("modelo").res_dif.agg(["mean", "size"])
    s["res_dentro"] = s.res_dif - s.groupby("local").res_dif.transform("mean")
    misto = s.groupby("local").modelo.transform("nunique") > 1
    dentro = s[misto].groupby("modelo").res_dentro.agg(["mean", "size"])
    # erro-padrão do contraste dentro do local, agrupado por local
    tab = bruto.join(dentro, rsuffix="_dentro_local", how="left")
    eps = {}
    for mod, g in s[misto].groupby("modelo"):
        por_local = g.groupby("local").res_dentro.sum()
        eps[mod] = np.sqrt((por_local ** 2).sum()) / len(g)
    tab["ep_dentro_local"] = pd.Series(eps)
    print("  resíduo médio na diferença Lula − Flávio por modelo de urna (bruto e dentro do mesmo local):")
    print(tab.round(3).to_string())
    # urnas trocadas entre os turnos
    s["trocou"] = (s.DS_MODELO_URNA_1 != s.DS_MODELO_URNA_2) & s.DS_MODELO_URNA_1.notna()
    tr = s[s.trocou]
    print(f"  seções com modelo de urna diferente entre turnos: {len(tr)}; resíduo médio dentro do local "
          f"{br(tr.res_dentro.mean(), 2)} (demais {br(s[~s.trocou].res_dentro.mean(), 2)})")
    print("  origem do voto no 2º turno:", s.DS_ORIGEM_VOTO_2.value_counts().to_dict())
    tab.round(4).to_csv(os.path.join(OUT, "forense_modelo_urna.csv"), encoding="utf-8-sig")
    resumo = {"residuo_media": s.res_dif.mean(), "residuo_dp": s.res_dif.std(),
              "pct_var_entre_zonas": 100 * s.groupby("zona").res_dif.transform("mean").var() / tot,
              "pct_var_entre_locais": 100 * s.groupby("local").res_dif.transform("mean").var() / tot,
              "urnas_trocadas": len(tr), "residuo_trocadas": tr.res_dentro.mean(),
              "secoes_fora_da_urna": int((s.DS_ORIGEM_VOTO_2.fillna("") != "Urna Eletrônica").sum())}
    pd.Series(resumo).to_csv(os.path.join(OUT, "forense_residuos_resumo.csv"), header=["valor"], encoding="utf-8-sig")
    # gráfico: resíduo dentro do local por modelo
    fig, axs = plt.subplots(1, 2, figsize=(14, 5))
    axs[0].hist(s.res_dif.clip(-80, 80), bins=160, color="#4b6584", log=True)
    axs[0].set_title("Resíduo na diferença Lula − Flávio por seção", loc="left", weight="bold", color=INK)
    axs[0].set_xlabel("votos (real − previsto pelo modelo; cortado em ±80)", color=INK)
    mods = tab.index.tolist()
    y = np.arange(len(mods))
    axs[1].errorbar(tab["mean_dentro_local"], y, xerr=1.645 * tab["ep_dentro_local"], fmt="o", color="#c0392b",
                    capsize=3, label="dentro do mesmo local (IC 90%)")
    axs[1].scatter(tab["mean"], y, marker="x", color=MUTED, label="bruto")
    axs[1].axvline(0, color="#9ca3af", lw=.8)
    axs[1].set_yticks(y, [f"{m} ({br(n, 0)})" for m, n in zip(mods, tab["size"])])
    axs[1].set_title("Resíduo médio por modelo de urna", loc="left", weight="bold", color=INK)
    axs[1].set_xlabel("votos por seção na diferença Lula − Flávio", color=INK); axs[1].legend(frameon=False)
    for ax in axs:
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "forense_residuos.png"), dpi=120); plt.close(fig)
    return s

def main():
    s = base()
    print(f"seções: {len(s):,} | locais de votação: {s.local.nunique():,} | sem informação de local: "
          f"{int(s.NR_LOCAL_VOTACAO_2.isna().sum())}")
    klimek(s)
    extremos(s)
    residuos(s)

if __name__ == "__main__":
    main()
