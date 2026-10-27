"""Modelo de transição de votos 1º -> 2º turno (Presidente 2026), por inferência ecológica.

Grupos do 1º turno: Lula, Flávio, Outros, Brancos, Nulos, Abstenção
Grupos do 2º turno: Lula, Flávio, Brancos, Nulos, Abstenção

Para cada município i, a composição do eleitorado no 2º turno (y_i, em frações) é modelada como
y_i = x_i · P, onde x_i é a composição no 1º turno e P é a matriz de transição (linhas somam 1,
entradas entre 0 e 1). P é estimada por mínimos quadrados ponderados pelo eleitorado, uma por região;
o resultado nacional soma os fluxos das regiões. A incerteza vem de bootstrap dos municípios.

Hipótese central (inferência ecológica): dentro de uma região, eleitores de um mesmo grupo se comportam
de forma parecida em todos os municípios. Se isso não valer, as estimativas podem ser enviesadas.

Uso:  python -E -P transicao.py saida/ [n_bootstrap]
"""
import sys, os, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
from scipy.optimize import minimize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
NBOOT = int(sys.argv[2]) if len(sys.argv) > 2 else 200
ELEICOES = {1: "6257", 2: "6258"}
G1 = ["Lula", "Flávio", "Outros", "Brancos", "Nulos", "Abstenção"]
G2 = ["Lula", "Flávio", "Brancos", "Nulos", "Abstenção"]
REG = {"N": "AC AP AM PA RO RR TO", "NE": "AL BA CE MA PB PE PI RN SE", "CO": "DF GO MT MS",
       "SE": "ES MG RJ SP", "S": "PR RS SC", "Exterior": "ZZ"}
REG_DE = {u.lower(): r for r, us in REG.items() for u in us.split()}

def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))

def baixa(turno, uf, cd):
    e = ELEICOES[turno]
    pasta = os.path.join(AQUI, f"tse_{turno}t_json")
    path = os.path.join(pasta, f"{uf}{cd}.json")
    if not os.path.exists(path):
        os.makedirs(pasta, exist_ok=True)
        data = get(f"https://resultados.tse.jus.br/oficial/ele2026/{e}/dados/{uf}/{uf}{cd}-c0001-e00{e}-u.json")
        json.loads(data)
        with open(path, "wb") as f:
            f.write(data)
    with open(path, "rb") as f:
        return json.loads(f.read())

def linha(j):
    r = {"Lula": 0, "Flávio": 0, "Outros": 0}
    for a in j["carg"][0]["agr"]:
        for p in a["par"]:
            for k in p["cand"]:
                nm = k["nmu"].upper()
                g = "Lula" if "LULA" in nm else "Flávio" if "FLAVIO" in nm or "FLÁVIO" in nm else "Outros"
                r[g] += int(k["vap"])
    r["Brancos"] = int(j["v"]["vb"])
    r["Nulos"] = int(j["v"]["tvn"])
    r["Abstenção"] = int(j["e"]["a"])
    r["eleitores"] = int(j["e"]["te"])
    if j["s"]["pst"] != "100,00":
        print("ATENÇÃO, apuração incompleta:", j["cdabr"], j["s"]["pst"])
    return r

def dados():
    cfg = json.loads(get(f"https://resultados.tse.jus.br/oficial/ele2026/{ELEICOES[2]}/config/mun-e00{ELEICOES[2]}-cm.json"))
    muns = [(a["cd"], m["cd"], m["nm"]) for a in cfg["abr"] for m in a["mu"]]
    tabs = {}
    for t in (1, 2):
        with ThreadPoolExecutor(12) as ex:
            js = list(ex.map(lambda m: baixa(t, m[0], m[1]), muns))
        tabs[t] = pd.DataFrame([linha(j) for j in js])
    d = pd.DataFrame({"uf": [m[0].upper() for m in muns], "cd": [m[1] for m in muns], "nome": [m[2] for m in muns]})
    d["regiao"] = [REG_DE[m[0]] for m in muns]
    for t, g in ((1, G1), (2, G2)):
        for c in g + ["eleitores"]:
            d[f"{c}_{t}"] = tabs[t][c].values
    # confere que cada turno fecha: grupos somam o eleitorado
    for t, g in ((1, G1), (2, G2)):
        dif = (d[[f"{c}_{t}" for c in g]].sum(axis=1) - d[f"eleitores_{t}"]).abs().max()
        print(f"turno {t}: maior diferença entre soma dos grupos e eleitorado num município = {dif}")
    return d

