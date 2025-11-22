# Matching Logic Docs

## Quick start
- Run `python run.py` from the repo root to print the current matching report.
- The fixtures live in `src/data/transactions.json` and `src/data/attachments.json`.

## Data model
- Transactions: `id`, `date` (YYYY-MM-DD), `amount` (positive for income, negative for spend), optional `contact`, optional `reference`.
- Attachments (invoices/receipts): `id`, `type`, and a `data` object that may contain `invoice_number`, `invoicing_date`, `due_date`, `issuer`, `recipient`, `supplier`, `total_amount`, and `reference`.
- Amount comparisons use the absolute transaction amount so expenses and income match correctly against positive attachment totals.

## Matching heuristics
1. Reference number match always wins. References are normalized by removing whitespace, uppercasing, and trimming leading zeros. If a transaction and an attachment share a normalized reference, that pair is returned immediately.
2. Score by signals when no reference match is found:
   - Amount: matches within `0.01` tolerance (required for any score).
   - Date: attachment `due_date` within `15` days of the transaction date.
   - Counterparty: transaction `contact` compared against `issuer`/`recipient`/`supplier`. Names are normalized to lowercase words; exact matches, subsets, or overlaps of at least two words count.
3. Thresholds: with a contact we require all three signals; without a contact we accept amount + date only. Ties are broken by picking the lowest attachment id to keep runs deterministic.

## Edge cases handled
- References like `"0000 5550"` and `"5550"` match after normalization.
- Missing contacts still allow receipt-style matches (amount + date).
- Negative transaction amounts are treated as positive to align with positive invoice totals.

## Debugging tips
- If a match surprises you, temporarily print `_calculate_match_score` inputs in `src/match.py` to see which signals triggered.
- You can also load the JSON fixtures in a REPL and call `find_attachment`/`find_transaction` directly for ad hoc checks.



## Implementation Overview

### How matching works

The logic implemented in `src/match.py` follows a deterministic scoring system so every run produces the same result:

1. **Reference number first** – both `find_attachment` and `find_transaction` normalize reference numbers (strip whitespace and leading zeros). If a transaction and an attachment share the same normalized reference, the functions immediately return that pair because reference matches are treated as definitive 1:1 links.
2. **Amount, date, and counterparty** – when no reference is available, we evaluate these three signals:
   - Amounts must match within a tolerance of `0.01` (after taking absolute values to treat payments and expenses uniformly). This provides the first score point.
   - Dates must be within `15` days of each other. Transactions use their booking date; attachments prefer due date, falling back to invoicing/receipt dates. A match adds another point.
   - Counterparty names are compared after normalization to account for casing, ordering, and suffixes (`Oy`, `LLC`, etc.). Exact matches, subset matches, or overlaps of at least two words add the final point.
3. **Minimum score thresholds** – when a transaction contains a `contact` value, we require all three signals (score ≥ 3). If the contact is missing, we allow amount + date (score ≥ 2) so receipts without names can still match.
4. **Tie-breaking** – we track the highest score found and, when scores tie, pick the lower attachment/transaction ID to keep results deterministic.

### Running the matcher

```
python run.py
```

The script loads `src/data/transactions.json` and `src/data/attachments.json`, calls both matching functions for every entry, and prints a table showing expected vs. actual matches. This is the fastest way to validate changes while working on the heuristics.

### Files of interest

- `src/match.py` – contains all matching logic and helper utilities.
- `debug.py` – optional helper that prints extensive scoring details for manual inspection.
- `src/data/*.json` – fixture data used by `run.py`.
- `run.py` – orchestrates loading data and printing the evaluation report (do not modify).

---