from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import pdfplumber
import io
import csv
import re
from datetime import datetime, timedelta
from collections import defaultdict
import tempfile

app = FastAPI(title="Bank PDF → CSV API")

# Add CORS middleware to allow requests from the frontend during development.
# In production, restrict origins to your frontend domain instead of using "*".
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5500",  # common simple static server port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# If you test by opening the HTML file directly (file://), the browser origin will be "null" and CORS
# will block requests. For file:// testing either serve the frontend with a local HTTP server or
# temporarily set allow_origins=["*"] for development (not recommended for production).


def clean_amount(s: str) -> int:
    s = (s or "").replace(",", "").strip()
    if s == "":
        return 0
    return int(float(s))


def parse_kotak_line(line: str):
    parts = line.strip().split()
    if len(parts) < 6:
        return None

    second_last = parts[-2]
    if not (second_last.startswith("+") or second_last.startswith("-")):
        return None

    debit = credit = 0
    if second_last.startswith("+"):
        credit = clean_amount(second_last.replace("+", ""))
    else:
        debit = clean_amount(second_last.replace("-", ""))

    # reconstruct date (original script used parts[1] + parts[2] + parts[3])
    try:
        date_raw = parts[1] + parts[2] + parts[3]  # e.g. 02Sep2025
        date_obj = datetime.strptime(date_raw, "%d%b%Y").date()
    except Exception:
        return None

    balance = clean_amount(parts[-1])
    return (date_obj, debit, credit, balance)


def parse_axis_line(line: str):
    # Heuristic parser for AXIS statements. It looks for common date formats and numeric amounts.
    date_pattern = re.search(r'(\d{2}[/-]\d{2}[/-]\d{2,4}|\d{2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{2}[A-Za-z]{3}\d{4})', line)
    if not date_pattern:
        return None
    date_str = date_pattern.group(1)
    date_obj = None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d%b%Y", "%d %B %Y", "%d-%m-%y"):
        try:
            date_obj = datetime.strptime(date_str, fmt).date()
            break
        except Exception:
            continue
    if not date_obj:
        return None

    # find numeric amounts (txn amount and balance)
    amount_regex = r'[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?'
    matches = list(re.finditer(amount_regex, line))
    if len(matches) < 2:
        return None

    txn_match = matches[-2]
    balance_match = matches[-1]
    txn_text = txn_match.group(0)
    txn_amt = clean_amount(txn_text)
    balance = clean_amount(balance_match.group(0))

    debit = credit = 0
    window_pre = line[max(0, txn_match.start()-6):txn_match.start()].upper()
    window_post = line[txn_match.end():txn_match.end()+6].upper()
    if 'DR' in window_pre or 'DR' in window_post or txn_text.startswith('-') or 'DEBIT' in window_pre or 'DEBIT' in window_post:
        debit = txn_amt
    elif 'CR' in window_pre or 'CR' in window_post or txn_text.startswith('+') or 'CREDIT' in window_pre or 'CREDIT' in window_post:
        credit = txn_amt
    else:
        # fallback: negative sign -> debit, otherwise credit
        if txn_text.startswith('-'):
            debit = txn_amt
        else:
            credit = txn_amt

    return (date_obj, debit, credit, balance)


def parse_line(line: str, bank: str):
    bank_key = (bank or '').strip().lower()
    if bank_key == 'axis':
        return parse_axis_line(line)
    else:
        # default to kotak parsing (handles 'kotak' and unknown banks)
        return parse_kotak_line(line)


@app.post("/convert")
async def convert(bank: str = Form(...), pdf: UploadFile = File(...), password: str = Form(None)):
    # save uploaded PDF to a temp file
    suffix = ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await pdf.read()
        tmp.write(content)
        tmp_path = tmp.name

    # extract transactions from PDF
    rows = []
    try:
        with pdfplumber.open(tmp_path, password=password) as doc:
            for page in doc.pages:
                text = page.extract_text()
                if not text:
                    continue
                for line in text.splitlines():
                    parsed = parse_line(line, bank)
                    if parsed:
                        date_obj, debit, credit, balance = parsed
                        rows.append((date_obj, debit, credit, balance))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {exc}")

    if not rows:
        raise HTTPException(status_code=400, detail="No transactions parsed from PDF")

    # Build per-date transactions
    txns = defaultdict(list)
    for date_obj, debit, credit, balance in rows:
        txns[date_obj].append((debit, credit, balance))

    all_dates = sorted(txns.keys())
    start_date = all_dates[0]
    end_date = all_dates[-1]

    # produce EOD ledger
    result_rows = []
    prev_eod = 0
    cur_date = start_date
    while cur_date <= end_date:
        if cur_date in txns:
            last_debit, last_credit, last_balance = txns[cur_date][-1]
            eod = last_balance
            result_rows.append([cur_date.strftime("%Y-%m-%d"), last_debit, last_credit, last_balance, eod])
            prev_eod = eod
        else:
            result_rows.append([cur_date.strftime("%Y-%m-%d"), 0, 0, prev_eod, prev_eod])
        cur_date += timedelta(days=1)

    # write CSV to memory
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Debit", "Credit", "Balance", "EOD"])
    writer.writerows(result_rows)
    csv_bytes = buf.getvalue().encode("utf-8")
    buf.close()

    return StreamingResponse(io.BytesIO(csv_bytes), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="eod.csv"'})