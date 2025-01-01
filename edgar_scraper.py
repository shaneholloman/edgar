import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
from datetime import datetime
import os
import logging

class EDGARScraper:
    def __init__(self, email):
        """
        Initialize the scraper with your email (required by SEC)
        """
        self.headers = {
            'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 {email}'
        }
        self.base_url = "https://www.sec.gov/Archives"
        logging.basicConfig(level=logging.INFO)
        self.logger = logging

    def get_company_ciks(self):
        """
        Get a list of all company CIKs from SEC
        """
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()

            # Convert to DataFrame and zero-pad CIKs to 10 digits
            df = pd.DataFrame.from_dict(data, orient='index')
            df['cik_str'] = df['cik_str'].astype(str).str.zfill(10)
            return df['cik_str'].tolist()
        except Exception as e:
            self.logger.error(f"Error getting company CIKs: {str(e)}")
            return []

    def get_def14a_links(self, cik):
        """
        Get all DEF 14A filing links for a given CIK
        """
        try:
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=DEF+14A&dateb=&owner=exclude&count=100"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            documents = []

            # Find all document links
            for row in soup.find_all('tr'):
                if row.find('td', text='DEF 14A'):
                    doc_link = row.find('a', {'id': 'documentsbutton'})
                    if doc_link:
                        documents.append(f"https://www.sec.gov{doc_link['href']}")

            return documents
        except Exception as e:
            self.logger.error(f"Error getting DEF 14A links for CIK {cik}: {str(e)}")
            return []

    def download_filing(self, doc_url, output_dir):
        """
        Download a specific filing and save it
        """
        try:
            # Get the document page
            response = requests.get(doc_url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the actual filing link
            filing_link = soup.find('a', {'href': lambda x: x and x.endswith('.htm')})
            if filing_link:
                filing_url = f"https://www.sec.gov{filing_link['href']}"

                # Download the filing
                filing_response = requests.get(filing_url, headers=self.headers)
                filing_response.raise_for_status()

                # Create filename from URL
                filename = os.path.join(output_dir,
                                      f"{doc_url.split('/')[-2]}_{filing_link['href'].split('/')[-1]}")

                # Save the filing
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(filing_response.text)

                self.logger.info(f"Successfully downloaded: {filename}")
                return True

            return False
        except Exception as e:
            self.logger.error(f"Error downloading filing {doc_url}: {str(e)}")
            return False

    def scrape_all_def14a(self, output_dir="def14a_filings"):
        """
        Main function to scrape all DEF 14A filings
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Get all company CIKs
        ciks = self.get_company_ciks()
        self.logger.info(f"Found {len(ciks)} companies")

        # Track progress
        total_downloaded = 0

        # Process each company
        for cik in ciks:
            # Respect SEC rate limit (10 requests per second)
            time.sleep(0.1)

            # Get all DEF 14A filings for this company
            filing_links = self.get_def14a_links(cik)

            for link in filing_links:
                time.sleep(0.1)  # Rate limiting
                if self.download_filing(link, output_dir):
                    total_downloaded += 1

            self.logger.info(f"Processed CIK {cik}: Found {len(filing_links)} filings")

        self.logger.info(f"Scraping completed. Total filings downloaded: {total_downloaded}")

if __name__ == "__main__":
    # Initialize scraper with your email
    scraper = EDGARScraper("dd367@cornell.edu")

    # Start scraping
    scraper.scrape_all_def14a()
