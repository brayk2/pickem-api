from src.models.db_models import TeamModel
from src.services.scrapers.base_scraper import BaseScraper


class NflScraper(BaseScraper):
    def __init__(self):
        super().__init__(base_url="https://www.nfl.com")

    def scrape_thumbnails(self):
        self.logger.info("scraping nfl thumbnails from nfl.com")
        soup = self.get_soup("teams/")
        figures = soup.find_all("figure", class_="nfl-c-custom-promo__figure")
        for figure in figures:
            img = figure.find("img")
            team, src = img.get("alt"), img.get("data-src")

            if team_model := TeamModel.get_or_none(name=team):
                self.logger.info(f"saving thumbnail for team {team}")
                team_model.thumbnail = src
                team_model.save()
            else:
                self.logger.info(f"cannot find team {team}")
