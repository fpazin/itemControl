from __future__ import annotations

from .domain import NotFoundError, ValidationError
from .repository import DEVICE_STATUSES, SQLiteRepository


class InventoryService:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    @staticmethod
    def _clean(text: str | None) -> str | None:
        if text is None:
            return None
        cleaned = text.strip()
        return cleaned if cleaned else None

    @staticmethod
    def _require_positive_quantity(quantity: int) -> None:
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than 0.")

    @staticmethod
    def _require_device_status(status: str | None) -> str:
        clean_status = InventoryService._clean(status)
        if not clean_status:
            raise ValidationError("Device status is required.")
        if clean_status not in DEVICE_STATUSES:
            raise ValidationError("Invalid device status.")
        return clean_status

    def create_country(self, name: str) -> int:
        clean_name = self._clean(name)
        if not clean_name:
            raise ValidationError("Country name is required.")
        try:
            return self.repository.create_country(clean_name)
        except Exception as exc:
            raise ValidationError(f"Could not create country: {exc}") from exc

    def create_location(self, country_id: int, name: str) -> int:
        clean_name = self._clean(name)
        if not clean_name:
            raise ValidationError("Location name is required.")
        if self.repository.get_country(country_id) is None:
            raise NotFoundError("Country not found.")
        try:
            return self.repository.create_location(country_id, clean_name)
        except Exception as exc:
            raise ValidationError(f"Could not create location: {exc}") from exc

    def create_item(self, serial: str | None, name: str) -> int:
        clean_serial = self._clean(serial)
        clean_name = self._clean(name)
        if not clean_name:
            raise ValidationError("Item name is required.")
        try:
            return self.repository.create_item(clean_serial, clean_name)
        except Exception as exc:
            raise ValidationError(f"Could not create item: {exc}") from exc

    def create_device_user(self, name: str) -> int:
        clean_name = self._clean(name)
        if not clean_name:
            raise ValidationError("User name is required.")
        try:
            return self.repository.create_device_user(clean_name)
        except Exception as exc:
            raise ValidationError(f"Could not create user: {exc}") from exc

    def create_device_type(self, name: str) -> int:
        clean_name = self._clean(name)
        if not clean_name:
            raise ValidationError("Device type name is required.")
        try:
            return self.repository.create_device_type(clean_name)
        except Exception as exc:
            raise ValidationError(f"Could not create device type: {exc}") from exc

    def create_device(
        self,
        serial: str,
        name: str,
        device_type_id: int,
        status: str,
        location_id: int,
        user_id: int | None = None,
        note: str = "",
    ) -> int:
        clean_serial = self._clean(serial)
        clean_name = self._clean(name)
        clean_status = self._require_device_status(status)
        clean_note = self._clean(note)
        if not clean_serial:
            raise ValidationError("Device serial is required.")
        if not clean_name:
            raise ValidationError("Device name is required.")
        if self.repository.get_location(location_id) is None:
            raise NotFoundError("Location not found.")
        if self.repository.get_device_type(device_type_id) is None:
            raise NotFoundError("Device type not found.")
        if clean_status == "Disponível":
            user_id = None
        else:
            if user_id is None:
                raise ValidationError("User is required for devices not marked as available.")
            if self.repository.get_device_user(user_id) is None:
                raise NotFoundError("User not found.")
        try:
            return self.repository.create_device(
                clean_serial,
                clean_name,
                device_type_id,
                clean_status,
                location_id,
                user_id,
                clean_note,
            )
        except Exception as exc:
            raise ValidationError(f"Could not create device: {exc}") from exc

    def add_item_to_location(
        self,
        item_id: int,
        location_id: int,
        quantity: int = 1,
        note: str = "",
    ) -> None:
        self._require_positive_quantity(quantity)
        if self.repository.get_item(item_id) is None:
            raise NotFoundError("Item not found.")
        if self.repository.get_location(location_id) is None:
            raise NotFoundError("Location not found.")

        with self.repository.transaction():
            current_qty = self.repository.get_stock(item_id, location_id)
            self.repository.set_stock(item_id, location_id, current_qty + quantity)
            self.repository.add_movement(
                item_id,
                "ADD",
                quantity,
                None,
                location_id,
                note or None,
            )

    def remove_item_from_location(
        self,
        item_id: int,
        location_id: int,
        quantity: int = 1,
        note: str = "",
    ) -> None:
        self._require_positive_quantity(quantity)
        if self.repository.get_item(item_id) is None:
            raise NotFoundError("Item not found.")
        if self.repository.get_location(location_id) is None:
            raise NotFoundError("Location not found.")

        current_qty = self.repository.get_stock(item_id, location_id)
        if current_qty < quantity:
            raise ValidationError(
                f"Insufficient stock at location. Available: {current_qty}, requested: {quantity}"
            )

        with self.repository.transaction():
            self.repository.set_stock(item_id, location_id, current_qty - quantity)
            self.repository.add_movement(
                item_id,
                "REMOVE",
                quantity,
                location_id,
                None,
                note or None,
            )

    def transfer_item(
        self,
        item_id: int,
        from_location_id: int,
        to_location_id: int,
        quantity: int = 1,
        note: str = "",
    ) -> None:
        self._require_positive_quantity(quantity)
        if from_location_id == to_location_id:
            raise ValidationError("Origin and destination locations must be different.")
        if self.repository.get_item(item_id) is None:
            raise NotFoundError("Item not found.")
        if self.repository.get_location(from_location_id) is None:
            raise NotFoundError("Origin location not found.")
        if self.repository.get_location(to_location_id) is None:
            raise NotFoundError("Destination location not found.")

        current_origin_qty = self.repository.get_stock(item_id, from_location_id)
        if current_origin_qty < quantity:
            raise ValidationError(
                f"Insufficient stock at origin. Available: {current_origin_qty}, requested: {quantity}"
            )

        with self.repository.transaction():
            self.repository.set_stock(
                item_id, from_location_id, current_origin_qty - quantity
            )
            destination_qty = self.repository.get_stock(item_id, to_location_id)
            self.repository.set_stock(
                item_id, to_location_id, destination_qty + quantity
            )
            self.repository.add_movement(
                item_id,
                "TRANSFER",
                quantity,
                from_location_id,
                to_location_id,
                note or None,
            )

    def transfer_device(
        self,
        device_id: int,
        location_id: int,
        user_id: int | None = None,
        status: str | None = None,
        note: str = "",
    ) -> None:
        device = self.repository.get_device(device_id)
        if device is None:
            raise NotFoundError("Device not found.")
        if self.repository.get_location(location_id) is None:
            raise NotFoundError("Location not found.")

        clean_status = self._require_device_status(status or device["status"])
        clean_note = self._clean(note)
        if clean_status == "Disponível":
            user_id = None
        else:
            if user_id is None:
                raise ValidationError("User is required for devices not marked as available.")
            if self.repository.get_device_user(user_id) is None:
                raise NotFoundError("User not found.")

        with self.repository.transaction():
            self.repository.update_device(
                device_id,
                int(device["device_type_id"]),
                clean_status,
                location_id,
                user_id,
                clean_note,
            )
            self.repository.add_device_transfer(
                device_id,
                device["user_id"],
                user_id,
                device["location_id"],
                location_id,
                device["status"],
                clean_status,
                clean_note,
            )

    def countries(self):
        return self.repository.list_countries()

    def locations(self):
        return self.repository.list_locations()

    def items(self):
        return self.repository.list_items()

    def movements(self, item_id: int | None = None):
        return self.repository.list_movements(item_id=item_id)

    def device_users(self):
        return self.repository.list_device_users()

    def device_types(self):
        return self.repository.list_device_types()

    def devices(self):
        if not self.repository.has_device_schema():
            return []
        return self.repository.list_devices()

    def device_transfers(self):
        if not self.repository.has_device_schema():
            return []
        return self.repository.list_device_transfers()

    def device_assignments(self, status: str | None = None):
        if not self.repository.has_device_schema():
            return []
        return self.repository.list_device_assignments(status=status)

    def stock_for_item(self, item_id: int):
        if self.repository.get_item(item_id) is None:
            raise NotFoundError("Item not found.")
        return self.repository.list_stock_for_item(item_id)

    def location_balance(self, location_id: int) -> int:
        if self.repository.get_location(location_id) is None:
            raise NotFoundError("Location not found.")
        return self.repository.count_items_at_location(location_id)

    def total_in_inventory(self) -> int:
        return self.repository.count_items_with_location()

    def dashboard(
        self,
        country_id: int | None = None,
        location_id: int | None = None,
        item_query: str | None = None,
    ) -> dict:
        clean_query = self._clean(item_query)
        rows = self.repository.list_dashboard_stock(
            country_id=country_id,
            location_id=location_id,
            item_query=clean_query,
        )

        country_totals: dict[tuple[int, str], int] = {}
        location_totals: dict[tuple[int, str, str], int] = {}
        item_ids: set[int] = set()
        country_ids: set[int] = set()
        location_ids: set[int] = set()
        total_units = 0

        for row in rows:
            quantity = int(row["quantity"])
            total_units += quantity
            item_ids.add(int(row["item_id"]))
            country_ids.add(int(row["country_id"]))
            location_ids.add(int(row["location_id"]))

            country_key = (int(row["country_id"]), row["country_name"])
            country_totals[country_key] = country_totals.get(country_key, 0) + quantity

            location_key = (
                int(row["location_id"]),
                row["country_name"],
                row["location_name"],
            )
            location_totals[location_key] = (
                location_totals.get(location_key, 0) + quantity
            )

        by_country = [
            {"id": key[0], "name": key[1], "quantity": quantity}
            for key, quantity in country_totals.items()
        ]
        by_country.sort(key=lambda row: (-row["quantity"], row["name"].lower()))

        by_location = [
            {
                "id": key[0],
                "country_name": key[1],
                "name": key[2],
                "label": f"{key[1]} / {key[2]}",
                "quantity": quantity,
            }
            for key, quantity in location_totals.items()
        ]
        by_location.sort(
            key=lambda row: (
                -row["quantity"],
                row["country_name"].lower(),
                row["name"].lower(),
            )
        )

        return {
            "total_units": total_units,
            "distinct_items": len(item_ids),
            "countries": len(country_ids),
            "locations": len(location_ids),
            "by_country": by_country,
            "by_location": by_location[:10],
            "details": rows,
        }
