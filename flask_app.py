import os
from spotify_grabber import SpotifyGrabber

SERVER_NAME = "http://127.0.0.1:5000"

from flask import Flask, render_template, request, redirect

app = Flask(__name__)


def generate_spotify_review(auth_code, instance_id):
    # Making a SpotifyGrabber object with this instance and letting it grab its token using our auth code
    grabber = SpotifyGrabber(instance_id=instance_id)
    grabber.request_token(auth_code)

    # This saves all the users playlist data files and images and produces all the graphs we want
    grabber.save_user_playlists()


def generate_path_list(instance_id):
    # This will give us a list of all of the playlists that we've generated files for that we can send to our HTML
    path_list = []

    i = 0

    # Theres a directory for every playlist and one for data, so we just need to list all of the folders except data

    for playlist in os.listdir(f"static/spotify_instances/{instance_id}/"):
        if playlist == "data":
            pass
        else:
            path_list.append(f"{instance_id}/{playlist}")

    return path_list


# This is where we start, it's just a button which directs the user to spotify to validate
@app.route('/')
def index():
    return render_template('python_spotify_start.html')


# This is where the button directs the user, here we create a SpotifyGrabber object which gets a URL from spotify to
# Authorise the user, we then send the user there
@app.route('/get_user_auth')
def get_user_auth():
    grabber = SpotifyGrabber()
    return redirect(grabber.authorise_server())

# Once the user has authorised they are directed here with a state parameter that we've defined to be equal to the id
# That we've given the user's instance, along with an auth code we can use to get access to the users playlists
# The whole process will take time, so on the way to their report we send the user to waiting page
@app.route('/validate/')
def recieve_spotify_code():
    # Getting the URL arguments that spotify sent to see which user this is and get their auth code
    auth_code = request.args.get("code")
    instance_id = request.args.get("state")

    param = f"?id={instance_id}&auth={auth_code}"

    return str(render_template('python_spotify_wait.html', param=param))

# This is the route which produces the graphs and images that we need. Those tasks will be being performed whil the user
# Is on the waiting page. The waiting page will be displaying a gif, this is an easy way to have the tasks look like
# They're running in the background without needing to use javascript
@app.route('/tasks/')
def do_tasks():
    instance_id = request.args.get("id")
    auth_code = request.args.get("auth")

    param = f"?id={instance_id}"

    generate_spotify_review(auth_code, instance_id)

    return redirect(f"{SERVER_NAME}/report/{param}")

# Once the tasks are finished users are sent here. The user instance id's are designed in such a way that they are
# random and will never repeat, and this page only takes the id and assigns to the HTML page the associated images
# So this page can be refreshed without any
@app.route('/report/')
def show_report():
    instance_id = request.args.get("id")
    path_list = generate_path_list(instance_id)

    return str(render_template('python_spotify_end.html', path_list=path_list))
