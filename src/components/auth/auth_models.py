from pydantic import BaseModel, Field

from src.models.base_models import BaseDto


# Pydantic models
class TokenResponse(BaseDto):
    token_type: str = Field(alias="tokenType")
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    expiration: float = Field(alias="exp")


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LeagueClaim(BaseModel):
    """One league's standing for the token holder.

    `years` lists the seasons they are rostered in; `commissioner` is per-league
    rather than per-season, since a season is opened with an empty roster and
    somebody has to be able to populate it.
    """

    years: list[int] = Field(default_factory=list)
    commissioner: bool = False


class DecodedToken(BaseModel):
    sub: str
    roles: list[str]
    # League standing, keyed by league id as a string (JSON object keys are
    # strings). Written at login/refresh so permission checks need no database
    # round trip; the 15 minute access token lifetime bounds how stale it gets.
    leagues: dict[str, LeagueClaim] = Field(default_factory=dict)
    exp: float | None = None  # Optional expiration time

    @classmethod
    def from_dict(cls, data: dict) -> "DecodedToken":
        return cls(**data)

    def to_dict(self) -> dict:
        return self.model_dump()

    @property
    def is_admin(self):
        return "admin" in self.roles

    def is_member(self, league_id: int, year: int) -> bool:
        """Whether the holder is on that league's roster for that season."""
        claim = self.leagues.get(str(league_id))
        return bool(claim and year in claim.years)

    def is_in_league(self, league_id: int) -> bool:
        """Whether the holder belongs to the league in any season.

        Reading a league's history is gated on this rather than on the specific
        season, so somebody who joins in 2026 can still see who won in 2023.
        Writing is still gated on that season's roster -- see is_member.
        """
        return str(league_id) in self.leagues

    def is_commissioner(self, league_id: int) -> bool:
        """Whether the holder commissions that league (any season)."""
        claim = self.leagues.get(str(league_id))
        return bool(claim and claim.commissioner)
