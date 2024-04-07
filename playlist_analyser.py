import matplotlib

# This is needed because we are only using this file in threads and not in a main loop
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from PIL import Image, ImageFont, ImageDraw
import json
import pandas as pd
import matplotlib
import seaborn as sb
from datetime import datetime
from matplotlib.font_manager import fontManager, FontProperties

# Defining some fonts
big_font = ImageFont.truetype("fonts/GothamBold.ttf", 100, encoding="unic")
medium_font = ImageFont.truetype("fonts/GothamMedium.ttf", 150, encoding="unic")
small_font = ImageFont.truetype("fonts/GothamMedium.ttf", 100, encoding="unic")
tiny_font = ImageFont.truetype("fonts/GothamLight.ttf", 80, encoding="unic")


class PlaylistAnalyser:
    def __init__(self, instance_id, playlist_num):
        # This prevents graphs from saving on top of each other
        plt.clf()

        # Adds the user and the playlist as attributes
        self.instance_id = instance_id
        self.playlist_num = playlist_num

        # Getting the playlist data as an attribute
        with open(f"static/spotify_instances/{self.instance_id}/playlist{self.playlist_num}/data.json",
                  "r+") as instance_file:
            self.playlist_data = json.load(instance_file)

        # Setting the playlists name as an attribute
        self.playlist_name = self.playlist_data["name"]
        self.playlist_description = self.playlist_data["description"]
        self.link = self.playlist_data["external_urls"]["spotify"]

        # Adding a spotify-esque font and setting seaborn style for the inevitable graphs

        path = "fonts/GothamMedium.ttf"
        fontManager.addfont(path)

        prop = FontProperties(fname=path)

        sb.set(style="darkgrid", font=prop.get_name())

        self.spot_green = "#1DB954"
    def generate_final_image(self):
        # Essentially, instead of trying to format the python_spotify_end.html file, I have decided to just list a
        # series of images in the HTML file and format those images using pillow, so this is going to be a large image
        # That has the playlist art cover, and also the info about it, it's name and number. It does admitedly look
        # A bit unprofessional on the HTML page because you can save this image, but it makes the HTML and CSS coding
        # Much easier, essentially it's moving the work that would be done there into python

        playlist_image = Image.open(
            f"static/spotify_instances/{self.instance_id}/playlist{self.playlist_num}/playlist_image.png")

        # This is the padding around the playlist art where we'll add text
        # The values are a bit add hoc, they were just eyeballed with trial and error

        right = 5000
        left = 300
        top = 1400
        bottom = 400

        # We get the dimensions of the playlist icon
        width, height = playlist_image.size

        # We add that to the padding
        new_width = width + right + left
        new_height = height + top + bottom

        # We create an image with those dimensions
        result = Image.new(playlist_image.mode, (new_width, new_height), (255, 255, 255))

        # We paste the playlist image into that image
        result.paste(playlist_image, (left, top))

        # We call draw the new image which will have the
        draw = ImageDraw.Draw(result)

        # Adding three bits of text: a playlist number text, a title text and a description text
        draw.text((left, 1100), f"PLAYLIST {self.playlist_num + 1}", fill=(100, 100, 100), font=big_font)
        draw.text((left + width + 150, top + 100), self.playlist_name, fill=(0, 0, 0), font=medium_font)
        draw.text((left + width + 150, top + 300), self.playlist_description, fill=(0, 0, 0), font=small_font)



        # Saving this new image as 'final heading'
        result.save(f"static/spotify_instances/{self.instance_id}/playlist{self.playlist_num}/final_heading.jpg")

    def year_graph_from_data(self, date_list):
        # Using our list to create a jpg bar chart

        # FORMATTING THE DATA

        # Turning the list of strings into a pandas series of floats
        date_series = pd.Series(date_list).astype(float)

        # Cutting off the last digit of the year to group the decades
        decades_series = (date_series / 10).astype(int)

        # Counting the entries in each decade and sorting them
        decades_count = decades_series.value_counts().sort_index()

        # Filling in the missing decades
        decades_count = decades_count.reindex(range(decades_count.index.min(), decades_count.index.max() + 1))

        # Giving those decades a count of 0
        decades_count = decades_count.fillna(0)

        # Making the decades index more presentable
        decades_count.index = decades_count.index.astype("string") + "0s"

        # GRAPHING THE DATA

        figure = sb.barplot(x=decades_count.index, y=decades_count, color=self.spot_green)

        figure.set(xlabel="Decades", ylabel="Tracks",
                   title=f"What decades are the tracks in {self.playlist_name} from?",
                   yticks=(range(int(decades_count.min()), int(decades_count.max() + 1),
                                 int(decades_count.max() / 10 + 1))))

        figure.set_xticklabels(figure.get_xticklabels(), rotation=30)

        plt.savefig(f"static/spotify_instances/{self.instance_id}/playlist{self.playlist_num}/graph.jpg", dpi=600)

        plt.close()

    def create_year_graph(self):

        # We first need to get a list of the years of all of the tracks from the playlists json file

        date_list = []

        for track in self.playlist_data["tracks"]["items"]:

            # Different tracks give different levels of precision for the release date. It can be the day, month or year
            # We want to fill our list with years in the form "yyyy"

            precision = track["track"]["album"]["release_date_precision"]
            date = track["track"]["album"]["release_date"]

            if precision == "day":
                strp_date = datetime.strptime(date, "%Y-%m-%d")
                year = strp_date.year

            elif precision == "month":
                strp_date = datetime.strptime(date, "%Y-%m")
                year = strp_date.year

            elif precision == "year":
                year = date

            else:
                print(f"ALERT: THERE IS A {date}")

            date_list.append(year)

        # Here we have a separate function which produces and saves the actual graph
        try:
            self.year_graph_from_data(date_list)
            self.generate_final_image()
        except:
            # Sometimes there can be access errors on spotify's end. If this happens then the playlists which encountered
            # issues won't have their associated images, but we'll still hopefully get some results
            pass
