# Roteiro do Pitch

Dois formatos, mesma espinha dorsal: o vídeo de 3 minutos (10% da nota) e a
apresentação à banca da Locaweb (50% da nota).

---

## A regra que organiza tudo

A banca não avalia quanto código vocês escreveram. Avalia se vocês entenderam o
problema **dela**. Os critérios oficiais são:

1. Clareza na definição do problema
2. Qualidade da análise exploratória
3. Coerência e justificativa da modelagem
4. Capacidade de antecipação (D+1 e D+7)
5. Geração de valor para a tomada de decisão
6. Comunicação dos resultados (storytelling executivo)

Quatro dos seis são sobre **entendimento e comunicação**, não sobre técnica.

---

## Abertura — os primeiros 30 segundos

Não comece por "nosso grupo desenvolveu uma plataforma AIOps". Comece pelo número
que dói:

> "Em 2025, a operação de vocês fechou o indicador de OLA de P2 em 75% de
> atingimento. Foram 42 violações. A faixa de 100% termina em 39.
>
> **Três incidentes.** Três incidentes separaram 75% de 100% de meta contratual.
>
> E nenhum dashboard mostraria isso, porque a taxa média de violação de P2 foi
> 0,81% — um número que parece excelente.
>
> O ORION existe para identificar esses três incidentes antes que aconteçam."

Isso faz três coisas ao mesmo tempo: prova que vocês leram o dicionário de dados
até o fim, mostra domínio do negócio deles, e cria a tensão que sustenta os
próximos dez minutos.

---

## Estrutura da apresentação (12 a 15 minutos)

### Bloco 1 · O problema (2 min)

* Operação 24x7, 122 mil incidentes/ano, disponibilidade como fator crítico
* Três perguntas sem resposta hoje: quanto vem? quem vai estourar? onde fechamos o ano?
* **O gancho dos 3 incidentes** (acima)

**Slide-chave:** o gráfico de degraus das faixas de meta, com a linha vertical em 42.

### Bloco 2 · O que os dados revelaram (3 min)

Escolha **três** achados. Mais que isso dilui.

1. **Quebra de regime em set/2025** — mostre o gráfico do salto de 6x e depois o
   gráfico da série de KPI estável. A frase: *"não é degradação da infraestrutura,
   é mudança de instrumentação. Quem modelasse o histórico inteiro previria lixo."*

2. **A divergência de OLA** — 3.399 casos em que o flag não bate com a regra escrita.
   A frase: *"encontramos violações registradas abaixo do limite e não-violações muito
   acima. Nossa hipótese é pausa de relógio. **Essa é a nossa pergunta para vocês.**"*
   Fazer uma pergunta técnica à banca inverte a dinâmica: vocês deixam de ser
   avaliados e passam a ser interlocutores.

3. **IC00349** — 1.448 incidentes de KPI a 120 por mês, um único ativo.
   A frase: *"isso não é incidente recorrente, é problema crônico. É a recomendação
   de maior retorno do projeto e não precisa de machine learning nenhum para ser
   executada."*

### Bloco 3 · A solução (3 min)

* Diagrama da arquitetura Bronze/Silver/Gold → Modelos → Agentes → BI
* Os cinco agentes, um slide, uma linha cada
* **Não descreva o código.** Descreva o que cada agente decide.

**Slide-chave:** a saída real do `plano_de_acao()` — o texto que chega ao Teams do
gestor todo dia. É a prova de que a solução produz decisão, não só número.

### Bloco 4 · Resultados (3 min)

Tabela de MAE contra baselines. E aqui vem o movimento que diferencia o grupo:

> "Nosso classificador de risco de OLA tem AUC de 0,842.
>
> Numa versão anterior ele tinha 0,977 — e nós o descartamos. Aquele modelo usava
> `Duração` e `Código de fechamento` como features. Esses campos só existem depois
> que o chamado é resolvido. No momento em que a operação precisa da previsão, eles
> estão vazios.
>
> 0,842 é o número que sobrevive à produção."

Assumir voluntariamente que vocês jogaram fora o número melhor é a coisa mais
convincente que se pode fazer numa banca técnica. Nenhum outro grupo vai fazer isso.

Feche com a tradução operacional:

> "Revisando os 6 chamados mais arriscados por dia, o sistema captura 52% das
> violações de OLA. Em 2025 isso seria a chance de interceptar cerca de 22 das 42
> violações de P2 — mais do que suficiente para devolver o indicador de 75% para 100%."

### Bloco 5 · Demonstração ao vivo (2 min)

