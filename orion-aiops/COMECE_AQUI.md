# Comece aqui

Guia prático do zero. Se você nunca abriu este projeto, siga na ordem.

**Estado atual:** o projeto existe apenas no `.zip` que você baixou. Ainda **não está
no GitHub** — a parte 3 deste guia resolve isso.

---

## Parte 1 · Preparar o ambiente (uma vez só)

### 1.1 Instale o que precisa

| Ferramenta | Onde baixar | Como saber se já tem |
|---|---|---|
| Python 3.11 ou 3.12 | python.org/downloads | `python --version` |
| Git | git-scm.com/downloads | `git --version` |
| VS Code (recomendado) | code.visualstudio.com | — |
| Power BI Desktop | Microsoft Store | — |

No Windows, ao instalar o Python, **marque a caixa "Add Python to PATH"**. É o erro
número um de quem depois não consegue rodar nada.

### 1.2 Extraia o projeto

Descompacte `orion-aiops.zip` num lugar sem espaços nem acentos no caminho.

* Bom: `C:\projetos\orion-aiops`
* Ruim: `C:\Users\Jéssica\Meus Documentos\Faculdade 2026\orion-aiops`

Caminhos com acento quebram algumas bibliotecas Python no Windows.

### 1.3 Abra o terminal na pasta

No VS Code: **Arquivo → Abrir Pasta** → selecione `orion-aiops` → **Terminal → Novo Terminal**.

Confirme que está no lugar certo:

```bash
dir        # Windows
ls         # Mac/Linux
```

Você deve ver `README.md`, `run_pipeline.py`, `src`, `notebooks`.

### 1.4 Crie o ambiente virtual

O ambiente virtual isola as bibliotecas deste projeto das do resto do computador.
Sem ele, instalar o LightGBM aqui pode quebrar outro trabalho seu.

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Deu certo quando aparece `(.venv)` no começo da linha do terminal.

> **Windows:** se der erro de "execução de scripts desabilitada", rode uma vez no
> PowerShell como administrador:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 1.5 Instale as bibliotecas

```bash
pip install -r requirements.txt
```

Leva 2 a 5 minutos. Vai instalar pandas, lightgbm, scikit-learn, fastapi e o resto.

### 1.6 Coloque o dataset no lugar

Copie o `LWDATASET.xlsx` para dentro de `data/raw/`.

```
orion-aiops/
└── data/
    └── raw/
        └── LWDATASET.xlsx   <-- aqui
```

**Sem esse arquivo nada roda.** Ele não vem no zip de propósito: é dado do cliente e
não deve ser versionado no GitHub. O `.gitignore` já está configurado para bloqueá-lo.

---

## Parte 2 · Rodar o projeto

### 2.1 O comando único

```bash
python run_pipeline.py
```

Isso é tudo. Em ~60 segundos ele executa as seis etapas na ordem correta e imprime o
progresso. Se terminar com a linha `Concluído em XX.Xs`, está tudo funcionando.

### 2.2 O que acontece nesses 60 segundos

```
[ 18s] BRONZE   lê o XLSX e salva em Parquet, sem alterar nada
         ↓       (src/orion/ingest.py)
[ 19s] SILVER   limpa, tipa, aplica as regras do dicionário, marca divergências
         ↓       (src/orion/transform.py)
[ 30s] GOLD     cria as tabelas de features e agregados
         ↓       (src/orion/features.py)
[ 56s] MODELOS  treina previsão de volume + risco de OLA, roda o backtest
         ↓       (src/orion/models/)
[ 56s] AGENTES  os 5 agentes leem a Gold e geram os sinais
         ↓       (src/orion/agents/ + orchestrator.py)
[ 57s] BI       exporta 15 CSVs para bi/exports/
```

Cada etapa só depende da anterior. É por isso que a ordem importa e por isso existe
o `run_pipeline.py` — para você não precisar decorar a sequência.

### 2.3 Rodar só um pedaço

Depois da primeira execução completa, você pode rodar partes:

```bash
python run_pipeline.py --etapa gold    # da camada Gold pra frente (pula ler o XLSX)
python run_pipeline.py --retreinar     # só modelos + agentes + BI
python run_pipeline.py --bi            # só regerar os CSVs do Power BI
```

Use `--retreinar` quando mexer em algum modelo, e `--bi` quando só quiser atualizar
o Power BI. Economiza tempo.

### 2.4 Os notebooks

