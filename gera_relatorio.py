"""Gera o README.md (relatório) a partir dos arquivos em saida/. Nenhum número é digitado à mão.

Uso:  python -X utf8 -E -P gera_relatorio.py
"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AQUI = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(AQUI, "saida")
G1 = ["Lula", "Flávio", "Outros", "Brancos", "Nulos", "Abstenção"]
G2 = ["Lula", "Flávio", "Brancos", "Nulos", "Abstenção"]
DESTS = ["Lula", "Flávio", "Branco/Nulo/Abstenção"]
ORIGENS = ["Outros", "Brancos", "Nulos", "Abstenção"]
ARQ = {"Outros": "outros", "Brancos": "brancos", "Nulos": "nulos", "Abstenção": "abstencao"}
REGIOES = [("NE", "Nordeste"), ("N", "Norte"), ("CO", "Centro-Oeste"), ("SE", "Sudeste"), ("S", "Sul")]
UFS_REG = {"N": "AC AP AM PA RO RR TO".split(), "NE": "AL BA CE MA PB PE PI RN SE".split(),
           "CO": "DF GO MT MS".split(), "SE": "ES MG RJ SP".split(), "S": "PR RS SC".split()}
POUCOS = ["RR", "AP", "AC"]   # estados com pouca informação, comentados à parte

def br(x, nd=1):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def mi(v):
    if abs(v) < 500:
        return "≈0"
    return f"{br(v / 1e6, 2)} mi" if abs(v) >= 1e5 else f"{br(v / 1e3, 0)} mil"

def le(nome, **kw):
    return pd.read_csv(os.path.join(S, nome), **kw)

sec = le("transicao_secoes.csv.gz", dtype={"cd": str})
mun = le("transicao_municipios.csv", dtype={"cd": str})
t1 = {g: sec[f"{g}_1"].sum() for g in G1}; t2 = {g: sec[f"{g}_2"].sum() for g in G2}
M = {nivel: {"brasil": le(f"{p}_brasil.csv"), "fluxos": le(f"{p}_fluxos_brasil.csv", index_col=0),
             "matrizes": le(f"{p}_matrizes.csv"), "origens": le(f"{p}_origens.csv"),
             "sens": le(f"{p}_sensibilidade.csv", index_col=0), "r2": le(f"{p}_r2.csv", index_col=0)}
     for nivel, p in (("secao", "transicao_secao"), ("municipio", "transicao_uf"))}
fr = le("transicao_fluxos.csv", index_col=0)   # modelo por região (sobre municípios)

def cel(nivel, a, b):
    return M[nivel]["brasil"].set_index(["de", "para"]).loc[(a, b)]

def pct_reg(a, b):
    return 100 * fr.loc[a, b] / fr.loc[a].sum()

def grupo(nivel, a, dest):
    return M[nivel]["origens"].query("uf == 'BRASIL' and de == @a and para == @dest").iloc[0]

def ganho(f):
    g = {k: f.loc[k, "Lula"] for k in G1 if k != "Lula"}
    perdas = f.loc["Lula"].sum() - f.loc["Lula", "Lula"]
    return g, perdas, f["Lula"].sum() - f.loc["Lula"].sum()

def tabela_matriz(nivel):
    b, flux = M[nivel]["brasil"].set_index(["de", "para"]), M[nivel]["fluxos"]
    linhas = ["| 1º turno ↓ / 2º turno → | " + " | ".join(G2) + " |", "|---|" + "---|" * len(G2)]
    for a in G1:
        c = [f"{br(b.loc[(a, x), 'pct'])}% [{br(b.loc[(a, x), 'pct_p5'])}–{br(b.loc[(a, x), 'pct_p95'])}]"
             f"<br>{mi(flux.loc[a, x])}" for x in G2]
        linhas.append(f"| **{a}** ({mi(flux.loc[a].sum())}) | " + " | ".join(c) + " |")
    return "\n".join(linhas)

def tabela_origem(nivel, origem):
    t = M[nivel]["origens"].query("de == @origem")
    piv, lo, hi = (t.pivot(index="uf", columns="para", values=v)[DESTS] for v in ("pct", "pct_p5", "pct_p95"))
    linhas = ["| Região | UF | " + " | ".join(f"→ {d}" for d in DESTS) + " |", "|---|---|" + "---:|" * len(DESTS)]
    anterior = None
    for nr, u in [(nr, u) for r, nr in REGIOES for u in sorted(UFS_REG[r])] + [("Exterior", "ZZ")]:
        reg = f"**{nr}**" if nr != anterior else ""
        anterior = nr
        nome = ("Exterior" if u == "ZZ" else u) + (" ⚠" if u in POUCOS else "")
        linhas.append(f"| {reg} | {nome} | " + " | ".join(
            f"{br(piv.loc[u, d], 0)}% [{br(lo.loc[u, d], 0)}–{br(hi.loc[u, d], 0)}]" for d in DESTS) + " |")
    b = t[t.uf == "BRASIL"].set_index("para")
    linhas.append("| **BRASIL** | | " + " | ".join(
        f"**{br(b.loc[d, 'pct'])}%** [{br(b.loc[d, 'pct_p5'])}–{br(b.loc[d, 'pct_p95'])}] · {mi(b.loc[d, 'eleitores'])}"
        for d in DESTS) + " |")
    return "\n".join(linhas)

def secao_origem(origem):
    total = M["secao"]["origens"].query("uf == 'BRASIL' and de == @origem").eleitores.sum()
    return (f"### {origem} ({mi(total)} no 1º turno)\n\n{tabela_origem('secao', origem)}\n\n"
            f"![{origem}, por estado](saida/transicao_secao_origem_{ARQ[origem]}.png)\n")

def estados_pequenos():
    """informação disponível em RR, AP, AC comparada a um estado médio, e a matriz desses estados"""
    sec["cl"] = sec.uf + "-" + sec.cd + "-" + sec.NR_ZONA.astype(str)
    mat = M["secao"]["matrizes"].set_index(["uf", "de", "para"])
    linhas = ["| UF | Seções | Zonas | Grupos zona × município | Maior grupo (% do eleitorado) | Votos em Outros | Brancos |"
              " Outros → Lula | Outros → Flávio |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for u in POUCOS + ["SE", "DF"]:
        g = sec[sec.uf == u]
        z = g.groupby("cl").eleitores_1.sum()
        ol, of = mat.loc[(u, "Outros", "Lula")], mat.loc[(u, "Outros", "Flávio")]
        linhas.append(f"| {u}{' ⚠' if u in POUCOS else ''} | {br(len(g), 0)} | {g.NR_ZONA.nunique()} | {len(z)} | "
                      f"{br(100 * z.max() / z.sum(), 0)}% | {br(g.Outros_1.sum(), 0)} | {br(g.Brancos_1.sum(), 0)} | "
                      f"{br(ol.pct, 0)}% [{br(ol.pct_p5, 0)}–{br(ol.pct_p95, 0)}] | "
                      f"{br(of.pct, 0)}% [{br(of.pct_p5, 0)}–{br(of.pct_p95, 0)}] |")
    tab = "\n".join(linhas)
    rr = []
    for a in ["Outros", "Brancos", "Nulos", "Abstenção"]:
        rr.append(f"| {a} | " + " | ".join(f"{br(mat.loc[('RR', a, b)].pct, 0)}%" for b in G2) + " |")
    rr = "| RR, 1º turno → | " + " | ".join(G2) + " |\n|---|" + "---:|" * len(G2) + "\n" + "\n".join(rr)
    peso = 100 * sec[sec.uf.isin(POUCOS)].Outros_1.sum() / sec.Outros_1.sum()
    return tab, rr, peso

gs, ps, ls = ganho(M["secao"]["fluxos"]); gm, pm, lm = ganho(M["municipio"]["fluxos"]); grg, prg, lrg = ganho(fr)

def virada(f):
    """decompõe a mudança da diferença Lula − Flávio entre os turnos (fluxos estimados)"""
    nao_cand = ["Abstenção", "Brancos", "Nulos"]
    mob = f.loc[nao_cand, "Lula"].sum() - f.loc[nao_cand, "Flávio"].sum()
    outros = f.loc["Outros", "Lula"] - f.loc["Outros", "Flávio"]
    total = (f["Lula"].sum() - f["Flávio"].sum()) - (f.loc["Lula"].sum() - f.loc["Flávio"].sum())
    return {"mob": mob, "mob_L": f.loc[nao_cand, "Lula"].sum(), "mob_F": f.loc[nao_cand, "Flávio"].sum(),
            "outros": outros, "resto": total - mob - outros, "total": total,
            "sem_mob": (f["Lula"].sum() - f["Flávio"].sum()) - mob}
vs, vm = virada(M["secao"]["fluxos"]), virada(M["municipio"]["fluxos"])
margem1 = t1["Flávio"] - t1["Lula"]; margem2 = t2["Lula"] - t2["Flávio"]
nv = {m: le(f"novos_votantes_{m}.csv").set_index("candidato") for m in ("bruto", "sem_outros")}
tf = le("teste_teto_flavio_faixas.csv"); ti = le("teste_teto_flavio_integrais.csv").set_index("candidato")
ta = le("teste_teto_flavio.csv"); tx = le("teste_teto_flavio_interacao.csv").iloc[0]

def reta(m, c):
    r = nv[m].loc[c]
    return f"y = {br(r.a, 3)}·x {'+' if r.b >= 0 else '−'} {br(abs(r.b), 2)}"

def tab_faixas():
    linhas = ["| Força do Flávio no 1º turno | Seções | Eleitores novos (média) | Seções com x ≥ 20 | Inclinação Flávio |"
              " Inclinação Lula | Votos Flávio | Votos Lula |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in tf.iterrows():
        linhas.append(f"| {br(r.forca_min, 0)}–{br(r.forca_max, 0)}% | {br(r.secoes, 0)} | {br(r.x_medio)} | "
                      f"{br(r.pct_x_20_ou_mais, 0)}% | {br(r['inclinacao_Flávio'], 2)} | {br(r.inclinacao_Lula, 2)} | "
                      f"{mi(r['votos_Flávio']) if abs(r['votos_Flávio']) >= 500 else '≈0'} | {mi(r.votos_Lula)} |")
    linhas.append(f"| **Total** | {br(tf.secoes.sum(), 0)} | | | | | **{mi(tf['votos_Flávio'].sum())}** | "
                  f"**{mi(tf.votos_Lula.sum())}** |")
    return "\n".join(linhas)

_aq = ta[(ta.candidato == "Flávio") & ta.curva.str.startswith("quintil")].iloc[:, 2]

def achat(c, curva):
    return br(ta[(ta.candidato == c) & (ta.curva == curva)].iloc[0, 2], 2)
tab_poucos, tab_rr, peso_poucos = estados_pequenos()
o_bna = grupo("secao", "Outros", "Branco/Nulo/Abstenção")
_o = M["secao"]["matrizes"].query("de == 'Outros' and uf != 'ZZ'").pivot(index="uf", columns="para", values="pct")
_mf = sorted(_o.index[_o["Flávio"] > _o["Lula"]])
mais_flavio = ", ".join(_mf[:-1]) + " e " + _mf[-1] + f" ({len(_mf)} de 27 estados)"

COMPARA = [("Outros", "Lula"), ("Outros", "Flávio"), ("Outros", "Brancos"), ("Outros", "Nulos"), ("Outros", "Abstenção"),
           ("Brancos", "Lula"), ("Brancos", "Brancos"), ("Nulos", "Lula"), ("Nulos", "Nulos"),
           ("Abstenção", "Lula"), ("Abstenção", "Flávio"), ("Abstenção", "Abstenção")]

def fmt_cel(nivel, a, b):
    c = cel(nivel, a, b)
    return f"{br(c.pct)}% [{br(c.pct_p5)}–{br(c.pct_p95)}]"

def tab_sens(nivel):
    s = M[nivel]["sens"]
    cols = list(s.columns)
    return "\n".join(["| Fluxo | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)] +
                     [f"| {i} | " + " | ".join(f"{br(v)}%" for v in r) + " |" for i, r in s.iterrows()])

def tab_r2():
    linhas = ["| Observações | " + " | ".join(G2) + " |", "|---|" + "---:|" * len(G2)]
    for nivel, nome in (("secao", "seções"), ("municipio", "municípios")):
        med = M[nivel]["r2"].median()
        linhas.append(f"| {nome} | " + " | ".join(br(med[g], 2) for g in G2) + " |")
    return "\n".join(linhas)

import relatorio_integridade
secoes_integridade, resumo_integridade = relatorio_integridade.secoes(S)

md = f"""# Transição de votos para presidente, 1º → 2º turno de 2026

