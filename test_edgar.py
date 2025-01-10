import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


class EDGARValidator:
    def __init__(self, email: str):
        self.headers = {
            'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 {email}'
        }
        self.base_url = "https://www.sec.gov/Archives"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging

    def get_filing_links(self, cik: str, filing_type: str = "DEF 14A", limit: int = 1) -> List[Dict]:
        """Get links to the filings for a given CIK."""
        # Ensure CIK is 10 digits with leading zeros
        cik = cik.zfill(10)
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={filing_type.replace(' ', '+')}&dateb=&owner=exclude&count={limit}"

        self.logger.info(f"Fetching from URL: {url}")

        try:
            time.sleep(0.1)  # SEC rate limit
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            self.logger.info(f"Got response with status code: {response.status_code}")

            soup = BeautifulSoup(response.text, 'html.parser')
            filings = []

            # Find the document links table
            doc_table = soup.find('table', {'class': 'tableFile2'})
            if not doc_table:
                self.logger.warning(f"No filings found for CIK {cik}")
                return []

            for row in doc_table.find_all('tr')[1:]:  # Skip header row
                cols = row.find_all('td')
                if len(cols) >= 4:
                    filing_type = cols[0].text.strip()
                    if filing_type == "DEF 14A":
                        filing_date = cols[3].text.strip()
                        doc_link = cols[1].find('a')
                        if doc_link:
                            doc_href = doc_link['href']
                            filing_info = {
                                'filing_type': filing_type,
                                'filing_date': filing_date,
                                'doc_url': f"https://www.sec.gov{doc_href}"
                            }
                            self.logger.info(f"Found filing: {filing_info}")
                            filings.append(filing_info)

            return filings

        except Exception as e:
            self.logger.error(f"Error getting filing links for CIK {cik}: {str(e)}")
            return []

    def get_filing_content(self, doc_url: str) -> Optional[str]:
        """Get the actual filing content."""
        try:
            self.logger.info(f"Fetching document page from: {doc_url}")

            time.sleep(0.1)  # SEC rate limit
            response = requests.get(doc_url, headers=self.headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Look specifically for the DEF 14A document link
            filing_link = None
            for link in soup.find_all('a'):
                href = link.get('href', '')
                if 'def14a.htm' in href.lower():  # Look specifically for def14a files
                    filing_link = f"https://www.sec.gov{href}"
                    self.logger.info(f"Found DEF 14A link: {filing_link}")
                    break

            if not filing_link:
                self.logger.warning(f"No DEF 14A filing found at {doc_url}")
                # Try alternative method - look for type
                for link in soup.find_all('a'):
                    href = link.get('href', '')
                    text = link.get_text().lower()
                    if '.htm' in href and 'def 14a' in text:
                        filing_link = f"https://www.sec.gov{href}"
                        self.logger.info(f"Found DEF 14A link (alternative method): {filing_link}")
                        break

            if not filing_link:
                return None

            time.sleep(0.1)  # SEC rate limit
            self.logger.info(f"Fetching filing content from: {filing_link}")
            response = requests.get(filing_link, headers=self.headers)
            response.raise_for_status()

            # Verify we got actual proxy statement content
            content = response.text
            if 'proxy statement' in content.lower():
                return content
            else:
                self.logger.warning("Retrieved content does not appear to be a proxy statement")
                return None

        except Exception as e:
            self.logger.error(f"Error getting filing content from {doc_url}: {str(e)}")
            return None

    def validate_filing_content(self, content: str) -> bool:
        """Validate that the filing content is actually a DEF 14A."""
        if not content:
            self.logger.warning("Empty content")
            return False

        soup = BeautifulSoup(content, 'html.parser')
        text_content = soup.get_text().lower()

        # Check for common DEF 14A terms
        required_terms = [
            r'proxy\s+statement',
            r'(executive\s+compensation|compensation\s+discussion)',
            r'(board\s+of\s+directors|corporate\s+governance)',
            r'(stock|share)\s+(ownership|holdings)',
        ]

        matches = 0
        for term in required_terms:
            if re.search(term, text_content, re.IGNORECASE):
                self.logger.info(f"Found term: {term}")
                matches += 1
            else:
                self.logger.info(f"Missing term: {term}")

        # Consider valid if at least 2 of the required terms are found
        # and one of them is "proxy statement"
        basic_valid = matches >= 2
        has_proxy = re.search(r'proxy\s+statement', text_content, re.IGNORECASE)

        return basic_valid and has_proxy


    def process_company(self, cik: str, output_dir: str = "def14a_filings"):
        """Process and validate filings for a company."""
        Path(output_dir).mkdir(exist_ok=True)

        filings = self.get_filing_links(cik)
        if not filings:
            return

        for filing in filings:
            content = self.get_filing_content(filing['doc_url'])
            if not content:
                continue

            if self.validate_filing_content(content):
                clean_date = filing['filing_date'].replace('/', '-')
                filename = f"{cik}_{clean_date}_def14a.htm"
                filepath = os.path.join(output_dir, filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)

                self.logger.info(f"Successfully saved valid filing to {filepath}")
            else:
                self.logger.warning(f"Invalid or empty filing found for CIK {cik} dated {filing['filing_date']}")

def main():
    validator = EDGARValidator("your.email@example.com")

    # Let's test with just Apple first
    test_cik = '0000320193'
    validator.process_company(test_cik)

if __name__ == "__main__":
    main()
