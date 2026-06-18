# Plano da Fase 1 — Extração, Modelagem e Curva ABC com Ponto de Pedido

## 1. Diagnóstico do negócio

- **Diferencial competitivo**: ter a peça na hora, com o carro no elevador. Decisões de
  estoque não podem ignorar isso.
- **Gargalo de estoque**: capital parado em peças de baixo giro (Curva C), enquanto peças
  de alto giro (Curva A) podem faltar.
- **Gargalo operacional** (Fase 2): 8 vagas para 12 funcionários — o tempo de permanência
  de cada carro limita a receita, e parte desse tempo é espera por peça.

A Fase 1 ataca o primeiro gargalo. A Fase 2 (Kanban da oficina) vai cruzar os dois,
medindo quanto tempo de elevador é perdido especificamente por falta de peça.

## 2. Decisões de arquitetura e por quê

| Decisão | Alternativa descartada | Motivo |
|---|---|---|
| Não tocar no sistema legado ("cabrito") | Migrar tudo para um sistema novo | Risco operacional alto demais; o balcão depende dele todos os dias |
| Extrair com `mdbtools` (Linux) | `pyodbc` + driver ODBC Access | O driver oficial da Microsoft só funciona nativamente no Windows; como o desenvolvimento é em Ubuntu (dual boot), `mdbtools` evita essa dependência |
| Cópia do `.mdb` fora do horário de pico | Ler o arquivo em produção | Arquivos Access usam lock de arquivo; ler durante o expediente pode travar o sistema da loja |
| PostgreSQL em Docker, isolado | Instalar Postgres direto no SO | Mais fácil de resetar, versionar a config (`docker-compose.yml`) e não conflitar com nada já instalado |
| Modelo fato/dimensão simples | Tabelas soltas "como vieram" | Fica fácil de consultar tanto para a Curva ABC quanto para qualquer análise futura (BI, dashboards) |

## 3. Passo a passo — do zero até o relatório ABC

### Passo 0 — Pré-requisitos no Ubuntu

```bash
sudo apt update
sudo apt install -y mdbtools docker.io docker-compose-plugin python3-venv
sudo usermod -aG docker $USER   # depois disso, faça logout/login para valer
```

### Passo 1 — Criar o repositório no GitHub

No seu computador (não aqui no Claude — este projeto vai morar na sua máquina):

```bash
cd ~/projetos   # ou onde preferir
# (descompacte aqui o zip que o Claude te entregou, projeto-estoque-autopecas/)
cd projeto-estoque-autopecas
git init
git add .
git commit -m "chore: estrutura inicial do projeto (fase 1)"
```

Crie o repositório vazio no GitHub (pelo site, sem README/gitignore automático) e depois:

```bash
git remote add origin git@github.com:LuizCavalini/projeto-estoque-autopecas.git
git branch -M main
git push -u origin main
```

### Passo 2 (alternativa) — Testar com dados fake antes do arquivo real

Já validei esse pipeline de ponta a ponta com dados sintéticos. Pra reproduzir:

```bash
python scripts/gerar_dados_fake.py     # gera data/raw_csv/PECAS.csv e VENDAS.csv
docker compose up -d                    # sobe o PostgreSQL
python etl/transform_load.py            # carrega
python analysis/abc_analysis.py         # gera docs/relatorios/curva_abc_AAAA-MM-DD.md
```

Um relatório de exemplo já está em `docs/relatorios/curva_abc_2026-06-18.md` — vale
abrir pra ver o formato de saída antes de rodar com dado real.

> Quando o arquivo `.accdb` real chegar, os Passos 2 a 5 abaixo (com `extract.py` via
> `mdbtools`) substituem este atalho — é só trocar `MDB_FILE_PATH` no `.env` e ajustar
> `NOME_TABELA_PECAS`/`NOME_TABELA_VENDAS` em `transform_load.py`.

### Passo 2 — Obter uma cópia do banco legado

Esse passo é manual por enquanto e depende do computador da loja:

1. Fora do horário de pico (ex: fim do dia ou madrugada), copie o arquivo `.mdb`/`.accdb`
   do "cabrito" para um pendrive ou pasta de rede.
