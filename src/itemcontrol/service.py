from __future__ import annotations

import unicodedata

from .domain import ItemControlError, NotFoundError, ValidationError
from .repository import DEVICE_STATUSES, SQLiteRepository


DEVICE_IMPORT_COLUMNS = (
    "serial",
    "name",
    "device_type",
    "status",
    "user",
    "country",
    "location",
    "note",
)


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
    def _fold(text: str | None) -> str:
        clean_text = InventoryService._clean(text) or ""
        normalized = unicodedata.normalize("NFKD", clean_text)
        return normalized.encode("ascii", "ignore").decode("ascii").lower()

    @staticmethod
    def _require_positive_quantity(quantity: int) -> None:
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than 0.")

    @staticmethod
    def _require_device_status(status: str | None) -> str:
        clean_status = InventoryService._clean(status)
        if not clean_status:
            raise ValidationError("Device status is required.")
        folded_status = InventoryService._fold(clean_status)
        for valid_status in DEVICE_STATUSES:
            if folded_status == InventoryService._fold(valid_status):
                return valid_status
        raise ValidationError("Invalid device status.")

    @staticmethod
    def _is_available_status(status: str) -> bool:
        return InventoryService._fold(status) == "disponivel"

    @staticmethod
    def _requires_device_user(status: str) -> bool:
        return InventoryService._fold(status) == "em uso"

    @staticmethod
    def _is_active_row(row) -> bool:
        return bool(int(row.get("is_active", 1)))

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
        device_type = self.repository.get_device_type(device_type_id)
        if device_type is None:
            raise NotFoundError("Device type not found.")
        if not self._is_active_row(device_type):
            raise ValidationError("Device type is inactive.")
        if self._requires_device_user(clean_status):
            if user_id is None:
                raise ValidationError("User is required for devices in use.")
            user = self.repository.get_device_user(user_id)
            if user is None:
                raise NotFoundError("User not found.")
            if not self._is_active_row(user):
                raise ValidationError("User is inactive.")
        else:
            user_id = None
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

    def update_device_details(
        self,
        device_id: int,
        serial: str,
        name: str,
        device_type_id: int,
        status: str,
        location_id: int,
        user_id: int | None = None,
        note: str = "",
    ) -> None:
        device = self.repository.get_device(device_id)
        if device is None:
            raise NotFoundError("Device not found.")

        clean_serial = self._clean(serial)
        clean_name = self._clean(name)
        clean_status = self._require_device_status(status)
        clean_note = self._clean(note)
        if not clean_serial:
            raise ValidationError("Device serial is required.")
        if not clean_name:
            raise ValidationError("Device name is required.")
        if self.repository.get_device_by_serial_casefold_excluding(
            clean_serial, device_id
        ) is not None:
            raise ValidationError("Device serial already exists.")
        if self.repository.get_location(location_id) is None:
            raise NotFoundError("Location not found.")
        device_type = self.repository.get_device_type(device_type_id)
        if device_type is None:
            raise NotFoundError("Device type not found.")
        if (
            int(device["device_type_id"]) != int(device_type_id)
            and not self._is_active_row(device_type)
        ):
            raise ValidationError("Device type is inactive.")

        if self._requires_device_user(clean_status):
            if user_id is None:
                raise ValidationError("User is required for devices in use.")
            user = self.repository.get_device_user(user_id)
            if user is None:
                raise NotFoundError("User not found.")
            if device["user_id"] != user_id and not self._is_active_row(user):
                raise ValidationError("User is inactive.")
        else:
            user_id = None

        changed_assignment = (
            int(device["location_id"]) != int(location_id)
            or device["user_id"] != user_id
            or device["status"] != clean_status
        )
        with self.repository.transaction():
            self.repository.update_device_details(
                device_id,
                clean_serial,
                clean_name,
                device_type_id,
                clean_status,
                location_id,
                user_id,
                clean_note,
            )
            if changed_assignment:
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

    def toggle_device_deactivated(self, device_id: int) -> str:
        device = self.repository.get_device(device_id)
        if device is None:
            raise NotFoundError("Device not found.")
        new_status = "Disponível" if device["status"] == "Desativado" else "Desativado"
        self.update_device_details(
            device_id,
            device["serial"],
            device["name"],
            int(device["device_type_id"]),
            new_status,
            int(device["location_id"]),
            None,
            device["note"] or "",
        )
        return new_status

    def update_device_user_name(self, user_id: int, name: str) -> None:
        clean_name = self._clean(name)
        if not clean_name:
            raise ValidationError("User name is required.")
        if self.repository.get_device_user(user_id) is None:
            raise NotFoundError("User not found.")
        try:
            self.repository.update_device_user_name(user_id, clean_name)
        except Exception as exc:
            raise ValidationError(f"Could not update user: {exc}") from exc

    def update_device_type_name(self, type_id: int, name: str) -> None:
        clean_name = self._clean(name)
        if not clean_name:
            raise ValidationError("Device type name is required.")
        if self.repository.get_device_type(type_id) is None:
            raise NotFoundError("Device type not found.")
        try:
            self.repository.update_device_type_name(type_id, clean_name)
        except Exception as exc:
            raise ValidationError(f"Could not update device type: {exc}") from exc

    def set_device_user_active(self, user_id: int, is_active: bool) -> None:
        if self.repository.get_device_user(user_id) is None:
            raise NotFoundError("User not found.")
        self.repository.set_device_user_active(user_id, is_active)

    def set_device_type_active(self, type_id: int, is_active: bool) -> None:
        if self.repository.get_device_type(type_id) is None:
            raise NotFoundError("Device type not found.")
        self.repository.set_device_type_active(type_id, is_active)

    def validate_device_import_rows(self, rows: list[dict[str, str]]) -> dict:
        return self._process_device_import_rows(rows, import_valid=False)

    def import_device_rows(self, rows: list[dict[str, str]]) -> dict:
        return self._process_device_import_rows(rows, import_valid=True)

    def _process_device_import_rows(
        self,
        rows: list[dict[str, str]],
        import_valid: bool,
    ) -> dict:
        serial_counts: dict[str, int] = {}
        for row in rows:
            serial = self._clean(row.get("serial"))
            if serial:
                key = self._fold(serial)
                serial_counts[key] = serial_counts.get(key, 0) + 1

        results = []
        imported_count = 0
        for index, row in enumerate(rows, start=1):
            result = self._validate_device_import_row(row, serial_counts, index)
            if import_valid and result["valid"]:
                try:
                    self._import_valid_device_row(result["data"])
                except ItemControlError as exc:
                    result["valid"] = False
                    result["errors"].append(str(exc))
                else:
                    result["imported"] = True
                    imported_count += 1
            results.append(result)

        invalid_count = len([result for result in results if not result["valid"]])
        return {
            "rows": results,
            "total": len(rows),
            "valid": len(rows) - invalid_count,
            "invalid": invalid_count,
            "imported": imported_count,
        }

    def _validate_device_import_row(
        self,
        row: dict[str, str],
        serial_counts: dict[str, int],
        row_number: int,
    ) -> dict:
        errors: list[str] = []
        serial = self._clean(row.get("serial"))
        name = self._clean(row.get("name"))
        device_type_name = self._clean(row.get("device_type"))
        status_text = self._clean(row.get("status"))
        user_name = self._clean(row.get("user"))
        country_name = self._clean(row.get("country"))
        location_name = self._clean(row.get("location"))
        note = self._clean(row.get("note"))

        status = None
        if serial:
            serial_key = self._fold(serial)
            if serial_counts.get(serial_key, 0) > 1:
                errors.append("Serial duplicado no CSV.")
            elif self.repository.get_device_by_serial_casefold(serial) is not None:
                errors.append("Serial ja existe na base.")
        else:
            errors.append("Serial e obrigatorio.")

        if not name:
            errors.append("Nome do device e obrigatorio.")
        if not device_type_name:
            errors.append("Tipo do device e obrigatorio.")
        if not country_name:
            errors.append("Pais e obrigatorio.")
        if not location_name:
            errors.append("Local e obrigatorio.")

        if status_text:
            try:
                status = self._require_device_status(status_text)
            except ValidationError as exc:
                errors.append(str(exc))
        else:
            errors.append("Status e obrigatorio.")

        country_id = None
        location_id = None
        if country_name:
            country = self.repository.get_country_by_name(country_name)
            if country is None:
                errors.append("Pais nao encontrado.")
            else:
                country_id = int(country["id"])
        if country_id is not None and location_name:
            location = self.repository.get_location_by_country_and_name(
                country_id, location_name
            )
            if location is None:
                errors.append("Local nao encontrado para o pais informado.")
            else:
                location_id = int(location["id"])

        device_type_id = None
        will_create_type = False
        if device_type_name:
            device_type = self.repository.get_device_type_by_name(device_type_name)
            if device_type is None:
                will_create_type = True
            elif not self._is_active_row(device_type):
                errors.append("Tipo do device esta inativo.")
            else:
                device_type_id = int(device_type["id"])

        user_id = None
        will_create_user = False
        if status is not None and self._requires_device_user(status):
            if not user_name:
                errors.append("Usuario e obrigatorio para devices em uso.")
            else:
                user = self.repository.get_device_user_by_name(user_name)
                if user is None:
                    will_create_user = True
                elif not self._is_active_row(user):
                    errors.append("Usuario esta inativo.")
                else:
                    user_id = int(user["id"])
        elif status is not None:
            user_name = None

        data = {
            "serial": serial,
            "name": name,
            "device_type_name": device_type_name,
            "device_type_id": device_type_id,
            "will_create_type": will_create_type,
            "status": status,
            "user_name": user_name,
            "user_id": user_id,
            "will_create_user": will_create_user,
            "country_name": country_name,
            "location_name": location_name,
            "location_id": location_id,
            "note": note,
        }
        return {
            "row": row_number,
            "valid": not errors,
            "errors": errors,
            "data": data,
            "imported": False,
        }

    def _import_valid_device_row(self, data: dict) -> int:
        device_type_id = data["device_type_id"]
        if device_type_id is None:
            device_type_id = self.create_device_type(data["device_type_name"])

        user_id = data["user_id"]
        if data["user_name"] and user_id is None:
            user_id = self.create_device_user(data["user_name"])

        return self.create_device(
            data["serial"],
            data["name"],
            device_type_id,
            data["status"],
            data["location_id"],
            user_id,
            data["note"] or "",
        )

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
        if self._requires_device_user(clean_status):
            if user_id is None:
                raise ValidationError("User is required for devices in use.")
            user = self.repository.get_device_user(user_id)
            if user is None:
                raise NotFoundError("User not found.")
            if not self._is_active_row(user):
                raise ValidationError("User is inactive.")
        else:
            user_id = None

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

    def active_device_users(self):
        return self.repository.list_active_device_users()

    def device_types(self):
        return self.repository.list_device_types()

    def active_device_types(self):
        return self.repository.list_active_device_types()

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

    def dashboard_devices(
        self,
        country_id: int | None = None,
        location_id: int | None = None,
        device_query: str | None = None,
    ) -> dict:
        if not self.repository.has_device_schema():
            return {
                "total_devices": 0,
                "by_status": [],
                "by_type": [],
                "details": [],
            }
        clean_query = self._clean(device_query)
        rows = self.repository.list_dashboard_devices(
            country_id=country_id,
            location_id=location_id,
            device_query=clean_query,
        )
        total_devices = len(rows)
        status_totals: dict[str, int] = {}
        type_totals: dict[str, int] = {}
        for row in rows:
            status = row["status"]
            device_type_name = row["device_type_name"]
            status_totals[status] = status_totals.get(status, 0) + 1
            type_totals[device_type_name] = type_totals.get(device_type_name, 0) + 1

        by_status = [
            {"name": name, "quantity": quantity}
            for name, quantity in status_totals.items()
        ]
        by_status.sort(key=lambda row: (-row["quantity"], row["name"].lower()))

        by_type = [
            {"name": name, "quantity": quantity}
            for name, quantity in type_totals.items()
        ]
        by_type.sort(key=lambda row: (-row["quantity"], row["name"].lower()))

        return {
            "total_devices": total_devices,
            "by_status": by_status,
            "by_type": by_type,
            "details": rows,
        }
