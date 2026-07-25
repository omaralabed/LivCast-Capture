# Antmicro SDI–MIPI Bridge — vendor reference

LivCast Capture overlay note (not part of Antmicro’s tree). Upstream clone lives in `sdi-mipi-bridge-hw/`.

## Links

- Product / board page: https://openhardware.antmicro.com/boards/sdi-mipi-bridge/
- Hardware repo: https://github.com/antmicro/sdi-mipi-bridge-hw
- License: **Apache-2.0** (see `sdi-mipi-bridge-hw/LICENSE`)

## Portal schematic PDF

Download from the openhardware “Schematic PDF” button often saves as **`undefined.pdf`** on Desktop (portal filename bug).

- Your file: `/Users/viewvision/Desktop/undefined.pdf`
- Title block: **SDI-MIPI Bridge**, Rev **1.3.4**, KiCad **9.0.7**, date **2023-10-12**, Antmicro Ltd.
- Same design as the git clone schematic; use either this PDF or `sdi-mipi-bridge-hw/*.kicad_sch`

Suggested rename:
`mv ~/Desktop/undefined.pdf ~/Desktop/SDI-MIPI-Bridge_schematic.pdf`

## LivCast Capture use

Used as **reference** for LivCast Capture sheet **04** (Semtech **GS2971A** + Lattice CrossLink **LIF-MD6000**).

We integrate this signal path onto the **CM5 carrier**, not as a standalone Antmicro daughterboard unless used for proto bring-up.

## Key files in clone

| Path | Notes |
|------|--------|
| `sdi-mipi-bridge-hw/sdi-mipi-bridge.kicad_sch` | Single-sheet schematic (title: SDI-MIPI Bridge) |
| `sdi-mipi-bridge-hw/sdi-mipi-bridge.kicad_pcb` | PCB |
| `sdi-mipi-bridge-hw/doc/sdi-mipi-bridge.pdf` | Schematic PDF in repo |
| `sdi-mipi-bridge-hw/lib/` | Symbols, footprints, 3D models |

## Key ICs (from schematic MPN)

- **U2** — Semtech **GS2971A** (SDI deserializer)
- **U4** — Lattice CrossLink **LIF-MD6000-6JMG80I**
