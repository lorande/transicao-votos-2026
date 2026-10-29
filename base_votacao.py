"""Base por seção e turno, a partir do arquivo de votação por seção do TSE (mesma montagem para qualquer ano).

Colunas por seção e turno: Lula (13), Adv (22: Bolsonaro em 2022, Flávio em 2026), Outros, Brancos (95), Nulos (96),
Comp (soma de todos os votos para presidente = comparecimento). Também a chave de município e zona.

Uso:  python -X utf8 -E -P base_votacao.py ANO        (lê dados_secao/votacao_secao_<ANO>_BR.zip — baixado do TSE
                                                       se não existir, ~270 MB em 2022 e ~240 MB em 2026 —
                                                       e grava saida/votacao_<ANO>.csv.gz)
"""
import os, sys, zipfile, shutil, urllib.request
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
ANO = sys.argv[1]
CHAVE = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"]
GRUPO = {13: "Lula", 22: "Adv", 95: "Brancos", 96: "Nulos"}

def baixa():
    destino = os.path.join(AQUI, "dados_secao", f"votacao_secao_{ANO}_BR.zip")
    if not os.path.exists(destino):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        url = f"https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_{ANO}_BR.zip"
        print("baixando", url)
        with urllib.request.urlopen(url, timeout=120) as r, open(destino + ".parcial", "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(destino + ".parcial", destino)
    return destino

def main():
    z = zipfile.ZipFile(baixa())
    nome = next(n for n in z.namelist() if n.endswith(".csv"))
    partes = []
    for ch in pd.read_csv(z.open(nome), sep=";", encoding="latin-1", chunksize=2_000_000,
                          usecols=CHAVE + ["DS_CARGO", "NR_VOTAVEL", "QT_VOTOS"]):
        ch = ch[ch.DS_CARGO.str.strip().str.upper() == "PRESIDENTE"]
        ch = ch.assign(g=ch.NR_VOTAVEL.astype(int).map(GRUPO).fillna("Outros"), v=ch.QT_VOTOS.astype(int))
        partes.append(ch.groupby(CHAVE + ["g"]).v.sum())
    v = pd.concat(partes).groupby(level=list(range(len(CHAVE) + 1))).sum().unstack("g", fill_value=0)
    v["Comp"] = v.sum(axis=1)
    v = v.reset_index().rename(columns={"SG_UF": "uf", "CD_MUNICIPIO": "cd"})
    v.to_csv(os.path.join(AQUI, "saida", f"votacao_{ANO}.csv.gz"), index=False)
    print(ANO, "| seções por turno:", v.groupby("NR_TURNO").size().to_dict())
    print(v.groupby("NR_TURNO")[["Lula", "Adv", "Outros", "Brancos", "Nulos", "Comp"]].sum().to_string())

if __name__ == "__main__":
    main()
