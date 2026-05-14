from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SiteSettingsOut
from app.services.site_settings import get_all_settings

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/site-settings", response_model=SiteSettingsOut)
def public_site_settings(db: Annotated[Session, Depends(get_db)]):
    return SiteSettingsOut(**get_all_settings(db))
