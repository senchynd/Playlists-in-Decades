import base64
import hashlib
import io
import json
import os
import shutil
import string
import secrets
from PIL import Image

import requests

from playlist_analyser import PlaylistAnalyser

# This will need to be replaced with the client id of your spotify app and your server name
SERVER_NAME = "http://127.0.0.1:5000"
CLIENT_ID = ""


def generate_verifier():
    # Generates the code_verifier and code_challenge for the PKCE extension method

    # The code verifier is a random string of letters and digits with a length that is between 43 and 126

    # We generate a random length for the code verifier

    code_verifier_length = 43 + secrets.randbelow(85)

    # We define the code verifier as a random sequence of letters and digits of that length

    code_alphabet = string.ascii_letters + string.digits
    code_verifier = "".join(secrets.choice(code_alphabet) for i in range(code_verifier_length))

    # Then we hash the code_verifier with the sha256 algorithm to get the code_challenge

    code_verifier_sha = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_verifier_sha_b64 = base64.urlsafe_b64encode(code_verifier_sha).decode('utf-8')
    code_challenge = code_verifier_sha_b64.replace('=', '')

    return code_verifier, code_challenge


def get_next_instance_id():
    # Our instance id's begin with an order number and then have a sequence of 10 random characters afterward
    # The order number will climb indefinitely, so it will reference what instance the user was totally
    # After 10 instances, the oldest instance (the intance_id with the lowest order number) will be deleted
    # The order number and the random characters are separated by a '-'

    MAX_INSTANCES = 10

    # If there hasn't been an instance yet then we'll pretend there's a 0th instance, so we begin at 1
    if not os.listdir("static/spotify_instances"):
        id_list = [str(0)]
    else:
        id_list = os.listdir("static/spotify_instances")

    # Getting the order number, the 'iter_id', for iteration id
    iter_id = []
    for id in id_list:
        iter_id.append(int(id.split("_")[0]))

    oldest_id_index = iter_id.index(min(iter_id))

    # Removing the oldest instance
    if len(id_list) >= MAX_INSTANCES:
        shutil.rmtree(f"static/spotify_instances/{id_list[oldest_id_index]}", ignore_errors=True)
        print(iter_id[oldest_id_index])

    # The next iter_id will be 1 more than the biggest current one
    next_id_begin = str(max(iter_id) + 1)

    # Producing a random string with the same method as the code_verifier
    id_alphabet = string.ascii_letters + string.digits
    next_id_end = "".join(secrets.choice(id_alphabet) for i in range(10))

    #Concatenating the iter_id and the random string
    next_id = next_id_begin + "_" + next_id_end

    return next_id


# The SpotifyGrabber class is what I'll use to request data from the spotify API.

# I use Authorisation Code Flow through the web API which you can find a tutorial for here:
# https://developer.spotify.com/documentation/web-api/tutorials/code-flow


