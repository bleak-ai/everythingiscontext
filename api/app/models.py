from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"


class Base(DeclarativeBase):
    pass


class Template(Base):
    __tablename__ = "templates"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=PENDING)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    files: Mapped[list["TemplateFile"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="TemplateFile.path"
    )


# One approved and at most one pending entry per workflow id.
Index(
    "uq_templates_id_approved",
    Template.id,
    unique=True,
    postgresql_where=Template.status == APPROVED,
)
Index(
    "uq_templates_id_pending",
    Template.id,
    unique=True,
    postgresql_where=Template.status == PENDING,
)


class TemplateFile(Base):
    __tablename__ = "template_files"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_pk: Mapped[int] = mapped_column(
        ForeignKey("templates.pk", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    template: Mapped[Template] = relationship(back_populates="files")
