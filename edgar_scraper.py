import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
from datetime import datetime
import os
from pathlib import Path
import logging
import json
from typing import Optional, List, Dict
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import backoff
import sqlite3
from tqdm import tqdm

class EDGARScraper:
    def __init__(self, email: str, output_dir: str = "def14a_filings", max_retries: int = 3):
        """
        Initialize the scraper
        :param email: Email for SEC tracking
        :param output_dir: Directory to save filings
        :param max_retries: Maximum number of retries for failed requests
        """
        self.headers = {
            'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 {email}'
        }
        self.base_url = "https://www.sec.gov/Archives"
        self.output_dir = output_dir
        self.max_retries = max_retries

        # Create directories
        Path(output_dir).mkdir(exist_ok=True)
        Path(output_dir + '/logs').mkdir(exist_ok=True)

        # Setup logging
        self._setup_logging()

        # Initialize database
        self.db_path = os.path.join(output_dir, 'filings.db')
        self._setup_database()

    def _setup_logging(self):
        """Configure logging with both file and console handlers"""
        log_file = os.path.join(self.output_dir, 'logs', f'scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging

    def _setup_database(self):
        """Initialize SQLite database for tracking scraping progress"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS filings (
                    cik TEXT,
                    filing_date TEXT,
                    file_path TEXT,
                    status TEXT,
                    last_updated TIMESTAMP,
                    url TEXT,
                    PRIMARY KEY (cik, filing_date)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS companies (
                    cik TEXT PRIMARY KEY,
                    name TEXT,
                    last_scraped TIMESTAMP
                )
            ''')

    @backoff.on_exception(backoff.expo,
                         (requests.exceptions.RequestException,
                          requests.exceptions.HTTPError),
                         max_tries=3)
    def _make_request(self, url: str) -> requests.Response:
        """Make request with exponential backoff retry"""
        time.sleep(0.1)  # SEC rate limit
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response

    def get_company_ciks(self) -> List[str]:
        """Get list of company CIKs from SEC"""
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            response = self._make_request(url)
            data = response.json()

            # Convert to DataFrame and zero-pad CIKs to 10 digits
            df = pd.DataFrame.from_dict(data, orient='index')
            df['cik_str'] = df['cik_str'].astype(str).str.zfill(10)

            # Save to database
            with sqlite3.connect(self.db_path) as conn:
                for _, row in df.iterrows():
                    conn.execute('''
                        INSERT OR REPLACE INTO companies (cik, name)
                        VALUES (?, ?)
                    ''', (row['cik_str'], row['title']))

            return df['cik_str'].tolist()
        except Exception as e:
            self.logger.error(f"Error getting company CIKs: {str(e)}")
            return []

    def get_filing_links(self, cik: str, filing_type: str = "DEF 14A", limit: int = 5) -> List[Dict]:
        """Get DEF 14A filing links for a company"""
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={filing_type.replace(' ', '+')}&dateb=&owner=exclude&count={limit}"

        try:
            response = self._make_request(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            filings = []
            doc_table = soup.find('table', {'class': 'tableFile2'})

            if not doc_table:
                self.logger.warning(f"No filings found for CIK {cik}")
                return []

            for row in doc_table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    filing_type = cols[0].text.strip()
                    if filing_type == "DEF 14A":
                        filing_date = cols[3].text.strip()
                        doc_link = cols[1].find('a')
                        if doc_link:
                            doc_href = doc_link['href']
                            filings.append({
                                'filing_type': filing_type,
                                'filing_date': filing_date,
                                'doc_url': f"https://www.sec.gov{doc_href}"
                            })

            return filings

        except Exception as e:
            self.logger.error(f"Error getting filing links for CIK {cik}: {str(e)}")
            return []

    def get_filing_content(self, doc_url: str) -> Optional[str]:
        """Get the actual DEF 14A filing content"""
        try:
            response = self._make_request(doc_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look specifically for the DEF 14A document link
            filing_link = None
            for link in soup.find_all('a'):
                href = link.get('href', '')
                if 'def14a.htm' in href.lower():
                    filing_link = f"https://www.sec.gov{href}"
                    break

            if not filing_link:
                for link in soup.find_all('a'):
                    href = link.get('href', '')
                    text = link.get_text().lower()
                    if '.htm' in href and 'def 14a' in text:
                        filing_link = f"https://www.sec.gov{href}"
                        break

            if not filing_link:
                return None

            response = self._make_request(filing_link)
            content = response.text

            if 'proxy statement' in content.lower():
                return content

            return None

        except Exception as e:
            self.logger.error(f"Error getting filing content from {doc_url}: {str(e)}")
            return None

    def validate_filing_content(self, content: str) -> bool:
        """Validate filing content"""
        if not content:
            return False

        soup = BeautifulSoup(content, 'html.parser')
        text_content = soup.get_text().lower()

        required_terms = [
            r'proxy\s+statement',
            r'(executive\s+compensation|compensation\s+discussion)',
            r'(board\s+of\s+directors|corporate\s+governance)',
            r'(stock|share)\s+(ownership|holdings)',
        ]

        matches = 0
        for term in required_terms:
            if re.search(term, text_content, re.IGNORECASE):
                matches += 1

        basic_valid = matches >= 2
        has_proxy = re.search(r'proxy\s+statement', text_content, re.IGNORECASE)

        return basic_valid and has_proxy

    def process_filing(self, cik: str, filing: Dict) -> bool:
        """Process a single filing"""
        try:
            # Check if already processed
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT status FROM filings
                    WHERE cik = ? AND filing_date = ?
                ''', (cik, filing['filing_date']))
                result = cursor.fetchone()
                if result and result[0] == 'completed':
                    return True

            content = self.get_filing_content(filing['doc_url'])
            if not content or not self.validate_filing_content(content):
                self._update_filing_status(cik, filing, 'invalid')
                return False

            # Save valid filing
            clean_date = filing['filing_date'].replace('/', '-')
            filename = f"{cik}_{clean_date}_def14a.htm"
            filepath = os.path.join(self.output_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            self._update_filing_status(cik, filing, 'completed', filepath)
            return True

        except Exception as e:
            self.logger.error(f"Error processing filing {filing['doc_url']}: {str(e)}")
            self._update_filing_status(cik, filing, 'error')
            return False

    def _update_filing_status(self, cik: str, filing: Dict, status: str, filepath: str = None):
        """Update filing status in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO filings
                (cik, filing_date, file_path, status, last_updated, url)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                cik,
                filing['filing_date'],
                filepath,
                status,
                datetime.now(),
                filing['doc_url']
            ))

    def process_company(self, cik: str) -> None:
        """Process all filings for a company"""
        self.logger.info(f"Processing CIK {cik}")

        filings = self.get_filing_links(cik)
        if not filings:
            return

        for filing in filings:
            try:
                self.process_filing(cik, filing)
            except Exception as e:
                self.logger.error(f"Error processing CIK {cik}: {str(e)}")

    def run(self, ciks: List[str] = None, max_workers: int = 4):
        """Run the scraper"""
        if not ciks:
            ciks = self.get_company_ciks()

        self.logger.info(f"Processing {len(ciks)} companies")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.process_company, cik) for cik in ciks]
            for future in tqdm(as_completed(futures), total=len(futures)):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Error in worker thread: {str(e)}")

def main():
    from dotenv import load_dotenv
    load_dotenv()

    email = os.getenv("SEC_EMAIL")
    if not email:
        raise ValueError("Please set SEC_EMAIL in .env file")

    scraper = EDGARScraper(email)

    # Optional: Process specific CIKs
    # test_ciks = ['0000320193', '0000789019', '0001652044']  # Apple, Microsoft, Google
    # scraper.run(test_ciks)

    # Or process all companies
    scraper.run()

if __name__ == "__main__":
    main()
