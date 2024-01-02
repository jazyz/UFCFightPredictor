import requests
from bs4 import BeautifulSoup
import csv

def get_additional_links(url):
    # Initialize a dictionary to hold the date and links
    result = {'date': '', 'links': []}

    # Fetch the content from the URL
    response = requests.get(url)
    if response.status_code == 200:
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract the date from the relevant section
        date_section = soup.find('li', class_='b-list__box-list-item')
        if date_section and "Date:" in date_section.text:
            date_text = date_section.text.replace('Date:', '').strip()
            result['date'] = date_text  # Save the date into the result dictionary

        # Find all the links that contain 'fight-details'
        links = soup.find_all('a', href=True)
        fight_links = [link['href'] for link in links if 'fight-details' in link['href']]
        result['links'] = fight_links  # Save the additional links into the result dictionary

    # Return the dictionary with date and links
    return result

def get_embedded_links(url):
    # Fetch the main page content
    response = requests.get(url)
    if response.status_code == 200:
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all rows with links
        rows = soup.find_all('tr', class_='b-statistics__table-row')

        # Extract the embedded links and dates
        all_links_details = {}
        for row in rows:
            link = row.find('a', href=True)
            if link:
                href = link['href']
                additional_links_details = get_additional_links(href)
                # Store the additional links and date under each embedded link
                all_links_details[href] = additional_links_details

        return all_links_details
    else:
        return {}

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

is_header_required = True

def write_to_csv(fight_details, filename=r'data\fight_details_date.csv'):
    global is_header_required
    file_mode = 'w' if is_header_required else 'a'
    with open(filename, mode=file_mode, newline='') as file:
        writer = csv.writer(file)
        
        # Prepare headers only if it's required (for the first time)
        if is_header_required:
            headers = [
                'Title', 'Winner', 'Loser', 'Draw', 'Method', 'Round', 'Time', 'Time Format', 'Referee', 'Details', 'Date',
            ] + [f"Red {key}" for key in fight_details['Fighter 1 Stats'].keys()] + [f"Blue {key}" for key in fight_details['Fighter 2 Stats'].keys()]
            writer.writerow(headers)

        is_header_required=False        
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
            fi.get('Details', ''),
            fight_details.get('Date', ''),
        ] + list(fight_details['Fighter 1 Stats'].values()) + list(fight_details['Fighter 2 Stats'].values())

        # Write the combined row
        writer.writerow(row)

def process_fight_urls(all_links_details, filename=r'data\fight_details_date.csv'):
    for embedded_link, details in all_links_details.items():
        for fight_link in details['links']:
            fight_details = get_fight_details(fight_link)
            fight_details['Date'] = details['date']  # Add the date to fight details
            write_to_csv(fight_details, filename)

def read_and_print_csv(filename=r'data\fight_details_date.csv'):
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

# URL of the UFC statistics events
url = "http://ufcstats.com/statistics/events/completed?page=all"
all_links_details = get_embedded_links(url)
process_fight_urls(all_links_details)