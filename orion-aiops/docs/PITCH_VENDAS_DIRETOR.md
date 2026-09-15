# ORION AIOps — Roteiro de Pitch (6 minutos, C-Level)
Método A.D.N.A. — apresentação para o Diretor da Locaweb

---

## A — Atenção (1 min · ~150 palavras)

Em 2025, o indicador de OLA de prioridade Alta (P2) da operação de vocês fechou em 75% de atingimento contratual. Foram 42 violações no ano. A faixa de 100% termina em 39.

Três incidentes. Três incidentes separaram 75% de 100% de meta contratual — 25 pontos percentuais de desconto, ano inteiro, por uma diferença que cabe numa única tarde ruim.

E o pior: nenhum dashboard hoje mostraria isso. A taxa média de violação de P2 foi 0,81% — um número que qualquer board olharia e diria "está ótimo". O problema não está na média. Está na contagem absoluta contra o degrau da meta, e isso é invisível até fechar o trimestre.

O ORION existe para uma coisa: mostrar, todo dia, a distância até esse degrau — antes que os três incidentes aconteçam, não depois.

---

## D — Dor (1 min · ~150 palavras)

Hoje a operação enxerga risco pelo retrovisor. O time descobre que perdeu a faixa de meta quando o relatório fecha, não quando dá para agir.

Isso custa em três frentes. Primeiro, financeiro direto: cada faixa perdida é desconto contratual, e a diferença entre faixas é pequena — três a cinco chamados, não trezentos. Segundo, ruído mascarando sinal: 65,6% da base de incidentes é gerada e fechada pelo próprio monitoramento, sem analista tocar. Isso enterra o time real dentro de um volume que parece três vezes maior do que é. Terceiro, causa raiz não tratada: um único ativo, sozinho, gera 1.448 incidentes por ano — 120 por mês, sempre o mesmo problema, sempre reaberto como se fosse novo. É gestão de sintoma, não de causa, e ninguém está bloqueado, mas todo mundo está ocupado.

O board não vê nada disso porque a métrica que ele recebe é a média. E a média esconde exatamente o que quebra a meta.

---

## N — Narrativa (2 min · ~300 palavras)

Imagine o seguinte: toda manhã, antes de qualquer reunião, o gestor da operação abre o Teams e já tem uma lista com os seis chamados mais arriscados do dia — não o volume inteiro, os seis que realmente importam. Esses seis, sozinhos, concentram mais da metade das violações de OLA que vão acontecer no mês. Não é uma planilha para ele interpretar. É uma recomendação pronta: "atue nestes agora".

O ORION funciona com cinco agentes automáticos, cada um com seu próprio relógio. Um verifica risco de hora em hora. Outro projeta se o volume de amanhã e da próxima semana vai estourar a capacidade do time. Outro traduz tudo isso para a linguagem que o board entende: não "taxa de violação", mas "quantos pontos percentuais de meta contratual estamos hoje, e quantos incidentes de folga ainda temos até cair de faixa". Um quarto agente identifica os ativos crônicos — como aquele único equipamento gerando 120 chamados por mês — e sinaliza que ali o problema não é imprevisibilidade, é manutenção adiada. E o quinto agente aprende sozinho: ele já percebeu, por conta própria, que o modelo superestima dezembro por causa de feriados, e ajustou a leitura.

Nada disso exige trocar a infraestrutura que a Locaweb já usa. O ORION lê os dados de incidente que já existem, roda sobre a nuvem que já está em uso, e o custo de operação fica entre 35 e 420 dólares por mês — não é um projeto de seis dígitos, é uma linha de orçamento.

A implantação inicial não mexe em processo nenhum do time. Ela só coloca, na frente de quem decide, a pergunta certa antes do incidente, em vez da explicação depois dele.

---

## A — Ação (2 min · ~300 palavras)

Não estou pedindo para aprovar uma plataforma nova hoje. Estou pedindo 30 dias.

A proposta é uma Prova de Conceito rodando sobre o histórico real de 2025 da própria operação da Locaweb — os mesmos 122 mil incidentes, os mesmos times, a mesma meta contratual de P2 que fechou em 75%. Sem mudar infraestrutura, sem contrato de longo prazo, sem risco de operação: é um teste, em paralelo, contra o que já existe.

O critério de sucesso é objetivo e o senhor mesmo pode conferir: se o ORION tivesse rodado em 2025, ele teria sinalizado, com antecedência, chamados suficientes para evitar as três violações que separaram P2 de 75% para 100%? Hoje, olhando os dados retroativos, a resposta é sim — o modelo captura mais da metade das violações reais revisando apenas os seis casos de maior risco por dia. Isso é matemática sobre o histórico de vocês, não uma promessa sobre o futuro.

Se o teste confirmar isso em produção, o próximo passo natural é decidir, com o time financeiro, quanto vale em reais recuperar uma faixa de meta contratual — esse número está no contrato de vocês, não no meu. Eu trago o mecanismo que evita perder a faixa; quem sabe o valor exato dela em reais é a Locaweb.

O que eu preciso do senhor hoje não é uma assinatura. É uma decisão menor e mais fácil: autorizar que o time me dê acesso aos dados de incidente dos últimos 12 meses para rodar essa prova de conceito, sem custo de infraestrutura nesta fase, com resultado em três semanas.

Se funcionar sobre o passado de vocês, funciona sobre o futuro. E aí a conversa muda de "vale a pena testar" para "quanto isso já economizou".

Podemos marcar essa entrada de dados ainda esta semana?
