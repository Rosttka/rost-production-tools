# Rost Render Passes (вбудовано в Rost Production Tools 4.3) - render selected view layers one after another,
# each with its own DoF switch and output path + render quality presets.

import bpy
import os
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, StringProperty, IntProperty, EnumProperty,
                       CollectionProperty, PointerProperty)

DEFAULT_PATH = "//renders/{scene}/{layer}/{layer}_"

# max, diffuse, glossy, transmission, volume, transparent
QUALITY = {
    "WORKBENCH": {"label": "Workbench", "engine": "BLENDER_WORKBENCH", "pct": 100},
    "LIGHT": {"label": "Light", "engine": "CYCLES", "pct": 50, "samples": 64,
              "bounces": (4, 1, 2, 2, 0, 8)},
    "MEDIUM": {"label": "Medium", "engine": "CYCLES", "pct": 100, "samples": 64,
               "bounces": (4, 1, 2, 2, 0, 8)},
    "PRODUCTION": {"label": "Production", "engine": "CYCLES", "pct": 200, "samples": 512,
                   "bounces": (8, 3, 4, 6, 0, 8)},
}
QUALITY_ORDER = ("WORKBENCH", "LIGHT", "MEDIUM", "PRODUCTION")
BOUNCE_PROPS = ("max_bounces", "diffuse_bounces", "glossy_bounces",
                "transmission_bounces", "volume_bounces", "transparent_max_bounces")


# ---------------------------------------------------------------- quality
def quality_apply(scene, key):
    q = QUALITY[key]
    r = scene.render
    r.engine = q["engine"]
    r.resolution_percentage = q["pct"]
    if q["engine"] == "CYCLES":
        c = scene.cycles
        c.samples = q["samples"]
        for name, val in zip(BOUNCE_PROPS, q["bounces"]):
            setattr(c, name, val)
        c.caustics_reflective = False
        c.caustics_refractive = False
        c.use_denoising = True


def quality_matches(scene, key):
    q = QUALITY[key]
    r = scene.render
    if r.engine != q["engine"] or r.resolution_percentage != q["pct"]:
        return False
    if q["engine"] == "CYCLES":
        c = scene.cycles
        if c.samples != q["samples"] or c.caustics_reflective or c.caustics_refractive:
            return False
        for name, val in zip(BOUNCE_PROPS, q["bounces"]):
            if getattr(c, name) != val:
                return False
    return True


# ---------------------------------------------------------------- render job
_job = {}


def expand_path(path, scene, layer):
    blend = os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "untitled"
    return (path.replace("{scene}", scene.name)
                .replace("{layer}", layer)
                .replace("{blend}", blend))


def _status(scene, text):
    scene["rost_rp_status"] = text
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _restore():
    job = _job
    scene = job.get("scene")
    if scene is None:
        return
    try:
        for name, use in job["layers"].items():
            vl = scene.view_layers.get(name)
            if vl:
                vl.use = use
        for cam, use in job["dof"]:
            cam.dof.use_dof = use
        r = scene.render
        r.filepath = job["filepath"]
        r.film_transparent = job["film_transparent"]
        r.image_settings.color_mode = job["color_mode"]
        r.engine = job["engine"]
        scene.cycles.samples = job["cy_samples"]
        scene.eevee.taa_render_samples = job["ee_samples"]
        scene.cycles.use_denoising = job["denoise"]
    except ReferenceError:
        pass


def _finish(text):
    scene = _job.get("scene")
    _restore()
    _job.clear()
    if scene is not None:
        try:
            _status(scene, text)
        except ReferenceError:
            pass


