# Carta OCR V6

Traduzione **offline** di PDF di matematica e ingegneria con testo digitale, per ora tedesco → italiano, su Mac Apple Silicon.
Tutto gira in locale: nessun servizio cloud e nessun dato inviato in rete (il lanciatore blocca la rete con `sandbox-exec`).
Le formule non passano mai dal modello di traduzione.

## Cosa c'è

| File / cartella | A cosa serve |
|---|---|
| `traduci_pdf_matematica_offline_v6.py` | Motore V6: PyMuPDF + Qwen3.5-9B (MLX, 4 bit). Le formule restano ritagli dell'originale, il testo è tradotto. Esce un PDF italiano con l'indicazione della pagina originale. |
| `avvia_v6.py` | Lanciatore: rete bloccata, cartella dei risultati ordinata, `AVVISI.txt` con ciò che è dubbio. |
| `frontend_v6.py`, `Avvia_Frontend.command` | Piccola finestra locale: scegli il PDF, le pagine e la lingua. |
| `lingua_deu.json`, `lingua_eng.json` | Liste per lingua. Il tedesco è stato provato su alcuni libri; l'inglese è **sperimentale**. |
| `prototipo_ibrido/` | Prototipo: lettura con DeepSeek-OCR 2, verifica di ogni formula contro il testo digitale del PDF, traduzione del Markdown con Qwen. Risultati misurati e limiti in `prototipo_ibrido/LEGGIMI.md`. |
| `strumenti_test/` | Download e prova di DeepSeek-OCR 2 (con misura della RAM). |
| `ISTRUZIONI_V6.txt`, `CAMBIAMENTI.md`, `PARTI_LABILI.md` | Istruzioni d'uso, storia delle versioni, parti delicate del codice. |

## Requisiti

Mac con Apple Silicon (sviluppato su M5 Max con 36 GB). Versioni con cui è stato provato: Python 3.14, mlx 0.32,
mlx-vlm 0.7.12, pymupdf 2.1, pymupdf4llm 2.1, Pillow, transformers 5.22, huggingface_hub.
Modello Qwen3.5-9B MLX 4 bit scaricato in locale. Per il prototipo ibrido serve anche DeepSeek-OCR-2 (circa 6,8 GB),
che si scarica una sola volta con `strumenti_test/scarica_deepseek_ocr2.py`.
**I pesi dei modelli non sono in questo repository.** Il PDF deve avere testo digitale (le scansioni non sono supportate).

## Limiti noti

- Provato soprattutto sul tedesco e su pochi libri di matematica e ingegneria: non è dimostrato che funzioni su altri testi.
- Le formule sono ritagli dell'originale e possono contenere frammenti delle righe vicine (circa il 29% dei ritagli
  in un capitolo di prova da 79 pagine).
- Il controllo dei numeri del motore ha un bug noto (vedi `CAMBIAMENTI.md`) che può lasciare un passaggio in tedesco.
- L'italiano prodotto da un modello da 9B a 4 bit va letto con l'originale accanto.

## Licenza e dati

Codice sotto **AGPL-3.0** (vedi `LICENSE`): usa PyMuPDF, che è AGPL.
Modelli: Qwen3.5 (Apache-2.0). DeepSeek-OCR-2: la copia MLX dichiara Apache-2.0, ma va controllata la licenza del modello originale.
**Non pubblicare libri né risultati di traduzione**: sono coperti da copyright. Il `.gitignore` esclude le cartelle dei risultati.
