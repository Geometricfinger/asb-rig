#!/usr/bin/env python3
"""Regenerate oiris/features/rf_tables.json (M-03) from two public registries:

  * Bluetooth SIG Assigned Numbers, company identifiers (YAML):
    https://bitbucket.org/bluetooth-SIG/public/raw/main/assigned_numbers/company_identifiers/company_identifiers.yaml
  * IEEE Registration Authority, MA-L (OUI) public listing (CSV):
    https://standards-oui.ieee.org/oui/oui.csv

Only factual identifier -> organisation facts are used. The coarse device TYPE for a company is
our own curated judgement (COMPANY_RULES below), not data from either registry. Camera OUIs are
the MA-L blocks of organisations whose main product line is IP / home security cameras; a match
is only a *hint* ("camera_like"), never proof, and never names a person.

usage: make_rf_tables.py company_identifiers.yaml oui.csv [--retrieved YYYY-MM-DD]"""
from __future__ import annotations
import argparse, csv, json, re
from pathlib import Path

COMPANY_RULES = [  # (regex on SIG company name, coarse type)
    (r"^Apple, Inc\.$|^Samsung Electronics Co\. Ltd\.$|^Google$|^Google LLC$|^OnePlus |^GuangDong Oppo |^vivo Mobile |"
     r"^Motorola$|^LG Electronics$|^Xiaomi Inc\.$|^Sony Corporation$|^Meta Platforms", "phone_or_wearable"),
    (r"^Garmin International|^Polar Electro|^Suunto Oy$|^Oura Health|^Withings$|^Anhui Huami |^Peloton ", "fitness_wearable"),
    (r"^Microsoft$|^Logitech International SA$|^Dell Computer Corporation$|^Lenovo \(Singapore\)|^Intel Corp\.$|^Nintendo Co|^Valve Corporation$",
     "pc_or_peripheral"),
    (r"^Nordic Semiconductor ASA$|^Espressif Systems|^Texas Instruments Inc\.$|^Silicon Laboratories$|^Telink Semiconductor|"
     r"^Cypress Semiconductor$|^Realtek Semiconductor Corporation$|^Broadcom Corporation$|^Infineon Technologies AG$|^Qualcomm Technologies, Inc\.$",
     "iot_module"),
    (r"^Signify Netherlands|^Nest Labs Inc\.$|^Sonos Inc$|^Hangzhou Tuya |^Amazon\.com Services LLC$|^Wyze Labs, Inc$", "smart_home"),
    (r"^Bose Corporation$|^Bang & Olufsen|^Beats Electronics$|^Harman International|^Skullcandy|^Shure Inc$", "audio_device"),
    (r"^Tile, Inc\.$", "beacon"),
    (r"^Dexcom, Inc\.$|^Medtronic Inc\.$|^Abbott$|^Abbott Medical$", "medical_device"),
    (r"^Tesla, Inc\.$|^Ford Motor Company$|^Volkswagen AG$", "vehicle"),
]
CAMERA_ORGS = r"^(Hangzhou Hikvision Digital Technology|Prama Hikvision India|Zhejiang Dahua Technology|ZHEJIANG DAHUA TECHNOLOGYCO|" \
              r"Axis Communications AB|Hanwha Vision|HANWHA VISION|SAMSUNG TECHWIN|Zhejiang Uniview Technologies|Vivotek|Mobotix AG|" \
              r"Reolink Innovation|Arlo Technology|Hangzhou Ezviz Software|Ring LLC|Avigilon)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("company_yaml"); ap.add_argument("oui_csv"); ap.add_argument("--retrieved", required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "oiris/features/rf_tables.json"))
    a = ap.parse_args()
    ents = re.findall(r"value: (0x[0-9A-Fa-f]+)\s+name: '(.*?)'\n", Path(a.company_yaml).read_text(encoding="utf-8"))
    companies = {}
    for v, name in ents:
        for rx, t in COMPANY_RULES:
            if re.search(rx, name):
                companies[f"0x{int(v, 16):04X}"] = {"type": t, "org": name}
                break
    ouis = {}
    with open(a.oui_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["Registry"] == "MA-L" and re.search(CAMERA_ORGS, r["Organization Name"].strip(), re.I):
                h = r["Assignment"].strip().lower()
                ouis[":".join(h[i:i + 2] for i in (0, 2, 4))] = r["Organization Name"].strip()
    out = {"sources": {"company_identifiers": "Bluetooth SIG Assigned Numbers (company_identifiers.yaml), bitbucket.org/bluetooth-SIG/public",
                       "oui": "IEEE Registration Authority MA-L public listing, standards-oui.ieee.org/oui/oui.csv",
                       "retrieved": a.retrieved,
                       "note": "Identifier->organisation facts from the registries; device types are O Iris's own coarse curation."},
           "company_types": dict(sorted(companies.items())), "camera_ouis": dict(sorted(ouis.items()))}
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(companies)} company ids, {len(ouis)} camera OUIs -> {a.out}")


if __name__ == "__main__":
    main()