class SpotifyGrabber:
    def __init__(self, instance_id=None):

        # If there is no instance_id passed onto the SpotifyGrabber then that means that this is a new user.
        # We generate a code verifier and code challenge and save them to a file.
        # Eventually we're also going to save the access token to that file.
        # We do this so the server can pull data from the users spotify account on demand

        self.token = None
        if (instance_id == None):

            if not os.path.exists("static/spotify_instances"):
                os.mkdir("static/spotify_instances")

            # This is the function we've defined which gets a unique instance_id for the user
            self.instance_id = get_next_instance_id()

            # Generating the code_challenge and code_verifier
            (self.code_verifier, self.code_challenge) = generate_verifier()

            instance_dict = {
                "id": self.instance_id,
                "code_verifier": self.code_verifier,
                "tokens": {},
            }

            print(f"new instance created: {self.instance_id}")

            # Creating a directory for this user, we'll store data and images here

            os.mkdir(f"static/spotify_instances/{self.instance_id}")
            os.mkdir(f"static/spotify_instances/{self.instance_id}/data")

            # Writing our data file into that directory
            try:
                with open(f"static/spotify_instances/{self.instance_id}/data/instance_data.json", "w") as instance_file:
                    json.dump(instance_dict, instance_file)

            except:
                print("Access or Path Error")

        # If there is a instance_id passed into the SpotifyGrabber creation then this is a previous user
        # we open the data_file that would have been saved on its creation in order to get its attributes

        else:
            try:
                with open(f"static/spotify_instances/{instance_id}/data/instance_data.json", "r+") as instance_file:
                    instance_data = json.load(instance_file)

                    self.instance_id = instance_id
                    self.code_verifier = instance_data["code_verifier"]
            except:
                print(f"Spotify Grabber Instance: {instance_id} Cannot Be Found Error")

    def authorise_server(self):
        # This is the initial step in the Authorisation Code Flow in order to get an Access Token

        # We set the state to instance_id so that the server can reference this user when they validate their spotify

        state = self.instance_id

        # These are the parameters spotify needs, we only need to have permission to get data on the users playlists

        auth_params = {"client_id": CLIENT_ID,
                       "response_type": "code",
                       "redirect_uri": f"{SERVER_NAME}/validate/",
                       "state": state,
                       "scope": "playlist-read-private",
                       "code_challenge_method": "S256",
                       "code_challenge": self.code_challenge,
                       "show_dialog": "false"}

        # We send the request to spotify
        try:
            auth = requests.get("https://accounts.spotify.com/authorize", params=auth_params)
        except:
            print("Network Error When Accessing: https://accounts.spotify.com/authorize ")

        # Spotify gives us a url for the user to sign in to their spotify and give us permissions

        # I just open it now because we're testing but I'll have a better way of doing it through the web browser later

        return auth.url

    def request_token(self, auth_code):
        # Once the user has validated their spotify we get an auth code
        # We can send use that auth code to request an access token from spotify
        # These access tokens are temporary and need to be renewed
        # They're what we'll need in order to make our data requests from spotify

        auth = requests.post("https://accounts.spotify.com/api/token",
                             headers={"Content-Type": "application/x-www-form-urlencoded"},
                             data={"grant_type": "authorization_code",
                                   "code": auth_code,
                                   "redirect_uri": f"{SERVER_NAME}/validate/",
                                   "client_id": CLIENT_ID,
                                   "code_verifier": self.code_verifier})
        try:
            self.token = auth.json()["access_token"]
        except:
            with open(f"static/spotify_instances/{self.instance_id}/data/error.json", "w") as f:
                f.write(auth.text)
            print(f"Request Token Error, See: static/spotify_instances/{self.instance_id}/data/error.json for Response")

    def save_user_playlists(self):

        # We request a data file on the users playlists

        response = requests.get(f"https://api.spotify.com/v1/me/playlists",
                                headers={"Authorization": "Bearer " + self.token,
                                         "Content-Type": "application/json"})

        playlists_data = response.json()

        try:
            playlists_data["items"]
        except:
            with open(f"static/spotify_instances/{self.instance_id}/data/error.json", "w") as f:
                f.write(response.text)
            print(f"Token Use Error, See: static/spotify_instances/{self.instance_id}/data/error.json for Response")

        # We create a list of dictionaries with info on the first four non spotify playlists

        i = 0
        playlist_list = []
        for item in playlists_data["items"]:

            # We get a maximum of 20 playlists (index starts at 0)
            if (i > 19):
                break

            # We want to ignore any playlists made by spotify such as blends and 'made for you' mixes and any playlists
            # which have less than 3 tracks in them

            try:
                conditions = (item["owner"]["display_name"] != "Spotify") \
                             and (int(item["tracks"]["total"]) > 3)
            except:
                conditions = False
                print(f"Playlist Conditions Error with Playlist {i} in Instance {self.instance_id}")

            if conditions:

                # Creating a dictionary of all the playlists we'll want to analyse
                playlist_entry = {"name": item["name"],
                                  "description": item["description"],
                                  "link_id": item["id"],
                                  "playlist_number": i}

                try:
                    playlist_entry["art_url"] = item["images"][0]["url"]
                except:
                    # Occasionally we get errors here for unknown reasons, this is just a placeholder
                    # image to make things run smoothly
                    playlist_entry["art_url"] = "https://i.scdn.co/image/ab67616d0000b273e0d42912ff2e2569eecff949"

                playlist_list.append(playlist_entry)

                i += 1

            else:
                print(f"Error with Playlist Data Entry, see: static/spotify_instances/{self.instance_id}"
                      f"/data/playlist_data.json for errors")
                pass

        # Writing the dictionary to a file so we can access it when we need to
        json_file = json.dumps(playlist_list)
        with open(f"static/spotify_instances/{self.instance_id}/data/playlist_data.json", "w") as f:
            f.write(json_file)

        # Now for each playlist we're going to create a folder with a data file, it's image and with the graph we want

        for playlist in playlist_list:

            try:
                # Rather than doing the 'i' thing again we can just use the playlist number
                x = playlist['playlist_number']

                # Making the request
                response = requests.get(f"https://api.spotify.com/v1/playlists/{playlist['link_id']}",
                                        headers={"Authorization": "Bearer " + self.token,
                                                 "Content-Type": "application/json"})

                # Making the folder
                os.mkdir(f"static/spotify_instances/{self.instance_id}/playlist{x}")

                # Saving the data file
                json_file = json.dumps(response.json())
                with open(f"static/spotify_instances/{self.instance_id}/playlist{x}/data.json", "w") as f:
                    f.write(json_file)

                # Making a request for the image
                # Again, requesting images from spotify can lead to errors so we should be careful
                try:
                    response = requests.get(playlist["art_url"],
                                            headers={"Authorization": "Bearer " + self.token,
                                                     "Content-Type": "application/json"})
                    im = Image.open(io.BytesIO(response.content))
                except:
                    print("image error")

                # Saving the image using Pillow
                im.save(f"static/spotify_instances/{self.instance_id}/playlist{x}/playlist_image.png")
                print(f"playlist_image{x} saved")

                # Using a PlaylistAnalyser object to create our graph
                analyser = PlaylistAnalyser(instance_id=self.instance_id, playlist_num=x)
                analyser.create_year_graph()
                print(f"graph_image{x} saved")

            except:
                print(f"Issue with Playlist Error, number: {playlist['playlist_number']}")
