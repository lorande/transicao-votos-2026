"""Monta a amostra de seções cujos logs de urna serão baixados (dados_urna/amostra.csv).

3.000 seções sorteadas proporcionalmente por UF (semente fixa) + seções sinalizadas pelos testes de forense.py:
comparecimento >= 95% no 2º turno, resultado que não saiu direto da urna e salto extremo de comparecimento.
Requer saida/transicao_secoes.csv.gz, saida/forense_info_secoes.csv.gz e saida/forense_extremos.csv.

Uso:  python -X utf8 -E -P urna_amostra.py
"""
import os
import numpy as np, pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(AQUI, "saida")
K = ["uf", "cd", "NR_ZONA", "NR_SECAO"]

def main():
    s = pd.read_csv(os.path.join(S, "transicao_secoes.csv.gz"), dtype={"cd": str})
    s = s.merge(pd.read_csv(os.path.join(S, "forense_info_secoes.csv.gz"), dtype={"cd": str}), on=K, how="left")
    rng = np.random.default_rng(2026)
    n_uf = (s.uf.value_counts(normalize=True) * 3000).round().astype(int)
    alea = pd.concat([g.iloc[rng.choice(len(g), min(n_uf[u], len(g)), replace=False)] for u, g in s.groupby("uf")])
    comp2 = 100 * (1 - s["Abstenção_2"] / s.eleitores_2.clip(lower=1))
    grupos = [alea.assign(grupo="aleatoria"),
              s[(comp2 >= 95) & (s.eleitores_2 >= 50)].assign(grupo="comparecimento>=95"),
              s[s.DS_ORIGEM_VOTO_2.fillna("") != "Urna Eletrônica"].assign(grupo="resultado fora da urna"),
              pd.read_csv(os.path.join(S, "forense_extremos.csv"), dtype={"cd": str})[K].merge(s, on=K)
                .assign(grupo="salto extremo")]
    a = pd.concat(grupos)[K + ["grupo"]].groupby(K, as_index=False).grupo.agg(lambda g: "+".join(sorted(set(g))))
    os.makedirs(os.path.join(AQUI, "dados_urna"), exist_ok=True)
    a.to_csv(os.path.join(AQUI, "dados_urna", "amostra.csv"), index=False)
    a.to_csv(os.path.join(S, "urna_amostra.csv"), index=False)
    print(len(a), "seções |", a.grupo.value_counts().to_dict())

if __name__ == "__main__":
    main()
