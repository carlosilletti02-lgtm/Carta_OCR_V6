#!/usr/bin/env python3
"""Percorso OCR alternativo, isolato dal risultato DeepSeek.

Legge il rapporto della fase 2 e invia a MiniCPM solo le pagine con errori
verificabili. Richiede un server Ollama locale con MiniCPM-OCR 1.0 gia' caricato.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
TRIGGER = ('eq_ritaglio', 'blocchi_con_differenze', 'inline_latex_sospetto',
           'formule_inline_sospette', 'parole_pdf_mancanti', 'parole_non_risolte')


def local_opener():
    """Non usare proxy di sistema per la connessione al server sul Mac."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def normalize_math(text: str) -> str:
    """Adatta i delimitatori LaTeX al lettore della fase 3."""
    text = re.sub(r'\\\[\s*(.*?)\s*\\\]', lambda m: '$$\n' + m.group(1) + '\n$$', text, flags=re.S)
    text = re.sub(r'\$\$\s*(.*?)\s*\$\$', lambda m: '$$\n' + m.group(1) + '\n$$', text, flags=re.S)
    return re.sub(r'\\\((.*?)\\\)', lambda m: '$' + m.group(1) + '$', text, flags=re.S)


def pages_to_retry(report: dict) -> list[tuple[str, list[str]]]:
    """Restituisce le pagine problematiche e i motivi; ignora il totale."""
    selected = []
    for page, counts in report.items():
        if page == 'TOTALE' or not isinstance(counts, dict):
            continue
        reasons = [f'{key}={counts[key]}' for key in TRIGGER if counts.get(key, 0) > 0]
        if reasons:
            selected.append((page, reasons))
    return selected


def pdf_pages(work: Path) -> dict[str, tuple[Path, int]]:
    result = {}
    for path in work.glob('*_p[0-9][0-9][0-9][0-9].json'):
        meta = json.loads(path.read_text(encoding='utf-8'))
        pdf = Path(meta['pdf'])
        if not pdf.is_file():
            on_desktop = Path.home() / 'Desktop' / pdf.name
            if on_desktop.is_file():
                pdf = on_desktop
            else:
                moved = sorted(pdf.parent.glob(f'*/{pdf.name}'))
                if len(moved) == 1:
                    pdf = moved[0]
        result[f'{pdf.stem}_p{int(meta["pagina"])}'] = (pdf, int(meta['pagina']))
    return result


def model_is_downloaded(endpoint: str, model: str) -> bool:
    """Impedisce l'invio del PDF se il modello non e' gia' presente sul Mac."""
    address = urlsplit(endpoint)
    tags_url = f'{address.scheme}://{address.netloc}/api/tags'
    with local_opener().open(tags_url, timeout=10) as response:
        names = [entry['name'] for entry in json.load(response).get('models', [])]
    return model in names or f'{model}:latest' in names


def recognize(pdf: Path, page_no: int, endpoint: str, model: str, dpi: int) -> str:
    with pymupdf.open(pdf) as document:
        image = document[page_no - 1].get_pixmap(dpi=dpi, alpha=False).tobytes('png')
    payload = json.dumps({
        'model': model,
        'prompt': ('Read this German document page exactly. Return Markdown in reading order. '
                   'Preserve German words, numbers and mathematical formulas as LaTeX. '
                   'Do not translate or invent missing text.'),
        'images': [base64.b64encode(image).decode('ascii')],
        'stream': False,
    }).encode('utf-8')
    request = urllib.request.Request(endpoint, data=payload, headers={'Content-Type': 'application/json'})
    with local_opener().open(request, timeout=300) as response:
        data = json.load(response)
    if data.get('done_reason') == 'length':
        raise ValueError('uscita MiniCPM troncata')
    text = data.get('response', '').strip()
    if not text:
        raise ValueError('MiniCPM ha restituito una pagina vuota')
    return normalize_math(text) + '\n'


def unload(endpoint: str, model: str) -> None:
    """Libera la memoria di MiniCPM prima che venga caricato Qwen."""
    payload = json.dumps({'model': model, 'prompt': '', 'keep_alive': 0, 'stream': False}).encode('utf-8')
    request = urllib.request.Request(endpoint, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with local_opener().open(request, timeout=20):
            pass
    except (OSError, urllib.error.URLError):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description='OCR di recupero su pagine segnalate dalla verifica')
    parser.add_argument('uscita', type=Path, help='cartella prodotta dalla fase 2')
    parser.add_argument('--cartella', type=Path, default=HERE / 'lavoro')
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434/api/generate')
    parser.add_argument('--modello', default='openbmb/minicpm-ocr1.0')
    parser.add_argument('--dpi', type=int, default=200)
    args = parser.parse_args()
    address = urlsplit(args.endpoint)
    if address.scheme != 'http' or address.hostname not in {'127.0.0.1', 'localhost', '::1'} or address.path != '/api/generate':
        parser.error('il recupero accetta solo un server HTTP locale')
    report = json.loads((args.uscita / 'rapporto.json').read_text(encoding='utf-8'))
    selected = pages_to_retry(report)
    if not selected:
        print('Nessuna pagina problematica: MiniCPM non viene avviato.')
        return 0
    try:
        downloaded = model_is_downloaded(args.endpoint, args.modello)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        print(f'Server Ollama locale non disponibile: {exc}')
        return 2
    if not downloaded:
        print(f'Modello non scaricato in locale: {args.modello}')
        return 2
    source = pdf_pages(args.cartella)
    dest = args.uscita / 'recupero_minicpm'
    dest.mkdir(exist_ok=True)
    results = []
    failures = 0
    for tag, reasons in selected:
        if tag not in source:
            failures += 1
            results.append(f'{tag}: PDF originale non trovato nella cache della fase 1')
            continue
        pdf, number = source[tag]
        output = dest / f'{pdf.stem}_p{number:04d}.md'
        try:
            if not pdf.is_file():
                raise FileNotFoundError(f'PDF originale non trovato: {pdf}')
            if not output.exists():
                output.write_text(recognize(pdf, number, args.endpoint, args.modello, args.dpi), encoding='utf-8')
            results.append(f'{pdf.name} p.{number}: OCR alternativo disponibile; motivo: {", ".join(reasons)}')
        except (OSError, ValueError, urllib.error.URLError) as exc:
            failures += 1
            results.append(f'{pdf.name} p.{number}: recupero non riuscito: {exc}')
    unload(args.endpoint, args.modello)
    (dest / 'RAPPORTO_RECUPERO.txt').write_text('\n'.join(results) + '\n', encoding='utf-8')
    print('\n'.join(results))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
