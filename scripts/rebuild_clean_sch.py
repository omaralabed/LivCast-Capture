#!/usr/bin/env python3
"""Rebuild livcast-capture symbols + sparse schematic (KiCad 9/10)."""
from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "kicad"
LIB_PATH = ROOT / "libs/livcast-capture/livcast-capture.kicad_sym"
SCH_PATH = ROOT / "LivCast_Capture.kicad_sch"
BNC_LIB = ROOT / "libs/antmicro-sdi-mipi/sdi-mipi-bridge.kicad_sym"
KICAD = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")

PITCH = 7.62
PIN_LEN = 3.81
STUB = 12.7


def uid() -> str:
    return str(uuid.uuid4())


def y_for(i: int, n: int) -> float:
    if n <= 1:
        return 0.0
    return (n - 1) * PITCH / 2 - i * PITCH


def pin_sexpr(etype: str, name: str, number: str, x: float, y: float, rot: int) -> str:
    return (
        f"      (pin {etype} line (at {x:g} {y:g} {rot}) (length {PIN_LEN})\n"
        f'        (name "{name}" (effects (font (size 1.0 1.0))))\n'
        f'        (number "{number}" (effects (font (size 0.8 0.8))))\n'
        f"      )"
    )


def make_symbol(
    name: str,
    mpn: str,
    left: list[tuple[str, str, str]],
    right: list[tuple[str, str, str]],
    width: float = 38.1,
    ref: str = "U",
) -> tuple[str, dict]:
    nL, nR = len(left), len(right)
    nmax = max(nL, nR, 1)
    h = (nmax - 1) * PITCH + 2 * PITCH
    cx = width / 2
    ytop = h / 2 + 2.54
    ybot = -h / 2 - 2.54
    lines: list[str] = []
    a = lines.append
    a(f'  (symbol "{name}" (in_bom yes) (on_board yes)')
    a("    (pin_names (offset 0.508) hide)")
    a(f'    (property "Reference" "{ref}" (id 0) (at {cx:g} {ytop:g} 0)')
    a("      (effects (font (size 1.27 1.27)))")
    a("    )")
    a(f'    (property "Value" "{name}" (id 1) (at {cx:g} {ybot:g} 0)')
    a("      (effects (font (size 1.27 1.27)))")
    a("    )")
    a(f'    (property "Footprint" "" (id 2) (at {cx:g} {ybot - 2.54:g} 0)')
    a("      (effects (font (size 1.27 1.27)) hide)")
    a("    )")
    a(f'    (property "Datasheet" "" (id 3) (at {cx:g} {ybot - 5.08:g} 0)')
    a("      (effects (font (size 1.27 1.27)) hide)")
    a("    )")
    a(f'    (property "MPN" "{mpn}" (id 4) (at {cx:g} {ybot - 3.81:g} 0)')
    a("      (effects (font (size 1.27 1.27)) hide)")
    a("    )")
    a(f'    (symbol "{name}_0_1"')
    a(f"      (rectangle (start 0 {-h / 2:g}) (end {width:g} {h / 2:g})")
    a("        (stroke (width 0.254) (type default))")
    a("        (fill (type background))")
    a("      )")
    a("    )")
    a(f'    (symbol "{name}_1_1"')
    pins: list[dict] = []
    for i, (etype, pname, pnum) in enumerate(left):
        y = y_for(i, nL)
        x = -PIN_LEN
        a(pin_sexpr(etype, pname, pnum, x, y, 0))
        pins.append({"name": pname, "num": pnum, "x": x, "y": y, "side": "left"})
    for i, (etype, pname, pnum) in enumerate(right):
        y = y_for(i, nR)
        x = width + PIN_LEN
        a(pin_sexpr(etype, pname, pnum, x, y, 180))
        pins.append({"name": pname, "num": pnum, "x": x, "y": y, "side": "right"})
    a("    )")
    a("  )")
    text = "\n".join(lines)
    assert text.count("(") == text.count(")"), name
    return text, {"name": name, "width": width, "height": h, "pins": pins}


