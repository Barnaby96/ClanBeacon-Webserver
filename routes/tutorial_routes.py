from flask import Flask, request, render_template, Blueprint, flash, redirect, send_from_directory
from flask_login import login_required

from utils.autocomplete import player_names

tutorial_routes = Blueprint("tutorial_routes", __name__)

@tutorial_routes.route('/dink')
@login_required
def dink():
    return render_template("tutorial_templates/dink.html", playernames=player_names())