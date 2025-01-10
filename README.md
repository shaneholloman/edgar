# Edgar Scraper

## What is this tool?

This tool extracts and analyzes executive info, education, compensation etc data from SEC filings. If you're not familiar with the U.S. financial system, here's what you need to know:

### Quick Background

The **Securities and Exchange Commission (SEC)** is the main financial regulator in the United States. Think of it as the watchdog that makes sure public companies play fair with investors. Created after the 1929 stock market crash, the SEC's job is to:

- Protect investors
- Keep markets fair and efficient
- Help companies raise capital properly

### What Data Does This Tool Get?

This tool specifically looks at **DEF 14A filings** (also called proxy statements). These are documents that public companies must file before their annual shareholder meetings. They contain juicy details like:

- How much executives get paid (salary, bonuses, stock options)
- Executive backgrounds and qualifications
- Board member information
- Important company decisions that need shareholder votes

### How Does It Work?

1. The tool connects to **EDGAR** (the SEC's electronic filing system)
2. It uses **CIKs** (Central Index Keys) to identify companies
   - A CIK is like a company's SEC ID number
   - Always 10 digits (e.g., Apple Inc. is 0000320193)
3. Downloads the proxy statements
4. Uses AI to extract and structure the executive compensation data

## Technical Details

### Installation

Requirements:

- Python 3.12 or higher
- uv package manager

```bash
# Clone the repository
git clone [repository-url]
cd [repository-name]

# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows

# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env with your:
# - SEC_EMAIL (required for SEC tracking)
# - DEEPSEEK_API_KEY (for AI processing)
```

### Usage

1. Basic Scraping:

    ```python
    from edgar_scraper import EDGARScraper

    scraper = EDGARScraper(email="your.email@example.com")
    scraper.run()  # Scrapes all companies
    ```

2. Specific Companies:

    ```python
    # Process specific companies by CIK
    test_ciks = ['0000320193',  # Apple
                '0000789019',  # Microsoft
                '0001652044']  # Google
    scraper.run(test_ciks)
    ```

3. Parse Executive Data:

    ```python
    from parse_exec_compensation import process_companies
    process_companies()  # Processes all scraped filings
    ```

### Project Structure

- `edgar_scraper.py`: Downloads and validates DEF 14A filings
- `parse_exec_compensation.py`: Extracts executive information
- `schema.py`: Data structure definitions
- `test_edgar.py` & `test_parser.py`: Test suites

### Data Storage

Uses SQLite database (`def14a_filings/filings.db`) with tables:

- `companies`: Company information
- `filings`: DEF 14A documents
- `executive_data`: Parsed compensation data
- `processing_status`: Tracks progress

### Features

- Rate-limited requests to comply with SEC guidelines
- Multi-threaded downloading
- AI-powered text extraction
- Robust error handling
- Progress tracking and resumable operations

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT

## Acknowledgments

- SEC EDGAR system for providing public access to filings
- DeepSeek AI for text processing capabilities
