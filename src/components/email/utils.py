def generate_html_table(data):
    html = """
    <html>
    <head>
        <style>
            table {border-collapse: collapse; width: 100%;}
            th, td {border: 1px solid #dddddd; text-align: left; padding: 4px;}
            th {background-color: #f2f2f2;}
        </style>
    </head>
    <body>
    """
    html += "<table>"
    html += (
        "<tr><th>Home Team</th><th>Spread</th><th>Away Team</th><th>Spread</th></tr>"
    )

    for game in data:
        teams = list(game.keys())
        spreads = list(game.values())

        # Determine home and away teams
        if "-" in spreads[0]:
            home_team, home_spread = teams[0], spreads[0]
            away_team, away_spread = teams[1], spreads[1]
        else:
            home_team, home_spread = teams[1], spreads[1]
            away_team, away_spread = teams[0], spreads[0]

        html += f"<tr><td>{home_team}</td><td>{home_spread}</td><td>{away_team}</td><td>{away_spread}</td></tr>"

    html += "</table>"
    html += "</body></html>"
    return html
