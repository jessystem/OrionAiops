# Cola de conceitos — pra eu revisar antes da banca

Esse documento não é pra impressionar ninguém, é pra mim. Reuni aqui os
conceitos técnicos do projeto que mais provavelmente vão virar pergunta —
explicados do jeito mais simples que consegui, sem assumir que quem lê já
sabe o termo. Se alguém perguntar qualquer um desses, a ideia é eu conseguir
responder com minhas palavras, sem precisar decorar frase pronta.

---

## 1. Vazamento de dados (data leakage)

**O que é, em uma frase:** usar, pra treinar o modelo, uma informação que na
vida real só existiria depois do momento em que eu preciso da previsão.

**Exemplo do meu projeto:** a duração do chamado só é conhecida quando ele é
resolvido. Se eu uso a duração pra prever se ele vai violar o prazo, não
estou prevendo nada — estou dando a resposta pro modelo de graça, porque a
definição de "violou" já é literalmente "duração maior que o limite". Um
modelo assim acerta 97%+ nos testes e não serve pra nada em produção, porque
no momento real da previsão (quando o chamado abre) essa informação nem
existe ainda.

**Como eu me protejo disso:** só uso, nas features do modelo de risco,
informações que já existiam no instante em que o chamado foi aberto —
prioridade, grupo, histórico de violação daquele grupo até aquele momento,
carga de trabalho da equipe. Nunca duração, status final, código de
fechamento.

**Se perguntarem "como vocês sabem que não tem vazamento?":** eu tenho uma
lista de colunas proibidas no código (`COLUNAS_VAZAMENTO`), calculo o
histórico olhando só pro passado de cada linha, e existe um teste automático
que quebra a build se alguma coluna proibida voltar pras features.

---

## 2. Por que não uso "acurácia" pra avaliar o modelo de risco

**O problema:** só 0,96% dos incidentes violam o OLA. Um modelo preguiçoso
que responde "nunca viola" pra tudo acerta 99% das vezes — e não serve pra
nada, porque não avisa nenhuma violação.

**O que eu uso no lugar — explicando cada termo:**

- **Precisão** é: das vezes que o modelo disse "vai violar", quantas
  realmente violaram.
- **Recall** é: das violações que de fato aconteceram, quantas o modelo
  conseguiu pegar.
- **PR-AUC** é um número único que resume o equilíbrio entre precisão e
  recall — quanto maior, melhor o modelo separa os casos raros dos comuns.
  O meu deu 0,188, contra uma "linha de base" de 0,0096 (a taxa real de
  violação). Dividindo um pelo outro dá **lift de 19,5** — ou seja, o
  modelo é quase 20 vezes melhor que simplesmente sortear ao acaso quem vai
  violar.
- **Recall @ top 10%** é: se eu revisar só os 10% de chamados que o modelo
  aponta como mais arriscados, quantas violações eu capturo. No meu caso,
  52%.

**Se perguntarem "o AUC de 0,84 não é baixo?":** ROC-AUC de 0,84 é razoável,
mas o número que importa de verdade pra evento raro é o PR-AUC, com lift de
19,5x. E um AUC muito mais alto (tipo 0,97) seria suspeito — provavelmente===
vazamento, não um modelo melhor.

---

## 3. Validação "andando no tempo" (walk-forward)

**O problema de validar embaralhando os dados:** se eu separo treino e
teste aleatoriamente, posso acabar treinando o modelo com um dia de
dezembro e testando com um dia de outubro — ou seja, o modelo "vê o
futuro" antes de prever o passado. Isso infla a nota de um jeito que não
existe na vida real.

**O que eu faço:** treino o modelo usando só os dias que já passaram, e
testo ele prevendo o dia seguinte, um de cada vez, andando no calendário pra
frente — do mesmo jeito que aconteceria se o modelo estivesse rodando de
verdade, todo dia, na operação.

**Se perguntarem "por que não split aleatório?":** porque em série
temporal isso vaza informação do futuro pro treino e mostra um resultado
bom demais pra ser real.

---

## 4. "Olhar só pro passado" no histórico (`shift().expanding()`)

**O que é:** ao calcular a taxa histórica de violação de um grupo, eu não
uso a média do ano inteiro. Uso só os incidentes daquele grupo que
aconteceram **antes** de cada chamado específico.

**Por que importa:** se eu usasse a média do ano inteiro, um chamado de
janeiro estaria "sabendo" da taxa de violação de dezembro — que ainda nem
tinha acontecido quando aquele chamado foi aberto. Parece inofensivo (não é
óbvio como usar a duração), mas é o mesmo tipo de erro: usar informação do
futuro.

