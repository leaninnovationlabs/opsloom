import uuid
import enum
from datetime import datetime

# TODO Sumedh: we should pydantic instead of sqlalchemy as a standard practice, but for now we are using sqlalchemy
from sqlalchemy import (
    create_engine, Column, String, ForeignKey, Boolean, BigInteger,
    TIMESTAMP, Text, Enum
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

Base = declarative_base()

# Define the Enum directly in Python as well for use in models/code
class EntityEnum(enum.Enum):
    account = "account"
    person = "person"

class Territory(Base):
    __tablename__ = 'territory'

    territory_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    territory_name = Column(Text, nullable=False, unique=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('territory.territory_id'), nullable=True)

    # Relationships
    parent = relationship("Territory", remote_side=[territory_id], back_populates="children")
    children = relationship("Territory", back_populates="parent")
    accounts = relationship("AccountFullcast", back_populates="territory")
    people = relationship("Person", back_populates="territory")
    move_events_from = relationship("MoveEvent", foreign_keys='MoveEvent.from_territory_id', back_populates="from_territory")
    move_events_to = relationship("MoveEvent", foreign_keys='MoveEvent.to_territory_id', back_populates="to_territory")

class AccountFullcast(Base):
    __tablename__ = 'account_fullcast'

    account_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    account_name = Column(Text, nullable=False)
    territory_id = Column(UUID(as_uuid=True), ForeignKey('territory.territory_id'), nullable=False)
    parent_account_id = Column("parent_account", UUID(as_uuid=True), ForeignKey('account_fullcast.account_id'), nullable=True)
    family_id = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    territory = relationship("Territory", back_populates="accounts")
    parent = relationship("AccountFullcast", remote_side=[account_id], back_populates="children")
    children = relationship("AccountFullcast", back_populates="parent", foreign_keys=[parent_account_id]) # Specify FK for self-referencing

class Person(Base):
    __tablename__ = 'person'

    person_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    person_name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=True)
    territory_id = Column(UUID(as_uuid=True), ForeignKey('territory.territory_id'), nullable=False)

    # Relationships
    territory = relationship("Territory", back_populates="people")
    acted_move_events = relationship("MoveEvent", back_populates="actor")


class MoveEvent(Base):
    __tablename__ = 'move_event'

    move_id = Column(BigInteger, primary_key=True, autoincrement=True)
    entity_type = Column(Enum(EntityEnum, name="entity_enum"), nullable=False) # Use the Python Enum
    entity_id = Column(UUID(as_uuid=True), nullable=False) # Note: No direct FK constraint here as type varies
    from_territory_id = Column(UUID(as_uuid=True), ForeignKey('territory.territory_id'), nullable=False)
    to_territory_id = Column(UUID(as_uuid=True), ForeignKey('territory.territory_id'), nullable=False)
    committed = Column(Boolean, server_default='false', nullable=False)
    family_flag = Column(Boolean, server_default='false', nullable=False)
    actor_person_id = Column(UUID(as_uuid=True), ForeignKey('person.person_id'), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    from_territory = relationship("Territory", foreign_keys=[from_territory_id], back_populates="move_events_from")
    to_territory = relationship("Territory", foreign_keys=[to_territory_id], back_populates="move_events_to")
    actor = relationship("Person", back_populates="acted_move_events")

    # TODO: Consider how to represent the relationship to the moved entity (account or person)
    # given that entity_id/entity_type don't form a direct FK.
    # This might involve logic in repository/service layers.
    # right now we are using the entity_id to get the entity details, and we dont consider many to many relationships

# If we need Pydantic schemas for API input/output validation later,
# we can define them separately, potentially using tools like sqlmodel
# or pydantic-sqlalchemy, or just defining parallel Pydantic models. 