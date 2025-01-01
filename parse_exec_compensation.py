from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import os
from pathlib import Path
import sqlite3
from bs4 import BeautifulSoup
from openai import OpenAI
import json
from dotenv import load_dotenv
import re
from schema import Education, Executive

def get_latest_def14a(cik: str) -> Optional[str]:
    """Get the latest DEF 14A filing content from the SQLite database"""
    db_path = 'def14a_filings/filings.db'

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("""
                SELECT file_path
                FROM filings
                WHERE cik = ? AND status = 'completed'
                ORDER BY filing_date DESC
                LIMIT 1
            """, (cik,))
            result = cursor.fetchone()

            if result and result[0]:
                print('file: ', result[0])
                with open(result[0], 'r', encoding='utf-8') as f:
                    return f.read()
    except Exception as e:
        print(f"Error reading filing: {e}")
        return None

def extract_major_sections(content: str) -> Dict[str, str]:
    """Extract sections based on heading tags and collect all text between them"""
    soup = BeautifulSoup(content, 'html.parser')
    sections = {}

    # Find all heading elements (h1, h2, h3)
    headings = soup.find_all(['h1', 'h2'])

    # Get all text elements
    all_elements = soup.find_all(string=True)
    elements_list = [elem.strip() for elem in all_elements if elem.strip()]

    # Process each heading
    for i in range(len(headings)):
        heading = headings[i].get_text().strip()

        # Find start index of content after this heading
        start_idx = next((idx for idx, text in enumerate(elements_list)
                         if heading in text), -1)

        if start_idx != -1:
            # Find end index (next heading or end)
            if i < len(headings) - 1:
                next_heading = headings[i + 1].get_text().strip()
                end_idx = next((idx for idx, text in enumerate(elements_list[start_idx + 1:], start_idx + 1)
                              if next_heading in text), len(elements_list))
            else:
                end_idx = len(elements_list)

            # Collect content between headings
            content = '\n'.join(elements_list[start_idx + 1:end_idx])

            # Only keep sections with substantial content
            if len(content) > 100:
                sections[heading] = content

    print(f"\nFound {len(sections)} sections")
    print("\nSection titles:")
    for title in sections.keys():
        print(f"- {title}")

    return sections

def filter_relevant_sections(sections: Dict[str, str], client: OpenAI) -> Dict[str, str]:
    """Use DeepSeek to identify sections likely to contain executive information"""

    # Create a list of section titles and first 200 characters of content
    section_previews = {
        title: content[:200] + "..."
        for title, content in sections.items()
    }

    prompt = """Review these section titles and previews from an SEC DEF 14A filing.
    Identify sections likely to contain:
    1. Executive compensation information
    2. Executive biographical information
    3. Management structure information

    Return a JSON array of section titles that are most relevant. Return at most 3 sections.
    Example: ["EXECUTIVE COMPENSATION", "BIOGRAPHICAL INFORMATION"]

    Here are the sections to review:
    """

    try:
        print("\nFiltering sections with DeepSeek...")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are an expert at identifying relevant sections in SEC filings."},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "I will identify the most relevant sections and return them as a JSON array."},
                {"role": "user", "content": json.dumps(section_previews, indent=2)}
            ],
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        # Handle both string and JSON formats
        if isinstance(content, str):
            try:
                relevant_titles = json.loads(content)
            except json.JSONDecodeError:
                # Extract titles between square brackets if JSON parsing fails
                matches = re.findall(r'"([^"]+)"', content)
                relevant_titles = matches if matches else []

        print("\nRelevant sections identified:", relevant_titles)

        # Return only the relevant sections
        return {
            title: content
            for title, content in sections.items()
            if any(rel_title.lower() in title.lower() for rel_title in relevant_titles)
        }

    except Exception as e:
        print(f"\nError filtering sections: {e}")
        # If there's an error, return some common section titles as fallback
        fallback_keywords = ['EXECUTIVE', 'COMPENSATION', 'BIOGRAPHICAL', 'BOARD', 'MANAGEMENT']
        return {
            title: content
            for title, content in sections.items()
            if any(keyword in title.upper() for keyword in fallback_keywords)
        }

