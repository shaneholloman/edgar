# TODO

App works, but needs some improvements.

- [ ] alter script to export to `./data/` (or destination choice) directory instead of `./`
  - [ ] lets use an env / conf file for that so all scripts can use it for paths
  - [ ] the def14a_filings dir has .htm files, those need to be paced in an `htm` dir
- [ ] create a script to process htm files to clean markdown
- [ ] provide option to use markdown files in lieu of htm files for parsing
- [ ] add ability to use ollama
- [ ] add ability to use anthropic
- [ ] create vectorized database
- [ ] add docstrings everywhere
- [ ] correct all pylint errors

Proposed structure:

```tree
edgar_scraper/
├── def14a_filings/
│   ├── filings.db
│   ├── data/
│   │   ├── htm/
│   │   │   ├── 0000320193/
│   │   │   │   ├── 0000320193-21-000010.htm
│   │   │   │   ├── 0000320193-21-000010.htm
│   │   │   │   └── ...
│   │   │   ├── 0000789019/
│   │   │   │   ├── 0000789019-21-000010.htm
│   │   │   │   ├── 0000789019-21-000010.htm
│   │   │   │   └── ...
│   │   │   └── ...
│   │   ├── md/
│   │   │   ├── 0000320193/
│   │   │   │   ├── 0000320193-21-000010.md
│   │   │   │   ├── 0000320193-21-000010.md
│   │   │   │   └── ...
│   │   │   ├── 0000789019/
│   │   │   │   ├── 0000789019-21-000010.md
│   │   │   │   ├── 0000789019-21-000010.md
│   │   │   │   └── ...
│   │   │   └── ...
├── edgar_scraper.py
├── parse_exec_compensation.py
├── schema.py
├── test_edgar.py
└── test_parser.py
```
