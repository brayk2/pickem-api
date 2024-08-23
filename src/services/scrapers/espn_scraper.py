from datetime import datetime, timezone

import pytz

from src.models.new_db_models import GameModel, SeasonModel, WeekModel, TeamModel
from src.services.scrapers.base_scraper import BaseScraper


class EspnScraper(BaseScraper):
    def __init__(self):
        # init scraper with corresponding url
        super().__init__(base_url="https://www.espn.com/nfl")

    def _parse_team_name(self, team_str: str) -> (str, str):
        elms = team_str.split("-")
        city_list, name = elms[:-1], elms[-1]
        city = " ".join(city_list).title()
        name = name.title()

        if name.lower() == "49ers":
            name = name.lower()

        return city, name

    def scrape_week(self, week: int, year: int) -> list:
        home_city, away_city, date, time = None, None, None, None

        soup = self.get_soup(url=f"schedule/_/week/{week}/year/{year}/seasontype/2")

        # This scrapes a table for each game day that season, need to pull date from
        # section header and then games from table rows
        game_days = soup.select("div.ScheduleTables--nfl div.ResponsiveTable")

        games_info = []
        for game_day in game_days:
            date_str = game_day.select_one("div.Table__Title").text.strip()
            date = datetime.strptime(date_str, "%A, %B %d, %Y")
            date = date.astimezone(pytz.utc)

            games = game_day.select("tbody.Table__TBODY tr.Table__TR")
            for game in games:
                # parse the teams' city information
                away_city_element = game.select_one("span.Table__Team.away")
                away_team_str = away_city_element.select_one("a")["href"].rsplit(
                    "/", 1
                )[-1]
                away_city, away_team = self._parse_team_name(team_str=away_team_str)

                home_city_element = game.select_one("span.Table__Team:not(.away)")
                home_team_str = home_city_element.select_one("a")["href"].rsplit(
                    "/", 1
                )[-1]
                home_city, home_team = self._parse_team_name(team_str=home_team_str)

                # parse the time
                time_str = game.select_one("td.date__col.Table__TD a").text.strip()

                if not time_str.lower() == "tbd":
                    time = datetime.strptime(time_str, "%I:%M %p").time()
                else:
                    self.logger.info("Time has not yet been set for game")

                games_info.append(
                    (home_city, home_team, away_city, away_team, date, time)
                )
        return games_info

    def _scrape_season(self, year: int, num_weeks: int = 18):
        season = {}
        for i in range(num_weeks):
            week = self.scrape_week(week=i + 1, year=year)
            self.logger.info(week)
            season[i + 1] = week
            print(f"Finished Loading Week {i + 1}".center(80, "-"))

        print(f"Finished Loading Season {year}".center(80, "-"))
        return season

    def _save_schedule(self, year: int, season: dict):
        season_model, created = SeasonModel.get_or_create(year=year)
        if created:
            self.logger.info(f"created season {year}")

        for week, games in season.items():
            for (
                home_city,
                home_team,
                away_city,
                away_team,
                start_date,
                start_time,
            ) in games:
                # load season model
                week_model, created = WeekModel.get_or_create(
                    season=season_model,
                    week_number=week,
                )
                if created:
                    self.logger.info(f"week created {week}")

                # load team models
                home_team_model, _ = TeamModel.get_or_create(
                    city=home_city, name=home_team
                )
                away_team_model, _ = TeamModel.get_or_create(
                    city=away_city, name=away_team
                )

                # create the game model
                game, created = GameModel.get_or_create(
                    season=season_model,
                    week=week_model,
                    home_team=home_team_model,
                    away_team=away_team_model,
                )
                game.start_date = start_date

                if created:
                    self.logger.info(f"created game {home_city} vs {away_city}")

                # some games don't have a start time yet (season 18)
                if start_time:
                    game.start_time = start_time
                    game.save()

    def _calculate_start_end_dates(self, year: int, week: int):
        pass

    def scrape_season(self, year: int):
        season = self._scrape_season(year=year)
        return self._save_schedule(year=year, season=season)


if __name__ == "__main__":
    scraper = EspnScraper()
    scraper.scrape_season(year=2024)
