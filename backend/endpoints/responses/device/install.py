import enum
from typing import Annotated

from pydantic import Field

from ..base import BaseModel, UTCDatetime


class InstallStatus(enum.StrEnum):
    PENDING = "pending"
    TAKEN = "taken"
    DONE = "done"
    ALREADY_INSTALLED = "already_installed"
    # An uninstall found nothing of the rom on the device.
    NOT_INSTALLED = "not_installed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InstallAction(enum.StrEnum):
    INSTALL = "install"
    UNINSTALL = "uninstall"


InstallReason = Annotated[str, Field(max_length=500)]


class InstallRequestSchema(BaseModel):
    """An install request, as served and as stored in Redis while pending or taken."""

    id: str
    user_id: int
    device_id: str
    rom_id: int
    # Requests stored before uninstall existed carry no action.
    action: InstallAction = InstallAction.INSTALL
    file_ids: list[int]
    status: InstallStatus
    reason: InstallReason | None
    created_at: UTCDatetime
    updated_at: UTCDatetime
