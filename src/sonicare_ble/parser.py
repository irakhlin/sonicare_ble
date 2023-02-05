"""Parser for Sonicare BLE advertisements."""
from __future__ import annotations

import asyncio
import logging
import time

from dataclasses import dataclass
from enum import Enum, auto

from bleak import BLEDevice, BleakGATTCharacteristic
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import SensorDeviceClass, SensorUpdate, Units
from sensor_state_data.enum import StrEnum

from .const import (
    BRUSHING_UPDATE_INTERVAL_SECONDS,
    CHARACTERISTIC_BATTERY,
    CHARACTERISTIC_BRUSHING_TIME,
    CHARACTERISTIC_CURRENT_TIME,
    CHARACTERISTIC_STATE,
    NOT_BRUSHING_UPDATE_INTERVAL_SECONDS,
    TIMEOUT_RECENTLY_BRUSHING,
    CHARACTERISTIC_BRUSH_USAGE,
    CHARACTERISTIC_BRUSH_LIFETIME,
    CHARACTERISTIC_SERIAL_NUMBER,
    CHARACTERISTIC_STRENGTH,
    CHARACTERISTIC_MODE,
    SONICARE_ADVERTISMENT_UUID,
    CHAR_DICT
)

_LOGGER = logging.getLogger(__name__)


class SonicareSensor(StrEnum):
    BRUSHING_TIME = "brushing_time"
    CURRENT_TIME = "current_time"
    TOOTHBRUSH_STATE = "toothbrush_state"
    MODE = "mode"
    SIGNAL_STRENGTH = "signal_strength"
    BATTERY_PERCENT = "battery_percent"
    BRUSH_STRENGTH = "brush_strength"
    BRUSH_HEAD_LIFETIME = "brush_head_lifetime"
    BRUSH_HEAD_USAGE = "brush_head_usage"
    BRUSH_SERIAL_NUMBER = "brush_serial_number"
    BRUSH_LIFETIME_PERCENTAGE = "brush_head_percentage"
    BRUSH_SESSION_ID = "current_session_id"


class SonicareBinarySensor(StrEnum):
    BRUSHING = "brushing"


class Models(Enum):
    HX6340 = auto()
    HX992X = auto()
    HX9990 = auto()


@dataclass
class ModelDescription:
    device_type: str
    modes: dict[int, str]


KIDS_MODES = {
    0: "none"
}

EXPERT_CLEAN_MODES = {
    120: "clean",
    200: "gun health",
    180: "deep clean+",
}
DIAMOND_CLEAN_MODES = EXPERT_CLEAN_MODES | {160: "white+"}
PRESTIGE_MODES = DIAMOND_CLEAN_MODES | {210: "sensitive"}

MODES = {

}
DEVICE_TYPES = {
    Models.HX6340: ModelDescription(
        device_type="HX6340",
        modes=KIDS_MODES
    ),
    Models.HX992X: ModelDescription(
        device_type="HX992X",
        modes=DIAMOND_CLEAN_MODES
    ),
    Models.HX9990: ModelDescription(
        device_type="HX9990",
        modes=PRESTIGE_MODES
    )
}

STRENGTH = {
    0: "low",
    1: "medium",
    2: "high"
}

STATES = {
    0: "off",
    1: "standby",
    2: "run",
    3: "charge",
    4: "shutdown",
    6: "validate",
    7: "lightsout",
}

BYTES_TO_MODEL = {
    b"\x062k": Models.HX6340,
    b"\x2a24": Models.HX992X,
    b"\x9999": Models.HX9990,
}


