import csv
import json
import sqlite3
from typing import Dict, List

from schema import Education, Executive


def dump_to_csv(output_file: str = 'executives.csv'):
    """Dump executive data to CSV with expanded education fields"""

    db_path = 'def14a_filings/filings.db'

    with sqlite3.connect(db_path) as conn:
        # Get all executive records with company names
        rows = conn.execute("""
            SELECT c.name as company_name, e.cik, e.filing_date, e.data
            FROM executive_data e
            JOIN companies c ON e.cik = c.cik
            ORDER BY c.name, e.filing_date DESC
        """).fetchall()

        if not rows:
            print("No executive data found")
            return

        # Define base fieldnames
        fieldnames = [
            'company_name', 'cik', 'filing_date',
            'name', 'age', 'current_role',
            'past_roles', 'compensation_salary',
            'compensation_stock', 'compensation_bonus',
            'compensation_other', 'compensation_total',
            'compensation_year', 'start_date',
            'board_member', 'committee_memberships',
            'other_board_memberships', 'notable_achievements',
            # Add education fields for up to 3 degrees
            'education1_degree', 'education1_field', 'education1_university', 'education1_year',
            'education2_degree', 'education2_field', 'education2_university', 'education2_year',
            'education3_degree', 'education3_field', 'education3_university', 'education3_year'
        ]

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for company_name, cik, filing_date, data_json in rows:
                data = json.loads(data_json)

                # Convert lists to strings
                past_roles = '; '.join(data.get('past_roles', []))
                committee_memberships = '; '.join(data.get('committee_memberships', []))
                other_board_memberships = '; '.join(data.get('other_board_memberships', []))

                # Base row data
                row = {
                    'company_name': company_name,
                    'cik': cik,
                    'filing_date': filing_date,
                    'name': data.get('name'),
                    'age': data.get('age'),
                    'current_role': data.get('current_role'),
                    'past_roles': past_roles,
                    'compensation_salary': data.get('compensation_salary'),
                    'compensation_stock': data.get('compensation_stock'),
                    'compensation_bonus': data.get('compensation_bonus'),
                    'compensation_other': data.get('compensation_other'),
                    'compensation_total': data.get('compensation_total'),
                    'compensation_year': data.get('compensation_year'),
                    'start_date': data.get('start_date'),
                    'board_member': data.get('board_member'),
                    'committee_memberships': committee_memberships,
                    'other_board_memberships': other_board_memberships,
                    'notable_achievements': data.get('notable_achievements')
                }

                # Add education data
                education_list = data.get('education', [])
                for i, edu in enumerate(education_list[:3], 1):  # Limit to 3 degrees
                    row.update({
                        f'education{i}_degree': edu.get('degree'),
                        f'education{i}_field': edu.get('field'),
                        f'education{i}_university': edu.get('university'),
                        f'education{i}_year': edu.get('year')
                    })

                writer.writerow(row)

        print(f"Wrote {len(rows)} executives to {output_file}")

if __name__ == "__main__":
    dump_to_csv()
