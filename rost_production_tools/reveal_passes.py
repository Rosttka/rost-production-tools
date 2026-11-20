# Rost Reveal Passes (вбудовано в Rost Production Tools 4.4)
# SHELL -> копії (alternative), три view layer-и (original / alternative / line)
# + композитор з редагованими нодами і multilayer EXR (original, alternative, line, object_mask).

import bpy
from bpy.props import (BoolProperty, StringProperty, FloatProperty, PointerProperty, EnumProperty)

LAYER_ALT = "alternative"
LAYER_LINE = "line"
COLL_ALT = "SHELL_alternative"
MAT_LINE = "RV_Line_Mat"
MAT_ALT = "RV_Alt_Glass"
WIRE_MOD = "RV_Wire"
PFX = "RV_"
OUT_NAMES = ("original", "alternative", "line", "object_mask")


# ------------------------------------------------------------------ helpers
def _tree(scene):
    from . import get_compositor_tree
    return get_compositor_tree(scene, create=True)


def _lc_find(lc, coll):
    if lc.collection == coll:
        return lc
    for ch in lc.children:
        r = _lc_find(ch, coll)
        if r:
            return r
    return None


def _contains(coll, target):
    for ch in coll.children:
        if ch == target or _contains(ch, target):
            return True
    return False


def _get_layer(scene, name):
    vl = scene.view_layers.get(name)
    return vl if vl else scene.view_layers.new(name)


def _shell_meshes(st):
    """Меші SHELL без об'єктів KEEP (KEEP лишається як є, навіть якщо лежить і в SHELL)."""
    keep = set(st.keep.all_objects) if st.keep else set()
    return [o for o in st.shell.all_objects if o.type == 'MESH' and o not in keep]


def _drive_inputs(node, empty):
    """Входи групи Gradient Mask керуються custom-властивостями Empty (як у fx.apply_mask)."""
    for i, sock in enumerate(node.inputs):
        if sock.is_linked or not hasattr(sock, "default_value"):
            continue
        p = sock.name
        if p not in empty:
            continue
        try:
            sock.driver_remove("default_value")
        except Exception:
            pass
        val = empty[p]
        try:
            if isinstance(val, (float, int)):
                d = sock.driver_add("default_value").driver
                d.type = 'AVERAGE'
                v = d.variables.new()
                v.name = "var"
                v.type = 'SINGLE_PROP'
                v.targets[0].id_type = 'OBJECT'
                v.targets[0].id = empty
                v.targets[0].data_path = '["%s"]' % p
            else:
                for j in range(len(val)):
                    d = sock.driver_add("default_value", j).driver
                    d.type = 'AVERAGE'
                    v = d.variables.new()
                    v.name = "var"
                    v.type = 'SINGLE_PROP'
                    v.targets[0].id_type = 'OBJECT'
                    v.targets[0].id = empty
                    v.targets[0].data_path = '["%s"][%d]' % (p, j)
        except Exception as e:
            print("[Reveal] driver:", p, e)


TRANS_KEY = "Transition Width"


def _expose_transition(tree, default, seen=None):
    """Проводить вхід 'Transition Width' від групи до Distortion усіх Wave Texture всередині.
    Повертає True, якщо дерево (або вкладене) має Wave Texture."""
    seen = seen if seen is not None else {}
    if tree.name in seen:
        return seen[tree.name]
    seen[tree.name] = False
    waves = [n for n in tree.nodes if n.bl_idname == 'ShaderNodeTexWave']
    kids = []
    for n in tree.nodes:
        if n.bl_idname == 'ShaderNodeGroup' and n.node_tree and _expose_transition(n.node_tree, default, seen):
            kids.append(n)
    if not waves and not kids:
        return False
    seen[tree.name] = True
    if not any(it.item_type == 'SOCKET' and it.in_out == 'INPUT' and it.name == TRANS_KEY
               for it in tree.interface.items_tree):
        sk = tree.interface.new_socket(TRANS_KEY, in_out='INPUT', socket_type='NodeSocketFloat')
        sk.default_value = default
        sk.min_value = 0.0
    gin = next((n for n in tree.nodes if n.bl_idname == 'NodeGroupInput'), None)
    if gin is None:
        gin = tree.nodes.new('NodeGroupInput')
    src = gin.outputs.get(TRANS_KEY)
    if src is None:
        return True
    for n in waves:
        dst = n.inputs['Distortion']
        if not dst.is_linked:
            tree.links.new(src, dst)
    for n in kids:
        dst = n.inputs.get(TRANS_KEY)
        if dst is not None and not dst.is_linked:
            tree.links.new(src, dst)
    return True


def _setup_transition(empty):
    """Ширина зони розсипання: custom-властивість Empty 'Transition Width' (Distortion у Wave Texture)."""
    root = bpy.data.node_groups.get(empty.get("fx_linked_group", ""))
    if root is None:
        return
    if TRANS_KEY not in empty:
        wv = None
        stack, seen = [root], set()
        while stack and wv is None:
            t = stack.pop()
            if t.name in seen:
                continue
            seen.add(t.name)
            for n in t.nodes:
                if n.bl_idname == 'ShaderNodeTexWave' and not n.inputs['Distortion'].is_linked:
                    wv = n
                    break
                if n.bl_idname == 'ShaderNodeGroup' and n.node_tree:
                    stack.append(n.node_tree)
        empty[TRANS_KEY] = float(wv.inputs['Distortion'].default_value) if wv else 0.13
    try:
        empty.id_properties_ui(TRANS_KEY).update(min=0.0, max=3.0, soft_max=1.0)
    except Exception:
        pass
    if not _expose_transition(root, float(empty[TRANS_KEY])):
        return
    for m in bpy.data.materials:
        if not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.bl_idname == 'ShaderNodeGroup' and n.node_tree == root:
                _drive_inputs(n, empty)