Os notebooks **explicam** o que o pipeline faz. Eles são o material da apresentação e
da defesa técnica — não são necessários para o sistema funcionar.

```bash
jupyter notebook
```

Abre no navegador. Rode na ordem:

| Ordem | Notebook | O que mostra |
|---|---|---|
| 1º | `01_eda_entendimento_dados.ipynb` | Os 6 achados críticos, com gráficos |
| 2º | `02_feature_engineering.ipynb` | As features e a demonstração do vazamento de alvo |
| 3º | `03_modelo_volume_d1_d7.ipynb` | Previsão D+1/D+7 e backtest |
| 4º | `04_modelo_risco_ola.ipynb` | Risco de OLA e escolha do ponto de operação |
| 5º | `05_agentes_orquestracao.ipynb` | Os 5 agentes e o ciclo PDCA |

Eles já vêm **com os resultados salvos**, então você consegue ler tudo sem executar.
Para rodar de novo: no menu, **Kernel → Restart & Run All**.

> Rode o `run_pipeline.py` **antes** dos notebooks. Os notebooks 03, 04 e 05 leem as
> tabelas da camada Gold, que só existem depois do pipeline.

### 2.5 A API (opcional, mas vale pontos)

O Challenge dá 10% da nota para "link da aplicação funcionando".

```bash
uvicorn orion.api:app --reload --port 8000
```

Abra `http://localhost:8000/docs` no navegador. Aparece uma interface onde dá para
testar cada endpoint clicando. Ótimo para gravar no vídeo pitch.

Se der erro de módulo não encontrado:

```bash
# Windows
set PYTHONPATH=src
# Mac/Linux
export PYTHONPATH=src
```

---

## Parte 3 · Subir no GitHub

### 3.1 Configure o Git (uma vez na vida)

```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu@email.com"
```

### 3.2 Crie o repositório vazio no GitHub

1. Entre em github.com e clique no **+** no canto superior direito → **New repository**
2. Nome: `orion-aiops`
3. Visibilidade: **Public** — o Challenge pede link público do GitHub (20% da nota)
4. **Não marque** "Add a README file", "Add .gitignore" nem "Choose a license".
   O projeto já tem os três; marcar cria conflito.
5. **Create repository**

O GitHub mostra uma tela com comandos. Ignore-a e use os daqui.

### 3.3 Envie o projeto

No terminal, dentro da pasta `orion-aiops`:

```bash
git init
git add .
git commit -m "ORION AIOps - Sprint 2: arquitetura, modelos e agentes"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/orion-aiops.git
git push -u origin main
```

Troque `SEU-USUARIO` pelo seu usuário do GitHub.

**Sobre a senha:** o GitHub não aceita mais senha no `git push`. Quando pedir, use um
**token**: github.com → foto do perfil → Settings → Developer settings → Personal access
tokens → Tokens (classic) → Generate new token → marque o escopo `repo` → copie o token
e cole no lugar da senha. Guarde o token, ele não aparece de novo.

### 3.4 Confira o que subiu

Atualize a página do repositório. Você deve ver o README renderizado com as tabelas de
resultado. E confira duas coisas:

* a pasta `data/raw/` deve estar **vazia** (só com o `.gitkeep`) — o dataset não subiu, como deve ser
* a aba **Actions** vai mostrar o CI rodando os 37 testes automaticamente

### 3.5 Enviando alterações depois

Toda vez que mudar alguma coisa:

```bash
git add .
git commit -m "descreva o que mudou"
git push
```

### 3.6 Trabalhando em grupo

Cada integrante clona uma vez:

```bash
git clone https://github.com/SEU-USUARIO/orion-aiops.git
cd orion-aiops
python -m venv .venv
.venv\Scripts\activate          # ou source .venv/bin/activate
pip install -r requirements.txt
```

E copia o `LWDATASET.xlsx` para `data/raw/` — ele não vem pelo Git.

Antes de começar a mexer, sempre: `git pull`. Isso evita 90% dos conflitos.

---

## Parte 4 · O Power BI

O pipeline já gerou os 15 CSVs em `bi/exports/`. O passo a passo completo —
modelo estrela, todas as medidas DAX e as quatro páginas — está em
[`docs/GUIA_BI.md`](docs/GUIA_BI.md).

Resumo do caminho: **Obter dados → Pasta →** aponte para `bi/exports/`. Depois monte
os relacionamentos e cole as medidas DAX do guia.

