"""Testes com os logs de urna da amostra (saida/urna_logs.csv.gz) contra a hipótese de fraude proporcional:
votos inseridos em nome de eleitores ausentes, a favor do Lula, no 2º turno.

Votos inseridos sem eleitor real precisam ser habilitados sem biometria (o eleitor não está lá para pôr o dedo) e
tendem a sair em sequência rápida. Então, sob a hipótese:
  A. as habilitações e os votos computados batem com o boletim (a fraude teria de passar pela urna);
  B. as habilitações sem biometria sobem do 1º para o 2º turno, e mais onde o Lula ganhou mais;
  C. aparecem votos rápidos, rajadas e votos fora de hora, também ligados ao ganho do Lula.
Calibração: injeta na amostra uma inserção de F% do eleitorado (votos no Lula, sem biometria, rápidos, tirados da
abstenção) e refaz os testes, para mostrar o que eles acusariam.

Uso:  python -X utf8 -E -P urna_analise.py [F]       (F em % do eleitorado; padrão 1)
"""
import os, sys
import numpy as np, pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(AQUI, "saida")
F = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0

def br(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def ols(y, X, grupos):
    X = np.column_stack([X, np.ones(len(y))])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ b
    Sg = pd.DataFrame(X * u[:, None]).groupby(grupos).sum().to_numpy()
    inv = np.linalg.inv(X.T @ X)
    return b, np.sqrt(np.diag(inv @ (Sg.T @ Sg) @ inv))

def main():
    lg = pd.read_csv(os.path.join(S, "urna_logs.csv.gz"), dtype={"cd": str})
    base = pd.read_csv(os.path.join(S, "transicao_secoes.csv.gz"), dtype={"cd": str})
    w = lg.pivot_table(index=["uf", "cd", "NR_ZONA", "NR_SECAO", "grupo"], columns="turno",
                       values=["habilitados", "computados", "biometricos", "sem_biometria", "apos_17h", "rapidos_20s",
                               "seq_10s", "pico_10min", "dur_mediana"], aggfunc="first")
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    d = w.reset_index().merge(base, on=["uf", "cd", "NR_ZONA", "NR_SECAO"], how="inner")
    for t in (1, 2):
        d[f"comp_bu_{t}"] = d[f"eleitores_{t}"] - d[f"Abstenção_{t}"]
    ok = d.dropna(subset=["computados_1", "computados_2"]).copy()
    print(f"seções com log nos dois turnos: {len(ok)} de {len(d)} ({ok.grupo.value_counts().to_dict()})")

    print("\nA. CONSISTÊNCIA (por seção e turno)")
    for t in (1, 2):
        e1 = (ok[f"habilitados_{t}"] != ok[f"computados_{t}"]).sum()
        e2 = (ok[f"computados_{t}"] != ok[f"comp_bu_{t}"]).sum()
        dif = (ok[f"computados_{t}"] - ok[f"comp_bu_{t}"])
        print(f"  {t}º turno: habilitados ≠ computados em {e1} seções; computados ≠ comparecimento do boletim em {e2}"
              f" (soma das diferenças {int(dif.sum())}, maior {int(dif.abs().max())})")
    ruins = ok[(ok.computados_2 != ok.comp_bu_2) | (ok.computados_1 != ok.comp_bu_1)]
    ruins[["uf", "cd", "NR_ZONA", "NR_SECAO", "grupo", "computados_1", "comp_bu_1", "computados_2", "comp_bu_2"]] \
        .to_csv(os.path.join(S, "urna_inconsistencias.csv"), index=False, encoding="utf-8-sig")

    al = ok[ok.grupo.str.contains("aleatoria")].copy()
    print(f"\nB. BIOMETRIA (amostra aleatória, {len(al)} seções)")
    for t in (1, 2):
        print(f"  {t}º turno: {br(100 * al[f'sem_biometria_{t}'].sum() / al[f'habilitados_{t}'].sum())}% dos eleitores "
              f"habilitados sem biometria; média {br(al[f'sem_biometria_{t}'].mean())} por seção")
    al["d_sem_bio"] = al.sem_biometria_2 - al.sem_biometria_1
    al["d_comp"] = al.comp_bu_2 - al.comp_bu_1
    al["ganho_L"] = al.Lula_2 - al.Lula_1
    al["x"] = (al.Lula_2 + al["Flávio_2"]) - (al.Lula_1 + al["Flávio_1"] + al.Outros_1)
    al["zona"] = al.uf + "-" + al.cd + "-" + al.NR_ZONA.astype(str)
    ep_d = al.d_sem_bio.std() / np.sqrt(len(al))
    print(f"  variação 1º → 2º turno nas habilitações sem biometria: {br(al.d_sem_bio.mean())} ± {br(ep_d)} por seção "
          f"(variação do comparecimento: {br(al.d_comp.mean())} por seção)")

    def testes(dd, rotulo):
        # ganho do Lula ~ x + Outros + Δ sem biometria (+ UF): coeficiente de Δ sem biometria
        uf = pd.get_dummies(dd.uf, drop_first=True, dtype=float).to_numpy()
        X = np.column_stack([dd.x, dd.Outros_1, dd.d_sem_bio, uf])
        b, ep = ols(dd.ganho_L.to_numpy(float), X, dd.zona.to_numpy())
        X2 = np.column_stack([dd.x, dd.Outros_1, dd.rapidos_20s_2 - dd.rapidos_20s_1, uf])
        b2, ep2 = ols(dd.ganho_L.to_numpy(float), X2, dd.zona.to_numpy())
        print(f"  [{rotulo}] Δ sem biometria médio {br(dd.d_sem_bio.mean())}; votos extras do Lula por habilitação extra "
              f"sem biometria: {br(b[2], 3)} ± {br(ep[2], 3)}; por voto rápido extra (<20 s): {br(b2[2], 3)} ± {br(ep2[2], 3)}")
        return b[2], ep[2]
    real = testes(al, "dados reais")
    # calibração: injeta F% do eleitorado como votos no Lula, habilitados sem biometria e rápidos, tirados da abstenção
    sim = al.copy()
    k = np.minimum(np.round(F / 100 * sim.eleitores_2), sim["Abstenção_2"])
    sim["Lula_2"] += k; sim["Abstenção_2"] -= k; sim["sem_biometria_2"] += k; sim["rapidos_20s_2"] += k
    sim["d_sem_bio"] = sim.sem_biometria_2 - sim.sem_biometria_1
    sim["ganho_L"] = sim.Lula_2 - sim.Lula_1
    sim["x"] = (sim.Lula_2 + sim["Flávio_2"]) - (sim.Lula_1 + sim["Flávio_1"] + sim.Outros_1)
    testes(sim, f"com {F:g}% do eleitorado inserido")
    print(f"  com {F:g}% inserido, a variação média das habilitações sem biometria seria {br(sim.d_sem_bio.mean())} "
          f"(real {br(al.d_sem_bio.mean())} ± {br(ep_d)}): a inserção máxima compatível com os dados (95%) é "
          f"{br(max(0, al.d_sem_bio.mean() + 1.645 * ep_d) / al.eleitores_2.mean() * 100, 2)}% do eleitorado")

    print("\nC. HORÁRIOS E RITMO (amostra aleatória; médias por seção)")
    tab = pd.DataFrame({t: {"votos após 17h": al[f"apos_17h_{t}"].mean(), "votos < 20 s após habilitação": al[f"rapidos_20s_{t}"].mean(),
                            "votos < 10 s após o anterior": al[f"seq_10s_{t}"].mean(), "pico de votos em 10 min": al[f"pico_10min_{t}"].mean(),
                            "duração mediana (s)": al[f"dur_mediana_{t}"].median()} for t in (1, 2)})
    tab.columns = ["1º turno", "2º turno"]
    print(tab.round(2).to_string())

    print("\nD. SEÇÕES SINALIZADAS × AMOSTRA ALEATÓRIA (2º turno)")
    ok["pct_sem_bio_2"] = 100 * ok.sem_biometria_2 / ok.habilitados_2
    ok["pct_sem_bio_1"] = 100 * ok.sem_biometria_1 / ok.habilitados_1
    ok["pct_rapidos_2"] = 100 * ok.rapidos_20s_2 / ok.computados_2
    ok["g"] = ok.grupo.str.replace("aleatoria+", "", regex=False)
    print(ok.groupby("g")[["pct_sem_bio_1", "pct_sem_bio_2", "pct_rapidos_2", "apos_17h_2", "pico_10min_2"]]
          .mean().round(2).to_string())
    ok.to_csv(os.path.join(S, "urna_analise_secoes.csv.gz"), index=False)
    tab.to_csv(os.path.join(S, "urna_ritmo.csv"), encoding="utf-8-sig")
    ok.groupby("g")[["pct_sem_bio_1", "pct_sem_bio_2", "apos_17h_2", "pico_10min_2"]].mean().round(3) \
        .to_csv(os.path.join(S, "urna_grupos.csv"), encoding="utf-8-sig")
    resumo = {"secoes_com_log": len(ok), "secoes_aleatorias": len(al),
              "log_dif_boletim_t1": int((ok.computados_1 != ok.comp_bu_1).sum()),
              "log_dif_boletim_t2": int((ok.computados_2 != ok.comp_bu_2).sum()),
              "pct_sem_bio_t1": 100 * al.sem_biometria_1.sum() / al.habilitados_1.sum(),
              "pct_sem_bio_t2": 100 * al.sem_biometria_2.sum() / al.habilitados_2.sum(),
              "d_sem_bio_media": al.d_sem_bio.mean(), "d_sem_bio_ep": ep_d, "d_comp_media": al.d_comp.mean(),
              "d_sem_bio_com_insercao": sim.d_sem_bio.mean(), "insercao_simulada_pct": F,
              "insercao_maxima_pct": max(0, al.d_sem_bio.mean() + 1.645 * ep_d) / al.eleitores_2.mean() * 100,
              "seq_10s_t2_media": al.seq_10s_2.mean()}
    pd.Series(resumo).to_csv(os.path.join(S, "urna_resumo.csv"), header=["valor"], encoding="utf-8-sig")

if __name__ == "__main__":
    main()