Para onde foram, no 2º turno, os eleitores de cada grupo do 1º turno — Lula, Flávio Bolsonaro, outros
candidatos, brancos, nulos e abstenção — estimado por inferência ecológica a partir dos resultados oficiais
do TSE. Todo o código, os dados derivados e os resultados estão neste repositório para que qualquer pessoa
possa replicar e validar.

## Resumo

- **Lula ganhou {mi(t2['Lula'] - t1['Lula'])} de votos entre os turnos; Flávio, {mi(t2['Flávio'] - t1['Flávio'])}.**
  Os outros candidatos somavam {mi(t1['Outros'])} no 1º turno — menos que o ganho do Lula sozinho.
- **Origem do ganho do Lula** (modelo principal, sobre seções eleitorais): outros candidatos
  {mi(gs['Outros'])}, abstenção do 1º turno {mi(gs['Abstenção'])}, nulos {mi(gs['Nulos'])}, brancos
  {mi(gs['Brancos'])}; perdas de {mi(ps)} (sobretudo eleitores dele que se abstiveram no 2º turno).
- **Eleitores de outros candidatos** se dividiram: {br(cel('secao', 'Outros', 'Lula').pct)}% para o Lula,
  {br(cel('secao', 'Outros', 'Flávio').pct)}% para o Flávio e {br(o_bna.pct)}% votaram branco, nulo ou se
  abstiveram. A divisão varia muito por estado: foram mais para o Flávio em {mais_flavio}; nos demais, mais para
  o Lula.