def _begin_pass():
    job = _job
    if not job:
        return None
    scene = job["scene"]
    if not job["queue"]:
        _finish("Done: " + ", ".join(job["done"]))
        return None
    p = job["queue"].pop(0)
    job["current"] = p["layer"]
    for vl in scene.view_layers:
        vl.use = (vl.name == p["layer"])
    for cam, use in job["dof"]:
        cam.dof.use_dof = use if p["dof"] else False
    r = scene.render
    r.engine = job["engine"] if p["engine"] == "SCENE" else p["engine"]
    scene.cycles.samples = job["cy_samples"]
    scene.eevee.taa_render_samples = job["ee_samples"]
    if p["samples"] > 0:
        if r.engine == "CYCLES":
            scene.cycles.samples = p["samples"]
        elif r.engine == "BLENDER_EEVEE":
            scene.eevee.taa_render_samples = p["samples"]
    scene.cycles.use_denoising = job["denoise"] and p["denoise"]
    r.film_transparent = True if p["alpha"] else job["film_transparent"]
    r.image_settings.color_mode = job["color_mode"]
    if p["alpha"]:
        try:
            r.image_settings.color_mode = "RGBA"
        except TypeError:
            pass
    path = expand_path(p["path"], scene, p["layer"])
    if not job["animation"]:
        path += "%04d" % scene.frame_current
    r.filepath = path
    n = len(job["done"]) + 1
    _status(scene, "Rendering %d/%d: %s" % (n, job["total"], p["layer"]))
    try:
        win = job["window"]
        with bpy.context.temp_override(window=win):
            bpy.ops.render.render("INVOKE_DEFAULT", animation=job["animation"],
                                  write_still=True, use_viewport=False)
    except Exception as e:
        _finish("Error: %s" % e)
    return None


@persistent
def _on_complete(*args):
    if not _job:
        return
    _job["done"].append(_job.get("current", "?"))
    bpy.app.timers.register(_begin_pass, first_interval=0.5)


@persistent
def _on_cancel(*args):
    if not _job:
        return
    cur = _job.get("current", "?")
    bpy.app.timers.register(lambda: _finish("Cancelled at: " + cur), first_interval=0.2)


# ---------------------------------------------------------------- data
class ROSTRP_Pass(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="Render this pass", default=True)
    layer: StringProperty(name="View Layer", description="Name of the view layer to render")
    use_dof: BoolProperty(
        name="DoF", default=True,
        description="On: cameras keep their own depth of field. Off: DoF is switched off "
                    "on all cameras of the scene for this pass and restored afterwards")
    alpha: BoolProperty(
        name="Alpha", default=False,
        description="Render this pass with transparent film (RGBA). Off: scene setting is used")
    engine: EnumProperty(
        name="Engine", description="Render engine of this pass",
        items=[("SCENE", "As scene", "Use the render engine of the scene"),
               ("CYCLES", "Cycles", ""),
               ("BLENDER_EEVEE", "EEVEE", "")],
        default="SCENE")
    samples: IntProperty(
        name="Samples", default=0, min=0, soft_max=1024,
        description="Render samples of this pass. 0 = scene setting")
    denoise: BoolProperty(
        name="Denoise", default=True,
        description="On: scene setting is used. Off: Cycles denoising is switched off for this pass")
    path: StringProperty(
        name="Output", subtype="FILE_PATH", default=DEFAULT_PATH,
        description="Output path of this pass. Tokens: {scene} {layer} {blend}")


class ROSTRP_Settings(bpy.types.PropertyGroup):
    passes: CollectionProperty(type=ROSTRP_Pass)
    quality_all: BoolProperty(name="All scenes", default=False,
                              description="Apply the quality preset to every scene of the file")


# ---------------------------------------------------------------- operators
class ROSTRP_OT_quality(bpy.types.Operator):
    bl_idname = "rost_rp.quality"
    bl_label = "Render Quality Preset"
    bl_description = "Set engine, resolution %, samples and light paths (caustics off)"
    bl_options = {"REGISTER", "UNDO"}
    preset: EnumProperty(items=[(k, QUALITY[k]["label"], "") for k in QUALITY_ORDER])

    def execute(self, context):
        scenes = bpy.data.scenes if context.scene.rost_rp.quality_all else [context.scene]
        for s in scenes:
            quality_apply(s, self.preset)
        self.report({"INFO"}, "%s: %d scene(s)" % (QUALITY[self.preset]["label"], len(scenes)))
        return {"FINISHED"}


