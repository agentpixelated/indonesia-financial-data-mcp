"""Safe, lossless extraction of raw facts from official IDX XBRL instances."""

from __future__ import annotations

import io
import math
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException


XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
_MAX_MEMBERS = 10_000
_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024



def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, local_name: str) -> str | None:
    for child in element.iter():
        if _local_name(child.tag) == local_name:
            return child.text
    return None


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > _MAX_MEMBERS:
        raise ValueError("XBRL ZIP contains too many members")
    total = 0
    for info in members:
        path = PurePosixPath(info.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe ZIP member: {info.filename}")
        total += info.file_size
        if total > _MAX_UNCOMPRESSED_BYTES:
            raise ValueError("XBRL ZIP uncompressed content exceeds maximum size")
    bad_member = archive.testzip()
    if bad_member:
        raise ValueError(f"corrupt ZIP member: {bad_member}")
    return members


def _period(context: ET.Element) -> dict[str, Any]:
    instant = _child_text(context, "instant")
    if instant:
        return {"type": "instant", "instant": instant}
    start_date = _child_text(context, "startDate")
    end_date = _child_text(context, "endDate")
    if start_date or end_date:
        return {"type": "duration", "start_date": start_date, "end_date": end_date}
    if any(_local_name(child.tag) == "forever" for child in context.iter()):
        return {"type": "forever"}
    return {"type": "unknown"}


def _contexts(root: ET.Element) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for context in root:
        if context.tag != f"{{{XBRLI}}}context" or not context.get("id"):
            continue
        identifier = next(
            (child for child in context.iter() if _local_name(child.tag) == "identifier"),
            None,
        )
        dimensions = []
        for child in context.iter():
            local = _local_name(child.tag)
            if local == "explicitMember":
                dimensions.append(
                    {"axis": child.get("dimension"), "member": (child.text or "").strip()}
                )
            elif local == "typedMember":
                value = "".join(child.itertext()).strip()
                dimensions.append(
                    {"axis": child.get("dimension"), "typed_member": value}
                )
        result[context.get("id", "")] = {
            "id": context.get("id"),
            "entity": {
                "identifier": (identifier.text or "").strip() if identifier is not None else None,
                "scheme": identifier.get("scheme") if identifier is not None else None,
            },
            "period": _period(context),
            "dimensions": dimensions,
        }
    return result


def _units(root: ET.Element) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for unit in root:
        if unit.tag != f"{{{XBRLI}}}unit" or not unit.get("id"):
            continue
        measures = [
            (child.text or "").strip()
            for child in unit.iter()
            if _local_name(child.tag) == "measure" and (child.text or "").strip()
        ]
        result[unit.get("id", "")] = {"id": unit.get("id"), "measures": measures}
    return result


def _numeric_value(raw_value: str | None, unit_ref: str | None) -> str | None:
    if raw_value is None or unit_ref is None:
        return None
    try:
        value = Decimal(raw_value.strip())
    except (InvalidOperation, AttributeError):
        return None
    if not value.is_finite():
        return None
    return str(value)


def parse_instance_zip(
    content: bytes,
    *,
    concept: str = "",
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    """Parse a single ``instance.xbrl`` while preserving raw filing semantics."""

    if not 1 <= limit <= 5_000:
        raise ValueError("limit must be between 1 and 5000")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = _safe_members(archive)
            instances = [
                member
                for member in members
                if PurePosixPath(member.filename.replace("\\", "/")).name.lower()
                == "instance.xbrl"
            ]
            if len(instances) != 1:
                raise ValueError("XBRL ZIP must contain exactly one instance.xbrl")
            xml = archive.read(instances[0])
    except zipfile.BadZipFile as exc:
        raise ValueError("attachment is not a valid ZIP archive") from exc

    try:
        root = SafeET.fromstring(xml)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise ValueError(f"Unsafe or invalid XBRL XML: {exc}") from exc

    contexts = _contexts(root)
    units = _units(root)
    needle = concept.strip().casefold()
    facts: list[dict[str, Any]] = []
    for element in root:
        context_ref = element.get("contextRef")
        if context_ref is None:
            continue
        local_name = _local_name(element.tag)
        if needle and needle not in local_name.casefold() and needle not in element.tag.casefold():
            continue
        nil = element.get(f"{{{XSI}}}nil", "").casefold() == "true"
        raw_value = None if nil else (element.text or "").strip()
        unit_ref = element.get("unitRef")
        numeric_value = _numeric_value(raw_value, unit_ref)
        value_type = "nil" if nil else "number" if numeric_value is not None else "text"
        facts.append(
            {
                "concept": local_name,
                "concept_qname": element.tag,
                "context_ref": context_ref,
                "context": contexts.get(context_ref),
                "unit_ref": unit_ref,
                "unit": units.get(unit_ref) if unit_ref else None,
                "decimals": element.get("decimals"),
                "precision": element.get("precision"),
                "value_type": value_type,
                "raw_value": raw_value,
                "numeric_value": numeric_value,
            }
        )

    total = len(facts)
    return {
        "facts": facts[offset : offset + limit],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
