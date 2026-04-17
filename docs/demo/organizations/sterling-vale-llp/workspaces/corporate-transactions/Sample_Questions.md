# Sample questions — Corporate & Transactions

**Workspace tag:** `CORPORATE` · **Demo focus:** vendor MSAs, indemnity, and deal closing

Use these prompts **after** uploading demo files from this folder into the **same workspace** in the app. Synthetic internal reference text only — not legal advice.

## Tier 1 pack (upload any or all)

- `Sterling_Vale_CORPORATE_Demo_Pack.md` — long Markdown compendium
- `Sterling_Vale_CORPORATE_Demo_Pack.html` — HTML export
- `Sterling_Vale_CORPORATE_Demo_Pack.txt` — plain-text export
- `Sterling_Vale_CORPORATE_Demo_Pack.docx` — Word
- `Sterling_Vale_CORPORATE_Demo_Pack.pdf` — multi-page PDF compendium

Other PDFs in this folder may come from `scripts/write_demo_pdf_assets_to_docs.py`; those are optional extras.

## Tier 1 — retrieval / chat smoke tests

1. What deal-phase topics does the Corporate demo pack emphasize (vendor MSAs, indemnity, closing)?
2. What SVL tag format is used in conflicts clearance verification lines in the demo pack?
3. What internal reference pattern is repeated in segment lines across the Corporate files?
4. When must partners align work product with the engagement letter and matter code?
5. What filename pattern uses SVL-matter-doctype-version?
6. What should teams do when a new regulator sends correspondence not listed on intake?
7. What archive suffix is used for superseded drafts in the checklist?
8. What does the demo text say about matter budget bands and escalation?

## Tier 2 pack (slides, spreadsheets, CSV, RTF)

- `Sterling_Vale_CORPORATE_Tier2_Pack.pptx` — PowerPoint deck
- `Sterling_Vale_CORPORATE_Tier2_Pack.xlsx` — Excel workbook (multiple sheets)
- `Sterling_Vale_CORPORATE_Tier2_Pack.csv` — tabular extract
- `Sterling_Vale_CORPORATE_Tier2_Pack.rtf` — rich text export
- `Sterling_Vale_CORPORATE_Tier2_Pack.xls` — legacy Excel (optional generator; requires `xlwt`)

## Tier 2 — retrieval / chat smoke tests

1. What workspace name is in cell B2 of the Summary sheet in the Tier 2 xlsx?
2. How many data rows (approx) are in the Tier 2 CSV after the header?
3. What RTF text references vendor MSAs or indemnity themes from the topic line?
4. What string identifies the Tier 2 XLS key row if you generated the .xls file?
5. What appears in the title placeholder on the second content slide of the deck?

## Tier 3 pack (email, ebooks, OCR/image)

- `Sterling_Vale_CORPORATE_Tier3_Pack.eml` — email with text body + attachment marker content
- `Sterling_Vale_CORPORATE_Tier3_Pack.epub` — EPUB chapter sample
- `Sterling_Vale_CORPORATE_Tier3_Pack_ocr.png` — OCR image sample
- `Sterling_Vale_CORPORATE_Tier3_Pack_ocr.jpg` — OCR image sample (jpeg)
- `Sterling_Vale_CORPORATE_Tier3_Pack_ocr.tiff` — OCR image sample (tiff)
- `Sterling_Vale_CORPORATE_Tier3_Pack_scanned.pdf` — image-only PDF for OCR fallback testing
- *(No `.msg` generated on this machine. Create via Outlook Save As .msg or provide fixture.)*
- `Sterling_Vale_CORPORATE_Tier3_Pack.mobi` — MOBI sample

## Tier 3 — retrieval / chat smoke tests

1. What vendor/MSA phrase appears in the Tier 3 EML body?
2. Which SVL OCR marker appears in the corporate Tier 3 image sample?
3. What line in the EPUB references indemnity/deal closing themes?
4. What is the attachment filename included in the EML test pack?

## Tips

- Ask one question at a time; confirm citations point at the uploaded document.
- If retrieval is empty, verify you selected the correct **workspace** and that ingestion finished.
- Tier 2 uploads index text from slides, sheet rows, CSV lines, and RTF body — ask about strings you know appear in those files.
- Tier 3 OCR quality depends on image clarity; for best results use high contrast black text on white background.