def extract_executive_info(sections: Dict[str, str], client: OpenAI) -> list:
    """Extract executive information from the filtered sections"""

    # Combine all relevant sections
    combined_content = "\n\n".join(f"{title}:\n{content}" for title, content in sections.items())

    prompt = """Extract detailed executive information from these proxy statement sections.

    For each Named Executive Officer (NEO), extract:

    1. Name and current position
    2. Age (if mentioned)
    3. Compensation for most recent fiscal year:
       - Base salary
       - Stock awards
       - Non-equity incentive plan / bonus
       - All other compensation
       - Total compensation
    4. Educational background (all degrees, universities, and fields)
    5. When they joined the company (if mentioned)
    6. Previous roles at the company
    7. Board and committee memberships

    Return as JSON array, with NO other details. Example:
    [
        {
            "name": "John Smith",
            "current_role": "Chief Executive Officer",
            "age": 55,
            "compensation_salary": 1000000,
            "compensation_stock": 5000000,
            "compensation_bonus": 2000000,
            "compensation_other": 500000,
            "compensation_total": 8500000,
            "compensation_year": 2023,
            "education": [
                {
                    "degree": "MBA",
                    "field": "Business Administration",
                    "university": "Harvard Business School",
                    "year": 1990
                }
            ],
            "start_date": "2015",
            "past_roles": ["COO", "SVP Operations"],
            "board_member": true,
            "committee_memberships": ["Executive Committee"],
            "other_board_memberships": [],
            "notable_achievements": null
        }
    ]
    """

    try:
        print("\nExtracting executive information from filtered sections...")
        # import pdb; pdb.set_trace()
        # print("\nAPI Input:", combined_content)
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are an expert at extracting executive compensation and biographical information from SEC filings."},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "I will extract the executive information and return it in the requested JSON format."},
                {"role": "user", "content": f"Here's the content:\n\n{combined_content}"}
            ],
            temperature=0.1
        )

        print("\nAPI Response:", response.choices[0].message.content)
        content = response.choices[0].message.content.strip()

        # Remove markdown code block markers if present
        if content.startswith('```json'):
            content = content[7:]  # Remove ```json prefix
        if content.endswith('```'):
            content = content[:-3]  # Remove ``` suffix

        content = content.strip()
        result = json.loads(content)
        return result

    except Exception as e:
        print(f"\nError extracting executive information: {e}")
        return []


def init_db():
    """Initialize database with fresh tables for executive data"""
    db_path = 'def14a_filings/filings.db'

    with sqlite3.connect(db_path) as conn:
        # Clear existing tables if they exist
        conn.execute("DROP TABLE IF EXISTS executive_data")
        conn.execute("DROP TABLE IF EXISTS processing_status")

        # Create new tables
        conn.execute("""
            CREATE TABLE executive_data (
                cik TEXT,
                filing_date TEXT,
                exec_name TEXT,
                data JSON,
                last_updated TIMESTAMP,
                PRIMARY KEY (cik, filing_date, exec_name)
            )
        """)

        conn.execute("""
            CREATE TABLE processing_status (
                cik TEXT PRIMARY KEY,
                filing_date TEXT,
                status TEXT,
                error_msg TEXT,
                last_updated TIMESTAMP
            )
        """)

def identify_headings(content: str) -> List[Tuple[str, float]]:
    """Identify potential section headings using multiple heuristics"""
    soup = BeautifulSoup(content, 'html.parser')
    headings = []

    # Traditional heading tags
    for tag in ['h1', 'h2', 'h3']:
        for h in soup.find_all(tag):
            headings.append((h.get_text().strip(), 0.9))

    # CSS class-based detection
    heading_patterns = ['heading', 'title', 'header', 'section']
    for elem in soup.find_all(class_=re.compile('|'.join(heading_patterns), re.I)):
        headings.append((elem.get_text().strip(), 0.8))

    # Font style based detection
    for elem in soup.find_all(style=re.compile('(font-weight.*?bold|font-size.*?1[2-9]px)', re.I)):
        text = elem.get_text().strip()
        if len(text) < 100:
            headings.append((text, 0.7))

    # Text pattern detection
    for elem in soup.find_all(string=True):
        text = elem.strip()
        if text and len(text) < 100:
            if text.isupper() and len(text) > 10:
                headings.append((text, 0.6))
            elif text.endswith(':'):
                headings.append((text, 0.5))

    # Deduplicate and clean
    seen = set()
    unique_headings = []
    for text, score in headings:
        text = re.sub(r'\s+', ' ', text).strip()
        if text and text not in seen and len(text) < 200:
            seen.add(text)
            unique_headings.append((text, score))

    return unique_headings

