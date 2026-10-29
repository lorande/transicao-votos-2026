"""Confere os boletins de urna (BU) da amostra com os dados publicados por seção.

O BU é o arquivo assinado que a urna grava ao fim da votação (formato ASN.1/DER do TSE). Para cada seção da amostra
(dados_urna/, baixada por urna_baixa.py), lê os votos para presidente no BU — Lula (13), adversário (22), outros
candidatos, brancos e nulos — e compara com saida/votacao_2026.csv.gz (base_votacao.py 2026), que vem do arquivo
de votação por seção dos dados abertos.

Se os totais tivessem sido redistribuídos depois da urna (na transmissão ou na totalização), o BU e o dado
publicado divergiriam. Uma troca feita dentro do software da própria urna não aparece aqui: o BU já sairia trocado.

Uso:  python -X utf8 -E -P urna_bu.py      grava saida/urna_bu_comparacao.csv e saida/urna_bu_resumo.csv
"""
import os, glob
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(AQUI, "saida")
TURNO = {"3220": 1, "3221": 2}

def tlv(b, i):
    """Lê um cabeçalho DER: devolve (byte de tag, número da tag, início do valor, tamanho)."""
    t = b[i]; i += 1
    tn = t & 0x1f
    if tn == 0x1f:
        tn = 0
        while True:
            x = b[i]; i += 1; tn = tn * 128 + (x & 0x7f)
            if not x & 0x80:
                break
    n = b[i]; i += 1
    if n & 0x80:
        k = n & 0x7f; n = int.from_bytes(b[i:i + k], "big"); i += k
    return t, tn, i, n

def arvore(b, i=0, fim=None):
    """Lista de nós (tag, número, valor-bytes ou filhos) de um trecho DER."""
    fim = len(b) if fim is None else fim
    nos = []
    while i < fim:
        t, tn, s, n = tlv(b, i)
        nos.append((t, tn, arvore(b, s, s + n) if t & 0x20 else b[s:s + n]))
        i = s + n
    return nos

inteiro = lambda v: int.from_bytes(v, "big", signed=True)

def votos_presidente(caminho):
    """Votos para presidente no BU: {Lula, Adv, Outros, Brancos, Nulos} (None se não houver o cargo)."""
    env = arvore(open(caminho, "rb").read())[0][2]
    conteudo = [v for t, tn, v in env if t == 0x04][-1]          # envelope -> BU (OCTET STRING)
    achou = []
    def busca(nos):
        for t, tn, v in nos:
            if not t & 0x20:
                continue
            # totaisVotosCargo: codigoCargo [1] cargoConstitucional, ordemImpressao, votosVotaveis
            if len(v) >= 3 and v[0][:2] == (0x81, 1) and v[1][0] == 0x02 and v[2][0] == 0x30:
                if inteiro(v[0][2]) == 1:                       # 1 = presidente
                    achou.append(v[2][2])
                continue
            busca(v)
    busca(arvore(conteudo))
    if not achou:
        return None
    r = dict(Lula=0, Adv=0, Outros=0, Brancos=0, Nulos=0)
    for _, _, vv in achou[0]:
        campos = {tn: v for t, tn, v in vv if t & 0xc0 == 0x80}  # [1] tipoVoto, [2] quantidade, [3] votável
        tipo, qtd = inteiro(campos[1]), inteiro(campos[2])
        if tipo == 1:
            cod = inteiro(campos[3][1][2])                       # identificacaoVotavel: partido, codigo
            r["Lula" if cod == 13 else "Adv" if cod == 22 else "Outros"] += qtd
        elif tipo == 2:
            r["Brancos"] += qtd
        elif tipo == 3:
            r["Nulos"] += qtd
        else:
            r["Outros"] += qtd
    return r

def main():
    linhas = []
    for f in glob.glob(os.path.join(AQUI, "dados_urna", "32*", "*", "*", "*", "*", "*-bu.dat")):
        p, uf, mun, zona, secao = os.path.normpath(f).split(os.sep)[-6:-1]
        try:
            v = votos_presidente(f)
        except Exception as e:
            v, erro = None, str(e)
        else:
            erro = "" if v else "sem cargo presidente"
        linhas.append(dict(NR_TURNO=TURNO[p], uf=uf.upper(), cd=int(mun), NR_ZONA=int(zona), NR_SECAO=int(secao),
                           erro=erro, **{f"bu_{k}": x for k, x in (v or {}).items()}))
    bu = pd.DataFrame(linhas)
    pub = pd.read_csv(os.path.join(S, "votacao_2026.csv.gz"))
    k = ["NR_TURNO", "uf", "cd", "NR_ZONA", "NR_SECAO"]
    m = bu.merge(pub, on=k, how="left", indicator=True)
    G = ["Lula", "Adv", "Outros", "Brancos", "Nulos"]
    for g in G:
        m[f"dif_{g}"] = m[f"bu_{g}"] - m[g]
    m["bate"] = (m[[f"dif_{g}" for g in G]].fillna(1).abs().sum(axis=1) == 0) & (m._merge == "both")
    m.to_csv(os.path.join(S, "urna_bu_comparacao.csv"), index=False)
    res = m.groupby("NR_TURNO").agg(boletins=("bate", "size"), lidos=("erro", lambda e: (e == "").sum()),
                                     sem_par_publicado=("_merge", lambda x: (x != "both").sum()),
                                     batem=("bate", "sum"),
                                     votos_bu=("bu_Lula", lambda _: 0)).reset_index()
    for t in (1, 2):
        x = m[(m.NR_TURNO == t) & (m.erro == "")]
        res.loc[res.NR_TURNO == t, "votos_bu"] = int(x[[f"bu_{g}" for g in G]].sum().sum())
        res.loc[res.NR_TURNO == t, "dif_abs_total"] = int(x[[f"dif_{g}" for g in G]].abs().sum().sum())
    res.to_csv(os.path.join(S, "urna_bu_resumo.csv"), index=False)
    print(res.to_string(index=False))
    print("\nerros de leitura:", m[m.erro != ""].erro.value_counts().to_dict())
    nb = m[~m.bate & (m.erro == "")]
    print("divergências:", len(nb))
    if len(nb):
        print(nb[k + [f"dif_{g}" for g in G] + ["_merge"]].head(30).to_string(index=False))
    for t in (1, 2):
        x = m[(m.NR_TURNO == t) & (m.erro == "")]
        print(f"{t}T soma BU:", x[[f"bu_{g}" for g in G]].sum().to_dict(), "| publicado:", x[G].sum().to_dict())

if __name__ == "__main__":
    main()
