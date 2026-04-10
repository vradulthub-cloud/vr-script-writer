"""
add_profile_columns.py

Adds profile columns (Height, Weight, Measurements, Hair, Eyes, Natural Breasts,
Tattoos, Shoe Size, Available For) to every agency tab in the Model Booking List,
then fills in data scraped manually from the agency profile pages.

Usage:
    python3 /Users/andrewninn/Scripts/add_profile_columns.py
"""

import gspread
from google.oauth2.service_account import Credentials
import os

SPREADSHEET_ID = '1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw'
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'service_account.json')

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

NEW_HEADERS = [
    'Height', 'Weight', 'Measurements', 'Hair', 'Eyes',
    'Natural Breasts', 'Tattoos', 'Shoe Size', 'Available For'
]

# Profile data from agency website screenshots
# Keys match NEW_HEADERS exactly
PROFILES = [
    {
        'tab': 'OC Models', 'name': 'Addis Fouche',
        'Height': "5'5\"", 'Weight': '125 lbs', 'Measurements': '32B',
        'Hair': 'Brown', 'Eyes': 'Brown', 'Natural Breasts': 'Yes',
        'Tattoos': 'Yes', 'Shoe Size': '7-7.5',
        'Available For': 'ATM, BJ, BBG, BG, BGG, BG Anal, BBG Anal, BGG Anal, Creampie, Deep Throat, Fetish, Foot Jobs, Gang Bang, GG, GG Anal, GGG, HJ, Interracial, Load Dumping, Milf, Orgy, Petite, Rimming, Solo, Solo w/Toys, Squirt, Swallow, Bondage, Blow Bangs',
    },
    {
        'tab': 'Hussie Models', 'name': 'Adriana Maya',
        'Height': "5'7\"", 'Weight': '138 lbs', 'Measurements': '32B',
        'Hair': '', 'Eyes': '', 'Natural Breasts': '',
        'Tattoos': 'Yes', 'Shoe Size': '10',
        'Available For': 'Anal, BBGG, BG, BGB, BJ, Blow Bang, Bondage, Creampie, Deep Throat, DP, Facial, Fetish, Gang Bang, GBG, GG, GGA, Group, HJ, Solo, Swallow, Taboo, Toys',
    },
    {
        'tab': 'Nexxxt Level', 'name': 'Diana Grace',
        'Height': "5'5\"", 'Weight': '125 lbs', 'Measurements': '34-24-34',
        'Hair': '', 'Eyes': '', 'Natural Breasts': '',
        'Tattoos': '', 'Shoe Size': '7',
        'Available For': 'Solo, GG, BJ/HJ, Swallow/Facial, Deep Throat, BG, BGG, BBG, Taboo/Incest, Light Fetish, Foot Fetish, Group, ATM, Incorporated, Mainstream, Anal',
    },
    {
        'tab': 'Foxxx Modeling', 'name': 'Ali Jones',
        'Height': "5'5\"", 'Weight': '100 lbs', 'Measurements': '32A',
        'Hair': '', 'Eyes': '', 'Natural Breasts': 'Yes',
        'Tattoos': '', 'Shoe Size': '8',
        'Available For': 'ATM, BG, BBG, BGG, Blowbang, BJ, Bondage, Creampie, Deep Throat, DV, Femdom, Fetish, GG, Gang Bang, Interracial, Orgy, Rimming, Solo, Squirt',
    },
    {
        'tab': 'Zen Models', 'name': 'Adriana Chechik',
        'Height': "5'4\"", 'Weight': '', 'Measurements': '32C',
        'Hair': 'Dark Brown', 'Eyes': 'Green', 'Natural Breasts': '',
        'Tattoos': '', 'Shoe Size': '7',
        'Available For': 'GG, BG, BGG, BBG, IR, Fetish, Rimming, Anal',
    },
    {
        'tab': '101 Models', 'name': 'Alina Voss',
        'Height': "5'5\"", 'Weight': '', 'Measurements': '30B-26-34',
        'Hair': '', 'Eyes': '', 'Natural Breasts': '',
        'Tattoos': '', 'Shoe Size': '',
        'Available For': 'Solo, Solo Stills, Solo Video, BJ, HJ, GG, BG, Anal, Swallow, Facial, Squirt, Fetish',
    },
    {
        'tab': 'Coxxx Models', 'name': 'Agatha Delicious',
        'Height': "5'8\"", 'Weight': '127 lbs', 'Measurements': '34C',
        'Hair': '', 'Eyes': '', 'Natural Breasts': '',
        'Tattoos': '', 'Shoe Size': '',
        'Available For': 'Appearances, Stills, Solo, BG, GG, Fetish, BJ, HJ, Foot Job, Deep Throat, Swallow, Facial, Anal, Gang Bang, Bukkake',
    },
    {
        'tab': 'ATMLA', 'name': 'Aaliyah Love',
        'Height': "5'2\"", 'Weight': '106 lbs', 'Measurements': '32A-22-34',
        'Hair': 'Blonde', 'Eyes': 'Hazel', 'Natural Breasts': 'Yes',
        'Tattoos': 'No', 'Shoe Size': '6',
        'Available For': 'BJ, Creampie, GG, Solo, BBG, Fetish, Milf, Swallow, BG, Flexible, Rim Job (GG Only), BGG, GG Anal',
    },
    {
        'tab': 'The Model Service', 'name': 'Baby Gemini',
        'Height': "5'7\"", 'Weight': '135 lbs', 'Measurements': '',
        'Hair': '', 'Eyes': '', 'Natural Breasts': '',
        'Tattoos': '', 'Shoe Size': '',
        'Available For': 'GG, BG, BGG, BBG',
    },
    {
        'tab': 'East Coast Talent', 'name': 'Amber Summer',
        'Height': "4'9\"", 'Weight': '80 lbs', 'Measurements': '',
        'Hair': '', 'Eyes': '', 'Natural Breasts': '',
        'Tattoos': '', 'Shoe Size': '',
        'Available For': 'BJ/HJ, Blow Bangs, BBG, BG, BGG, Creampie, Fetish, GG, Group, Solo, Squirt',
    },
    {
        'tab': 'The Bakery Talent', 'name': 'Agatha Vega',
        'Height': "5'5\"", 'Weight': '', 'Measurements': '34B-30-38',
        'Hair': 'Strawberry Blonde', 'Eyes': 'Brown', 'Natural Breasts': '',
        'Tattoos': '', 'Shoe Size': '6.5',
        'Available For': 'BG, GG, BGG, BBG',
    },
    {
        'tab': 'Invision Models', 'name': 'August Skye',
        'Height': "5'8\"", 'Weight': '', 'Measurements': '36DD',
        'Hair': 'Black', 'Eyes': 'Brown', 'Natural Breasts': '',
        'Tattoos': '', 'Shoe Size': '9',
        'Available For': 'BG, BBB, BGG, GG, Group, VR, Kink, Fetish, Milf, Squirt, Spanish Speaker',
    },
]


