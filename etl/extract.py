"""
extract.py — Extrai tabelas de uma CÓPIA local do banco legado "cabrito" (.mdb/.accdb)
para arquivos CSV, usando mdbtools (Linux), sem precisar de driver ODBC da Microsoft.

PRÉ-REQUISITOS (rodar uma vez no Ubuntu):
    sudo apt update && sudo apt install -y mdbtools

IMPORTANTE:
    Este script espera uma CÓPIA do arquivo, nunca o original em produção.
    A cópia deve ser feita fora do horário de pico (ex: de madrugada), por um
    simples copy/robocopy no computador da loja, e depois transferida para
    ./data/ (pendrive, rede local, etc.). Esse passo manual/agendado ainda
    não está automatizado aqui — ver docs/plano_fase1.md.

USO:
    python etl/extract.py
    (lê o caminho do arquivo em MDB_FILE_PATH, no .env)
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MDB_FILE_PATH = os.getenv("MDB_FILE_PATH")
OUTPUT_DIR = Path("data/raw_csv")


def checar_mdbtools() -> None:
    """Garante que o mdbtools está instalado antes de seguir."""
    try:
        subprocess.run(["mdb-ver", MDB_FILE_PATH], capture_output=True, check=False)
    except FileNotFoundError:
        sys.exit(
            "mdbtools não encontrado. Instale com:\n"
            "    sudo apt update && sudo apt install -y mdbtools"
        )


def listar_tabelas(mdb_path: str) -> list[str]:
    """Lista as tabelas do banco Access (uma por linha)."""
    resultado = subprocess.run(
        ["mdb-tables", "-1", mdb_path], capture_output=True, text=True, check=True
    )
    tabelas = [t.strip() for t in resultado.stdout.splitlines() if t.strip()]
    return tabelas


def exportar_tabela(mdb_path: str, tabela: str, destino: Path) -> None:
    """Exporta uma tabela específica para CSV via mdb-export."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        subprocess.run(
            ["mdb-export", mdb_path, tabela], stdout=f, check=True
        )
    print(f"  -> {tabela}: {destino}")


def main() -> None:
    if not MDB_FILE_PATH:
        sys.exit("Defina MDB_FILE_PATH no arquivo .env (veja .env.example).")
    if not Path(MDB_FILE_PATH).exists():
        sys.exit(
            f"Arquivo não encontrado: {MDB_FILE_PATH}\n"
            "Você já tem uma cópia do .mdb/.accdb do 'cabrito'? Coloque em ./data/."
        )

    checar_mdbtools()

    print(f"Lendo tabelas de: {MDB_FILE_PATH}")
    tabelas = listar_tabelas(MDB_FILE_PATH)
    print(f"Tabelas encontradas ({len(tabelas)}): {tabelas}")

    for tabela in tabelas:
        destino = OUTPUT_DIR / f"{tabela}.csv"
        exportar_tabela(MDB_FILE_PATH, tabela, destino)

    print(
        "\nExtração concluída. Próximo passo: abrir os CSVs em data/raw_csv/ e "
        "identificar quais correspondem a vendas/itens/peças — depois ajustar "
        "etl/transform_load.py com os nomes reais de tabelas e colunas."
    )


if __name__ == "__main__":
    main()