2. Traga essa cópia para o seu projeto, em `data/cabrito_copia.accdb`
   (essa pasta já está no `.gitignore` — **nunca** comitar dados reais do negócio).
3. Preencha o `.env` (copie de `.env.example`) apontando `MDB_FILE_PATH` para esse arquivo.

> Enquanto você não tem essa cópia em mãos, ainda dá para validar todo o resto do
> pipeline com dados sintéticos — me avise se quiser que eu gere um `.mdb` ou CSVs
> de exemplo para testar antes de ter o arquivo real.

### Passo 3 — Descobrir a estrutura real das tabelas

```bash
source .venv/bin/activate  # depois de criar com: python3 -m venv .venv
pip install -r requirements.txt

mdb-tables -1 data/cabrito_copia.accdb        # lista as tabelas
mdb-schema data/cabrito_copia.accdb            # mostra colunas e tipos de cada tabela
```

Anote aqui quais tabelas correspondem a:
- Cadastro de peças (provavelmente algo como `PECAS`, `PRODUTOS`, `ESTOQUE`)
- Vendas / itens de OS (provavelmente `VENDAS`, `ITENS_OS`, `MOVIMENTO`)

### Passo 4 — Extrair para CSV

```bash
python etl/extract.py
```

Isso gera um CSV por tabela em `data/raw_csv/`. Abra os CSVs das tabelas identificadas
no Passo 3 e confira os nomes reais das colunas (código da peça, descrição, data,
quantidade, valor unitário).

### Passo 5 — Ajustar o mapeamento e subir o PostgreSQL

1. Edite `etl/transform_load.py`: substitua `NOME_TABELA_PECAS`, `NOME_TABELA_VENDAS`
   e os dicionários `COLUNAS_PECAS` / `COLUNAS_VENDAS` pelos nomes reais encontrados.
2. Suba o banco:

```bash
docker compose up -d
docker compose logs -f postgres   # confirme que iniciou e aplicou sql/schema.sql
```

### Passo 6 — Carregar os dados

```bash
python etl/transform_load.py
```

### Passo 7 — Gerar a análise Curva ABC + Ponto de Pedido

```bash
python analysis/abc_analysis.py
```

Isso grava o resultado na tabela `resultado_abc` e gera um relatório em
`docs/relatorios/curva_abc_AAAA-MM-DD.md` — esse relatório pode (e deve) ser commitado
no GitHub como evidência do trabalho.

### Passo 8 — Comitar o progresso

```bash
git add docs/relatorios/ etl/ analysis/
git commit -m "feat: pipeline de extração e analise ABC com ponto de pedido"
git push
```

## 4. Metodologia da análise

**Curva ABC**: peças ordenadas por valor total vendido no período; Classe A = até 80%
do valor acumulado, B = até 95%, C = restante. É a forma clássica de identificar onde
focar reposição (A) e onde considerar reduzir/parar compra (C).

**Ponto de Pedido (ROP)**:

```
ROP = (demanda média diária × lead time em dias) + Estoque de Segurança
Estoque de Segurança = Z × desvio_padrão_diário × √(lead time em dias)
```

Z = 1,65 equivale a ~95% de nível de serviço (ajustável em `Z_NIVEL_SERVICO`).
`lead_time_dias` é configurável por peça em `dim_peca` (default 7 dias até termos
dado real do fornecedor).

**Limitação conhecida**: a demanda é calculada a partir do que foi *vendido*, não do
que foi *pedido*. Se um cliente pediu uma peça em falta e isso não foi registrado em
lugar nenhum, essa demanda perdida não aparece na análise — vale investigar se o
"cabrito" registra esse tipo de evento (Fase 2).

## 5. Próximos passos (Fase 2 e 3)

- Cruzar tempo de permanência no elevador (Kanban) com motivo "aguardando peça",
  para priorizar compra por impacto operacional, não só por valor financeiro.
- Evoluir Curva ABC para ABC/XYZ (cruzando volume com variabilidade de demanda).
- Alertas preditivos de manutenção recorrente via WhatsApp (reaproveitando a
  experiência já existente com automação via n8n).