def _make_line_material(empty):
    group = bpy.data.node_groups.get(empty.get("fx_linked_group", ""))
    if group is None:
        return None
    mat = bpy.data.materials.get(MAT_LINE)
    if mat is None:
        mat = bpy.data.materials.new(MAT_LINE)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (700, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (350, 0)
    bsdf.inputs['Base Color'].default_value = (0, 0, 0, 1)
    bsdf.inputs['Roughness'].default_value = 1.0
    bsdf.inputs['Specular IOR Level'].default_value = 0.0
    bsdf.inputs['Emission Color'].default_value = (1, 1, 1, 1)
    g = nt.nodes.new('ShaderNodeGroup')
    g.node_tree = group
    g.location = (-250, 0)
    add = nt.nodes.new('ShaderNodeMath')
    add.operation = 'ADD'
    add.location = (100, -200)
    nt.links.new(g.outputs['Line'], bsdf.inputs['Emission Strength'])
    nt.links.new(g.outputs['Surface'], add.inputs[0])
    nt.links.new(g.outputs['Line'], add.inputs[1])
    nt.links.new(add.outputs[0], bsdf.inputs['Alpha'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    _drive_inputs(g, empty)
    empty.update_tag()
    return mat


def _make_alt_material():
    mat = bpy.data.materials.get(MAT_ALT)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(MAT_ALT)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Transmission Weight'].default_value = 1.0
    bsdf.inputs['IOR'].default_value = 1.08
    bsdf.inputs['Specular IOR Level'].default_value = 0.2
    bsdf.inputs['Roughness'].default_value = 0.03
    bsdf.inputs['Emission Color'].default_value = (0.35, 0.75, 1.0, 1.0)
    fr = nt.nodes.new('ShaderNodeFresnel')
    fr.location = (-300, -250)
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 0.6
    mul.location = (-100, -250)
    nt.links.new(fr.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], bsdf.inputs['Emission Strength'])
    return mat


def _shell_material_ids(st):
    names = set()
    for o in _shell_meshes(st):
        for s in o.material_slots:
            if s.material:
                names.add(s.material.name)
    return ",".join(('"%s"' % n) if "," in n else n for n in sorted(names))



# ------------------------------------------------------------------ shape mask (SDF)
SHAPES_COLL = "RV_Shapes"
SDF_GROUP = "RV_ShapeSDF"
SDF_VER = 1
MAX_SHAPES = 8
K_MODE = "Mask Mode"
K_INV = "Shape Invert"
K_SOFT = "Shape Softness"
SHAPE_ITEMS = (
    ('SPHERE', "Sphere", "Сфера (радіус 1 при Scale 1)", 'MESH_UVSPHERE', 0),
    ('BOX', "Box", "Куб (півсторона 1 при Scale 1)", 'MESH_CUBE', 1),
    ('CYLINDER', "Cylinder", "Циліндр уздовж Z (радіус 1, півдовжина 1 при Scale 1)", 'MESH_CYLINDER', 2),
    ('CAPSULE', "Capsule", "Капсула уздовж Z (радіус 1, прямий відрізок 2 при Scale 1)", 'MESH_CAPSULE', 3),
)
SHAPE_IDX = {i[0]: i[4] for i in SHAPE_ITEMS}


class _B:
    """Мала обгортка для побудови нод із авторозкладкою."""

    def __init__(self, tree, prefix="", x0=0, y0=0):
        self.t = tree
        self.pfx = prefix
        self.x0 = x0
        self.y0 = y0
        self.i = 0

    def node(self, idname):
        n = self.t.nodes.new(idname)
        n.location = (self.x0 + (self.i % 9) * 210, self.y0 - (self.i // 9) * 170)
        self.i += 1
        if self.pfx:
            n.name = self.pfx + n.name
        return n

    def _set(self, n, i, x):
        if x is None:
            return
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = float(x)
        elif isinstance(x, tuple):
            n.inputs[i].default_value = x
        else:
            self.t.links.new(x, n.inputs[i])

    def math(self, op, a, b=None, c=None):
        n = self.node('ShaderNodeMath')
        n.operation = op
        for i, x in enumerate((a, b, c)):
            self._set(n, i, x)
        return n.outputs[0]

    def vec(self, op, a, b=None):
        n = self.node('ShaderNodeVectorMath')
        n.operation = op
        self._set(n, 0, a)
        self._set(n, 1, b)
        return n

    def vlen(self, a):
        return self.vec('LENGTH', a).outputs['Value']

    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.t.links.new(v, n.inputs[0])
        return n.outputs['X'], n.outputs['Y'], n.outputs['Z']

    def comb(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        for i, v in enumerate((x, y, z)):
            self._set(n, i, v)
        return n.outputs[0]


def _sdf_group():
    """Група RV_ShapeSDF: знакова відстань до фігури в її локальному просторі.
    Входи: P (Texture Coordinate > Object фігури), Shape = (тип 0..3, масштаб, увімкнено)."""
    g = bpy.data.node_groups.get(SDF_GROUP)
    if g is not None and g.get("rv_ver") == SDF_VER:
        return g
    if g is None:
        g = bpy.data.node_groups.new(SDF_GROUP, 'ShaderNodeTree')
    else:
        g.nodes.clear()
        g.interface.clear()
    g["rv_ver"] = SDF_VER
    g.interface.new_socket("Distance", in_out='OUTPUT', socket_type='NodeSocketFloat')
    g.interface.new_socket("P", in_out='INPUT', socket_type='NodeSocketVector')
    ss = g.interface.new_socket("Shape", in_out='INPUT', socket_type='NodeSocketVector')
    ss.default_value = (0.0, 1.0, 0.0)
    gin = g.nodes.new('NodeGroupInput')
    gin.location = (-300, 0)
    gout = g.nodes.new('NodeGroupOutput')
    gout.location = (2200, 0)
    b = _B(g, "", 0, 300)
    p = gin.outputs['P']
    px, py, pz = b.sep(p)
    tp, sc, on = b.sep(gin.outputs['Shape'])
    # sphere
    dS = b.math('SUBTRACT', b.vlen(p), 1.0)
    # box
    q = b.vec('SUBTRACT', b.vec('ABSOLUTE', p).outputs['Vector'], (1.0, 1.0, 1.0)).outputs['Vector']
    qx, qy, qz = b.sep(q)
    mx = b.math('MAXIMUM', b.math('MAXIMUM', qx, qy), qz)
    qp = b.vec('MAXIMUM', q, (0.0, 0.0, 0.0)).outputs['Vector']
    dB = b.math('ADD', b.vlen(qp), b.math('MINIMUM', mx, 0.0))
    # cylinder (вісь Z)
    dxy = b.math('SUBTRACT', b.vlen(b.comb(px, py, 0.0)), 1.0)
    dz = b.math('SUBTRACT', b.math('ABSOLUTE', pz), 1.0)
    mn = b.math('MINIMUM', b.math('MAXIMUM', dxy, dz), 0.0)
    ax = b.math('MAXIMUM', dxy, 0.0)
    az = b.math('MAXIMUM', dz, 0.0)
    ln = b.math('SQRT', b.math('ADD', b.math('MULTIPLY', ax, ax), b.math('MULTIPLY', az, az)))
    dC = b.math('ADD', ln, mn)
    # capsule (вісь Z, відрізок -1..1)
    cz = b.math('MINIMUM', b.math('MAXIMUM', pz, -1.0), 1.0)
    dK = b.math('SUBTRACT', b.vlen(b.comb(px, py, b.math('SUBTRACT', pz, cz))), 1.0)
    # вибір за типом
    w = [b.math('COMPARE', tp, float(i), 0.5) for i in range(4)]
    d = b.math('MULTIPLY_ADD', dS, w[0],
               b.math('MULTIPLY_ADD', dB, w[1],
                      b.math('MULTIPLY_ADD', dC, w[2], b.math('MULTIPLY', dK, w[3]))))
    d = b.math('MULTIPLY', d, sc)
    d = b.math('MULTIPLY_ADD', b.math('SUBTRACT', d, 1000.0), on, 1000.0)
    g.links.new(d, gout.inputs['Distance'])
    return g


def _expose_chain(tree, key, stype, default, seen=None):
    """Додає вхід key у всі групи від кореня до групи з Wave Texture і з'єднує їх."""
    seen = seen if seen is not None else {}
    if tree.name in seen:
        return seen[tree.name]
    seen[tree.name] = False
    leaf = any(n.bl_idname == 'ShaderNodeTexWave' for n in tree.nodes)
    kids = [n for n in tree.nodes if n.bl_idname == 'ShaderNodeGroup' and n.node_tree
            and _expose_chain(n.node_tree, key, stype, default, seen)]
    if not leaf and not kids:
        return False
    seen[tree.name] = True
    if not any(it.item_type == 'SOCKET' and it.in_out == 'INPUT' and it.name == key
               for it in tree.interface.items_tree):
        sk = tree.interface.new_socket(key, in_out='INPUT', socket_type=stype)
        try:
            sk.default_value = default
        except Exception:
            pass
    if kids:
        gin = next((n for n in tree.nodes if n.bl_idname == 'NodeGroupInput'), None)
        if gin is None:
            gin = tree.nodes.new('NodeGroupInput')
        src = gin.outputs.get(key)
        if src is not None:
            for n in kids:
                dst = n.inputs.get(key)
                if dst is not None and not dst.is_linked:
                    tree.links.new(src, dst)
    return True


def _leaf_trees(root, seen=None):
    seen = seen if seen is not None else set()
    out = []
    if root.name in seen:
        return out
    seen.add(root.name)
    if any(n.bl_idname == 'ShaderNodeTexWave' for n in root.nodes):
        out.append(root)
    for n in root.nodes:
        if n.bl_idname == 'ShaderNodeGroup' and n.node_tree:
            out += _leaf_trees(n.node_tree, seen)
    return out


def _setup_shape_mask(leaf, objs):
    """У групі з Wave Texture: Z-координата хвилі береться або від площини (Empty), або від відстані до фігур."""
    waves = [n for n in leaf.nodes if n.bl_idname == 'ShaderNodeTexWave']
    mapn = leaf.nodes.get('Mapping')
    gin = next((n for n in leaf.nodes if n.bl_idname == 'NodeGroupInput'), None)
    if not waves or mapn is None or gin is None or gin.outputs.get(K_MODE) is None or gin.outputs.get(K_SOFT) is None:
        return False
    for n in [n for n in leaf.nodes if n.name.startswith('RVS_')]:
        leaf.nodes.remove(n)
    for w in waves:
        leaf.links.new(mapn.outputs['Vector'], w.inputs['Vector'])
    b = _B(leaf, 'RVS_', -1700, -1000)
    x, y, z = b.sep(mapn.outputs['Vector'])
    sdf = _sdf_group()
    ds = []
    for i, o in enumerate(objs[:MAX_SHAPES], 1):
        tc = b.node('ShaderNodeTexCoord')
        tc.object = o
        gn = b.node('ShaderNodeGroup')
        gn.node_tree = sdf
        leaf.links.new(tc.outputs['Object'], gn.inputs['P'])
        leaf.links.new(gin.outputs['Shape %d' % i], gn.inputs['Shape'])
        ds.append(gn.outputs['Distance'])
    if ds:
        D = ds[0]
        for s in ds[1:]:
            D = b.math('MINIMUM', D, s)
    else:
        D = b.math('ADD', 1000.0, 0.0)
    s2 = b.math('MULTIPLY_ADD', gin.outputs[K_INV], 2.0, -1.0)
    zeq = b.math('DIVIDE', b.math('MULTIPLY', D, s2), b.math('MAXIMUM', gin.outputs[K_SOFT], 0.001))
    zc = b.math('MAXIMUM', b.math('MINIMUM', zeq, 6.5), -3.5)
    val = leaf.nodes.get('Value')
    sc_in = val.outputs[0] if val is not None else float(mapn.inputs['Scale'].default_value[0])
    zD = b.math('MULTIPLY_ADD', zc, sc_in, float(mapn.inputs['Location'].default_value[2]))
    zsel = b.math('MULTIPLY_ADD', b.math('SUBTRACT', zD, z), gin.outputs[K_MODE], z)
    vec = b.comb(x, y, zsel)
    for w in waves:
        leaf.links.new(vec, w.inputs['Vector'])
    return True


def _shapes_coll(sc, create=True):
    c = bpy.data.collections.get(SHAPES_COLL)
    if c is None and create:
        c = bpy.data.collections.new(SHAPES_COLL)
    if c is not None and create and c.name not in sc.collection.children:
        sc.collection.children.link(c)
    return c


def _shape_objects(sc):
    c = _shapes_coll(sc, create=False)
    if c is None:
        return []
    return sorted(c.all_objects, key=lambda o: o.name)[:MAX_SHAPES]


def _shapes_visible(sc):
    c = _shapes_coll(sc, create=False)
    if c is None:
        return
    for vl in sc.view_layers:
        lc = _lc_find(vl.layer_collection, c)
        if lc:
            lc.exclude = False
            lc.holdout = False


def _clear_drivers(idb, path):
    try:
        idb.driver_remove(path)
    except Exception:
        pass


def _drive_shape_slot(e, key, o):
    _clear_drivers(e, '["%s"]' % key)
    e[key] = [float(SHAPE_IDX.get(o.rv_shape, 0)), 1.0, 1.0]
    d = e.driver_add('["%s"]' % key, 0).driver
    d.type = 'AVERAGE'
    v = d.variables.new()
    v.name = "t"
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'
    v.targets[0].id = o
    v.targets[0].data_path = 'rv_shape'
    d = e.driver_add('["%s"]' % key, 1).driver
    d.type = 'AVERAGE'
    for ax in 'XYZ':
        v = d.variables.new()
        v.name = "s" + ax
        v.type = 'TRANSFORMS'
        v.targets[0].id = o
        v.targets[0].transform_type = 'SCALE_' + ax
        v.targets[0].transform_space = 'WORLD_SPACE'


def _setup_shapes(sc, st):
    """Колекція RV_Shapes -> слоти Shape 1..8 на Empty, входи в групах, нода SDF у Gradient Mask."""
    e = st.empty
    if e is None:
        return 0
    root = bpy.data.node_groups.get(e.get("fx_linked_group", ""))
    if root is None:
        return 0
    _shapes_coll(sc)
    _shapes_visible(sc)
    objs = _shape_objects(sc)
    _expose_chain(root, K_MODE, 'NodeSocketFloat', 0.0, {})
    _expose_chain(root, K_INV, 'NodeSocketFloat', 0.0, {})
    _expose_chain(root, K_SOFT, 'NodeSocketFloat', 1.0, {})
    for i in range(1, MAX_SHAPES + 1):
        _expose_chain(root, "Shape %d" % i, 'NodeSocketVector', (0.0, 1.0, 0.0), {})
    for lf in _leaf_trees(root):
        _setup_shape_mask(lf, objs)
    e[K_MODE] = 1.0 if st.mask_source == 'SHAPES' else 0.0
    e[K_INV] = 1.0 if st.shape_invert else 0.0
    if K_SOFT not in e:
        e[K_SOFT] = 1.0
    for i in range(1, MAX_SHAPES + 1):
        key = "Shape %d" % i
        if i <= len(objs):
            _drive_shape_slot(e, key, objs[i - 1])
        else:
            _clear_drivers(e, '["%s"]' % key)
            e[key] = [0.0, 1.0, 0.0]
    for m in bpy.data.materials:
        if not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.bl_idname == 'ShaderNodeGroup' and n.node_tree == root:
                _drive_inputs(n, e)
    e.update_tag()
    return len(objs)

# ------------------------------------------------------------------ wireframe collection
COLL_WIRE = "SHELL_wire"
SFX_WIRE = ".wire"


def _wire_sync(sc, st, alt_mat):
    """Колекція SHELL_wire: копії деталей SHELL зі спільним мешем, усі вимкнені (hide_render, hide_viewport).
    Існуючі копії (модифікатори, матеріали) не чіпаємо: додаємо відсутні, прибираємо зайві."""
    wc = bpy.data.collections.get(COLL_WIRE)
    if wc is None:
        wc = bpy.data.collections.new(COLL_WIRE)
    if wc.name not in sc.collection.children:
        sc.collection.children.link(wc)
    src = _shell_meshes(st)
    srcset = set(src)
    want = {o.name + SFX_WIRE for o in src}
    for c in list(wc.objects):
        if c.name not in want:
            bpy.data.objects.remove(c, do_unlink=True)
    copies, fresh = {}, set()
    for o in src:
        nm = o.name + SFX_WIRE
        c = wc.objects.get(nm)
        if c is None:
            c = bpy.data.objects.new(nm, o.data)
            wc.objects.link(c)
            c.hide_viewport = True
            c.hide_render = True
            for s in c.material_slots:
                s.link = 'OBJECT'
                s.material = alt_mat
            fresh.add(o)
        copies[o] = c
    for o in fresh:
        c = copies[o]
        par = o.parent
        c.parent = copies.get(par, par) if par in srcset else par
        c.parent_type = o.parent_type
        c.parent_bone = o.parent_bone
        c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        c.matrix_basis = o.matrix_basis.copy()
    return wc


def _wire_targets(context):
    out = []
    for o in context.selected_objects:
        base = o.name[:-len(SFX_WIRE)] if o.name.endswith(SFX_WIRE) else o.name
        c = bpy.data.objects.get(base + SFX_WIRE)
        if c is not None and c not in out:
            out.append(c)
    return out


def _upd_wire(self, context):
    wc = bpy.data.collections.get(COLL_WIRE)
    if wc is None:
        return
    for c in wc.objects:
        md = c.modifiers.get(WIRE_MOD)
        if md is not None:
            md.thickness = self.wire_thickness


def _upd_mask(self, context):
    e = self.empty
    if e is None:
        return
    root = bpy.data.node_groups.get(e.get("fx_linked_group", ""))
    if root is None:
        return
    if K_MODE not in e:
        if self.mask_source == 'SHAPES':
            _setup_shapes(context.scene, self)
        return
    e[K_MODE] = 1.0 if self.mask_source == 'SHAPES' else 0.0
    e[K_INV] = 1.0 if self.shape_invert else 0.0
    e.update_tag()

# ------------------------------------------------------------------ copies
def _build_copies(sc, st, alt_mat):
    shell = st.shell
    ac = bpy.data.collections.get(COLL_ALT)
    if ac is None:
        ac = bpy.data.collections.new(COLL_ALT)
        sc.collection.children.link(ac)
    elif ac.name not in sc.collection.children:
        sc.collection.children.link(ac)
    for o in list(ac.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    src = _shell_meshes(st)
    srcset = set(src)
    copies = {}
    for o in src:
        c = bpy.data.objects.new(o.name + ".alt", o.data)
        copies[o] = c
        ac.objects.link(c)
    for o, c in copies.items():
        par = o.parent
        c.parent = copies.get(par, par) if par in srcset else par
        c.parent_type = o.parent_type
        c.parent_bone = o.parent_bone
        c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        c.matrix_basis = o.matrix_basis.copy()
        for s in c.material_slots:
            s.link = 'OBJECT'
            s.material = alt_mat
    return ac, len(copies)


# ------------------------------------------------------------------ layers
def _apply_layers(sc, st, ac, line_mat):
    shell, keep = st.shell, st.keep
    shell_objs = set(_shell_meshes(st))
    vl_o = sc.view_layers[st.original_layer]
    vl_a = _get_layer(sc, LAYER_ALT)
    vl_l = _get_layer(sc, LAYER_LINE)

    # original: тільки без копій
    lc = _lc_find(vl_o.layer_collection, ac)
    if lc:
        lc.exclude = True
    wc = bpy.data.collections.get(COLL_WIRE)
    lw = _lc_find(vl_o.layer_collection, wc) if wc else None
    if lw:
        lw.exclude = True
    shp = bpy.data.collections.get(SHAPES_COLL)
    vl_o.use_pass_cryptomatte_material = True
    vl_o.pass_cryptomatte_depth = 4

    # alternative: без SHELL і без колекцій, де лежать об'єкти SHELL; KEEP і копії лишаються
    def walk_alt(lc0):
        for ch in lc0.children:
            c = ch.collection
            if c == ac or c == keep or _contains(c, keep) or _contains(c, ac):
                ch.exclude = False
                if c != keep and c != ac:
                    walk_alt(ch)
            elif c == shell or any(o in shell_objs for o in c.objects):
                ch.exclude = True
            else:
                ch.exclude = False
                walk_alt(ch)
    walk_alt(vl_a.layer_collection)

    # line: лише SHELL + KEEP (KEEP = holdout), решта вимкнена, світла немає
    def walk_line(lc0):
        for ch in lc0.children:
            c = ch.collection
            if shp is not None and c == shp:
                ch.exclude = False
                ch.holdout = False
            elif c == shell or c == keep:
                ch.exclude = False
                ch.holdout = (c == keep)
            elif _contains(c, shell) or _contains(c, keep):
                ch.exclude = False
                ch.holdout = False
                walk_line(ch)
            else:
                ch.exclude = True
    walk_line(vl_l.layer_collection)
    vl_l.use_sky = False
    if line_mat:
        vl_l.material_override = line_mat
    return vl_a, vl_l


# ------------------------------------------------------------------ compositor
def _build_compositor(sc, st, reset=False):
    from . import _new_color_ramp, _set_alpha_replace
    tree = _tree(sc)
    nodes, links = tree.nodes, tree.links
    if reset:
        for n in [n for n in nodes if n.name.startswith(PFX)]:
            nodes.remove(n)
    matte = _shell_material_ids(st)

    def get(name, idname, label, loc, parent=None):
        n = nodes.get(name)
        if n is None:
            n = nodes.new(idname)
            n.name = name
            n.location = loc
            n.label = label
            n.parent = parent
            return n, True
        return n, False

    fr, _ = get(PFX + "Frame", 'NodeFrame', "Reveal Passes", (0, 0))
    fr.label_size = 20
    fr.shrink = True
    rls = {}
    y = 0
    for key, layer in (("original", st.original_layer), (LAYER_ALT, LAYER_ALT), (LAYER_LINE, LAYER_LINE)):
        rl, new = get(PFX + "RL_" + key, 'CompositorNodeRLayers', "RL " + key, (-700, y), fr)
        rl.scene = sc
        rl.layer = layer
        rls[key] = rl
        y -= 420
    ramp, n1 = get(PFX + "Line_Ramp", 'ShaderNodeValToRGB', "Line Ramp", (-380, -840), fr)
    if n1:
        ramp.parent = fr
    sa, n2 = get(PFX + "Line_SetAlpha", 'CompositorNodeSetAlpha', "Line Set Alpha", (-120, -840), fr)
    if n2:
        _set_alpha_replace(sa)
    cr, n3 = get(PFX + "ObjectMask", 'CompositorNodeCryptomatteV2', "object_mask", (-380, -1200), fr)
    cr.scene = sc
    cr.source = 'RENDER'
    cr.layer_name = st.original_layer + ".CryptoMaterial"
    cr.matte_id = matte
    fo, n4 = get(PFX + "FileOut", 'CompositorNodeOutputFile', "Reveal EXR", (300, -400), fr)
    if n4:
        fo.directory = st.output_dir
        fo.file_name = "reveal_"
        fo.format.file_format = 'OPEN_EXR_MULTILAYER'
        fo.format.color_depth = '16'
        fo.format.exr_codec = 'DWAA'
        for nm in OUT_NAMES:
            fo.file_output_items.new('FLOAT' if nm == "object_mask" else 'RGBA', nm)

    def link_once(a, b):
        if not b.is_linked:
            links.new(a, b)

    if n1 or n2 or n3 or n4 or reset:
        links.new(rls[LAYER_LINE].outputs['Image'], sa.inputs['Image'])
        links.new(rls[LAYER_LINE].outputs['Image'], ramp.inputs[0])
        links.new(ramp.outputs[0], sa.inputs['Alpha'])
        by = {i.name: k for k, i in enumerate(fo.file_output_items)}
        src = {"original": rls["original"].outputs['Image'],
               "alternative": rls[LAYER_ALT].outputs['Image'],
               "line": sa.outputs[0],
               "object_mask": cr.outputs['Matte']}
        for nm, s in src.items():
            if nm in by:
                links.new(s, fo.inputs[by[nm]])
    # F12 показує original, якщо вихід композитора вільний
    from . import _compositor_output_sockets
    for sock in _compositor_output_sockets(tree):
        link_once(rls["original"].outputs['Image'], sock)
    sc.render.use_compositing = True
    return tree


# ------------------------------------------------------------------ properties
class ROSTRV_Settings(bpy.types.PropertyGroup):
    shell: PointerProperty(type=bpy.types.Collection, name="SHELL",
                           description="Меші, що стають склом / іншим матеріалом (зникають в original)")
    keep: PointerProperty(type=bpy.types.Collection, name="KEEP",
                          description="Меші, що лишаються як є (видно у всіх шарах, у line - holdout)")
    empty: PointerProperty(type=bpy.types.Object, name="Gradient Empty",
                           poll=lambda self, o: o.type == 'EMPTY',
                           description="Empty активного Gradient Mask (Gradient_Direction)")
    original_layer: StringProperty(name="Original layer", description="View layer з оригінальними матеріалами та маскою")
    alt_material: PointerProperty(type=bpy.types.Material, name="Alternative material",
                                  description="Матеріал для alternative-проходу (скло або будь-що). Порожньо = RV_Alt_Glass")
    wire_thickness: FloatProperty(name="Thickness", default=0.0008, min=0.0, precision=4, unit='LENGTH',
                                  update=_upd_wire)
    mask_source: EnumProperty(name="Mask", items=(('PLANE', "Plane", "Площина (Empty Gradient_Direction)"),
                                                  ('SHAPES', "Shapes", "Фігури з колекції RV_Shapes")),
                              default='PLANE', update=_upd_mask)
    shape_invert: BoolProperty(name="Invert", default=False, update=_upd_mask,
                               description="Інвертувати: ефект зовні фігур замість усередині")
    show_adv: BoolProperty(name="Advanced", default=False)
    output_dir: StringProperty(name="Output", subtype='DIR_PATH', default="//renders/reveal/")


# ------------------------------------------------------------------ operators
class ROSTRV_OT_build(bpy.types.Operator):
    bl_idname = "rost_rv.build"
    bl_label = "Build / Update"
    bl_description = ("Створити або оновити: копії SHELL, view layer-и alternative і line, "
                      "матеріал лінії, Cryptomatte-маску й ноди композитора. Наявні ноди RV_ не перезаписує")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import sys
        sc = context.scene
        st = sc.rost_rv
        if not st.shell or not st.keep:
            self.report({'ERROR'}, "Вкажи колекції SHELL і KEEP")
            return {'CANCELLED'}
        targets = _shell_meshes(st)
        if not targets:
            self.report({'ERROR'}, "У SHELL немає мешів (за вирахуванням KEEP)")
            return {'CANCELLED'}
        cur = context.view_layer.name
        if st.original_layer not in sc.view_layers or st.original_layer in (LAYER_ALT, LAYER_LINE):
            if cur in (LAYER_ALT, LAYER_LINE):
                self.report({'ERROR'}, "Перейди на свій оригінальний view layer і натисни Build")
                return {'CANCELLED'}
            st.original_layer = cur

        # 1) Gradient-інструмент: створюємо, якщо ще немає
        if (st.empty is not None and "fx_linked_group" not in st.empty
                and st.empty.name == sc.fx_active_empty_name and sc.fx_active_group_name):
            st.empty["fx_linked_group"] = sc.fx_active_group_name
        grp_ok = st.empty is not None and bpy.data.node_groups.get(st.empty.get("fx_linked_group", "")) is not None
        if not grp_ok:
            if 'FINISHED' not in bpy.ops.fx.create_new_instance():
                self.report({'ERROR'}, "Не вдалося створити Gradient-інструмент")
                return {'CANCELLED'}
            st.empty = bpy.data.objects.get(sc.fx_active_empty_name)
        else:
            sc.fx_active_empty_name = st.empty.name
            sc.fx_active_group_name = st.empty["fx_linked_group"]

        # 2) маска на матеріали SHELL (локалізація Library Override + Surface Mode).
        #    Композитор Gradient Mask при цьому не чіпаємо: його будуємо самі (RV_*)
        pkg = sys.modules[__package__]
        saved = (pkg.setup_compositor, pkg.ensure_comp_output)
        pkg.setup_compositor = lambda scene: None
        pkg.ensure_comp_output = lambda scene: None
        try:
            with context.temp_override(selected_objects=targets, active_object=targets[0]):
                bpy.ops.fx.apply_mask()
                bpy.ops.fx.switch_mode(mode='SURFACE')
        finally:
            pkg.setup_compositor, pkg.ensure_comp_output = saved

        # стартова ширина лінії (у шаблоні групи 0 = лінії не видно)
        if st.empty.get("Line Border Size", 0.0) == 0.0:
            st.empty["Line Border Size"] = 0.03

        _setup_transition(st.empty)
        _setup_shapes(sc, st)

        # 3) лінія, копії, шари, композитор
        line_mat = _make_line_material(st.empty)
        if line_mat is None:
            self.report({'ERROR'}, "Група Gradient Mask не знайдена")
            return {'CANCELLED'}
        alt_mat = st.alt_material or _make_alt_material()
        ac, n = _build_copies(sc, st, alt_mat)
        _wire_sync(sc, st, alt_mat)
        _apply_layers(sc, st, ac, line_mat)
        _build_compositor(sc, st)
        sc["rost_rv_status"] = "Копій: %d. Шари: %s / %s / %s" % (n, st.original_layer, LAYER_ALT, LAYER_LINE)
        self.report({'INFO'}, sc["rost_rv_status"])
        return {'FINISHED'}


class ROSTRV_OT_select_gradient(bpy.types.Operator):
    bl_idname = "rost_rv.select_gradient"
    bl_label = "Select Gradient"
    bl_description = "Виділити Empty градієнта (його рухають і анімують, щоб проявлявся шел)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        e = context.scene.rost_rv.empty
        if e is None or e.name not in context.view_layer.objects:
            self.report({'WARNING'}, "Empty ще не створено або його немає в цьому view layer")
            return {'CANCELLED'}
        for o in context.view_layer.objects:
            o.select_set(False)
        e.select_set(True)
        context.view_layer.objects.active = e
        return {'FINISHED'}


class ROSTRV_OT_reset_comp(bpy.types.Operator):
    bl_idname = "rost_rv.reset_comp"
    bl_label = "Reset Compositor Nodes"
    bl_description = "Видалити ноди RV_ і створити їх заново (твої правки в них буде втрачено)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = context.scene.rost_rv
        if not st.shell:
            self.report({'ERROR'}, "Спочатку вкажи SHELL")
            return {'CANCELLED'}
        if st.original_layer not in context.scene.view_layers:
            st.original_layer = context.view_layer.name
        _build_compositor(context.scene, st, reset=True)
        return {'FINISHED'}


class ROSTRV_OT_refresh_mask(bpy.types.Operator):
    bl_idname = "rost_rv.refresh_mask"
    bl_label = "Refresh object_mask"
    bl_description = "Оновити список матеріалів SHELL у Cryptomatte-вузлі object_mask"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sc = context.scene
        st = sc.rost_rv
        tree = _tree(sc)
        cr = tree.nodes.get(PFX + "ObjectMask")
        if cr is None or not st.shell:
            self.report({'WARNING'}, "Немає вузла RV_ObjectMask або SHELL")
            return {'CANCELLED'}
        cr.matte_id = _shell_material_ids(st)
        return {'FINISHED'}


class ROSTRV_OT_remove(bpy.types.Operator):
    bl_idname = "rost_rv.remove"
    bl_label = "Remove Reveal Setup"
    bl_description = ("Видалити копії, колекцію SHELL_alternative, view layer-и alternative/line, "
                      "ноди RV_ і створені матеріали. Original layer не чіпає")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sc = context.scene
        st = sc.rost_rv
        ac = bpy.data.collections.get(COLL_ALT)
        if ac:
            for o in list(ac.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(ac)
        wcl = bpy.data.collections.get(COLL_WIRE)
        if wcl:
            for o in list(wcl.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(wcl)
        for nm in (LAYER_ALT, LAYER_LINE):
            vl = sc.view_layers.get(nm)
            if vl and len(sc.view_layers) > 1:
                sc.view_layers.remove(vl)
        tree = _tree(sc)
        for n in [n for n in tree.nodes if n.name.startswith(PFX)]:
            tree.nodes.remove(n)
        for nm in (MAT_LINE, MAT_ALT):
            m = bpy.data.materials.get(nm)
            if m and m.users == 0:
                bpy.data.materials.remove(m)
        sc["rost_rv_status"] = "Reveal setup видалено"
        return {'FINISHED'}



class ROSTRV_OT_add_shape(bpy.types.Operator):
    bl_idname = "rost_rv.add_shape"
    bl_label = "Add Shape"
    bl_description = "Додати фігуру маски в колекцію RV_Shapes (у позицію 3D-курсора)"
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(items=SHAPE_ITEMS, default='SPHERE')

    def execute(self, context):
        sc = context.scene
        st = sc.rost_rv
        coll = _shapes_coll(sc)
        if len(coll.all_objects) >= MAX_SHAPES:
            self.report({'WARNING'}, "Максимум %d фігур" % MAX_SHAPES)
            return {'CANCELLED'}
        o = bpy.data.objects.new("RV_" + self.kind.title(), _shape_mesh(self.kind))
        coll.objects.link(o)
        o.location = sc.cursor.location
        o.rv_shape = self.kind
        o.display_type = 'WIRE'
        o.hide_render = True
        _shapes_visible(sc)
        for x in context.view_layer.objects:
            x.select_set(False)
        if o.name in context.view_layer.objects:
            o.select_set(True)
            context.view_layer.objects.active = o
        _setup_shapes(sc, st)
        return {'FINISHED'}


class ROSTRV_OT_remove_shape(bpy.types.Operator):
    bl_idname = "rost_rv.remove_shape"
    bl_label = "Remove Shape"
    bl_options = {'REGISTER', 'UNDO'}
    name: StringProperty()

    def execute(self, context):
        o = bpy.data.objects.get(self.name)
        if o is not None:
            bpy.data.objects.remove(o, do_unlink=True)
        _setup_shapes(context.scene, context.scene.rost_rv)
        return {'FINISHED'}


class ROSTRV_OT_update_shapes(bpy.types.Operator):
    bl_idname = "rost_rv.update_shapes"
    bl_label = "Update Shapes"
    bl_description = "Перечитати колекцію RV_Shapes (якщо перетягнув туди свій об'єкт або змінив склад)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = _setup_shapes(context.scene, context.scene.rost_rv)
        self.report({'INFO'}, "Фігур: %d" % n)
        return {'FINISHED'}


class ROSTRV_OT_select_shapes(bpy.types.Operator):
    bl_idname = "rost_rv.select_shapes"
    bl_label = "Select Shapes"
    bl_description = "Виділити фігури маски"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = [o for o in _shape_objects(context.scene) if o.name in context.view_layer.objects]
        if not objs:
            self.report({'WARNING'}, "Немає фігур у цьому view layer")
            return {'CANCELLED'}
        for x in context.view_layer.objects:
            x.select_set(False)
        for o in objs:
            o.select_set(True)
        context.view_layer.objects.active = objs[0]
        return {'FINISHED'}


class ROSTRV_OT_wire_add(bpy.types.Operator):
    bl_idname = "rost_rv.wire_add"
    bl_label = "Wire: Add Selected"
    bl_description = ("Увімкнути wireframe для виділених деталей SHELL: їхня копія в SHELL_wire отримує "
                      "модифікатор Wireframe (лише рендер) і вмикається в alternative")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = context.scene.rost_rv
        tg = _wire_targets(context)
        if not tg:
            self.report({'WARNING'}, "Виділи деталі SHELL (після Build)")
            return {'CANCELLED'}
        polys = 0
        for c in tg:
            md = c.modifiers.get(WIRE_MOD)
            if md is None:
                md = c.modifiers.new(WIRE_MOD, 'WIREFRAME')
            md.thickness = st.wire_thickness
            md.show_viewport = False
            md.show_render = True
            c.hide_render = False
            polys += len(c.data.polygons)
        self.report({'INFO'}, "Wire увімкнено: %d деталей (~%d тис. полігонів до модифікатора)" % (len(tg), polys // 1000))
        return {'FINISHED'}


class ROSTRV_OT_wire_clear(bpy.types.Operator):
    bl_idname = "rost_rv.wire_clear"
    bl_label = "Wire: Remove"
    bl_description = "Вимкнути wireframe для виділених деталей (або для всіх)"
    bl_options = {'REGISTER', 'UNDO'}
    all: BoolProperty(default=False)

    def execute(self, context):
        wc = bpy.data.collections.get(COLL_WIRE)
        tg = list(wc.objects) if (self.all and wc) else _wire_targets(context)
        for c in tg:
            md = c.modifiers.get(WIRE_MOD)
            if md is not None:
                c.modifiers.remove(md)
            c.hide_render = True
        return {'FINISHED'}


def _shape_mesh(kind):
    import math as _m
    name = "RV_ShapeMesh_" + kind
    me = bpy.data.meshes.get(name)
    if me is not None:
        return me
    S = 24
    verts, faces = [], []
    if kind == 'BOX':
        verts = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    else:
        if kind == 'SPHERE':
            R = 12
            prof = [(_m.cos(-_m.pi / 2 + _m.pi * j / R), _m.sin(-_m.pi / 2 + _m.pi * j / R)) for j in range(R + 1)]
        elif kind == 'CYLINDER':
            prof = [(0.0, -1.0), (1.0, -1.0), (1.0, 1.0), (0.0, 1.0)]
        else:
            n = 6
            prof = [(_m.cos(-_m.pi / 2 + (_m.pi / 2) * j / n), -1.0 + _m.sin(-_m.pi / 2 + (_m.pi / 2) * j / n)) for j in range(n + 1)]
            prof += [(_m.cos((_m.pi / 2) * j / n), 1.0 + _m.sin((_m.pi / 2) * j / n)) for j in range(n + 1)]
        idx = []
        for r, z in prof:
            if r < 1e-6:
                verts.append((0.0, 0.0, z))
                idx.append((True, len(verts) - 1))
            else:
                base = len(verts)
                for k in range(S):
                    a = 2 * _m.pi * k / S
                    verts.append((r * _m.cos(a), r * _m.sin(a), z))
                idx.append((False, base))
        for (pa, ia), (pb, ib) in zip(idx, idx[1:]):
            if pa and pb:
                continue
            for k in range(S):
                k2 = (k + 1) % S
                if pa:
                    faces.append((ia, ib + k2, ib + k))
                elif pb:
                    faces.append((ia + k, ia + k2, ib))
                else:
                    faces.append((ia + k, ia + k2, ib + k2, ib + k))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    return me


# ------------------------------------------------------------------ panel
class ROSTRV_PT_panel(bpy.types.Panel):
    bl_idname = "ROSTRV_PT_panel"
    bl_label = "Reveal Passes"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rost Tools"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        L = self.layout
        sc = context.scene
        st = sc.rost_rv
        col = L.column(align=True)
        col.prop(st, "shell")
        col.prop(st, "keep")
        col.prop(st, "alt_material", text="Glass")
        col = L.column(align=True)
        col.scale_y = 1.5
        col.operator("rost_rv.build", icon="NODETREE")
        if st.empty:
            box = L.box()
            box.label(text="Лінія", icon="IPO_EASE_IN_OUT")
            for key, label in (("Line Border Size", "Width"), ("Transition Width", "Transition"), ("Border Noise", "Waviness")):
                if key in st.empty:
                    box.prop(st.empty, '["%s"]' % key, text=label)
            box.operator("rost_rv.select_gradient", icon="EMPTY_AXIS")
            box = L.box()
            box.label(text="Маска", icon="MOD_MASK")
            box.row().prop(st, "mask_source", expand=True)
            if st.mask_source == 'SHAPES':
                row = box.row(align=True)
                for it in SHAPE_ITEMS:
                    op = row.operator("rost_rv.add_shape", text="", icon=it[3])
                    op.kind = it[0]
                objs = _shape_objects(sc)
                for o in objs:
                    r = box.row(align=True)
                    r.prop(o, "name", text="")
                    r.prop(o, "rv_shape", text="")
                    x = r.operator("rost_rv.remove_shape", text="", icon="X")
                    x.name = o.name
                if not objs:
                    box.label(text="Додай фігуру кнопками вище", icon="INFO")
                if K_SOFT in st.empty:
                    box.prop(st.empty, '["%s"]' % K_SOFT, text="Softness")
                r = box.row(align=True)
                r.prop(st, "shape_invert", toggle=True)
                r.operator("rost_rv.update_shapes", text="Update", icon="FILE_REFRESH")
                r.operator("rost_rv.select_shapes", text="Select", icon="RESTRICT_SELECT_OFF")
            box = L.box()
            box.label(text="Wireframe", icon="MOD_WIREFRAME")
            wc = bpy.data.collections.get(COLL_WIRE)
            if wc is None:
                box.label(text="Колекція SHELL_wire з'явиться після Build")
            else:
                n_on = sum(1 for c in wc.objects if not c.hide_render)
                box.label(text="Увімкнено деталей: %d з %d" % (n_on, len(wc.objects)))
                box.prop(st, "wire_thickness")
                row = box.row(align=True)
                row.operator("rost_rv.wire_add", text="Add to Selected", icon="ADD")
                op = row.operator("rost_rv.wire_clear", text="Remove", icon="REMOVE")
                op.all = False
                op = box.operator("rost_rv.wire_clear", text="Remove All", icon="TRASH")
                op.all = True
        status = sc.get("rost_rv_status", "")
        if status:
            L.label(text=status, icon="INFO")
        row = L.row()
        row.prop(st, "show_adv", icon="TRIA_DOWN" if st.show_adv else "TRIA_RIGHT", emboss=False)
        if st.show_adv:
            box = L.box()
            box.prop_search(st, "original_layer", sc, "view_layers", text="Original")
            box.prop(st, "output_dir")
            row = box.row(align=True)
            row.operator("rost_rv.refresh_mask", icon="FILE_REFRESH")
            row.operator("rost_rv.reset_comp", icon="LOOP_BACK")
            box.operator("rost_rv.remove", icon="TRASH")
            box.label(text="Вихід: Compositor > RV_FileOut (multilayer EXR)")


CLASSES = (ROSTRV_Settings, ROSTRV_OT_build, ROSTRV_OT_reset_comp, ROSTRV_OT_refresh_mask,
           ROSTRV_OT_remove, ROSTRV_OT_select_gradient, ROSTRV_OT_add_shape, ROSTRV_OT_remove_shape,
           ROSTRV_OT_update_shapes, ROSTRV_OT_select_shapes, ROSTRV_OT_wire_add, ROSTRV_OT_wire_clear,
           ROSTRV_PT_panel)


def register():
    bpy.types.Object.rv_shape = EnumProperty(name="Shape", items=SHAPE_ITEMS, default='SPHERE')
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.rost_rv = PointerProperty(type=ROSTRV_Settings)


def unregister():
    try:
        del bpy.types.Object.rv_shape
    except Exception:
        pass
    del bpy.types.Scene.rost_rv
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
