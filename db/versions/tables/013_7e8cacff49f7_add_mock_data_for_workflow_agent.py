"""add mock data for workflow agent

Revision ID: 7e8cacff49f7
Revises: 5bdbb3f3fc2c
Create Date: 2025-04-23 01:34:54.732770

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '7e8cacff49f7'
down_revision: Union[str, None] = '5bdbb3f3fc2c'
branch_labels: Union[str, Sequence[str], None] = None
defaults_on: Union[str, Sequence[str], None] = None


# --- Define table helpers for bulk insert --- 
territory_table = sa.table(
    "territory",
    sa.column("territory_id", UUID),
    sa.column("territory_name", sa.Text),
    sa.column("parent_id", UUID),
)

account_fullcast_table = sa.table(
    "account_fullcast",
    sa.column("account_id", UUID),
    sa.column("account_name", sa.Text),
    sa.column("territory_id", UUID),
    sa.column("parent_account", UUID),
    sa.column("family_id", UUID),
)

person_table = sa.table(
    "person",
    sa.column("person_id", UUID),
    sa.column("person_name", sa.Text),
    sa.column("email", sa.Text),
    sa.column("territory_id", UUID),
)

# --- Mock Data IDs ---
# Territories
T_GLOBAL_ID = uuid.uuid4()
T_WEST_ID = uuid.uuid4()
T_EAST_ID = uuid.uuid4()
T_WEST_ENT_ID = uuid.uuid4()
T_EAST_SMB_ID = uuid.uuid4()

# People
P_JULIE_ID = uuid.uuid4()
P_BOB_ID = uuid.uuid4()
P_ALICE_ID = uuid.uuid4()

# Accounts
A_DISNEY_ID = uuid.uuid4()
A_PIXAR_ID = uuid.uuid4() # Subsidiary of Disney
A_ACME_ID = uuid.uuid4()
A_STARK_ID = uuid.uuid4()

# Families
F_DISNEY_FAMILY_ID = uuid.uuid4()

def upgrade() -> None:
    print("--- Seeding Workflow Agent Mock Data ---")

    # 1. Seed Territories (ensure parent IDs exist or are NULL)
    op.bulk_insert(
        territory_table,
        [
            {"territory_id": T_GLOBAL_ID, "territory_name": "Global", "parent_id": None},
            {"territory_id": T_WEST_ID, "territory_name": "West", "parent_id": T_GLOBAL_ID},
            {"territory_id": T_EAST_ID, "territory_name": "East", "parent_id": T_GLOBAL_ID},
            {"territory_id": T_WEST_ENT_ID, "territory_name": "West Enterprise", "parent_id": T_WEST_ID},
            {"territory_id": T_EAST_SMB_ID, "territory_name": "East SMB", "parent_id": T_EAST_ID},
        ],
    )
    print("Seeded Territories")

    # 2. Seed People
    op.bulk_insert(
        person_table,
        [
            {
                "person_id": P_JULIE_ID,
                "person_name": "Julie Smith",
                "email": "julie.smith@example.com",
                "territory_id": T_WEST_ENT_ID, # Julie is in West Enterprise
            },
            {
                "person_id": P_BOB_ID,
                "person_name": "Bob Johnson",
                "email": "bob.j@sample.org",
                "territory_id": T_EAST_SMB_ID, # Bob is in East SMB
            },
             {
                "person_id": P_ALICE_ID,
                "person_name": "Alice Brown",
                "email": "alice.b@corp.net",
                "territory_id": T_WEST_ENT_ID, # Alice also in West Enterprise
            },
            # Add more people as needed
        ],
    )
    print("Seeded People")

    # 3. Seed Accounts
    op.bulk_insert(
        account_fullcast_table,
        [
            {
                "account_id": A_DISNEY_ID,
                "account_name": "Disney",
                "territory_id": T_WEST_ENT_ID, # Disney starts in West Ent
                "parent_account": None,
                "family_id": F_DISNEY_FAMILY_ID,
            },
            {
                "account_id": A_PIXAR_ID,
                "account_name": "Pixar",
                "territory_id": T_WEST_ENT_ID, # Pixar also starts in West Ent
                "parent_account": A_DISNEY_ID, # Pixar is child of Disney
                "family_id": F_DISNEY_FAMILY_ID, # Same family
            },
             {
                "account_id": A_ACME_ID,
                "account_name": "Acme Corporation",
                "territory_id": T_EAST_SMB_ID,
                "parent_account": None,
                "family_id": None, # No family
            },
             {
                "account_id": A_STARK_ID,
                "account_name": "Stark Industries",
                "territory_id": T_EAST_SMB_ID,
                "parent_account": None,
                "family_id": None,
            },
            # Add more accounts as needed
        ],
    )
    print("Seeded Accounts")

    # 4. Seed Move Events (Optional - example)
    # You might want to add example proposed/committed moves here
    # op.bulk_insert(move_event_table, [...])
    print("--- Seeding Complete ---")


def downgrade() -> None:
    print("--- Removing Workflow Agent Mock Data ---")
    # Delete in reverse order of creation due to FKs
    # Note: No move events seeded, so no delete needed yet
    op.execute(f"DELETE FROM {account_fullcast_table.name}")
    print("Deleted Accounts")
    op.execute(f"DELETE FROM {person_table.name}")
    print("Deleted People")
    op.execute(f"DELETE FROM {territory_table.name}")
    print("Deleted Territories")
    print("--- Removal Complete ---")
