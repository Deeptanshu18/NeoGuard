"""DSA midterm structures actively used by NeoGuard.

Demonstrates classes, inheritance, recursion, and a custom linked list using
sensor readings. This module is safe to run with real readings or demo values.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Iterable, Any


@dataclass
class Sensor:
    """Base class for all sensor types (classes + inheritance)."""
    name: str
    value: float
    unit: str
    timestamp: str = ""

    def status(self) -> str:
        return "NORMAL"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp or datetime.now().isoformat(timespec="seconds"),
            "status": self.status(),
            "class": type(self).__name__,
        }


class TemperatureSensor(Sensor):
    """Temperature sensor inherits shared fields/behavior from Sensor."""
    def status(self) -> str:
        return "CHECK" if self.value < 15 or self.value > 30 else "NORMAL"


class HumiditySensor(Sensor):
    """Humidity sensor inherits shared fields/behavior from Sensor."""
    def status(self) -> str:
        return "CHECK" if self.value < 30 or self.value > 70 else "NORMAL"


class StateSensor(Sensor):
    """Digital sensor such as movement/vibration/fever."""
    def status(self) -> str:
        return "ACTIVE" if bool(self.value) else "INACTIVE"


@dataclass
class LinkedListNode:
    data: dict
    next: Optional["LinkedListNode"] = None


class SensorReadingLinkedList:
    """Singly linked list storing the latest sensor readings in arrival order."""
    def __init__(self):
        self.head: Optional[LinkedListNode] = None
        self.tail: Optional[LinkedListNode] = None
        self.size = 0

    def append(self, data: dict) -> None:
        node = LinkedListNode(data)
        if self.head is None:
            self.head = self.tail = node
        else:
            assert self.tail is not None
            self.tail.next = node
            self.tail = node
        self.size += 1

    def delete_first(self) -> Optional[dict]:
        if self.head is None:
            return None
        removed = self.head.data
        self.head = self.head.next
        self.size -= 1
        if self.head is None:
            self.tail = None
        return removed

    def traverse(self) -> list[dict]:
        result = []
        current = self.head
        while current is not None:
            result.append(current.data)
            current = current.next
        return result

    def find(self, sensor_name: str) -> Optional[dict]:
        current = self.head
        while current is not None:
            if current.data.get("name") == sensor_name:
                return current.data
            current = current.next
        return None


def recursive_count(items: list[Any], index: int = 0) -> int:
    """Recursively count records; base case is the end of the list."""
    if index >= len(items):
        return 0
    return 1 + recursive_count(items, index + 1)


def recursive_find(items: list[dict], key: str, value: Any, index: int = 0) -> Optional[dict]:
    """Recursive linear search with an explicit base case."""
    if index >= len(items):
        return None
    if items[index].get(key) == value:
        return items[index]
    return recursive_find(items, key, value, index + 1)


def build_sensor_objects(rows: Iterable[dict]) -> list[Sensor]:
    """Convert backend/database rows into polymorphic sensor objects."""
    objects: list[Sensor] = []
    for row in rows:
        name = str(row.get("sensor_name", row.get("name", "UNKNOWN")))
        value = float(row.get("value", 0) or 0)
        unit = str(row.get("unit", ""))
        timestamp = str(row.get("timestamp", ""))
        upper = name.upper()
        if "TEMP" in upper or "NTC" in upper:
            obj = TemperatureSensor(name, value, unit, timestamp)
        elif "HUMID" in upper or "DHT11" in upper:
            obj = HumiditySensor(name, value, unit, timestamp)
        else:
            obj = StateSensor(name, value, unit, timestamp)
        objects.append(obj)
    return objects


def run_midterm_demo(rows: Iterable[dict]) -> dict:
    """Run all four DSA concepts on the supplied real/latest sensor rows."""
    objects = build_sensor_objects(rows)
    object_rows = [obj.to_dict() for obj in objects]
    history = SensorReadingLinkedList()
    for item in object_rows:
        history.append(item)
    traversed = history.traverse()
    return {
        "requirements": {
            "classes": {"status": "USED", "example": "Sensor and SensorReadingLinkedList"},
            "inheritance": {"status": "USED", "example": "TemperatureSensor, HumiditySensor and StateSensor inherit Sensor"},
            "recursion": {"status": "USED", "example": "recursive_count and recursive_find"},
            "linked_lists": {"status": "USED", "example": "SensorReadingLinkedList append, traverse, find and delete_first"},
        },
        "readings": traversed,
        "linked_list": {"size": history.size, "traversal_count": len(traversed)},
        "recursive_count": recursive_count(traversed),
        "recursive_find_temperature": recursive_find(traversed, "name", "DHT_TEMP"),
        "note": "Live rows are used when available; an empty database returns an empty demo until sensor data arrives.",
    }