def ajusta(X, Y, w, P0=None, prior=None, lam=0.0):
    """mínimos quadrados ponderados com linhas de P somando 1 e entradas em [0,1].
    Com prior, soma lam·||P - prior||² (lam em "municípios médios"), puxando P para o prior."""
    k1, k2 = X.shape[1], Y.shape[1]
    w = w / w.mean()
    Xw, Yw = X * np.sqrt(w)[:, None], Y * np.sqrt(w)[:, None]
    A, B = Xw.T @ Xw, Xw.T @ Yw   # forma quadrática: soma ||Xw P - Yw||² = tr(P'AP) - 2 tr(P'B) + const
    if prior is not None and lam > 0:
        # peso de cada linha proporcional à informação média que um município traz sobre ela,
        # para que lam valha de fato "lam municípios" (grupos pequenos têm pouca informação)
        D = np.diag(np.diag(A)) / w.sum()
        A, B = A + lam * D, B + lam * D @ prior
    # divide pelo peso total: não muda o ótimo, mas mantém a função na escala de 1 mesmo com centenas de
    # milhares de observações (sem isso o SLSQP perde precisão na busca linear com dados por seção)
    A, B = A / w.sum(), B / w.sum()
    f = lambda p: (np.sum(p.reshape(k1, k2) * (A @ p.reshape(k1, k2))) - 2 * np.sum(p.reshape(k1, k2) * B))
    g = lambda p: (2 * (A @ p.reshape(k1, k2)) - 2 * B).ravel()
    cons = [{"type": "eq", "fun": (lambda p, i=i: p.reshape(k1, k2)[i].sum() - 1),
             "jac": (lambda p, i=i: np.eye(k1)[i][:, None].repeat(k2, 1).ravel())} for i in range(k1)]
    p0 = np.full(k1 * k2, 1 / k2) if P0 is None else P0.ravel()
    r = minimize(f, p0, jac=g, bounds=[(0, 1)] * (k1 * k2), constraints=cons, method="SLSQP",
                 options={"maxiter": 500, "ftol": 1e-12})
    if not r.success:
        print("ATENÇÃO, otimizador não convergiu:", r.message)
    return r.x.reshape(k1, k2)

def matrizes(d):
    X1 = d[[f"{c}_1" for c in G1]].to_numpy(float)
    Y2 = d[[f"{c}_2" for c in G2]].to_numpy(float)
    ok = (X1.sum(1) > 0) & (Y2.sum(1) > 0)   # há cidades do exterior sem eleitor
    X1, Y2 = X1[ok], Y2[ok]
    X = X1 / X1.sum(1, keepdims=True)
    Y = Y2 / Y2.sum(1, keepdims=True)
    return X, Y, X1.sum(1), X1, Y2

def modelo(d, rng=None, P0s=None):
    """ajusta uma P por região; devolve dict regiao -> (P, fluxos em votos)"""
    res = {}
    for r, g in d.groupby("regiao"):
        if rng is not None:
            g = g.iloc[rng.integers(0, len(g), len(g))]
        X, Y, w, X1, Y2 = matrizes(g)
        P = ajusta(X, Y, w, None if P0s is None else P0s[r])
        # escala os fluxos para que o 2º turno da região bata com o eleitorado do 2º turno
        F = X1.sum(0)[:, None] * P * (Y2.sum() / X1.sum())
        res[r] = (P, F)
    return res

def r2(d, res):
    out = {}
    for r, g in d.groupby("regiao"):
        X, Y, w, _, _ = matrizes(g)
        pred = X @ res[r][0]
        ybar = (Y * w[:, None]).sum(0) / w.sum()
        out[r] = 1 - (w[:, None] * (Y - pred) ** 2).sum(0) / (w[:, None] * (Y - ybar) ** 2).sum(0)
    return pd.DataFrame(out, index=G2).T.round(3)

