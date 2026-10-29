"""Baixa log e boletim de urna (BU) de seções eleitorais, nos dois turnos, do site de resultados do TSE.

Estrutura no site:
  .../ele2026/arquivo-urna/<pleito>/dados/<uf>/<municipio>/<zona>/<secao>/p00<pleito>-<uf>-m<mun>-z<zona>-s<secao>-aux.json
     -> lista de hashes; os arquivos ficam em .../<secao>/<hash>/<nome>
  pleito 3220 = 1º turno (eleição 6257), 3221 = 2º turno (eleição 6258)

Uso:  python -X utf8 -E -P urna_baixa.py amostra.csv [tipos]     tipos padrão: log,bu
      amostra.csv com colunas uf, cd, NR_ZONA, NR_SECAO
Arquivos em dados_urna/<pleito>/<uf>/<mun>/<zona>/<secao>/; o que já existe não é baixado de novo.
"""
import os, sys, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(AQUI, "dados_urna")
BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna"
PLEITOS = ("3220", "3221")

def get(url, tentativas=4):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:
            if getattr(e, "code", None) == 404 or i == tentativas - 1:
                raise
            time.sleep(2 * (i + 1))

def baixa_secao(uf, mun, zona, secao, tipos):
    uf, mun, zona, secao = uf.lower(), f"{int(mun):05d}", f"{int(zona):04d}", f"{int(secao):04d}"
    status = {}
    for p in PLEITOS:
        pasta = os.path.join(DEST, p, uf, mun, zona, secao)
        os.makedirs(pasta, exist_ok=True)
        cam = f"{BASE}/{p}/dados/{uf}/{mun}/{zona}/{secao}"
        aux_path = os.path.join(pasta, "aux.json")
        try:
            if not os.path.exists(aux_path):
                aux = get(f"{cam}/p00{p}-{uf}-m{mun}-z{zona}-s{secao}-aux.json")
                json.loads(aux)
                open(aux_path, "wb").write(aux)
            aux = json.load(open(aux_path, encoding="utf-8"))
            # usa o último hash totalizado (o que entrou no resultado)
            hs = [h for h in aux.get("hashes", []) if h.get("st", "").lower().startswith("totaliz")] or aux.get("hashes", [])
            if not hs:
                status[p] = "sem arquivos"; continue
            h = hs[-1]
            for a in h["arq"]:
                if a["tp"] not in tipos:
                    continue
                destino = os.path.join(pasta, a["nm"])
                if not os.path.exists(destino):
                    dados = get(f"{cam}/{h['hash']}/{a['nm']}")
                    open(destino + ".parcial", "wb").write(dados)
                    os.replace(destino + ".parcial", destino)
            status[p] = "ok"
        except Exception as e:
            status[p] = f"erro: {e}"
    return status

def main():
    amostra = pd.read_csv(sys.argv[1], dtype={"cd": str})
    tipos = set((sys.argv[2] if len(sys.argv) > 2 else "log,bu").split(","))
    linhas = list(amostra[["uf", "cd", "NR_ZONA", "NR_SECAO"]].itertuples(index=False))
    erros, feitos = [], 0
    with ThreadPoolExecutor(6) as ex:
        for (uf, mun, zona, secao), st in zip(linhas, ex.map(lambda r: baixa_secao(*r, tipos), linhas)):
            feitos += 1
            for p, v in st.items():
                if v != "ok":
                    erros.append((uf, mun, zona, secao, p, v))
            if feitos % 250 == 0:
                print(f"{feitos}/{len(linhas)} seções, {len(erros)} problemas", flush=True)
    print(f"concluído: {feitos} seções, {len(erros)} problemas")
    if erros:
        pd.DataFrame(erros, columns=["uf", "cd", "zona", "secao", "pleito", "status"]) \
            .to_csv(os.path.join(DEST, "erros_download.csv"), index=False)

if __name__ == "__main__":
    main()