Ordem de impacto decrescente — se o tempo acabar, o que já foi mostrado é o melhor:

1. Página executiva do Power BI, com o cartão de folga em vermelho
2. `python run_pipeline.py` rodando (60 segundos, cabe na apresentação)
3. `GET /agentes/plano` no `/docs` da API

### Bloco 6 · Limitações e roadmap (1 min)

Não pule este bloco. Ele vale mais que um slide a mais de resultado.

> "Três limitações que conhecemos: o modelo não sabe o que é feriado, e por isso
> superestima dezembro em 25% — o nosso próprio agente de aprendizado detectou isso
> sozinho. Não temos a regra de pausa do OLA. E 63% dos registros não têm taxonomia,
> o que limita a análise de causa raiz."

Terminar admitindo o que não se sabe passa mais confiança do que terminar afirmando
que está tudo resolvido.

### Encerramento (30 s)

Volte aos três incidentes. Feche o arco.

---

## Vídeo pitch (3 minutos)

Comprima para quatro blocos, 45 segundos cada:

| Tempo | Conteúdo |
|---|---|
| 0:00–0:45 | O gancho dos três incidentes + o problema |
| 0:45–1:30 | Os três achados (rápido, com gráficos na tela) |
| 1:30–2:15 | A solução em movimento: pipeline rodando + plano de ação dos agentes |
| 2:15–3:00 | Resultados + a admissão do AUC descartado + fechamento |

Dicas de produção:

* Grave a tela com narração; evite falar em frente à câmera o tempo todo
* Legendas embutidas — muita gente assiste sem som
* Suba como **não listado** no YouTube e teste o link numa aba anônima antes de entregar
* O arquivo `.TXT` com o link deve trazer nome da equipe, RMs e nomes em ordem
  alfabética, conforme a regra 16 do documento do Challenge

---

## Perguntas que a banca provavelmente vai fazer

**"Por que LightGBM e não ARIMA/Prophet para série temporal?"**
Porque a sazonalidade dominante é o dia da semana, e árvores capturam isso via
features de calendário. Além disso, precisávamos incorporar variáveis exógenas —
carga por grupo, ICs ativos, violações recentes — sem reformular o modelo. E o mesmo
pipeline atende duas prioridades e dois horizontes. Testamos contra três baselines
ingênuos e o modelo ganhou nas quatro combinações.

**"O AUC de 0,84 não é baixo?"**
Para um evento com 0,96% de prevalência, o que importa é o PR-AUC: 0,188 contra uma
linha de base de 0,0096 é um lift de 19,5 vezes. Traduzindo: os 10% de maior score
concentram 5,2 vezes mais violações que a fila aleatória.

**"Como vocês sabem que não há vazamento?"**
Três camadas de proteção: uma lista explícita de colunas proibidas em `features.py`,
histórico calculado com `shift(1).expanding()` em vez de média do período, e um teste
automatizado que falha o CI se qualquer coluna post-mortem voltar para as features.

**"Isso funciona em qualquer nuvem?"**
Sim. Nenhum serviço proprietário está acoplado ao código. A camada de persistência é
Parquet, e trocar caminho local por S3, Blob ou GCS é mudar uma linha em `config.py`.

**"Quanto custaria rodar isso?"**
Entre US$ 35 e US$ 420 por mês, dependendo de usar EC2 com cron ou Airflow gerenciado.
O detalhamento está em `docs/ARQUITETURA.md`.

**"Por que cinco agentes e não um script?"**
Porque cada um tem relógio próprio — risco roda de hora em hora, performance uma vez
por dia, aprendizado uma vez por semana — e porque a falha de um não pode derrubar os
outros. O orquestrador isola exceção por agente; demonstramos isso no notebook 05.

---

## Checklist de entrega (Sprint 2 — 17/05/2026)

- [ ] `EC_Sprint_2_2TSCP_arqsolucao_ORION_<nome_grupo>.pptx`
- [ ] Nome completo e RM de todos os integrantes, em **ordem alfabética**
- [ ] Problema, público-alvo e proposta da Sprint 1 **atualizados**, indicando o que mudou
- [ ] Desenho da arquitetura + papel de cada tecnologia
- [ ] Protótipos com descrição do significado de cada um
- [ ] Gestão do projeto com framework ágil (backlog, sprints, divisão de tarefas)
- [ ] Análise exploratória dos dados fornecidos
- [ ] Finalização e agradecimentos
- [ ] Arquivo entregue em **todas** as disciplinas no portal da FIAP
- [ ] Cópia completa com todos os integrantes (regra da "Dica" do documento)
