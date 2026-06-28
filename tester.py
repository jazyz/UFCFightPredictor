# import pandas as pd

# def process_fight():
#     data = pd.read_csv("data/detailed_fighter_stats.csv")

#     islam = data[data["Fighter"] == "Islam Makhachev"].set_index("Fighter")
#     jack = data[data["Fighter"] == "Jack Della Maddalena"].set_index("Fighter")

# process_fight()

# import requests
# from bs4 import BeautifulSoup

# # Step 1: Fetch the page
# url = "https://www.python.org"
# response = requests.get(url)

# if response.status_code == 200:
#     # Step 2: Parse the HTML
#     json = response.json()
#     print(json)
#     soup = BeautifulSoup(response.text, "html.parser")

#     # Step 3: Find and print all links
#     for link in soup.find_all("a"):
#         print(link.get_text(strip=True), " -> ", link.get("href"))

import io
import csv
csv_str ="""Red Fighter,Blue Fighter,Probability Win,Probability Lose
Ilia Topuria,Max Holloway,0.6971865523674146,0.3028134476325854
Max Holloway,Ilia Topuria,0.2972684084823777,0.7027315915176222
Robert Whittaker,Khamzat Chimaev,0.29004844454135914,0.7099515554586409
Khamzat Chimaev,Robert Whittaker,0.6994925614892065,0.30050743851079365
Lerone Murphy,Dan Ige,0.3773005934103272,0.6226994065896727
Dan Ige,Lerone Murphy,0.5873599312620696,0.4126400687379304
Magomed Ankalaev,Aleksandar Rakic,0.5484405143046505,0.4515594856953496
Aleksandar Rakic,Magomed Ankalaev,0.39565734991711593,0.6043426500828841
Geoff Neal,Rafael Dos Anjos,0.6048959185461292,0.39510408145387077
Rafael Dos Anjos,Geoff Neal,0.4002081257797423,0.5997918742202577
Said Nurmagomedov,Daniel Santos,0.6127139816070593,0.3872860183929407
Daniel Santos,Said Nurmagomedov,0.3223891796304734,0.6776108203695266
Abus Magomedov,Brunno Ferreira,0.49079151674260146,0.5092084832573984
Brunno Ferreira,Abus Magomedov,0.47974245183271397,0.520257548167286
Kennedy Nzechukwu,Chris Barnett,0.7143630418141649,0.2856369581858352
Chris Barnett,Kennedy Nzechukwu,0.32529989331006737,0.6747001066899326
Ismail Naurdiev,Bruno Silva,0.5654112678417527,0.4345887321582474
Bruno Silva,Ismail Naurdiev,0.5179957004459962,0.4820042995540038
"""


f = io.StringIO(csv_str)
reader = csv.DictReader(f)

data = [row for row in reader]
print(data)
