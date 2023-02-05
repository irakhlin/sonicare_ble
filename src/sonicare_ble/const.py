TIMEOUT_RECENTLY_BRUSHING = 20
NOT_BRUSHING_UPDATE_INTERVAL_SECONDS = 30
BRUSHING_UPDATE_INTERVAL_SECONDS = 15

SONICARE_ADVERTISMENT_UUID = "477ea600-a260-11e4-ae37-0002a5d50001"
SONICARE_STATE_SERVICE = "477ea600-a260-11e4-ae37-0002a5d50002"
SONICARE_BRUSH_SERVICE = "477ea600-a260-11e4-ae37-0002a5d50006"

# In Use
CHARACTERISTIC_BATTERY = "00002a19-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_MODEL = "00002a24-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_BRUSHING_TIME = "477ea600-a260-11e4-ae37-0002a5d54090"
CHARACTERISTIC_STATE = "477ea600-a260-11e4-ae37-0002a5d54010"
CHARACTERISTIC_CURRENT_TIME = "477ea600-a260-11e4-ae37-0002a5d54050"
CHARACTERISTIC_MODE = "477ea600-a260-11e4-ae37-0002a5d54091"
CHARACTERISTIC_STRENGTH = "477ea600-a260-11e4-ae37-0002a5d540b0"

# Extra
CHARACTERISTIC_BRUSH_USAGE = "477ea600-a260-11e4-ae37-0002a5d54290"
CHARACTERISTIC_BRUSH_LIFETIME = "477ea600-a260-11e4-ae37-0002a5d54280"
CHARACTERISTIC_SERIAL_NUMBER = "477ea600-a260-11e4-ae37-0002a5d54230"
CHARACTERISTIC_BRUSH_SERIAL_NUMBER = "477ea600-a260-11e4-ae37-0002a5d54230"


CHAR_DICT = {
    "BATTERY": ("00002a19-0000-1000-8000-00805f9b34fb", "battery"),
    "MODEL": ("00002a24-0000-1000-8000-00805f9b34fb", "model"),
    "BRUSHING_TIME": ("477ea600-a260-11e4-ae37-0002a5d54090", "brushing_time", "Brushing time"),
    "STATE": ("477ea600-a260-11e4-ae37-0002a5d54010", "toothbrush_state", "Toothbrush State"),
    "BRUSH_STATE": ("477ea600-a260-11e4-ae37-0002a5d54010", "brush_state", "Toothbrush State"),
    "CURRENT_TIME": ("477ea600-a260-11e4-ae37-0002a5d54050", "current_time", "Toothbrush current time"),
    "MODE": ("477ea600-a260-11e4-ae37-0002a5d54091", "mode", "Toothbrush current mode"),
    "STRENGTH": ("477ea600-a260-11e4-ae37-0002a5d540b0", "brush_strength", "Toothbrush current strength"),
    "BRUSH_USAGE": ("477ea600-a260-11e4-ae37-0002a5d54290", "brush_head_usage"),
    "BRUSH_HEAD_LIFETIME": ("477ea600-a260-11e4-ae37-0002a5d54280", "brush_head_lifetime"),
    "BRUSH_SERIAL_NUMBER": ("477ea600-a260-11e4-ae37-0002a5d54230", "brush_serial_number", "Toothbrush serial number"),
    "SESSION_ID": ("477ea600-a260-11e4-ae37-0002a5d54230", "current_session_id")
}