def extract_symbol(text: str, name: str) -> str:
    token = f'(symbol "{name}"'
    i = text.find(token)
    if i < 0:
        raise SystemExit(f"missing symbol {name}")
    depth = 0
    for j in range(i, len(text)):
        ch = text[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                chunk = text[i : j + 1]
                assert chunk.count("(") == chunk.count(")"), name
                return chunk
    raise SystemExit(f"unclosed symbol {name}")


def parse_pins_from_upgraded(chunk: str) -> list[dict]:
    pins = []
    # KiCad 10 expanded format
    for m in re.finditer(
        r'\(pin (\w+) line\s*\n\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*\n\s*\(length [-\d.]+\)\s*\n'
        r'\s*\(name "([^"]+)"[\s\S]*?\(number "([^"]+)"',
        chunk,
    ):
        etype, x, y, rot, pname, pnum = m.groups()
        pins.append(
            {
                "etype": etype,
                "x": float(x),
                "y": float(y),
                "rot": int(rot),
                "name": pname,
                "num": pnum,
                "side": "left" if float(x) < 0 else "right",
            }
        )
    if pins:
        return pins
    # compact fallback
    for m in re.finditer(
        r'\(pin (\w+) line \(at ([-\d.]+) ([-\d.]+) (\d+)\) \(length [-\d.]+\)\s+'
        r'\(name "([^"]+)"[^\n]*\n\s+\(number "([^"]+)"',
        chunk,
    ):
        etype, x, y, rot, pname, pnum = m.groups()
        pins.append(
            {
                "etype": etype,
                "x": float(x),
                "y": float(y),
                "rot": int(rot),
                "name": pname,
                "num": pnum,
                "side": "left" if float(x) < 0 else "right",
            }
        )
    return pins


def force_hide_pin_names(chunk: str) -> str:
    """Ensure pin_names hide + per-name hide yes (KiCad 10 expanded)."""
    # pin_names block
    if "(pin_names" in chunk and "(hide yes)" not in chunk.split("(pin_names", 1)[1][:80]:
        chunk = chunk.replace(
            "(pin_names\n\t\t(offset",
            "(pin_names\n\t\t(hide yes)\n\t\t(offset",
            1,
        )
        chunk = chunk.replace("(pin_names hide)", "(pin_names hide)", 1)
    # Ensure (pin_names (hide yes)) style variants already ok
    if re.search(r"\(pin_names\s*\n\s*\(hide yes\)", chunk) is None:
        chunk = re.sub(
            r"\(pin_names(\s*\n\s*\(offset [-\d.]+\))?",
            "(pin_names\n\t\t(hide yes)\\1",
            chunk,
            count=1,
        )
    # Add (hide yes) under each (name ...) if missing
    def hide_name(m: re.Match) -> str:
        block = m.group(0)
        if "(hide yes)" in block:
            return block
        # insert before closing of name
        return block[:-1] + "\n\t\t\t\t\t(hide yes)\n\t\t\t\t)"

    chunk = re.sub(
        r'\(name "[^"]+"\s*\n(?:\t+\([^\n]*\)\s*\n)*?\t+\)',
        hide_name,
        chunk,
    )
    return chunk


def build_compact_lib() -> dict[str, dict]:
    defs: list[tuple] = []

    def add(name, mpn, left, right, width=38.1, ref="U"):
        defs.append((name, mpn, left, right, width, ref))

    add(
        "TMDS_BUF_1TO2",
        "TMDS_BUF_1TO2",
        [
            ("input", "IN_D0_P", "1"),
            ("input", "IN_D0_N", "2"),
            ("input", "IN_D1_P", "3"),
            ("input", "IN_D1_N", "4"),
            ("input", "IN_D2_P", "5"),
            ("input", "IN_D2_N", "6"),
            ("input", "IN_CK_P", "7"),
            ("input", "IN_CK_N", "8"),
            ("input", "OE#", "9"),
            ("power_in", "VDD", "10"),
            ("power_in", "GND", "11"),
        ],
        [
            ("output", "OUTA_D0_P", "12"),
            ("output", "OUTA_D0_N", "13"),
            ("output", "OUTA_D1_P", "14"),
            ("output", "OUTA_D1_N", "15"),
            ("output", "OUTA_D2_P", "16"),
            ("output", "OUTA_D2_N", "17"),
            ("output", "OUTA_CK_P", "18"),
            ("output", "OUTA_CK_N", "19"),
            ("output", "OUTB_D0_P", "20"),
            ("output", "OUTB_D0_N", "21"),
            ("output", "OUTB_D1_P", "22"),
            ("output", "OUTB_D1_N", "23"),
            ("output", "OUTB_D2_P", "24"),
            ("output", "OUTB_D2_N", "25"),
            ("output", "OUTB_CK_P", "26"),
            ("output", "OUTB_CK_N", "27"),
        ],
        45.72,
    )
    add(
        "Conn_HDMI_A",
        "Conn_HDMI_A",
        [
            ("passive", "D0_P", "1"),
            ("passive", "D0_N", "2"),
            ("passive", "D1_P", "3"),
            ("passive", "D1_N", "4"),
            ("passive", "D2_P", "5"),
            ("passive", "D2_N", "6"),
            ("passive", "CK_P", "7"),
            ("passive", "CK_N", "8"),
            ("passive", "DDC_SDA", "9"),
            ("passive", "DDC_SCL", "10"),
            ("passive", "HPD", "11"),
            ("passive", "+5V", "12"),
            ("passive", "GND", "13"),
            ("passive", "SHIELD", "14"),
        ],
        [],
        25.4,
        "J",
    )
    add(
        "IT66021FN",
        "IT66021FN",
        [
            ("input", "RX0_P", "1"),
            ("input", "RX0_N", "2"),
            ("input", "RX1_P", "3"),
            ("input", "RX1_N", "4"),
            ("input", "RX2_P", "5"),
            ("input", "RX2_N", "6"),
            ("input", "RXC_P", "7"),
            ("input", "RXC_N", "8"),
            ("output", "HPD", "9"),
            ("bidirectional", "DDC_SDA", "10"),
            ("bidirectional", "DDC_SCL", "11"),
            ("power_in", "+5V_HDMI", "12"),
            ("input", "RESET#", "13"),
            ("bidirectional", "I2C_SDA", "14"),
            ("bidirectional", "I2C_SCL", "15"),
            ("open_collector", "INT#", "16"),
        ],
        [
            ("output", "VIDEO_BUS", "17"),
            ("output", "PCLK", "18"),
            ("output", "HS", "19"),
            ("output", "VS", "20"),
            ("output", "DE", "21"),
            ("power_in", "VDD33", "22"),
            ("power_in", "VDD18", "23"),
            ("power_in", "VDD12", "24"),
            ("power_in", "GND1", "25"),
            ("power_in", "GND2", "26"),
            ("power_in", "GND3", "27"),
        ],
        45.72,
    )
    add(
        "GS2962A",
        "GS2962A",
        [
            ("input", "VIDEO_BUS", "1"),
            ("input", "PCLK", "2"),
            ("input", "H_HSYNC", "3"),
            ("input", "V_VSYNC", "4"),
            ("input", "F_DE", "5"),
            ("input", "SDO_EN", "6"),
            ("input", "STANDBY#", "7"),
            ("input", "BIT20_10", "8"),
            ("input", "RATE_SEL0", "9"),
            ("input", "RATE_SEL1", "10"),
            ("input", "SMPTE_BYPASS", "11"),
            ("input", "DVB_ASI", "12"),
            ("input", "SDIN", "13"),
            ("output", "SDOUT", "14"),
            ("input", "SCLK", "15"),
            ("input", "CS#", "16"),
        ],
        [
            ("output", "SDO", "17"),
            ("output", "SDO#", "18"),
            ("power_in", "VDD_CORE_1V2", "19"),
            ("power_in", "VDD_IO", "20"),
            ("power_in", "VDD_A_3V3", "21"),
            ("power_in", "VDD_CD", "22"),
            ("power_in", "GND1", "23"),
            ("power_in", "GND2", "24"),
            ("power_in", "GND3", "25"),
            ("power_in", "GND4", "26"),
        ],
        50.8,
    )
    add(
        "TPS25751D",
        "TPS25751D",
        [
            ("passive", "VBUS", "1"),
            ("passive", "CC1", "2"),
            ("passive", "CC2", "3"),
            ("power_in", "GND", "4"),
            ("power_in", "VIN_3V3", "5"),
            ("bidirectional", "I2C_SDA", "6"),
            ("bidirectional", "I2C_SCL", "7"),
        ],
        [
            ("power_out", "PP5V", "8"),
            ("power_out", "PPHV", "9"),
            ("passive", "GPIO1", "10"),
            ("power_in", "GND2", "11"),
        ],
        30.48,
    )
    add(
        "Conn_USB_C_PWR",
        "Conn_USB_C_PWR",
        [
            ("passive", "VBUS", "1"),
            ("passive", "CC1", "2"),
            ("passive", "CC2", "3"),
            ("passive", "GND", "4"),
        ],
        [],
        20.32,
        "J",
    )
    add(
        "Conn_USB_C_DATA",
        "Conn_USB_C_DATA",
        [
            ("passive", "VBUS", "1"),
            ("passive", "USB_DP", "2"),
            ("passive", "USB_DN", "3"),
            ("passive", "CC1", "4"),
            ("passive", "CC2", "5"),
            ("passive", "GND", "6"),
        ],
        [],
        20.32,
        "J",
    )
    add(
        "Conn_DTAP",
        "Conn_DTAP",
        [("passive", "VIN", "1"), ("passive", "GND", "2")],
        [],
        15.24,
        "J",
    )
    add(
        "LM76003",
        "LM76003",
        [
            ("power_in", "VIN", "1"),
            ("input", "EN", "2"),
            ("power_in", "GND", "3"),
            ("input", "FB", "4"),
            ("passive", "SS", "5"),
        ],
        [
            ("passive", "SW", "6"),
            ("power_out", "VOUT", "7"),
            ("open_collector", "PG", "8"),
            ("passive", "BOOT", "9"),
        ],
        30.48,
    )
    add(
        "TPS62130A",
        "TPS62130A",
        [
            ("power_in", "VIN", "1"),
            ("input", "EN", "2"),
            ("power_in", "GND", "3"),
            ("input", "FB", "4"),
            ("passive", "SS", "5"),
        ],
        [
            ("passive", "SW", "6"),
            ("power_out", "VOUT", "7"),
            ("open_collector", "PG", "8"),
            ("passive", "BOOT", "9"),
        ],
        30.48,
    )
    add(
        "CM5_PWR",
        "CM5_PWR",
        [
            ("power_in", "+5V_1", "1"),
            ("power_in", "+5V_2", "2"),
            ("power_in", "+5V_3", "3"),
            ("power_in", "GND_1", "4"),
            ("power_in", "GND_2", "5"),
            ("power_in", "GND_3", "6"),
            ("bidirectional", "USB_DP", "7"),
            ("bidirectional", "USB_DN", "8"),
        ],
        [],
        30.48,
    )
    add(
        "CM5_HDMI",
        "CM5_HDMI",
        [],
        [
            ("output", "HDMI_TX_D0_P", "1"),
            ("output", "HDMI_TX_D0_N", "2"),
            ("output", "HDMI_TX_D1_P", "3"),
            ("output", "HDMI_TX_D1_N", "4"),
            ("output", "HDMI_TX_D2_P", "5"),
            ("output", "HDMI_TX_D2_N", "6"),
            ("output", "HDMI_TX_CK_P", "7"),
            ("output", "HDMI_TX_CK_N", "8"),
        ],
        35.56,
    )
    add(
        "CM5_CSI0",
        "CM5_CSI0",
        [
            ("input", "CSI0_D0_P", "1"),
            ("input", "CSI0_D0_N", "2"),
            ("input", "CSI0_D1_P", "3"),
            ("input", "CSI0_D1_N", "4"),
            ("input", "CSI0_D2_P", "5"),
            ("input", "CSI0_D2_N", "6"),
            ("input", "CSI0_D3_P", "7"),
            ("input", "CSI0_D3_N", "8"),
            ("input", "CSI0_CK_P", "9"),
            ("input", "CSI0_CK_N", "10"),
        ],
        [],
        30.48,
    )
    add(
        "CM5_CSI1",
        "CM5_CSI1",
        [
            ("input", "CSI1_D0_P", "1"),
            ("input", "CSI1_D0_N", "2"),
            ("input", "CSI1_D1_P", "3"),
            ("input", "CSI1_D1_N", "4"),
            ("input", "CSI1_D2_P", "5"),
            ("input", "CSI1_D2_N", "6"),
            ("input", "CSI1_D3_P", "7"),
            ("input", "CSI1_D3_N", "8"),
            ("input", "CSI1_CK_P", "9"),
            ("input", "CSI1_CK_N", "10"),
        ],
        [],
        30.48,
    )
    add(
        "CM5_CTRL",
        "CM5_CTRL",
        [
            ("bidirectional", "I2C_SDA", "1"),
            ("bidirectional", "I2C_SCL", "2"),
            ("output", "SPI_MOSI", "3"),
            ("input", "SPI_MISO", "4"),
            ("output", "SPI_SCK", "5"),
            ("output", "SPI_CS", "6"),
            ("output", "SDI_TX_SPI_MOSI", "7"),
            ("output", "SDI_TX_SPI_SCK", "8"),
            ("output", "SDI_TX_SPI_CS", "9"),
        ],
        [],
        35.56,
    )

    parts = []
    metas = {}
    for name, mpn, left, right, width, ref in defs:
        txt, meta = make_symbol(name, mpn, left, right, width, ref)
        parts.append(txt)
        metas[name] = meta
    lib = (
        "(kicad_symbol_lib\n  (version 20211014)\n  (generator \"livcast_rebuild\")\n"
        + "\n".join(parts)
        + "\n)\n"
    )
    LIB_PATH.write_text(lib)
    print(f"Wrote compact lib {LIB_PATH} ({LIB_PATH.stat().st_size} bytes)")
    return metas


def upgrade_lib() -> str:
    out = LIB_PATH.with_suffix(".upgraded.kicad_sym")
    r = subprocess.run(
        [str(KICAD), "sym", "upgrade", "--force", "-o", str(out), str(LIB_PATH)],
        capture_output=True,
        text=True,
    )
    print(r.stdout, r.stderr, "exit", r.returncode)
    if r.returncode != 0 or not out.exists():
        raise SystemExit("symbol upgrade failed")
    # Replace lib with upgraded
    LIB_PATH.write_text(out.read_text())
    out.unlink(missing_ok=True)
    print(f"Upgraded lib in place ({LIB_PATH.stat().st_size} bytes)")
    return LIB_PATH.read_text()



def main() -> None:
    metas_geom = build_compact_lib()
    lib_text = upgrade_lib()

    names = list(metas_geom.keys())
    embeds = []
    metas = {}
    for name in names:
        chunk = extract_symbol(lib_text, name)
        chunk = force_hide_pin_names(chunk)
        # Prefer geometry from compact builder (authoritative pitch/positions)
        pins = metas_geom[name]["pins"]
        w = metas_geom[name]["width"]
        h = metas_geom[name]["height"]
        embed = chunk.replace(f'(symbol "{name}"', f'(symbol "livcast-capture:{name}"', 1)
        assert embed.count("(") == embed.count(")"), name
        embeds.append(embed)
        metas[name] = {"name": name, "width": w, "height": h, "pins": pins, "chunk": embed}
        print(f"  {name}: {len(pins)} pins H={h:g}")

    # BNC
    bnc_raw = extract_symbol(BNC_LIB.read_text(), "Conn_BNC_031-70526-21")
    bnc_tmp = ROOT / "_bnc_tmp.kicad_sym"
    bnc_up = ROOT / "_bnc_up.kicad_sym"
    bnc_tmp.write_text(
        "(kicad_symbol_lib\n  (version 20211014)\n  (generator x)\n" + bnc_raw + "\n)\n"
    )
    subprocess.run(
        [str(KICAD), "sym", "upgrade", "--force", "-o", str(bnc_up), str(bnc_tmp)],
        check=True,
        capture_output=True,
    )
    bnc_chunk = extract_symbol(bnc_up.read_text(), "Conn_BNC_031-70526-21")
    bnc_pins = parse_pins_from_upgraded(bnc_chunk)
    if not bnc_pins:
        # fallback known geometry
        bnc_pins = [
            {"name": "In", "num": "1", "x": 0.0, "y": 0.0, "side": "left"},
            {"name": "GND", "num": "2", "x": 5.08, "y": -5.08, "side": "right"},
        ]
    bnc_embed = bnc_chunk.replace(
        '(symbol "Conn_BNC_031-70526-21"',
        '(symbol "sdi-mipi-bridge:Conn_BNC_031-70526-21"',
        1,
    )
    embeds.append(bnc_embed)
    bnc_tmp.unlink(missing_ok=True)
    bnc_up.unlink(missing_ok=True)
    print(f"  BNC: {len(bnc_pins)} pins")

    # Rewrite lib with hidden names (no duplicates)
    lib_out = (
        "(kicad_symbol_lib\n\t(version 20251024)\n\t(generator \"livcast_rebuild\")\n"
        "\t(generator_version \"10.0\")\n"
    )
    for name in names:
        c = metas[name]["chunk"].replace(
            f'(symbol "livcast-capture:{name}"', f'(symbol "{name}"', 1
        )
        lib_out += c + "\n"
    lib_out += ")\n"
    assert lib_out.count("(") == lib_out.count(")")
    LIB_PATH.write_text(lib_out)
    print(f"Rewrote lib with hides ({LIB_PATH.stat().st_size} bytes)")

    # ---- schematic ----
    wires: list[str] = []
    labels: list[str] = []
    texts: list[str] = []
    instances: list[str] = []

    def emit_wire(x1, y1, x2, y2):
        wires.append(
            f"\t(wire\n\t\t(pts\n\t\t\t(xy {x1:g} {y1:g}) (xy {x2:g} {y2:g})\n\t\t)\n"
            f"\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f'\t\t(uuid "{uid()}")\n\t)'
        )

    def emit_glabel(name, x, y, rot=0, justify="left"):
        labels.append(
            f'\t(global_label "{name}"\n'
            f"\t\t(shape bidirectional)\n"
            f"\t\t(at {x:g} {y:g} {rot})\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {justify})\n\t\t)\n"
            f'\t\t(uuid "{uid()}")\n'
            f'\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}"\n'
            f"\t\t\t(at {x:g} {y:g} 0)\n"
            f"\t\t\t(hide yes)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n"
            f"\t\t)\n\t)"
        )

    def emit_label(name, x, y):
        labels.append(
            f'\t(label "{name}"\n'
            f"\t\t(at {x:g} {y:g} 0)\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify left)\n\t\t)\n"
            f'\t\t(uuid "{uid()}")\n\t)'
        )

    def emit_text(msg, x, y, size=1.27):
        texts.append(
            f'\t(text "{msg}"\n'
            f"\t\t(exclude_from_sim no)\n"
            f"\t\t(at {x:g} {y:g} 0)\n"
            f"\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n\t\t\t)\n"
            f"\t\t\t(justify left bottom)\n\t\t)\n"
            f'\t\t(uuid "{uid()}")\n\t)'
        )

    def place(lib_id, ref, value, at_x, at_y, meta):
        pins_block = "\n".join(
            f'\t\t(pin "{p["num"]}"\n\t\t\t(uuid "{uid()}")\n\t\t)' for p in meta["pins"]
        )
        hy = meta["height"] / 2
        instances.append(
            f"\t(symbol\n"
            f'\t\t(lib_id "{lib_id}")\n'
            f"\t\t(at {at_x:g} {at_y:g} 0)\n"
            f"\t\t(unit 1)\n"
            f"\t\t(exclude_from_sim no)\n"
            f"\t\t(in_bom yes)\n"
            f"\t\t(on_board yes)\n"
            f"\t\t(dnp no)\n"
            f'\t\t(uuid "{uid()}")\n'
            f'\t\t(property "Reference" "{ref}"\n'
            f"\t\t\t(at {at_x:g} {at_y - hy - 2.54:g} 0)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
            f'\t\t(property "Value" "{value}"\n'
            f"\t\t\t(at {at_x:g} {at_y - hy:g} 0)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
            f'\t\t(property "Footprint" ""\n'
            f"\t\t\t(at {at_x:g} {at_y:g} 0)\n\t\t\t(hide yes)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
            f'\t\t(property "Datasheet" ""\n'
            f"\t\t\t(at {at_x:g} {at_y:g} 0)\n\t\t\t(hide yes)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
            f'\t\t(property "Description" ""\n'
            f"\t\t\t(at {at_x:g} {at_y:g} 0)\n\t\t\t(hide yes)\n"
            f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
            f"{pins_block}\n\t)"
        )
        return {
            p["name"]: {
                "x": at_x + p["x"],
                "y": at_y + p["y"],
                "side": p["side"],
                "num": p["num"],
            }
            for p in meta["pins"]
        }

    def stub(pin, net):
        x, y, side = pin["x"], pin["y"], pin["side"]
        if side == "left":
            x2 = x - STUB
            emit_wire(x, y, x2, y)
            emit_glabel(net, x2, y, rot=180, justify="right")
        else:
            x2 = x + STUB
            emit_wire(x, y, x2, y)
            emit_glabel(net, x2, y, rot=0, justify="left")

    def connect(p1, p2, mid=None):
        x1, y1 = p1["x"], p1["y"]
        x2, y2 = p2["x"], p2["y"]
        if abs(y1 - y2) < 0.01:
            emit_wire(x1, y1, x2, y2)
            if mid:
                emit_label(mid, (x1 + x2) / 2, y1)
        else:
            xm = (x1 + x2) / 2
            emit_wire(x1, y1, xm, y1)
            emit_wire(xm, y1, xm, y2)
            emit_wire(xm, y2, x2, y2)
            if mid:
                emit_label(mid, xm, (y1 + y2) / 2)

    emit_text(
        "LivCast Capture Rev A — sparse symbols, pin names hidden, VIDEO_BUS simplified",
        20,
        15,
        2.0,
    )
    emit_text(
        "SDI playback: CM5_HDMI -> TMDS 1:2 -> HDMI mon + IT66021FN -> VIDEO_BUS -> GS2962A -> BNC",
        20,
        22,
    )
    emit_text(
        "VIDEO_BUS = 20-bit parallel PDATA/DIN — expand as bus on PCB (not drawn pin-by-pin)",
        20,
        28,
    )
    emit_text("Power column left. Labels on wire stubs only. CM5 split: U201-U205.", 20, 34)

    j101 = place("livcast-capture:Conn_DTAP", "J101", "Conn_DTAP", 50, 90, metas["Conn_DTAP"])
    stub(j101["VIN"], "VIN_RAW")
    stub(j101["GND"], "GND")

    j102 = place(
        "livcast-capture:Conn_USB_C_PWR", "J102", "Conn_USB_C_PWR", 50, 170, metas["Conn_USB_C_PWR"]
    )
    for n, net in [("VBUS", "VBUS"), ("CC1", "CC1_PWR"), ("CC2", "CC2_PWR"), ("GND", "GND")]:
        stub(j102[n], net)

    u101 = place("livcast-capture:TPS25751D", "U101", "TPS25751D", 50, 280, metas["TPS25751D"])
    for n, net in [
        ("VBUS", "VBUS"),
        ("CC1", "CC1_PWR"),
        ("CC2", "CC2_PWR"),
        ("GND", "GND"),
        ("VIN_3V3", "+3V3"),
        ("I2C_SDA", "I2C_SDA"),
        ("I2C_SCL", "I2C_SCL"),
        ("PP5V", "PP5V"),
        ("PPHV", "PPHV"),
        ("GPIO1", "PD_GPIO1"),
        ("GND2", "GND"),
    ]:
        stub(u101[n], net)

    u102 = place("livcast-capture:LM76003", "U102", "LM76003", 50, 400, metas["LM76003"])
    for n, net in [
        ("VIN", "VIN_RAW"),
        ("EN", "BUCK_EN"),
        ("GND", "GND"),
        ("FB", "FB_5V"),
        ("SS", "SS_5V"),
        ("SW", "SW_5V"),
        ("VOUT", "+5V"),
        ("PG", "PG_5V"),
        ("BOOT", "BOOT_5V"),
    ]:
        stub(u102[n], net)

    u103 = place("livcast-capture:TPS62130A", "U103", "TPS62130A", 50, 520, metas["TPS62130A"])
    for n, net in [
        ("VIN", "+5V"),
        ("EN", "BUCK33_EN"),
        ("GND", "GND"),
        ("FB", "FB_3V3"),
        ("SS", "SS_3V3"),
        ("SW", "SW_3V3"),
        ("VOUT", "+3V3"),
        ("PG", "PG_3V3"),
        ("BOOT", "BOOT_3V3"),
    ]:
        stub(u103[n], net)

    j103 = place(
        "livcast-capture:Conn_USB_C_DATA",
        "J103",
        "Conn_USB_C_DATA",
        50,
        640,
        metas["Conn_USB_C_DATA"],
    )
    for n, net in [
        ("VBUS", "VBUS"),
        ("USB_DP", "USB_DP"),
        ("USB_DN", "USB_DN"),
        ("CC1", "CC1_DATA"),
        ("CC2", "CC2_DATA"),
        ("GND", "GND"),
    ]:
        stub(j103[n], net)

    u201 = place("livcast-capture:CM5_PWR", "U201", "CM5_PWR", 220, 120, metas["CM5_PWR"])
    for n, net in [
        ("+5V_1", "+5V"),
        ("+5V_2", "+5V"),
        ("+5V_3", "+5V"),
        ("GND_1", "GND"),
        ("GND_2", "GND"),
        ("GND_3", "GND"),
        ("USB_DP", "USB_DP"),
        ("USB_DN", "USB_DN"),
    ]:
        stub(u201[n], net)

    u202 = place("livcast-capture:CM5_HDMI", "U202", "CM5_HDMI", 220, 260, metas["CM5_HDMI"])
    for n in [
        "HDMI_TX_D0_P",
        "HDMI_TX_D0_N",
        "HDMI_TX_D1_P",
        "HDMI_TX_D1_N",
        "HDMI_TX_D2_P",
        "HDMI_TX_D2_N",
        "HDMI_TX_CK_P",
        "HDMI_TX_CK_N",
    ]:
        stub(u202[n], n)

    u203 = place("livcast-capture:CM5_CSI0", "U203", "CM5_CSI0", 220, 420, metas["CM5_CSI0"])
    for p in metas["CM5_CSI0"]["pins"]:
        stub(u203[p["name"]], p["name"])

    u204 = place("livcast-capture:CM5_CSI1", "U204", "CM5_CSI1", 220, 560, metas["CM5_CSI1"])
    for p in metas["CM5_CSI1"]["pins"]:
        stub(u204[p["name"]], p["name"])

    u205 = place("livcast-capture:CM5_CTRL", "U205", "CM5_CTRL", 220, 700, metas["CM5_CTRL"])
    for p in metas["CM5_CTRL"]["pins"]:
        stub(u205[p["name"]], p["name"])

    u301 = place(
        "livcast-capture:TMDS_BUF_1TO2", "U301", "TMDS_BUF_1TO2", 420, 260, metas["TMDS_BUF_1TO2"]
    )
    for pn, net in [
        ("IN_D0_P", "HDMI_TX_D0_P"),
        ("IN_D0_N", "HDMI_TX_D0_N"),
        ("IN_D1_P", "HDMI_TX_D1_P"),
        ("IN_D1_N", "HDMI_TX_D1_N"),
        ("IN_D2_P", "HDMI_TX_D2_P"),
        ("IN_D2_N", "HDMI_TX_D2_N"),
        ("IN_CK_P", "HDMI_TX_CK_P"),
        ("IN_CK_N", "HDMI_TX_CK_N"),
        ("OE#", "TMDS_OE#"),
        ("VDD", "+3V3"),
        ("GND", "GND"),
    ]:
        stub(u301[pn], net)
    outa = [
        "OUTA_D0_P",
        "OUTA_D0_N",
        "OUTA_D1_P",
        "OUTA_D1_N",
        "OUTA_D2_P",
        "OUTA_D2_N",
        "OUTA_CK_P",
        "OUTA_CK_N",
    ]
    outb = [
        "OUTB_D0_P",
        "OUTB_D0_N",
        "OUTB_D1_P",
        "OUTB_D1_N",
        "OUTB_D2_P",
        "OUTB_D2_N",
        "OUTB_CK_P",
        "OUTB_CK_N",
    ]
    mon = [
        "HDMI_MON_D0_P",
        "HDMI_MON_D0_N",
        "HDMI_MON_D1_P",
        "HDMI_MON_D1_N",
        "HDMI_MON_D2_P",
        "HDMI_MON_D2_N",
        "HDMI_MON_CK_P",
        "HDMI_MON_CK_N",
    ]
    rx = [
        "HDMI_RX_D0_P",
        "HDMI_RX_D0_N",
        "HDMI_RX_D1_P",
        "HDMI_RX_D1_N",
        "HDMI_RX_D2_P",
        "HDMI_RX_D2_N",
        "HDMI_RX_CK_P",
        "HDMI_RX_CK_N",
    ]
    for pn, net in zip(outa, mon):
        stub(u301[pn], net)
    for pn, net in zip(outb, rx):
        stub(u301[pn], net)

    j201 = place("livcast-capture:Conn_HDMI_A", "J201", "Conn_HDMI_A", 620, 120, metas["Conn_HDMI_A"])
    for pn, net in [
        ("D0_P", "HDMI_MON_D0_P"),
        ("D0_N", "HDMI_MON_D0_N"),
        ("D1_P", "HDMI_MON_D1_P"),
        ("D1_N", "HDMI_MON_D1_N"),
        ("D2_P", "HDMI_MON_D2_P"),
        ("D2_N", "HDMI_MON_D2_N"),
        ("CK_P", "HDMI_MON_CK_P"),
        ("CK_N", "HDMI_MON_CK_N"),
        ("DDC_SDA", "HDMI_MON_DDC_SDA"),
        ("DDC_SCL", "HDMI_MON_DDC_SCL"),
        ("HPD", "HDMI_MON_HPD"),
        ("+5V", "+5V_HDMI"),
        ("GND", "GND"),
        ("SHIELD", "GND"),
    ]:
        stub(j201[pn], net)

    u401 = place("livcast-capture:IT66021FN", "U401", "IT66021FN", 620, 360, metas["IT66021FN"])
    for pn, net in [
        ("RX0_P", "HDMI_RX_D0_P"),
        ("RX0_N", "HDMI_RX_D0_N"),
        ("RX1_P", "HDMI_RX_D1_P"),
        ("RX1_N", "HDMI_RX_D1_N"),
        ("RX2_P", "HDMI_RX_D2_P"),
        ("RX2_N", "HDMI_RX_D2_N"),
        ("RXC_P", "HDMI_RX_CK_P"),
        ("RXC_N", "HDMI_RX_CK_N"),
        ("HPD", "HDMI_RX_HPD"),
        ("DDC_SDA", "HDMI_RX_DDC_SDA"),
        ("DDC_SCL", "HDMI_RX_DDC_SCL"),
        ("+5V_HDMI", "+5V_HDMI"),
        ("RESET#", "IT66021_RESET#"),
        ("I2C_SDA", "I2C_SDA"),
        ("I2C_SCL", "I2C_SCL"),
        ("INT#", "IT66021_INT#"),
    ]:
        stub(u401[pn], net)

    u501 = place("livcast-capture:GS2962A", "U501", "GS2962A", 820, 360, metas["GS2962A"])
    connect(u401["VIDEO_BUS"], u501["VIDEO_BUS"], "VIDEO_BUS")
    connect(u401["PCLK"], u501["PCLK"], "PCLK")
    connect(u401["HS"], u501["H_HSYNC"], "HS")
    connect(u401["VS"], u501["V_VSYNC"], "VS")
    connect(u401["DE"], u501["F_DE"], "DE")

    for pn, net in [
        ("VDD33", "+3V3"),
        ("VDD18", "+1V8"),
        ("VDD12", "+1V2"),
        ("GND1", "GND"),
        ("GND2", "GND"),
        ("GND3", "GND"),
    ]:
        stub(u401[pn], net)

    for pn, net in [
        ("SDO_EN", "SDO_EN"),
        ("STANDBY#", "GS_STANDBY#"),
        ("BIT20_10", "BIT20_10"),
        ("RATE_SEL0", "RATE_SEL0"),
        ("RATE_SEL1", "RATE_SEL1"),
        ("SMPTE_BYPASS", "SMPTE_BYPASS"),
        ("DVB_ASI", "DVB_ASI"),
        ("SDIN", "SDI_TX_SPI_MOSI"),
        ("SDOUT", "GS_SDOUT"),
        ("SCLK", "SDI_TX_SPI_SCK"),
        ("CS#", "SDI_TX_SPI_CS"),
        ("SDO", "SDI_TX_P"),
        ("SDO#", "SDI_TX_N"),
        ("VDD_CORE_1V2", "+1V2"),
        ("VDD_IO", "+3V3"),
        ("VDD_A_3V3", "+3V3"),
        ("VDD_CD", "+1V2"),
        ("GND1", "GND"),
        ("GND2", "GND"),
        ("GND3", "GND"),
        ("GND4", "GND"),
    ]:
        stub(u501[pn], net)

    # BNC
    bnc_meta = {"height": 10.0, "pins": bnc_pins}
    bnc_at = (1020.0, 360.0)
    pins_block = "\n".join(
        f'\t\t(pin "{p["num"]}"\n\t\t\t(uuid "{uid()}")\n\t\t)' for p in bnc_pins
    )
    instances.append(
        f"\t(symbol\n"
        f'\t\t(lib_id "sdi-mipi-bridge:Conn_BNC_031-70526-21")\n'
        f"\t\t(at {bnc_at[0]:g} {bnc_at[1]:g} 0)\n"
        f"\t\t(unit 1)\n"
        f"\t\t(exclude_from_sim no)\n"
        f"\t\t(in_bom yes)\n"
        f"\t\t(on_board yes)\n"
        f"\t\t(dnp no)\n"
        f'\t\t(uuid "{uid()}")\n'
        f'\t\t(property "Reference" "J501"\n'
        f"\t\t\t(at {bnc_at[0]:g} {bnc_at[1] - 8:g} 0)\n"
        f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
        f'\t\t(property "Value" "Conn_BNC_031-70526-21"\n'
        f"\t\t\t(at {bnc_at[0]:g} {bnc_at[1] - 5:g} 0)\n"
        f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
        f'\t\t(property "Footprint" "sdi-mipi-bridge-footprints:Conn_BNC_031-70526-21"\n'
        f"\t\t\t(at {bnc_at[0]:g} {bnc_at[1]:g} 0)\n\t\t\t(hide yes)\n"
        f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
        f'\t\t(property "Datasheet" ""\n'
        f"\t\t\t(at {bnc_at[0]:g} {bnc_at[1]:g} 0)\n\t\t\t(hide yes)\n"
        f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
        f'\t\t(property "Description" ""\n'
        f"\t\t\t(at {bnc_at[0]:g} {bnc_at[1]:g} 0)\n\t\t\t(hide yes)\n"
        f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n"
        f"{pins_block}\n\t)"
    )
    for p in bnc_pins:
        ax, ay = bnc_at[0] + p["x"], bnc_at[1] + p["y"]
        if p["num"] == "1":
            emit_wire(ax, ay, ax - STUB, ay)
            emit_glabel("SDI_TX_P", ax - STUB, ay, rot=180, justify="right")
        else:
            emit_wire(ax, ay, ax, ay - STUB)
            emit_glabel("GND", ax, ay - STUB, rot=270, justify="right")

    emit_text("HDMI IN ingest - TBD (archive_sheets/03)", 40, 800)
    emit_text("SDI IN ingest - TBD (archive_sheets/04, Antmicro)", 40, 808)

    parts = [
        "(kicad_sch",
        "\t(version 20250114)",
        '\t(generator "livcast_rebuild")',
        '\t(generator_version "9.0")',
        f'\t(uuid "{uid()}")',
        '\t(paper "A0")',
        "\t(title_block",
        '\t\t(title "LivCast Capture - Complete")',
        '\t\t(date "2026-07-25")',
        '\t\t(rev "A")',
        '\t\t(company "LivCast")',
        '\t\t(comment 1 "Pin names hidden; CM5 split U201-U205; VIDEO_BUS single wire")',
        '\t\t(comment 2 "SDI playback: CM5->TMDS->HDMI+IT66021->VIDEO_BUS->GS2962->BNC")',
        "\t)",
        "\t(lib_symbols",
    ]
    for e in embeds:
        assert e.count("(") == e.count(")")
        parts.append(e)
    parts.append("\t)")
    parts.extend(texts)
    parts.extend(instances)
    parts.extend(wires)
    parts.extend(labels)
    parts += [
        "\t(sheet_instances",
        '\t\t(path "/"',
        '\t\t\t(page "1")',
        "\t\t)",
        "\t)",
        "\t(embedded_fonts no)",
        ")",
    ]
    text = "\n".join(parts) + "\n"
    print("parens", text.count("("), text.count(")"))
    assert text.count("(") == text.count(")")
    SCH_PATH.write_text(text)
    print(f"Wrote {SCH_PATH} ({SCH_PATH.stat().st_size} bytes)")
    print(f"instances={len(instances)} wires={len(wires)} labels={len(labels)}")


if __name__ == "__main__":
    main()
