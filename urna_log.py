"""Extrai indicadores dos logs de urna baixados por urna_baixa.py, por seção e dia de votação.

O log (.jez é um ZIP com logd.dat, texto separado por tabulação: data/hora, nível, id da urna, aplicação, mensagem,
hash) acumula a história da urna; o do 2º turno costuma conter também o 1º. Cada dia é lido do log do próprio turno
quando ele existe; senão, do outro log da mesma seção.

Indicadores por dia (aplicação VOTA):
  habilitados        "Eleitor foi habilitado"
  computados         "O voto do eleitor foi computado"
  biometricos        "Tipo de habilitação do eleitor [biométrica]"
  sem_biometria      habilitados − biometricos
  apos_17h           votos computados depois das 17:00:00
  rapidos_20s        votos computados menos de 20 s após a habilitação
  dur_mediana        mediana de segundos entre habilitação e voto computado
  seq_10s            votos computados menos de 10 s após o voto anterior
  pico_10min         maior número de votos computados numa janela de 10 minutos

Uso:  python -X utf8 -E -P urna_log.py     (lê dados_urna/amostra.csv, grava saida/urna_logs.csv.gz)
"""
import os, zipfile, glob
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
import numpy as np, pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, "dados_urna")
DIAS = {"04/10/2026": 1, "25/10/2026": 2}
PLEITO = {1: "3220", 2: "3221"}

def le_log(caminho):
    try:
        with zipfile.ZipFile(caminho) as z:
            nome = next(n for n in z.namelist() if n.endswith(".dat"))
            return z.read(nome).decode("latin-1").splitlines()
    except Exception:
        return None

def indicadores(linhas, dia):
    hab, comp, bio = [], [], 0
    for l in linhas:
        if not l.startswith(dia):
            continue
        p = l.split("\t")
        if len(p) < 5 or p[3] != "VOTA":
            continue
        m = p[4]
        if m == "Eleitor foi habilitado":
            hab.append(p[0])
        elif m == "O voto do eleitor foi computado":
            comp.append(p[0])
        elif m == "Tipo de habilitação do eleitor [biométrica]":
            bio += 1
    if not hab and not comp:
        return None
    th = np.array([datetime.strptime(t, "%d/%m/%Y %H:%M:%S").timestamp() for t in hab])
    tc = np.array([datetime.strptime(t, "%d/%m/%Y %H:%M:%S").timestamp() for t in comp])
    # cada voto computado é casado com a habilitação imediatamente anterior
    idx = np.searchsorted(th, tc, side="right") - 1
    dur = np.where(idx >= 0, tc - th[np.clip(idx, 0, None)], np.nan) if len(th) else np.full(len(tc), np.nan)
    gaps = np.diff(np.sort(tc))
    fim17 = datetime.strptime(dia + " 17:00:00", "%d/%m/%Y %H:%M:%S").timestamp()
    tcs = np.sort(tc)
    pico = int(max((np.searchsorted(tcs, t + 600, side="left") - i for i, t in enumerate(tcs)), default=0))
    return {"habilitados": len(hab), "computados": len(tc), "biometricos": bio, "sem_biometria": len(hab) - bio,
            "apos_17h": int((tc > fim17).sum()), "rapidos_20s": int((dur < 20).sum()),
            "dur_mediana": float(np.nanmedian(dur)) if len(dur) else np.nan,
            "seq_10s": int((gaps < 10).sum()), "pico_10min": pico,
            "primeiro": comp[0][11:] if comp else "", "ultimo": comp[-1][11:] if comp else ""}

def processa(chave):
    uf, mun, zona, secao = chave
    pastas = {t: os.path.join(DADOS, PLEITO[t], uf.lower(), f"{int(mun):05d}", f"{int(zona):04d}", f"{int(secao):04d}")
              for t in (1, 2)}
    logs = {t: (glob.glob(os.path.join(pastas[t], "*-log.jez")) or [None])[0] for t in (1, 2)}
    linhas = {t: le_log(logs[t]) if logs[t] else None for t in (1, 2)}
    saida = []
    for dia, t in DIAS.items():
        r, fonte = None, None
        for tt in (t, 3 - t):                 # primeiro o log do próprio turno
            if linhas[tt]:
                r = indicadores(linhas[tt], dia)
                if r:
                    fonte = tt; break
        saida.append({"uf": uf, "cd": str(mun), "NR_ZONA": zona, "NR_SECAO": secao, "turno": t,
                      "log_do_turno": fonte, **(r or {})})
    return saida

def main():
    a = pd.read_csv(os.path.join(DADOS, "amostra.csv"), dtype={"cd": str})
    chaves = list(a[["uf", "cd", "NR_ZONA", "NR_SECAO"]].itertuples(index=False, name=None))
    with ProcessPoolExecutor() as ex:
        res = [l for lista in ex.map(processa, chaves, chunksize=50) for l in lista]
    r = pd.DataFrame(res).merge(a, on=["uf", "cd", "NR_ZONA", "NR_SECAO"], how="left")
    r.to_csv(os.path.join(AQUI, "saida", "urna_logs.csv.gz"), index=False)
    print(f"seções × turnos: {len(r)} | sem log lido: {int(r.computados.isna().sum())} | "
          f"lidos do log do outro turno: {int((r.log_do_turno.notna() & (r.log_do_turno != r.turno)).sum())}")

if __name__ == "__main__":
    main()