def get_client():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def find_notes_col(headers):
    """Return 0-indexed position of Notes column, or -1 if not found."""
    for i, h in enumerate(headers):
        if str(h).strip().lower() == 'notes':
            return i
    return -1


def add_columns_to_all_tabs(ss):
    print("\n=== STEP 1: Adding profile columns to all tabs ===")
    for sheet in ss.worksheets():
        name = sheet.title
        try:
            headers = sheet.row_values(3)
        except Exception as e:
            print(f"  [SKIP] {name}: could not read row 3 ({e})")
            continue

        notes_idx = find_notes_col(headers)
        if notes_idx == -1:
            print(f"  [SKIP] {name}: no Notes column found")
            continue

        # Check if already added
        if 'Height' in headers:
            print(f"  [SKIP] {name}: profile columns already exist")
            continue

        notes_col_1indexed = notes_idx + 1  # gspread uses 1-indexed

        # Insert 9 blank columns before Notes
        sheet.insert_cols([[] for _ in range(9)], col=notes_col_1indexed)

        # Write headers into row 3 at the new columns
        header_range = sheet.range(3, notes_col_1indexed, 3, notes_col_1indexed + 8)
        for i, cell in enumerate(header_range):
            cell.value = NEW_HEADERS[i]
        sheet.update_cells(header_range)

        print(f"  [OK] {name}: inserted 9 columns before Notes (was col {notes_col_1indexed})")

    print("Done adding columns.\n")


def fill_profile_data(ss):
    print("=== STEP 2: Filling in profile data ===")
    for profile in PROFILES:
        tab_name = profile['tab']
        model_name = profile['name']

        sheet = ss.worksheet(tab_name)
        if not sheet:
            print(f"  [MISS] Tab not found: {tab_name}")
            continue

        # Get headers from row 3
        headers = sheet.row_values(3)
        col_map = {str(h).strip(): i + 1 for i, h in enumerate(headers)}  # 1-indexed

        # Find model row by name
        all_names = sheet.col_values(col_map.get('Name', 1))
        model_row = None
        for i, n in enumerate(all_names):
            if str(n).strip().lower() == model_name.lower():
                model_row = i + 1  # 1-indexed
                break

        if not model_row:
            print(f"  [MISS] {model_name} not found in {tab_name}")
            continue

        # Write each field
        updates = []
        for field in NEW_HEADERS:
            value = profile.get(field, '')
            if value and field in col_map:
                updates.append({
                    'range': gspread.utils.rowcol_to_a1(model_row, col_map[field]),
                    'values': [[value]]
                })

        if updates:
            sheet.batch_update(updates)
            print(f"  [OK] {model_name} ({tab_name}) — {len(updates)} fields written")
        else:
            print(f"  [SKIP] {model_name} ({tab_name}) — no data or columns not found")

    print("Done filling profiles.\n")


def main():
    print("Connecting to Google Sheets...")
    gc = get_client()
    ss = gc.open_by_key(SPREADSHEET_ID)
    print(f"Opened: {ss.title}\n")

    add_columns_to_all_tabs(ss)
    fill_profile_data(ss)

    print("All done! Open the sheet to review the new profile columns.")


if __name__ == '__main__':
    main()
