# Bulk processing of field inspection acts in a billing web app (Selenium)

A Python + Selenium tool that automates a daily back-office task in a
water-utility billing system (WG Craft). Field inspectors submit inspection
acts from a mobile app; each new act has to be accepted for processing and its
GPS record confirmed by hand — around ten clicks per act, hundreds of acts per
batch. The script takes a list of act numbers from Excel and does it unattended.

> Built for an internal system I work with. **No real subscriber data, URLs or
> credentials are included** – the demo workbook contains fictional act numbers.
> Use automation like this only on systems you are authorised to operate.

## What it does

For every act number in the Excel list:

1. Opens *Inspection acts (new)* and searches by act number.
2. Opens the row menu and chooses *Accept for processing*, then confirms.
3. Opens the act's GPS record, adds a note, applies and confirms.
4. Checks that the GPS status changed to *changes applied* and logs the result.

## Features

- **Resumable:** every result is appended to `logs/results.csv`; acts marked
  `OK` are skipped on the next run, so a crash or a lost connection costs nothing.
- **Selectors kept out of the code:** all XPaths live in `selectors.json`, so a
  UI change means editing one JSON file, not the Python code.
- **Self-healing session:** if the site logs the user out mid-run, the script
  logs back in automatically.
- **Debuggable:** on any error a screenshot and the page HTML are saved to
  `logs/`; the run stops after 5 consecutive errors.
- **Step-by-step mode:** set `"step_by_step": true` in `config.json` to pause
  before every click while testing on a new screen.
- **Secrets stay out of the repo:** URL and credentials come from `.env`.

## Project structure

```
main.py             entry point: reads Excel, runs the loop, writes results
inspection_acts.py  the business workflow for one act
browser.py          Selenium wrapper: waits, clicks, typing, login
config.json         Excel file/column, timeouts, browser
selectors.json      XPath selectors for every UI element
demo_acts.xlsx      fictional sample input
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in WGCRAFT_URL, WGCRAFT_LOGIN, WGCRAFT_PASSWORD
```

Requires Python 3.9+ and Google Chrome (Selenium Manager downloads the driver).
Set `"browser": "edge"` in `config.json` to use Edge instead.

## Usage

```bash
python main.py --dry-run          # preview: list pending acts, no browser
python main.py --limit 5          # test run on the first 5 acts
python main.py                    # full run, resumes from logs/results.csv
python main.py --excel my.xlsx    # use another input file
```

The Excel file needs a column with act numbers (`act_column` in `config.json`,
default `Номер`). `start_row` / `end_row` limit the processed range.

## Output

`logs/results.csv` has one row per act with a status:

| Status  | Meaning |
|---------|---------|
| `OK`    | accepted and GPS confirmed (or GPS was already confirmed) |
| `SKIP`  | act not found, or it cannot be accepted any more |
| `CHECK` | saved, but the GPS status did not update – check manually |
| `ERROR` | unexpected error – see the screenshot and HTML in `logs/` |

## Notes

- Element lookup is based on the visible (Russian-language) labels of the web
  app, so it needs adapting for another UI language or product.
- Tech: Python, Selenium, pandas, python-dotenv.
