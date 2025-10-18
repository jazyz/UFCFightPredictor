"""
Incremental UFC Fight Scraper
Scrapes only new fights since the last update date in fight_details_date.csv
"""
import requests
from bs4 import BeautifulSoup
import csv
import os
from datetime import datetime
import pandas as pd


def get_last_scraped_date(csv_path='data/fight_details_date.csv'):
    """
    Read the most recent fight date from existing CSV.
    Returns: datetime object of the last scraped date, or None if file doesn't exist
    """
    if not os.path.exists(csv_path):
        print(f"No existing data found at {csv_path}. Will scrape all fights.")
        return None
    
    try:
        df = pd.read_csv(csv_path)
        if df.empty or 'Date' not in df.columns:
            return None
        
        # Parse dates and find the most recent
        df['Date'] = pd.to_datetime(df['Date'], format='%B %d, %Y')
        last_date = df['Date'].max()
        print(f"Last scraped date: {last_date.strftime('%B %d, %Y')}")
        return last_date
    except Exception as e:
        print(f"Error reading last date: {e}")
        return None


def parse_event_date(date_str):
    """Convert date string to datetime object"""
    try:
        return datetime.strptime(date_str, '%B %d, %Y')
    except:
        return None


def get_event_details(url):
    """Extract event date and fight links from an event page"""
    result = {'date': '', 'links': []}
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract the date
            date_section = soup.find('li', class_='b-list__box-list-item')
            if date_section and "Date:" in date_section.text:
                date_text = date_section.text.replace('Date:', '').strip()
                result['date'] = date_text
            
            # Find all fight detail links
            links = soup.find_all('a', href=True)
            fight_links = [link['href'] for link in links if 'fight-details' in link['href']]
            result['links'] = fight_links
            
        return result
    except Exception as e:
        print(f"Error fetching event details from {url}: {e}")
        return result


def get_new_events(last_date=None):
    """
    Fetch only new events since last_date from UFC stats.
    If last_date is None, fetches all events.
    """
    url = "http://ufcstats.com/statistics/events/completed?page=all"
    new_events = {}
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch events list: status {response.status_code}")
            return new_events
        
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr', class_='b-statistics__table-row')
        
        print(f"Found {len(rows)} total events on page")
        
        for row in rows:
            link = row.find('a', href=True)
            if link:
                href = link['href']
                # Get event details (date + fight links)
                event_details = get_event_details(href)
                
                if event_details['date']:
                    event_date = parse_event_date(event_details['date'])
                    
                    # Only include events AFTER the last scraped date
                    if last_date is None or (event_date and event_date > last_date):
                        new_events[href] = event_details
                        print(f"  ✓ New event: {event_details['date']} ({len(event_details['links'])} fights)")
                    elif event_date and event_date <= last_date:
                        # Since events are in reverse chronological order, we can stop
                        print(f"  ✗ Reached already-scraped date: {event_details['date']}")
                        break
        
        print(f"\nTotal new events to scrape: {len(new_events)}")
        return new_events
        
    except Exception as e:
        print(f"Error fetching events: {e}")
        return new_events


