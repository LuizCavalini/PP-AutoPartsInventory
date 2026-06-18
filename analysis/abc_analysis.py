"""
abc_analysis.py — Classifica peças em Curva A/B/C por valor de venda e calcula
ponto de pedido (ROP) + estoque de segurança por peça, com base no histórico
em fato_vendas. Grava o resultado na tabela resultado_abc e gera um relatório
em Markdown em docs/relatorios/.

Metodologia:
- Curva ABC por valor total vendido no período (Pareto: A = até 80% acumulado,
  B = até 95%, C = restante). É um ponto de partida — pondera por valor
  financeiro, não por criticidade operacional (isso é uma extensão de Fase 2,
  ver docs/plano_fase1.md).
- Ponto de Pedido = (demanda média diária × lead time em dias) + estoque de segurança
- Estoque de Segurança = z × desvio_padrao_diario × sqrt(lead_time_dias)
  (z=1.65 para ~95% de nível de serviço; ajustável)

USO:
    python analysis/abc_analysis.py
"""

import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

Z_NIVEL_SERVICO = 1.65  # ~95% de nível de serviço. Para 90% use 1.28; para 99% use 2.33.
JANELA_ANALISE_DIAS = 365  # quantos dias de histórico considerar


def get_engine():
    user = os.getenv("POSTGRES_USER")
    pwd = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB")
    return create_engine(f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}")


def carregar_vendas(engine) -> pd.DataFrame:
    data_corte = date.today() - timedelta(days=JANELA_ANALISE_DIAS)
    query = text("""
        SELECT id_peca, data_venda, quantidade, valor_total
        FROM fato_vendas
        WHERE data_venda >= :data_corte
    """)
    return pd.read_sql(query, engine, params={"data_corte": data_corte})


def classificar_abc(vendas: pd.DataFrame) -> pd.DataFrame:
    por_peca = (
        vendas.groupby("id_peca")
        .agg(qtd_total_periodo=("quantidade", "sum"),
             valor_total_periodo=("valor_total", "sum"))
        .sort_values("valor_total_periodo", ascending=False)
    )

    por_peca["pct_acumulado"] = (
        por_peca["valor_total_periodo"].cumsum() / por_peca["valor_total_periodo"].sum() * 100
    )

    def classe(pct):
        if pct <= 80:
            return "A"
        elif pct <= 95:
            return "B"
        return "C"

    por_peca["classe_abc"] = por_peca["pct_acumulado"].apply(classe)
    return por_peca.reset_index()


def calcular_demanda_diaria(vendas: pd.DataFrame) -> pd.DataFrame:
    """Demanda média e desvio-padrão diários por peça, considerando dias sem venda como zero."""
    primeiro_dia = vendas["data_venda"].min()
    ultimo_dia = vendas["data_venda"].max()
    todos_os_dias = pd.date_range(primeiro_dia, ultimo_dia, freq="D")

    diario = (
        vendas.groupby(["id_peca", "data_venda"])["quantidade"]
        .sum()
        .unstack(fill_value=0)
    )
    # garante que todos os dias do período apareçam, mesmo sem venda
    diario = diario.reindex(columns=todos_os_dias, fill_value=0)

    estatisticas = diario.T.agg(["mean", "std"]).T.reset_index()
    estatisticas.columns = ["id_peca", "demanda_media_dia", "desvio_padrao_dia"]
    estatisticas["desvio_padrao_dia"] = estatisticas["desvio_padrao_dia"].fillna(0)
    return estatisticas


def calcular_ponto_de_pedido(df: pd.DataFrame, lead_times: pd.DataFrame) -> pd.DataFrame:
    df = df.merge(lead_times, on="id_peca", how="left")
    df["lead_time_dias"] = df["lead_time_dias"].fillna(7)

    df["estoque_seguranca"] = (
        Z_NIVEL_SERVICO * df["desvio_padrao_dia"] * (df["lead_time_dias"] ** 0.5)
    )
    df["ponto_de_pedido"] = (
        df["demanda_media_dia"] * df["lead_time_dias"] + df["estoque_seguranca"]
    )
    return df


def gravar_resultado(engine, df: pd.DataFrame) -> None:
    colunas_tabela = [
        "id_peca", "qtd_total_periodo", "valor_total_periodo", "pct_acumulado",
        "classe_abc", "demanda_media_dia", "desvio_padrao_dia",
        "estoque_seguranca", "ponto_de_pedido",
    ]
    df_gravar = df[colunas_tabela]

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM resultado_abc"))
        df_gravar.to_sql("resultado_abc", conn, if_exists="append", index=False, method="multi")


def gerar_relatorio_markdown(df: pd.DataFrame, vendas_brutas: pd.DataFrame, engine) -> None:
    pecas = pd.read_sql("SELECT id_peca, codigo_legado, descricao FROM dim_peca", engine)
    relatorio = df.merge(pecas, on="id_peca", how="left")
    relatorio = relatorio.sort_values("valor_total_periodo", ascending=False)

    n_a = (relatorio["classe_abc"] == "A").sum()
    n_b = (relatorio["classe_abc"] == "B").sum()
    n_c = (relatorio["classe_abc"] == "C").sum()
    valor_total = relatorio["valor_total_periodo"].sum()

    linhas = [
        f"# Relatório Curva ABC — gerado em {date.today().isoformat()}",
        "",
        f"Período analisado: últimos {JANELA_ANALISE_DIAS} dias.",
        f"Faturamento total considerado: R$ {valor_total:,.2f}",
        "",
        f"- **Classe A** (alto giro, repor sempre): {n_a} peças",
        f"- **Classe B**: {n_b} peças",
        f"- **Classe C** (estoque morto, candidatas a parar de comprar): {n_c} peças",
        "",
        "## Top 20 peças — Classe A",
        "",
        "| Código | Descrição | Valor no período | % acumulado | Ponto de Pedido |",
        "|---|---|---|---|---|",
    ]

    for _, row in relatorio[relatorio["classe_abc"] == "A"].head(20).iterrows():
        linhas.append(
            f"| {row['codigo_legado']} | {row['descricao']} | "
            f"R$ {row['valor_total_periodo']:,.2f} | {row['pct_acumulado']:.1f}% | "
            f"{row['ponto_de_pedido']:.1f} un |"
        )

    linhas += [
        "",
        "## Peças Classe C (candidatas a redução de estoque)",
        "",
        "| Código | Descrição | Valor no período |",
        "|---|---|---|",
    ]
    for _, row in relatorio[relatorio["classe_abc"] == "C"].head(30).iterrows():
        linhas.append(
            f"| {row['codigo_legado']} | {row['descricao']} | R$ {row['valor_total_periodo']:,.2f} |"
        )

    destino = Path("docs/relatorios") / f"curva_abc_{date.today().isoformat()}.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas), encoding="utf-8")
    print(f"Relatório gerado em: {destino}")


def main() -> None:
    engine = get_engine()
    vendas = carregar_vendas(engine)

    if vendas.empty:
        print("Nenhuma venda encontrada em fato_vendas no período. Rode a carga (transform_load.py) antes.")
        return

    abc = classificar_abc(vendas)
    demanda = calcular_demanda_diaria(vendas)
    lead_times = pd.read_sql("SELECT id_peca, lead_time_dias FROM dim_peca", engine)

    resultado = abc.merge(demanda, on="id_peca", how="left")
    resultado = calcular_ponto_de_pedido(resultado, lead_times)

    gravar_resultado(engine, resultado)
    gerar_relatorio_markdown(resultado, vendas, engine)
    print("Análise ABC + Ponto de Pedido concluída.")


if __name__ == "__main__":
    main()