def main():
    os.makedirs(OUT, exist_ok=True)
    d = dados()
    d.to_csv(os.path.join(OUT, "transicao_municipios.csv"), index=False, encoding="utf-8-sig")
    tot1 = d[[f"{c}_1" for c in G1]].sum(); tot2 = d[[f"{c}_2" for c in G2]].sum()
    print("\ntotais 1º turno:", {c: int(v) for c, v in zip(G1, tot1)})
    print("totais 2º turno:", {c: int(v) for c, v in zip(G2, tot2)})

    res = modelo(d)
    F = sum(f for _, f in res.values())
    print("\nR² por região e grupo do 2º turno (quanto da variação entre municípios o modelo explica):")
    print(r2(d, res))

    # bootstrap
    rng = np.random.default_rng(42)
    P0s = {r: p for r, (p, _) in res.items()}
    boots = []
    for b in range(NBOOT):
        rb = modelo(d, rng, P0s)
        boots.append(sum(f for _, f in rb.values()))
    boots = np.array(boots)
    lo, hi = np.percentile(boots, 5, axis=0), np.percentile(boots, 95, axis=0)

    flux = pd.DataFrame(F, index=G1, columns=G2)
    pct = flux.div(flux.sum(axis=1), axis=0) * 100
    bpct = boots / boots.sum(2, keepdims=True) * 100
    plo, phi = np.percentile(bpct, 5, axis=0), np.percentile(bpct, 95, axis=0)
    print("\nBRASIL, transição em % de cada grupo do 1º turno (intervalo 90% do bootstrap entre colchetes):")
    for i, a in enumerate(G1):
        print(f"  {a:14s}", "  ".join(f"{b}: {pct.iloc[i, j]:5.1f} [{plo[i, j]:4.1f}-{phi[i, j]:4.1f}]" for j, b in enumerate(G2)))
    print("\nBRASIL, fluxos em milhões de eleitores:")
    print((flux / 1e6).round(2))
    print("\nconferência: 2º turno estimado x real (milhões):")
    print(pd.DataFrame({"estimado": flux.sum(axis=0) / 1e6, "real": tot2.values / 1e6}).round(3))
    print("\nganho do Lula decomposto (milhões): vindo de cada grupo do 1º turno, menos o que ele perdeu")
    ganho = flux["Lula"].copy(); ganho["Lula"] = -(flux.loc["Lula"].sum() - flux.loc["Lula", "Lula"])
    print((ganho / 1e6).round(2).to_dict())

    for r, (P, f) in res.items():
        print(f"\n{r}: % de cada grupo do 1º turno")
        print((pd.DataFrame(P, index=G1, columns=G2) * 100).round(1))

    flux.to_csv(os.path.join(OUT, "transicao_fluxos.csv"), encoding="utf-8-sig")
    pd.concat({r: pd.DataFrame(P * 100, index=G1, columns=G2) for r, (P, _) in res.items()}).round(2)\
        .to_csv(os.path.join(OUT, "transicao_por_regiao.csv"), encoding="utf-8-sig")
    grafico(pct, plo, phi, flux)

def grafico(pct, plo, phi, flux, arquivo="transicao.png",
            nota="Inferência ecológica por região (municípios, ponderado pelo eleitorado).",
            titulo="Transição de votos para presidente, 1º → 2º turno 2026"):
    INK, MUTED = "#1f2328", "#6b7280"
    fig, ax = plt.subplots(figsize=(11, 7.2))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("azul", ["#f4f7fb", "#1d4e89"])
    ax.imshow(pct.values, cmap=cmap, vmin=0, vmax=100, aspect="auto")
    for i in range(len(G1)):
        for j in range(len(G2)):
            v = pct.iloc[i, j]
            cor = "white" if v > 55 else INK
            ax.text(j, i - .12, f"{v:.0f}%", ha="center", va="center", fontsize=13, color=cor, weight="bold")
            ax.text(j, i + .22, f"[{plo[i, j]:.0f}–{phi[i, j]:.0f}]  {flux.iloc[i, j] / 1e6:.1f} mi",
                    ha="center", va="center", fontsize=8, color=cor if v > 55 else MUTED)
    tot = flux.sum(axis=1) / 1e6
    ax.set_yticks(range(len(G1)), [f"{g}\n({t:.1f} mi)" for g, t in zip(G1, tot)], color=INK)
    ax.set_xticks(range(len(G2)), G2, color=INK)
    ax.xaxis.tick_top(); ax.xaxis.set_label_position("top")
    ax.set_xlabel("para onde foram no 2º turno", color=INK, labelpad=8)
    ax.set_ylabel("grupo no 1º turno", color=INK)
    ax.set_xticks(np.arange(-.5, len(G2)), minor=True); ax.set_yticks(np.arange(-.5, len(G1)), minor=True)
    ax.grid(which="minor", color="white", lw=2); ax.tick_params(which="both", length=0)
    for s in ax.spines.values(): s.set_visible(False)
    fig.text(.01, .01, nota + " Entre colchetes: intervalo de 90% do bootstrap. Linhas somam 100%.",
             fontsize=8, color=MUTED)
    plt.title(titulo, color=INK, loc="left", pad=34)
    plt.tight_layout(rect=(0, .03, 1, 1))
    plt.savefig(os.path.join(OUT, arquivo), dpi=130)
    plt.close(fig)

if __name__ == "__main__":
    main()
