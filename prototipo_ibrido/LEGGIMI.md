# Ibrido: DeepSeek-OCR 2 + verifica contro il PDF + traduzione Qwen (PROTOTIPO, 13 nov 2026)

## Scelta nella finestra di Carta OCR V6

Nel menu **Modello di lettura** si puo' scegliere: V6 attuale, DeepSeek-OCR 2,
MiniCPM-OCR 1.0 oppure Automatico (DeepSeek e recupero MiniCPM solo sulle pagine segnalate).
Tutti i percorsi producono un PDF italiano. I tre percorsi OCR conservano anche Markdown tedesco e italiano.
Il PDF OCR e' una copia da leggere, con una pagina per ogni pagina originale; non ricostruisce l'impaginazione del libro.
Formule OCR LaTeX malformate sono segnalate in `AVVISI_PDF.txt` e mostrate come testo da verificare.
La traduzione resta affidata a Qwen. Per MiniCPM e Automatico, la finestra avvia Ollama da sola se necessario,
con `OLLAMA_NO_CLOUD=1` e ascolto limitato a `127.0.0.1`. Il modello deve gia' essere scaricato sul Mac.

Obiettivo: da un PDF con testo digitale ottenere un **Markdown italiano con formule in LaTeX** piu' fedele di quello che darebbe
DeepSeek da solo. Le formule non passano mai da Qwen. **V6 (il motore) non e' stato toccato.**
Tre processi in sequenza, mai due modelli insieme: DeepSeek (fase 1) -> nessun modello (fase 2) -> Qwen (fase 3).

## Come funziona
1. **Fase 1** (`fase1_ocr_deepseek.py`, offline): DeepSeek-OCR 2 legge la pagina e restituisce blocchi con riquadro + testo/LaTeX.
   Uscita grezza in `lavoro/` (cache). A fine processo il modello esce dalla memoria. Picco RAM 8,47 GB, 3-9 s a pagina.
2. **Fase 2** (`fase2_assembla.py`, nessun modello): per ogni blocco confronta con il **testo digitale del PDF** nello stesso riquadro.
   - *Equazione*: lettere, cifre, greche e operatori del LaTeX devono coincidere, **in numero**, con quelli del PDF. Coincidono ->
     LaTeX. Non coincidono o il LaTeX e' malformato -> **ritaglio dell'originale** + motivo nel rapporto.
   - *Riparazioni sicure*: parole nelle formule ("f u r" -> "für", dal PDF), comandi incollati (`\colonR`), `R` -> `\mathbb{R}`,
     frecce composte dal PDF (↦, ⟹); parole sbagliate nel testo corrette con quelle del PDF (allineamento ordinato); l/I/1.
   - *Figure*: ritaglio dell'originale. Un simbolo che il testo digitale di **quel** libro non contiene mai (es. Δ) e' "non verificabile".
3. **Fase 3** (`fase3_traduci.py`, Qwen3.5-9B, offline): riusa il `Translator` di V6 (segnaposto `<F1>`/`<E1>` per le formule, validazione di
   tag/numeri/parole non tradotte, scala di recupero, cache, glossario). Le frasi interrotte da un'equazione sono tradotte come UNA
   unita'. Le parole dentro le formule (`\text{für alle}`) si traducono con una tabella (`lingua_ibrido_deu.json`), poi Qwen come ripiego.
   I titoli ("Definition 2.18") sono forzati con la tabella di V6. **A fine traduzione un controllo automatico verifica che
   TUTTE le formule siano identiche a quelle in ingresso** (ignorando solo le parole in `\text{}`).

## Uso
```
PY="$HOME/Library/Application Support/CartaOCR/runtime/bin/python3"
cd "$HOME/Desktop/CartaOCR_Progetto/05_V6_in_sviluppo/prototipo_ibrido"
"$PY" -B avvia_ibrido.py 978-3-658-50521-9.pdf:30-35 1783639.pdf:25            # lettura + traduzione
"$PY" -B avvia_ibrido.py 978-3-658-50521-9.pdf:30-35 --solo-lettura            # solo Markdown verificato, tedesco
```
Pagine = numeri del lettore PDF. Risultato in `uscita/<data ora>/`: `*_p<NNNN>.md` (tedesco verificato), `*_p<NNNN>_it.md` (italiano),
`*_italiano.md` (tutte le pagine), `formule/` e `figure/` (ritagli), **`RAPPORTO.txt` e `RAPPORTO_TRADUZIONE.txt` (da leggere)**.
Le formule sono `$...$` / `$$...$$`: servono un lettore Markdown con KaTeX/MathJax (non ho un renderer offline qui).
I blocchi dubbi hanno un commento `<!-- DA VERIFICARE CON L'ORIGINALE: ... -->`.
Terminologia: aggiungi voci in `~/Library/Application Support/CartaOCR/glossario.json` (lingua "deu": {"Takt": "ciclo", ...}):
V6 e fase 3 le usano senza toccare il codice.

## Risultati misurati (14 pagine di 5 libri tedeschi, 57 equazioni, 234 formule in linea)
**Lettura (fasi 1-2)**

