"""
Log de eventos da simulação em arquivo (logs/<protocolo>.log).

O motor abre o arquivo no início de cada execução e fecha no fim; os nós só
chamam `write`. Sem arquivo aberto, `write` não faz nada.
"""
from pathlib import Path
from typing import Optional, TextIO

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

_file: Optional[TextIO] = None


def open_log(name: str, header: str) -> Path:
    global _file
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"{name}.log"
    _file = open(path, "w", encoding="utf-8", buffering=1)  # por linha: dá para acompanhar ao vivo
    _file.write(header + "\n\n")
    return path


def write(line: str) -> None:
    if _file is not None:
        _file.write(line + "\n")


def close_log(footer: str = "") -> None:
    global _file
    if _file is not None:
        if footer:
            _file.write("\n" + footer + "\n")
        _file.close()
        _file = None
