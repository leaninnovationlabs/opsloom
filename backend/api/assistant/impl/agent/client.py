import httpx
from typing import List, Optional
from .schemas import (
    ServiceSchema,
    ServiceOrderSchema,
    ReservationSchema,
    CreateReservationRequest,
    ActionURLSchema  # Import the new schema
)
import logging
from backend.util.config import get_config_value

logger = logging.getLogger(__name__)

EXTERNAL_API_BASE_URL = get_config_value("EXTERNAL_API_BASE_URL")

class HotelApiClient:
    """Encapsulates all external HTTP calls for reservations, services, etc."""

    def __init__(self):
        # Initialize the URL schema
        self.url_schema = ActionURLSchema()
        self.url_schema.BASE_URL = EXTERNAL_API_BASE_URL

    async def get_reservations_for_guest(self, guest_id: int) -> List[ReservationSchema]:
        url = f"{EXTERNAL_API_BASE_URL}/reservations/{guest_id}"
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            r.raise_for_status()
        data = r.json()
        return [ReservationSchema(**item) for item in data]

    async def create_reservation(self, req: CreateReservationRequest) -> ReservationSchema:
        url = self.url_schema.get_reservation_create_url()
        payload = req.model_dump_json(exclude_unset=True)
        logger.info(f"Creating reservation: {payload}")
        async with httpx.AsyncClient() as client:
            r = await client.post(url, content=payload)
            r.raise_for_status()
        return ReservationSchema(**r.json())

    async def modify_reservation(
        self,
        reservation_id: int,
        check_in: Optional[str],
        check_out: Optional[str],
        room_type: Optional[str]
    ) -> ReservationSchema:
        url = self.url_schema.get_reservation_modify_url(reservation_id)
        payload = {}
        if check_in:
            payload["check_in"] = check_in
        if check_out:
            payload["check_out"] = check_out
        if room_type:
            payload["room_type"] = room_type

        logger.info(f"Modifying reservation {reservation_id}: URL={url}, payload={payload}")
        async with httpx.AsyncClient() as client:
            r = await client.patch(url, json=payload)
            r.raise_for_status()
        return ReservationSchema(**r.json())

    async def cancel_reservation(self, reservation_id: int) -> bool:
        url = self.url_schema.get_reservation_cancel_url(reservation_id)
        async with httpx.AsyncClient() as client:
            r = await client.delete(url)
            r.raise_for_status()
        return True

    async def list_all_services(self) -> List[ServiceSchema]:
        url = f"{EXTERNAL_API_BASE_URL}/services"
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            r.raise_for_status()
        data = r.json()
        return [ServiceSchema(**svc) for svc in data]

    async def create_service_order(
        self,
        reservation_id: int,
        service_id: int,
        quantity: int,
        status: str
    ) -> ServiceOrderSchema:
        url = self.url_schema.get_service_order_url()
        payload = {
            "reservation_id": reservation_id,
            "service_id": service_id,
            "quantity": quantity,
            "status": status,
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
        return ServiceOrderSchema(**r.json())

    async def list_service_orders_for_reservation(self, reservation_id: int) -> List[ServiceOrderSchema]:
        url = f"{EXTERNAL_API_BASE_URL}/serviceorders/by_reservation/{reservation_id}"
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            r.raise_for_status()
        data = r.json()
        return [ServiceOrderSchema(**item) for item in data]

    async def delete_service_order(self, order_id: int) -> bool:
        url = f"{EXTERNAL_API_BASE_URL}/serviceorders/{order_id}"
        async with httpx.AsyncClient() as client:
            r = await client.delete(url)
            r.raise_for_status()
        return True

    async def delete_service_orders_for_reservation(self, reservation_id: int) -> bool:
        url = f"{EXTERNAL_API_BASE_URL}/serviceorders/for_reservation/{reservation_id}"
        async with httpx.AsyncClient() as client:
            r = await client.delete(url)
            r.raise_for_status()
        return True