import requests
import re
from bs4 import BeautifulSoup

def scrape_fighter_records(fighter_links):
    for link in fighter_links:
        response = requests.get(link, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            fighter_name = soup.find('h2', class_='b-content__title').get_text().strip()
            # print(fighter_name)
            name_match = re.search(r'^([^\n]+)', fighter_name)
            name = name_match.group(1).strip()
            record_match = re.search(r"Record: (\d+-\d+-\d+ \(.*\))", fighter_name)
            if not record_match:
                record_match = re.search(r'Record: (\d+-\d+-\d+)', fighter_name)
            record = record_match.group(1).strip()
            stats = soup.find_all('li', class_='b-list__box-list-item')
            fighter_stats = {'Name': name}
            fighter_stats['Record']=record

            physical_info = soup.find('ul', class_='b-list__box-list')
            if physical_info:
                info_items = physical_info.find_all('li', class_='b-list__box-list-item')
                physical_characteristics = {}

                for item in info_items:
                    label_elem = item.find('i', class_='b-list__box-item-title b-list__box-item-title_type_width')
                    if label_elem:
                        value_elem = label_elem.next_sibling
                        value = value_elem.text.strip() if value_elem else ""
                        label = label_elem.text.strip()
                        label = label.replace(":", "")
                        physical_characteristics[label] = value
            fighter_stats.update(physical_characteristics)
            for stat in stats:
                label = ""
                value = ""
                if stat.find('i', class_='b-list__box-item-title b-list__box-item-title_font_lowercase b-list__box-item-title_type_width') is not None:
                    label = stat.find('i', class_='b-list__box-item-title b-list__box-item-title_font_lowercase b-list__box-item-title_type_width').get_text().strip()
                    stat_elem = stat.find('i', class_='b-list__box-item-title b-list__box-item-title_font_lowercase b-list__box-item-title_type_width')
                    if stat_elem:
                        value = stat_elem.next_sibling.strip()
                    label=label.replace(":","")
                    fighter_stats[label] = value
            
            fights_table = soup.find('table', class_='b-fight-details__table')
            if fights_table:
                rows = fights_table.find_all('tr', class_='b-fight-details__table-row__hover')
                fight_history = []

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) > 1:
                        fight_info = {
                            "result": cols[0].find('a').text.strip(),
                            "opponent": cols[1].find_all('a')[1].text.strip(),
                            "KD": cols[2].find('p').text.strip(),
                            "STR": cols[3].find('p').text.strip(),
                            "TD": cols[4].find('p').text.strip(),
                            "SUB": cols[5].find('p').text.strip(),
                            "event": cols[6].find('a').text.strip(),
                            "date": cols[6].find_next('p').find_next('p').text.strip(),
                            "method": cols[7].find('p').text.strip(),
                            "round": cols[8].find('p').text.strip(),
                            "time": cols[9].find('p').text.strip(),
                        }
                        fight_history.append(fight_info)
                        
            if fighter_name:
                for label, value in fighter_stats.items():
                    print(f"{label}: {value}")
                print("Fight History:")
                for fight in fight_history:
                    print(f"Result: {fight['result']}, Opponent: {fight['opponent']}, Event: {fight['event']}, Date: {fight['date']}, Method: {fight['method']}, KD: {fight['KD']}, STR: {fight['STR']}, TD: {fight['TD']}, SUB: {fight['SUB']}")
                print("=" * 20)

def scrape_ufc_fighters_by_char(character):
    url = f"http://ufcstats.com/statistics/fighters?char={character}&page=1"
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        fighters_table = soup.find('table', class_='b-statistics__table')

        fighter_links = []
        if fighters_table:
            rows = fighters_table.find_all('tr')

            for row in rows[1:]:
                cols = row.find_all('td')
                if len(cols) > 1:
                    fighter_link = cols[1].find('a')['href']
                    fighter_links.append(fighter_link)

        return fighter_links
    else:
        print(f"Failed to fetch data for character '{character}' from the website.")
        return None

if __name__ == "__main__":
    all_characters = "a"
    all_fighter_links = []

    for char in all_characters:
        fighter_links = scrape_ufc_fighters_by_char(char)
        if fighter_links:
            all_fighter_links.extend(fighter_links)

    if all_fighter_links:
        print("Scraping fighter records...")
        scrape_fighter_records(all_fighter_links)
        print("Done")
    else:
        print("Scraping failed.")
