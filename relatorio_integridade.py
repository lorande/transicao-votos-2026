"""Seções do README sobre o estresse das regressões e os testes de integridade estatística (usado por gera_relatorio.py).

Todos os números vêm dos CSVs de saida/ gerados por estresse_regressao.py, coef_por_forca.py, forense.py,
teste_fraude_constante.py, urna_analise.py, benford.py, poisson_brancos_nulos.py, fe_modelo.py e fe_interceptos.py.
"""
import os
import numpy as np, pandas as pd

def br(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def le(S, nome, **kw):
    return pd.read_csv(os.path.join(S, nome), **kw)

def serie(S, nome):
    return le(S, nome, index_col=0)["valor"]

def secoes(S):
    est = le(S, "estresse_regressao.csv", index_col=[0, 1])
    reg = le(S, "estresse_regressao_regioes.csv")
    med = le(S, "estresse_regressao_medias.csv", index_col=0)
    cf = le(S, "coef_por_forca_ajustes.csv").set_index("forma")
    kl = le(S, "forense_klimek.csv")
    ex = serie(S, "forense_extremos_resumo.csv")
    rs = serie(S, "forense_residuos_resumo.csv")
    mu = le(S, "forense_modelo_urna.csv", index_col=0)
    fc = le(S, "teste_fraude_constante.csv")
    ur = serie(S, "urna_resumo.csv")
    bu = le(S, "urna_bu_resumo.csv").set_index("NR_TURNO")
    bf = le(S, "benford.csv")
    po = le(S, "poisson_brancos_nulos.csv")
    fe = le(S, "fe_modelo.csv", index_col=[0, 1, 2])
    ir = {a: le(S, f"fe_interceptos_regioes_{a}.csv", index_col=0) for a in (2022, 2026)}

    c = lambda spec, var: est.loc[(spec, var), "coef"]
    fcp = fc[(fc["variável"] == "ganho_Lula") & (fc["especificação"] == "efeito fixo de local + composição")].iloc[0]
    fbn = fc[(fc["variável"] == "queda_BNA") & (fc["especificação"] == "efeito fixo de local + composição")].iloc[0]
    sim_col = [k for k in fc.columns if k.startswith("c_com_fraude")][0]
    K = sim_col.split("_")[-1]
    lim_c = fcp.c_real + 1.645 * fcp.ep_real
    k2 = kl[(kl.turno == 2)].set_index("candidato")

    def cand_tab():
        linhas = ["| Candidato do 1º turno | Fração para o Lula (efeito fixo de estado) |", "|---|---:|"]
        for v in ("Cury", "Renan Santos", "Caiado", "Zema", "Demais"):
            if ("Outros por candidato + EF UF", v) in est.index:
                linhas.append(f"| {v} | {br(c('Outros por candidato + EF UF', v))} |")
        return "\n".join(linhas)

    def bf_tab(nivel):
        x = bf[bf.teste == nivel]
        cal = x[x.papel == "calibração"]
        linhas = []
        for _, t in x[x.papel == "teste"].iterrows():
            z = (t.MAD - cal.MAD.mean()) / cal.MAD.std()
            linhas.append(f"| {nivel} | {br(cal.MAD.min(), 4)} a {br(cal.MAD.max(), 4)} | {t.candidato}: "
                          f"{br(t.MAD, 4)} (z = {br(z, 1)}) |")
        return "\n".join(linhas)

    def po_lin(eleicao, var):
        r = po[(po["eleição"] == eleicao) & (po["variável"] == var)].iloc[0]
        return (f"| {var} {eleicao}{' (teste)' if r.papel == 'teste' else ''} | {br(r.phi_mediana, 3)} | "
                f"{br(r['%zonas_excesso(p<0,05)'], 1)}% | {br(r['%zonas_falta(p<0,05)'], 1)}% |")

    def fe_lin(var, rot):
        return (f"| {rot} | {br(fe.loc[(2022, 'Lula', var), 'coef'])} | {br(fe.loc[(2026, 'Lula', var), 'coef'])} | "
                f"{br(fe.loc[(2026, 'Flávio', var), 'coef'])} |")

    def ir_lin(r):
        return f"| {r} | {br(ir[2022].loc[r, 'mediana'], 1)} | {br(ir[2026].loc[r, 'mediana'], 1)} |"

    reg_l = "\n".join(f"| {r.região} | {br(r.a_x)} | {br(r.c_Outros)} | {br(r['x médio'], 1)} |"
                      for _, r in reg[reg.região != "Exterior"].iterrows())

    texto = f"""## Estresse da regressão de eleitores novos

A regressão ganho ~ x + Outros (seção [Eleitores novos](#eleitores-novos)) foi refeita em várias especificações
({br(med.loc['eleitores_1', 'média'], 0)} eleitores por seção em média; x médio {br(med.loc['x', 'média'], 1)}, dos quais
{br(med.loc['dA', 'média'], 1)} de queda da abstenção e {br(med.loc['dBN', 'média'], 1)} de queda de brancos e nulos).
Pela identidade ganho do Lula + ganho do Flávio = x + Outros, os coeficientes das duas equações somam 1 e basta a do Lula.

| Especificação (Lula) | x | Outros | r² |
|---|---:|---:|---:|
| Base | {br(c('base', 'x'))} | {br(c('base', 'Outros'))} | {br(est.loc[('base', 'x'), 'r2'])} |
| Ponderada pelo eleitorado | {br(c('peso = eleitorado', 'x'))} | {br(c('peso = eleitorado', 'Outros'))} | {br(est.loc[('peso = eleitorado', 'x'), 'r2'])} |
| Efeito fixo de estado | {br(c('efeito fixo de UF', 'x'))} | {br(c('efeito fixo de UF', 'Outros'))} | {br(est.loc[('efeito fixo de UF', 'x'), 'r2'])} |
| + força de Lula e Flávio no 1º turno | {br(c('+ força no 1º turno', 'x'))} | {br(c('+ força no 1º turno', 'Outros'))} | {br(est.loc[('+ força no 1º turno', 'x'), 'r2'])} |

- **Queda de brancos e nulos × queda da abstenção:** separando x, a queda de brancos e nulos rende
  {br(c('x separado', 'dBN'))} voto ao Lula ({br(c('x separado + EF UF', 'dBN'))} com efeito fixo de estado); a queda
  da abstenção, {br(c('x separado', 'dA'))} ({br(c('x separado + EF UF', 'dA'))}). Quem deixou de votar branco ou nulo
  foi quase todo para o Lula.
- **Intercepto = força local.** Com os votos do Lula no 1º turno como controle, o intercepto quase some e aparece
  +{br(c('+ força no 1º turno', 'Lula1'), 3)} × votos do Lula no 1º turno; os do Flávio ficam com ≈ 0.
- **Por região:**

| Região | x → Lula | Outros → Lula | x médio por seção |
|---|---:|---:|---:|
{reg_l}

- **Outros separados por candidato:**

{cand_tab()}

  Estes coeficientes embutem a parcela dos eleitores de cada candidato que foi para branco, nulo ou abstenção (que
  reduz x). O do Zema tem pouca precisão (poucos votos, concentrados em Minas).

### Coeficientes que dependem da força local

Os coeficientes de x e de Outros como função da força do Lula no 1º turno (p = votos do Lula ÷ eleitorado da seção):

| Forma | Eleitores novos | Outros | r² |
|---|---|---|---:|
| Coeficientes fixos | {br(c('base', 'x'), 3)} | {br(c('base', 'Outros'), 3)} | {br(est.loc[('base', 'x'), 'r2'], 3)} |
| Linear a·(1 + b·p) | {br(cf.loc['linear', 'a_x'], 3)}·(1 + {br(cf.loc['linear', 'b_x'])}·p) | {br(cf.loc['linear', 'a_O'], 3)}·(1 + {br(cf.loc['linear', 'b_O'])}·p) | {br(cf.loc['linear', 'r2'], 3)} |
| Logística 1/(1 + e^−(α+β·p)) | α = {br(cf.loc['logística', 'alfa_x'])}, β = {br(cf.loc['logística', 'beta_x'])} | α = {br(cf.loc['logística', 'alfa_O'])}, β = {br(cf.loc['logística', 'beta_O'])} | {br(cf.loc['logística', 'r2'], 3)} |

![Coeficientes por força do Lula](saida/coef_por_forca.png)

Os eleitores novos e os de Outros se dividiram conforme a força local do Lula, com a mesma sensibilidade (β ≈
{br(cf.loc['logística', 'beta_x'], 1)} nas duas variáveis). Na curva livre, a fração de Outros que foi para o Lula cai
nas seções onde ele é muito dominante — possivelmente porque ali quem votou em outro candidato tende a ser o eleitor
contrário a ele.

## Testes de integridade estatística

Estatística encontra anomalias, não fraude: cada teste abaixo foi desenhado para detectar um tipo de manipulação, e
os que podem ser calibrados foram calibrados injetando a fraude nos dados reais ou comparando com eleições anteriores.
Nenhum substitui as auditorias oficiais (boletins assinados, registro digital do voto, teste de integridade).

| Teste | O que detectaria | Resultado |
|---|---|---|
| Impressão digital (comparecimento × votação) | inserção de votos em seções específicas | sem cauda; {int(k2.loc['Lula', 'secoes_comp95_voto95'])} seções com comparecimento e voto no Lula ≥ 95% em {br(ex['secoes'], 0)} |
| Salto de comparecimento × vizinhas do mesmo local | adulteração localizada | {int(ex['secoes_z4'])} seções a 4+ desvios, nos dois sentidos; efeito líquido de {br(ex['efeito_liquido_z4'], 0)} votos na diferença |
| Resíduos por modelo de urna, no mesmo local | urna de um modelo com resultado diferente | diferenças ≤ {br(mu['mean_dentro_local'].abs().max(), 2)} voto por seção |
| Votos fixos por urna | conversão de K votos por urna | c = {br(fcp.c_real)} ± {br(fcp.ep_real)} (com {K} injetados: {br(fcp[sim_col], 1)}); máximo compatível {br(lim_c, 2)} voto por urna |
| Logs de urna: biometria (amostra) | votos sem eleitor real | liberações sem biometria +{br(ur['d_sem_bio_media'])} por seção (com {br(ur['insercao_simulada_pct'], 0)}% inserido: +{br(ur['d_sem_bio_com_insercao'])}); inserção máxima {br(ur['insercao_maxima_pct'], 2)}% do eleitorado |
| Boletins de urna × dados publicados (amostra) | redistribuição dos votos depois da urna | {br(bu.batem.min(), 0)} de {br(bu.boletins.min(), 0)} boletins batem voto a voto nos dois turnos |
| Benford 1BL e 2BL, calibrado | números fabricados | dentro da faixa de 2022 e do 1º turno de 2026 |
| Brancos e nulos × Poisson, por zona | números regulares demais | igual ao 2º turno de 2022 |
| Efeitos fixos por zona, contra 2022 | concentração em zonas | distribuições contínuas, sem zonas destoantes |

### Impressão digital, seções extremas e resíduos

![Impressão digital](saida/forense_klimek.png)

- **Impressão digital:** nuvens contínuas, sem mancha no canto de comparecimento e votação próximos de 100%; correlação
  entre comparecimento e votação de {br(k2.loc['Lula', 'corr_comparecimento_voto'])} (Lula) e
  {br(k2.loc['Flávio', 'corr_comparecimento_voto'])} (Flávio) no 2º turno.
- **Comparecimento ≥ 95%:** {int(ex['comp95_t2'])} seções no 2º turno, pequenas (mediana de
  {br(ex['eleitores_mediana_comp95_t2'], 0)} eleitores, contra {br(ex['eleitores_mediana_brasil'], 0)}), quase sempre a
  única do seu local; o comparecimento alto é do lugar inteiro.
- **Salto de comparecimento contra as vizinhas do mesmo local:** desvio típico de {br(ex['dp_robusto_desvio_pp'], 1)}
  ponto; {int(ex['z6_acima'])} seções a 6+ desvios acima e {int(ex['z6_abaixo'])} abaixo (lista em
  `saida/forense_extremos.csv`).
- **Resíduos do modelo de transição:** média de {br(rs['residuo_media'])} voto por seção na diferença Lula − Flávio;
  {br(rs['pct_var_entre_locais'], 0)}% da variação fica entre locais de votação (geografia). Por modelo de urna, as
  diferenças brutas somem ao comparar seções do mesmo local. {int(rs['urnas_trocadas'])} urnas trocadas entre os turnos
  não destoam (resíduo {br(rs['residuo_trocadas'])}). {int(rs['secoes_fora_da_urna'])} seções têm resultado que não saiu
  direto da urna.

![Salto de comparecimento](saida/forense_salto_comparecimento.png)
![Resíduos por modelo de urna](saida/forense_residuos.png)

### Votos fixos por urna

Hipótese testada: {K} votos de brancos, nulos ou abstenção convertidos em votos no Lula em cada urna. Um número fixo
pesa mais nas seções pequenas; o teste compara seções de tamanhos diferentes no mesmo local de votação.

![Teste de votos fixos por urna](saida/teste_fraude_constante.png)

Nos dados reais, c = {br(fcp.c_real)} ± {br(fcp.ep_real)} voto por urna no ganho do Lula e {br(fbn.c_real)} na queda de
brancos, nulos e abstenção; com a fraude injetada, {br(fcp[sim_col], 1)} e {br(fbn[sim_col], 1)}. Uma fraude
**proporcional** ao eleitorado não é distinguível por este teste.

### Logs de urna

Amostra de {int(ur['secoes_aleatorias'])} seções sorteadas por estado e {int(ur['secoes_com_log'] - ur['secoes_aleatorias'])}
seções sinalizadas pelos testes acima; log e boletim dos dois turnos (`urna_amostra.py`, `urna_baixa.py`, `urna_log.py`).
Os arquivos de log não estão no repositório.

- **Biometria:** {br(ur['pct_sem_bio_t1'])}% dos eleitores liberados sem biometria no 1º turno e
  {br(ur['pct_sem_bio_t2'])}% no 2º; variação de {br(ur['d_sem_bio_media'])} ± {br(ur['d_sem_bio_ep'])} por seção. Uma
  inserção de {br(ur['insercao_simulada_pct'], 0)}% do eleitorado em votos sem eleitor real levaria a
  {br(ur['d_sem_bio_com_insercao'])}; a inserção máxima compatível com os dados é de {br(ur['insercao_maxima_pct'], 2)}%
  do eleitorado.
- **Ritmo:** nenhum voto a menos de 10 segundos do anterior; o voto mais rápido no 2º turno vem da cédula com um só cargo.
- **Consistência:** em {int(ur['log_dif_boletim_t2'])} seções o log tem menos votos que o boletim no 2º turno
  (provavelmente urnas substituídas durante o dia; só o log da urna totalizada foi baixado). Lista em
  `saida/urna_inconsistencias.csv`.

### Boletins de urna × dados publicados

O boletim de urna (BU) é o arquivo assinado que cada urna grava ao encerrar a votação, antes de qualquer transmissão,
e que também é impresso e afixado na seção. Para as seções da amostra de logs, `urna_bu.py` lê no BU os votos para
presidente (Lula, adversário, outros, brancos e nulos) e compara com o arquivo de votação por seção dos dados abertos,
usado em todas as análises deste repositório.

| Turno | Boletins | Batem voto a voto | Votos conferidos | Diferença absoluta |
|---|---:|---:|---:|---:|
{chr(10).join(f"| {t}º | {br(r.boletins, 0)} | {br(r.batem, 0)} | {br(r.votos_bu, 0)} | {br(r.dif_abs_total, 0)} |" for t, r in bu.iterrows())}

Batem também todas as seções sinalizadas (comparecimento ≥ 95%, salto extremo, resultado fora da urna). Uma
redistribuição dos totais na transmissão ou na totalização apareceria aqui como divergência; uma troca feita dentro do
programa da urna, não, porque o BU já sairia trocado. A assinatura digital dos BUs não foi conferida. Comparação
seção a seção em `saida/urna_bu_comparacao.csv`.

### Benford, calibrado

1BL nos totais por município (e por zona) e 2BL nas contagens por seção. Calibração: 2022 1º e 2º turnos (Lula e
Bolsonaro) e 2026 1º turno; teste: 2026 2º turno. Com 500 mil seções o qui-quadrado rejeita Benford em qualquer
eleição; o que importa é se o caso testado destoa da calibração.

| Teste | MAD na calibração | 2026 2º turno |
|---|---|---|
{bf_tab('1BL município')}
{bf_tab('1BL zona')}
{bf_tab('2BL seção')}

![Benford](saida/benford.png)

### Brancos e nulos × Poisson

Em cada zona, esperado por seção = taxa da zona × comparecimento; φ = X² / (n − 1) (1 = Poisson; < 1 = regular demais).

| Caso | φ mediano | Zonas com excesso de variação | Zonas com falta de variação |
|---|---:|---:|---:|
{po_lin('2022 2º turno', 'Brancos')}
{po_lin('2026 2º turno', 'Brancos')}
{po_lin('2022 2º turno', 'Nulos')}
{po_lin('2026 2º turno', 'Nulos')}

Sob Poisson puro, 5% das zonas apareceriam com falta de variação.

![Brancos e nulos](saida/poisson_brancos_nulos.png)

### Efeitos fixos por zona eleitoral, contra 2022

ΔVotos = efeito fixo da zona + β1·ΔComparecimento + β2·Queda de brancos + β3·Queda de nulos + β4·Outros 1T, por seção
(os β do adversário são 1 − β do Lula).

| β | Lula 2022 | Lula 2026 | Flávio 2026 |
|---|---:|---:|---:|
{fe_lin('dComp', 'β1 ΔComparecimento')}
{fe_lin('qBrancos', 'β2 Queda de brancos')}
{fe_lin('qNulos', 'β3 Queda de nulos')}
{fe_lin('Outros1', 'β4 Outros no 1º turno')}

![Efeitos fixos por zona](saida/fe_modelo.png)

O Lula capta mais de cada fluxo em 2026 do que em 2022, sobretudo de brancos e nulos. Estimados zona a zona, os β têm
distribuição contínua, sem um grupo de zonas destoante; os resíduos de 2026 têm caudas até mais leves que os de 2022.

**Interceptos de zona** (votos do Lula por seção não explicados pelos quatro fluxos; mediana das zonas):

| Região | 2022 | 2026 |
|---|---:|---:|
{chr(10).join(ir_lin(r) for r in ('NE', 'N', 'SE', 'CO', 'S'))}

![Interceptos de zona](saida/fe_interceptos.png)

A distribuição inteira se deslocou a favor do Lula de 2022 para 2026, com a mesma ordem entre regiões; o intercepto
acompanha a força do Lula no 1º turno (r = {br(ir[2026]['r_forca'].iloc[0])}). O agrupamento das zonas (k-means) não
encontra grupos naturais: as zonas variam de forma contínua, em faixas alinhadas à força do Lula. Roraima destoa (cerca
de +11 votos por seção): o comparecimento caiu entre os turnos e quem deixou de votar foi, em grande parte, eleitor do
Flávio — em 2026 ele perdeu votos em números absolutos em AC, AP, RR, AM, TO e MA, o que não aconteceu com Bolsonaro em
nenhum estado em 2022.

**O que estes testes não alcançam:** a conferência dos boletins exclui redistribuição depois da urna nas seções da
amostra, mas uma troca proporcional dentro do programa da urna (voto branco gravado como Lula,
sem eleitor a mais) seria indistinguível do comportamento real em todos os testes acima; ela é o objeto do teste de
integridade (votação paralela) e da auditoria do código, não de estatística sobre os dados publicados.
"""
    resumo = (f"- **Testes de integridade estatística** (impressão digital, seções extremas, modelo de urna, votos fixos "
              f"por urna, logs de biometria, Benford, Poisson e efeitos fixos por zona, calibrados com 2022) não mostram as "
              f"marcas de manipulação que detectariam; a inserção de votos sem eleitor real compatível com os logs é de no "
              f"máximo {br(ur['insercao_maxima_pct'], 2)}% do eleitorado, e os {br(bu.boletins.min(), 0)} boletins de urna "
              f"conferidos batem voto a voto com os dados publicados (ver "
              f"[Testes de integridade](#testes-de-integridade-estatística)).")
    return texto, resumo