def get_fight_details(url):
    """Scrape detailed statistics for a single fight"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return {"Error": f"Failed to retrieve fight data, status code {response.status_code}"}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        fight_info = {}
        
        # Fight title
        fight_title = soup.find('i', class_='b-fight-details__fight-title')
        if fight_title:
            fight_info['Title'] = fight_title.get_text(strip=True)
        
        # Fight details (method, round, time, etc.)
        fight_details = soup.find('div', class_='b-fight-details__content')
        if fight_details:
            detail_items = fight_details.find_all('p', class_='b-fight-details__text')
            for detail in detail_items:
                items = detail.find_all('i')
                for item in items:
                    label = item.find('i', class_='b-fight-details__label')
                    if label:
                        label_text = label.get_text(strip=True).rstrip(':')
                        value = item.get_text(strip=True).replace(label_text + ":", '').strip()
                        fight_info[label_text] = value
        
        # Fighter names and results
        fighters = soup.find_all('div', class_='b-fight-details__person')
        winner = loser = None
        draw = False
        
        for fighter in fighters:
            status_elem = fighter.find('i', class_='b-fight-details__person-status')
            name_elem = fighter.find('h3', class_='b-fight-details__person-name')
            
            if status_elem and name_elem:
                status = status_elem.get_text().strip()
                name = name_elem.get_text().strip()
                
                if status == 'W':
                    winner = name
                elif status == 'L':
                    loser = name
                elif status == 'D':
                    draw = True
        
        # Fighter statistics tables
        tables = soup.find_all('tbody', class_='b-fight-details__table-body')
        fighter1_stats = {}
        fighter2_stats = {}
        
        for table_body in tables:
            fighter1_data = []
            fighter2_data = []
            
            # Get headers
            thead = table_body.find_previous('thead')
            if thead:
                headers = [th.get_text(strip=True) for th in thead.find_all('th')]
                
                # Get data rows
                for row in table_body.find_all('tr', class_='b-fight-details__table-row'):
                    cells = row.find_all('td', class_='b-fight-details__table-col')
                    for cell in cells:
                        paragraphs = cell.find_all('p', class_='b-fight-details__table-text')
                        fighter1_data.append(paragraphs[0].get_text(strip=True) if paragraphs else '')
                        fighter2_data.append(paragraphs[1].get_text(strip=True) if len(paragraphs) > 1 else '')
                
                # Merge stats from multiple tables
                fighter1 = {header: data for header, data in zip(headers, fighter1_data)}
                fighter2 = {header: data for header, data in zip(headers, fighter2_data)}
                
                fighter1_stats.update(fighter1)
                fighter2_stats.update(fighter2)
        
        return {
            "Winner": winner,
            "Loser": loser,
            "Draw": draw,
            "Fight Info": fight_info,
            "Fighter 1 Stats": fighter1_stats,
            "Fighter 2 Stats": fighter2_stats
        }
        
    except Exception as e:
        return {"Error": str(e)}


def append_fight_to_csv(fight_details, filename='data/fight_details_date.csv'):
    """
    Append a single fight to the CSV file.
    Creates file with headers if it doesn't exist.
    """
    file_exists = os.path.exists(filename)
    
    try:
        with open(filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # Write header if this is a new file
            if not file_exists:
                headers = [
                    'Title', 'Winner', 'Loser', 'Draw', 'Method', 'Round', 'Time', 
                    'Time Format', 'Referee', 'Details', 'Date',
                ] + [f"Red {key}" for key in fight_details['Fighter 1 Stats'].keys()] + \
                    [f"Blue {key}" for key in fight_details['Fighter 2 Stats'].keys()]
                writer.writerow(headers)
            
            # Prepare row data
            fi = fight_details['Fight Info']
            row = [
                fi.get('Title', ''),
                fight_details.get('Winner', ''),
                fight_details.get('Loser', ''),
                fight_details.get('Draw', ''),
                fi.get('Method', ''),
                fi.get('Round', ''),
                fi.get('Time', ''),
                fi.get('Time Format', ''),
                fi.get('Referee', ''),
                fi.get('Details', ''),
                fight_details.get('Date', ''),
            ] + list(fight_details['Fighter 1 Stats'].values()) + \
                list(fight_details['Fighter 2 Stats'].values())
            
            writer.writerow(row)
            
    except Exception as e:
        print(f"Error writing to CSV: {e}")


def scrape_new_fights(last_date=None):
    """
    Main function to scrape only new fights since last_date.
    Returns: number of new fights scraped
    """
    print("\n" + "="*60)
    print("Starting Incremental UFC Fight Scraper")
    print("="*60)
    
    # Get events that are newer than last_date
    new_events = get_new_events(last_date)
    
    if not new_events:
        print("\n✓ No new fights to scrape. Database is up to date!")
        return 0
    
    total_fights = 0
    
    # Process each new event
    for event_url, event_details in new_events.items():
        print(f"\nProcessing event: {event_details['date']}")
        
        for i, fight_url in enumerate(event_details['links'], 1):
            try:
                print(f"  Scraping fight {i}/{len(event_details['links'])}...", end=" ")
                fight_details = get_fight_details(fight_url)
                
                if "Error" not in fight_details:
                    fight_details['Date'] = event_details['date']
                    append_fight_to_csv(fight_details)
                    total_fights += 1
                    print("✓")
                else:
                    print(f"✗ {fight_details['Error']}")
                    
            except Exception as e:
                print(f"✗ Error: {e}")
    
    print(f"\n{'='*60}")
    print(f"✓ Successfully scraped {total_fights} new fights!")
    print(f"{'='*60}\n")
    
    return total_fights


if __name__ == "__main__":
    # Get the last scraped date
    last_date = get_last_scraped_date()
    
    # Scrape only new fights
    scrape_new_fights(last_date)
