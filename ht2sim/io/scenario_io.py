from __future__ import annotations

import json

from ..core.scenario import Scenario, TagConfig
from ..core.session import Halt, ReadPage, ReadPageInv, StartAuth, WritePage

SCHEMA_VERSION = 1


def _to_int(value) -> int:
    if isinstance(value, int):
        return value
    return int(str(value).strip().lower().replace("0x", ""), 16)


def _hex(value: int, width: int) -> str:
    return f"0x{value:0{width}X}"


def action_to_dict(a) -> dict:
    if isinstance(a, StartAuth):
        return {"type": "START_AUTH", "psw_b": _hex(a.psw_b, 8)}
    if isinstance(a, ReadPage):
        return {"type": "READ_PAGE", "page": a.page}
    if isinstance(a, ReadPageInv):
        return {"type": "READ_PAGE_INV", "page": a.page}
    if isinstance(a, WritePage):
        return {"type": "WRITE_PAGE", "page": a.page, "value": _hex(a.value, 8)}
    if isinstance(a, Halt):
        return {"type": "HALT"}
    raise ValueError(f"cannot serialize action {a!r}")


def action_from_dict(d: dict):
    t = d["type"]
    if t == "START_AUTH":
        return StartAuth(_to_int(d["psw_b"]))
    if t == "READ_PAGE":
        return ReadPage(int(d["page"]))
    if t == "READ_PAGE_INV":
        return ReadPageInv(int(d["page"]))
    if t == "WRITE_PAGE":
        return WritePage(int(d["page"]), _to_int(d["value"]))
    if t == "HALT":
        return Halt()
    raise ValueError(f"unknown action type {t!r}")


def scenario_to_dict(scn: Scenario) -> dict:
    tag = scn.tag
    return {
        "version": SCHEMA_VERSION,
        "tag": {
            "ide": _hex(tag.ide, 8),
            "psw_b": _hex(tag.psw_b, 8),
            "tmcf": _hex(tag.tmcf, 2),
            "psw_t": _hex(tag.psw_t, 6),
            "user": [_hex(u, 8) for u in tag.user],
        },
        "program": [action_to_dict(a) for a in scn.program],
    }


def scenario_from_dict(d: dict) -> Scenario:
    version = d.get("version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported scenario version: {version!r}")
    t = d["tag"]
    tag = TagConfig(
        ide=_to_int(t["ide"]),
        psw_b=_to_int(t["psw_b"]),
        tmcf=_to_int(t["tmcf"]),
        psw_t=_to_int(t["psw_t"]),
        user=[_to_int(u) for u in t["user"]],
    )
    program = [action_from_dict(a) for a in d["program"]]
    return Scenario(tag=tag, program=program)


def save_scenario(scn: Scenario, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scenario_to_dict(scn), f, indent=2)


def load_scenario(path: str) -> Scenario:
    with open(path, encoding="utf-8") as f:
        return scenario_from_dict(json.load(f))
