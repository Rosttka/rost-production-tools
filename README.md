# Rost Production Tools 4.2

Blender 5.2 add-on: STEP pipeline, CAD Auto-Rig, Rost Light Rig, HUD graphics (Callout, Measure, Section, Volume Cut, Style, FUI), Proximity Alpha, Gradient Mask, scene utilities. All panels live in the N-panel tab **Rost Tools**.

## Installation

1. Download `rost_production_tools_4.2.0.zip` (it contains the `rost_production_tools` folder with the add-on and all its libraries).
2. Blender → Edit → Preferences → Add-ons → ⌄ (top right) → **Install from Disk…** → pick the zip.
3. Enable **Rost Production Tools** in the list.

The add-on is a package: `rost_production_tools/__init__.py` plus `rost_production_tools/library/` (HUD libraries, node groups, Proximity Alpha and Gradient Mask assets, Callout presets). Nothing outside that folder is needed for the HUD, Proximity Alpha, Gradient Mask and CAD Auto-Rig tools. Paths in the add-on preferences (**HUD Library**, **STEP Pipeline folder**) are only overrides.

STEP Pipeline also needs the CADder add-on and the pipeline scripts (`STEP Pipeline folder` in preferences).

## Source layout

```
rost_production_tools/        add-on package (zip this folder)
  __init__.py
  library/
    HUD/                      HUD_Elements, HUD_FUI, HUD_Section, HUD_Style, HUD_VolumeCut, Callout_Presets/
    PT_NodeGroups_and_Mats.blend
    fx_data.blend
    GN_Proximity_Mask.blend
docs/                         guide (GitHub Pages)
```

## Guide

Step-by-step guide with screenshots (Ukrainian): https://rosttka.github.io/rost-production-tools/guide.html

The **?** button in the Production Tools header opens the same page.
