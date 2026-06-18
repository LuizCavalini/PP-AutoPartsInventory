"""
gerar_dados_fake.py — Gera CSVs sintéticos no MESMO formato que esperamos do
mdb-export real (mesmas colunas que etl/transform_load.py já está configurado
para ler), para validar todo o pipeline (carga + Curva ABC + Ponto de Pedido)
antes de ter acesso ao arquivo .accdb real do "cabrito".

Quando você tiver o arquivo real, este script deixa de ser necessário — ele
existe só para teste/demonstração (inclusive é um bom item pra mostrar no
GitHub: evidencia de que você testou a lógica antes de plugar no dado real).

USO:
    python scripts/gerar_dados_fake.py
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

OUTPUT_DIR = Path("data/raw_csv")
DIAS_HISTORICO = 180

CATEGORIAS = ["Motor", "Freios", "Suspensão", "Elétrica", "Filtros", "Arrefecimento"]
FORNECEDORES = ["Bosch", "NGK", "Cofap", "Fras-le", "Nakata", "Magneti Marelli"]

# (descrição, categoria, custo_unitario, popularidade)
# popularidade alta = vende muito (vira Classe A), baixa = quase não vende (Classe C)
PECAS_BASE = [
    ("Filtro de Óleo", "Filtros", 18.0, 30),
    ("Filtro de Ar", "Filtros", 25.0, 25),
    ("Pastilha de Freio Diant.", "Freios", 65.0, 28),
    ("Óleo Motor 5W30 (litro)", "Motor", 32.0, 35),
    ("Vela de Ignição", "Elétrica", 22.0, 20),
    ("Correia Dentada", "Motor", 80.0, 8),
    ("Amortecedor Diant.", "Suspensão", 210.0, 4),
    ("Bateria 60Ah", "Elétrica", 320.0, 6),
    ("Disco de Freio Diant.", "Freios", 140.0, 10),
    ("Filtro de Combustível", "Filtros", 28.0, 15),
    ("Radiador", "Arrefecimento", 380.0, 2),
    ("Bomba de Água", "Arrefecimento", 150.0, 3),
    ("Kit Embreagem", "Motor", 450.0, 1),
    ("Terminal de Direção", "Suspensão", 70.0, 5),
    ("Sensor de Oxigênio", "Elétrica", 180.0, 3),
    ("Mangueira do Radiador", "Arrefecimento", 45.0, 6),
    ("Pastilha de Freio Tras.", "Freios", 58.0, 18),
    ("Coxim do Motor", "Motor", 95.0, 4),
    ("Rolamento de Roda", "Suspensão", 85.0, 7),
    ("Vela de Aquecimento (Diesel)", "Elétrica", 38.0, 2),
    ("Correia Alternador", "Motor", 35.0, 9),
    ("Junta do Cabeçote", "Motor", 120.0, 1),
    ("Lâmpada Farol H4", "Elétrica", 15.0, 22),
    ("Amortecedor Tras.", "Suspensão", 195.0, 3),
    ("Tensor da Correia", "Motor", 55.0, 5),
]


def gerar_pecas() -> pd.DataFrame:
    registros = []
    for i, (descricao, categoria, custo, popularidade) in enumerate(PECAS_BASE, start=1):
        registros.append({
            "CODIGO": f"P{i:04d}",
            "DESCRICAO": descricao,
            "CATEGORIA": categoria,
            "FORNECEDOR": random.choice(FORNECEDORES),
            "CUSTO": custo,
            "_popularidade": popularidade,  # usado só pra gerar vendas, não vai pro CSV final
        })
    return pd.DataFrame(registros)


def gerar_vendas(pecas: pd.DataFrame) -> pd.DataFrame:
    hoje = date.today()
    registros = []
    num_os = 1000

    for dia_offset in range(DIAS_HISTORICO):
        dia = hoje - timedelta(days=dia_offset)
        for _, peca in pecas.iterrows():
            # probabilidade de vender essa peça hoje, proporcional à popularidade
            prob_venda = peca["_popularidade"] / 100
            if random.random() < prob_venda:
                quantidade = random.choice([1, 1, 1, 2, 2, 3])
                margem = random.uniform(1.3, 2.2)
                valor_unit = round(peca["CUSTO"] * margem, 2)
                num_os += 1
                registros.append({
                    "CODIGO_PECA": peca["CODIGO"],
                    "DATA": dia.isoformat(),
                    "QUANTIDADE": quantidade,
                    "VALOR_UNIT": valor_unit,
                    "NUM_OS": f"OS-{num_os}",
                })

    return pd.DataFrame(registros)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pecas = gerar_pecas()
    vendas = gerar_vendas(pecas)

    pecas.drop(columns=["_popularidade"]).to_csv(OUTPUT_DIR / "PECAS.csv", index=False)
    vendas.to_csv(OUTPUT_DIR / "VENDAS.csv", index=False)

    print(f"Geradas {len(pecas)} peças e {len(vendas)} registros de venda "
          f"({DIAS_HISTORICO} dias de histórico) em {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
