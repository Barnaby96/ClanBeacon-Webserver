import json
import os
from pathlib import Path

from flask import Flask, request, render_template, Blueprint, flash, redirect, send_from_directory, Response, current_app
from flask_login import login_required

from utils.autocomplete import player_names

tutorial_routes = Blueprint("tutorial_routes", __name__)

@tutorial_routes.route('/dink')
@login_required
def dink():
    return render_template("tutorial_templates/dink.html", playernames=player_names())


@tutorial_routes.route('/dink/settings')
@login_required
def dink_settings():
    webhook_url = os.environ.get("DINK_WEBHOOK_URL", "").strip()

    if not webhook_url:
        return Response(
            "Dink webhook URL is not configured.",
            status=503,
            mimetype="text/plain"
        )

    template_path = (
        Path(current_app.root_path) /
        "static" /
        "images" /
        "dink" /
        "dink_template.txt"
    )

    try:
        config = json.loads(
            template_path.read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        return Response(
            "Dink settings template is not configured.",
            status=503,
            mimetype="text/plain"
        )
    except json.JSONDecodeError:
        return Response(
            "Dink settings template is invalid.",
            status=500,
            mimetype="text/plain"
        )

    config["discordWebhook"] = webhook_url

    return Response(
        json.dumps(config, separators=(",", ":"), ensure_ascii=False),
        mimetype="text/plain; charset=utf-8"
    )
