from pydantic import BaseModel, Field


class UpgradePlanRequest(BaseModel):
    plan: str = Field(..., description="Target plan name: free, premium")


class UpgradePlanResponse(BaseModel):
    detail: str
    plan: str
