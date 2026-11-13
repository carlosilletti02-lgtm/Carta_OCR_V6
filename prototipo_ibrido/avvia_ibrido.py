#!/usr/bin/env python3
"""Ibrido (prototipo): fase 1 (DeepSeek-OCR 2) e poi fase 2 (assemblaggio verificato), una dopo l'altra.

Le due fasi sono processi SEPARATI: la fase 1 termina (e il modello esce dalla memoria) prima che parta la fase 2, che
non usa nessun modello. Entrambe girano con la rete bloccata a livello di sistema (sandbox-exec).
Poi (fase 3) parte Qwen, in un terzo processo, e traduce il Markdown verificato in italiano. Con --solo-lettura ci si ferma prima.

Uso (dalla cartella 05_V6_in_sviluppo/prototipo_ibrido):
  PY="$HOME/Library/Application Support/CartaOCR/runtime/bin/python3"
  "$PY" -B avvia_ibrido.py 978-3-658-50521-9.pdf:30-35 1783639.pdf:25
Pagine = numeri del lettore PDF. I PDF si cercano in ~/Desktop/manuali in tedesco/ se non si da' il percorso intero.
Risultato: uscita/<data ora>/  (un .md per pagina, PDF italiano, formule/ e figure/ con i ritagli, rapporti da leggere).
La cache della fase 1 e' in lavoro/: rilanciare sulle stesse pagine non rilegge con DeepSeek (--rifai per forzare).
"""
import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = ['sandbox-exec', '-p', '(version 1)(allow default)(deny network*)']


def run(cmd: list[str], label: str, sandboxed: bool = True) -> int:
    if sandboxed and shutil.which('sandbox-exec'):
        cmd = SANDBOX + cmd
    elif sandboxed:
        print('Attenzione: sandbox-exec non disponibile; il programma comunque non usa Internet.')
    print(f'\n=== {label} ===', flush=True)
    return subprocess.run(cmd, cwd=str(HERE)).returncode


def main() -> int:
    ap = argparse.ArgumentParser(description='Ibrido: DeepSeek-OCR 2 + verifica contro il PDF')
    ap.add_argument('pagine', nargs='+', metavar='FILE.pdf:PAGINE')
    ap.add_argument('--cartella', default='lavoro')
    ap.add_argument('--lingua', default='deu', help='lingua del libro (deve esistere lingua_<codice>.json nella cartella sopra)')
    ap.add_argument('--solo-lettura', action='store_true', help='ferma dopo la fase 2: Markdown verificato, senza tradurre')
    ap.add_argument('--rifai', action='store_true', help='rilegge con DeepSeek anche le pagine gia\' in cache')
    ap.add_argument('--senza-recupero', action='store_true', help='non usare MiniCPM sulle pagine segnalate')
    args = ap.parse_args()
    out = HERE / 'uscita' / datetime.now().strftime('%Y%m%d_%H%M%S')
    print(f'Risultati in: {out}', flush=True)

    cmd1 = [sys.executable, '-B', str(HERE / 'fase1_ocr_deepseek.py'), '--cartella', args.cartella] + (['--rifai'] if args.rifai else []) + args.pagine
    code = run(cmd1, 'FASE 1: DeepSeek-OCR 2 legge le pagine (processo separato, poi si chiude)')
    if code != 0:
        print(f'\nFase 1 non riuscita (codice {code}): mi fermo.', file=sys.stderr)
        return code
    cmd2 = [sys.executable, '-B', str(HERE / 'fase2_assembla.py'), '--cartella', args.cartella, '--uscita', str(out)] + args.pagine
    code = run(cmd2, 'FASE 2: assemblaggio e verifica contro il testo digitale del PDF (nessun modello)')
    if code != 0:
        return code
    recupero = out / 'recupero_minicpm'
    if not args.senza_recupero:
        cmd_recupero = [sys.executable, '-B', str(HERE / 'recupero_minicpm.py'), str(out), '--cartella', args.cartella]
        recovery_code = run(cmd_recupero, 'RECUPERO: MiniCPM legge solo le pagine segnalate, in una cartella separata',
                            sandboxed=False)
        if recovery_code:
            print('MiniCPM non disponibile o recupero incompleto: i risultati principali restano utilizzabili.', file=sys.stderr)
    if args.solo_lettura:
        print(f'\nFATTO (solo lettura). Apri la cartella: {out}\nLeggi per prima: {out / "RAPPORTO.txt"}')
        return 0
    # DeepSeek e' gia' uscito dalla memoria (fase 1 finita): ora, e solo ora, si carica Qwen.
    cmd3 = [sys.executable, '-B', str(HERE / 'fase3_traduci.py'), str(out), '--lingua', args.lingua]
    code = run(cmd3, 'FASE 3: Qwen traduce il Markdown verificato (DeepSeek non e\' piu\' in memoria)')
    if code == 0:
        code = run([sys.executable, '-B', str(HERE / 'esporta_pdf.py'), str(out)],
                   'FASE 4: creo il PDF italiano dal Markdown')
    if code == 0 and recupero.is_dir() and list(recupero.glob('*_p[0-9][0-9][0-9][0-9].md')):
        cmd_alt = [sys.executable, '-B', str(HERE / 'fase3_traduci.py'), str(recupero), '--lingua', args.lingua,
                   '--cache', str(recupero / 'cache_qwen.json')]
        alt_code = run(cmd_alt, 'TRADUZIONE ALTERNATIVA: Qwen traduce le pagine lette da MiniCPM')
        if alt_code == 0:
            alt_code = run([sys.executable, '-B', str(HERE / 'esporta_pdf.py'), str(recupero)],
                           'PDF ALTERNATIVO: creo il PDF delle pagine lette da MiniCPM')
        if alt_code:
            print('La traduzione alternativa richiede verifica: leggi il suo rapporto.', file=sys.stderr)
    if code == 0:
        print(f'\nFATTO. Apri la cartella: {out}\nLeggi per prime: {out / "RAPPORTO.txt"} e {out / "RAPPORTO_TRADUZIONE.txt"}'
              f'\nTraduzione: i file *_it.md (una pagina), *_italiano.md e *_italiano.pdf (tutte le pagine).')
        if recupero.is_dir():
            print(f'Recupero MiniCPM: {recupero}\nConfronta i file *_it.md alternativi e leggi {recupero / "RAPPORTO_RECUPERO.txt"}.')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
