"""Teste 2 — Distribuição de brancos e nulos por seção: Poisson dentro de cada zona eleitoral?

Em cada zona z, com taxa r_z = (brancos da zona) / (comparecimento da zona), o esperado na seção i é
E_i = r_z × comparecimento_i. Se cada eleitor tem a mesma probabilidade, as contagens são Poisson (binomial) e
    X²_z = Σ (O_i − E_i)² / E_i  ~  qui-quadrado com (n_z − 1) graus de liberdade
O índice de dispersão φ_z = X²_z / (n_z − 1) é o VMR ajustado pelo tamanho de cada seção (≈ 1 sob Poisson).
φ > 1: mais variação que Poisson (natural: bairros diferentes dentro da zona). φ < 1: menos variação que o acaso
permite — o sinal típico de números fabricados, regulares demais.
Também: VMR bruto das contagens por zona e um Poisson simulado com as mesmas taxas e comparecimentos (referência).
Calibração: 2022 1º e 2º turnos e 2026 1º turno; teste: 2026 2º turno.

Uso:  python -X utf8 -E -P poisson_brancos_nulos.py saida/
"""
import os, sys
import numpy as np, pandas as pd
from scipy.stats import chi2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1] if len(sys.argv) > 1 else "saida"
CASOS = [(2022, 1), (2022, 2), (2026, 1), (2026, 2)]
MIN_SECOES = 20

def br(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def por_zona(v, col, rng):
    v = v[v.Comp > 0]
    g = v.groupby(["uf", "NR_ZONA"])
    taxa = g[col].transform("sum") / g.Comp.transform("sum")
    E = taxa * v.Comp
    ok = E > 0
    v, E = v[ok], E[ok]
    sim = rng.poisson(E)                                     # mesmo modelo, contagens geradas por Poisson
    d = pd.DataFrame({"z": v.uf + "-" + v.NR_ZONA.astype(str), "O": v[col], "E": E, "S": sim})
    d["x2"] = (d.O - d.E) ** 2 / d.E
    d["x2s"] = (d.S - d.E) ** 2 / d.E
    z = d.groupby("z").agg(n=("O", "size"), X2=("x2", "sum"), X2s=("x2s", "sum"), media=("O", "mean"),
                           var=("O", "var"), E=("E", "sum"))
    z = z[(z.n >= MIN_SECOES) & (z.E >= 50)]   # zonas com pelo menos 50 brancos (ou nulos) esperados
    z["gl"] = z.n - 1
    z["phi"] = z.X2 / z.gl
    z["phi_sim"] = z.X2s / z.gl
    z["p_acima"] = chi2.sf(z.X2, z.gl)                       # excesso de variação
    z["p_abaixo"] = chi2.cdf(z.X2, z.gl)                     # falta de variação
    z["vmr"] = z["var"] / z.media
    return z

def main():
    rng = np.random.default_rng(1)
    linhas, phis = [], {}
    for ano, t in CASOS:
        v = pd.read_csv(os.path.join(OUT, f"votacao_{ano}.csv.gz"), dtype={"cd": str}).query("NR_TURNO == @t")
        for col in ("Brancos", "Nulos"):
            z = por_zona(v, col, rng)
            phis[(ano, t, col)] = z
            linhas.append({"eleição": f"{ano} {t}º turno", "variável": col,
                           "papel": "teste" if (ano, t) == (2026, 2) else "calibração", "zonas": len(z),
                           "taxa_%": 100 * v[col].sum() / v.Comp.sum(),
                           "phi_mediana": z.phi.median(), "phi_p10": z.phi.quantile(.1), "phi_p90": z.phi.quantile(.9),
                           "phi_mediana_poisson_sim": z.phi_sim.median(),
                           "%zonas_excesso(p<0,05)": 100 * (z.p_acima < .05).mean(),
                           "%zonas_falta(p<0,05)": 100 * (z.p_abaixo < .05).mean(),
                           "%zonas_falta_poisson_sim": 100 * (chi2.cdf(z.X2s, z.gl) < .05).mean(),
                           "VMR_bruto_mediana": z.vmr.median(),
                           "X2_total/gl": z.X2.sum() / z.gl.sum()})
    r = pd.DataFrame(linhas)
    pd.set_option("display.width", 250)
    print(r.round(3).to_string(index=False))
    r.round(4).to_csv(os.path.join(OUT, "poisson_brancos_nulos.csv"), index=False, encoding="utf-8-sig")

    # mesmas zonas nos dois turnos de 2026: φ do 2º turno contra o do 1º (zonas que mudaram de comportamento)
    for col in ("Brancos", "Nulos"):
        a, b = phis[(2026, 1, col)].phi, phis[(2026, 2, col)].phi
        c = pd.concat([a, b], axis=1, keys=["t1", "t2"]).dropna()
        a22, b22 = phis[(2022, 1, col)].phi, phis[(2022, 2, col)].phi
        c22 = pd.concat([a22, b22], axis=1, keys=["t1", "t2"]).dropna()
        print(f"{col}: correlação φ 1º × 2º turno por zona — 2026: {br(np.corrcoef(np.log(c.t1), np.log(c.t2))[0, 1])}"
              f" | 2022: {br(np.corrcoef(np.log(c22.t1), np.log(c22.t2))[0, 1])}; "
              f"zonas de 2026 com φ < 1 no 2º turno: {int((c.t2 < 1).sum())} de {len(c)}")

    fig, axs = plt.subplots(1, 2, figsize=(15, 5.5), sharey=True)
    cores = {(2022, 1): "#9ca3af", (2022, 2): "#4b5563", (2026, 1): "#7fb3d5", (2026, 2): "#c0392b"}
    bins = np.logspace(np.log10(.3), np.log10(20), 70)
    for ax, col in zip(axs, ("Brancos", "Nulos")):
        for (ano, t), cor in cores.items():
            ax.hist(phis[(ano, t, col)].phi, bins=bins, histtype="step", lw=2 if (ano, t) == (2026, 2) else 1.3,
                    color=cor, label=f"{ano} {t}º turno" + (" (teste)" if (ano, t) == (2026, 2) else ""))
        ax.hist(phis[(2026, 2, col)].phi_sim, bins=bins, histtype="stepfilled", color="#e5e7eb", zorder=0,
                label="Poisson puro simulado (2026 2º turno)")
        ax.axvline(1, color="#1f2328", lw=.8, ls=":")
        ax.set_xscale("log"); ax.set_xlabel("φ por zona = X² / graus de liberdade (1 = Poisson)")
        ax.set_title(f"{col}: dispersão dentro de cada zona eleitoral", loc="left", weight="bold")
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
        ax.legend(frameon=False, fontsize=8.5)
    axs[0].set_ylabel("zonas")
    fig.text(.01, .01, f"Zonas com pelo menos {MIN_SECOES} seções. Esperado por seção = taxa da zona × comparecimento "
             "da seção. φ < 1 indicaria contagens regulares demais; φ > 1, heterogeneidade entre bairros.",
             fontsize=8.5, color="#6b7280")
    plt.tight_layout(rect=(0, .03, 1, 1))
    plt.savefig(os.path.join(OUT, "poisson_brancos_nulos.png"), dpi=115)

if __name__ == "__main__":
    main()