- **Brancos e nulos do 1º turno** foram em grande parte para o Lula
  ({br(cel('secao', 'Brancos', 'Lula').pct)}% e {br(cel('secao', 'Nulos', 'Lula').pct)}%); o Flávio recebeu cerca
  de 2% de cada grupo. Cerca de um quarto a um terço repetiu o voto branco ou nulo.
- **Abstenção do 1º turno:** {br(cel('secao', 'Abstenção', 'Abstenção').pct)}% continuou se abstendo;
  {br(cel('secao', 'Abstenção', 'Lula').pct)}% votou no Lula e {br(cel('secao', 'Abstenção', 'Flávio').pct)}% no Flávio.
- **A virada foi decidida pela mobilização.** O Flávio terminou o 1º turno {mi(margem1)} à frente e perdeu o 2º
  por {mi(margem2)}. Da virada, {mi(vs['mob'])} vêm de quem não tinha votado em candidato no 1º turno (abstenção,
  brancos e nulos, saldo Lula − Flávio) e só {mi(vs['outros'])} dos eleitores de outros candidatos. A conclusão vale
  também no modelo sobre municípios (ver [Conclusões e hipóteses](#conclusões-e-hipóteses)).
- **Os eleitores novos seguiram a inclinação política do lugar:** onde o Flávio era fraco, quase todos foram para o
  Lula; onde era forte, ele levou a maior parte. Houve mais eleitores novos onde o Lula era forte (ver
  [Eleitores novos](#eleitores-novos)).
- **O que é robusto:** estimando sobre municípios em vez de seções, a direção de todos os fluxos é a mesma.
  Muda o tamanho de alguns: sobre municípios, Outros → Lula sobe para {br(cel('municipio', 'Outros', 'Lula').pct)}%
  e Abstenção → Lula cai para {br(cel('municipio', 'Abstenção', 'Lula').pct)}%. O modelo sobre seções é o mais
  confiável (ver [Comparação](#comparação-entre-modelos)).
{resumo_integridade}
- **Roraima, Amapá e Acre** têm pouca informação para estimar a matriz; as estimativas de Roraima, em especial,
  não devem ser interpretadas (ver [Estados com pouca informação](#estados-com-pouca-informação-rr-ap-e-ac)).
  Juntos têm {br(peso_poucos)}% dos votos em outros candidatos, o que pesa pouco no total do Brasil.

![Fluxos de eleitores entre o 1º e o 2º turno](saida/transicao_secao_fluxos.png)

## Dados

| Nível | Fonte | Uso |
|---|---|---|
| Seção eleitoral | Dados abertos do TSE: `votacao_secao_2026_BR.zip` e `detalhe_votacao_secao_2026.zip` | modelo principal |
| Município | Site de resultados do TSE (`resultados.tse.jus.br`), eleições 6257 (1º turno) e 6258 (2º turno) | comparação |

- Base por seção: {br(len(sec), 0)} seções, todas presentes nos dois turnos, nenhuma anulada.
  Eleitorado de {br(sec.eleitores_1.sum(), 0)}.
- Os totais de Lula, Flávio, brancos, abstenção e eleitorado batem voto a voto entre as duas fontes e com o
  resultado oficial (Lula {br(t2['Lula'], 0)} e Flávio {br(t2['Flávio'], 0)} no 2º turno). A única diferença são
  {br(sec.Outros_1.sum() - mun.Outros_1.sum(), 0)} votos do 1º turno que o site de resultados conta como nulos e o
  arquivo por seção conta em outros candidatos (provavelmente votos em candidaturas indeferidas): 0,06% de Outros.
- Nulos incluem os votos anulados em apuração separada. Em 41 seções os grupos diferem do eleitorado em até
  29 eleitores, nas duas fontes.

## Metodologia

- Para cada seção (ou município), a composição do eleitorado no 2º turno é modelada como a composição do 1º turno
  multiplicada por uma matriz de transição P (6 × 5): cada linha soma 100% e cada entrada fica entre 0 e 100%.
- **Uma matriz por estado**, estimada por mínimos quadrados com essas restrições, ponderando cada observação pelo
  eleitorado. Cada matriz estadual é puxada para a matriz da sua região com peso equivalente a 5 observações
  médias; sobre seções esse puxão é desprezível (ver [Sensibilidade](#sensibilidade)).
- **Brasil:** soma dos fluxos estimados em cada estado e no exterior, o que equivale a ponderar cada matriz pelo
  eleitorado de cada grupo do 1º turno naquele estado.
- **Incerteza:** bootstrap com 200 reamostragens. No modelo sobre seções, reamostram-se grupos inteiros de
  zona eleitoral × município dentro de cada estado, porque seções da mesma zona votam de forma parecida;
  reamostrar seções soltas daria intervalos estreitos demais. Intervalos de 90%.
- Para comparação, o mesmo modelo foi estimado sobre municípios, e uma versão com uma matriz por região.

## Resultados — modelo principal (sobre seções)

### Matriz nacional

% de cada grupo do 1º turno, intervalo de 90% entre colchetes, e eleitores estimados.

{tabela_matriz('secao')}

![Matriz nacional sobre seções](saida/transicao_secao.png)

### De onde veio o ganho do Lula

| Origem no 1º turno | Seções (principal) | Municípios, por estado | Municípios, por região |
|---|---:|---:|---:|
""" + "\n".join(f"| {k} | {mi(gs[k])} | {mi(gm[k])} | {mi(grg[k])} |" for k in ["Outros", "Abstenção", "Nulos", "Brancos", "Flávio"]) + f"""
| Perdas (eleitores do Lula no 1º turno que não votaram nele no 2º) | −{mi(ps)} | −{mi(pm)} | −{mi(prg)} |
| **Ganho líquido** | **{mi(ls)}** | **{mi(lm)}** | **{mi(lrg)}** |

### Conferência: 2º turno estimado × real

| Grupo | Real | Estimado (seções) | Estimado (municípios) |
|---|---:|---:|---:|
""" + "\n".join(f"| {g} | {br(t2[g], 0)} | {br(M['secao']['fluxos'][g].sum(), 0)} | {br(M['municipio']['fluxos'][g].sum(), 0)} |" for g in G2) + f"""

### Por estado

Uma tabela e um gráfico por grupo do 1º turno, com o destino no 2º turno: Lula, Flávio ou
Branco/Nulo/Abstenção (somados). As três colunas somam 100% em cada estado. Estados agrupados por região e em
ordem alfabética. ⚠ = pouca informação (ver seção própria). O intervalo de Branco/Nulo/Abstenção vem das
repetições do bootstrap, não da soma dos intervalos de cada destino.

{chr(10).join(secao_origem(o) for o in ORIGENS)}

## Comparação entre modelos

Brasil, % de cada grupo do 1º turno.

| Fluxo | Seções, por estado (principal) | Municípios, por estado | Municípios, por região |
|---|---|---|---|
""" + "\n".join(f"| {a} → {b} | {fmt_cel('secao', a, b)} | {fmt_cel('municipio', a, b)} | {br(pct_reg(a, b))}% |" for a, b in COMPARA) + f"""

- **Por que o modelo sobre seções é o principal.** A hipótese central da inferência ecológica — eleitores de um
  mesmo grupo se comportam de forma parecida dentro de um estado — é muito mais razoável em grupos de algumas
  centenas de eleitores do mesmo bairro do que em municípios inteiros. Com {br(len(sec), 0)} seções em vez de
  {br(len(mun), 0)} municípios, os intervalos ficam bem mais estreitos e desaparecem artefatos do modelo por
  município, como Brancos → Lula encostando em 100% em vários estados do Nordeste.
- **O que muda.** Sobre municípios, uma parte do ganho do Lula sai de Abstenção e vai para Outros. Uma explicação
  provável (não testada aqui) é que, dentro de um município, os bairros com mais votos em outros candidatos não são
  os mesmos em que mais eleitores voltaram a votar; somando o município inteiro, os dois efeitos se misturam e o
  modelo não consegue separá-los.
- **Identificação no modelo por município.** Em alguns estados (exterior, RS, SC, RJ, PR) os dados por município
  admitem soluções que diferem em 2 a 3 pontos numa célula com praticamente o mesmo ajuste; o total do Brasil
  muda menos de 10 mil eleitores. É mais um motivo para preferir o modelo sobre seções.

## Estados com pouca informação: RR, AP e AC

Roraima, Amapá e Acre têm poucas zonas eleitorais, um eleitorado concentrado na capital e poucos votos em outros
candidatos e em branco — exatamente as linhas da matriz que mais interessam. Sergipe e Distrito Federal, estados
pequenos com estimativas bem determinadas, aparecem para comparação.

{tab_poucos}

- **Roraima** é o caso extremo. O intervalo de 90% vem do número de grupos de zona reamostrados (16, que
  correspondem a 9 zonas eleitorais), não do número de seções; e dois grupos de Boa Vista concentram mais de
  metade do eleitorado. Tirando uma zona de cada vez, o resultado só se mexe quando a zona retirada é de Boa
  Vista. Em parte das reamostragens a solução salta para outra, com Outros → Flávio perto de 0%, o que estica o
  intervalo até zero. A matriz estimada encosta nos limites (0% e 100%) em várias células, sinal de que os dados
  não sustentam valores intermediários:

{tab_rr}

  Nulos indo em sua maioria para a abstenção e Abstenção → Abstenção em 100% não são plausíveis; os números de
  Roraima não devem ser interpretados.
- **Amapá e Acre** ficam no meio do caminho: as estimativas são estáveis, mas os intervalos de brancos e nulos são
  largos (dezenas de pontos). Dá para ler a direção dos fluxos de Outros, não os valores de brancos e nulos.
- **Efeito no Brasil:** os três estados somam {br(peso_poucos)}% dos votos em outros candidatos; a incerteza
  deles já está incluída no intervalo nacional.

## Eleitores novos

Uma conta mais simples, sem modelo de transição, sobre todas as {br(nv['bruto'].loc['Lula'].secoes, 0)} seções:

- **x (eleitores novos em candidato)** = votos em candidato no 2º turno (Lula + Flávio) − votos em candidato no
  1º turno (Lula + Flávio + Outros) = aumento do comparecimento + queda de brancos e nulos.
- **y** = votos que o candidato ganhou entre os turnos.

Cada ponto do gráfico é a média das seções com o mesmo x; a reta e o r são calculados sobre todas as seções (para x
inteiro, a reta das médias ponderadas pelo número de seções é a mesma). O r das médias seria quase 1 e não mede
quanto x explica o ganho de cada seção; o que vale é o r sobre as seções.

| | Ganho total | Ganho sem a parcela de Outros |
|---|---|---|
| **Lula** | {reta('bruto', 'Lula')} · r = {br(nv['bruto'].loc['Lula'].r, 2)} | {reta('sem_outros', 'Lula')} · r = {br(nv['sem_outros'].loc['Lula'].r, 2)} |
| **Flávio** | {reta('bruto', 'Flávio')} · r = {br(nv['bruto'].loc['Flávio'].r, 2)} | {reta('sem_outros', 'Flávio')} · r = {br(nv['sem_outros'].loc['Flávio'].r, 2)} |

![Ganho × eleitores novos](saida/novos_votantes.png)

**Sem a parcela de Outros:** de cada seção sai a parcela que veio de outros candidatos, estimada pela fração Outros →
candidato da matriz do estado × votos em Outros na seção no 1º turno.

![Ganho sem a parcela de Outros × eleitores novos](saida/novos_votantes_sem_outros.png)

- **Inclinação:** cada eleitor novo rendeu em média cerca de {br(nv['sem_outros'].loc['Lula'].a, 1)} voto ao Lula e
  {br(nv['sem_outros'].loc['Flávio'].a, 1)} ao Flávio, com ou sem a parcela de Outros — a relação com os eleitores
  novos não vem da transferência de outros candidatos.
- **Intercepto:** numa seção sem eleitores novos, tirada a parcela de Outros, o Lula ainda ganha cerca de
  {br(nv['sem_outros'].loc['Lula'].b, 0)} votos e o Flávio perde cerca de {br(-nv['sem_outros'].loc['Flávio'].b, 0)}
  (perdas para abstenção, brancos e nulos e trocas entre os dois).
- **Conferência sem a matriz:** a regressão múltipla ganho ~ x + votos em Outros dá
  {br(nv['sem_outros'].loc['Lula'].mult_x, 2)}·x + {br(nv['sem_outros'].loc['Lula'].mult_outros, 2)}·Outros para o
  Lula e {br(nv['sem_outros'].loc['Flávio'].mult_x, 2)}·x + {br(nv['sem_outros'].loc['Flávio'].mult_outros, 2)}·Outros
  para o Flávio. As inclinações em x batem. Os coeficientes de Outros somam 1 por construção (os ganhos dos dois somam
  x + Outros), por isso não são comparáveis às frações da matriz.

### Teste: o achatamento do Flávio é geográfico?

Nos gráficos acima, o ganho do Flávio para de crescer a partir de uns 15 eleitores novos. Para testar se isso é um
"teto" ou efeito de mistura de lugares diferentes, as seções foram divididas em cinco faixas de força do Flávio no
1º turno (% do eleitorado), e cada faixa ganhou sua própria curva; e foi estimada uma curva livre (uma indicadora
para cada valor de x) com efeito fixo de estado e força de Lula e Flávio no 1º turno.

![Teste do achatamento do Flávio](saida/teste_teto_flavio.png)

{tab_faixas()}

Votos = ganho sem a parcela de Outros somado nas seções da faixa (a integral da curva ponderada pelo número de seções).

- **Dentro de cada faixa a curva é quase reta.** O achatamento (inclinação entre x = 15 e 40 dividida pela de 0 a 15;
  1 = reta) fica entre {br(_aq.min(), 2)} e {br(_aq.max(), 2)} nas {len(_aq)} faixas com dados suficientes até
  x = 40, contra {achat('Flávio', 'sem controles')} na curva nacional.
- **A inclinação do Flávio cresce com a força dele no lugar,** de {br(tf['inclinacao_Flávio'].iloc[0], 2)} a
  {br(tf['inclinacao_Flávio'].iloc[-1], 2)}; a do Lula cai de {br(tf.inclinacao_Lula.iloc[0], 2)} a
  {br(tf.inclinacao_Lula.iloc[-1], 2)}. Com interação, a inclinação do Flávio é
  {br(tx.x, 3)} + {br(tx.x_forca, 4)} × força do Flávio (%).
- **Houve mais eleitores novos onde o Flávio era fraco:** seções com 20 ou mais eleitores novos são
  {br(tf.pct_x_20_ou_mais.iloc[0] / tf.pct_x_20_ou_mais.iloc[-1], 0)} vezes mais comuns na faixa mais fraca dele do que
  na mais forte. Nos x altos a média nacional é dominada por esses lugares, e a curva achata.
- **Os controles aditivos não removem o achatamento** ({achat('Flávio', 'com controles')}), porque só deslocam a curva
  — o que muda entre os lugares é a inclinação.
- **Integrais das curvas relativas a x = 0** (votos associados aos eleitores novos): Lula
  {mi(ti.loc['Lula'].sem_controles)} sem controles e {mi(ti.loc['Lula'].com_controles)} com controles; Flávio
  {mi(ti.loc['Flávio'].sem_controles)} e {mi(ti.loc['Flávio'].com_controles)}. Somados, ficam perto do total de
  eleitores novos nessas seções.

**Conclusão do teste:** não há um teto do Flávio em cada lugar; o achatamento é efeito de mistura. Os eleitores novos
seguiram a inclinação política do lugar, e houve mais deles onde o Lula era forte.

## Conclusões e hipóteses

**Fatos (aritmética dos resultados oficiais):**

- Lula ganhou {mi(t2['Lula'] - t1['Lula'])}; Flávio, {mi(t2['Flávio'] - t1['Flávio'])}. Os outros candidatos tinham
  {mi(t1['Outros'])} no 1º turno, então ao menos {mi(t2['Lula'] - t1['Lula'] + t2['Flávio'] - t1['Flávio'] - t1['Outros'])}
  do ganho somado vieram de quem não tinha votado em candidato no 1º turno.
- A diferença virou de {mi(margem1)} para o Flávio no 1º turno para {mi(margem2)} para o Lula no 2º.

**O que o modelo indica com boa confiança — decomposição da virada:**

| Origem | Modelo sobre seções | Modelo sobre municípios |
|---|---:|---:|
| Abstenção, brancos e nulos do 1º turno (Lula − Flávio) | {mi(vs['mob'])} ({mi(vs['mob_L'])} − {mi(vs['mob_F'])}) | {mi(vm['mob'])} |
| Eleitores de outros candidatos (Lula − Flávio) | {mi(vs['outros'])} | {mi(vm['outros'])} |
| Perdas e trocas entre os dois | {mi(vs['resto'])} | {mi(vm['resto'])} |
| **Virada total (estimada)** | **{mi(vs['total'])}** | **{mi(vm['total'])}** |

- **A mobilização de quem não tinha votado em candidato decidiu a eleição** nos dois modelos. Mantidas as demais
  parcelas, sem ela o Flávio teria terminado {mi(-vs['sem_mob'])} à frente (modelo sobre seções).
- Os eleitores de outros candidatos se dividiram quase ao meio, com forte padrão regional.
- As bases foram estáveis: cerca de 99% dos eleitores de cada candidato no 1º turno repetiram o voto.

**Hipóteses (plausíveis, não testadas):**

1. **Mobilização de comparecimento nos redutos do Lula** — o ganho extra veio onde o comparecimento mais subiu; o dado
   não diz se por campanha, rejeição ao adversário ou outro motivo.
2. **Parte dos nulos do 1º turno era voto "errado" do Lula** — com seis votos na urna, o nulo para presidente tende a
   ser maior onde o Lula é forte; com um voto só no 2º turno, esse eleitor teria acertado. Teste possível: comparar
   o nulo para presidente com o nulo para outros cargos na mesma seção.
3. **Os eleitores de outros candidatos seguiram a geografia, não o candidato** — a divisão acompanha a região.

A hipótese do "teto do Flávio" foi testada e descartada (ver o teste acima).

**O que não dá para concluir:** comportamento individual (é inferência ecológica), rotatividade (os fluxos são
líquidos) e causas.

{secoes_integridade}

## Sensibilidade

Brasil, % da linha, variando o peso que puxa cada matriz estadual para a da região (lam, em observações médias;
0 = só os dados do estado; 100 ≈ matriz da região). O modelo principal usa 5.

**Sobre seções**

{tab_sens('secao')}

**Sobre municípios**

{tab_sens('municipio')}

## Qualidade do ajuste

R² dentro de cada estado (variação entre observações explicada pelo modelo), mediana entre os estados:

{tab_r2()}

O R² sobre seções é menor porque cada seção tem poucos votos brancos e nulos, e o ruído de contagem pesa; isso
não indica modelo pior. Lula e Flávio são muito bem explicados nos dois níveis.

## Ressalvas

- **Inferência ecológica.** O modelo infere comportamento individual a partir de totais por seção. Ele vê, por
  exemplo, que o Lula cresceu mais onde havia mais brancos e nulos no 1º turno e atribui esse ganho a esses
  eleitores. Parte disso pode ser efeito de lugar: no 1º turno havia seis votos na mesma urna, e o voto branco ou
  nulo para presidente costuma ser maior onde o Lula já é forte.
- **Fluxos líquidos.** "0% do Lula para o Flávio" significa que as trocas diretas entre os dois se compensaram,
  não que ninguém trocou.
- **O intervalo de 90% mede só a incerteza de amostra,** não o erro que vem da hipótese do modelo, que é maior.

## Como reproduzir

Requer Python 3.11+ e as bibliotecas de `requirements.txt`. Os dados brutos não estão no repositório: os scripts
baixam da fonte oficial (cerca de 95 MB do site de resultados e 476 MB dos dados abertos).

```
pip install -r requirements.txt
python -X utf8 -E -P transicao.py saida/ 200                    # baixa os dados por município; modelo por região
python -X utf8 -E -P transicao_uf.py saida/ 200 5 municipio     # modelo por estado sobre municípios
python -X utf8 -E -P secao_base.py                              # baixa os dados por seção e monta a base
python -X utf8 -E -P transicao_uf.py saida/ 200 5 secao         # modelo principal
python -X utf8 -E -P grafico_fluxos.py saida/ secao             # diagrama de fluxos (também: municipio)
python -X utf8 -E -P grafico_fluxos.py saida/ secao SC          # diagrama de um estado (aqui, Santa Catarina)
python -X utf8 -E -P grafico_novos_votantes.py saida/ bruto      # ganho × eleitores novos
python -X utf8 -E -P grafico_novos_votantes.py saida/ sem_outros # idem, sem a parcela de Outros
python -X utf8 -E -P teste_teto_flavio.py saida/                # teste do achatamento do Flávio
python -X utf8 -E -P estresse_regressao.py saida/               # estresse da regressão de eleitores novos
python -X utf8 -E -P coef_por_forca.py saida/                   # coeficientes que dependem da força do Lula
python -X utf8 -E -P forense.py saida/                          # impressão digital, extremos, resíduos
python -X utf8 -E -P teste_fraude_constante.py saida/ 10        # votos fixos por urna (aqui, 10)
python -X utf8 -E -P urna_amostra.py                            # amostra de seções para os logs
python -X utf8 -E -P urna_baixa.py dados_urna/amostra.csv       # baixa log e boletim (~1 GB)
python -X utf8 -E -P urna_log.py                                # lê os logs
python -X utf8 -E -P urna_analise.py 1                          # testes com os logs
python -X utf8 -E -P base_votacao.py 2022                       # base por seção de 2022 (baixa ~270 MB)
python -X utf8 -E -P base_votacao.py 2026                       # mesma montagem para 2026
python -X utf8 -E -P urna_bu.py                                 # boletins de urna × dados publicados
python -X utf8 -E -P benford.py saida/                          # Benford calibrado
python -X utf8 -E -P poisson_brancos_nulos.py saida/            # brancos e nulos × Poisson
python -X utf8 -E -P fe_modelo.py saida/                        # efeitos fixos por zona, 2022 e 2026
python -X utf8 -E -P fe_interceptos.py saida/                   # interceptos de zona
python -X utf8 -E -P gera_relatorio.py                          # este README
python -X utf8 -E -P validar.py                                 # confere os resultados
```

O bootstrap usa semente fixa, então os resultados se repetem exatamente. Para validar sem baixar nada, rode só
`validar.py`: ele usa as bases já montadas em `saida/` (`transicao_municipios.csv` e `transicao_secoes.csv.gz`),
refaz os ajustes e confere a coerência de todos os resultados publicados.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `transicao.py` | baixa os resultados por município do site do TSE e estima o modelo por região |
| `transicao_uf.py` | modelo por estado (sobre municípios ou seções), agregado para o Brasil, e gráficos |
| `secao_base.py` | baixa os dados abertos por seção e monta a base dos dois turnos |
| `grafico_fluxos.py` | diagrama de fluxos entre os turnos, do Brasil ou de um estado (`transicao_secao_fluxos_sc.png`: Santa Catarina) |
| `grafico_novos_votantes.py` | ganho de cada candidato × eleitores novos, por seção (`saida/novos_votantes*`) |
| `teste_teto_flavio.py` | teste do achatamento do Flávio por faixa de força e com controles (`saida/teste_teto_flavio*`) |
| `estresse_regressao.py`, `coef_por_forca.py` | estresse da regressão e coeficientes em função da força do Lula (`saida/estresse_regressao*`, `saida/coef_por_forca*`) |
| `forense.py`, `teste_fraude_constante.py` | impressão digital, seções extremas, resíduos por modelo de urna, votos fixos por urna (`saida/forense_*`, `saida/teste_fraude_constante*`) |
| `urna_amostra.py`, `urna_baixa.py`, `urna_log.py`, `urna_analise.py` | amostra, download, leitura e testes dos logs de urna (`saida/urna_*`) |
| `urna_bu.py` | lê os boletins de urna da amostra e compara com os dados publicados (`saida/urna_bu_*`) |
| `base_votacao.py`, `benford.py`, `poisson_brancos_nulos.py`, `fe_modelo.py`, `fe_interceptos.py` | bases de 2022 e 2026 e os testes calibrados (`saida/votacao_*`, `saida/benford*`, `saida/poisson_*`, `saida/fe_*`) |
| `relatorio_integridade.py` | seções do README sobre o estresse e os testes de integridade |
| `gera_relatorio.py` | gera este README a partir de `saida/` |
| `validar.py` | confere os resultados publicados |
| `saida/transicao_secoes.csv.gz`, `saida/transicao_municipios.csv` | bases por seção e por município |
| `saida/transicao_secao_*` | modelo principal: matrizes por estado, Brasil, origens agrupadas, fluxos, sensibilidade, R², gráficos (`transicao_secao_origem_*.png` por origem, `transicao_secao_fluxos.png` diagrama de fluxos) |
| `saida/transicao_uf_*`, `saida/transicao_origem_*.png` | mesmo modelo sobre municípios (`transicao_uf_fluxos.png` diagrama de fluxos) |
| `saida/transicao.png`, `saida/transicao_fluxos.csv`, `saida/transicao_por_regiao.csv` | modelo por região |
| `saida/*_log.txt` | saída completa de cada etapa |

## Licença

Código sob licença MIT (ver `LICENSE`). Os dados eleitorais são públicos, do Tribunal Superior Eleitoral.
"""
open(os.path.join(AQUI, "README.md"), "w", encoding="utf-8").write(md)
print("README.md:", len(md), "caracteres")