def extract_sections(content: str, headings: List[Tuple[str, float]]) -> Dict[str, str]:
    """Extract sections using identified headings"""
    soup = BeautifulSoup(content, 'html.parser')
    sections = {}

    # Get all text elements
    text_elements = [elem.strip() for elem in soup.find_all(string=True) if elem.strip()]

    # Sort headings by confidence
    headings = sorted(headings, key=lambda x: x[1], reverse=True)

    for i, (heading, _) in enumerate(headings):
        try:
            start_idx = next(idx for idx, text in enumerate(text_elements)
                           if heading in text)

            # Find next heading
            end_idx = len(text_elements)
            for next_heading, _ in headings[i+1:]:
                try:
                    next_idx = next(idx for idx, text in enumerate(text_elements[start_idx+1:], start_idx+1)
                                  if next_heading in text)
                    if next_idx < end_idx:
                        end_idx = next_idx
                except StopIteration:
                    continue

            content = '\n'.join(text_elements[start_idx+1:end_idx])
            if len(content) > 100:
                sections[heading] = content

        except StopIteration:
            continue

    return sections

def get_compensation_section(sections: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Find relevant sections containing executive information"""
    relevant_sections = {}

    # Keywords for different types of information
    section_keywords = {
        'compensation': [
            'summary compensation table',
            'executive compensation',
            'compensation discussion',
            'director compensation'
        ],
        'biography': [
            'executive officers',
            'board of directors',
            'biographical information',
            'director nominees'
        ]
    }

    # Check each section
    for heading, content in sections.items():
        heading_lower = heading.lower()

        # Check if section contains tables
        has_tables = bool(BeautifulSoup(content, 'html.parser').find_all('table'))

        for category, keywords in section_keywords.items():
            if any(k in heading_lower for k in keywords) or \
               any(k in content.lower()[:1000] for k in keywords):
                if category == 'compensation' and not has_tables:
                    continue  # Skip compensation sections without tables
                relevant_sections[heading] = content

    return relevant_sections if relevant_sections else None

def process_companies():
    """Process all companies, only looking at their latest filing"""
    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )

    db_path = 'def14a_filings/filings.db'

    with sqlite3.connect(db_path) as conn:
        # Get latest filing for each company
        companies = conn.execute("""
            WITH latest_filings AS (
                SELECT f.cik, f.filing_date, f.file_path, c.name,
                       ROW_NUMBER() OVER (PARTITION BY f.cik ORDER BY f.filing_date DESC) as rn
                FROM filings f
                JOIN companies c ON f.cik = c.cik
                WHERE f.status = 'completed'
            )
            SELECT cik, name, filing_date, file_path
            FROM latest_filings
            WHERE rn = 1
            ORDER BY filing_date DESC
        """).fetchall()

        for cik, name, filing_date, file_path in companies:
            try:
                # Skip if already processed
                status = conn.execute(
                    "SELECT status FROM processing_status WHERE cik = ?",
                    (cik,)
                ).fetchone()

                if status and status[0] == 'completed':
                    print(f"Skipping {name} - already processed")
                    continue

                print(f"\nProcessing {name} (CIK: {cik})")

                # Read filing content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract sections using robust parsing
                headings = identify_headings(content)
                sections = extract_sections(content, headings)

                if not sections:
                    raise Exception("No sections found")

                relevant_sections = get_compensation_section(sections)
                if not relevant_sections:
                    raise Exception("No compensation section found")

                # Extract executive information
                executives = extract_executive_info(relevant_sections, client)
                if not executives:
                    raise Exception("No executive information extracted")

                # Store results
                for exec_data in executives:
                    conn.execute("""
                        INSERT OR REPLACE INTO executive_data
                        (cik, filing_date, exec_name, data, last_updated)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (cik, filing_date, exec_data['name'], json.dumps(exec_data)))

                # Mark as completed
                conn.execute("""
                    INSERT OR REPLACE INTO processing_status
                    (cik, filing_date, status, last_updated)
                    VALUES (?, ?, 'completed', CURRENT_TIMESTAMP)
                """, (cik, filing_date))
                conn.commit()

            except Exception as e:
                print(f"Error processing {name}: {str(e)}")
                conn.execute("""
                    INSERT OR REPLACE INTO processing_status
                    (cik, filing_date, status, error_msg, last_updated)
                    VALUES (?, ?, 'failed', ?, CURRENT_TIMESTAMP)
                """, (cik, filing_date, str(e)))
                conn.commit()

def main():
    """Main entry point"""
    try:
        print("Initializing database...")
        init_db()

        print("Processing companies...")
        process_companies()

    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
