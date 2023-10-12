from playhouse.shortcuts import model_to_dict

from src.models.db_models import TeamModel, GameModel, SeasonModel
from src.services.scrapers.base_scraper import BaseScraper


class PfrScraper(BaseScraper):
    def __init__(self):
        # init scraper with corresponding url
        super().__init__(url="https://www.pro-football-reference.com")

    def scrape_teams(self):
        self.logger.info(f"scraping NFL teams from {self.base_url}/teams/")
        soup = self.get_soup(url="teams/")
        team_elements = soup.find_all("th", attrs={"data-stat": "team_name"})
        for team_element in team_elements:
            if team := team_element.find("a"):
                # create model for team
                self.logger.info(f"loading team {team.text.strip()}")
                model, _ = TeamModel.get_or_create(name=team.text.strip())
                model.reference = team.get("href")
                model.save()

    def scrape_schedule(self):
        season, _ = SeasonModel.get_or_create(year="2023")

        for i in range(18):
            games = []
            soup = self.get_soup(url=f"years/2023/week_{i + 1}.htm")

            summaries = soup.find_all("div", class_="game_summary")
            for summary in summaries:
                teams = summary.find("table", class_="teams")
                _, away, home = teams.find_all("tr")

                away, link = away.find_all("a")
                home = home.find("a")

                away = TeamModel.get(name=away.text.strip())
                home = TeamModel.get(name=home.text.strip())

                self.logger.info(f"creating game model {home} v {away}")
                game, _ = GameModel.get_or_create(
                    home_team=home, away_team=away, week=f"{i + 1}", season_id=season
                )
                game.reference = link.get("href")
                game.save()
                games.append(model_to_dict(game))
