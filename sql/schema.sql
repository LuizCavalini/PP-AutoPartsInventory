-- Schema inicial do banco analítico (Fase 1)
-- Modelo simples fato/dimensão. Os nomes de colunas aqui são um ponto de partida
-- razoável; ajuste depois de rodar `mdb-schema` no banco legado real (ver
-- docs/plano_fase1.md, seção "Passo 3").

CREATE TABLE IF NOT EXISTS dim_peca (
    id_peca         SERIAL PRIMARY KEY,
    codigo_legado   TEXT UNIQUE NOT NULL,   -- código/SKU como está no "cabrito"
    descricao       TEXT NOT NULL,
    categoria       TEXT,
    fornecedor      TEXT,
    custo_unitario  NUMERIC(12,2),
    lead_time_dias  INTEGER DEFAULT 7,      -- prazo médio de entrega do fornecedor
                                             -- (default conservador até termos dado real)
    ativo           BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS fato_vendas (
    id_venda        SERIAL PRIMARY KEY,
    id_peca         INTEGER NOT NULL REFERENCES dim_peca(id_peca),
    data_venda      DATE NOT NULL,
    quantidade      NUMERIC(12,2) NOT NULL,
    valor_unitario  NUMERIC(12,2) NOT NULL,
    valor_total     NUMERIC(12,2) GENERATED ALWAYS AS (quantidade * valor_unitario) STORED,
    id_os_legado    TEXT                    -- referência à OS/venda original, se existir
);

CREATE INDEX IF NOT EXISTS idx_fato_vendas_peca ON fato_vendas(id_peca);
CREATE INDEX IF NOT EXISTS idx_fato_vendas_data ON fato_vendas(data_venda);

-- Tabela de saída da análise ABC + Ponto de Pedido (escrita por analysis/abc_analysis.py)
CREATE TABLE IF NOT EXISTS resultado_abc (
    id_peca             INTEGER PRIMARY KEY REFERENCES dim_peca(id_peca),
    qtd_total_periodo   NUMERIC(12,2),
    valor_total_periodo NUMERIC(12,2),
    pct_acumulado       NUMERIC(5,2),
    classe_abc          CHAR(1),            -- 'A', 'B' ou 'C'
    demanda_media_dia   NUMERIC(12,4),
    desvio_padrao_dia   NUMERIC(12,4),
    estoque_seguranca   NUMERIC(12,2),
    ponto_de_pedido     NUMERIC(12,2),
    atualizado_em       TIMESTAMP DEFAULT now()
);
