
import requests
import re
from bs4 import BeautifulSoup
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///detailedfighters.db'
db = SQLAlchemy(app)

class Fighter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    record = db.Column(db.String)
    SLpM = db.Column(db.Float)
    Str_Acc = db.Column(db.String)
    SApM = db.Column(db.Float)
    Str_Def = db.Column(db.String)
    TD_Avg = db.Column(db.Float)
    TD_Acc = db.Column(db.String)
    TD_Def = db.Column(db.String)
    Sub_Avg = db.Column(db.Float)
    Height = db.Column(db.String)
    Weight = db.Column(db.String)
    Reach = db.Column(db.String)
    Stance = db.Column(db.String)
    DOB = db.Column(db.String)

    fights = db.relationship('Fight', back_populates='fighter')

class Fight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fighter_id = db.Column(db.Integer, db.ForeignKey('fighter.id'))
    result = db.Column(db.String)
    opponent = db.Column(db.String)
    fighterKD = db.Column(db.String)
    fighterSTR = db.Column(db.String)
    fighterTD = db.Column(db.String)
    fighterSUB = db.Column(db.String)
    opponentKD = db.Column(db.String)
    opponentSTR = db.Column(db.String)
    opponentTD = db.Column(db.String)
    opponentSUB = db.Column(db.String)
    titlefight = db.Column(db.Boolean)
    event = db.Column(db.String)
    date = db.Column(db.String)
    method = db.Column(db.String)
    round = db.Column(db.String)
    time = db.Column(db.String)

    fighter = db.relationship('Fighter', back_populates='fights')

def scrape_fighter_records(fighter_links):
    for link in fighter_links:
        response = requests.get(link, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            fighter_name = soup.find('h2', class_='b-content__title').get_text().strip()
            name_match = re.search(r'^([^\n]+)', fighter_name)
            name = name_match.group(1).strip()
            record_match = re.search(r"Record: (\d+-\d+-\d+ \(.*\))", fighter_name)
            if not record_match:
                record_match = re.search(r'Record: (\d+-\d+-\d+)', fighter_name)
            record = record_match.group(1).strip()

            fighter_stats = {'name': name, 'record': record}

            key_mapping = {
                'SLpM': 'SLpM',
                'Str. Acc.': 'Str_Acc',
                'SApM': 'SApM',
                'Str. Def': 'Str_Def',
                'TD Avg.': 'TD_Avg',
                'TD Acc.': 'TD_Acc',
                'TD Def.': 'TD_Def',
                'Sub. Avg.': 'Sub_Avg',
                'Height': 'Height',
                'Weight': 'Weight',
                'Reach': 'Reach',
                'STANCE': 'Stance',
                'DOB': 'DOB'
            }

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
                        if label == "STANCE":
                            label = label.title()
                        if label in key_mapping:
                            physical_characteristics[key_mapping[label]] = value

                fighter_stats.update(physical_characteristics)

            stats = soup.find_all('li', class_='b-list__box-list-item')
            for stat in stats:
                label = ""
                value = ""
                if stat.find('i', class_='b-list__box-item-title b-list__box-item-title_font_lowercase b-list__box-item-title_type_width') is not None:
                    label = stat.find('i', class_='b-list__box-item-title b-list__box-item-title_font_lowercase b-list__box-item-title_type_width').get_text().strip()
                    stat_elem = stat.find('i', class_='b-list__box-item-title b-list__box-item-title_font_lowercase b-list__box-item-title_type_width')
                    if stat_elem:
                        value = stat_elem.next_sibling.strip()
                    label = label.replace(":", "")
                    if label in key_mapping:
                        fighter_stats[key_mapping[label]] = value

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
                            "fighterKD": cols[2].find_all('p')[0].text.strip(),
                            "opponentKD": cols[2].find_all('p')[1].text.strip(),
                            "fighterSTR": cols[3].find_all('p')[0].text.strip(),
                            "opponentSTR": cols[3].find_all('p')[1].text.strip(),
                            "fighterTD": cols[4].find_all('p')[0].text.strip(),
                            "opponentTD": cols[4].find_all('p')[1].text.strip(),
                            "fighterSUB": cols[5].find_all('p')[0].text.strip(),
                            "opponentSUB": cols[5].find_all('p')[1].text.strip(),
                            "event": cols[6].find('a').text.strip(),
                            "date": cols[6].find_next('p').find_next('p').text.strip(),
                            "titlefight": cols[6].find_next('p').find_next('p').find('img')!=None,
                            "method": cols[7].find('p').text.strip(),
                            "round": cols[8].find('p').text.strip(),
                            "time": cols[9].find('p').text.strip(),
                        }
                        fight_history.append(fight_info)

                fighter_stats['fights'] = [Fight(**fight) for fight in fight_history]
            fighter_instance = Fighter(**fighter_stats)
            # print(fighter_stats)
            print(name)
            with app.app_context():
                db.session.add(fighter_instance)
                db.session.commit()