Quando rodar `python run_pipeline.py --bi`, basta clicar em **Atualizar** no Power BI
que os números novos entram.

Salve o `.pbix` em `bi/dashboard_orion.pbix`. Esse arquivo **deve** ir para o Git —
ele é um dos entregáveis.

---

## Parte 5 · O mapa dos arquivos

### Você vai mexer nestes

| Arquivo | Para quê |
|---|---|
| `src/orion/config.py` | **Todas** as regras de negócio: limites de OLA, faixas de meta, limiares. Mudou uma regra? É aqui, e só aqui. |
| `README.md` | Preencher a tabela de integrantes com nome e RM em ordem alfabética |
| `notebooks/*.ipynb` | Material da apresentação; ajuste textos e gráficos como quiser |
| `bi/dashboard_orion.pbix` | Você ainda vai criar |

### Você provavelmente não vai mexer

| Arquivo | O que faz |
|---|---|
| `run_pipeline.py` | Orquestra as 6 etapas na ordem |
| `src/orion/ingest.py` | Lê o XLSX → camada Bronze |
| `src/orion/transform.py` | Limpeza e regras → camada Silver |
| `src/orion/features.py` | Features e agregados → camada Gold |
| `src/orion/models/volume_model.py` | Previsão D+1 e D+7 |
| `src/orion/models/ola_model.py` | Risco de violação de OLA |
| `src/orion/agents/*.py` | Os 5 agentes |
| `src/orion/orchestrator.py` | Ciclo PDCA que roda os agentes |
| `src/orion/api.py` | Endpoints HTTP |
| `tests/` | 37 testes das regras de negócio |

### Documentação — o que ler e quando

| Documento | Leia quando |
|---|---|
| `COMECE_AQUI.md` | Agora (é este) |
| `README.md` | Para a visão geral e os resultados |
| `docs/EDA_ACHADOS.md` | Antes de montar os slides — é o conteúdo da análise |
| `docs/DICIONARIO_ENTENDIMENTO.md` | Para defender as decisões técnicas na banca |
| `docs/ARQUITETURA.md` | Para o slide de arquitetura |
| `docs/GUIA_BI.md` | Ao construir o Power BI |
| `docs/ROTEIRO_PITCH.md` | Ao preparar a apresentação e o vídeo |

---

## Parte 6 · Quando der errado

| Erro | Causa | Solução |
|---|---|---|
| `python não é reconhecido` | Python fora do PATH | Reinstale marcando "Add Python to PATH" |
| `No module named orion` | Rodou de fora da pasta, ou sem PYTHONPATH | `cd` para a raiz do projeto; ou `set PYTHONPATH=src` |
| `No module named pandas` | Ambiente virtual não ativado | `.venv\Scripts\activate` e reinstale |
| `Arquivo de origem não encontrado` | Falta o dataset | Copie o `LWDATASET.xlsx` para `data/raw/` |
| `FileNotFoundError` em notebook 03/04/05 | Camada Gold não existe | Rode `python run_pipeline.py` primeiro |
| `Permission denied` no `git push` | Senha em vez de token | Gere um token pessoal (passo 3.3) |
| LightGBM não instala | Falta compilador/libgomp | Windows: instale o Visual C++ Redistributable. Linux: `sudo apt install libgomp1` |
| Notebook não abre | Jupyter fora do venv | Ative o venv e rode `pip install jupyter` |

Para confirmar que o ambiente está sadio a qualquer momento:

```bash
python -m pytest tests/ -v
```

Se os 37 testes passarem, a instalação está correta.

---

## Checklist antes de entregar

- [ ] `python run_pipeline.py` roda até o fim sem erro
- [ ] Os 5 notebooks abrem com os resultados visíveis
- [ ] `python -m pytest tests/` → 37 passed
- [ ] Repositório público no GitHub, com o README renderizando bonito
- [ ] `data/raw/` vazia no GitHub (dataset do cliente não versionado)
- [ ] Nomes e RMs preenchidos no README, em ordem alfabética
- [ ] `.pbix` criado, salvo em `bi/` e commitado
- [ ] `.pptx` da Sprint 2 no padrão `EC_Sprint_2_2TSCP_arqsolucao_ORION_<grupo>.pptx`
- [ ] Vídeo pitch no YouTube (público ou não listado) + arquivo `.TXT` com o link
- [ ] Tudo anexado no portal da FIAP, em **todas** as disciplinas
- [ ] Todos os integrantes com cópia completa dos arquivos
