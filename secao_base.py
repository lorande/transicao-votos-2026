"""Monta a base por seção eleitoral (Presidente 2026, 1º e 2º turno) a partir dos dados abertos do TSE.

Entradas (em dados_secao/, baixadas do TSE se não existirem, ~476 MB):
  votacao_secao_2026_BR.zip          votos por candidato em cada seção
  detalhe_votacao_secao_2026.zip     aptos, abstenção, brancos e nulos em cada seção

Saída: saida/transicao_secoes.csv.gz, uma linha por seção presente nos dois turnos, com as colunas
Lula_1, Flávio_1, Outros_1, Brancos_1, Nulos_1, Abstenção_1, eleitores_1 e o mesmo para o 2º turno
(sem Outros), no formato que transicao_uf.py usa.

Uso:  python -X utf8 -E -P secao_base.py
"""
import os, zipfile, shutil, urllib.request
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, "dados_secao")
OUT = os.path.join(AQUI, "saida")
CHAVE = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
LULA, FLAVIO, BRANCO, NULO = 13, 22, 95, 96
REG = {"N": "AC AP AM PA RO RR TO", "NE": "AL BA CE MA PB PE PI RN SE", "CO": "DF GO MT MS",
       "SE": "ES MG RJ SP", "S": "PR RS SC", "Exterior": "ZZ"}
REG_DE = {u: r for r, us in REG.items() for u in us.split()}

FONTES = {
    "votacao_secao_2026_BR.zip": "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip",
    "detalhe_votacao_secao_2026.zip":
        "https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip",
}

def baixa_dados():
    os.makedirs(DADOS, exist_ok=True)
    for nome, url in FONTES.items():
        destino = os.path.join(DADOS, nome)
        if os.path.exists(destino):
            continue
        print("baixando", url)
        with urllib.request.urlopen(url, timeout=120) as r, open(destino + ".parcial", "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(destino + ".parcial", destino)

def votos():
    z = zipfile.ZipFile(os.path.join(DADOS, "votacao_secao_2026_BR.zip"))
    partes = []
    cols = ["NR_TURNO", "DS_CARGO"] + CHAVE + ["NR_VOTAVEL", "QT_VOTOS"]
    for ch in pd.read_csv(z.open("votacao_secao_2026_BR.csv"), sep=";", encoding="latin-1", usecols=cols,
                          chunksize=2_000_000):
        ch = ch[ch.DS_CARGO.str.strip().str.upper() == "PRESIDENTE"]
        n = ch.NR_VOTAVEL
        ch = ch.assign(grupo=n.map({LULA: "Lula", FLAVIO: "Flávio", BRANCO: "_branco", NULO: "_nulo"}).fillna("Outros"))
        partes.append(ch.groupby(["NR_TURNO"] + CHAVE + ["grupo"]).QT_VOTOS.sum())
    v = pd.concat(partes).groupby(level=list(range(len(CHAVE) + 2))).sum().unstack("grupo", fill_value=0)
    return v

def detalhe():
    z = zipfile.ZipFile(os.path.join(DADOS, "detalhe_votacao_secao_2026.zip"))
    cols = ["NR_TURNO", "DS_CARGO"] + CHAVE + ["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "QT_VOTOS_NOMINAIS",
            "QT_VOTOS_BRANCOS", "QT_VOTOS_NULOS", "QT_VOTOS_ANULADOS_APU_SEP", "ST_SECAO_ANULADA"]
    d = pd.read_csv(z.open("detalhe_votacao_secao_2026_BR.csv"), sep=";", encoding="latin-1", usecols=cols)
    d = d[d.DS_CARGO.str.strip().str.upper() == "PRESIDENTE"].drop(columns="DS_CARGO")
    return d.set_index(["NR_TURNO"] + CHAVE)

def main():
    baixa_dados()
    v = votos()
    d = detalhe()
    print("seções por turno (votos):", v.groupby(level="NR_TURNO").size().to_dict())
    print("seções por turno (detalhe):", d.groupby(level="NR_TURNO").size().to_dict())
    print("seções anuladas por turno:", d[d.ST_SECAO_ANULADA.str.strip() != "Não"].groupby(level="NR_TURNO").size().to_dict())
    j = d.join(v, how="left").fillna(0)
    sem_voto = (j[["Lula", "Flávio"]].sum(axis=1) == 0) & (j.QT_COMPARECIMENTO > 0)
    print("seções com comparecimento e sem voto no arquivo de votos:", int(sem_voto.sum()))

    # nulos = votos nulos + votos anulados em apuração separada (o TSE soma os dois no total de nulos)
    j["Nulos"] = j.QT_VOTOS_NULOS + j.QT_VOTOS_ANULADOS_APU_SEP
    j["Brancos"] = j.QT_VOTOS_BRANCOS
    j["Abstenção"] = j.QT_ABSTENCOES
    j["eleitores"] = j.QT_APTOS
    nom = j[["Lula", "Flávio", "Outros"]].sum(axis=1)
    print("diferença votos nominais (detalhe - soma dos candidatos), total por turno:",
          (j.QT_VOTOS_NOMINAIS - nom).groupby(level="NR_TURNO").sum().to_dict())
    fecha = (nom + j.Brancos + j.Nulos + j.Abstenção - j.eleitores)
    print("seções em que os grupos não somam os aptos, por turno:", (fecha != 0).groupby(level="NR_TURNO").sum().to_dict(),
          "| maior diferença:", int(fecha.abs().max()))

    G = {1: ["Lula", "Flávio", "Outros", "Brancos", "Nulos", "Abstenção", "eleitores"],
         2: ["Lula", "Flávio", "Brancos", "Nulos", "Abstenção", "eleitores"]}
    t = {k: j.xs(k, level="NR_TURNO")[G[k]].add_suffix(f"_{k}") for k in (1, 2)}
    so1 = t[1].index.difference(t[2].index); so2 = t[2].index.difference(t[1].index)
    print(f"seções só no 1º turno: {len(so1)} ({int(t[1].loc[so1, 'eleitores_1'].sum())} eleitores) | "
          f"só no 2º turno: {len(so2)} ({int(t[2].loc[so2, 'eleitores_2'].sum())} eleitores)")
    b = t[1].join(t[2], how="inner").reset_index()
    b = b.rename(columns={"SG_UF": "uf", "CD_MUNICIPIO": "cd"})
    b["regiao"] = b.uf.map(REG_DE)
    print("seções nos dois turnos:", len(b), "| sem região:", int(b.regiao.isna().sum()))
    for k, g in G.items():
        print(f"totais {k}º turno:", {c: int(b[f"{c}_{k}"].sum()) for c in g})
    os.makedirs(OUT, exist_ok=True)
    b.to_csv(os.path.join(OUT, "transicao_secoes.csv.gz"), index=False, encoding="utf-8")

if __name__ == "__main__":
    main()