class ROSTRP_OT_pass_add(bpy.types.Operator):
    bl_idname = "rost_rp.pass_add"
    bl_label = "Add Pass"
    bl_description = "Add a render pass (takes the next view layer that is not in the list yet)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        used = {p.layer for p in sc.rost_rp.passes}
        p = sc.rost_rp.passes.add()
        free = [vl.name for vl in sc.view_layers if vl.name not in used]
        p.layer = free[0] if free else ""
        return {"FINISHED"}


class ROSTRP_OT_pass_remove(bpy.types.Operator):
    bl_idname = "rost_rp.pass_remove"
    bl_label = "Remove Pass"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty()

    def execute(self, context):
        context.scene.rost_rp.passes.remove(self.index)
        return {"FINISHED"}


class ROSTRP_OT_pass_move(bpy.types.Operator):
    bl_idname = "rost_rp.pass_move"
    bl_label = "Move Pass"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty()
    direction: IntProperty(default=-1)

    def execute(self, context):
        ps = context.scene.rost_rp.passes
        j = self.index + self.direction
        if 0 <= j < len(ps):
            ps.move(self.index, j)
        return {"FINISHED"}


class ROSTRP_OT_copy_to_scenes(bpy.types.Operator):
    bl_idname = "rost_rp.copy_to_scenes"
    bl_label = "Copy Passes to All Scenes"
    bl_description = "Replace the pass list of every other scene with this one"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        src = context.scene
        n = 0
        for s in bpy.data.scenes:
            if s == src:
                continue
            s.rost_rp.passes.clear()
            for p in src.rost_rp.passes:
                q = s.rost_rp.passes.add()
                for k in ("enabled", "layer", "use_dof", "alpha", "path", "engine", "samples", "denoise"):
                    setattr(q, k, getattr(p, k))
            n += 1
        self.report({"INFO"}, "Copied to %d scene(s)" % n)
        return {"FINISHED"}


class ROSTRP_OT_render(bpy.types.Operator):
    bl_idname = "rost_rp.render"
    bl_label = "Render Passes"
    bl_description = "Render the enabled passes one after another"
    animation: BoolProperty(default=True)

    def execute(self, context):
        if _job:
            self.report({"WARNING"}, "Render passes are already running")
            return {"CANCELLED"}
        sc = context.scene
        queue = []
        for p in sc.rost_rp.passes:
            if not p.enabled:
                continue
            if p.layer not in sc.view_layers:
                self.report({"ERROR"}, "View layer not found: '%s'" % p.layer)
                return {"CANCELLED"}
            if not p.path.strip():
                self.report({"ERROR"}, "No output path for '%s'" % p.layer)
                return {"CANCELLED"}
            queue.append({"layer": p.layer, "dof": p.use_dof, "alpha": p.alpha, "path": p.path,
                          "engine": p.engine, "samples": p.samples, "denoise": p.denoise})
        if not queue:
            self.report({"ERROR"}, "No enabled passes")
            return {"CANCELLED"}
        paths = [expand_path(q["path"], sc, q["layer"]) for q in queue]
        if len(set(paths)) != len(paths):
            self.report({"ERROR"}, "Two passes write to the same path")
            return {"CANCELLED"}
        cams = {o.data for o in sc.objects if o.type == "CAMERA"}
        r = sc.render
        _job.update({
            "scene": sc, "window": context.window, "animation": self.animation,
            "queue": queue, "total": len(queue), "done": [],
            "layers": {vl.name: vl.use for vl in sc.view_layers},
            "dof": [(c, c.dof.use_dof) for c in cams],
            "filepath": r.filepath, "film_transparent": r.film_transparent,
            "color_mode": r.image_settings.color_mode,
            "engine": r.engine, "cy_samples": sc.cycles.samples,
            "ee_samples": sc.eevee.taa_render_samples, "denoise": sc.cycles.use_denoising,
        })
        bpy.app.timers.register(_begin_pass, first_interval=0.1)
        return {"FINISHED"}


class ROSTRP_OT_restore(bpy.types.Operator):
    bl_idname = "rost_rp.restore"
    bl_label = "Stop Queue and Restore"
    bl_description = "Drop the remaining passes and put view layers, DoF and output path back"

    def execute(self, context):
        if _job:
            _finish("Stopped")
        return {"FINISHED"}