def scrape_ufc_fighters_by_char(character):
    url = f"http://ufcstats.com/statistics/fighters?char={character}&page=all"
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

def write_fighter_details_to_file(fighter, file):
    file.write("Fighter Details:\n")
    file.write(f"Name: {fighter.name}\n")
    file.write(f"Record: {fighter.record}\n")
    file.write(f"SLpM: {fighter.SLpM}\n")
    file.write(f"Str_Acc: {fighter.Str_Acc}\n")
    file.write(f"SApM: {fighter.SApM}\n")
    file.write(f"Str_Def: {fighter.Str_Def}\n")
    file.write(f"TD_Avg: {fighter.TD_Avg}\n")
    file.write(f"TD_Acc: {fighter.TD_Acc}\n")
    file.write(f"TD_Def: {fighter.TD_Def}\n")
    file.write(f"Sub_Avg: {fighter.Sub_Avg}\n")
    file.write(f"Height: {fighter.Height}\n")
    file.write(f"Weight: {fighter.Weight}\n")
    file.write(f"Reach: {fighter.Reach}\n")
    file.write(f"Stance: {fighter.Stance}\n")
    file.write(f"DOB: {fighter.DOB}\n")

    file.write("Fight History:\n")
    for fight in fighter.fights:
        file.write(f"Opponent: {fight.opponent}\n")
        file.write(f"Result: {fight.result}\n")
        file.write(f"fighterKD: {fight.fighterKD}\n")
        file.write(f"fighterSTR: {fight.fighterSTR}\n")
        file.write(f"fighterTD: {fight.fighterTD}\n")
        file.write(f"fighterSUB: {fight.fighterSUB}\n")
        file.write(f"opponentKD: {fight.opponentKD}\n")
        file.write(f"opponentSTR: {fight.opponentSTR}\n")
        file.write(f"opponentTD: {fight.opponentTD}\n")
        file.write(f"opponentSUB: {fight.opponentSUB}\n")
        file.write(f"titlefight: {fight.titlefight}\n")
        file.write(f"Event: {fight.event}\n")
        file.write(f"Date: {fight.date}\n")
        file.write(f"Method: {fight.method}\n")
        file.write(f"Round: {fight.round}\n")
        file.write(f"Time: {fight.time}\n")
        
    file.write("=" * 40 + "\n")

def write_all_fighter_details_to_file(file_name):
    with app.app_context():
        fighters = Fighter.query.all()
        with open(file_name, 'w') as file:
            for fighter in fighters:
                write_fighter_details_to_file(fighter, file)

def delete_db():
    with app.app_context():
        db.drop_all()

def print_db():
    write_all_fighter_details_to_file("allfighters.txt")

def main():
    with app.app_context():
        db.create_all()

    all_characters = "abcdefghijklmnopqrstuvwxyz"
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
    

if __name__ == "__main__":
    # delete_db()
    # main()
    print_db()
    
