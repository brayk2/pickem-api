from src.config.base_service import BaseService
from src.services.scrapers.nfl_scraper import NflScraper
from src.services.scrapers.pfr_scraper import PfrScraper
from src.util.injection import dependency, inject


@dependency
class ScraperService(BaseService):
    @inject
    def __init__(self, pfr_scraper: PfrScraper, nfl_scraper: NflScraper):
        self.pfr_scraper = pfr_scraper
        self.nfl_scraper = nfl_scraper


if __name__ == "__main__":
    # teams = scrape_teams()
    # print(teams)
    scraper = ScraperService()
    scraper.nfl_scraper.scrape_thumbnails()

    # load_details()

    # for team, thumb in scrape_thumbnails().items():
    #     team_model, _ = TeamModel.get_or_create(name=team)
    #     team_model.thumbnail = thumb
    #     team_model.save()
    #
    #     print(model_to_dict(team_model))