# ---------------------------------------------------------------- UI
class ROSTRP_PT_panel(bpy.types.Panel):
    bl_idname = "ROSTRP_PT_panel"
    bl_label = "Render Passes"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rost Tools"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        L = self.layout
        sc = context.scene
        st = sc.rost_rp

        col = L.column(align=True)
        col.label(text="Quality", icon="SCENE")
        grid = col.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for k in QUALITY_ORDER:
            op = grid.operator("rost_rp.quality", text=QUALITY[k]["label"],
                               depress=quality_matches(sc, k))
            op.preset = k
        r = sc.render
        info = "%d x %d" % (r.resolution_x * r.resolution_percentage // 100,
                            r.resolution_y * r.resolution_percentage // 100)
        if r.engine == "CYCLES":
            info += "  |  %d smp" % sc.cycles.samples
        row = col.row()
        row.label(text=info)
        row.prop(st, "quality_all")

        L.separator()
        L.label(text="Passes (view layer / DoF / path)", icon="RENDERLAYERS")
        for i, p in enumerate(st.passes):
            box = L.box()
            row = box.row(align=True)
            row.prop(p, "enabled", text="")
            sub = row.row(align=True)
            sub.alert = bool(p.layer) and p.layer not in sc.view_layers
            sub.prop_search(p, "layer", sc, "view_layers", text="")
            op = row.operator("rost_rp.pass_move", text="", icon="TRIA_UP")
            op.index = i
            op.direction = -1
            op = row.operator("rost_rp.pass_move", text="", icon="TRIA_DOWN")
            op.index = i
            op.direction = 1
            row.operator("rost_rp.pass_remove", text="", icon="X").index = i
            row = box.row(align=True)
            row.active = p.enabled
            row.prop(p, "use_dof", text="DoF on" if p.use_dof else "DoF off", toggle=True)
            row.prop(p, "alpha", text="Alpha", toggle=True)
            row.prop(p, "denoise", text="Denoise", toggle=True)
            row = box.row(align=True)
            row.active = p.enabled
            row.prop(p, "engine", text="")
            row.prop(p, "samples", text="Samples" if p.samples else "Samples (scene)")
            row = box.row()
            row.active = p.enabled
            row.prop(p, "path", text="")
        row = L.row(align=True)
        row.operator("rost_rp.pass_add", icon="ADD")
        row.operator("rost_rp.copy_to_scenes", text="To All Scenes", icon="DUPLICATE")

        L.separator()
        col = L.column(align=True)
        col.enabled = not _job
        col.scale_y = 1.5
        col.operator("rost_rp.render", text="RENDER ANIMATION", icon="RENDER_ANIMATION").animation = True
        row = L.row()
        row.enabled = not _job
        row.operator("rost_rp.render", text="Render Frame %d" % sc.frame_current,
                     icon="RENDER_STILL").animation = False
        if _job:
            L.operator("rost_rp.restore", icon="CANCEL")
        status = sc.get("rost_rp_status", "")
        if status:
            L.label(text=status, icon="INFO")


CLASSES = (ROSTRP_Pass, ROSTRP_Settings, ROSTRP_OT_quality, ROSTRP_OT_pass_add,
           ROSTRP_OT_pass_remove, ROSTRP_OT_pass_move, ROSTRP_OT_copy_to_scenes,
           ROSTRP_OT_render, ROSTRP_OT_restore)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.rost_rp = PointerProperty(type=ROSTRP_Settings)
    bpy.utils.register_class(ROSTRP_PT_panel)
    bpy.app.handlers.render_complete.append(_on_complete)
    bpy.app.handlers.render_cancel.append(_on_cancel)


def unregister():
    for h, f in ((bpy.app.handlers.render_complete, _on_complete),
                 (bpy.app.handlers.render_cancel, _on_cancel)):
        if f in h:
            h.remove(f)
    if _job:
        _restore()
        _job.clear()
    try:
        bpy.utils.unregister_class(ROSTRP_PT_panel)
    except Exception:
        pass
    del bpy.types.Scene.rost_rp
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
