import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI


@dataclass
class Education:
    degree: str
    field: str
    university: str
    year: Optional[int] = None

@dataclass
class Executive:
    name: str
    age: Optional[int]
    current_role: str
    past_roles: List[str]
    education: List[Education]
    compensation_salary: float
    compensation_stock: float
    compensation_bonus: float
    compensation_other: float
    compensation_total: float
    compensation_year: int
    start_date: Optional[str]
    board_member: bool
    committee_memberships: List[str]
    other_board_memberships: List[str]
    notable_achievements: Optional[str]

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
        print("\nAPI Input:", combined_content)
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

def test_parser():
    """Test the parser with Apple"""
    load_dotenv()
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )

    cik = '0000320193'  # Apple
    print(f"\nProcessing Apple (CIK: {cik})")

    content = get_latest_def14a(cik)
    if content:
        # Extract all major sections
        sections = extract_major_sections(content)

        if sections:
            # Filter for relevant sections
            relevant_sections = filter_relevant_sections(sections, client)

            # Extract executive information from filtered sections
            if relevant_sections:
                executives = extract_executive_info(relevant_sections, client)
                print("\nExtracted executive information:")
                print(json.dumps(executives, indent=2))
            else:
                print("No relevant sections found after filtering")
        else:
            print("No sections found in filing")
    else:
        print("No filing found")

if __name__ == "__main__":
    test_parser()
