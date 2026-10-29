"""Teste 1 — Lei de Benford, calibrada com outras eleições.

1BL (primeiro dígito) nos totais de cada candidato por município (e, para comparação, por zona eleitoral);
2BL (segundo dígito) nas contagens por seção (só contagens >= 10, que têm segundo dígito).
Casos de calibração: 2022 1º e 2º turnos (Lula e Bolsonaro) e 2026 1º turno (Lula e Flávio).
Caso testado: 2026 2º turno (Lula e Flávio).

Com centenas de milhares de seções, o qui-quadrado rejeita Benford em qualquer eleição real; por isso a referência é
a calibração: o caso testado destoa das eleições de referência? Medidas: MAD (desvio absoluto médio entre frequência
observada e esperada; faixas de Nigrini), qui-quadrado e, no 2BL, a média do segundo dígito (esperada 4,187).

Uso:  python -X utf8 -E -P benford.py saida/
"""
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
P1 = np.log10(1 + 1 / np.arange(1, 10))                                     # 1º dígito, 1..9
P2 = np.array([sum(np.log10(1 + 1 / (10 * k + d)) for k in range(1, 10)) for d in range(10)])   # 2º dígito, 0..9
CASOS = [(2022, 1), (2022, 2), (2026, 1), (2026, 2)]
NOME_ADV = {2022: "Bolsonaro", 2026: "Flávio"}

def br(x, nd=4):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def digito(v, pos):
    v = v[v >= (10 if pos == 2 else 1)].astype(np.int64).astype(str)
    return v.str[pos - 1].astype(int).to_numpy()

def mede(dig, esperado, primeiro):
    dom = np.arange(1, 10) if primeiro else np.arange(10)
    obs = np.array([(dig == d).sum() for d in dom])
    n = obs.sum()
    freq = obs / n
    x2 = ((obs - n * esperado) ** 2 / (n * esperado)).sum()
    return {"n": int(n), "MAD": np.abs(freq - esperado).mean(), "qui2": x2,
            "p": chi2.sf(x2, len(dom) - 1), "media": (dom * freq).sum(), "freq": freq}

def main():
    linhas, freqs = [], {}
    for ano, t in CASOS:
        v = pd.read_csv(os.path.join(OUT, f"votacao_{ano}.csv.gz"), dtype={"cd": str}).query("NR_TURNO == @t")
        v = v[v.uf != "ZZ"]                                        # exterior: cidades no mundo, outra lógica
        for col, cand in (("Lula", "Lula"), ("Adv", NOME_ADV[ano])):
            mun = v.groupby(["uf", "cd"])[col].sum()
            zon = v.groupby(["uf", "NR_ZONA"])[col].sum()
            for nivel, serie, pos in (("1BL município", mun, 1), ("1BL zona", zon, 1), ("2BL seção", v[col], 2)):
                r = mede(digito(serie, pos), P1 if pos == 1 else P2, pos == 1)
                papel = "teste" if (ano, t) == (2026, 2) else "calibração"
                linhas.append({"teste": nivel, "eleição": f"{ano} {t}º turno", "candidato": cand, "papel": papel,
                               **{k: r[k] for k in ("n", "MAD", "qui2", "p", "media")}})
                freqs[(nivel, ano, t, col)] = r["freq"]
    r = pd.DataFrame(linhas)
    r.to_csv(os.path.join(OUT, "benford.csv"), index=False, encoding="utf-8-sig")
    for nivel in ("1BL município", "1BL zona", "2BL seção"):
        x = r[r.teste == nivel]
        print(f"\n{nivel}")
        print(x[["eleição", "candidato", "papel", "n", "MAD", "qui2", "p"] + (["media"] if nivel.startswith("2") else [])]
              .round(5).to_string(index=False))
        cal = x[x.papel == "calibração"]
        for _, tt in x[x.papel == "teste"].iterrows():
            z = (tt.MAD - cal.MAD.mean()) / cal.MAD.std()
            print(f"  teste {tt.candidato}: MAD {br(tt.MAD)} | calibração {br(cal.MAD.min())} a {br(cal.MAD.max())} "
                  f"(média {br(cal.MAD.mean())}) | z = {br(z, 2)}")

    # gráficos: frequências observadas x esperadas
    fig, axs = plt.subplots(2, 4, figsize=(18, 8), sharey="row")
    cores = {"Lula": "#c0392b", "Adv": "#1d4e89"}
    for j, (ano, t) in enumerate(CASOS):
        for i, (nivel, esp, dom) in enumerate((("1BL município", P1, np.arange(1, 10)), ("2BL seção", P2, np.arange(10)))):
            ax = axs[i, j]
            ax.plot(dom, esp, color="#1f2328", lw=1.5, ls="--", label="Benford")
            for k, col in enumerate(("Lula", "Adv")):
                ax.bar(dom + (k - .5) * .38, freqs[(nivel, ano, t, col)], width=.38, color=cores[col], alpha=.8,
                       label="Lula" if col == "Lula" else NOME_ADV[ano])
            ax.set_title(f"{nivel} — {ano} {t}º turno" + ("  (TESTE)" if (ano, t) == (2026, 2) else ""), loc="left",
                         fontsize=10.5, weight="bold")
            ax.set_xticks(dom)
            for sp in ("top", "right"): ax.spines[sp].set_visible(False)
            if j == 0: ax.set_ylabel("frequência")
            ax.legend(frameon=False, fontsize=8)
    fig.text(.01, .005, "1BL: primeiro dígito dos totais por município (exterior excluído). 2BL: segundo dígito das "
             "contagens por seção (contagens >= 10). Linha tracejada: frequência esperada pela Lei de Benford.",
             fontsize=8.5, color="#6b7280")
    plt.tight_layout(rect=(0, .02, 1, 1))
    plt.savefig(os.path.join(OUT, "benford.png"), dpi=110)

if __name__ == "__main__":
    main()
