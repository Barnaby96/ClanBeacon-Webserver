# ClanBeacon Webserver

ClanBeacon Webserver is a Discord-connected web dashboard for running and tracking Old School RuneScape clan events, with a primary focus on clan Bingo.

It is designed for clan organisers who want a central dashboard for teams, players, tiles, evidence, progress tracking, and event administration.

## Project Status

Current focus areas include:

- OSRS clan Bingo management
- Team and player administration
- Dink plugin drop and pet tracking
- Wise Old Man competition tracking
- Manual evidence submission
- Admin and organiser dashboard tools
- Discord bot integration

## Features

ClanBeacon currently supports:

- Dashboard user accounts
- Player, admin, and organiser roles
- Team and player management
- Bingo tile management
- Leaderboard and team progress pages
- Manual evidence submission
- Dink webhook ingestion for relevant drops and pets
- Dink setup export with private webhook injection
- Wise Old Man configuration for competition tracking
- Organiser tools such as account role changes and password resets

## External Services

ClanBeacon is intended to be used with:

- Discord
- Old School RuneScape
- Dink RuneLite plugin
- Wise Old Man
- PostgreSQL
- Railway or another Python-compatible hosting provider

Secrets and deployment-specific values should be configured through environment variables. Do not commit real Discord tokens, webhook URLs, database credentials, Flask secrets, or API keys.

See `.env.example` for the expected environment variable names.

## Local Development

This project is a Python Flask application backed by PostgreSQL.

The local development environment used for this project includes:

- Python 3.11
- PostgreSQL
- Flask
- discord.py
- Waitress
- pytest

The app is normally run locally from `main.py`.

## Acknowledgements

ClanBeacon Webserver began as a customised continuation of the original DanBot Old School RuneScape clan Bingo tracker.

Special thanks to the original DanBot project and its contributors, including Danny, Taercy, and Max uwu.

Additional thanks to the Dink developers. Dink makes RuneLite-based event tracking significantly easier and is a core part of the planned automation workflow.

## Contact

For ClanBeacon enquiries, contact:

- Email: clan.beacon@outlook.com
