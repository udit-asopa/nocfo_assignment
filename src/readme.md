
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
