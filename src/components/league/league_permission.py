from fastapi import Depends

from src.components.auth.auth_models import DecodedToken
from src.components.auth.permission_checker import PermissionChecker
from src.components.league.league_exceptions import (
    NotALeagueCommissionerException,
    NotALeagueMemberException,
)


class LeaguePermission:
    """
    League-scoped route gates.

    These read the `leagues` claim on the token and never touch the database.
    The claim is written at login and refresh (see LeagueService.get_league_claims),
    so a roster change reaches the holder on their next refresh -- bounded by the
    15 minute access token lifetime.
    """

    @staticmethod
    def member(
        league_id: int,
        year: int,
        token: DecodedToken = Depends(PermissionChecker.authenticated),
    ) -> DecodedToken:
        if token.is_admin or token.is_member(league_id=league_id, year=year):
            return token

        raise NotALeagueMemberException(
            username=token.sub, league_id=league_id, year=year
        )

    @staticmethod
    def commissioner(
        league_id: int,
        token: DecodedToken = Depends(PermissionChecker.authenticated),
    ) -> DecodedToken:
        if token.is_admin or token.is_commissioner(league_id=league_id):
            return token

        raise NotALeagueCommissionerException(
            username=token.sub, league_id=league_id
        )
