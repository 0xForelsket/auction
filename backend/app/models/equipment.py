from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EquipmentCode(Base):
    __tablename__ = "equipment_codes"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name_ja: Mapped[str | None] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(50))