class SonicareBluetoothDeviceData(BluetoothData):
    """Data for Sonicare BLE sensors."""

    def __init__(self) -> None:
        # If this is True, we are currently brushing or were brushing as of the last advertisement data
        self._brushing = False
        self._last_brush = 0.0
        self._model = None
        self._device = None
        self._client = None
        self._session = None
        self._notify_future: asyncio.Future[bytearray] | None = None
        super().__init__()

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing Sonicare BLE advertisement data: %s", service_info)
        service_uuids = service_info.service_uuids
        address = service_info.address
        if (
            SONICARE_ADVERTISMENT_UUID not in service_uuids
        ):
            _LOGGER.debug("Not a Philips Sonicare BLE advertisement for address: %s", address)
            return


        self.set_device_manufacturer("Philips Sonicare")
        # model = BYTES_TO_MODEL.get(device_bytes, Models.HX6340)
        model = Models.HX992X
        self._model = model
        model_info = DEVICE_TYPES[model]
        self.set_device_type(model_info.device_type)
        name = f"{model_info.device_type} {short_address(address)}"
        self.set_device_name(name)
        self.set_title(name)

    def poll_needed(
        self, service_info: BluetoothServiceInfo, last_poll: float | None
    ) -> bool:
        """
        This is called every time we get a service_info for a device. It means the
        device is working and online.
        """
        _LOGGER.debug("poll_needed called")
        if last_poll is None:
            return True
        update_interval = NOT_BRUSHING_UPDATE_INTERVAL_SECONDS
        if (
            self._brushing
            or time.monotonic() - self._last_brush <= TIMEOUT_RECENTLY_BRUSHING
        ):
            update_interval = BRUSHING_UPDATE_INTERVAL_SECONDS
        _LOGGER.debug("poll_needed returning update_interval of %s", update_interval)
        return last_poll > update_interval

    async def async_poll(self, ble_device: BLEDevice) -> SensorUpdate:
        """
        Poll the device to retrieve any values we can't get from passive listening.
        """
        _LOGGER.debug("async_poll")
        client = await establish_connection(
            BleakClientWithServiceCache, ble_device, ble_device.address
        )
        new_session = False
        try:
            state_char = client.services.get_characteristic(CHAR_DICT.get("STATE")[0])
            state_payload = await client.read_gatt_char(state_char)
            tb_state = STATES.get(state_payload[0], f"unknown state {state_payload[0]}")
            _LOGGER.debug("brushing state is changing to %s the payload is %s", tb_state, state_payload[0])

            battery_char = client.services.get_characteristic(CHARACTERISTIC_BATTERY)
            battery_payload = await client.read_gatt_char(battery_char)

            current_time_char = client.services.get_characteristic(
                CHARACTERISTIC_CURRENT_TIME
            )
            current_time_payload = await client.read_gatt_char(current_time_char)
            current_time_epoch = int.from_bytes(current_time_payload, "little")
            current_time_stamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time_epoch))

            if tb_state == "run" or int.from_bytes(state_payload[0], "little") == 2:
                self._brushing = True
                self._last_brush = time.monotonic()
                _LOGGER.debug("Toothbrush is running, subscribing to events")
                await client.start_notify(CHAR_DICT.get("STATE")[0], self._notification_handler)
                await client.start_notify(CHAR_DICT.get("BRUSHING_TIME")[0], self._notification_handler)
                await client.start_notify(CHAR_DICT.get("MODE")[0], self._notification_handler)
                await client.start_notify(CHAR_DICT.get("STRENGTH")[0], self._notification_handler)

            else:
                self._brushing = False
                await client.stop_notify(CHAR_DICT.get("STATE")[0], self._notification_handler)
                await client.stop_notify(CHAR_DICT.get("BRUSHING_TIME")[0], self._notification_handler)
                await client.stop_notify(CHAR_DICT.get("MODE")[0], self._notification_handler)
                await client.stop_notify(CHAR_DICT.get("STRENGTH")[0], self._notification_handler)
                _LOGGER.debug("not updating frequently")

            session_payload = await client.read_gatt_char(
                client.services.get_characteristic(CHAR_DICT.get("SESSION_ID")[0])
            )
            session = int.from_bytes(session_payload, "little")

            if self._session is None or self._session != session:
                self._session = session
                new_session = True
                _LOGGER.debug(f"New brushing session: {session}")
                brush_serial_number_char = client.services.get_characteristic(CHAR_DICT.get("BRUSH_SERIAL_NUMBER")[0])
                serial_number_payload = await client.read_gatt_char(brush_serial_number_char)
                serial_number = int.from_bytes(serial_number_payload, "little")

                brush_usage_char = client.services.get_characteristic(CHAR_DICT.get("BRUSH_USAGE")[0])
                brush_usage_payload = await client.read_gatt_char(brush_usage_char)
                usage = int.from_bytes(brush_usage_payload, "little")

                brush_lifetime_char = client.services.get_characteristic(CHARACTERISTIC_BRUSH_LIFETIME)
                brush_lifetime_payload = await client.read_gatt_char(brush_lifetime_char)
                lifetime = int.from_bytes(brush_lifetime_payload, "little")

                if lifetime != 0 and usage != 0:
                    brush_life_percentage_left = round(((lifetime - usage) / lifetime) * 100)
                else:
                    brush_life_percentage_left = 0

                mode_char = client.services.get_characteristic(CHARACTERISTIC_MODE)
                mode_payload = await client.read_gatt_char(mode_char)
                mode_int = int.from_bytes(mode_payload, "little")
                if self._model:
                    info = DEVICE_TYPES[self._model]
                    mode = info.modes.get(mode_int, f"unknown mode {mode_int}")
                else:
                    mode = "unknown mode"

                strength_char = client.services.get_characteristic(CHARACTERISTIC_STRENGTH)
                strength_payload = await client.read_gatt_char(strength_char)
                strength_result = STRENGTH.get(int.from_bytes(strength_payload, "little"),
                                               f"unknown speed {strength_payload}")



                brushing_time_char = client.services.get_characteristic(
                    CHARACTERISTIC_BRUSHING_TIME
                )
                brushing_time_payload = await client.read_gatt_char(brushing_time_char)

        finally:
            if not self._brushing:
                await client.disconnect()

        self.update_sensor(
            str(SonicareSensor.BATTERY_PERCENT),
            Units.PERCENTAGE,
            battery_payload[0],
            SensorDeviceClass.BATTERY,
            "Battery",
        )

        self.update_sensor(
            str(SonicareSensor.TOOTHBRUSH_STATE),
            None,
            tb_state,
            None,
            "Toothbrush State",
        )

        self.update_sensor(
            str(SonicareSensor.CURRENT_TIME),
            None,
            current_time_stamp,
            None,
            "Toothbrush current time",
        )

        if new_session:
            self.update_sensor(
                str(SonicareSensor.BRUSH_HEAD_LIFETIME),
                None,
                lifetime,
                None,
                "Brush head lifetime"
            )

            self.update_sensor(
                str(SonicareSensor.BRUSH_HEAD_USAGE),
                None,
                usage,
                None,
                "Brush head usage"
            )

            self.update_sensor(
                str(SonicareSensor.BRUSH_SERIAL_NUMBER),
                None,
                serial_number,
                None,
                "Toothbrush serial number"
            )

            self.update_sensor(
                str(SonicareSensor.BRUSH_LIFETIME_PERCENTAGE),
                None,
                brush_life_percentage_left,
                None,
                "Brush head remaining"
            )

            self.update_sensor(
                str(SonicareSensor.BRUSH_SESSION_ID),
                None,
                session,
                None,
                "Session ID"
            )
            self.update_sensor(
                str(SonicareSensor.BRUSHING_TIME),
                None,
                int.from_bytes(brushing_time_payload, "little"),
                None,
                "Brushing time",
            )
            self.update_sensor(
                str(SonicareSensor.MODE),
                None,
                mode,
                None,
                "Toothbrush current mode"
            )

            self.update_sensor(
                str(SonicareSensor.BRUSH_STRENGTH),
                None,
                strength_result,
                None,
                "Toothbrush current strength"
            )
        return self._finish_update()

    def _notification_handler(self, _sender: BleakGATTCharacteristic, data: bytearray) -> SensorUpdate:
        """Start notification"""
        _LOGGER.error(f"notification handler executed for {_sender.uuid} with value of {data}")
        if _sender.uuid == CHAR_DICT.get("STATE")[0]:
            sensor_value = STATES.get(data[0], f"unknown state {data[0]}")
            sensor_id = CHAR_DICT.get("STATE")[1]
            sensor_string = CHAR_DICT.get("STATE")[2]
            if sensor_value != 2:
                self._brushing = False
                _LOGGER.error("brushing ended")
            else:
                self._last_brush = time.monotonic()
                self._brushing = True
                _LOGGER.error("brushing started")
            self.update_sensor(
                str(SonicareSensor.TOOTHBRUSH_STATE),
                None,
                sensor_value,
                None,
                "Toothbrush State",
            )
            return self._finish_update()
        elif _sender.uuid == CHAR_DICT.get("BRUSHING_TIME")[0]:
            value = int.from_bytes(data, "little")
            sensor_value = value
            sensor_id = CHAR_DICT.get("BRUSHING_TIME")[1]
            sensor_string = CHAR_DICT.get("BRUSHING_TIME")[2]
        elif _sender.uuid == CHAR_DICT.get("MODE")[0]:
            value = int.from_bytes(data, "little")
            sensor_value = DEVICE_TYPES[self._model].modes.get(value, f"unknown mode")
            sensor_id = CHAR_DICT.get("MODE")[1]
            sensor_string = CHAR_DICT.get("MODE")[2]
        elif _sender.uuid == CHAR_DICT.get("STRENGTH")[0]:
            value = int.from_bytes(data, "little")
            sensor_value = STRENGTH.get(value, f"unknown speed")
            sensor_id = CHAR_DICT.get("STRENGTH")[1]
            sensor_string = CHAR_DICT.get("STRENGTH")[2]

        self.update_sensor(
            sensor_id,
            None,
            sensor_value,
            None,
            sensor_string
        )
        return self._finish_update()
    