| Problema di DeepSeek da solo | Trovato | Esito con l'ibrido |
|---|---|---|
| Parole dentro le formule storpiate ("f u r", ü persa) | 6 (p.25) | tutte ripristinate dal PDF |
| Indice scambiato in una formula (p.208, `p_l` -> `p_k`) | 1 | **rilevato**, sostituito dal ritaglio |
| LaTeX non compilabile (`\colonR`, `\toR`, `\timesR`) | 5 | riparati |
| `R` invece di `\mathbb{R}` | ~12 | riparati |
| Parole sbagliate nel testo (anche una frase: "ist soll" per "stellt") | ~10 | corrette con il PDF |
| Equazioni accettate / al ritaglio | 55 / 2 | 1 vero errore + 1 elenco puntato |
| Errori in formule **in linea** (⊂⊂ perso a p.195, coefficienti binomiali a p.37) | 2 blocchi | **solo segnalati**, non sostituiti |

Controllo a occhio: 20 equazioni *accettate* su pagine mai usate per scrivere le regole: 20 su 20 corrette (con 20 campioni l'errore
reale resta sotto il ~14% al 95%). `banco_di_prova.py`: 16 controlli sugli errori noti (16/16), serve a non peggiorare modificando il codice.

**Traduzione (fase 3)**: 14 pagine in 109 s (Qwen carica in 2 s); 0 passaggi falliti; **0 pagine con formule modificate**.
Giudizio sull'italiano (lettura di 7 pagine su 14; indicativo): circa **78/100**. Buono sul tecnico e sulle frasi lunghe con formule;
errori tipici di un modello da 9B a 4 bit, circa uno ogni pagina: "tatti di controllo" (Regelungstakte), "le prime due numeri dispari",
"insieme convesso" per una funzione, "dal relativo dimostrazione", un accento inventato in un titolo maiuscolo ("SALTÒ").

## Bug di V6 trovato (NON corretto in V6)
Il controllo dei numeri di V6 (`validate`) toglie `\d{1,2}\.` come se fosse un ordinale ("1. Ordnung"). Cosi' anche "teorema 4.24. Per ..."
perde una cifra e una traduzione corretta e' bocciata con "numeri modificati". Nella fase 3 e' corretto **in memoria** (`patch_validate`).
Lo stesso falso allarme colpisce V6: portare la correzione nel motore e' una modifica di una riga (decide l'utente).

## Limiti noti (importanti)
- **Il controllo delle formule conta i simboli, non guarda la disposizione.** Un apice scambiato con un pedice (stessi simboli) passerebbe.
- Le formule **in linea** sbagliate sono segnalate, **non sostituite** (servirebbe localizzarle nel PDF, come fa V6).
- Serve il **testo digitale** nel PDF; per le scansioni il confronto non e' possibile.
- Una frase spezzata da un elenco puntato ("... ob diese Behauptung • ... • stimmt.") viene tradotta a pezzi: il pezzo finale perde il senso.
- Testato solo su tedesco, 5 libri, nessuna tabella (i blocchi HTML sono lasciati in tedesco e segnalati), nessuna scansione, nessun inglese.
- Il LaTeX non e' stato compilato (niente renderer offline): controllati solo parentesi, \begin/\end e comandi noti.
- Se il PDF ha un refuso ("Spannnungs..."), l'ibrido lo riproduce. Non c'e' ancora la riscrittura in PDF: l'uscita e' Markdown.

## Percorso di recupero MiniCPM (separato)

`avvia_ibrido.py` esegue il percorso principale come prima. Dopo la fase 2, legge `rapporto.json`: se una pagina ha
equazioni scartate, formule in linea sospette, differenze con il PDF o parole mancanti, `recupero_minicpm.py` la rilegge
con MiniCPM-OCR 1.0 tramite un server **Ollama locale**. Le altre pagine non vengono rilette. Il risultato alternativo
si trova in `uscita/<data>/recupero_minicpm/`, con un suo rapporto e una sua cache di traduzione. Il percorso principale
non legge mai i file del recupero; se MiniCPM non e' disponibile, rimane utilizzabile.

Serve Ollama con il modello `openbmb/minicpm-ocr1.0` scaricato e il servizio locale attivo. Ollama e' il programma che
esegue il modello sul Mac; non occorre aggiungere librerie Python al runtime di CartaOCR. `--senza-recupero` disattiva
il secondo percorso. Il recupero usa l'API locale `http://127.0.0.1:11434/api/generate`.
Se usi gli script dal Terminale senza la finestra, avvia il servizio manualmente in modalita' solo locale con
`OLLAMA_NO_CLOUD=1 ollama serve` e lascia aperto il terminale durante il lavoro. `OLLAMA_NO_CLOUD=1` disattiva le funzioni cloud di Ollama. Il modello
si scarica una sola volta con `ollama pull openbmb/minicpm-ocr1.0` (serve Internet solo durante il download).

**Il secondo risultato e' una proposta da verificare**, soprattutto sulle formule: MiniCPM legge la pagina intera e non
fornisce i riquadri che la fase 2 usa per confrontare ogni formula con il PDF. I due Markdown sono quindi conservati
separatamente. Il modello dichiara inglese e cinese come lingue principali; per i libri tedeschi va confrontato sulle
stesse pagine difficili prima di sceglierlo come risultato definitivo.

## File
`fase1_ocr_deepseek.py`, `fase2_assembla.py`, `fase3_traduci.py`, `avvia_ibrido.py`, `banco_di_prova.py`, `lingua_ibrido_deu.json`,
`lavoro/` (cache DeepSeek e Qwen), `uscita/` (`prova_14_pagine/` = risultato di riferimento, tedesco + italiano).
Non pubblicare `lavoro/` e `uscita/`: contengono testo dei libri.
