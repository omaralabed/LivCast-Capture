# LivCast Capture — Chip Shortlist (Rev A)

Status: **Rev A picks locked** (2026-07-25).  
Priority: **guaranteed** 720p / **1080i** / 1080p on **both** HDMI and SDI (best quality, dual CSI).

Reference designs:
- **Antmicro SDI→MIPI CSI bridge** (golden SDI path): [openhardware portal](https://openhardware.antmicro.com/boards/sdi-mipi-bridge/) · [GitHub](https://github.com/antmicro/sdi-mipi-bridge-hw) · local copy [`refs/antmicro-sdi-mipi-bridge/`](../refs/antmicro-sdi-mipi-bridge/) (KiCad + `doc/sdi-mipi-bridge.pdf`, Apache-2.0)
- **Sheet 04** (`kicad/04_SDI_CSI.kicad_sch`): Antmicro-based **GS2971A + CrossLink** for **SDI ingest → CSI1** only. Antmicro **J2/GS2988 input-loop is NOT product SDI out**.
- **SDI playback out (required):** **GS2962A** (+ cable drive) — see signal map; sheet `07_SDI_OUT`
- ITE **IT6616** HDMI→CSI (datasheet: **interlaced mode in CSI**)
- Prior Livcast adapter BOM for Semtech SDI + TI power (UVC path rejected)

**Rejected for production:** Toshiba **TC358743** — Pi-common, but **not** accepted here for solid 1080i.

---

## Rev A primary picks

| Block | MPN | Mfr | Role |
|-------|-----|-----|------|
| SoC | **CM5** (eMMC) | Raspberry Pi | Capture, encode, USB gadget, SPI UI, HDMI TX |
| HDMI → CSI | **IT6616** | ITE | HDMI 1.4 → MIPI CSI-2 (CAM0); **CSI interlaced mode supported** |
| SDI RX | **GS2971A** | Semtech | 3G-SDI EQ + deserialize + reclock (10-bit 4:2:2 parallel) |
| SDI → CSI | **LIF-MD6000-6JMG80I** | Lattice CrossLink | Parallel → MIPI CSI-2 (CAM1); **copy Antmicro sch** |
| SDI out (ser) | **GS2962A** | Semtech | **Required** — 3G-SDI serializer for **playback** out (not input loop) |
| SDI cable driver | **GS2989** (or GS2962A integrated CD) | Semtech | Drive SDI out BNC if not using GS2962A integrated driver |
| HDMI tap for SDI out | **IT66021FN** (or equiv. HDMI RX) | ITE | Parallel from **CM5 HDMI TX** mirror → GS2962A |
| USB-C PD (power in) | **TPS25751D** | TI | PD **sink** ≥60 W → system VIN |
| USB-C PD (phone) | **TPS25751S/D** | TI | PD **source** + data **UFP** (gadget); charge iPhone |
| VIN buck | **LM76003** (or TPS54560) | TI | D-Tap / PD VIN → **5 V / ≥5 A** |
| 3V3 buck | **TPS62130A** | TI | 5 V → 3V3 |
| Bridge rails | per DS | TI LDOs/bucks | GS2971A / CrossLink / IT6616 |
| eFuse (phone VBUS) | **TPS25947** | TI | Phone charge path |
| Display | Hosyond **3.5" 480×320 SPI** | — | 40-pin GPIO |

### Alternates (supply only — same format contract)

| Block | Alternate | Notes |
|-------|-----------|--------|
| HDMI → CSI | **IT6625** | HDMI 2.0; also **CSI interlaced mode** in ITE docs |
| HDMI → CSI (symmetric) | **IT66021FN** → parallel → CrossLink | Same CSI bridge style as SDI; use if IT6616 NDA/availability blocks |
| SDI → CSI | CrossLink-NX **LIFCL-40** | More headroom |
| SDI RX | GS2961A + external EQ | If GS2971A unavailable |
| PD | TPS25750 | Fallback |

---

## Signal map (locked)

```
HDMI in ──► IT6616 ──────────────────► CSI0 ──► CM5 ──┬── USB-C data+charge ──► iPhone
SDI in  ──► GS2971A ──► CrossLink ──► CSI1 ──► CM5 ──┤
                                                     ├── HDMI TX ──┬──► HDMI out (monitor)
                                                     │             └──► IT66021FN ──► GS2962A ──► SDI out (playback)
                                                     └── SPI ──► 3.5" preview

Power: D-Tap and/or USB-C PD in ──► 5V0
```

Software selects **CSI0 or CSI1** (one live input).

**SDI out = playback** (same program as HDMI out from CM5), **not** a reclocked loop of SDI in.  
Antmicro J2/GS2988 loop may stay on sheet 04 for debug only — **do not ship as the product SDI out.**

---

## Format support (locked requirement)

| Format | HDMI (**IT6616**) | SDI (GS2971A + CrossLink) |
|--------|-------------------|---------------------------|
| 720p | Required / supported | Required / SMPTE |
| 1080p | Required / supported | Required / 3G-SDI |
| 1080i | Required — **IT6616 CSI interlaced mode** | Required / SMPTE; iOS deinterlaces |

No “bench risk” language on the primary HDMI part — format set is a **hard product requirement**. Bring-up still verifies firmware/EDID, but silicon choice is made for interlaced CSI.

---

## Why not TC358743

Common on Pi HATs; weak / non-guaranteed 1080i story for production. **Do not use** on LivCast Capture Rev A.

---

## Power parts detail

| Rail | Source | Target |
|------|--------|--------|
| VIN | D-Tap (~12–17 V) and/or USB-C PD sink (9–20 V) | OR’d into buck |
| 5V0 | LM76003 | CM5 + loads; ≥5 A |
| Phone VBUS | TPS25751 + eFuse | Charge iPhone |
| 3V3 / 1V8 / 1V2 / … | From 5V0 | Per video IC DS |

No internal battery. Operator owns camera-battery runtime.

---

## Connectors

| Ref | Part | Function |
|-----|------|----------|
| J_HDMI_IN | HDMI Type-A | Camera HDMI |
| J_HDMI_OUT | HDMI Type-A / Micro | Monitor |
| J_SDI_IN | HD-BNC 75 Ω | Camera SDI |
| J_SDI_OUT | HD-BNC 75 Ω | SDI deck |
| J_USBC_PWR | USB-C | PD power in |
| J_USBC_PHONE | USB-C | Data + PD charge out |
| J_DTAP | D-Tap | Camera battery in |
| J_LCD | 40-pin | Hosyond SPI |
| U_CM5 | CM5 | Compute Module 5 |

ESD: HDMI/USB TPD4E05U06-class; SDI per Semtech; D-Tap fuse + reverse protection.

---

## PCB notes

- Semtech 75 Ω SDI layout; GS2989 placement  
- MIPI length match CSI0/CSI1 → CM5  
- USB-C: PD + gadget data; USB2 minimum for ECM  
- Thermal: CM5 + GS2971A + CrossLink + IT6616  
- Suggest **6-layer**

---

## Bring-up (verification, not part-selection)

1. IT6616: 720p / 1080i / 1080p HDMI → CSI0  
2. GS2971A+CrossLink: same on SDI → CSI1  
3. TPS25751: phone charge + USB gadget  
4. LM76003: D-Tap / PD under box + phone charge load  
