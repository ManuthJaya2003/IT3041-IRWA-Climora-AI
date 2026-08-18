"""
Pydantic schemas for API requests and responses.
Defines the data contracts between frontend and backend.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# --- Enums ---

class UserType(str, Enum):
    """Type of user making the request."""
    INDIVIDUAL = "individual"
    STUDENT = "student"
    FARMER = "farmer"
    BUSINESS = "business"
    ORGANIZATION = "organization"
    INSTITUTION = "institution"


class RiskLevel(str, Enum):
    """Risk level assessment."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AgentStatus(str, Enum):
    """Status of an agent."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    STUB = "stub"


# --- Request Models ---

class ChatRequest(BaseModel):
    """User chat request to the system."""
    query: str = Field(..., description="The user's climate-related question or concern")
    location: Optional[str] = Field(None, description="User's location (city, region, country)")
    user_type: Optional[UserType] = Field(None, description="Type of user for tailored responses")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    context: Optional[dict] = Field(None, description="Additional context (time period, specific concerns)")


# --- Response Models ---

class SourceEvidence(BaseModel):
    """A piece of evidence from a retrieved source."""
    source_name: str = Field(..., description="Name of the source")
    source_url: Optional[str] = Field(None, description="URL of the source")
    content_snippet: str = Field(..., description="Relevant snippet from the source")
    retrieved_at: Optional[datetime] = Field(None, description="When this source was retrieved")
    reliability_score: Optional[float] = Field(None, ge=0, le=1, description="Source reliability 0-1")


class RiskAssessment(BaseModel):
    """Risk assessment from the analysis agent."""
    risk_level: RiskLevel = Field(..., description="Overall risk level")
    risk_factors: list[str] = Field(default_factory=list, description="Identified risk factors")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Confidence in assessment")
    explanation: Optional[str] = Field(None, description="Why this risk level was assigned")


class Recommendation(BaseModel):
    """A practical recommendation for the user."""
    action: str = Field(..., description="What the user should do")
    priority: str = Field(..., description="Priority level: immediate, short-term, long-term")
    explanation: Optional[str] = Field(None, description="Why this is recommended")


class ChatResponse(BaseModel):
    """Complete response from the multi-agent system."""
    session_id: str = Field(..., description="Session identifier")
    query: str = Field(..., description="Original user query")
    summary: str = Field(..., description="Main response summary")
    detailed_analysis: Optional[str] = Field(None, description="Detailed analysis text")
    risk_assessment: Optional[RiskAssessment] = Field(None, description="Risk assessment if applicable")
    recommendations: list[Recommendation] = Field(default_factory=list, description="Practical recommendations")
    sources: list[SourceEvidence] = Field(default_factory=list, description="Supporting evidence sources")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Overall response confidence")
    disclaimer: str = Field(
        default="This information is for awareness purposes. For emergency situations, contact local authorities.",
        description="Standard disclaimer"
    )
    processing_time_ms: Optional[float] = Field(None, description="Total processing time in ms")
    agents_used: list[str] = Field(default_factory=list, description="Agents that contributed to this response")


# --- Agent Communication Models ---

class AgentTaskMessage(BaseModel):
    """Message sent from orchestrator to an agent."""
    task_id: str = Field(..., description="Unique task identifier")
    source_agent: str = Field(..., description="Agent sending the task")
    target_agent: str = Field(..., description="Agent receiving the task")
    task_type: str = Field(..., description="Type of task to perform")
    payload: dict = Field(default_factory=dict, description="Task-specific data")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentTaskResult(BaseModel):
    """Result returned from an agent after processing a task."""
    task_id: str = Field(..., description="Original task identifier")
    agent_name: str = Field(..., description="Agent that produced this result")
    success: bool = Field(..., description="Whether the task completed successfully")
    result: Optional[dict] = Field(None, description="Task result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    processing_time_ms: Optional[float] = Field(None, description="Time taken to process")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