**Se perguntarem:** essa é uma forma mais sutil de vazamento que eu só
percebi depois de já ter cometido um erro parecido nas médias móveis do
modelo de volume — por isso tratei os dois do mesmo jeito.

---

## 5. Por que a nota da meta pula em degraus, não sobe suave

**O que descobri:** a nota de atingimento contratual não segue uma régua
contínua (tipo "quanto menor a taxa de erro, proporcionalmente melhor a
nota"). Ela segue uma tabela de faixas fixas: um certo número de violações
cai numa faixa, um número um pouco maior já cai na faixa de baixo.

**Exemplo real do meu dataset:** em 2025, P2 teve 42 violações e ficou na
faixa de 75%. A faixa de 100% ia até 39. Ou seja, 3 violações a menos e a
nota pularia direto pra 100% — um salto de 25 pontos percentuais por causa
de 3 chamados.

**Por que isso importa pro projeto:** um dashboard comum, que só mostra a
taxa média de violação, nunca revelaria o quão perto da borda a operação
estava. Por isso o `AgentePerformance` não reporta taxa, reporta "quantos
incidentes de folga restam antes de cair de faixa".

---

## 6. Codificação cíclica do dia da semana (seno/cosseno)

**O problema:** se eu represento o dia da semana como um número de 0
(segunda) a 6 (domingo), o modelo enxerga domingo (6) e segunda (0) como
"longe" um do outro — quando na real são dias vizinhos no calendário.

**A solução:** transformo esse número em duas coordenadas, usando seno e
cosseno. Isso desenha a semana como um círculo, então domingo e segunda
ficam matematicamente próximos, do jeito que fazem sentido.

**Se perguntarem:** é um truque padrão pra representar qualquer coisa
cíclica (hora do dia, mês do ano) sem criar uma "quebra" artificial entre o
fim e o começo do ciclo.

---

## 7. Ruído de monitoramento

**O que é:** um chamado que o próprio sistema de monitoramento abre
sozinho e fecha sozinho, sem nenhum analista tocar nele. No dataset, isso é
identificado quando o status é "Sem Intervenção" e quem abriu foi
"Monitoramento".

**Por que é importante:** é 65,6% da base inteira. Em setembro de 2025 esse
ruído salta de menos de 50 por mês pra quase 18 mil por mês — mas o volume
de chamados que exige trabalho humano de verdade continua estável no mesmo
período. Ou seja, a "explosão" de incidentes não é a infraestrutura
piorando, é uma ferramenta de monitoramento nova gerando mais alarme
automático.

---

## 8. Divergência entre o flag do cliente e o cálculo teórico de OLA

**O que encontrei:** recalculei "violou o OLA" do zero (duração maior que
o limite da prioridade) e comparei com o flag que já vem pronto no
dataset. Em 3.399 casos (13,3% dos incidentes de KPI), o meu cálculo e o
flag do cliente não batem.

**Minha hipótese:** deve existir uma regra de pausa no relógio de OLA
(tempo esperando resposta do cliente, janela de manutenção, horário
comercial) que não está descrita em nenhuma coluna do dataset.

**Decisão que tomei:** usei o flag do cliente como alvo dos modelos, porque
é a verdade contratual, e deixei a divergência exposta numa coluna própria
em vez de esconder o problema. Virou pergunta pra levar pra banca da
Locaweb.

---

## 9. O que faz um "agente" ser diferente de uma função qualquer

**O contrato comum:** todo agente do projeto segue os mesmos três passos —
observar (lê sua fatia dos dados), decidir (aplica uma regra ou modelo e
gera alertas) e executar (junta os dois passos). Cada agente sempre devolve
uma lista de "sinais" no mesmo formato: severidade, mensagem, ação
recomendada, evidência.

**Ciclo PDCA** é uma sigla de gestão de qualidade: Plan (planejar), Do
(fazer), Check (checar), Act (agir). No projeto: os agentes leem os dados
(Plan), tomam decisões (Do), o agente de aprendizado audita se as previsões
anteriores estavam certas (Check), e o orquestrador consolida tudo num
plano de ação (Act).

---

## 10. Por que um agente quebrando não derruba os outros

**O que fiz:** o orquestrador roda cada agente dentro de um bloco de
tratamento de erro (try/except). Se um agente falhar, o erro fica registrado
numa lista separada, mas os outros quatro continuam rodando normalmente.

**Por que importa:** numa operação real, se o agente de capacidade travar
por falta de dado num dia, isso não pode impedir o agente de risco de OLA
de gerar a fila do dia. Testei esse comportamento simulando uma falha de
propósito no notebook 05.
