#!/usr/bin/env python3
"""Converte i Markdown italiani del percorso OCR in PDF, usando Pandoc e XeLaTeX.

Le formule OCR strutturalmente errate restano leggibili come codice e vengono
elencate in un rapporto; il PDF non viene presentato come matematicamente verificato.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MATH_ENV = re.compile(r'\\(begin|end)\{([^{}]+)\}')
PANDOC = shutil.which('pandoc') or '/opt/homebrew/bin/pandoc'
XELATEX = shutil.which('xelatex') or '/Library/TeX/texbin/xelatex'


def math_problem(formula: str) -> str | None:
    """Controlla solo la struttura TeX; non giudica la correttezza matematica."""
    depth = 0
    for index, char in enumerate(formula):
        if char in '{}':
            backslashes = 0
            pos = index - 1
            while pos >= 0 and formula[pos] == '\\':
                backslashes += 1
                pos -= 1
            if backslashes % 2:
                continue
            depth += 1 if char == '{' else -1
            if depth < 0:
                return 'parentesi graffa chiusa senza apertura'
    if depth:
        return 'parentesi graffe non bilanciate'
    stack = []
    for action, name in MATH_ENV.findall(formula):
        if action == 'begin':
            stack.append(name)
        elif not stack or stack.pop() != name:
            return f'ambiente LaTeX {name} chiuso in modo errato'
    if stack:
        return f'ambiente LaTeX {stack[-1]} non chiuso'
    return None


def prepare_math(node, warnings: list[str]):
    if isinstance(node, list):
        return [prepare_math(item, warnings) for item in node]
    if not isinstance(node, dict):
        return node
    if node.get('t') == 'Math':
        kind, source = node['c']
        # \left e \right cambiano solo la dimensione dei delimitatori; l'OCR
        # spesso ne perde uno, facendo fallire la compilazione dell'intero PDF.
        safe = re.sub(r'\\(?:left|right)(?=[^A-Za-z]|$)', '', source)
        problem = math_problem(safe)
        if problem:
            warnings.append(f'{problem}: {source[:160]}')
            return {'t': 'Span', 'c': [['', [], []], [
                {'t': 'Strong', 'c': [{'t': 'Str', 'c': '[Formula OCR da verificare]'}]},
                {'t': 'Space'},
                {'t': 'Code', 'c': [['', [], []], source]},
            ]]}
        return {'t': 'Math', 'c': [kind, safe]}
    return {key: prepare_math(value, warnings) for key, value in node.items()}


def export_one(markdown: Path, output: Path) -> tuple[int, list[str], str]:
    with tempfile.TemporaryDirectory(prefix='cartaocr_pdf_') as temporary:
        text = markdown.read_text(encoding='utf-8')
        first_page = True

        def page_break(match):
            nonlocal first_page
            if first_page:
                first_page = False
                return ''
            return '\n\n\\newpage\n\n'

        text = re.sub(r'<!-- pagina PDF \d+ -->', page_break, text)
        prepared_md = Path(temporary) / 'pages.md'
        prepared_md.write_text(text, encoding='utf-8')
        resources = f'--resource-path={markdown.parent}'
        source = subprocess.run([PANDOC, str(prepared_md), resources,
                                 '--from=markdown+tex_math_dollars+raw_tex', '--to=json'],
                                capture_output=True, text=True, check=True)
        warnings: list[str] = []
        document = prepare_math(json.loads(source.stdout), warnings)
        prepared = Path(temporary) / 'document.json'
        prepared.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
        command = [PANDOC, str(prepared), resources, '--from=json', f'--pdf-engine={XELATEX}', '--standalone',
                   '-V', 'geometry:margin=22mm', '-V', 'fontsize=11pt', '-V', 'papersize:a4', '-o', str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode, warnings, result.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description='Esporta in PDF i Markdown italiani del percorso OCR')
    parser.add_argument('cartella', type=Path)
    args = parser.parse_args()
    if not Path(PANDOC).is_file() or not Path(XELATEX).is_file():
        parser.error('servono Pandoc e XeLaTeX installati sul Mac')
    sources = sorted(args.cartella.glob('*_italiano.md'))
    if not sources:
        parser.error(f'nessun Markdown italiano in {args.cartella}')
    failed = False
    overview = ['AVVISI PDF - esportazione locale dei Markdown italiani.',
                'Le formule OCR non sono verificate contro il libro originale.',
                'Controlla anche RAPPORTO_TRADUZIONE.txt per le traduzioni difficili.', '']
    translation_report = args.cartella / 'RAPPORTO_TRADUZIONE.txt'
    if translation_report.is_file():
        report_text = translation_report.read_text(encoding='utf-8')
        failed_translations = re.search(r'livello_5_fallito:\s*(\d+)', report_text)
        if failed_translations and int(failed_translations.group(1)):
            overview += [f'ATTENZIONE: {failed_translations.group(1)} passaggi di traduzione falliti; '
                         'controlla il Markdown italiano e il rapporto.', '']
    for source in sources:
        output = source.with_suffix('.pdf')
        code, warnings, error = export_one(source, output)
        report = source.with_suffix('.pdf_avvisi.txt')
        lines = ['Esportazione PDF di Carta OCR.',
                 'Le formule OCR non sono verificate contro il libro originale.',
                 f'Formule con struttura LaTeX sospetta mostrate come testo: {len(warnings)}', ''] + warnings
        if code:
            failed = True
            output.unlink(missing_ok=True)
            lines += ['', 'ERRORE DI COMPILAZIONE:', error[-3000:]]
            print(f'PDF non creato: {source.name}\n{error[-1200:]}', file=sys.stderr)
        else:
            print(f'PDF creato: {output}', flush=True)
        report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        overview += [f'{source.name}: {"PDF non creato" if code else "PDF creato"}; '
                     f'{len(warnings)} formule OCR mostrate come testo.', f'Dettagli: {report.name}', '']
    (args.cartella / 'AVVISI_PDF.txt').write_text('\n'.join(overview), encoding='utf-8')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
