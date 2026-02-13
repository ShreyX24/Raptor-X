"""
Branding API - serves and updates banner gradient colors for SUTs
"""

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter(tags=["branding"])

DEFAULT_BANNER_GRADIENT = [93, 135, 141, 183, 189, 231]
CONFIG_FILE = Path.home() / ".rpx" / "service_manager_config.json"


class BrandingUpdate(BaseModel):
    banner_gradient: List[int]

    @field_validator("banner_gradient")
    @classmethod
    def validate_gradient(cls, v: List[int]) -> List[int]:
        if len(v) != 6:
            raise ValueError("banner_gradient must have exactly 6 values")
        for code in v:
            if not (0 <= code <= 255):
                raise ValueError(f"ANSI color code must be 0-255, got {code}")
        return v


@router.get("/branding")
async def get_branding():
    """Return the banner gradient configuration for SUTs."""
    gradient = DEFAULT_BANNER_GRADIENT
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            saved = config.get("banner_gradient")
            if isinstance(saved, list) and len(saved) == 6:
                gradient = saved
    except (json.JSONDecodeError, IOError):
        pass
    return {"banner_gradient": gradient}


@router.post("/branding")
async def update_branding(body: BrandingUpdate):
    """Update the banner gradient configuration."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Read existing config (preserve other keys)
        config = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError):
                config = {}

        config["banner_gradient"] = body.banner_gradient

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        return {"status": "ok", "banner_gradient": body.banner_gradient}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save branding: {e}")
