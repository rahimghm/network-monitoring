from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class EquipmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    hostname: str = Field(..., min_length=1, max_length=150)
    community: str = Field(default="public", max_length=50)


class EquipmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    hostname: Optional[str] = Field(default=None, min_length=1, max_length=150)
    community: Optional[str] = Field(default=None, max_length=50)


class EquipmentOut(BaseModel):
    id: int
    name: str
    hostname: str
    community: str
    last_ip: Optional[str]
    is_up: Optional[bool]
    created_at: datetime


class InterfaceMetricOut(BaseModel):
    if_index: int
    if_descr: Optional[str]
    oper_status: Optional[str]
    admin_status: Optional[str]
    speed_bps: Optional[int]
    in_octets: Optional[int]
    out_octets: Optional[int]
    in_packets: Optional[int]
    out_packets: Optional[int]
    in_errors: Optional[int]
    out_errors: Optional[int]
    in_discards: Optional[int]
    out_discards: Optional[int]
    stp_state: Optional[str]


class DiagnosticOut(BaseModel):
    id: int
    equipment_id: int
    equipment_name: Optional[str] = None
    equipment_hostname: Optional[str] = None
    resolved_ip: Optional[str]
    is_up: bool
    sys_descr: Optional[str]
    sys_uptime: Optional[int]
    cpu_usage: Optional[float]
    ram_total_kb: Optional[int]
    ram_used_kb: Optional[int]
    temperature_c: Optional[float]
    error_message: Optional[str]
    collected_at: datetime
    interfaces: List[InterfaceMetricOut] = []


class MetricPointOut(BaseModel):
    equipment_id: Optional[int] = None
    collected_at: datetime
    cpu_usage: Optional[float]
    ram_total_kb: Optional[int]
    ram_used_kb: Optional[int]
    is_up: bool


# ---------- Auth & RBAC ----------

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    role: str = Field(default="technician")  # admin | technician | supervisor


class UserUpdate(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=6)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


# ---------- Alertes ----------

class ThresholdCreate(BaseModel):
    equipment_id: Optional[int] = None  # None = seuil global
    metric: str  # cpu_usage | ram_percent | temperature_c
    operator: str = "gt"  # gt | lt
    threshold_value: float
    enabled: bool = True


class ThresholdOut(BaseModel):
    id: int
    equipment_id: Optional[int]
    metric: str
    operator: str
    threshold_value: float
    enabled: bool
    created_at: datetime


class AlertEventOut(BaseModel):
    id: int
    equipment_id: int
    diagnostic_id: int
    metric: str
    value: Optional[float]
    threshold_value: Optional[float]
    message: Optional[str]
    created_at: datetime


# ---------- Snapshots / historique ----------

class SnapshotCreate(BaseModel):
    label: str
    equipment_ids: List[int]


class SnapshotUpdate(BaseModel):
    label: str = Field(..., min_length=1, max_length=150)


class SnapshotOut(BaseModel):
    id: int
    label: str
    created_by: Optional[int]
    created_at: datetime


class SnapshotDetailOut(SnapshotOut):
    diagnostics: List[DiagnosticOut] = []
    metrics: List[MetricPointOut] = []


class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int]
    username: str
    role: str
    action: str
    resource: Optional[str]
    resource_id: Optional[int]
    details: Optional[dict]
    created_at: datetime
