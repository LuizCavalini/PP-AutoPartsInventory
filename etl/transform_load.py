"""
transform_load.py — Lê os CSVs extraídos do "cabrito" (data/raw_csv/), normaliza
os dados para o schema de dim_peca / fato_vendas, e carrega no PostgreSQL.

ATENÇÃO: os nomes de arquivo/coluna abaixo (NOME_TABELA_PECAS, NOME_TABELA_VENDAS,
COLUNA_*) são placeholders. Depois de rodar etl/extract.py, abra os CSVs gerados,
identifique as tabelas reais de peças e de vendas/itens de OS, e ajuste as
constantes na seção CONFIGURAÇÃO abaixo. Isso é esperado e normal — bancos
legados de sistemas de balcão raramente têm nomes autoexplicativos.

USO:
    python etl/transform_load.py
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

# ───────────────────────── CONFIGURAÇÃO (ajustar após explorar os CSVs) ─────────────────────────
RAW_DIR = Path("data/raw_csv")

# Valores abaixo já funcionam com os dados fake gerados por scripts/gerar_dados_fake.py.
# Quando você tiver o arquivo .accdb real, troque pelos nomes encontrados no Passo 3
# (mdb-tables / mdb-schema) — ver docs/plano_fase1.md.
NOME_TABELA_PECAS = "PECAS.csv"
NOME_TABELA_VENDAS = "VENDAS.csv"

COLUNAS_PECAS = {
    # coluna_no_csv_legado: coluna_no_schema_novo
    "CODIGO": "codigo_legado",
    "DESCRICAO": "descricao",
    "CATEGORIA": "categoria",
    "FORNECEDOR": "fornecedor",
    "CUSTO": "custo_unitario",
}

COLUNAS_VENDAS = {
    "CODIGO_PECA": "codigo_legado",
    "DATA": "data_venda",
    "QUANTIDADE": "quantidade",
    "VALOR_UNIT": "valor_unitario",
    "NUM_OS": "id_os_legado",
}
# ──────────────────────────────────────────────────────────────────────────────────────────────


def get_engine():
    user = os.getenv("POSTGRES_USER")
    pwd = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB")
    url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    return create_engine(url)


def carregar_pecas(engine) -> None:
    caminho = RAW_DIR / NOME_TABELA_PECAS
    df = pd.read_csv(caminho)
    df = df.rename(columns=COLUNAS_PECAS)[list(COLUNAS_PECAS.values())]
    df = df.drop_duplicates(subset="codigo_legado")

    df.to_sql("dim_peca", engine, if_exists="append", index=False,
              method="multi", chunksize=500)
    print(f"dim_peca: {len(df)} peças carregadas.")


def carregar_vendas(engine) -> None:
    caminho = RAW_DIR / NOME_TABELA_VENDAS
    df = pd.read_csv(caminho)
    df = df.rename(columns=COLUNAS_VENDAS)

    # Resolve codigo_legado -> id_peca consultando a dim_peca já carregada
    dim_peca = pd.read_sql("SELECT id_peca, codigo_legado FROM dim_peca", engine)
    df = df.merge(dim_peca, on="codigo_legado", how="inner")

    df["data_venda"] = pd.to_datetime(df["data_venda"]).dt.date

    colunas_finais = ["id_peca", "data_venda", "quantidade", "valor_unitario", "id_os_legado"]
    df = df[colunas_finais]

    df.to_sql("fato_vendas", engine, if_exists="append", index=False,
              method="multi", chunksize=1000)
    print(f"fato_vendas: {len(df)} registros de venda carregados.")


def main() -> None:
    engine = get_engine()
    carregar_pecas(engine)
    carregar_vendas(engine)
    print("Carga concluída.")


if __name__ == "__main__":
    main()
