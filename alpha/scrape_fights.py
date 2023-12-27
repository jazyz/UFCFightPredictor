import requests
from bs4 import BeautifulSoup
import csv

def merge_dicts(d1, d2):
    result = d1.copy()  # Start with keys and values of the first dictionary
    for key, value in d2.items():
        if key not in result:
            result[key] = value
    return result

def get_fight_details(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            fight_info = {}
            fight_title = soup.find('i', class_='b-fight-details__fight-title').get_text(strip=True)
            fight_info['Title'] = fight_title

            fight_details = soup.find('div', class_='b-fight-details__content').find_all('p', class_='b-fight-details__text')
            for detail in fight_details:
                items = detail.find_all('i')
                for item in items:
                    label = item.find('i', class_='b-fight-details__label')
                    if label:
                        label_text = label.get_text(strip=True).rstrip(':')
                        value = item.get_text(strip=True).replace(label_text + ":", '').strip()
                        fight_info[label_text] = value

            fighters = soup.find_all('div', class_='b-fight-details__person')
            winner = loser = None
            draw = False
            for fighter in fighters:
                status = fighter.find('i', class_='b-fight-details__person-status').get_text().strip()
                name = fighter.find('h3', class_='b-fight-details__person-name').get_text().strip()
                if status == 'W':
                    winner = name
                elif status == 'L':
                    loser = name
                elif status == 'D':
                    draw=True

            tables = soup.find_all('tbody', class_='b-fight-details__table-body')
            fighter1_stats = {}
            fighter2_stats = {}

            for table_body in tables:
                fighter1_data = []
                fighter2_data = []
                headers = [th.get_text(strip=True) for th in table_body.find_previous('thead').find_all('th')]
                for row in table_body.find_all('tr', class_='b-fight-details__table-row'):
                    cells = row.find_all('td', class_='b-fight-details__table-col')
                    for cell in cells:
                        paragraphs = cell.find_all('p', class_='b-fight-details__table-text')
                        fighter1_data.append(paragraphs[0].get_text(strip=True) if paragraphs else '')
                        fighter2_data.append(paragraphs[1].get_text(strip=True) if len(paragraphs) > 1 else '')

                fighter1 = {header: data for header, data in zip(headers, fighter1_data)}
                fighter2 = {header: data for header, data in zip(headers, fighter2_data)}
                fighter1_stats = merge_dicts(fighter1_stats, fighter1)
                fighter2_stats = merge_dicts(fighter2_stats, fighter2)

            return {
                "Winner": winner,
                "Loser": loser,
                "Draw": draw,
                "Fight Info": fight_info,
                "Fighter 1 Stats": fighter1_stats,
                "Fighter 2 Stats": fighter2_stats
            }
        else:
            return {"Error": f"Failed to retrieve data, status code {response.status_code}"}
    except Exception as e:
        return {"Error": str(e)}

def write_to_csv(fight_details, filename='fight_details.csv', is_header_required=True):
    file_mode = 'w' if is_header_required else 'a'
    with open(filename, mode=file_mode, newline='') as file:
        writer = csv.writer(file)
        
        # Prepare headers only if it's required (for the first time)
        if is_header_required:
            headers = [
                'Title', 'Winner', 'Loser', 'Draw', 'Method', 'Round', 'Time', 'Time Format', 'Referee', 'Details'
            ] + [f"Red {key}" for key in fight_details['Fighter 1 Stats'].keys()] + [f"Blue {key}" for key in fight_details['Fighter 2 Stats'].keys()]
            writer.writerow(headers)
        
        # Prepare fight info for easier access
        fi = fight_details['Fight Info']
        
        # Prepare row with fight info and both fighters' stats
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
            fi.get('Details', '')
        ] + list(fight_details['Fighter 1 Stats'].values()) + list(fight_details['Fighter 2 Stats'].values())

        # Write the combined row
        writer.writerow(row)

def process_fight_urls(url_list, filename='fight_details.csv'):
    # Write details for each URL
    for i, url in enumerate(url_list):
        fight_details = get_fight_details(url)
        write_to_csv(fight_details, filename, is_header_required=(i==0))  # Header only for the first one

def read_and_print_csv(filename='fight_details.csv'):
    with open(filename, mode='r', newline='') as file:
        reader = csv.reader(file)
        
        # Read the header
        headers = next(reader, None)
        if headers:
            print("Fight Details:")
            print("-" * 100)
        
        # Read and print each row of the CSV file
        for row in reader:
            for header, value in zip(headers, row):
                print(f"{header}: {value}")
            print("-" * 100)  # Separator for each fight

urls=["http://ufcstats.com/fight-details/f2b407019b2a5c15"]
process_fight_urls(urls)
read_and_print_csv()
