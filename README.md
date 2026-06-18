# Gestão Inteligente de Estoque — [Nome da Autopeças]

Projeto pessoal de engenharia de dados aplicado a um negócio real: uma autopeças/oficina
que opera com um sistema legado em Microsoft Access (apelidado aqui de "cabrito").

O objetivo é construir, **sem alterar ou substituir o sistema legado**, uma camada de dados
moderna e satélite que extrai, organiza e analisa os dados de vendas/estoque para:

1. Identificar quais peças têm alto giro (Curva A) e quais são estoque morto (Curva C);
2. Calcular pontos de pedido e estoque de segurança por peça, automatizando decisões de compra;
3. (Fases futuras) Visualizar o fluxo operacional da oficina (Kanban de elevadores) e gerar
   alertas preditivos de manutenção recorrente.

## Por que isso importa

- **Gargalo de estoque**: dinheiro parado em peças sem saída, enquanto peças de giro alto
  faltam na hora em que o cliente está com o carro no elevador.
- **Gargalo operacional**: 8 vagas para 12 funcionários — o tempo de permanência do carro
  na vaga (muitas vezes esperando peça) limita a receita.

## Arquitetura (Fase 1)

```
┌─────────────────┐      cópia noturna       ┌──────────────────┐
│  Sistema Legado  │ ───────────────────────▶ │  Cópia local do   │
│  "Cabrito"       │   (fora do horário de    │  .mdb/.accdb       │
│  (MS Access)     │    pico, só leitura)     │                    │
└─────────────────┘                           └─────────┬──────────┘
                                                          │ mdbtools
                                                          ▼
                                                ┌──────────────────┐
                                                │  Extração (CSV)   │
                                                │  etl/extract.py   │
                                                └─────────┬──────────┘
                                                          │ pandas
                                                          ▼
                                                ┌──────────────────┐
                                                │ Transform + Load  │
                                                │ etl/transform_    │
                                                │ load.py           │
                                                └─────────┬──────────┘
                                                          │
                                                          ▼
                                                ┌──────────────────┐
                                                │ PostgreSQL        │
                                                │ (Docker)          │
                                                └─────────┬──────────┘
                                                          │
                                                          ▼
                                                ┌──────────────────┐
                                                │ Análise ABC + ROP │
                                                │ analysis/         │
                                                │ abc_analysis.py   │
                                                └──────────────────┘
```

**Decisão de arquitetura importante**: a extração usa `mdbtools` (Linux) em vez de
`pyodbc` + driver ODBC da Microsoft, porque o desenvolvimento é feito em Ubuntu
(dual boot) e o driver Access oficial só existe nativamente para Windows.

## Status

- [x] Diagnóstico do negócio e arquitetura definidos
- [ ] Cópia de teste do `.mdb` obtida
- [ ] Estrutura real das tabelas do "cabrito" mapeada (`mdb-schema`)
- [ ] ETL ajustado aos nomes reais de tabelas/colunas
- [ ] PostgreSQL rodando via Docker
- [ ] Análise Curva ABC + Ponto de Pedido gerando relatório

Detalhes do plano completo da Fase 1: [`docs/plano_fase1.md`](docs/plano_fase1.md).

## Stack

Python (pandas, SQLAlchemy, psycopg2) · mdbtools · PostgreSQL · Docker · (Fases futuras: React/Next.js, Tailwind)

## Como rodar

Ver passo a passo completo em [`docs/plano_fase1.md`](docs/plano_fase1.md#como-executar).
