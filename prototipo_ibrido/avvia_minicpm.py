#!/usr/bin/env python3
"""MiniCPM-OCR come percorso autonomo: PDF -> Markdown tedesco -> Qwen italiano."""
from __future__ import annotations

import argparse
from datetime import datetime
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf

from recupero_minicpm import model_is_downloaded, recognize, unload

HERE = Path(__file__).resolve().parent
ENDPOINT = 'http://127.0.0.1:11434/api/generate'
MODEL = 'openbmb/minicpm-ocr1.0'


def main() -> int:
    parser = argparse.ArgumentParser(description='OCR MiniCPM e traduzione locale con Qwen')
    parser.add_argument('--pdf', required=True, type=Path)
    parser.add_argument('--da', type=int, required=True)
    parser.add_argument('--a', type=int, required=True)
    parser.add_argument('--lingua', default='deu')
    args = parser.parse_args()
    pdf = args.pdf.expanduser().resolve()
    if not pdf.is_file():
        parser.error(f'PDF non trovato: {pdf}')
    with pymupdf.open(pdf) as document:
        total = len(document)
    if not 1 <= args.da <= args.a <= total:
        parser.error(f'pagine non valide: il PDF ha {total} pagine')
    try:
        if not model_is_downloaded(ENDPOINT, MODEL):
            parser.error(f'MiniCPM non e\' scaricato in locale: {MODEL}')
    except OSError as exc:
        parser.error(f'Ollama locale non disponibile: {exc}. Avvia OLLAMA_NO_CLOUD=1 ollama serve')

    out = HERE / 'uscita' / f'{pdf.stem[:40]}_minicpm_p{args.da}-{args.a}_{datetime.now():%Y%m%d_%H%M%S}'
    out.mkdir(parents=True, exist_ok=False)
    print(f'Risultati in: {out}', flush=True)
    try:
        for number in range(args.da, args.a + 1):
            text = recognize(pdf, number, ENDPOINT, MODEL, 200)
            (out / f'{pdf.stem}_p{number:04d}.md').write_text(text, encoding='utf-8')
            print(f'Pagina PDF {number}/{args.a}: MiniCPM completato', flush=True)
    finally:
        unload(ENDPOINT, MODEL)
    command = [sys.executable, '-B', str(HERE / 'fase3_traduci.py'), str(out), '--lingua', args.lingua,
               '--cache', str(out / 'cache_qwen.json')]
    sandbox = shutil.which('sandbox-exec')
    if sandbox:
        command = [sandbox, '-p', '(version 1)(allow default)(deny network*)'] + command
    code = subprocess.run(command, cwd=HERE).returncode
    if code:
        return code
    return subprocess.run([sys.executable, '-B', str(HERE / 'esporta_pdf.py'), str(out)], cwd=HERE).returncode


if __name__ == '__main__':
    raise SystemExit(main())
