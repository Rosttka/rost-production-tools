bl_info = {
    "name": "Rost Production Tools 4.0",
    "author": "Rost",
    "version": (4, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Rost Tools",
    "description": "HUD Callout (Add, Cutout, Presets), Proximity Alpha, Gradient Mask (multi-instance), CAD Auto-Rig, Material cleanup, Delta transforms, Rost Light Rig, STEP Pipeline",
    "category": "Object",
}

# v4.0: Rost Light Rig і STEP Pipeline (колишній EXM Pipeline Panel) — в одному аддоні.
#       STEP Pipeline — імпорт / матеріали / риг / перетесселяція; шаблон ролика прибрано.
#
# v3.8: HUD Measure — Angle: стабільна дуга при ручках (Use Points) без стрибка на 180°, кут 0–360°
#       (атан2 + площина з осі Z інструмента, GN_HUD_Angle у PT_NodeGroups_and_Mats.blend);
#       кнопка Outer (зовнішній кут 360° − θ) при створенні з виділення; текст Angle / Diameter /
#       Dimension: Text Rotation (X/Y/Z) і Mirror Text X/Y/Z (масштаб −1 по осі) навколо центру тексту.
#
# v3.7: HUD FUI — Tick Scale, Brackets, Counter, Bars/Sliders; Face Camera.
#
# v3.6: HUD Style — єдиний стиль (лінії/текст/гапи/стрілки наживо, шрифт і матеріали — Apply Style).
#
# v3.5: HUD Section — Add Section, Add to Selected (розріз у матеріалах + каркас), Remove, Refresh.
#
# v3.4: Add Handles (емпті для променів/виноски), заливки з візерунками, | = новий рядок у Label.
#
# v3.3: Angle from Selection (2 ребра / 3 вершини / 2 грані), GN_HUD_Angle.
#
# v3.2: HUD Measure — Diameter from Selection (Edit Mode, fit кола), GN_HUD_Diameter з PT_NodeGroups_and_Mats.
#
# v3.1: Ghost (X-Ray контури в дірці) + кнопка Update HUD from Library.
#
# v3.0.1: Hole Opacity — напівпрозора дірка (драйвер + поле в панелі).
#
# v3.0: блок HUD Callout — Add Callout з бібліотеки, Cutout/X-Ray без Boolean (шейдер HUD_Cutout
#       з драйверами від кіл), пресети Callout у JSON (MotionDesign_Lib\HUD\Callout_Presets).
#       Шлях до бібліотеки — у Preferences аддона.
#
# v2.9: блок Rigging -> CAD Auto-Rig (код з cad_autorig.py, тепер кнопкою в панелі).
#       Налаштування (кільця, довжини кісток, обертання) - у розгортному блоці.
#       Назви для UE (Armature / RigRoot / B_<меш>) зафіксовані в константах AR_*.
#
# v2.8: сумісність з Blender 5.x (і далі працює в 4.5).
# Blender 5 переробив композитор: замість scene.node_tree тепер окрема
# нод-група в scene.compositing_node_group, ноди Composite більше немає
# (результат іде в Group Output), Color Ramp у композиторі став спільною
# нодою ShaderNodeValToRGB, а режим Set Alpha став вхідним сокетом "Type".
# Змінено лише композиторну частину (блок "СУМІСНІСТЬ КОМПОЗИТОРА" нижче,
# setup_compositor і кінець FX_OT_SwitchMode).
# Також у v2.8:
# - Create New Tool прив'язує Texture Coordinate копії групи до нового Empty
#   (раніше лишався прив'язаним до схованого шаблонного Empty _TPL);
# - Clear Material Slots працює лише з виділеними мешами;
# - панель розділена на блоки Proximity Alpha і Gradient Mask;
# - прибрано Copy Bone Viewport Display (блок Rigging); код є у v2.7.

import bpy
import os
import json
from pathlib import Path

# ==============================================================================
# НАЛАШТУВАННЯ АСЕТІВ ТА НАЗВ
# ==============================================================================
LIBRARY_BLEND_PATH = r"G:\My Drive\WORK\Blender\VEffects\GN_Proximity_Mask.blend"
GN_GROUP_NAME = "GN_Proximity_Mask"
SHADER_GROUP_NAME = "M_Proximity_Alpha"

# ==============================================================================
# ФУНКЦІЇ ДЛЯ GRADIENT ANIMATED MASK (мульти-інстансна архітектура)
# ==============================================================================
# Ідея: з fx_data.blend один раз тягнемо "еталонний" шаблон (TEMPLATE),
# ховаємо його від сцени (fake_user, не лінкований в колекцію) і ніколи
# не чіпаємо напряму. Кожна кнопка "Create New Tool" робить ПОВНУ глибоку
# копію (група + всі вкладені групи + Empty) з унікальними іменами.
# Активний інстанс зберігається в scene.fx_active_group_name / fx_active_empty_name.

TEMPLATE_GROUP_NAME = "LineSurface switcher"
TEMPLATE_EMPTY_NAME = "Gradient_Direction"
TEMPLATE_SUFFIX = "_TPL"


def get_template_group_tree():
    return bpy.data.node_groups.get(TEMPLATE_GROUP_NAME + TEMPLATE_SUFFIX)

def get_template_empty():
    return bpy.data.objects.get(TEMPLATE_EMPTY_NAME + TEMPLATE_SUFFIX)

def get_active_group_tree(context):
    return bpy.data.node_groups.get(context.scene.fx_active_group_name)

def get_active_empty_obj(context):
    return bpy.data.objects.get(context.scene.fx_active_empty_name)


def load_template_assets(context):
    """Одноразово підтягує шаблон групи + Empty з fx_data.blend і ховає їх
    (перейменовує з суфіксом _TPL, не лінкує Empty в сцену). Якщо шаблон
    вже існує - нічого не робить."""
    if get_template_group_tree() and get_template_empty():
        return True

    addon_dir = os.path.dirname(__file__)
    filepath = os.path.join(addon_dir, "fx_data.blend")

    if not os.path.exists(filepath):
        return False

    with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
        if TEMPLATE_GROUP_NAME in data_from.node_groups and not get_template_group_tree():
            data_to.node_groups = [TEMPLATE_GROUP_NAME]
        if TEMPLATE_EMPTY_NAME in data_from.objects and not get_template_empty():
            data_to.objects = [TEMPLATE_EMPTY_NAME]

    tpl_group = bpy.data.node_groups.get(TEMPLATE_GROUP_NAME)
    tpl_empty = bpy.data.objects.get(TEMPLATE_EMPTY_NAME)

    if tpl_group and not tpl_group.name.endswith(TEMPLATE_SUFFIX):
        tpl_group.name = TEMPLATE_GROUP_NAME + TEMPLATE_SUFFIX
        tpl_group.use_fake_user = True

    if tpl_empty and not tpl_empty.name.endswith(TEMPLATE_SUFFIX):
        tpl_empty.name = TEMPLATE_EMPTY_NAME + TEMPLATE_SUFFIX
        tpl_empty.use_fake_user = True
        # Шаблонний Empty НЕ лінкуємо в сцену - він не для використання напряму

    return bool(get_template_group_tree() and get_template_empty())


def deep_copy_node_group(tree, memo):
    """Рекурсивно копіює node group і ВСІ вкладені (nested) node group'и,
    які використовуються всередині через GROUP-ноди. Без цього другий
    інстанс ділив би внутрішні підгрупи з першим і ламав би його."""
    if tree in memo:
        return memo[tree]
    new_tree = tree.copy()
    memo[tree] = new_tree
    for node in new_tree.nodes:
        if node.type == 'GROUP' and node.node_tree:
            node.node_tree = deep_copy_node_group(node.node_tree, memo)
    return new_tree


# Кеш потрібен, щоб Python не почистив рядки, які Blender використовує
# для динамічного EnumProperty (відомий баг API, якщо рядки не тримати живими)
_instance_enum_cache = []

def _get_instance_enum_items(self, context):
    global _instance_enum_cache
    items = []
    for obj in bpy.data.objects:
        if not obj.name.startswith(TEMPLATE_EMPTY_NAME):
            continue
        if obj.name.endswith(TEMPLATE_SUFFIX):
            continue
        group_name = obj.get("fx_linked_group", "")
        if group_name and group_name in bpy.data.node_groups:
            items.append((obj.name, obj.name, f"Група: {group_name}"))
    if not items:
        items.append(("NONE", "— немає активних інструментів —", ""))
    _instance_enum_cache = items
    return _instance_enum_cache


def _on_instance_picked(self, context):
    scene = context.scene
    empty = bpy.data.objects.get(scene.fx_instance_picker)
    if empty and "fx_linked_group" in empty:
        scene.fx_active_empty_name = empty.name
        scene.fx_active_group_name = empty["fx_linked_group"]


# ==============================================================================
# СУМІСНІСТЬ КОМПОЗИТОРА (Blender 4.x і 5.x)
# ==============================================================================
def _uses_nodes(idblock):
    """use_nodes у Blender 5 застарів (ноди завжди ввімкнені). Працює в обох."""
    if idblock is None or getattr(idblock, "node_tree", None) is None:
        return False
    return getattr(idblock, "use_nodes", True)


def get_compositor_tree(scene, create=False):
    """Повертає дерево композитора сцени.
    Blender 5.x: окрема нод-група в scene.compositing_node_group.
    Blender 4.x: scene.node_tree (лише якщо Use Nodes увімкнено).
    create=True створює/вмикає композитор, якщо його ще немає."""
    if hasattr(scene, "compositing_node_group"):
        tree = scene.compositing_node_group
        if tree is None and create:
            tree = bpy.data.node_groups.new(f"{scene.name} Compositing", 'CompositorNodeTree')
            tree.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
            out = tree.nodes.new('NodeGroupOutput')
            out.location = (900, 0)
            scene.compositing_node_group = tree
        return tree

    if create:
        scene.use_nodes = True
    return scene.node_tree if scene.use_nodes else None


def _compositor_output_sockets(tree):
    """Входи, куди йде фінальна картинка: Composite і Viewer (4.x)
    або активний Group Output і Viewer (5.x)."""
    sockets = []
    for n in tree.nodes:
        if n.type in ('COMPOSITE', 'VIEWER'):
            if n.inputs:
                sockets.append(n.inputs[0])
        elif n.type == 'GROUP_OUTPUT' and getattr(n, "is_active_output", True):
            sock = next((s for s in n.inputs if s.bl_idname != 'NodeSocketVirtual'), None)
            if sock:
                sockets.append(sock)
    return sockets


def _new_color_ramp(nodes):
    # 4.x: CompositorNodeValToRGB; 5.x: спільна нода ShaderNodeValToRGB
    for idname in ('CompositorNodeValToRGB', 'ShaderNodeValToRGB'):
        try:
            return nodes.new(idname)
        except RuntimeError:
            continue
    return None


def _set_alpha_replace(node):
    if hasattr(node, "mode"):           # 4.x
        node.mode = 'REPLACE_ALPHA'
    else:                               # 5.x: режим став сокетом-меню "Type"
        sock = node.inputs.get("Type")
        if sock:
            sock.default_value = 'Replace Alpha'


def setup_compositor(scene):
    tree = get_compositor_tree(scene, create=True)
    nodes = tree.nodes
    links = tree.links

    rl = next((n for n in nodes if n.type == 'R_LAYERS'), None)
    if not rl:
        rl = nodes.new('CompositorNodeRLayers')
        rl.name = "Render Layers"

    set_alpha = next((n for n in nodes if n.name == "Set Alpha" or n.label == "Set Alpha"), None)
    if not set_alpha:
        set_alpha = nodes.new('CompositorNodeSetAlpha')
        set_alpha.name = "Set Alpha"
        _set_alpha_replace(set_alpha)
        set_alpha.location = (600, -200)

    c_ramp = next((n for n in nodes if n.name == "Color Ramp" or n.label == "Color Ramp"), None)
    if not c_ramp:
        c_ramp = _new_color_ramp(nodes)
        c_ramp.name = "Color Ramp"
        c_ramp.location = (300, -200)

    links.new(rl.outputs[0], set_alpha.inputs['Image'])
    links.new(rl.outputs[0], c_ramp.inputs[0])
    links.new(c_ramp.outputs[0], set_alpha.inputs['Alpha'])
    return tree


def apply_scene_mode(scene, is_line):
    """Сценна частина Line/Surface Mode: композитор, світло, фон світу."""
    tree = get_compositor_tree(scene, create=False)
    if tree:
        setup_compositor(scene)
        nodes = tree.nodes
        links = tree.links

        if is_line:
            comp_src = next((n for n in nodes if n.name == "Set Alpha" or n.label == "Set Alpha"), None)
        else:
            comp_src = next((n for n in nodes if n.type == 'R_LAYERS'), None)

        if comp_src:
            for sock in _compositor_output_sockets(tree):
                links.new(comp_src.outputs[0], sock)

    for o in scene.objects:
        if o.type == 'LIGHT':
            o.hide_render = is_line
            o.hide_viewport = is_line

    if _uses_nodes(scene.world):
        bg = next((n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND'), None)
        if bg:
            if is_line:
                if not scene.fx_bg_saved:
                    scene.fx_original_bg_strength = bg.inputs[1].default_value
                    scene.fx_bg_saved = True
                bg.inputs[1].default_value = 0.0
            else:
                if scene.fx_bg_saved:
                    bg.inputs[1].default_value = scene.fx_original_bg_strength


# ==============================================================================
# ОПЕРАТОРИ GRADIENT ANIMATED MASK
# ==============================================================================
class FX_OT_CreateNewInstance(bpy.types.Operator):
    bl_idname = "fx.create_new_instance"
    bl_label = "Create New Tool"
    bl_description = ("Створює повністю незалежну копію групи (з усіма вкладеними "
                       "підгрупами) і новий Empty. Використовуй, коли потрібен другий, "
                       "незалежний ефект - щоб не зламати попередній")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not load_template_assets(context):
            self.report({'WARNING'}, "Файл fx_data.blend не знайдено.")
            return {'CANCELLED'}

        tpl_tree = get_template_group_tree()
        tpl_empty = get_template_empty()
        if not tpl_tree or not tpl_empty:
            self.report({'ERROR'}, "Не вдалося завантажити шаблон з fx_data.blend.")
            return {'CANCELLED'}

        memo = {}
        new_tree = deep_copy_node_group(tpl_tree, memo)
        new_tree.name = TEMPLATE_GROUP_NAME  # Blender сам додасть .001/.002/...

        new_empty = tpl_empty.copy()
        new_empty.name = TEMPLATE_EMPTY_NAME
        new_empty.animation_data_clear()
        for k in list(new_empty.keys()):
            del new_empty[k]
        context.scene.collection.objects.link(new_empty)

        # Прив'язуємо Empty до його групи явно (незалежно від того, чи
        # співпали числові суфікси в іменах)
        new_empty["fx_linked_group"] = new_tree.name

        # Texture Coordinate у копіях груп досі дивиться на схований шаблонний
        # Empty (_TPL). Перепризначаємо на новий Empty, щоб градієнт рухався за ним.
        for tree in memo.values():
            for node in tree.nodes:
                if node.type == 'TEX_COORD' and node.object == tpl_empty:
                    node.object = new_empty

        context.scene.fx_active_group_name = new_tree.name
        context.scene.fx_active_empty_name = new_empty.name
        context.scene.fx_instance_picker = new_empty.name

        self.report({'INFO'}, f"Новий інструмент створено: {new_tree.name} / {new_empty.name}")
        return {'FINISHED'}


class FX_OT_ApplyMask(bpy.types.Operator):
    bl_idname = "fx.apply_mask"
    bl_label = "Load & Apply Gradient Mask"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        group_tree = get_active_group_tree(context)
        empty_obj = get_active_empty_obj(context)

        if not group_tree or not empty_obj:
            self.report({'WARNING'}, "Немає активного інструменту. Спочатку натисни 'Create New Tool'.")
            return {'CANCELLED'}

        copied_mats = {}
        touched_trees = set()

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            for slot in obj.material_slots:
                orig_mat = slot.material
                if not _uses_nodes(orig_mat):
                    continue

                # Перевіряємо чи вже є маска на цьому матеріалі
                has_mask = any(n.type == 'GROUP' and getattr(n, "node_tree", None) == group_tree for n in orig_mat.node_tree.nodes)

                # Якщо маски немає, дублюємо матеріал
                if not has_mask:
                    if orig_mat.name not in copied_mats:
                        new_mat = orig_mat.copy()
                        copied_mats[orig_mat.name] = new_mat
                    slot.material = copied_mats[orig_mat.name]

                mat = slot.material
                nodes = mat.node_tree.nodes
                bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
                if not bsdf:
                    continue

                mask_node = next((n for n in nodes if n.type == 'GROUP' and n.node_tree == group_tree), None)
                if not mask_node:
                    mask_node = nodes.new('ShaderNodeGroup')
                    mask_node.node_tree = group_tree
                    mask_node.location = (bsdf.location.x - 250, bsdf.location.y - 200)

                if empty_obj:
                    touched_trees.add(mat.node_tree)
                    for i, socket in enumerate(mask_node.inputs):
                        if socket.is_linked or not hasattr(socket, "default_value"):
                            continue

                        p_name = socket.name
                        val = socket.default_value

                        if p_name not in empty_obj:
                            if type(val) in (float, int):
                                empty_obj[p_name] = float(val)
                            else:
                                try:
                                    empty_obj[p_name] = val[:]
                                    if len(val) in (3, 4) and "color" in p_name.lower():
                                        empty_obj.id_properties_ui(p_name).update(subtype='COLOR')
                                except:
                                    continue

                        try:
                            mask_node.inputs[i].driver_remove("default_value")
                        except:
                            pass

                        try:
                            if type(empty_obj[p_name]) in (float, int):
                                fcurve = mask_node.inputs[i].driver_add("default_value")
                                d = fcurve.driver
                                d.type = 'AVERAGE'
                                v = d.variables.new()
                                v.name = "var"
                                v.type = 'SINGLE_PROP'
                                v.targets[0].id_type = 'OBJECT'
                                v.targets[0].id = empty_obj
                                v.targets[0].data_path = f'["{p_name}"]'
                            else:
                                for j in range(len(empty_obj[p_name])):
                                    fcurve = mask_node.inputs[i].driver_add("default_value", j)
                                    d = fcurve.driver
                                    d.type = 'AVERAGE'
                                    v = d.variables.new()
                                    v.name = "var"
                                    v.type = 'SINGLE_PROP'
                                    v.targets[0].id_type = 'OBJECT'
                                    v.targets[0].id = empty_obj
                                    v.targets[0].data_path = f'["{p_name}"][{j}]'
                        except Exception as e:
                            print(f"Driver Error: {e}")

        # Нові властивості на Empty Blender сам не помічає: драйвер шукає їх
        # у старій обчисленій копії Empty, не знаходить, і Blender вимикає
        # його назавжди. Тому явно позначаємо Empty як змінений...
        empty_obj.update_tag()

        # ...і скидаємо позначку "зламаний" з драйверів, щоб повторне
        # натискання кнопки так само оживляло вже зламані драйвери.
        for tree in touched_trees:
            if tree.animation_data:
                for fc in tree.animation_data.drivers:
                    fc.driver.is_valid = True
            tree.update_tag()
        context.view_layer.update()

        setup_compositor(context.scene)
        return {'FINISHED'}

class FX_OT_SwitchMode(bpy.types.Operator):
    bl_idname = "fx.switch_mode"
    bl_label = "Switch Mode"
    mode: bpy.props.StringProperty()

    def execute(self, context):
        is_line = (self.mode == 'LINE')
        scene = context.scene

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            for slot in obj.material_slots:
                mat = slot.material
                if not _uses_nodes(mat):
                    continue

                nodes = mat.node_tree.nodes
                links = mat.node_tree.links
                bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
                mask_node = next((n for n in nodes if n.type == 'GROUP' and n.node_tree and "LineSurface switcher" in n.node_tree.name), None)

                if not bsdf or not mask_node:
                    continue

                if is_line:
                    # Запобіжник: Зберігаємо лінки лише якщо вони ще НЕ збережені
                    if "fx_saved_links" not in mat:
                        saved_links = []
                        for input_socket in bsdf.inputs:
                            if input_socket.is_linked:
                                for link in input_socket.links:
                                    if link.from_node != mask_node and "FX_Alpha_Add" not in link.from_node.name:
                                        saved_links.append({
                                            "from_node": link.from_node.name,
                                            "from_socket": link.from_socket.name,
                                            "to_socket": link.to_socket.name
                                        })
                        if saved_links:
                            mat["fx_saved_links"] = json.dumps(saved_links)

                    # Завжди видаляємо існуючі лінки до BSDF (крім маски) перед переходом в Line Mode
                    for input_socket in bsdf.inputs:
                        if input_socket.is_linked:
                            for link in reversed(input_socket.links):
                                if link.from_node != mask_node and "FX_Alpha_Add" not in link.from_node.name:
                                    links.remove(link)

                    # Запобіжник: Зберігаємо оригінальні кольори лише якщо вони ще НЕ збережені
                    if "Base Color" in bsdf.inputs:
                        if "fx_saved_base_color" not in mat:
                            mat["fx_saved_base_color"] = list(bsdf.inputs["Base Color"].default_value)
                        bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)

                    if "Emission Color" in bsdf.inputs:
                        if "fx_saved_em_color" not in mat:
                            mat["fx_saved_em_color"] = list(bsdf.inputs["Emission Color"].default_value)
                        bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)

                    add_node = next((n for n in nodes if n.name == "FX_Alpha_Add"), None)
                    if not add_node:
                        add_node = nodes.new('ShaderNodeMath')
                        add_node.name = "FX_Alpha_Add"
                        add_node.operation = 'ADD'
                        add_node.location = (mask_node.location.x + 200, mask_node.location.y - 100)

                    if "Surface" in mask_node.outputs and "Line" in mask_node.outputs:
                        links.new(mask_node.outputs["Surface"], add_node.inputs[0])
                        links.new(mask_node.outputs["Line"], add_node.inputs[1])
                        links.new(add_node.outputs[0], bsdf.inputs["Alpha"])

                    emission_socket = bsdf.inputs.get("Emission Strength", bsdf.inputs.get("Emission"))
                    if "Line" in mask_node.outputs and emission_socket:
                        links.new(mask_node.outputs["Line"], emission_socket)

                else: # SURFACE MODE
                    add_node = next((n for n in nodes if n.name == "FX_Alpha_Add"), None)
                    if add_node:
                        nodes.remove(add_node)

                    if "Surface" in mask_node.outputs and "Alpha" in bsdf.inputs:
                        links.new(mask_node.outputs["Surface"], bsdf.inputs["Alpha"])

                    emission_socket = bsdf.inputs.get("Emission Strength", bsdf.inputs.get("Emission"))
                    if emission_socket:
                        for link in list(emission_socket.links):
                            if link.from_node == mask_node:
                                links.remove(link)

                    # Надійне відновлення лінків
                    if "fx_saved_links" in mat:
                        try:
                            saved_links = json.loads(mat["fx_saved_links"])
                            for sl in saved_links:
                                from_n = nodes.get(sl["from_node"])
                                to_socket = bsdf.inputs.get(sl["to_socket"])
                                if from_n and to_socket:
                                    from_socket = from_n.outputs.get(sl["from_socket"])
                                    if from_socket:
                                        links.new(from_socket, to_socket)
                        except Exception as e:
                            print(f"Помилка відновлення лінків: {e}")
                        del mat["fx_saved_links"]

                    # Відновлення кольорів
                    if "fx_saved_base_color" in mat and "Base Color" in bsdf.inputs:
                        bsdf.inputs["Base Color"].default_value = mat["fx_saved_base_color"]
                        del mat["fx_saved_base_color"]

                    if "fx_saved_em_color" in mat and "Emission Color" in bsdf.inputs:
                        bsdf.inputs["Emission Color"].default_value = mat["fx_saved_em_color"]
                        del mat["fx_saved_em_color"]

        apply_scene_mode(scene, is_line)

        return {'FINISHED'}

class FX_OT_RemoveMask(bpy.types.Operator):
    bl_idname = "fx.remove_mask"
    bl_label = "Remove Mask"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.fx.switch_mode(mode='SURFACE')

        group_name = "LineSurface switcher"
        removed = False

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            for slot in obj.material_slots:
                mat = slot.material
                if not _uses_nodes(mat):
                    continue

                nodes = mat.node_tree.nodes
                mask_node = next((n for n in nodes if n.type == 'GROUP' and getattr(n, "node_tree", None) and group_name in n.node_tree.name), None)

                if mask_node:
                    nodes.remove(mask_node)
                    removed = True

                add_node = next((n for n in nodes if n.name == "FX_Alpha_Add"), None)
                if add_node:
                    nodes.remove(add_node)

        if removed:
            self.report({'INFO'}, "Ефект маски успішно очищено з виділених об'єктів.")
        else:
            self.report({'WARNING'}, "Маску не знайдено на виділених об'єктах.")

        return {'FINISHED'}


# ==============================================================================
# ОПЕРАТОРИ ІЗ ROST PRODUCTION TOOLS
# ==============================================================================
class OBJECT_OT_ApplyProximitySetup(bpy.types.Operator):
    bl_idname = "object.apply_proximity_setup"
    bl_label = "Apply Proximity Alpha Setup"
    bl_options = {'REGISTER', 'UNDO'}

    def _append_node_group(self, blend_path, group_name):
        if group_name in bpy.data.node_groups:
            return bpy.data.node_groups[group_name]

        if not Path(blend_path).exists():
            return None

        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            if group_name in data_from.node_groups:
                data_to.node_groups = [group_name]

        return bpy.data.node_groups.get(group_name)

    def execute(self, context):
        gn_tree = self._append_node_group(LIBRARY_BLEND_PATH, GN_GROUP_NAME)
        shader_group_tree = self._append_node_group(LIBRARY_BLEND_PATH, SHADER_GROUP_NAME)

        if not gn_tree and not shader_group_tree:
            self.report({'ERROR'}, f"Не знайдено нодові групи в сцені або бібліотеці: {LIBRARY_BLEND_PATH}")
            return {'CANCELLED'}

        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_meshes:
            self.report({'WARNING'}, "Не виділено жодного меш-об'єкта")
            return {'CANCELLED'}

        for obj in selected_meshes:
            if gn_tree:
                mod = next((m for m in obj.modifiers if m.type == 'NODES' and m.node_group == gn_tree), None)
                if not mod:
                    mod = obj.modifiers.new(name=GN_GROUP_NAME, type='NODES')
                    mod.node_group = gn_tree

            if shader_group_tree:
                for slot in obj.material_slots:
                    mat = slot.material
                    if not _uses_nodes(mat):
                        continue

                    nodes = mat.node_tree.nodes
                    links = mat.node_tree.links

                    group_node = next((n for n in nodes if n.type == 'GROUP' and n.node_tree == shader_group_tree), None)
                    if not group_node:
                        group_node = nodes.new(type='ShaderNodeGroup')
                        group_node.node_tree = shader_group_tree

                        principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
                        if principled:
                            group_node.location = (principled.location.x - 300, principled.location.y - 300)
                            alpha_in = principled.inputs.get("Alpha")
                            alpha_out = group_node.outputs.get("Alpha") or group_node.outputs[0]
                            if alpha_in and alpha_out:
                                links.new(alpha_out, alpha_in)

        self.report({'INFO'}, f"Proximity Alpha налаштовано для {len(selected_meshes)} об'єктів")
        return {'FINISHED'}

class OBJECT_OT_ClearVisibleMaterialSlots(bpy.types.Operator):
    bl_idname = "object.clear_visible_material_slots"
    bl_label = "Clear Material Slots"
    bl_options = {'REGISTER', 'UNDO'}

    bl_description = "Видаляє всі слоти матеріалів у виділених меш-об'єктах"

    def execute(self, context):
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not meshes:
            self.report({'WARNING'}, "Не виділено жодного меш-об'єкта")
            return {'CANCELLED'}

        for obj in meshes:
            obj.data.materials.clear()

        self.report({'INFO'}, f"Очищено матеріали у {len(meshes)} об'єктах")
        return {'FINISHED'}

class OBJECT_OT_ClearAndDelta(bpy.types.Operator):
    bl_idname = "object.clear_and_delta"
    bl_label = "Clear Parent & Delta Transform"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        bpy.ops.object.transforms_to_deltas(mode='ALL')
        self.report({'INFO'}, "Parent очищено, дельта-трансформи застосовано")
        return {'FINISHED'}


# ==============================================================================
# CAD AUTO-RIG (перенесено з cad_autorig.py)
# ==============================================================================
# Що робить (коротко):
#   кістка B_<меш> на кожен виділений меш у його півоті, ієрархія кісток =
#   ієрархія об'єктів, кріплення (STK-) -> кістка-кільце, Empty -> допоміжні
#   кістки (не деформують), NoBone / no_bone -> деталь їде з кісткою батька.
#   Повторний запуск безпечний: назви кісток не змінюються, анімація лишається.
# Назви нижче - контракт з Unreal (не міняти без потреби):
AR_RIG_NAME     = "Armature"   # так UE не додає зайву кореневу кістку
AR_ROOT_NAME    = "RigRoot"    # не "root": UE не розрізняє регістр
AR_BONE_PREFIX  = "B_"         # ім'я кістки != ім'я меша (для UE)
AR_RING_PROP    = "ring"       # Custom Property: 1 = примусово кільце, 0 = примусово звичайна
AR_NOBONE_COL   = "NoBone"
AR_NOBONE_PROP  = "no_bone"
AR_PROP         = "cad_rig_parent"
AR_WGT_NAME     = "WGT_CadRing"
AR_WGT_COL      = "WGT"
AR_RING_COLOR   = 'THEME09'
AR_HELPER_COLOR = 'THEME04'


class CADRIG_Settings(bpy.types.PropertyGroup):
    show_settings: bpy.props.BoolProperty(name="Налаштування", default=False)
    round_patterns: bpy.props.StringProperty(
        name="Кріплення (назва містить)", default="STK-",
        description="Через кому. Меші з таким текстом у назві отримують кістку-кільце")
    round_auto_axis: bpy.props.BoolProperty(
        name="Авто-вісь кілець", default=True,
        description="Вісь кільця = вимір, що відрізняється від двох інших (діаметра)")
    round_tolerance: bpy.props.FloatProperty(
        name="Допуск круглості", default=0.2, min=0.0, max=1.0, subtype='FACTOR',
        description="Кільце, лише якщо два виміри збігаються з такою точністю (шестигранник ~15%)")
    head_at: bpy.props.EnumProperty(
        name="Голова кістки",
        items=[('ORIGIN', "Півот об'єкта", ""), ('BBOX_CENTER', "Центр габариту", "")],
        default='ORIGIN')
    len_factor: bpy.props.FloatProperty(
        name="Довжина × габарит", default=0.2, min=0.01, max=2.0,
        description="Довжина звичайної кістки = найбільший габарит × це")
    min_len: bpy.props.FloatProperty(name="Мін. довжина", default=1.5, min=0.001)
    max_len: bpy.props.FloatProperty(name="Макс. довжина", default=12.0, min=0.001)
    rot_mode: bpy.props.EnumProperty(
        name="Обертання",
        items=[('XYZ', "Euler XYZ", "Зручно в Graph Editor"), ('QUATERNION', "Quaternion", "")],
        default='XYZ')


def _ar_has_bone(obj):
    """Пустушки завжди дають кістку; меші - якщо не позначені як NoBone."""
    if obj.type == 'EMPTY':
        return True
    if AR_NOBONE_PROP in obj and obj[AR_NOBONE_PROP]:
        return False
    return not any(c.name == AR_NOBONE_COL for c in obj.users_collection)


def _ar_round_axis(d):
    """Вісь, перпендикулярно до якої два виміри найближчі, і їхня різниця."""
    best, axis = None, 2
    for k in range(3):
        a, b = [j for j in range(3) if j != k]
        diff = abs(d[a] - d[b]) / max(d[a], d[b], 1e-6)
        if best is None or diff < best:
            best, axis = diff, k
    return axis, best


def _ar_is_round(obj, s):
    if obj.type != 'MESH':
        return False
    if AR_RING_PROP in obj:                    # ручний перемикач має пріоритет
        return bool(obj[AR_RING_PROP])
    patterns = [p.strip() for p in s.round_patterns.split(",") if p.strip()]
    if not any(p in obj.name for p in patterns):
        return False
    _, diff = _ar_round_axis(obj.dimensions)
    return diff <= s.round_tolerance


def _ar_get_widget(scene):
    """Кільце в площині XZ кістки (перпендикулярно до її напрямку)."""
    obj = bpy.data.objects.get(AR_WGT_NAME)
    if obj:
        return obj
    import math
    n = 32
    verts = [(math.cos(2 * math.pi * i / n), 0.0, math.sin(2 * math.pi * i / n)) for i in range(n)]
    edges = [(i, (i + 1) % n) for i in range(n)]
    me = bpy.data.meshes.new(AR_WGT_NAME)
    me.from_pydata(verts, edges, [])
    obj = bpy.data.objects.new(AR_WGT_NAME, me)
    col = bpy.data.collections.get(AR_WGT_COL)
    if col is None:
        col = bpy.data.collections.new(AR_WGT_COL)
        scene.collection.children.link(col)
    col.objects.link(obj)
    col.hide_viewport = True
    col.hide_render = True
    return obj


def _ar_bone_frame(obj, mw, s):
    """Повертає (матриця кістки, довжина, радіус кільця або None)."""
    from mathutils import Matrix, Vector
    rot = mw.to_3x3().normalized()
    axes = [rot.col[0].copy(), rot.col[1].copy(), rot.col[2].copy()]
    d = obj.dimensions
    axis = 2            # за замовчуванням: локальна Z об'єкта
    radius = None

    if _ar_is_round(obj, s):
        if s.round_auto_axis:
            axis, _ = _ar_round_axis(d)
        a, b = [j for j in range(3) if j != axis]
        radius = max(d[a], d[b]) * 0.5

    y = axes[axis].normalized()
    x = axes[(axis + 1) % 3].normalized()
    z = x.cross(y).normalized()
    x = y.cross(z).normalized()

    m = Matrix((x, y, z)).transposed().to_4x4()

    if s.head_at == 'BBOX_CENTER' and obj.type == 'MESH':
        c = sum((Vector(v) for v in obj.bound_box), Vector()) / 8.0
        m.translation = mw @ c
    else:
        m.translation = mw.translation.copy()

    if obj.type == 'EMPTY':
        # допоміжна кістка: довжина = видимий розмір пустушки
        length = max(s.min_len, obj.empty_display_size * max(mw.to_scale()) * 1.5)
    elif radius is None:
        length = max(d) * s.len_factor
    else:
        length = d[axis]
    length = min(s.max_len, max(s.min_len, length))
    return m, length, radius


def cad_autorig_run(context, s):
    """Будує / перебудовує риг. Повертає текст звіту або кидає RuntimeError."""
    from mathutils import Matrix
    ctx = context
    if ctx.object and ctx.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    scene = ctx.scene
    # Меші -> деформуючі кістки; Empty -> допоміжні (не деформуючі) кістки
    objs = [o for o in scene.objects
            if o.type in ('MESH', 'EMPTY') and o.name != AR_WGT_NAME
            and (o.select_get() or AR_PROP in o)]
    meshes = [o for o in objs if o.type == 'MESH']
    if not meshes:
        raise RuntimeError("Виділіть меші для ригу (Object Mode).")

    # 1. Ієрархія: актуальний батько (меш або пустушка) має пріоритет над збереженим
    for o in objs:
        p = o.parent
        if p and p.type in ('MESH', 'EMPTY'):
            o[AR_PROP] = p.name
        elif AR_PROP not in o:
            o[AR_PROP] = ""

    # 2. Single User для інстансів
    for o in meshes:
        if o.data.users > 1:
            o.data = o.data.copy()

    # 3. Позиції спокою
    mws = {o.name: o.matrix_world.copy() for o in objs}

    by_name = {o.name: o for o in objs}
    boned = [o for o in objs if _ar_has_bone(o)]

    def owner(name):
        """Іде вгору по ієрархії до першого об'єкта з кісткою. '' = Root."""
        seen = set()
        while name and name in by_name and name not in seen:
            seen.add(name)
            ob = by_name[name]
            if _ar_has_bone(ob):
                return name
            name = ob[AR_PROP]
        return ""

    # 4. Арматура
    rig = bpy.data.objects.get(AR_RIG_NAME)
    if rig is None:
        arm = bpy.data.armatures.new(AR_RIG_NAME)
        rig = bpy.data.objects.new(AR_RIG_NAME, arm)
        scene.collection.objects.link(rig)
    rig.matrix_world = Matrix.Identity(4)
    rig.show_in_front = True
    rig.data.display_type = 'OCTAHEDRAL'

    wgt = _ar_get_widget(scene)

    bpy.ops.object.select_all(action='DESELECT')
    rig.hide_set(False)
    rig.select_set(True)
    ctx.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')

    eb = rig.data.edit_bones
    for b in list(eb):
        eb.remove(b)

    root = eb.new(AR_ROOT_NAME)
    root.head = (0, 0, 0)
    root.tail = (0, 0, 10)
    root.use_deform = False
    root_name = root.name

    bone_name = {}
    radius_of = {}
    for o in boned:
        m, length, radius = _ar_bone_frame(o, mws[o.name], s)
        b = eb.new(AR_BONE_PREFIX + o.name)
        b.head = (0, 0, 0)
        b.tail = (0, 1, 0)
        b.matrix = m
        b.length = length
        b.use_deform = (o.type == 'MESH')
        bone_name[o.name] = b.name
        radius_of[o.name] = radius

    for o in boned:
        b = eb[bone_name[o.name]]
        p = owner(o[AR_PROP])
        b.parent = eb[bone_name[p]] if p else root
        b.use_connect = False

    # Деталь без кістки і без батька з кісткою -> їде з Root
    if any(not _ar_has_bone(o) and not owner(o[AR_PROP]) for o in meshes):
        root.use_deform = True

    bpy.ops.object.mode_set(mode='OBJECT')

    # 5. Відображення кісток
    for o in boned:
        bn = bone_name[o.name]
        pb = rig.pose.bones[bn]
        bone = rig.data.bones[bn]
        pb.rotation_mode = s.rot_mode
        r = radius_of[o.name]
        if o.type == 'EMPTY':
            pb.custom_shape = None
            if hasattr(bone, "color"):
                bone.color.palette = AR_HELPER_COLOR
        elif r is not None:
            pb.custom_shape = wgt
            pb.use_custom_shape_bone_size = True
            sc = max(r * 1.15, s.min_len * 0.5) / bone.length
            pb.custom_shape_scale_xyz = (sc, sc, sc)
            if hasattr(bone, "color"):
                bone.color.palette = AR_RING_COLOR
        else:
            pb.custom_shape = None

    # 6. Вертексні групи + модифікатор
    for o in meshes:
        if _ar_has_bone(o):
            bn = bone_name[o.name]
        else:
            t = owner(o[AR_PROP])
            bn = bone_name[t] if t else root_name
        o.vertex_groups.clear()
        vg = o.vertex_groups.new(name=bn)
        n = len(o.data.vertices)
        if n:
            vg.add(list(range(n)), 1.0, 'REPLACE')
        for md in [md for md in o.modifiers if md.type == 'ARMATURE']:
            o.modifiers.remove(md)
        md = o.modifiers.new(AR_RIG_NAME, 'ARMATURE')
        md.object = rig

    # 7. Перепарентування під арматуру без зсуву
    for o in objs:
        o.parent = rig
        o.parent_type = 'OBJECT'
        o.matrix_parent_inverse = rig.matrix_world.inverted()
    for o in objs:
        o.matrix_world = mws[o.name]

    # Пустушки після ригу лише "пам'ятають" місце кістки: ховаємо
    for o in objs:
        if o.type == 'EMPTY':
            o.hide_set(True)

    rig.select_set(True)
    ctx.view_layer.objects.active = rig

    rings = sum(1 for v in radius_of.values() if v is not None)
    helpers = sum(1 for o in objs if o.type == 'EMPTY')
    parts = sum(1 for o in meshes if _ar_has_bone(o))
    nobone = len(meshes) - parts
    return (f"CAD Auto-Rig: {parts} кісток деталей ({rings} кілець), "
            f"{helpers} допоміжних, {nobone} без кістки -> '{AR_RIG_NAME}'")


class OBJECT_OT_CadAutoRig(bpy.types.Operator):
    bl_idname = "object.cad_autorig"
    bl_label = "CAD Auto-Rig"
    bl_description = ("Кістка на кожен виділений меш у його півоті, ієрархія = ієрархія об'єктів. "
                      "Повторний запуск безпечний: меші, що вже в ригу, підхоплюються самі")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            msg = cad_autorig_run(context, context.scene.cadrig_settings)
        except RuntimeError as e:
            self.report({'WARNING'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# ==============================================================================
# ПАНЕЛЬ У VIEWPORT (N-PANEL)
# ==============================================================================
GUIDE_URL = "https://rosttka.github.io/rost-production-tools/guide.html"


class OBJECT_PT_RossToolsPanel(bpy.types.Panel):
    bl_options = {'DEFAULT_CLOSED'}
    bl_label = "Production Tools"
    bl_idname = "OBJECT_PT_ross_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Rost Tools'

    def draw_header(self, context):
        op = self.layout.operator("wm.url_open", text="", icon='HELP', emboss=False)
        op.url = GUIDE_URL

    def draw(self, context):
        layout = self.layout

        # Блок Proximity Alpha
        box = layout.box()
        box.label(text="Proximity Alpha", icon='MOD_MASK')
        box.operator("object.apply_proximity_setup", icon='NODETREE')

        # Блок Gradient Mask
        box = layout.box()
        box.label(text="Gradient Mask", icon='NODE_TEXTURE')
        box.operator("fx.create_new_instance", icon='DUPLICATE')

        items = _get_instance_enum_items(None, context)
        if not (len(items) == 1 and items[0][0] == "NONE"):
            box.prop(context.scene, "fx_instance_picker", text="Активний")

        active_group = get_active_group_tree(context)
        if active_group:
            box.label(text=f"Група: {active_group.name}", icon='NODETREE')
        else:
            box.label(text="Немає активного інструменту", icon='ERROR')

        box.separator()

        row_apply = box.row(align=True)
        row_apply.operator("fx.apply_mask", icon='NODETREE')
        row_apply.operator("fx.remove_mask", text="", icon='TRASH')

        row_mode = box.row(align=True)
        row_mode.operator("fx.switch_mode", text="Surface Mode").mode = 'SURFACE'
        row_mode.operator("fx.switch_mode", text="Line Mode").mode = 'LINE'

        empty_obj = get_active_empty_obj(context)
        group_tree = get_active_group_tree(context)

        if empty_obj and group_tree:
            valid_keys = []
            if hasattr(group_tree, "interface"):
                valid_keys = [item.name for item in group_tree.interface.items_tree]
            elif hasattr(group_tree, "inputs"):
                valid_keys = [inp.name for inp in group_tree.inputs]

            box.separator()
            has_props = False
            for key in empty_obj.keys():
                if key in valid_keys:
                    box.prop(empty_obj, f'["{key}"]', text=key)
                    has_props = True

            if not has_props:
                box.label(text="Press 'Load & Apply Mask' to init")

        # Блок Rigging
        box = layout.box()
        box.label(text="Rigging", icon='ARMATURE_DATA')
        box.operator("object.cad_autorig", icon='BONE_DATA')
        s = context.scene.cadrig_settings
        box.prop(s, "show_settings", emboss=False,
                 icon='TRIA_DOWN' if s.show_settings else 'TRIA_RIGHT')
        if s.show_settings:
            col = box.column(align=True)
            col.prop(s, "round_patterns", text="Кріплення")
            col.prop(s, "round_auto_axis")
            col.prop(s, "round_tolerance")
            col.separator()
            col.prop(s, "head_at", text="Голова")
            col.prop(s, "len_factor")
            row = col.row(align=True)
            row.prop(s, "min_len", text="Мін")
            row.prop(s, "max_len", text="Макс")
            col.prop(s, "rot_mode", text="")

        # Блок оптимізації та сцени
        box = layout.box()
        box.label(text="Scene Utilities", icon='SCENE_DATA')
        box.operator("object.clear_visible_material_slots", icon='TRASH')
        box.operator("object.clear_and_delta", icon='FILE_REFRESH')


# ==============================================================================
# HUD CALLOUT (v3.0)
# ==============================================================================
import os, re, json, time

HUD_LIB_DEFAULT = r"G:\My Drive\WORK\Blender\MotionDesign_Lib\HUD\HUD_Elements.blend"
HUD_TEMPLATE_COLL = "HUD_Callout"
HUD_TEMPLATE_LOCAL = "_HUD_Callout_Template"
HUD_RING = "GN_HUD_RingLayer"
HUD_LABEL = "GN_HUD_CalloutLabel"
HUD_SETTINGS = "GN_HUD_CalloutSettings"
HUD_SETTINGS_MOD = "Callout Settings"
HUD_CUTOUT_SHADER = "HUD_Cutout"
HUD_GROUPS = (HUD_RING, HUD_LABEL, HUD_SETTINGS)
HUD_FRAME_KEYS = {"Start Frame", "Out Frame"}
HUD_ID_COLLS = {
    "NodeSocketMaterial": "materials", "NodeSocketObject": "objects",
    "NodeSocketCollection": "collections", "NodeSocketFont": "fonts",
    "NodeSocketImage": "images",
}


def _hud_base(name):
    return re.sub(r"\.\d{3}$", "", name)


def hud_lib_path(context):
    try:
        p = context.preferences.addons[__name__].preferences.hud_library
        if p:
            return bpy.path.abspath(p)
    except Exception:
        pass
    return HUD_LIB_DEFAULT


def hud_presets_dir(context):
    return os.path.join(os.path.dirname(hud_lib_path(context)), "Callout_Presets")


def _hud_inputs(g):
    return [it for it in g.interface.items_tree
            if it.item_type == 'SOCKET' and it.in_out == 'INPUT'
            and it.socket_type != 'NodeSocketGeometry']


def _hud_ids(g):
    return {it.name: it.identifier for it in _hud_inputs(g)}


def _hud_sock(md, ident):
    if not ident:
        return None
    return getattr(md.properties.inputs, ident, None)


def _hud_get(md, ident):
    s = _hud_sock(md, ident)
    return s.value if s is not None else None


def _hud_set(md, ident, v):
    s = _hud_sock(md, ident)
    if s is None:
        return
    try:
        s.value = v
    except Exception as e:
        print("[HUD] не вдалося записати", md.name, ident, e)


def hud_kind(md):
    if md.type != 'NODES' or not md.node_group:
        return None
    b = _hud_base(md.node_group.name)
    return b if b in HUD_GROUPS else None


def hud_is_callout(obj):
    return (obj is not None and obj.type == 'MESH'
            and any(hud_kind(m) for m in obj.modifiers))


def hud_settings_mod(obj):
    for m in obj.modifiers:
        if hud_kind(m) == HUD_SETTINGS:
            return m
    return None


def hud_ring_mods(obj):
    return [m for m in obj.modifiers if hud_kind(m) == HUD_RING and m.show_viewport]


def hud_get_callout(context):
    ob = context.active_object
    if hud_is_callout(ob):
        return ob
    if ob is not None and ob.type == 'EMPTY':
        for o in context.scene.objects:
            if not hud_is_callout(o):
                continue
            for m in o.modifiers:
                if hud_kind(m) != HUD_LABEL:
                    continue
                for it in _hud_inputs(m.node_group):
                    if it.socket_type == 'NodeSocketObject' and _hud_get(m, it.identifier) == ob:
                        return o
    c = getattr(context.scene, "hud_callout", None)
    return c if hud_is_callout(c) else None


# ------------------------------------------------------------------ drivers --
def _hud_var(d, name, target, path):
    v = d.variables.new()
    v.name = name
    v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'
    v.targets[0].id = target
    v.targets[0].data_path = path


def _hud_driver(owner, prop, target, path, index=-1):
    fc = owner.driver_add(prop, index) if index >= 0 else owner.driver_add(prop)
    d = fc.driver
    for v in list(d.variables):
        d.variables.remove(v)
    d.type = 'AVERAGE'
    _hud_var(d, "v", target, path)
    return fc


def hud_setup_align(obj, cam):
    sm = hud_settings_mod(obj)
    if sm is None:
        return
    sm.name = HUD_SETTINGS_MOD
    ids = _hud_ids(sm.node_group)
    if "Align to Camera" not in ids:
        return
    c = obj.constraints.get("Align to Camera") or obj.constraints.new('TRACK_TO')
    c.name = "Align to Camera"
    c.track_axis = 'TRACK_Z'
    c.up_axis = 'UP_Y'
    c.target = cam
    try:
        c.driver_remove("influence")
    except Exception:
        pass
    _hud_driver(c, "influence", obj,
                f'modifiers["{HUD_SETTINGS_MOD}"].properties.inputs.{ids["Align to Camera"]}.value')


# ---------------------------------------------------------------- library --
def _hud_iface_sig(g):
    try:
        return [(i.name, getattr(i, "socket_type", "")) for i in g.interface.items_tree if i.item_type == 'SOCKET']
    except Exception:
        return None


def _hud_dedupe(before):
    """Злиття дублікатів після довантаження з бібліотеки.
    Звичайні дані: лишається локальна копія.
    HUD-нод-групи: якщо набір параметрів відрізняється (нова версія в бібліотеці) — виграє бібліотечна,
    значення модифікаторів переносяться за назвою параметра."""
    hud_names = set(HUD_GROUPS) | {HUD_CUTOUT_SHADER}
    for cname in ("node_groups", "materials", "fonts", "images"):
        coll = getattr(bpy.data, cname)
        for idb in list(coll):
            if idb.name in before[cname]:
                continue
            b = _hud_base(idb.name)
            if b == idb.name or b not in before[cname]:
                continue
            old = coll[b]
            if cname == "node_groups" and b in hud_names and _hud_iface_sig(old) != _hud_iface_sig(idb):
                saved = []
                for o in bpy.data.objects:
                    for m in o.modifiers:
                        if m.type == 'NODES' and m.node_group == old:
                            vals = {}
                            for it in _hud_inputs(old):
                                try:
                                    vals[it.name] = _hud_get(m, it.identifier)
                                except Exception:
                                    pass
                            saved.append((o, m.name, vals))
                old.user_remap(idb)
                coll.remove(old)
                idb.name = b
                ids = {it.name: it.identifier for it in _hud_inputs(idb)}
                for o, mn, vals in saved:
                    m = o.modifiers.get(mn)
                    if not m:
                        continue
                    for k, v in vals.items():
                        if k in ids:
                            try:
                                _hud_set(m, ids[k], v)
                            except Exception:
                                pass
                continue
            idb.user_remap(old)
            coll.remove(idb)



def _hud_load(context, collections=(), node_groups=()):
    lib = hud_lib_path(context)
    if not os.path.exists(lib):
        return None, f"Не знайдено бібліотеку: {lib}"
    names = ("node_groups", "materials", "fonts", "images", "objects")
    before = {n: set(x.name for x in getattr(bpy.data, n)) for n in names}
    with bpy.data.libraries.load(lib, link=False) as (src, dst):
        dst.collections = [c for c in collections if c in src.collections]
        dst.node_groups = [g for g in node_groups if g in src.node_groups]
    _hud_dedupe(before)
    return (dst, before), None


def _hud_is_lib_file(context):
    a = os.path.normcase(os.path.abspath(hud_lib_path(context)))
    b = os.path.normcase(os.path.abspath(bpy.data.filepath)) if bpy.data.filepath else ""
    return a == b


def hud_ensure_template(context):
    if _hud_is_lib_file(context):
        t = bpy.data.collections.get(HUD_TEMPLATE_COLL)
        return (t, None) if t else (None, "У файлі бібліотеки немає колекції HUD_Callout")
    t = bpy.data.collections.get(HUD_TEMPLATE_LOCAL)
    if t is not None and len(t.objects):
        return t, None
    res, err = _hud_load(context, collections=(HUD_TEMPLATE_COLL,))
    if err:
        return None, err
    dst, before = res
    if not dst.collections or dst.collections[0] is None:
        return None, "У бібліотеці немає колекції HUD_Callout"
    t = dst.collections[0]
    keep = set(t.all_objects)
    for o in list(bpy.data.objects):          # напр. тестова камера з бібліотеки
        if o.name not in before["objects"] and o not in keep:
            bpy.data.objects.remove(o)
    t.name = HUD_TEMPLATE_LOCAL
    t.use_fake_user = True
    return t, None


def hud_ensure_groups(context):
    # Завжди звіряємо з бібліотекою: відсутні — додаються, застарілі (інший набір параметрів) — оновлюються в _hud_dedupe
    if _hud_is_lib_file(context):
        return None
    _, err = _hud_load(context, node_groups=HUD_GROUPS + (HUD_CUTOUT_SHADER,))
    return err



def hud_new_index():
    names = {o.name for o in bpy.data.objects}
    i = 1
    while f"Callout_{i:02d}" in names:
        i += 1
    return i


def hud_instantiate(context, template):
    objs = list(template.objects)
    src_callout = next((o for o in objs if hud_is_callout(o)), None)
    if src_callout is None:
        return None
    n = hud_new_index()
    coll = bpy.data.collections.new(f"HUD_Callout_{n:02d}")
    context.collection.children.link(coll)
    mp = {}
    for o in objs:
        c = o.copy()
        mp[o] = c
        coll.objects.link(c)
    cur = context.scene.cursor.location.copy()
    for o, c in mp.items():
        c.name = f"Callout_{n:02d}" if o == src_callout else f"Callout_{n:02d}_Label"
        if o.parent in mp:
            c.parent = mp[o.parent]
        else:
            c.location = cur + (o.location - src_callout.location)
        for m in c.modifiers:
            if m.type == 'NODES' and m.node_group:
                for it in _hud_inputs(m.node_group):
                    if it.socket_type == 'NodeSocketObject':
                        v = _hud_get(m, it.identifier)
                        if v in mp:
                            _hud_set(m, it.identifier, mp[v])
        for con in c.constraints:
            if getattr(con, "target", None) in mp:
                con.target = mp[con.target]
        if c.animation_data:
            for fc in c.animation_data.drivers:
                for v in fc.driver.variables:
                    for t in v.targets:
                        if t.id in mp:
                            t.id = mp[t.id]
    new = mp[src_callout]
    hud_setup_align(new, context.scene.camera)
    return new


# ----------------------------------------------------------------- cutout --
def hud_cutout_nodes(mat, callout=None):
    res = []
    nt = getattr(mat, "node_tree", None) if mat else None
    if nt is None:
        return res
    for n in nt.nodes:
        if n.type == 'GROUP' and n.node_tree and _hud_base(n.node_tree.name) == HUD_CUTOUT_SHADER:
            src = None
            inp = n.inputs.get("Callout Coords")
            if inp is not None and inp.is_linked:
                fn = inp.links[0].from_node
                if fn.type == 'TEX_COORD':
                    src = fn.object
            if callout is None or src == callout:
                res.append((n, src))
    return res


def _hud_clear_node_drivers(nt, node):
    ad = nt.animation_data
    if ad is None:
        return
    pref = f'nodes["{node.name}"]'
    for fc in list(ad.drivers):
        if fc.data_path.startswith(pref):
            ad.drivers.remove(fc)


def _hud_outer_ring(obj):
    best, br = None, -1.0
    for m in hud_ring_mods(obj):
        ids = _hud_ids(m.node_group)
        r = (_hud_get(m, ids.get("Radius (mm)")) or 0.0) + 0.5 * (_hud_get(m, ids.get("Width (mm)")) or 0.0)
        if r > br:
            best, br = m, r
    return best


def hud_build_cutout_drivers(mat, node, callout):
    nt = mat.node_tree
    _hud_clear_node_drivers(nt, node)
    sm = hud_settings_mod(callout)
    if sm is not None:
        ids = _hud_ids(sm.node_group)
        base = f'modifiers["{sm.name}"].properties.inputs.'
        for nm in ("Enable", "Margin (mm)", "Depth (mm)", "Softness (mm)", "Hole Opacity",
                   "Ghost", "Ghost Strength", "Ghost Edge", "Ghost Fill", "Rim Width (mm)", "Rim Strength"):
            if nm in ids and nm in node.inputs:
                _hud_driver(node.inputs[nm], "default_value", callout, base + ids[nm] + ".value")
        if "Rim Color" in ids and "Rim Color" in node.inputs:
            for i in range(3):
                _hud_driver(node.inputs["Rim Color"], "default_value", callout,
                            base + ids["Rim Color"] + f".value[{i}]", i)
    rings = hud_ring_mods(callout)
    if rings:
        fc = node.inputs["Radius (mm)"].driver_add("default_value")
        d = fc.driver
        d.type = 'SCRIPTED'
        expr = None
        for k, m in enumerate(rings):
            ids = _hud_ids(m.node_group)
            p = f'modifiers["{m.name}"].properties.inputs.'
            _hud_var(d, f"R{k}", callout, p + ids["Radius (mm)"] + ".value")
            _hud_var(d, f"W{k}", callout, p + ids["Width (mm)"] + ".value")
            t = f"(R{k}+W{k}*0.5)"
            expr = t if expr is None else f"max({expr}, {t})"
        d.expression = expr
        om = _hud_outer_ring(callout)
        if om is not None:
            ids = _hud_ids(om.node_group)
            p = f'modifiers["{om.name}"].properties.inputs.'
            fc = node.inputs["Reveal"].driver_add("default_value")
            d = fc.driver
            d.type = 'SCRIPTED'
            for vn, sn in (("S", "Start Frame"), ("D", "Duration"), ("U", "Use Out"),
                           ("O", "Out Frame"), ("E", "Out Duration")):
                _hud_var(d, vn, callout, p + ids[sn] + ".value")
            d.expression = ("min(max(min((frame-S)/max(D,1),1),0), "
                            "1-U*max(min((frame-O)/max(E,1),1),0))")


def hud_cutout_insert(mat, callout, group):
    if hud_cutout_nodes(mat, callout):
        return False
    nt = mat.node_tree
    outs = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL']
    if not outs:
        return False
    out = next((n for n in outs if n.is_active_output), outs[0])
    surf = out.inputs["Surface"]
    if not surf.is_linked:
        return False
    src = surf.links[0].from_socket
    x, y = out.location
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = callout
    tc.label = f"Callout: {callout.name}"
    tc.location = (x - 220, y - 320)
    tc.hide = True
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = group
    g.name = f"HUD_Cutout · {callout.name}"
    g.label = g.name
    g.location = (x, y)
    out.location = (x + 280, y)
    nt.links.new(src, g.inputs["Shader"])
    nt.links.new(tc.outputs["Object"], g.inputs["Callout Coords"])
    nt.links.new(g.outputs[0], surf)
    hud_build_cutout_drivers(mat, g, callout)
    return True


def hud_cutout_remove(mat, callout=None):
    cnt = 0
    for g, _src in hud_cutout_nodes(mat, callout):
        nt = mat.node_tree
        inl = g.inputs["Shader"].links[0].from_socket if g.inputs["Shader"].is_linked else None
        outs = [l.to_socket for l in g.outputs[0].links]
        tc = g.inputs["Callout Coords"].links[0].from_node if g.inputs["Callout Coords"].is_linked else None
        _hud_clear_node_drivers(nt, g)
        nt.nodes.remove(g)
        if tc is not None and not any(o.is_linked for o in tc.outputs):
            nt.nodes.remove(tc)
        if inl is not None:
            for t in outs:
                nt.links.new(inl, t)
        cnt += 1
    return cnt


def hud_refresh_callout(callout):
    n = 0
    for mat in bpy.data.materials:
        for g, _src in hud_cutout_nodes(mat, callout):
            hud_build_cutout_drivers(mat, g, callout)
            n += 1
    return n


def _hud_target_mats(context):
    mats = []
    for o in context.selected_objects:
        if hud_is_callout(o) or o.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META', 'CURVES'}:
            continue
        for s in o.material_slots:
            m = s.material
            if m and m.node_tree and not m.name.startswith("HUD_") and m not in mats:
                mats.append(m)
    return mats


# ---------------------------------------------------------------- presets --
_hud_preset_cache = []


def _hud_preset_items(self, context):
    global _hud_preset_cache
    d = hud_presets_dir(context)
    items = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d), key=str.lower):
            if f.lower().endswith(".json"):
                n = f[:-5]
                items.append((n, n, ""))
    if not items:
        items = [("NONE", "— немає пресетів —", "")]
    _hud_preset_cache = items
    return items


def _hud_ser(v):
    if isinstance(v, bpy.types.ID):
        return {"__id__": type(v).__name__, "name": v.name}
    if isinstance(v, (str, bool, int, float)) or v is None:
        return v
    try:
        return [float(x) for x in v]
    except Exception:
        return str(v)


def hud_preset_data(callout, name):
    data = {"version": 1, "name": name, "blender": bpy.app.version_string, "modifiers": []}
    for m in callout.modifiers:
        k = hud_kind(m)
        if not k:
            continue
        e = {"name": m.name, "group": k, "show_viewport": m.show_viewport,
             "show_render": m.show_render, "inputs": {}}
        for it in _hud_inputs(m.node_group):
            s = _hud_sock(m, it.identifier)
            if s is None:
                continue
            e["inputs"][it.name] = {"type": it.socket_type, "value": _hud_ser(s.value)}
        data["modifiers"].append(e)
    return data


def _hud_start(values):
    v = [x for x in values if isinstance(x, (int, float))]
    return min(v) if v else None


def hud_apply_preset(context, callout, data, keep_start, keep_text):
    old_label, old_text, cur_starts = None, None, []
    for m in callout.modifiers:
        k = hud_kind(m)
        if not k:
            continue
        ids = _hud_ids(m.node_group)
        if "Start Frame" in ids:
            cur_starts.append(_hud_get(m, ids["Start Frame"]))
        if k == HUD_LABEL:
            old_label = _hud_get(m, ids.get("Label"))
            old_text = _hud_get(m, ids.get("Text"))
    pre_starts = [e["inputs"].get("Start Frame", {}).get("value") for e in data["modifiers"]]
    a, b = _hud_start(cur_starts), _hud_start(pre_starts)
    delta = (a - b) if (keep_start and a is not None and b is not None) else 0.0

    for m in [m for m in callout.modifiers if hud_kind(m)]:
        callout.modifiers.remove(m)

    for e in data["modifiers"]:
        g = bpy.data.node_groups.get(e["group"])
        if g is None:
            continue
        m = callout.modifiers.new(e["name"], 'NODES')
        m.node_group = g
        m.show_viewport = e.get("show_viewport", True)
        m.show_render = e.get("show_render", True)
        ids = _hud_ids(g)
        for nm, info in e["inputs"].items():
            if nm not in ids:
                continue
            v = info["value"]
            if isinstance(v, dict) and "__id__" in v:
                if nm == "Label":
                    continue
                coll = getattr(bpy.data, HUD_ID_COLLS.get(info["type"], ""), None)
                v = coll.get(v["name"]) if coll is not None else None
                if v is None:
                    continue
            if nm == "Text" and keep_text:
                continue
            if nm in HUD_FRAME_KEYS and isinstance(v, (int, float)):
                v = v + delta
            _hud_set(m, ids[nm], v)
        if e["group"] == HUD_LABEL:
            if old_label is not None and "Label" in ids:
                _hud_set(m, ids["Label"], old_label)
            if keep_text and old_text is not None and "Text" in ids:
                _hud_set(m, ids["Text"], old_text)

    con = callout.constraints.get("Align to Camera")
    cam = con.target if (con and con.target) else context.scene.camera
    hud_setup_align(callout, cam)
    hud_refresh_callout(callout)


# -------------------------------------------------------------- operators --
class HUD_OT_add_callout(bpy.types.Operator):
    """Додати HUD Callout з бібліотеки в 3D-курсор"""
    bl_idname = "hud.add_callout"
    bl_label = "Add Callout"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        t, err = hud_ensure_template(context)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        hud_ensure_groups(context)
        new = hud_instantiate(context, t)
        if new is None:
            self.report({'ERROR'}, "У шаблоні немає Callout")
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        new.select_set(True)
        context.view_layer.objects.active = new
        context.scene.hud_callout = new
        if context.scene.camera is None:
            self.report({'WARNING'}, f"{new.name} додано. У сцені немає камери — Align to Camera без цілі")
        else:
            self.report({'INFO'}, f"{new.name} додано")
        return {'FINISHED'}


class HUD_OT_cutout_add(bpy.types.Operator):
    """Прорізати матеріали виділених об'єктів активним Callout (без Boolean)"""
    bl_idname = "hud.cutout_add"
    bl_label = "Add to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hud_get_callout(context) is not None

    def execute(self, context):
        co = hud_get_callout(context)
        err = hud_ensure_groups(context)
        grp = bpy.data.node_groups.get(HUD_CUTOUT_SHADER)
        if grp is None:
            self.report({'ERROR'}, err or "Немає шейдерної групи HUD_Cutout")
            return {'CANCELLED'}
        mats = _hud_target_mats(context)
        if not mats:
            self.report({'WARNING'}, "Виділи деталі (і Callout активним останнім)")
            return {'CANCELLED'}
        done = sum(1 for m in mats if hud_cutout_insert(m, co, grp))
        skipped = len(mats) - done
        msg = f"{co.name}: прорізано матеріалів — {done}"
        if skipped:
            msg += f", пропущено {skipped} (вже є або немає Surface)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class HUD_OT_cutout_remove(bpy.types.Operator):
    """Прибрати прорізання цього Callout з виділених деталей (нічого не виділено — з усіх матеріалів)"""
    bl_idname = "hud.cutout_remove"
    bl_label = "Remove Cutout"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hud_get_callout(context) is not None

    def execute(self, context):
        co = hud_get_callout(context)
        mats = _hud_target_mats(context) or list(bpy.data.materials)
        n = sum(hud_cutout_remove(m, co) for m in mats)
        self.report({'INFO'}, f"{co.name}: прибрано з матеріалів — {n}")
        return {'FINISHED'}


class HUD_OT_cutout_refresh(bpy.types.Operator):
    """Оновити зв'язки дірки з кільцями (після додавання/видалення кіл)"""
    bl_idname = "hud.cutout_refresh"
    bl_label = "Refresh Cutout"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        co = hud_get_callout(context)
        cos = [co] if co else [o for o in bpy.data.objects if hud_is_callout(o)]
        n = sum(hud_refresh_callout(c) for c in cos)
        self.report({'INFO'}, f"Оновлено дірок: {n}")
        return {'FINISHED'}


class HUD_OT_preset_save(bpy.types.Operator):
    """Зберегти стек кіл, підпису й налаштувань активного Callout як пресет"""
    bl_idname = "hud.preset_save"
    bl_label = "Save Preset"

    preset_name: bpy.props.StringProperty(name="Назва", default="My Callout")

    @classmethod
    def poll(cls, context):
        return hud_get_callout(context) is not None

    def invoke(self, context, event):
        cur = context.scene.hud_preset
        if cur and cur != "NONE":
            self.preset_name = cur
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = re.sub(r'[\\/:*?"<>|]', "_", self.preset_name).strip()
        if not name:
            return {'CANCELLED'}
        d = hud_presets_dir(context)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name + ".json")
        existed = os.path.exists(p)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(hud_preset_data(hud_get_callout(context), name), f, ensure_ascii=False, indent=2)
        context.scene.hud_preset = name
        self.report({'INFO'}, ("Перезаписано: " if existed else "Збережено: ") + name)
        return {'FINISHED'}


class HUD_OT_preset_apply(bpy.types.Operator):
    """Застосувати пресет до виділених Callout-ів (позиція, поворот і підпис лишаються)"""
    bl_idname = "hud.preset_apply"
    bl_label = "Apply"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.hud_preset not in ("", "NONE") and hud_get_callout(context) is not None

    def execute(self, context):
        sc = context.scene
        p = os.path.join(hud_presets_dir(context), sc.hud_preset + ".json")
        if not os.path.exists(p):
            self.report({'ERROR'}, "Файл пресету не знайдено")
            return {'CANCELLED'}
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        hud_ensure_groups(context)
        targets = [o for o in context.selected_objects if hud_is_callout(o)] or [hud_get_callout(context)]
        for c in targets:
            hud_apply_preset(context, c, data, sc.hud_keep_start, sc.hud_keep_text)
        self.report({'INFO'}, f"Пресет «{sc.hud_preset}» → {len(targets)} Callout")
        return {'FINISHED'}


class HUD_OT_preset_delete(bpy.types.Operator):
    """Прибрати пресет (файл переноситься в Callout_Presets/_deleted)"""
    bl_idname = "hud.preset_delete"
    bl_label = "Delete Preset"

    @classmethod
    def poll(cls, context):
        return context.scene.hud_preset not in ("", "NONE")

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        d = hud_presets_dir(context)
        name = context.scene.hud_preset
        src = os.path.join(d, name + ".json")
        if os.path.exists(src):
            dd = os.path.join(d, "_deleted")
            os.makedirs(dd, exist_ok=True)
            os.replace(src, os.path.join(dd, f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.json"))
        self.report({'INFO'}, f"Пресет «{name}» перенесено в _deleted")
        return {'FINISHED'}


class HUD_OT_preset_folder(bpy.types.Operator):
    """Відкрити папку пресетів"""
    bl_idname = "hud.preset_folder"
    bl_label = "Open Presets Folder"

    def execute(self, context):
        d = hud_presets_dir(context)
        os.makedirs(d, exist_ok=True)
        try:
            os.startfile(d)
        except Exception:
            bpy.ops.wm.path_open(filepath=d)
        return {'FINISHED'}


def hud_update_from_library(context):
    """Підтягнути свіжі GN_HUD_* і HUD_Cutout з бібліотеки у поточний файл."""
    targets = [g for g in HUD_GROUPS + (HUD_CUTOUT_SHADER,)]
    lib = hud_lib_path(context)
    if not os.path.exists(lib):
        return None, f"Не знайдено бібліотеку: {lib}"
    names = ("node_groups", "materials", "fonts", "images", "objects")
    before = {n: set(x.name for x in getattr(bpy.data, n)) for n in names}
    with bpy.data.libraries.load(lib, link=False) as (src, dst):
        dst.node_groups = [g for g in targets if g in src.node_groups]
    loaded = [g for g in dst.node_groups if g is not None]
    replaced = []
    for new in loaded:
        base = _hud_base(new.name)
        old = bpy.data.node_groups.get(base)
        if old is not None and old != new and base in before["node_groups"]:
            old_ids = {it.identifier for it in _hud_inputs(old)}
            mods = [m for o in bpy.data.objects for m in o.modifiers
                    if m.type == 'NODES' and m.node_group == old]
            old.user_remap(new)
            for m in mods:                      # нові входи → значення за замовчуванням
                for it in _hud_inputs(new):
                    if it.identifier not in old_ids and hasattr(it, "default_value"):
                        try:
                            _hud_set(m, it.identifier, it.default_value)
                        except Exception:
                            pass
            fake = old.use_fake_user
            bpy.data.node_groups.remove(old)
            new.name = base
            new.use_fake_user = fake
            replaced.append(base)
        else:
            new.name = base
    # інше, що приїхало разом (матеріали, шрифти, внутрішні групи) — на локальні копії
    keep = {g.name for g in loaded}
    for cname in ("node_groups", "materials", "fonts", "images"):
        coll = getattr(bpy.data, cname)
        for idb in list(coll):
            if idb.name in before[cname] or idb.name in keep:
                continue
            b = _hud_base(idb.name)
            if b != idb.name and b in before[cname]:
                idb.user_remap(coll[b])
                coll.remove(idb)
    # шаблон для Add Callout — перечитати при наступному додаванні
    t = bpy.data.collections.get(HUD_TEMPLATE_LOCAL)
    if t is not None:
        for o in list(t.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(t)
    cos = [o for o in bpy.data.objects if hud_is_callout(o)]
    nd = sum(hud_refresh_callout(c) for c in cos)
    for c in cos:
        con = c.constraints.get("Align to Camera")
        hud_setup_align(c, con.target if (con and con.target) else context.scene.camera)
    return (replaced, len(cos), nd), None


class HUD_OT_update_from_library(bpy.types.Operator):
    """Оновити нод-групи HUD Callout і HUD_Cutout у цьому файлі з бібліотеки (значення на Callout-ах зберігаються)"""
    bl_idname = "hud.update_from_library"
    bl_label = "Update HUD from Library"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return not _hud_is_lib_file(context)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        res, err = hud_update_from_library(context)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        replaced, nco, nd = res
        replaced += _hud_replace_groups(hud_measure_lib(context), MEASURE_GROUPS)
        replaced += _hud_replace_groups(sec_lib_path(context), SEC_GROUPS)
        if os.path.exists(vc_lib_path(context)):
            replaced += _hud_replace_groups(vc_lib_path(context), VC_GROUPS)
        replaced += _hud_replace_groups(fui_lib_path(context), FUI_GROUPS)
        for _s in [o for o in bpy.data.objects if sec_is_section(o)]:
            sec_refresh(_s)
        for _s in [o for o in bpy.data.objects if vc_is_cutter(o)]:
            vc_refresh(_s)
        for _tn in (DIA_LOCAL, "_Angle_Tool_Template"):
            t = bpy.data.collections.get(_tn)
            if t is not None:
                for o in list(t.objects):
                    bpy.data.objects.remove(o)
                bpy.data.collections.remove(t)
        self.report({'INFO'}, f"Оновлено груп: {len(replaced)} · Callout-ів: {nco} · дірок: {nd}")
        return {'FINISHED'}


class OBJECT_PT_RossHUDPanel(bpy.types.Panel):
    bl_options = {'DEFAULT_CLOSED'}
    bl_label = "HUD Callout"
    bl_idname = "OBJECT_PT_ross_hud"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Rost Tools'

    def draw_header(self, context):
        self.layout.label(icon='MESH_CIRCLE')

    def draw(self, context):
        L = self.layout
        sc = context.scene
        co = hud_get_callout(context)

        r = L.row()
        r.scale_y = 1.5
        r.operator("hud.add_callout", icon='ADD')

        box = L.box()
        if co is not None and co == context.active_object:
            box.label(text=co.name, icon='RESTRICT_SELECT_OFF')
        else:
            box.prop(sc, "hud_callout", text="")
        if co is not None:
            sm = hud_settings_mod(co)
            if sm is not None:
                ids = _hud_ids(sm.node_group)
                col = box.column(align=True)
                for nm, txt in (("Align to Camera", "Align to Camera"), ("Enable", "Cutout"),
                                ("Margin (mm)", "Margin mm"), ("Depth (mm)", "Depth mm"),
                                ("Hole Opacity", "Hole Opacity"), ("Ghost", "Ghost")):
                    s = _hud_sock(sm, ids.get(nm))
                    if s is not None:
                        col.prop(s, "value", text=txt)

        b = L.box()
        b.label(text="Cutout / X-Ray", icon='MOD_BOOLEAN')
        r = b.row(align=True)
        r.scale_y = 1.2
        r.operator("hud.cutout_add", icon='SELECT_SUBTRACT')
        r.operator("hud.cutout_remove", text="", icon='X')
        r.operator("hud.cutout_refresh", text="", icon='FILE_REFRESH')
        if co is not None:
            n = sum(len(hud_cutout_nodes(m, co)) for m in bpy.data.materials)
            b.label(text=f"Прорізано матеріалів: {n}", icon='MATERIAL')
        else:
            b.label(text="Зроби Callout активним", icon='INFO')

        b = L.box()
        b.label(text="Presets", icon='PRESET')
        r = b.row(align=True)
        r.prop(sc, "hud_preset", text="")
        r.operator("hud.preset_folder", text="", icon='FILE_FOLDER')
        r.operator("hud.preset_delete", text="", icon='TRASH')
        r = b.row(align=True)
        r.scale_y = 1.2
        r.operator("hud.preset_apply", icon='IMPORT')
        r.operator("hud.preset_save", text="Save", icon='EXPORT')
        r = b.row(align=True)
        r.prop(sc, "hud_keep_start", toggle=True)
        r.prop(sc, "hud_keep_text", toggle=True)

        L.separator()
        L.operator("hud.update_from_library", icon='FILE_REFRESH')


# ==============================================================================
# HUD MEASURE (v3.2) — Diameter
# ==============================================================================
import bmesh
from mathutils import Vector, Matrix

HUD_MEASURE_LIB = "PT_NodeGroups_and_Mats.blend"
DIA_GROUP = "GN_HUD_Diameter"
DIA_COLL = "Diameter_Tool"
DIA_LOCAL = "_Diameter_Tool_Template"
MEASURE_GROUPS = (DIA_GROUP, "GN_HUD_Angle")


def hud_measure_lib(context):
    return os.path.join(os.path.dirname(os.path.dirname(hud_lib_path(context))), HUD_MEASURE_LIB)


def _same_file(a):
    if not bpy.data.filepath:
        return False
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(bpy.data.filepath))


def _tool_template(libfile, coll_name, local_name):
    if _same_file(libfile):
        t = bpy.data.collections.get(coll_name)
        return (t, None) if t else (None, f"У файлі немає {coll_name}")
    t = bpy.data.collections.get(local_name)
    if t is not None and len(t.objects):
        return t, None
    if not os.path.exists(libfile):
        return None, f"Не знайдено бібліотеку: {libfile}"
    names = ("node_groups", "materials", "fonts", "images", "objects")
    before = {n: set(x.name for x in getattr(bpy.data, n)) for n in names}
    with bpy.data.libraries.load(libfile, link=False) as (src, dst):
        dst.collections = [coll_name] if coll_name in src.collections else []
    if not dst.collections or dst.collections[0] is None:
        return None, f"У бібліотеці немає {coll_name}"
    _hud_dedupe(before)
    t = dst.collections[0]
    keep = set(t.all_objects)
    for o in list(bpy.data.objects):
        if o.name not in before["objects"] and o not in keep:
            bpy.data.objects.remove(o)
    t.name = local_name
    t.use_fake_user = True
    if t.asset_data is not None:
        t.asset_clear()
    return t, None


def _hud_replace_groups(libfile, names_wanted):
    """Замінити наявні у файлі групи свіжими з libfile (значення модифікаторів зберігаються)."""
    want = [n for n in names_wanted if n in bpy.data.node_groups]
    if not want or _same_file(libfile) or not os.path.exists(libfile):
        return []
    names = ("node_groups", "materials", "fonts", "images", "objects")
    before = {n: set(x.name for x in getattr(bpy.data, n)) for n in names}
    with bpy.data.libraries.load(libfile, link=False) as (src, dst):
        dst.node_groups = [n for n in want if n in src.node_groups]
    loaded = [g for g in dst.node_groups if g is not None]
    replaced = []
    for new in loaded:
        base = _hud_base(new.name)
        old = bpy.data.node_groups.get(base)
        if old is not None and old != new:
            old_ids = {it.identifier for it in _hud_inputs(old)}
            mods = [m for o in bpy.data.objects for m in o.modifiers if m.type == 'NODES' and m.node_group == old]
            old.user_remap(new)
            for m in mods:
                for it in _hud_inputs(new):
                    if it.identifier not in old_ids and hasattr(it, "default_value"):
                        try:
                            _hud_set(m, it.identifier, it.default_value)
                        except Exception:
                            pass
            bpy.data.node_groups.remove(old)
            replaced.append(base)
        new.name = base
    keep = {g.name for g in loaded}
    for cname in ("node_groups", "materials", "fonts", "images"):
        coll = getattr(bpy.data, cname)
        for idb in list(coll):
            if idb.name in before[cname] or idb.name in keep:
                continue
            b = _hud_base(idb.name)
            if b != idb.name and b in before[cname]:
                idb.user_remap(coll[b])
                coll.remove(idb)
    return replaced


def _fit_circle(points):
    """Площина (PCA) + коло найменших квадратів у площині. Працює й для дуг."""
    import numpy as np
    P = np.array([tuple(p) for p in points], dtype=float)
    c0 = P.mean(axis=0)
    w, vecs = np.linalg.eigh(np.cov((P - c0).T))
    nrm = Vector(vecs[:, 0]).normalized()
    ax = Vector(vecs[:, 2]).normalized()
    ay = nrm.cross(ax).normalized()
    Q = P - c0
    x = Q @ np.array(ax)
    y = Q @ np.array(ay)
    A = np.column_stack((2 * x, 2 * y, np.ones_like(x)))
    b = x * x + y * y
    (a, bb, cc), *_ = np.linalg.lstsq(A, b, rcond=None)
    r = float(np.sqrt(max(cc + a * a + bb * bb, 0.0)))
    center = Vector(c0) + ax * float(a) + ay * float(bb)
    return center, nrm, r


def _measure_collection(context):
    c = bpy.data.collections.get("HUD_Measure")
    if c is None:
        c = bpy.data.collections.new("HUD_Measure")
        context.scene.collection.children.link(c)
    elif c.name not in context.scene.collection.children and not any(
            c in ch.children_recursive for ch in [context.scene.collection]):
        context.scene.collection.children.link(c)
    return c


def _tool_mod(obj, group):
    for m in obj.modifiers:
        if m.type == 'NODES' and m.node_group and _hud_base(m.node_group.name) == group:
            return m
    return None


def _orient_matrix(center, nrm, cam):
    z = nrm.normalized()
    if cam is not None and (cam.matrix_world.translation - center).dot(z) < 0:
        z = -z
    up = Vector((0, 0, 1))
    x = up.cross(z)
    if x.length < 1e-4:
        x = Vector((1, 0, 0))
    x.normalize()
    y = z.cross(x).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = center + z * 0.0005   # 0.5 мм над поверхнею, щоб не тонуло
    return m


class HUD_OT_add_diameter(bpy.types.Operator):
    """Edit Mode: виділи кромку отвору або торець труби → HUD-розмір діаметра в центрі"""
    bl_idname = "hud.add_diameter"
    bl_label = "Diameter from Selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        pts = []
        objs = list(getattr(context, 'objects_in_mode', None) or []) or ([context.edit_object] if context.edit_object else [])
        for o in objs:
            if o.type != 'MESH':
                continue
            bm = bmesh.from_edit_mesh(o.data)
            mw = o.matrix_world
            pts += [mw @ v.co for v in bm.verts if v.select]
        if len(pts) < 3:
            self.report({'WARNING'}, "Виділи кромку отвору (щонайменше 3 вершини)")
            return {'CANCELLED'}
        center, nrm, r = _fit_circle(pts)
        bpy.ops.object.mode_set(mode='OBJECT')
        t, err = _tool_template(hud_measure_lib(context), DIA_COLL, DIA_LOCAL)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        src = next((o for o in t.objects if _tool_mod(o, DIA_GROUP)), None)
        if src is None:
            self.report({'ERROR'}, "У шаблоні немає об'єкта з GN_HUD_Diameter")
            return {'CANCELLED'}
        i = 1
        while f"Diameter_{i:02d}" in bpy.data.objects:
            i += 1
        new = src.copy()
        new.name = f"Diameter_{i:02d}"
        _measure_collection(context).objects.link(new)
        new.matrix_world = _orient_matrix(center, nrm, context.scene.camera)
        md = _tool_mod(new, DIA_GROUP)
        ids = _hud_ids(md.node_group)
        sl = context.scene.unit_settings.scale_length or 1.0
        d_mm = 2.0 * r * sl * 1000.0
        _hud_set(md, ids["Diameter (mm)"], d_mm)
        if "Start Frame" in ids:
            _hud_set(md, ids["Start Frame"], float(context.scene.frame_current))
        new.update_tag()
        for o in context.selected_objects:
            o.select_set(False)
        new.select_set(True)
        context.view_layer.objects.active = new
        self.report({'INFO'}, f"{new.name}: Ø {d_mm:.2f} mm")
        return {'FINISHED'}


ANG_GROUP = "GN_HUD_Angle"
ANG_COLL = "Angle_Tool"
ANG_LOCAL = "_Angle_Tool_Template"


def _edit_selection(context):
    objs = list(getattr(context, 'objects_in_mode', None) or []) or ([context.edit_object] if context.edit_object else [])
    V_, E_, F_, H_ = [], [], [], []
    for o in objs:
        if o.type != 'MESH':
            continue
        bm = bmesh.from_edit_mesh(o.data)
        mw = o.matrix_world
        vmap = {}
        for v in bm.verts:
            if v.select:
                vmap[v] = mw @ v.co
        V_ += list(vmap.values())
        for e in bm.edges:
            if e.select:
                E_.append((mw @ e.verts[0].co, mw @ e.verts[1].co))
        for f in bm.faces:
            if f.select:
                nrm = (mw.to_3x3().inverted_safe().transposed() @ f.normal).normalized()
                F_.append((mw @ f.calc_center_median(), [mw @ v.co for v in f.verts], nrm))
        H_ += [mw @ h.co for h in bm.select_history if isinstance(h, bmesh.types.BMVert)]
    return V_, E_, F_, H_


def _same(a, b):
    return (a - b).length < 1e-7


def _angle_from_selection(context):
    """→ (apex, A, B) у світових координатах, A/B — вектори від вершини (довжина = довжина променя)."""
    V_, E_, F_, H_ = _edit_selection(context)
    if len(F_) == 2:
        (c1, v1, n1), (c2, v2, n2) = F_
        shared = [p for p in v1 if any(_same(p, q) for q in v2)]
        if len(shared) >= 2:
            d = (shared[1] - shared[0]).normalized()
            apex = (shared[0] + shared[1]) * 0.5
            def perp(c):
                w = c - apex
                return w - d * w.dot(d)
            A, B = perp(c1), perp(c2)
            if n1.dot(B) < 0:      # опукле ребро: сектор між гранями — в матеріалі → малюємо протилежний (той самий кут) зовні
                return apex, -A, -B, "грані (зовні)"
            return apex, A, B, "грані"
        return None, None, None, "Дві грані мають мати спільне ребро"
    if len(H_) == 3:
        a, apex, b = H_
        return apex, a - apex, b - apex, "3 вершини"
    if len(E_) == 2:
        (a0, a1), (b0, b1) = E_
        for pa, oa in ((a0, a1), (a1, a0)):
            for pb, ob in ((b0, b1), (b1, b0)):
                if _same(pa, pb):
                    return pa, oa - pa, ob - pb, "2 ребра"
        d1 = (a1 - a0); d2 = (b1 - b0)
        n = d1.cross(d2)
        if n.length < 1e-9:
            return None, None, None, "Ребра паралельні"
        import mathutils.geometry as mg
        r = mg.intersect_line_line(a0, a1, b0, b1)
        if r is None:
            return None, None, None, "Не вдалося знайти перетин"
        apex = (r[0] + r[1]) * 0.5
        m1 = (a0 + a1) * 0.5; m2 = (b0 + b1) * 0.5
        A = d1 if (m1 - apex).dot(d1) > 0 else -d1
        B = d2 if (m2 - apex).dot(d2) > 0 else -d2
        A = A.normalized() * max((m1 - apex).length, d1.length * 0.5)
        B = B.normalized() * max((m2 - apex).length, d2.length * 0.5)
        return apex, A, B, "2 ребра (перетин)"
    if len(V_) == 3:
        return None, None, None, "Для 3 вершин клацай їх по черзі: край → вершина кута → край"
    return None, None, None, "Виділи 2 ребра, 3 вершини (по черзі) або 2 суміжні грані"


class HUD_OT_add_angle(bpy.types.Operator):
    """Edit Mode: 2 ребра / 3 вершини по черзі / 2 суміжні грані → HUD-розмір кута"""
    bl_idname = "hud.add_angle"
    bl_label = "Angle from Selection"
    bl_options = {'REGISTER', 'UNDO'}

    outer: bpy.props.BoolProperty(
        name="Outer (360° − θ)", default=False,
        description="Зовнішній кут: дуга з іншого боку (більше 180°)")

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        apex, A, B, how = _angle_from_selection(context)
        if apex is None:
            self.report({'WARNING'}, how)
            return {'CANCELLED'}
        if A.length < 1e-9 or B.length < 1e-9:
            self.report({'WARNING'}, "Нульова довжина променя")
            return {'CANCELLED'}
        cam = context.scene.camera
        z = A.cross(B)
        if z.length < 1e-9:
            z = A.orthogonal()
        z.normalize()
        if cam is not None and (cam.matrix_world.translation - apex).dot(z) < 0:
            A, B = B, A
            z = -z
        theta = A.angle(B)
        if self.outer:
            # зовнішній кут: дуга від B проти годинникової до A (A стоїть на 2π − θ від B)
            x = B.normalized()
            theta = 6.283185307179586 - theta
        else:
            x = A.normalized()
        y = z.cross(x).normalized()
        bpy.ops.object.mode_set(mode='OBJECT')
        t, err = _tool_template(hud_measure_lib(context), ANG_COLL, ANG_LOCAL)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        src = next((o for o in t.objects if _tool_mod(o, ANG_GROUP)), None)
        if src is None:
            self.report({'ERROR'}, "У шаблоні немає об'єкта з GN_HUD_Angle")
            return {'CANCELLED'}
        i = 1
        while f"Angle_{i:02d}" in bpy.data.objects:
            i += 1
        new = src.copy()
        new.name = f"Angle_{i:02d}"
        _measure_collection(context).objects.link(new)
        m = Matrix((x, y, z)).transposed().to_4x4()
        m.translation = apex + z * 0.0002
        new.matrix_world = m
        md = _tool_mod(new, ANG_GROUP)
        ids = _hud_ids(md.node_group)
        sl = context.scene.unit_settings.scale_length or 1.0
        ray_mm = min(A.length, B.length) * sl * 1000.0
        _hud_set(md, ids["Angle"], theta)
        if "Closed Margin" in ids:
            _hud_set(md, ids["Closed Margin"], 0.0872665)
        if "Ray Length (mm)" in ids:
            _hud_set(md, ids["Ray Length (mm)"], ray_mm)
        if "Arc Radius (mm)" in ids:
            _hud_set(md, ids["Arc Radius (mm)"], ray_mm * 0.55)
        if "Start Frame" in ids:
            _hud_set(md, ids["Start Frame"], float(context.scene.frame_current))
        new.update_tag()
        for o in context.selected_objects:
            o.select_set(False)
        new.select_set(True)
        context.view_layer.objects.active = new
        import math as _m
        self.report({'INFO'}, f"{new.name}: {_m.degrees(theta):.2f}° ({how})")
        return {'FINISHED'}


class HUD_OT_add_angle_free(bpy.types.Operator):
    """Object Mode: Angle у 3D-курсорі (вісь Z курсора = вісь кута) + ручки A / B / Label. Ручки далі прив'язуй до вершин / груп"""
    bl_idname = "hud.add_angle_free"
    bl_label = "Add Angle"
    bl_options = {'REGISTER', 'UNDO'}

    angle: bpy.props.FloatProperty(
        name="Start Angle", subtype='ANGLE', default=0.5235988, min=0.0, max=6.2831853,
        description="Початковий кут між ручками A і B (далі кут визначають ручки)")

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        t, err = _tool_template(hud_measure_lib(context), ANG_COLL, ANG_LOCAL)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        src = next((o for o in t.objects if _tool_mod(o, ANG_GROUP)), None)
        if src is None:
            self.report({'ERROR'}, "У шаблоні немає об'єкта з GN_HUD_Angle")
            return {'CANCELLED'}
        i = 1
        while f"Angle_{i:02d}" in bpy.data.objects:
            i += 1
        new = src.copy()
        new.name = f"Angle_{i:02d}"
        _measure_collection(context).objects.link(new)
        new.matrix_world = context.scene.cursor.matrix.copy()
        md = _tool_mod(new, ANG_GROUP)
        ids = _hud_ids(md.node_group)
        _hud_set(md, ids["Angle"], self.angle)
        if "Closed Margin" in ids:
            _hud_set(md, ids["Closed Margin"], 0.0872665)      # 5°: кут «зачинено» не перескакує на 360°
        if "Start Frame" in ids:
            _hud_set(md, ids["Start Frame"], float(context.scene.frame_current))
        for o in context.selected_objects:
            o.select_set(False)
        new.select_set(True)
        context.view_layer.objects.active = new
        bpy.ops.hud.add_handles()
        new.update_tag()
        self.report({'INFO'}, f"{new.name}: ручки {new.name}_A / _B / _Label — прив'яжи їх до деталі")
        return {'FINISHED'}


def _new_handle(name, parent, local_co, coll):
    e = bpy.data.objects.get(name)
    if e is None:
        e = bpy.data.objects.new(name, None)
        coll.objects.link(e)
    e.empty_display_type = 'SPHERE'
    e.empty_display_size = 0.0015
    e.parent = parent
    e.matrix_parent_inverse.identity()
    e.location = local_co
    e.hide_render = True
    return e


class HUD_OT_add_handles(bpy.types.Operator):
    """Створити емпті-ручки для активного інструмента (Angle: Point A / B + Label; Diameter: Label) і ввімкнути їх"""
    bl_idname = "hud.add_handles"
    bl_label = "Add Handles"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and (_tool_mod(ob, ANG_GROUP) or _tool_mod(ob, DIA_GROUP))

    def execute(self, context):
        import math as _m
        ob = context.active_object
        coll = ob.users_collection[0] if ob.users_collection else context.collection
        md = _tool_mod(ob, ANG_GROUP)
        if md is not None:
            ids = _hud_ids(md.node_group)
            g = lambda n: _hud_get(md, ids[n])
            th = g("Angle"); rl = g("Ray Length (mm)") * 0.001
            r = g("Arc Radius (mm)") * 0.001 + g("Leader Length (mm)") * 0.001
            a = _new_handle(ob.name + "_A", ob, Vector((rl, 0, 0)), coll)
            b = _new_handle(ob.name + "_B", ob, Vector((rl * _m.cos(th), rl * _m.sin(th), 0)), coll)
            lb = _new_handle(ob.name + "_Label", ob, Vector((r * _m.cos(th / 2), r * _m.sin(th / 2), 0)), coll)
            for k, v in (("Point A", a), ("Point B", b), ("Label Point", lb), ("Use Points", True), ("Use Label Point", True)):
                _hud_set(md, ids[k], v)
        md = _tool_mod(ob, DIA_GROUP)
        if md is not None:
            ids = _hud_ids(md.node_group)
            g = lambda n: _hud_get(md, ids[n])
            ang = g("Angle"); r = g("Diameter (mm)") * 0.0005 + g("Leader Length (mm)") * 0.001
            lb = _new_handle(ob.name + "_Label", ob, Vector((r * _m.cos(ang), r * _m.sin(ang), 0)), coll)
            _hud_set(md, ids["Label Point"], lb)
            _hud_set(md, ids["Use Label Point"], True)
        ob.update_tag()
        self.report({'INFO'}, "Ручки створено — рухай емпті")
        return {'FINISHED'}


class OBJECT_PT_RossMeasurePanel(bpy.types.Panel):
    bl_options = {'DEFAULT_CLOSED'}
    bl_label = "HUD Measure"
    bl_idname = "OBJECT_PT_ross_measure"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Rost Tools'

    def draw_header(self, context):
        self.layout.label(icon='DRIVER_DISTANCE')

    def draw(self, context):
        L = self.layout
        r = L.row()
        r.scale_y = 1.6
        r.operator("hud.add_angle_free", icon='ADD')
        L.label(text="Object Mode: у 3D-курсорі + ручки A / B / Label")
        r = L.row()
        r.scale_y = 1.4
        r.operator("hud.add_diameter", icon='MESH_CIRCLE')
        r = L.row()
        r.scale_y = 1.4
        r.operator("hud.add_angle", icon='DRIVER_ROTATIONAL_DIFFERENCE')
        r.operator("hud.add_angle", text="Outer", icon='FULLSCREEN_ENTER').outer = True
        if context.mode != 'EDIT_MESH':
            L.label(text="Diameter / Angle from Selection — в Edit Mode", icon='INFO')
        ob = context.active_object
        md = _tool_mod(ob, ANG_GROUP) if ob is not None else None
        if md is not None:
            ids = _hud_ids(md.node_group)
            box = L.box()
            box.label(text=ob.name, icon='RESTRICT_SELECT_OFF')
            col = box.column(align=True)
            for nm in ("Angle", "Style", "Label", "Arc Radius (mm)", "Fill Sector", "Fill Pattern", "Pattern Size (mm)", "Face Camera", "Text Rotation", "Mirror Text X", "Mirror Text Y", "Mirror Text Z", "Closed Margin", "Preview Full", "Start Frame"):
                sck = _hud_sock(md, ids.get(nm))
                if sck is not None:
                    col.prop(sck, "value", text=nm)
            box.operator("hud.add_handles", icon='EMPTY_ARROWS')
        md = _tool_mod(ob, DIA_GROUP) if ob is not None else None
        if md is not None:
            ids = _hud_ids(md.node_group)
            box = L.box()
            box.label(text=ob.name, icon='RESTRICT_SELECT_OFF')
            col = box.column(align=True)
            for nm in ("Diameter (mm)", "Style", "Label", "Angle", "Fill Circle", "Fill Pattern", "Pattern Size (mm)", "Face Camera", "Text Rotation", "Mirror Text X", "Mirror Text Y", "Mirror Text Z", "Preview Full", "Start Frame"):
                sck = _hud_sock(md, ids.get(nm))
                if sck is not None:
                    col.prop(sck, "value", text=nm)
            box.operator("hud.add_handles", icon='EMPTY_ARROWS')


class RossToolsPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    hud_library: bpy.props.StringProperty(
        name="HUD Library", subtype='FILE_PATH', default=HUD_LIB_DEFAULT,
        description="HUD_Elements.blend — звідки беруться Callout і HUD_Cutout; поруч папка Callout_Presets")

    preset_dir: bpy.props.StringProperty(
        name="Light Rig presets folder", subtype='DIR_PATH', default="",
        description="Folder with Rost Light Rig presets (*.json). Empty = Blender user presets")

    def draw(self, context):
        self.layout.prop(self, "hud_library")
        self.layout.prop(self, "preset_dir")


hud_classes = (
    RossToolsPreferences,
    HUD_OT_add_callout,
    HUD_OT_cutout_add,
    HUD_OT_cutout_remove,
    HUD_OT_cutout_refresh,
    HUD_OT_preset_save,
    HUD_OT_preset_apply,
    HUD_OT_preset_delete,
    HUD_OT_preset_folder,
    HUD_OT_update_from_library,
    OBJECT_PT_RossHUDPanel,
    HUD_OT_add_diameter,
    HUD_OT_add_angle,
    HUD_OT_add_angle_free,
    HUD_OT_add_handles,
    OBJECT_PT_RossMeasurePanel,
)


def hud_register():
    for cls in hud_classes:
        bpy.utils.register_class(cls)
    S = bpy.types.Scene
    S.hud_callout = bpy.props.PointerProperty(
        name="Callout", type=bpy.types.Object, poll=lambda self, o: hud_is_callout(o))
    S.hud_preset = bpy.props.EnumProperty(name="Preset", items=_hud_preset_items)
    S.hud_keep_start = bpy.props.BoolProperty(
        name="Keep Start", default=True,
        description="Зберегти поточний Start Frame (пресет зсувається, внутрішні затримки лишаються)")
    S.hud_keep_text = bpy.props.BoolProperty(
        name="Keep Text", default=True, description="Не чіпати текст підпису")


def hud_unregister():
    S = bpy.types.Scene
    for p in ("hud_callout", "hud_preset", "hud_keep_start", "hud_keep_text"):
        if hasattr(S, p):
            delattr(S, p)
    for cls in reversed(hud_classes):
        bpy.utils.unregister_class(cls)


# ==============================================================================
# HUD SECTION (v3.5) — Section / Cutaway
# ==============================================================================
SEC_LIB = "HUD_Section.blend"
SEC_COLL = "HUD_Section"
SEC_GN = "GN_HUD_Section"
SEC_WIRE = "GN_HUD_SectionWire"
SEC_SHADER = "HUD_Section"
SEC_GROUPS = (SEC_GN, SEC_WIRE, SEC_SHADER)
# v3.9 Volume Cut
VC_GN = "GN_HUD_VolumeCut"
VC_PART = "GN_HUD_VolumeCutPart"
VC_SHADER = "HUD_VolumeCut"
VC_GROUPS = (VC_GN, VC_PART, VC_SHADER)
SEC_WIRE_MOD = "HUD_SectionWire"

# шейдерний вхід -> параметр модифікатора Section
SEC_NODE_MAP = {
    "Enable": "Enable", "Flip": "Flip Side",
    "Edge Width (mm)": "Edge Width (mm)", "Edge Glow (mm)": "Edge Glow (mm)",
    "Edge Strength": "Edge Strength", "Ghost": "Ghost", "Ghost Strength": "Ghost Strength",
    "Cap Stripes": "Cap Stripes", "Stripe Width (mm)": "Stripe Width (mm)",
    "Stripe Angle": "Stripe Angle", "Cap Strength": "Cap Strength",
    # v3.8: матеріал Ghost і заливки
    "Ghost Body": "Ghost Body", "Ghost Opacity": "Ghost Opacity", "Ghost Roughness": "Ghost Roughness",
    "Ghost Transmission": "Ghost Transmission", "Ghost IOR": "Ghost IOR",
    "Ghost Keep Material": "Ghost Keep Material", "Cap Use Material": "Cap Use Material",
    "Ghost Use Material": "Ghost Use Material", "Cap Use Custom": "Cap Use Custom",
    "Edge Use Material": "Edge Use Material",
}
SEC_NODE_COLORS = ("Edge Color", "Cap Color A", "Cap Color B", "Ghost Color")
# вхід каркаса -> параметр модифікатора Section
SEC_WIRE_MAP = {"Flip Side": "Flip Side", "Thickness (mm)": "Wire (mm)",
                "Opacity": "Ghost Wire", "Angle": "Wire Angle"}


def sec_lib_path(context):
    return os.path.join(os.path.dirname(hud_lib_path(context)), SEC_LIB)


def sec_mod(o):
    if o is None:
        return None
    for m in o.modifiers:
        if m.type == 'NODES' and m.node_group and _hud_base(m.node_group.name) in (SEC_GN, VC_GN):
            return m
    return None


def sec_is_section(o):
    m = sec_mod(o)
    return o is not None and o.type == 'MESH' and m is not None and _hud_base(m.node_group.name) == SEC_GN


def sec_get(context):
    o = context.active_object
    if sec_is_section(o):
        return o
    o = getattr(context.scene, "hud_section", None)
    return o if sec_is_section(o) else None


def _sec_load(context, collections=(), node_groups=()):
    lib = sec_lib_path(context)
    if not os.path.exists(lib):
        return None, f"Не знайдено бібліотеку: {lib}"
    if _same_file(lib):
        return None, None
    names = ("node_groups", "materials", "fonts", "images", "objects")
    before = {n: set(x.name for x in getattr(bpy.data, n)) for n in names}
    with bpy.data.libraries.load(lib, link=False) as (src, dst):
        dst.collections = [c for c in collections if c in src.collections]
        dst.node_groups = [g for g in node_groups if g in src.node_groups]
    _hud_dedupe(before)
    return dst, None


def sec_ensure_groups(context):
    missing = [g for g in SEC_GROUPS if g not in bpy.data.node_groups]
    if not missing:
        return None
    _, err = _sec_load(context, node_groups=tuple(missing))
    return err


def _sec_path(m, ids, name):
    return f'modifiers["{m.name}"].properties.inputs.{ids[name]}.value'


# ---------------------------------------------------------------- shader --
def sec_nodes(mat, sec=None):
    res = []
    nt = getattr(mat, "node_tree", None) if mat else None
    if nt is None:
        return res
    for n in nt.nodes:
        if n.type == 'GROUP' and n.node_tree and _hud_base(n.node_tree.name) in (SEC_SHADER, VC_SHADER) \
                and not n.name.startswith("SECCOORD|"):
            src = None
            inp = n.inputs.get("Section Coords")
            if inp is not None and inp.is_linked and inp.links[0].from_node.type == 'TEX_COORD':
                src = inp.links[0].from_node.object
            if sec is None or src == sec:
                res.append((n, src))
    return res


def sec_build_node_drivers(mat, node, sec):
    nt = mat.node_tree
    _hud_clear_node_drivers(nt, node)
    m = sec_mod(sec)
    ids = _hud_ids(m.node_group)
    for k, s in SEC_NODE_MAP.items():
        if k in node.inputs and s in ids:
            _hud_driver(node.inputs[k], "default_value", sec, _sec_path(m, ids, s))
    for k in SEC_NODE_COLORS:
        if k in node.inputs and k in ids:
            for i in range(3):
                _hud_driver(node.inputs[k], "default_value", sec, _sec_path(m, ids, k) + f"[{i}]", i)
    # осі площини у світі (для точної проєкції заливки розрізу)
    for nm, ax in (("Axis X", 0), ("Axis Y", 1), ("Axis Z", 2)):
        for r in range(3):
            _hud_driver(node.inputs[nm], "default_value", sec, f"matrix_world[{ax}][{r}]", r)
    if _hud_base(m.node_group.name) == VC_GN:
        for k in ("Shape", "Radius (mm)", "Size X (mm)", "Size Y (mm)", "Size Z (mm)"):
            if k in node.inputs and k in ids:
                _hud_driver(node.inputs[k], "default_value", sec, _sec_path(m, ids, k))
    if "Offset (mm)" in node.inputs:
        node.inputs["Offset (mm)"].default_value = 0.0


def sec_insert(mat, sec, group):
    if sec_nodes(mat, sec):
        return False
    nt = mat.node_tree
    outs = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL']
    if not outs:
        return False
    out = next((n for n in outs if n.is_active_output), outs[0])
    surf = out.inputs["Surface"]
    if not surf.is_linked:
        return False
    src = surf.links[0].from_socket
    x, y = out.location
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = sec
    tc.label = f"Section: {sec.name}"
    tc.location = (x - 220, y - 320)
    tc.hide = True
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = group
    g.name = f"HUD_Section · {sec.name}"
    g.label = g.name
    g.location = (x, y)
    out.location = (x + 280, y)
    nt.links.new(src, g.inputs["Shader"])
    nt.links.new(tc.outputs["Object"], g.inputs["Section Coords"])
    nt.links.new(g.outputs[0], surf)
    sec_build_node_drivers(mat, g, sec)
    mat.use_transparent_shadow = True
    mat.use_backface_culling = False
    try:
        mat.surface_render_method = 'DITHERED'
    except Exception:
        pass
    return True


def sec_remove_nodes(mat, sec=None):
    cnt = 0
    for g, _src in sec_nodes(mat, sec):
        nt = mat.node_tree
        inl = g.inputs["Shader"].links[0].from_socket if g.inputs["Shader"].is_linked else None
        outs = [l.to_socket for l in g.outputs[0].links]
        tc = g.inputs["Section Coords"].links[0].from_node if g.inputs["Section Coords"].is_linked else None
        _hud_clear_node_drivers(nt, g)
        nt.nodes.remove(g)
        if sec is not None:
            for sn in [n for n in nt.nodes if n.name.startswith((f"SECSLOT|{sec.name}|", f"SECCOORD|{sec.name}"))]:
                if sn.name.startswith("SECCOORD|"):
                    _hud_clear_node_drivers(nt, sn)
                nt.nodes.remove(sn)
        if tc is not None and not any(o.is_linked for o in tc.outputs):
            nt.nodes.remove(tc)
        if inl is not None:
            for t in outs:
                nt.links.new(inl, t)
        cnt += 1
    return cnt


# ----------------------------------------------------------------- wire --
def sec_wire_mods(obj, sec=None):
    res = []
    for w in obj.modifiers:
        if w.type == 'NODES' and w.node_group and _hud_base(w.node_group.name) == SEC_WIRE:
            ids = _hud_ids(w.node_group)
            tgt = _hud_get(w, ids.get("Section"))
            if sec is None or tgt == sec:
                res.append(w)
    return res


def _sec_clear_obj_drivers(obj, w):
    ad = obj.animation_data
    if ad is None:
        return
    pref = f'modifiers["{w.name}"]'
    for fc in list(ad.drivers):
        if fc.data_path.startswith(pref):
            ad.drivers.remove(fc)


def sec_wire_drivers(obj, w, sec):
    _sec_clear_obj_drivers(obj, w)
    m = sec_mod(sec)
    sids = _hud_ids(m.node_group)
    wids = _hud_ids(w.node_group)
    for dst, src in SEC_WIRE_MAP.items():
        if dst in wids and src in sids:
            _hud_driver(obj, f'modifiers["{w.name}"].properties.inputs.{wids[dst]}.value',
                        sec, _sec_path(m, sids, src))


def sec_wire_to_last(obj, w):
    idx = list(obj.modifiers).index(w)
    last = len(obj.modifiers) - 1
    if idx != last:
        obj.modifiers.move(idx, last)


def sec_wire_add(obj, sec):
    if obj.type != 'MESH':
        return False
    have = sec_wire_mods(obj, sec)
    if have:
        sec_wire_to_last(obj, have[0])
        sec_wire_drivers(obj, have[0], sec)
        return False
    w = obj.modifiers.new(f"{SEC_WIRE_MOD} · {sec.name}", 'NODES')
    w.node_group = bpy.data.node_groups[SEC_WIRE]
    wids = _hud_ids(w.node_group)
    for it in _hud_inputs(w.node_group):        # явні значення за замовчуванням
        if hasattr(it, "default_value") and it.socket_type not in ('NodeSocketObject', 'NodeSocketMaterial'):
            _hud_set(w, it.identifier, it.default_value)
    _hud_set(w, wids["Section"], sec)
    m = sec_mod(sec)
    sids = _hud_ids(m.node_group)
    mat = (sec_wire_material(sec) or _hud_get(m, sids.get("Frame Material"))
           or bpy.data.materials.get("HUD_Line"))
    if mat is not None:
        _hud_set(w, wids["Material"], mat)
    sec_wire_to_last(obj, w)
    sec_wire_drivers(obj, w, sec)
    return True


def sec_wire_remove(obj, sec=None):
    cnt = 0
    for w in sec_wire_mods(obj, sec):
        _sec_clear_obj_drivers(obj, w)
        obj.modifiers.remove(w)
        cnt += 1
    return cnt


# ------------------------------------------------------- справжній кап-меш --
# Заливка зрізу як реальна геометрія: Boolean (Intersect) деталі з півпростором за площиною Section,
# з результату лишаються тільки грані на площині. Тому заливка суцільна, закриває все, що позаду,
# і приймає звичайний Material (Set Material). Hole Tolerant (Exact) закриває щілини в мешах.
SEC_CAP_GROUP = "GN_HUD_SectionCap"
SEC_CAP_MOD = "HUD_SectionCap"


def sec_cap_group():
    g = bpy.data.node_groups.get(SEC_CAP_GROUP)
    if g is not None:
        return g
    g = bpy.data.node_groups.new(SEC_CAP_GROUP, 'GeometryNodeTree')
    I = g.interface
    I.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    I.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    I.new_socket("Section", in_out='INPUT', socket_type='NodeSocketObject')
    I.new_socket("Flip Side", in_out='INPUT', socket_type='NodeSocketBool')
    I.new_socket("Hole Tolerant", in_out='INPUT', socket_type='NodeSocketBool')
    so = I.new_socket("Offset (mm)", in_out='INPUT', socket_type='NodeSocketFloat')
    so.default_value, so.min_value = 0.01, 0.0
    st = I.new_socket("Tolerance (mm)", in_out='INPUT', socket_type='NodeSocketFloat')
    st.default_value, st.min_value = 0.005, 0.0
    I.new_socket("Material", in_out='INPUT', socket_type='NodeSocketMaterial')
    N, Lk = g.nodes, g.links

    def nd(t, x, y, label=""):
        n = N.new(t)
        n.location = (x, y)
        n.label = label
        return n

    def Mt(op, a=None, b=None, x=0, y=0, label=""):
        n = nd('ShaderNodeMath', x, y, label)
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                Lk.new(v, n.inputs[i])
        return n

    gi = nd('NodeGroupInput', -1800, 0)
    go = nd('NodeGroupOutput', 2400, 0)
    oi = nd('GeometryNodeObjectInfo', -1500, 400)
    oi.transform_space = 'RELATIVE'
    Lk.new(gi.outputs["Section"], oi.inputs["Object"])
    inv = nd('FunctionNodeInvertMatrix', -1300, 400)
    Lk.new(oi.outputs["Transform"], inv.inputs[0])
    bb = nd('GeometryNodeBoundBox', -1500, 0)
    Lk.new(gi.outputs["Geometry"], bb.inputs["Geometry"])
    vsub = nd('ShaderNodeVectorMath', -1300, 0)
    vsub.operation = 'SUBTRACT'
    Lk.new(bb.outputs["Max"], vsub.inputs[0])
    Lk.new(bb.outputs["Min"], vsub.inputs[1])
    vlen = nd('ShaderNodeVectorMath', -1150, 0)
    vlen.operation = 'LENGTH'
    Lk.new(vsub.outputs[0], vlen.inputs[0])
    vmid = nd('ShaderNodeVectorMath', -1300, -200)
    vmid.operation = 'ADD'
    Lk.new(bb.outputs["Max"], vmid.inputs[0])
    Lk.new(bb.outputs["Min"], vmid.inputs[1])
    vhalf = nd('ShaderNodeVectorMath', -1150, -200)
    vhalf.operation = 'SCALE'
    vhalf.inputs[3].default_value = 0.5
    Lk.new(vmid.outputs[0], vhalf.inputs[0])
    cs = nd('FunctionNodeTransformPoint', -1000, -200, "bbox center in section space")
    Lk.new(vhalf.outputs[0], cs.inputs[0])
    Lk.new(inv.outputs[0], cs.inputs[1])
    csep = nd('ShaderNodeSeparateXYZ', -850, -200)
    Lk.new(cs.outputs[0], csep.inputs[0])
    a1 = Mt('MULTIPLY', vlen.outputs[0], 3.0, -1000, 100)
    a2 = Mt('ADD', a1.outputs[0], 0.2, -850, 100)
    cz = Mt('ABSOLUTE', csep.outputs[2], None, -850, -350)
    S = Mt('MULTIPLY_ADD', cz.outputs[0], 2.0, -700, 100, "box size")
    Lk.new(a2.outputs[0], S.inputs[2])
    sw = nd('GeometryNodeSwitch', -1500, -500, "side sign")
    sw.input_type = 'FLOAT'
    Lk.new(gi.outputs["Flip Side"], sw.inputs["Switch"])
    sw.inputs[1].default_value = -1.0
    sw.inputs[2].default_value = 1.0
    sgn = sw.outputs[0]
    off_m = Mt('MULTIPLY', gi.outputs["Offset (mm)"], 0.001, -1500, -650, "offset m")
    tol_m = Mt('MULTIPLY', gi.outputs["Tolerance (mm)"], 0.001, -1500, -750, "tol m")
    zplane = Mt('MULTIPLY', sgn, off_m.outputs[0], -1300, -600, "cap plane z")
    half = Mt('MULTIPLY', S.outputs[0], 0.5, -550, 100)
    hz = Mt('MULTIPLY', sgn, half.outputs[0], -400, 100)
    zc = Mt('ADD', zplane.outputs[0], hz.outputs[0], -250, 100, "box center z")
    cube = nd('GeometryNodeMeshCube', -400, 300)
    cs3 = nd('ShaderNodeCombineXYZ', -550, 300)
    for i in range(3):
        Lk.new(S.outputs[0], cs3.inputs[i])
    Lk.new(cs3.outputs[0], cube.inputs["Size"])
    ct = nd('ShaderNodeCombineXYZ', -100, 300)
    Lk.new(csep.outputs[0], ct.inputs[0])
    Lk.new(csep.outputs[1], ct.inputs[1])
    Lk.new(zc.outputs[0], ct.inputs[2])
    t1 = nd('GeometryNodeTransform', 100, 300, "box in section space")
    Lk.new(cube.outputs["Mesh"], t1.inputs["Geometry"])
    Lk.new(ct.outputs[0], t1.inputs["Translation"])
    t2 = nd('GeometryNodeTransform', 300, 300, "box in part space")
    t2.inputs["Mode"].default_value = 'Matrix'
    Lk.new(t1.outputs[0], t2.inputs["Geometry"])
    Lk.new(oi.outputs["Transform"], t2.inputs["Transform"])
    b1 = nd('GeometryNodeMeshBoolean', 600, 200, "Manifold")
    b1.operation, b1.solver = 'INTERSECT', 'MANIFOLD'
    b2 = nd('GeometryNodeMeshBoolean', 600, -100, "Exact · hole tolerant")
    b2.operation, b2.solver = 'INTERSECT', 'EXACT'
    b2.inputs["Hole Tolerant"].default_value = True
    for b in (b1, b2):
        Lk.new(gi.outputs["Geometry"], b.inputs["Mesh"])
        Lk.new(t2.outputs[0], b.inputs["Mesh"])
    sw2 = nd('GeometryNodeSwitch', 850, 100)
    sw2.input_type = 'GEOMETRY'
    Lk.new(gi.outputs["Hole Tolerant"], sw2.inputs["Switch"])
    Lk.new(b1.outputs["Mesh"], sw2.inputs[1])
    Lk.new(b2.outputs["Mesh"], sw2.inputs[2])
    pos = nd('GeometryNodeInputPosition', 700, -500)
    tp = nd('FunctionNodeTransformPoint', 850, -500)
    Lk.new(pos.outputs[0], tp.inputs[0])
    Lk.new(inv.outputs[0], tp.inputs[1])
    sp = nd('ShaderNodeSeparateXYZ', 1000, -500)
    Lk.new(tp.outputs[0], sp.inputs[0])
    dz = Mt('SUBTRACT', sp.outputs[2], zplane.outputs[0], 1150, -500)
    adz = Mt('ABSOLUTE', dz.outputs[0], None, 1300, -500)
    ev = nd('GeometryNodeFieldOnDomain', 1450, -500)
    ev.domain, ev.data_type = 'FACE', 'FLOAT'
    Lk.new(adz.outputs[0], ev.inputs[0])
    cmp = nd('FunctionNodeCompare', 1600, -500)
    cmp.data_type, cmp.operation = 'FLOAT', 'GREATER_THAN'
    Lk.new(ev.outputs[0], cmp.inputs[0])
    Lk.new(tol_m.outputs[0], cmp.inputs[1])
    dl = nd('GeometryNodeDeleteGeometry', 1750, 100)
    dl.domain, dl.mode = 'FACE', 'ALL'
    Lk.new(sw2.outputs[0], dl.inputs["Geometry"])
    Lk.new(cmp.outputs[0], dl.inputs["Selection"])
    sm = nd('GeometryNodeSetMaterial', 1950, 100)
    Lk.new(dl.outputs[0], sm.inputs["Geometry"])
    Lk.new(gi.outputs["Material"], sm.inputs["Material"])
    jn = nd('GeometryNodeJoinGeometry', 2150, 0)
    Lk.new(gi.outputs["Geometry"], jn.inputs[0])
    Lk.new(sm.outputs[0], jn.inputs[0])
    Lk.new(jn.outputs[0], go.inputs[0])
    return g


def sec_cap_builtin(sec):
    """Вбудований матеріал заливки (Panel): Color A/B, Stripes, Width, Angle, Strength з панелі."""
    name = f"HUD_SecCap · {sec.name}"
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    nt = mat.node_tree
    nt.nodes.clear()
    N, Lk = nt.nodes, nt.links
    m = sec_mod(sec)
    ids = _hud_ids(m.node_group)

    def Mt(op, x, y, a=None, b=None):
        n = N.new('ShaderNodeMath')
        n.operation = op
        n.location = (x, y)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                Lk.new(v, n.inputs[i])
        return n

    def drv(sock, nm, idx=-1):
        if nm in ids:
            p = _sec_path(m, ids, nm) + (f"[{idx}]" if idx >= 0 else "")
            _hud_driver(sock, "default_value", sec, p, idx)

    tc = N.new('ShaderNodeTexCoord')
    tc.object = sec
    tc.location = (-1100, 0)
    sp = N.new('ShaderNodeSeparateXYZ')
    sp.location = (-900, 0)
    Lk.new(tc.outputs["Object"], sp.inputs[0])
    rad = Mt('RADIANS', -900, -250, 0.0)
    drv(rad.inputs[0], "Stripe Angle")
    cs = Mt('COSINE', -750, -250, rad.outputs[0])
    sn = Mt('SINE', -750, -400, rad.outputs[0])
    ux = Mt('MULTIPLY', -600, 100, sp.outputs[0], cs.outputs[0])
    u = Mt('MULTIPLY_ADD', -450, 0, sp.outputs[1], sn.outputs[0])
    Lk.new(ux.outputs[0], u.inputs[2])
    wd = Mt('MULTIPLY', -600, -550, 4.0, 0.001)
    drv(wd.inputs[0], "Stripe Width (mm)")
    q = Mt('DIVIDE', -300, 0, u.outputs[0], wd.outputs[0])
    fr = Mt('FRACT', -150, 0, q.outputs[0])
    gt = Mt('GREATER_THAN', 0, 0, fr.outputs[0], 0.5)
    on = Mt('MULTIPLY', 150, 0, gt.outputs[0], 1.0)
    drv(on.inputs[1], "Cap Stripes")
    mx = N.new('ShaderNodeMix')
    mx.data_type = 'RGBA'
    mx.location = (320, 0)
    Lk.new(on.outputs[0], mx.inputs["Factor"])
    for i in range(3):
        drv(mx.inputs["A"], "Cap Color A", i)
        drv(mx.inputs["B"], "Cap Color B", i)
    em = N.new('ShaderNodeEmission')
    em.location = (520, 0)
    Lk.new(mx.outputs["Result"], em.inputs["Color"])
    drv(em.inputs["Strength"], "Cap Strength")
    out = N.new('ShaderNodeOutputMaterial')
    out.location = (720, 0)
    Lk.new(em.outputs[0], out.inputs["Surface"])
    return mat


def sec_cap_mods(obj, sec=None):
    res = []
    for w in obj.modifiers:
        if w.type == 'NODES' and w.node_group and w.node_group.name.startswith(SEC_CAP_GROUP):
            if sec is None or _hud_get(w, _hud_ids(w.node_group).get("Section")) == sec:
                res.append(w)
    return res


def sec_cap_material(sec):
    m = sec_mod(sec)
    ids = _hud_ids(m.node_group)
    if _hud_get(m, ids.get("Cap Use Custom")):
        M = _hud_get(m, ids.get("Cap Material"))
        if M is not None:
            return M
    return sec_cap_builtin(sec)


def sec_cap_sync(sec):
    if vc_is_cutter(sec):
        return vc_sync(sec)
    mat = sec_cap_material(sec)
    n = 0
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        for w in sec_cap_mods(o, sec):
            ids = _hud_ids(w.node_group)
            if _hud_get(w, ids.get("Material")) != mat:
                _hud_set(w, ids["Material"], mat)
            n += 1
    return n


def sec_cap_drivers(obj, w, sec):
    _sec_clear_obj_drivers(obj, w)
    m = sec_mod(sec)
    sids = _hud_ids(m.node_group)
    wids = _hud_ids(w.node_group)
    if "Flip Side" in sids:
        _hud_driver(obj, f'modifiers["{w.name}"].properties.inputs.{wids["Flip Side"]}.value',
                    sec, _sec_path(m, sids, "Flip Side"))
    if "Hole Tolerant" in wids:
        _hud_driver(obj, f'modifiers["{w.name}"].properties.inputs.{wids["Hole Tolerant"]}.value', sec, '["hud_cap_holes"]')
    for prop in ("show_viewport", "show_render"):
        fc = obj.driver_add(f'modifiers["{w.name}"].{prop}')
        d = fc.driver
        for v in list(d.variables):
            d.variables.remove(v)
        d.type = 'SCRIPTED'
        d.expression = "cap and en"
        _hud_var(d, "cap", sec, '["hud_cap"]')
        _hud_var(d, "en", sec, _sec_path(m, sids, "Enable"))


def sec_cap_add(obj, sec):
    if obj.type != 'MESH':
        return False
    if sec.get("hud_cap") is None:
        sec["hud_cap"] = 1
    if sec.get("hud_cap_holes") is None:
        sec["hud_cap_holes"] = 0
    have = sec_cap_mods(obj, sec)
    g = sec_cap_group()
    if have:
        w = have[0]
        new = False
    else:
        w = obj.modifiers.new(f"{SEC_CAP_MOD} · {sec.name}", 'NODES')
        w.node_group = g
        wids = _hud_ids(g)
        _hud_set(w, wids["Section"], sec)
        _hud_set(w, wids["Offset (mm)"], 0.01)
        _hud_set(w, wids["Tolerance (mm)"], 0.005)
        new = True
    # місце в стеку: прямо перед каркасом (або останнім)
    # (v3.8.1) заливка МАЄ стояти перед каркасом: якщо каркас іде першим, GN губить
    # матеріал заливки і вона зникає. Раніше move() ставив заливку ПІСЛЯ каркаса.
    wires = sec_wire_mods(obj, sec)
    mods = list(obj.modifiers)
    cur = mods.index(w)
    if wires:
        wi = mods.index(wires[0])
        if cur > wi:
            obj.modifiers.move(cur, wi)
    elif cur != len(mods) - 1:
        obj.modifiers.move(cur, len(mods) - 1)
    sec_cap_drivers(obj, w, sec)
    return new


def sec_cap_remove(obj, sec=None):
    cnt = 0
    for w in sec_cap_mods(obj, sec):
        _sec_clear_obj_drivers(obj, w)
        obj.modifiers.remove(w)
        cnt += 1
    return cnt


# ------------------------------------------------ слоти матеріалів (v3.8) --
# Шейдер не може приймати звичайний вибір матеріалу, тому вибраний матеріал копіюється
# в нод-групу "HUD_SecMat · <ім'я>" і підключається у вхід Ghost / Cap / Edge Shader розрізу.
SEC_SLOTS = (("Ghost", "Ghost Shader", "Ghost Material"),
             ("Cap", "Cap Shader", "Cap Material"),
             ("Edge", "Edge Shader", "Edge Material"))
_MC_SKIP = {"rna_type", "inputs", "outputs", "internal_links", "dimensions", "select", "name", "type",
            "bl_idname", "bl_label", "bl_description", "bl_icon", "bl_static_type", "location", "parent",
            "is_active_output", "location_absolute", "bl_width_default", "bl_width_min", "bl_width_max",
            "bl_height_default", "bl_height_min", "bl_height_max"}


def _sock_index(socks, sock):
    p = sock.as_pointer()
    for i, x in enumerate(socks):
        if x.as_pointer() == p:
            return i
    return -1


def _mc_copy_node(n, g):
    n2 = g.nodes.new(n.bl_idname)
    for p in n.bl_rna.properties:
        pid = p.identifier
        if pid in _MC_SKIP or p.is_readonly:
            continue
        try:
            setattr(n2, pid, getattr(n, pid))
        except Exception:
            pass
    n2.location = n.location
    n2.label = n.label
    try:
        cr = getattr(n, "color_ramp", None)
        if cr is not None:
            cr2 = n2.color_ramp
            cr2.interpolation = cr.interpolation
            while len(cr2.elements) < len(cr.elements):
                cr2.elements.new(0.5)
            for i, e in enumerate(cr.elements):
                cr2.elements[i].position = e.position
                cr2.elements[i].color = e.color
    except Exception:
        pass
    try:
        mp = getattr(n, "mapping", None)
        if mp is not None and hasattr(mp, "curves"):
            for ci, c in enumerate(mp.curves):
                c2 = n2.mapping.curves[ci]
                while len(c2.points) < len(c.points):
                    c2.points.new(0.0, 0.0)
                for i, pt in enumerate(c.points):
                    c2.points[i].location = pt.location
                    c2.points[i].handle_type = pt.handle_type
            n2.mapping.update()
    except Exception:
        pass
    for i, sk in enumerate(n.inputs):
        if i < len(n2.inputs) and hasattr(sk, "default_value") and not sk.is_linked:
            try:
                n2.inputs[i].default_value = sk.default_value
            except Exception:
                pass
    # вузли Value / RGB зберігають значення у виході
    for i, sk in enumerate(n.outputs):
        if i < len(n2.outputs) and hasattr(sk, "default_value") and n.bl_idname in ("ShaderNodeValue", "ShaderNodeRGB"):
            try:
                n2.outputs[i].default_value = sk.default_value
            except Exception:
                pass
    return n2


def sec_ensure_cap_coords(g):
    """Додає групі HUD_Section вихід 'Cap Coords': точка, де промінь камери перетинає площину розрізу
    (u, v у системі Section). Саме по ній текстури лягають на зріз, а не на внутрішні стінки деталі."""
    if g is None or any(i.item_type == 'SOCKET' and i.in_out == 'OUTPUT' and i.name == "Cap Coords"
                        for i in g.interface.items_tree):
        return True
    nu, nv = g.nodes.get("Math.009"), g.nodes.get("Math.010")
    go = next((n for n in g.nodes if n.bl_idname == 'NodeGroupOutput'), None)
    if nu is None or nv is None or go is None:
        return False
    g.interface.new_socket("Cap Coords", in_out='OUTPUT', socket_type='NodeSocketVector')
    cx = g.nodes.new('ShaderNodeCombineXYZ')
    cx.label = "Cap coords (ray hit on plane)"
    cx.location = (go.location.x - 200, go.location.y - 500)
    g.links.new(nu.outputs[0], cx.inputs[0])
    g.links.new(nv.outputs[0], cx.inputs[1])
    g.links.new(cx.outputs[0], go.inputs["Cap Coords"])
    return True


def sec_matgroup(mat, rebuild=False, planar=None):
    """Матеріал -> нод-група з виходом Shader (копія вузлів; оновлюється при rebuild / ⟳).
    planar = об'єкт Section: координати Generated/UV/Object беруться з площини розрізу
    (для заливки й бордера, інакше процедурні текстури на зрізі виходять плоскими)."""
    name = f"HUD_SecMat · {mat.name}" + (f" @{planar.name}" if planar is not None else "")
    g = bpy.data.node_groups.get(name)
    has_c = g is not None and any(i.item_type == 'SOCKET' and i.name == "Coords" for i in g.interface.items_tree)
    if g is not None and not rebuild and (planar is None or has_c):
        return g
    if g is None:
        g = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    else:
        # інтерфейс НЕ чистимо: interface.clear() рве лінки всіх вузлів-споживачів групи (чорний шейдер у Ghost/Cap)
        g.nodes.clear()
    _have = {i.name for i in g.interface.items_tree if i.item_type == 'SOCKET'}
    if "Shader" not in _have:
        g.interface.new_socket("Shader", in_out='OUTPUT', socket_type='NodeSocketShader')
    cin = None
    if planar is not None:
        if "Coords" not in _have:
            g.interface.new_socket("Coords", in_out='INPUT', socket_type='NodeSocketVector')
        cin = g.nodes.new('NodeGroupInput')
        cin.location = (-900, 300)
    go = g.nodes.new('NodeGroupOutput')
    src = mat.node_tree
    if src is None:
        return g
    mp = {}
    scl = {}
    for n in src.nodes:
        if n.type == 'OUTPUT_MATERIAL':
            continue
        if n.type == 'GROUP' and n.node_tree and _hud_base(n.node_tree.name) == SEC_SHADER:
            continue
        mp[n.name] = _mc_copy_node(n, g)
        if planar is not None and n.type == 'TEX_COORD':
            scl[n.name] = None
    if planar is not None:
        # координати = точка перетину променя з площиною розрізу, нормована розміром Section (0..1)
        sc = g.nodes.new('ShaderNodeVectorMath')
        sc.operation = 'SCALE'
        sc.label = "Section size"
        sc.location = (-650, 300)
        size = max(planar.dimensions.x, planar.dimensions.y, 1e-6)
        sc.inputs[3].default_value = 1.0 / size
        g.links.new(cin.outputs["Coords"], sc.inputs[0])
        for nm in list(scl):
            scl[nm] = sc
        # текстури без підключеного Vector за замовчуванням беруть Generated: теж на площину
        for n in src.nodes:
            n2 = mp.get(n.name)
            if n2 is not None and n.type.startswith("TEX_") and "Vector" in n.inputs and not n.inputs["Vector"].is_linked:
                try:
                    g.links.new(sc.outputs[0], n2.inputs["Vector"])
                except Exception:
                    pass
    for l in src.links:
        a, b = mp.get(l.from_node.name), mp.get(l.to_node.name)
        if a is None or b is None:
            continue
        fi = _sock_index(l.from_node.outputs, l.from_socket)
        if planar is not None and l.from_node.type == 'TEX_COORD' and l.from_socket.name in ("Generated", "UV", "Object"):
            a, fi = scl[l.from_node.name], 0
        ti = _sock_index(l.to_node.inputs, l.to_socket)
        if fi >= 0 and ti >= 0:
            try:
                g.links.new(a.outputs[fi], b.inputs[ti])
            except Exception:
                pass
    outs = [n for n in src.nodes if n.type == 'OUTPUT_MATERIAL']
    out = next((n for n in outs if n.is_active_output), outs[0] if outs else None)
    if out is not None and out.inputs["Surface"].is_linked:
        l = out.inputs["Surface"].links[0]
        a = mp.get(l.from_node.name)
        if a is not None:
            fi = _sock_index(l.from_node.outputs, l.from_socket)
            if fi >= 0:
                g.links.new(a.outputs[fi], go.inputs[0])
    go.location = (max([n.location.x for n in g.nodes] + [0]) + 300, 0)
    return g


_SEC_REG = set()     # імена Section, що мають слоти-матеріали
_SEC_SRC = {}        # (section, матеріал) -> підпис вузлів джерела


def _val_sig(v):
    try:
        return tuple(round(x, 5) if isinstance(x, float) else x for x in v)
    except TypeError:
        return round(v, 5) if isinstance(v, float) else v


def _mat_sig(mat):
    """Підпис значень вузлів матеріалу: змінився — копію в слоті треба оновити."""
    nt = mat.node_tree
    if nt is None:
        return None
    out = []
    for n in nt.nodes:
        if n.type == 'OUTPUT_MATERIAL':
            continue
        props = []
        for p in n.bl_rna.properties:
            if p.identifier in _MC_SKIP or p.is_readonly or p.type not in ('BOOLEAN', 'INT', 'FLOAT', 'ENUM', 'STRING'):
                continue
            try:
                props.append(_val_sig(getattr(n, p.identifier)))
            except Exception:
                pass
        ins = []
        for sk in n.inputs:
            if hasattr(sk, "default_value") and not sk.is_linked:
                try:
                    ins.append(_val_sig(sk.default_value))
                except Exception:
                    pass
        extra = ()
        if n.bl_idname in ("ShaderNodeValue", "ShaderNodeRGB"):
            extra = (_val_sig(n.outputs[0].default_value),)
        cr = getattr(n, "color_ramp", None)
        if cr is not None:
            extra = tuple((round(e.position, 5), _val_sig(e.color)) for e in cr.elements)
        out.append((n.name, tuple(props), tuple(ins), extra))
    out.append(tuple(sorted((l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name) for l in nt.links)))
    return hash(tuple(out))


def sec_src_changed(sec):
    m = sec_mod(sec)
    if m is None:
        return False
    ids = _hud_ids(m.node_group)
    ch = False
    for _slot, _sh, mname in SEC_SLOTS:
        M = _hud_get(m, ids.get(mname))
        if M is None:
            continue
        key = (sec.name, M.name)
        sg = (_mat_sig(M), round(sec.dimensions.x, 4), round(sec.dimensions.y, 4))
        if _SEC_SRC.get(key) != sg:
            _SEC_SRC[key] = sg
            ch = True
    return ch


def sec_apply_slots(sec, rebuild=False):
    """Підключає матеріали слотів Ghost / Cap / Edge до шейдера розрізу у всіх матеріалах деталей."""
    m = sec_mod(sec)
    if m is None:
        return 0
    _SEC_REG.add(sec.name)
    sec_src_changed(sec)
    ids = _hud_ids(m.node_group)
    built = {}
    cnt = 0
    for mat in list(bpy.data.materials):
        for node, _src in sec_nodes(mat, sec):
            nt = mat.node_tree
            for k, (slot, shin, mname) in enumerate(SEC_SLOTS):
                inp = node.inputs.get(shin)
                if inp is None:
                    continue
                M = _hud_get(m, ids.get(mname))
                key = f"SECSLOT|{sec.name}|{slot}"
                gn = nt.nodes.get(key)
                if M is None or M.node_tree is None or M == mat:
                    # порожній слот: підставляємо власний матеріал деталі (а не чорний шейдер)
                    if gn is not None:
                        nt.nodes.remove(gn)
                        cnt += 1
                    sh = node.inputs.get("Shader")
                    if sh is not None and sh.is_linked and not inp.is_linked:
                        nt.links.new(sh.links[0].from_socket, inp)
                    continue
                pl = sec if slot in ("Cap", "Edge") else None
                bk = (M.name, pl.name if pl else "")
                grp = built.get(bk)
                if grp is None:
                    grp = built[bk] = sec_matgroup(M, rebuild, pl)
                if gn is None:
                    gn = nt.nodes.new("ShaderNodeGroup")
                    gn.name = key
                    gn.location = (node.location.x - 280, node.location.y - 420 - 110 * k)
                gn.node_tree = grp
                gn.label = f"{slot}: {M.name}"
                if pl is not None and gn.inputs.get("Coords") is not None and sec_ensure_cap_coords(node.node_tree):
                    # окремий екземпляр групи лише заради виходу Cap Coords (інакше цикл: група -> слот -> група)
                    cn = nt.nodes.get(f"SECCOORD|{sec.name}")
                    if cn is None or cn.node_tree != node.node_tree:
                        if cn is not None:
                            _hud_clear_node_drivers(nt, cn)
                            nt.nodes.remove(cn)
                        cn = nt.nodes.new("ShaderNodeGroup")
                        cn.node_tree = node.node_tree
                        cn.name = f"SECCOORD|{sec.name}"
                        cn.label = "Cap coords (helper)"
                        cn.location = (node.location.x - 280, node.location.y - 900)
                        cn.hide = True
                        scoord = node.inputs["Section Coords"]
                        if scoord.is_linked:
                            nt.links.new(scoord.links[0].from_socket, cn.inputs["Section Coords"])
                        sec_build_node_drivers(mat, cn, sec)
                    oc = cn.outputs.get("Cap Coords")
                    if oc is not None and (not gn.inputs["Coords"].is_linked or gn.inputs["Coords"].links[0].from_socket != oc):
                        nt.links.new(oc, gn.inputs["Coords"])
                if not inp.is_linked or inp.links[0].from_node != gn:
                    nt.links.new(gn.outputs[0], inp)
                cnt += 1
            mat.update_tag()
    return cnt


def sec_wire_builtin(sec):
    """Вбудований матеріал каркаса секції: Wire Color / Wire Strength з панелі."""
    name = f"HUD_SecWire · {sec.name}"
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    base = bpy.data.materials.get("HUD_Line")
    if base is not None:
        mat = base.copy()
        mat.name = name
    else:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        em = nt.nodes.new("ShaderNodeEmission")
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(em.outputs[0], o.inputs[0])
    m = sec_mod(sec)
    ids = _hud_ids(m.node_group)
    nt = mat.node_tree
    for n in nt.nodes:
        if n.type != 'OUTPUT_MATERIAL' and "Color" in n.inputs and "Strength" in n.inputs:
            _hud_clear_node_drivers(nt, n)
            if "Wire Color" in ids:
                for i in range(3):
                    _hud_driver(n.inputs["Color"], "default_value", sec, _sec_path(m, ids, "Wire Color") + f"[{i}]", i)
            if "Wire Strength" in ids:
                _hud_driver(n.inputs["Strength"], "default_value", sec, _sec_path(m, ids, "Wire Strength"))
            break
    return mat


def sec_wire_material(sec):
    """Матеріал каркаса за перемикачем Wire Use Material (None = не чіпати)."""
    m = sec_mod(sec)
    ids = _hud_ids(m.node_group)
    if _hud_get(m, ids.get("Wire Use Material")):
        return _hud_get(m, ids.get("Wire Material"))
    return sec_wire_builtin(sec)


SEC_V38_NAMES = ("Ghost Body", "Ghost Color", "Ghost Opacity", "Ghost Roughness", "Ghost Transmission",
                 "Ghost IOR", "Ghost Keep Material", "Cap Use Material")


def sec_init_defaults(sec):
    """Section зі старої версії (або створений без значень): підставити типові значення нових параметрів 3.8."""
    if sec is None:
        return
    m = sec_mod(sec)
    if m is None:
        return
    for marker, names in (("hud_v38", SEC_V38_NAMES), ("hud_v38b", ("Wire Color", "Wire Strength"))):
        if sec.get(marker):
            continue
        for it in _hud_inputs(m.node_group):
            if it.name in names:
                _hud_set(m, it.identifier, it.default_value)
        sec[marker] = 1


def sec_sync_wire_material(sec):
    """Wire Material з Section -> усі його каркаси (v3.8). Порожній слот = лишити як є."""
    if vc_is_cutter(sec):
        return 0
    m = sec_mod(sec)
    if m is None:
        return 0
    mat = sec_wire_material(sec)
    if mat is None:
        return 0
    n = 0
    for o in bpy.data.objects:
        for w in sec_wire_mods(o, sec):
            wids = _hud_ids(w.node_group)
            if "Material" in wids and _hud_get(w, wids["Material"]) is not mat:
                _hud_set(w, wids["Material"], mat)
                o.update_tag()
                n += 1
    return n


_SEC_SIG = {}


def _sec_sig(sec):
    m = sec_mod(sec)
    ids = _hud_ids(m.node_group)
    vals = []
    for nm in ("Ghost Material", "Cap Material", "Edge Material", "Wire Material"):
        x = _hud_get(m, ids.get(nm))
        vals.append(x.name if x else None)
    vals.append(bool(_hud_get(m, ids.get("Wire Use Material"))))
    vals.append(bool(_hud_get(m, ids.get("Cap Use Custom"))))
    return tuple(vals)


@bpy.app.handlers.persistent
def _sec_wire_mat_handler(*_a):
    """Активний Section: зміна полів матеріалів у панелі підхоплюється одразу (без ⟳)."""
    try:
        ob = bpy.context.active_object
        if ob is not None and sec_mod(ob) is not None:
            sig = _sec_sig(ob)
            if _SEC_SIG.get(ob.name) != sig:
                _SEC_SIG[ob.name] = sig
                sec_apply_slots(ob)
                sec_sync_wire_material(ob)
                sec_cap_sync(ob)
        # правки у матеріалі-джерелі (будь-який активний об'єкт) підхоплюються наживо
        for nm in list(_SEC_REG):
            so = bpy.data.objects.get(nm)
            if so is None or sec_mod(so) is None:
                _SEC_REG.discard(nm)
                continue
            if sec_src_changed(so):
                sec_apply_slots(so, rebuild=True)
    except Exception:
        pass


def sec_refresh(sec):
    sec_init_defaults(sec)
    sec_apply_slots(sec, rebuild=True)
    sec_sync_wire_material(sec)
    nm = 0
    for mat in bpy.data.materials:
        for g, _s in sec_nodes(mat, sec):
            sec_build_node_drivers(mat, g, sec)
            mat.update_tag()
            nm += 1
    nw = 0
    for o in bpy.data.objects:
        for w in sec_wire_mods(o, sec):
            sec_wire_to_last(o, w)
            sec_wire_drivers(o, w, sec)
            sec_cap_add(o, sec)
            o.update_tag()
            nw += 1
    sec_cap_sync(sec)
    sec.update_tag(refresh={'OBJECT'})
    return nm, nw


def _sec_targets(context, sec):
    return [o for o in context.selected_objects
            if o != sec and not sec_is_section(o) and not hud_is_callout(o)
            and o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META', 'CURVES'}]


# ------------------------------------------------------------ operators --
class HUD_OT_section_add(bpy.types.Operator):
    """Додати Section (площину розрізу) з бібліотеки в 3D-курсор"""
    bl_idname = "hud.section_add"
    bl_label = "Add Section"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        dst, err = _sec_load(context, collections=(SEC_COLL,))
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        coll = dst.collections[0] if (dst and dst.collections and dst.collections[0]) else None
        if coll is None:
            self.report({'ERROR'}, "У бібліотеці немає колекції HUD_Section")
            return {'CANCELLED'}
        if coll.asset_data:
            coll.asset_clear()
        coll.use_fake_user = False
        context.scene.collection.children.link(coll)
        sec = next((o for o in coll.objects if sec_is_section(o)), None)
        if sec is None:
            self.report({'ERROR'}, "У колекції немає об'єкта Section")
            return {'CANCELLED'}
        sec.matrix_world = context.scene.cursor.matrix
        for o in context.selected_objects:
            o.select_set(False)
        sec.select_set(True)
        context.view_layer.objects.active = sec
        sec_init_defaults(sec)
        context.scene.hud_section = sec
        self.report({'INFO'}, f"{sec.name} додано. Виділи деталі, Section активним → Add to Selected")
        return {'FINISHED'}


class HUD_OT_section_apply(bpy.types.Operator):
    """Підключити виділені деталі до активного Section: розріз у матеріалах + каркас (останнім у стеку)"""
    bl_idname = "hud.section_apply"
    bl_label = "Add to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return sec_get(context) is not None

    def execute(self, context):
        sec = sec_get(context)
        sec_init_defaults(sec)
        err = sec_ensure_groups(context)
        grp = bpy.data.node_groups.get(SEC_SHADER)
        if grp is None or SEC_WIRE not in bpy.data.node_groups:
            self.report({'ERROR'}, err or "Немає груп HUD_Section / GN_HUD_SectionWire")
            return {'CANCELLED'}
        objs = _sec_targets(context, sec)
        if not objs:
            self.report({'WARNING'}, "Виділи деталі (і Section активним останнім)")
            return {'CANCELLED'}
        mats = []
        for o in objs:
            for s in o.material_slots:
                m = s.material
                if m and m.node_tree and not m.name.startswith("HUD_") and m not in mats:
                    mats.append(m)
        nm = sum(1 for m in mats if sec_insert(m, sec, grp))
        nw = sum(1 for o in objs if sec_wire_add(o, sec))
        for o in objs:
            sec_cap_add(o, sec)
        sec_cap_sync(sec)
        sec_apply_slots(sec)
        sec_sync_wire_material(sec)
        sec.update_tag(refresh={'OBJECT'})
        self.report({'INFO'}, f"{sec.name}: матеріалів — {nm}, каркасів — {nw}")
        return {'FINISHED'}


class HUD_OT_section_remove(bpy.types.Operator):
    """Відключити виділені деталі від Section (без виділених деталей — від усіх)"""
    bl_idname = "hud.section_remove"
    bl_label = "Remove Section"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return sec_get(context) is not None

    def execute(self, context):
        sec = sec_get(context)
        objs = _sec_targets(context, sec)
        if objs:
            mats = {s.material for o in objs for s in o.material_slots if s.material}
        else:
            objs = list(bpy.data.objects)
            mats = set(bpy.data.materials)
        nm = sum(sec_remove_nodes(m, sec) for m in mats)
        nw = sum(sec_wire_remove(o, sec) for o in objs)
        for o in objs:
            sec_cap_remove(o, sec)
        self.report({'INFO'}, f"{sec.name}: прибрано з матеріалів — {nm}, каркасів — {nw}")
        return {'FINISHED'}


class HUD_OT_section_refresh(bpy.types.Operator):
    """Перебудувати драйвери Section і поставити каркас останнім у стеку"""
    bl_idname = "hud.section_refresh"
    bl_label = "Refresh Section"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return sec_get(context) is not None

    def execute(self, context):
        nm, nw = sec_refresh(sec_get(context))
        self.report({'INFO'}, f"Оновлено: матеріалів — {nm}, каркасів — {nw}")
        return {'FINISHED'}


class OBJECT_PT_RossSectionPanel(bpy.types.Panel):
    bl_options = {'DEFAULT_CLOSED'}
    bl_label = "HUD Section"
    bl_idname = "OBJECT_PT_ross_section"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Rost Tools'

    def draw_header(self, context):
        self.layout.label(icon='MOD_BOOLEAN')

    def draw(self, context):
        L = self.layout
        sc = context.scene
        sec = sec_get(context)
        r = L.row()
        r.scale_y = 1.5
        r.operator("hud.section_add", icon='ADD')
        box = L.box()
        if sec is not None and sec == context.active_object:
            box.label(text=sec.name, icon='RESTRICT_SELECT_OFF')
        else:
            box.prop(sc, "hud_section", text="")
        if sec is not None:
            m = sec_mod(sec)
            ids = _hud_ids(m.node_group)
            def _props(layout, items):
                c = layout.column(align=True)
                for nm, lab in items:
                    sk = _hud_sock(m, ids.get(nm))
                    if sk is not None:
                        c.prop(sk, "value", text=lab or nm)
            _props(box, (("Enable", None), ("Flip Side", None), ("Frame Opacity", None)))
            def _switch(layout, use_nm, mat_nm):
                use = _hud_sock(m, ids.get(use_nm))
                if use is None:
                    return False
                r = layout.row(align=True)
                r.prop(use, "value", text="Panel", toggle=True, invert_checkbox=True, icon='PREFERENCES')
                r.prop(use, "value", text="Material", toggle=True, icon='MATERIAL')
                if use.value:
                    mk = _hud_sock(m, ids.get(mat_nm))
                    if mk is not None:
                        layout.prop(mk, "value", text="")
                return bool(use.value)

            head, body = box.panel("sec_ghost", default_closed=True)
            head.label(text="GHOST  ·  відсічена частина", icon='GHOST_ENABLED')
            if body is not None:
                if not _switch(body, "Ghost Use Material", "Ghost Material"):
                    _props(body, (("Ghost", "Rim (контур)"), ("Ghost Strength", "Rim Strength"),
                                  ("Ghost Body", "Body (матеріал)"), ("Ghost Color", "Color"),
                                  ("Ghost Opacity", "Opacity"), ("Ghost Roughness", "Roughness"),
                                  ("Ghost Transmission", "Transmission"), ("Ghost IOR", "IOR"),
                                  ("Ghost Keep Material", "Keep Part Material")))
            head, body = box.panel("sec_wire", default_closed=True)
            head.label(text="GHOST WIRE  ·  каркас", icon='MOD_WIREFRAME')
            if body is not None:
                _props(body, (("Ghost Wire", "Opacity"), ("Wire (mm)", "Thickness (mm)"), ("Wire Angle", "Edge Angle")))
                if not _switch(body, "Wire Use Material", "Wire Material"):
                    _props(body, (("Wire Color", "Color"), ("Wire Strength", "Strength")))
            head, body = box.panel("sec_edge", default_closed=True)
            head.label(text="CUT EDGE  ·  бордер розрізу", icon='SNAP_EDGE')
            if body is not None:
                _props(body, (("Edge Width (mm)", "Width (mm)"), ("Edge Glow (mm)", "Blur (mm)")))
                if not _switch(body, "Edge Use Material", "Edge Material"):
                    _props(body, (("Edge Color", "Color"), ("Edge Strength", "Strength")))
            head, body = box.panel("sec_cap", default_closed=True)
            head.label(text="CUT FILL  ·  заливка розрізу", icon='SNAP_FACE')
            if body is not None:
                if sec.get("hud_cap") is not None:
                    cr = body.row(align=True)
                    cr.prop(sec, '["hud_cap"]', text="Real cap (mesh)", toggle=True, icon='MESH_PLANE')
                    cr.prop(sec, '["hud_cap_holes"]', text="Close gaps", toggle=True, icon='MOD_BOOLEAN')
                if not _switch(body, "Cap Use Custom", "Cap Material"):
                    _props(body, (("Cap Use Material", "Mix Part Material"), ("Cap Strength", "Strength"),
                                  ("Cap Color A", "Color A"), ("Cap Color B", "Color B"),
                                  ("Cap Stripes", "Stripes"), ("Stripe Width (mm)", "Stripe Width (mm)"),
                                  ("Stripe Angle", "Stripe Angle")))
        b = L.box()
        r = b.row(align=True)
        r.scale_y = 1.2
        r.operator("hud.section_apply", icon='SELECT_SUBTRACT')
        r.operator("hud.section_remove", text="", icon='X')
        r.operator("hud.section_refresh", text="", icon='FILE_REFRESH')
        if sec is not None:
            nm = sum(len(sec_nodes(mt, sec)) for mt in bpy.data.materials)
            nw = sum(len(sec_wire_mods(o, sec)) for o in bpy.data.objects)
            b.label(text=f"Матеріалів: {nm} · Каркасів: {nw}", icon='MATERIAL')
        else:
            b.label(text="Зроби Section активним", icon='INFO')


sec_classes = (
    HUD_OT_section_add,
    HUD_OT_section_apply,
    HUD_OT_section_remove,
    HUD_OT_section_refresh,
    OBJECT_PT_RossSectionPanel,
)


def sec_register():
    for cls in sec_classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hud_section = bpy.props.PointerProperty(
        name="Section", type=bpy.types.Object, poll=lambda self, o: sec_is_section(o))
    if _sec_wire_mat_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_sec_wire_mat_handler)


def sec_unregister():
    if _sec_wire_mat_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_sec_wire_mat_handler)
    if hasattr(bpy.types.Scene, "hud_section"):
        del bpy.types.Scene.hud_section
    for cls in reversed(sec_classes):
        bpy.utils.unregister_class(cls)


# ==============================================================================
# HUD STYLE (v3.6) — єдиний стиль на сцену
# ==============================================================================
STY_LIB = "HUD_Style.blend"
STY_COLL = "HUD_Style"
STY_GN = "GN_HUD_Style"
STY_HELPER = "HUD_StyleValue"
# стиль -> сокети елементів (шрифт/матеріали роздаються кнопкою Apply Style)
STY_PUSH = {
    "Font": ("Font",),
    "Line Material": ("Line Material", "Material", "Frame Material"),
    "Text Material": ("Text Material",),
    "Fill Material": ("Fill Material",),
}


def sty_lib_path(context):
    return os.path.join(os.path.dirname(hud_lib_path(context)), STY_LIB)


def sty_mod(o):
    if o is None:
        return None
    for m in o.modifiers:
        if m.type == 'NODES' and m.node_group and _hud_base(m.node_group.name) == STY_GN:
            return m
    return None


def sty_is_style(o):
    return o is not None and o.type == 'MESH' and sty_mod(o) is not None


def sty_get(context):
    o = context.active_object
    if sty_is_style(o):
        return o
    o = getattr(context.scene, "hud_style", None)
    if sty_is_style(o):
        return o
    return next((x for x in context.scene.objects if sty_is_style(x)), None)


def sty_styled_mods(scene):
    """Усі GN-модифікатори сцени, у яких є вхід Style (тобто стильовані HUD-елементи)."""
    res = []
    for o in scene.objects:
        for m in o.modifiers:
            if m.type == 'NODES' and m.node_group:
                ids = _hud_ids(m.node_group)
                if "HUD Style" in ids and "Use Style" in ids:
                    res.append((o, m, ids))
    return res


def sty_apply(scene, style, push=True):
    sm = sty_mod(style)
    sids = _hud_ids(sm.node_group)
    vals = {k: _hud_get(sm, sids[k]) for k in STY_PUSH if k in sids}
    n = 0
    for o, m, ids in sty_styled_mods(scene):
        if _hud_get(m, ids["HUD Style"]) is None:      # перше підключення -> стиль увімкнено
            _hud_set(m, ids["Use Style"], True)
        _hud_set(m, ids["HUD Style"], style)
        if push and _hud_get(m, ids["Use Style"]):
            for k, targets in STY_PUSH.items():
                v = vals.get(k)
                if v is None:
                    continue
                for t in targets:
                    if t in ids:
                        _hud_set(m, ids[t], v)
        o.update_tag()
        n += 1
    # каркаси Section беруть матеріал ліній
    if push and vals.get("Line Material") is not None:
        for o in scene.objects:
            for w in sec_wire_mods(o):
                wids = _hud_ids(w.node_group)
                if "Material" in wids:
                    _hud_set(w, wids["Material"], vals["Line Material"])
    return n


class HUD_OT_style_add(bpy.types.Operator):
    """Додати HUD Style (один на сцену) і підключити до нього всі HUD-елементи"""
    bl_idname = "hud.style_add"
    bl_label = "Add Style"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ex = next((x for x in context.scene.objects if sty_is_style(x)), None)
        if ex is not None:
            context.scene.hud_style = ex
            self.report({'INFO'}, f"У сцені вже є стиль: {ex.name}")
            return {'FINISHED'}
        lib = sty_lib_path(context)
        if not os.path.exists(lib):
            self.report({'ERROR'}, f"Не знайдено бібліотеку: {lib}")
            return {'CANCELLED'}
        names = ("node_groups", "materials", "fonts", "images", "objects")
        before = {n: set(x.name for x in getattr(bpy.data, n)) for n in names}
        with bpy.data.libraries.load(lib, link=False) as (src, dst):
            dst.collections = [STY_COLL] if STY_COLL in src.collections else []
        _hud_dedupe(before)
        coll = dst.collections[0] if dst.collections and dst.collections[0] else None
        if coll is None:
            self.report({'ERROR'}, "У бібліотеці немає колекції HUD_Style")
            return {'CANCELLED'}
        if coll.asset_data:
            coll.asset_clear()
        coll.use_fake_user = False
        context.scene.collection.children.link(coll)
        st = next((o for o in coll.objects if sty_is_style(o)), None)
        context.scene.hud_style = st
        n = sty_apply(context.scene, st, push=False)
        self.report({'INFO'}, f"{st.name} додано, підключено елементів: {n}")
        return {'FINISHED'}


class HUD_OT_style_apply(bpy.types.Operator):
    """Підключити всі HUD-елементи сцени до стилю і роздати шрифт/матеріали (там, де Use Style увімкнено)"""
    bl_idname = "hud.style_apply"
    bl_label = "Apply Style"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return sty_get(context) is not None

    def execute(self, context):
        n = sty_apply(context.scene, sty_get(context), push=True)
        self.report({'INFO'}, f"Стиль застосовано до елементів: {n}")
        return {'FINISHED'}


class HUD_OT_style_toggle_selected(bpy.types.Operator):
    """Увімкнути/вимкнути Use Style на виділених HUD-елементах"""
    bl_idname = "hud.style_toggle_selected"
    bl_label = "Use Style on Selected"
    bl_options = {'REGISTER', 'UNDO'}
    state: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        n = 0
        for o in context.selected_objects:
            for m in o.modifiers:
                if m.type == 'NODES' and m.node_group:
                    ids = _hud_ids(m.node_group)
                    if "Use Style" in ids:
                        _hud_set(m, ids["Use Style"], self.state)
                        n += 1
            o.update_tag()
        self.report({'INFO'}, f"Use Style = {self.state}: модифікаторів {n}")
        return {'FINISHED'}


class OBJECT_PT_RossStylePanel(bpy.types.Panel):
    bl_options = {'DEFAULT_CLOSED'}
    bl_label = "HUD Style"
    bl_idname = "OBJECT_PT_ross_style"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Rost Tools'

    def draw_header(self, context):
        self.layout.label(icon='BRUSHES_ALL')

    def draw(self, context):
        L = self.layout
        st = sty_get(context)
        if st is None:
            r = L.row(); r.scale_y = 1.5
            r.operator("hud.style_add", icon='ADD')
            return
        sm = sty_mod(st)
        ids = _hud_ids(sm.node_group)
        L.label(text=st.name, icon='BRUSHES_ALL')
        col = L.column(align=True)
        for nm in ("Line (mm)", "Thin Line (mm)", "Accent Line (mm)", "Ring Line Scale",
                   "Font Size (mm)", "Text Gap (mm)", "Text Padding (mm)",
                   "Arrow Length (mm)", "Arrow Width (mm)", "Dot Size (mm)", "Pattern Size (mm)"):
            s = _hud_sock(sm, ids.get(nm))
            if s is not None:
                col.prop(s, "value", text=nm)
        col = L.column(align=True)
        for nm in ("Font", "Line Material", "Text Material", "Fill Material"):
            s = _hud_sock(sm, ids.get(nm))
            if s is not None:
                col.prop(s, "value", text=nm)
        r = L.row(); r.scale_y = 1.3
        r.operator("hud.style_apply", icon='CHECKMARK')
        r = L.row(align=True)
        r.operator("hud.style_toggle_selected", text="Selected: Style On", icon='LINKED').state = True
        r.operator("hud.style_toggle_selected", text="Own", icon='UNLINKED').state = False
        n = len(sty_styled_mods(context.scene))
        L.label(text=f"Стильованих модифікаторів у сцені: {n}", icon='INFO')


sty_classes = (HUD_OT_style_add, HUD_OT_style_apply, HUD_OT_style_toggle_selected, OBJECT_PT_RossStylePanel)


def sty_register():
    for cls in sty_classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hud_style = bpy.props.PointerProperty(
        name="HUD Style", type=bpy.types.Object, poll=lambda self, o: sty_is_style(o))


def sty_unregister():
    if hasattr(bpy.types.Scene, "hud_style"):
        del bpy.types.Scene.hud_style
    for cls in reversed(sty_classes):
        bpy.utils.unregister_class(cls)


# ==============================================================================
# HUD FUI (v3.7) — Tick Scale, Brackets, Counter, Bars/Sliders
# ==============================================================================
FUI_LIB = "HUD_FUI.blend"
FUI_KINDS = (
    ("TICK", "Tick Scale", "Шкала з рисками, числами і покажчиком", "HUD_TickScale", "GN_HUD_TickScale", 'MOD_TIME'),
    ("BRACKETS", "Brackets", "Кутові дужки / рамка (активний об'єкт -> Fit To)", "HUD_Brackets", "GN_HUD_Brackets", 'SELECT_SET'),
    ("COUNTER", "Counter", "Лічильник чисел", "HUD_Counter", "GN_HUD_Counter", 'LINENUMBERS_ON'),
    ("BARS", "Bars / Sliders", "Bar, Segments, Equalizer, Slider", "HUD_Bars", "GN_HUD_Bars", 'ALIGN_JUSTIFY'),
)
FUI_GROUPS = tuple(k[4] for k in FUI_KINDS) + ("GN_HUD_Style",)
FUI_CAM_CON = "HUD Face Camera"


def fui_lib_path(context):
    return os.path.join(os.path.dirname(hud_lib_path(context)), FUI_LIB)


def _fui_hook_style(context, obj):
    st = sty_get(context) if 'sty_get' in globals() else None
    if st is None:
        return
    for m in obj.modifiers:
        if m.type == 'NODES' and m.node_group:
            ids = _hud_ids(m.node_group)
            if "HUD Style" in ids and "Use Style" in ids:
                _hud_set(m, ids["Use Style"], True)
                _hud_set(m, ids["HUD Style"], st)


class HUD_OT_fui_add(bpy.types.Operator):
    """Додати FUI-елемент з бібліотеки в 3D-курсор"""
    bl_idname = "hud.fui_add"
    bl_label = "Add FUI Element"
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[(k[0], k[1], k[2]) for k in FUI_KINDS])

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        spec = next(k for k in FUI_KINDS if k[0] == self.kind)
        lib = fui_lib_path(context)
        if not os.path.exists(lib):
            self.report({'ERROR'}, f"Не знайдено бібліотеку: {lib}")
            return {'CANCELLED'}
        target = context.active_object if (context.active_object and context.active_object.select_get()) else None
        names = ("node_groups", "materials", "fonts", "images", "objects")
        before = {n: set(x.name for x in getattr(bpy.data, n)) for n in names}
        with bpy.data.libraries.load(lib, link=False) as (src, dst):
            dst.collections = [spec[3]] if spec[3] in src.collections else []
        _hud_dedupe(before)
        coll = dst.collections[0] if dst.collections and dst.collections[0] else None
        if coll is None:
            self.report({'ERROR'}, f"У бібліотеці немає {spec[3]}")
            return {'CANCELLED'}
        if coll.asset_data:
            coll.asset_clear()
        coll.use_fake_user = False
        context.scene.collection.children.link(coll)
        obj = coll.objects[0]
        obj.matrix_world = context.scene.cursor.matrix
        if self.kind == "BRACKETS" and target is not None and target.type in {'MESH', 'CURVE', 'FONT'} \
                and not hud_is_callout(target):
            m = obj.modifiers[0]
            ids = _hud_ids(m.node_group)
            _hud_set(m, ids["Fit To"], target)
            obj.location = target.matrix_world.translation
        _fui_hook_style(context, obj)
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        self.report({'INFO'}, f"{obj.name} додано")
        return {'FINISHED'}


class HUD_OT_face_camera(bpy.types.Operator):
    """Повернути виділені HUD-елементи до камери сцени (Copy Rotation) або прибрати це"""
    bl_idname = "hud.face_camera"
    bl_label = "Face Camera"
    bl_options = {'REGISTER', 'UNDO'}
    state: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        cam = context.scene.camera
        if self.state and cam is None:
            self.report({'ERROR'}, "У сцені немає камери")
            return {'CANCELLED'}
        n = 0
        for o in context.selected_objects:
            c = o.constraints.get(FUI_CAM_CON)
            if self.state:
                if c is None:
                    c = o.constraints.new('COPY_ROTATION')
                    c.name = FUI_CAM_CON
                c.target = cam
            elif c is not None:
                o.constraints.remove(c)
            n += 1
        self.report({'INFO'}, f"Face Camera = {self.state}: {n}")
        return {'FINISHED'}


class HUD_OT_preview_all(bpy.types.Operator):
    """Показати всі HUD-елементи сцени повністю незалежно від кадру (Preview Full) або повернути анімацію"""
    bl_idname = "hud.preview_all"
    bl_label = "Preview All"
    bl_options = {'REGISTER', 'UNDO'}
    state: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        n = 0
        for o in context.scene.objects:
            for m in o.modifiers:
                if m.type == 'NODES' and m.node_group:
                    ids = _hud_ids(m.node_group)
                    if "Preview Full" in ids:
                        _hud_set(m, ids["Preview Full"], self.state)
                        n += 1
            o.update_tag()
        self.report({'INFO'}, f"Preview Full = {self.state}: модифікаторів {n}")
        return {'FINISHED'}


class OBJECT_PT_RossFUIPanel(bpy.types.Panel):
    bl_options = {'DEFAULT_CLOSED'}
    bl_label = "HUD FUI"
    bl_idname = "OBJECT_PT_ross_fui"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Rost Tools'

    def draw_header(self, context):
        self.layout.label(icon='MOD_TIME')

    def draw(self, context):
        L = self.layout
        r = L.row(align=True)
        r.operator("hud.preview_all", text="Preview All: On", icon='HIDE_OFF').state = True
        r.operator("hud.preview_all", text="Off", icon='TIME').state = False
        col = L.column(align=True)
        col.scale_y = 1.3
        for k in FUI_KINDS:
            col.operator("hud.fui_add", text=k[1], icon=k[5]).kind = k[0]
        L.label(text="Brackets: спершу виділи об'єкт — обгорнуть його", icon='INFO')
        r = L.row(align=True)
        r.operator("hud.face_camera", text="Face Camera", icon='CAMERA_DATA').state = True
        r.operator("hud.face_camera", text="", icon='X').state = False


fui_classes = (HUD_OT_fui_add, HUD_OT_face_camera, HUD_OT_preview_all, OBJECT_PT_RossFUIPanel)


def fui_register():
    for cls in fui_classes:
        bpy.utils.register_class(cls)


def fui_unregister():
    for cls in reversed(fui_classes):
        bpy.utils.unregister_class(cls)



# ==============================================================================
# HUD VOLUME CUT (v3.9) — розріз об'ємом: Sphere / Box / Cylinder / Custom Mesh
# ==============================================================================
# Архітектура:
#  * Різак (cutter) = порожній меш з модифікатором GN_HUD_VolumeCut: параметри + превʼю форми.
#  * Шейдер HUD_VolumeCut (копія HUD_Section, площина замінена формулою «всередині» SDF):
#    Ghost / Cut Edge / fake-cap рахуються в матеріалах деталей, без геометрії (примітиви).
#  * Модифікатор GN_HUD_VolumeCutPart на кожній деталі: ОДИН Boolean (деталь ∩ тіло різака),
#    з нього кап-меш (грані на поверхні різака) і каркас привида (ребра всередині).
VC_LIB = "HUD_VolumeCut.blend"
VC_MOD = "HUD_VolumeCut"
VC_SHAPES = (("Sphere", 'MESH_UVSPHERE'), ("Box", 'MESH_CUBE'), ("Cylinder", 'MESH_CYLINDER'), ("Custom", 'OBJECT_DATA'))
VC_PART_MAP = {"Shape": "Shape", "Radius (mm)": "Radius (mm)", "Size X (mm)": "Size X (mm)",
               "Size Y (mm)": "Size Y (mm)", "Size Z (mm)": "Size Z (mm)", "Resolution": "Resolution",
               "Flip Side": "Flip Side", "Hole Tolerant": "Close Gaps", "Real Cap": "Real Cap",
               "Opacity": "Ghost Wire", "Thickness (mm)": "Wire (mm)", "Angle": "Wire Angle"}


def vc_lib_path(context):
    return os.path.join(os.path.dirname(hud_lib_path(context)), VC_LIB)


def vc_is_cutter(o):
    m = sec_mod(o)
    return o is not None and o.type == 'MESH' and m is not None and _hud_base(m.node_group.name) == VC_GN


def vc_get(context):
    o = context.active_object
    if vc_is_cutter(o):
        return o
    o = getattr(context.scene, "hud_volcut", None)
    return o if vc_is_cutter(o) else None


def vc_ensure_groups(context):
    missing = [g for g in VC_GROUPS if g not in bpy.data.node_groups]
    if not missing:
        return None
    lib = vc_lib_path(context)
    if not os.path.exists(lib):
        return f"Не знайдено бібліотеку: {lib}"
    with bpy.data.libraries.load(lib, link=False) as (src, dst):
        dst.node_groups = [g for g in missing if g in src.node_groups]
    return None


def vc_init_defaults(cut):
    m = sec_mod(cut)
    for it in _hud_inputs(m.node_group):
        if it.socket_type in ('NodeSocketObject', 'NodeSocketMaterial') or not hasattr(it, "default_value"):
            continue
        _hud_set(m, it.identifier, it.default_value)
    cut["hud_v38"] = 1
    cut["hud_v38b"] = 1
    ids = _hud_ids(m.node_group)
    fm = bpy.data.materials.get("HUD_Line")
    if fm is not None and "Frame Material" in ids:
        _hud_set(m, ids["Frame Material"], fm)


def vc_new_cutter(context, shape=0, custom=None):
    err = vc_ensure_groups(context)
    if err:
        return None, err
    n = 1
    base = "VolCut"
    name = base
    while name in bpy.data.objects:
        name = f"{base}.{n:03d}"
        n += 1
    me = bpy.data.meshes.new(name)
    cut = bpy.data.objects.new(name, me)
    context.collection.objects.link(cut)
    md = cut.modifiers.new("GN_HUD_VolumeCut", 'NODES')
    md.node_group = bpy.data.node_groups[VC_GN]
    cut.matrix_world = context.scene.cursor.matrix
    vc_init_defaults(cut)
    ids = _hud_ids(md.node_group)
    _hud_set(md, ids["Shape"], int(shape))
    if custom is not None:
        _hud_set(md, ids["Custom Object"], custom)
    cut["hud_volcut"] = 1
    return cut, None


def vc_part_mods(obj, cut=None):
    res = []
    for w in obj.modifiers:
        if w.type == 'NODES' and w.node_group and _hud_base(w.node_group.name) == VC_PART:
            if cut is None or _hud_get(w, _hud_ids(w.node_group).get("Cutter")) == cut:
                res.append(w)
    return res


def vc_part_drivers(obj, w, cut):
    _sec_clear_obj_drivers(obj, w)
    m = sec_mod(cut)
    cids = _hud_ids(m.node_group)
    wids = _hud_ids(w.node_group)
    for dst, src in VC_PART_MAP.items():
        if dst in wids and src in cids:
            _hud_driver(obj, f'modifiers["{w.name}"].properties.inputs.{wids[dst]}.value', cut, _sec_path(m, cids, src))
    for prop in ("show_viewport", "show_render"):
        fc = obj.driver_add(f'modifiers["{w.name}"].{prop}')
        d = fc.driver
        for v in list(d.variables):
            d.variables.remove(v)
        d.type = 'SCRIPTED'
        d.expression = "en"
        _hud_var(d, "en", cut, _sec_path(m, cids, "Enable"))


def vc_part_add(obj, cut):
    if obj.type != 'MESH':
        return False
    have = vc_part_mods(obj, cut)
    g = bpy.data.node_groups[VC_PART]
    if have:
        w = have[0]
        new = False
    else:
        w = obj.modifiers.new(f"{VC_MOD} · {cut.name}", 'NODES')
        w.node_group = g
        wids = _hud_ids(g)
        for it in _hud_inputs(g):
            if it.socket_type not in ('NodeSocketObject', 'NodeSocketMaterial') and hasattr(it, "default_value"):
                _hud_set(w, it.identifier, it.default_value)
        _hud_set(w, wids["Cutter"], cut)
        new = True
    vc_part_drivers(obj, w, cut)
    return new


def vc_part_remove(obj, cut=None):
    cnt = 0
    for w in vc_part_mods(obj, cut):
        _sec_clear_obj_drivers(obj, w)
        obj.modifiers.remove(w)
        cnt += 1
    return cnt


def vc_sync(cut):
    # матеріали кап-меша / каркаса + Custom Object -> усі модифікатори деталей цього різака
    m = sec_mod(cut)
    cids = _hud_ids(m.node_group)
    capm = sec_cap_material(cut)
    wirem = sec_wire_material(cut) or bpy.data.materials.get("HUD_Line")
    cus = _hud_get(m, cids.get("Custom Object"))
    n = 0
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        for w in vc_part_mods(o, cut):
            wids = _hud_ids(w.node_group)
            for nm, v in (("Cap Material", capm), ("Wire Material", wirem), ("Custom Object", cus)):
                if nm in wids and _hud_get(w, wids[nm]) != v:
                    _hud_set(w, wids[nm], v)
            n += 1
    return n


def vc_refresh(cut):
    sec_apply_slots(cut, rebuild=True)
    nm = 0
    for mat in bpy.data.materials:
        for g, _s in sec_nodes(mat, cut):
            sec_build_node_drivers(mat, g, cut)
            mat.update_tag()
            nm += 1
    npart = 0
    for o in bpy.data.objects:
        for w in vc_part_mods(o, cut):
            vc_part_drivers(o, w, cut)
            o.update_tag()
            npart += 1
    vc_sync(cut)
    cut.update_tag(refresh={'OBJECT'})
    return nm, npart


def vc_targets(context, cut):
    return [o for o in context.selected_objects
            if o != cut and not vc_is_cutter(o) and not sec_is_section(o) and not hud_is_callout(o)
            and o != _hud_get(sec_mod(cut), _hud_ids(sec_mod(cut).node_group).get("Custom Object"))
            and o.type == 'MESH']


class HUD_OT_vc_add(bpy.types.Operator):
    """Додати Volume Cut (різак: сфера / куб / циліндр / довільний меш) у 3D-курсор"""
    bl_idname = "hud.vc_add"
    bl_label = "Add Volume Cut"
    bl_options = {'REGISTER', 'UNDO'}
    shape: bpy.props.IntProperty(default=0, min=0, max=3)

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        custom = None
        if self.shape == 3:
            custom = context.active_object
            if custom is None or custom.type != 'MESH' or vc_is_cutter(custom):
                self.report({'WARNING'}, "Custom: зроби активним закритий меш-різак")
                return {'CANCELLED'}
        cut, err = vc_new_cutter(context, self.shape, custom)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        if custom is not None:
            custom.hide_render = True
            custom.display_type = 'WIRE'
        for o in context.selected_objects:
            o.select_set(False)
        cut.select_set(True)
        context.view_layer.objects.active = cut
        context.scene.hud_volcut = cut
        self.report({'INFO'}, f"{cut.name} додано. Виділи деталі, різак активним → Add to Selected")
        return {'FINISHED'}


class HUD_OT_vc_apply(bpy.types.Operator):
    """Підключити виділені деталі до активного різака: Ghost/Edge у матеріалах + кап-меш і каркас (GN)"""
    bl_idname = "hud.vc_apply"
    bl_label = "Add to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return vc_get(context) is not None

    def execute(self, context):
        cut = vc_get(context)
        err = vc_ensure_groups(context)
        grp = bpy.data.node_groups.get(VC_SHADER)
        if grp is None or VC_PART not in bpy.data.node_groups:
            self.report({'ERROR'}, err or "Немає груп HUD_VolumeCut / GN_HUD_VolumeCutPart")
            return {'CANCELLED'}
        objs = vc_targets(context, cut)
        if not objs:
            self.report({'WARNING'}, "Виділи деталі (і різак активним останнім)")
            return {'CANCELLED'}
        mats = []
        for o in objs:
            for s in o.material_slots:
                mt = s.material
                if mt and mt.node_tree and not mt.name.startswith("HUD_") and mt not in mats:
                    mats.append(mt)
        nm = sum(1 for mt in mats if sec_insert(mt, cut, grp))
        npart = sum(1 for o in objs if vc_part_add(o, cut))
        vc_sync(cut)
        sec_apply_slots(cut)
        cut.update_tag(refresh={'OBJECT'})
        self.report({'INFO'}, f"{cut.name}: матеріалів — {nm}, деталей — {npart}")
        return {'FINISHED'}


class HUD_OT_vc_remove(bpy.types.Operator):
    """Відключити виділені деталі від різака (без виділених — від усіх)"""
    bl_idname = "hud.vc_remove"
    bl_label = "Remove Volume Cut"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return vc_get(context) is not None

    def execute(self, context):
        cut = vc_get(context)
        objs = vc_targets(context, cut)
        if objs:
            mats = {s.material for o in objs for s in o.material_slots if s.material}
        else:
            objs = list(bpy.data.objects)
            mats = set(bpy.data.materials)
        nm = sum(sec_remove_nodes(mt, cut) for mt in mats)
        npart = sum(vc_part_remove(o, cut) for o in objs)
        self.report({'INFO'}, f"{cut.name}: прибрано з матеріалів — {nm}, деталей — {npart}")
        return {'FINISHED'}


class HUD_OT_vc_refresh(bpy.types.Operator):
    """Перебудувати драйвери, слоти матеріалів і матеріали кап-меша / каркаса"""
    bl_idname = "hud.vc_refresh"
    bl_label = "Refresh Volume Cut"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return vc_get(context) is not None

    def execute(self, context):
        nm, npart = vc_refresh(vc_get(context))
        self.report({'INFO'}, f"Оновлено: матеріалів — {nm}, деталей — {npart}")
        return {'FINISHED'}


class HUD_OT_vc_shape(bpy.types.Operator):
    """Змінити форму активного різака"""
    bl_idname = "hud.vc_shape"
    bl_label = "Shape"
    bl_options = {'REGISTER', 'UNDO'}
    shape: bpy.props.IntProperty(default=0, min=0, max=3)

    @classmethod
    def poll(cls, context):
        return vc_get(context) is not None

    def execute(self, context):
        cut = vc_get(context)
        m = sec_mod(cut)
        _hud_set(m, _hud_ids(m.node_group)["Shape"], self.shape)
        cut.update_tag()
        return {'FINISHED'}


class OBJECT_PT_RossVolumeCutPanel(bpy.types.Panel):
    bl_options = {'DEFAULT_CLOSED'}
    bl_label = "HUD Volume Cut"
    bl_idname = "OBJECT_PT_ross_volcut"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Rost Tools'

    def draw_header(self, context):
        self.layout.label(icon='MESH_UVSPHERE')

    def draw(self, context):
        L = self.layout
        sc = context.scene
        cut = vc_get(context)
        r = L.row(align=True)
        r.scale_y = 1.5
        for i, (nm, ic) in enumerate(VC_SHAPES):
            op = r.operator("hud.vc_add", text="" if i == 3 else nm, icon=ic)
            op.shape = i
        box = L.box()
        if cut is not None and cut == context.active_object:
            box.label(text=cut.name, icon='RESTRICT_SELECT_OFF')
        else:
            box.prop(sc, "hud_volcut", text="")
        if cut is not None:
            m = sec_mod(cut)
            ids = _hud_ids(m.node_group)

            def _props(layout, items):
                c = layout.column(align=True)
                for nm, lab in items:
                    sk = _hud_sock(m, ids.get(nm))
                    if sk is not None:
                        c.prop(sk, "value", text=lab or nm)

            cur = _hud_get(m, ids["Shape"])
            sr = box.row(align=True)
            for i, (nm, ic) in enumerate(VC_SHAPES):
                b = sr.operator("hud.vc_shape", text=nm if i < 3 else "Custom", depress=(cur == i))
                b.shape = i
            if cur == 0:
                _props(box, (("Radius (mm)", None),))
            elif cur == 1:
                _props(box, (("Size X (mm)", "Width X (mm)"), ("Size Y (mm)", "Width Y (mm)"), ("Size Z (mm)", "Height Z (mm)")))
            elif cur == 2:
                _props(box, (("Radius (mm)", None), ("Size Z (mm)", "Height (mm)")))
            else:
                _props(box, (("Custom Object", "Cutter Mesh"),))
            _props(box, (("Enable", None), ("Flip Side", "Cut Outside (keep inside)"), ("Frame Opacity", None)))

            def _switch(layout, use_nm, mat_nm):
                use = _hud_sock(m, ids.get(use_nm))
                if use is None:
                    return False
                rr = layout.row(align=True)
                rr.prop(use, "value", text="Panel", toggle=True, invert_checkbox=True, icon='PREFERENCES')
                rr.prop(use, "value", text="Material", toggle=True, icon='MATERIAL')
                if use.value:
                    mk = _hud_sock(m, ids.get(mat_nm))
                    if mk is not None:
                        layout.prop(mk, "value", text="")
                return bool(use.value)

            head, body = box.panel("vc_ghost", default_closed=True)
            head.label(text="GHOST  ·  відсічена частина", icon='GHOST_ENABLED')
            if body is not None:
                if not _switch(body, "Ghost Use Material", "Ghost Material"):
                    _props(body, (("Ghost", "Rim (контур)"), ("Ghost Strength", "Rim Strength"),
                                  ("Ghost Body", "Body (матеріал)"), ("Ghost Color", "Color"),
                                  ("Ghost Opacity", "Opacity"), ("Ghost Roughness", "Roughness"),
                                  ("Ghost Transmission", "Transmission"), ("Ghost IOR", "IOR"),
                                  ("Ghost Keep Material", "Keep Part Material")))
            head, body = box.panel("vc_wire", default_closed=True)
            head.label(text="GHOST WIRE  ·  каркас", icon='MOD_WIREFRAME')
            if body is not None:
                _props(body, (("Ghost Wire", "Opacity"), ("Wire (mm)", "Thickness (mm)"), ("Wire Angle", "Edge Angle")))
                if not _switch(body, "Wire Use Material", "Wire Material"):
                    _props(body, (("Wire Color", "Color"), ("Wire Strength", "Strength")))
            head, body = box.panel("vc_edge", default_closed=True)
            head.label(text="CUT EDGE  ·  бордер розрізу", icon='SNAP_EDGE')
            if body is not None:
                _props(body, (("Edge Width (mm)", "Width (mm)"), ("Edge Glow (mm)", "Blur (mm)")))
                if not _switch(body, "Edge Use Material", "Edge Material"):
                    _props(body, (("Edge Color", "Color"), ("Edge Strength", "Strength")))
            head, body = box.panel("vc_cap", default_closed=True)
            head.label(text="CUT FILL  ·  заливка розрізу", icon='SNAP_FACE')
            if body is not None:
                _props(body, (("Real Cap", "Real cap (mesh)"), ("Close Gaps", "Close gaps (Exact)")))
                if not _switch(body, "Cap Use Custom", "Cap Material"):
                    _props(body, (("Cap Use Material", "Mix Part Material"), ("Cap Strength", "Strength"),
                                  ("Cap Color A", "Color A"), ("Cap Color B", "Color B"),
                                  ("Cap Stripes", "Stripes"), ("Stripe Width (mm)", "Stripe Width (mm)"),
                                  ("Stripe Angle", "Stripe Angle")))
        b = L.box()
        r = b.row(align=True)
        r.scale_y = 1.2
        r.operator("hud.vc_apply", icon='SELECT_SUBTRACT')
        r.operator("hud.vc_remove", text="", icon='X')
        r.operator("hud.vc_refresh", text="", icon='FILE_REFRESH')
        if cut is not None:
            nm = sum(len(sec_nodes(mt, cut)) for mt in bpy.data.materials)
            npart = sum(len(vc_part_mods(o, cut)) for o in bpy.data.objects)
            b.label(text=f"Матеріалів: {nm} · Деталей: {npart}", icon='MATERIAL')
        else:
            b.label(text="Зроби різак активним", icon='INFO')


vc_classes = (HUD_OT_vc_add, HUD_OT_vc_apply, HUD_OT_vc_remove, HUD_OT_vc_refresh, HUD_OT_vc_shape,
              OBJECT_PT_RossVolumeCutPanel)


def vc_register():
    for cls in vc_classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hud_volcut = bpy.props.PointerProperty(
        name="Volume Cut", type=bpy.types.Object, poll=lambda self, o: vc_is_cutter(o))


def vc_unregister():
    if hasattr(bpy.types.Scene, "hud_volcut"):
        del bpy.types.Scene.hud_volcut
    for cls in reversed(vc_classes):
        bpy.utils.unregister_class(cls)


# ==============================================================================
# РЕЄСТРАЦІЯ
# ==============================================================================
classes = (
    FX_OT_CreateNewInstance,
    FX_OT_ApplyMask,
    FX_OT_SwitchMode,
    FX_OT_RemoveMask,
    OBJECT_OT_ApplyProximitySetup,
    OBJECT_OT_ClearVisibleMaterialSlots,
    OBJECT_OT_ClearAndDelta,
    OBJECT_OT_CadAutoRig,
    OBJECT_PT_RossToolsPanel,
)

# ======================= Rost Light Rig (з rost_light_rig.py 1.1.0) =======================
# Rost Light Rig — one armature with a FIXED set of light slots (same channels in every action).
# Slots: MAIN 7 area (shape switchable), ADD 6 area, SPOT 4, POINT 4.
# Everything that defines a light setup lives on the source bone as keyable custom properties
# (enabled, on, exposure, temperature, spread / cone / blend, shape, size, size_y, radius) and on the
# slider bones (local X) — so an action applied to another instance of the rig reproduces the setup,
# including which slots are enabled.
# Lamp objects stay selectable: colour, power and shader nodes are free; driven fields are purple.


import bpy, math, os, json
from bpy.app.handlers import persistent
from mathutils import Vector, Matrix

TRAVEL = 0.15            # slider travel each side (m, bone local X)
EXP_STOPS = 4.0          # stops at full travel
TEMP_RANGE = 3800.0      # K at full travel
SPREAD_RANGE = 90.0      # deg at full travel
CONE_RANGE = 60.0        # deg at full travel
WGT_MARGIN = 1.15        # area widget is this much bigger than the lamp
TGT_DOME = 1.25          # targets sit on a dome (half sphere on the floor) of model_radius * this, on the source aim line
SLOT_COLORS = ["THEME%02d" % i for i in (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)]
ACTION_SLOT = "LightRig"
SHAPES = ("SQUARE", "RECTANGLE", "DISK", "ELLIPSE")
SHAPE_LABELS = ("Square", "Rect", "Disk", "Ellipse")
ROWS = {
    "AREA":  (("EXP", 0.07, "diamond"), ("TEMP", 0.0, "circle"), ("SPREAD", -0.07, "triangle")),
    "SPOT":  (("EXP", 0.07, "diamond"), ("TEMP", 0.0, "circle"), ("CONE", -0.07, "triangle")),
    "POINT": (("EXP", 0.035, "diamond"), ("TEMP", -0.035, "circle")),
}
GROUPS = (("MAIN", "Main"), ("ADD", "Additional"), ("SPOT", "Spots"), ("POINT", "Points"))
COLORS = dict(src="THEME09", tgt="THEME04", sld="THEME03", root="THEME01")
TYPE_ICON = {"AREA": "LIGHT_AREA", "SPOT": "LIGHT_SPOT", "POINT": "LIGHT_POINT"}


# ---------------- slot set ----------------
def _slot(name, typ, group, pos, shape="DISK", size=1.0, size_y=1.0, energy=100.0, enabled=False, **kw):
    d = dict(name=name, type=typ, group=group, pos=pos, shape=shape, size=size, size_y=size_y,
             energy=energy, enabled=enabled)
    d.update(kw)
    return d

def default_slots():
    # positions relative to the model centre, for a model of radius ~0.9 m (scaled by the real radius)
    S = [
        _slot("Key", "AREA", "MAIN", (-1.6, -2.0, 1.9), "DISK", 1.2, energy=200, enabled=True),
        _slot("Fill", "AREA", "MAIN", (2.2, -1.2, 1.0), "DISK", 2.0, energy=50, enabled=True),
        _slot("Rim", "AREA", "MAIN", (0.8, 1.6, 2.2), "DISK", 1.0, energy=250, enabled=True),
        _slot("Kicker", "AREA", "MAIN", (-1.8, 1.5, 0.9), "RECTANGLE", 0.5, 1.5, 150),
        _slot("Top", "AREA", "MAIN", (0.0, 0.2, 2.6), "RECTANGLE", 1.2, 1.2, 150, enabled=True),
        _slot("Strip_L", "AREA", "MAIN", (-2.0, -0.4, 0.1), "RECTANGLE", 0.25, 2.0, 100),
        _slot("Strip_R", "AREA", "MAIN", (2.0, -0.4, 0.1), "RECTANGLE", 0.25, 2.0, 100),
    ]
    for i in range(6):
        a = math.radians(30 + 60 * i)
        S.append(_slot(f"Add_{i + 1}", "AREA", "ADD", (2.4 * math.cos(a), 2.4 * math.sin(a), 1.2 + 0.4 * (i % 2)),
                       "DISK", 0.5, energy=100))
    for i in range(4):
        a = math.radians(45 + 90 * i)
        S.append(_slot(f"Spot_{i + 1}", "SPOT", "SPOT", (2.6 * math.cos(a), 2.6 * math.sin(a), 2.6),
                       energy=300, cone=40.0, blend=0.15, radius=0.05))
    for i in range(4):
        a = math.radians(90 * i)
        S.append(_slot(f"Point_{i + 1}", "POINT", "POINT", (1.5 * math.cos(a), 1.5 * math.sin(a), 1.2),
                       energy=100, radius=0.1))
    return S


# ---------------- widgets (shared, unit size) ----------------
def _circle(r, n=32, plane="XZ", c=(0, 0, 0)):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n; u, v = r * math.cos(a), r * math.sin(a)
        p = {"XZ": (u, 0, v), "XY": (u, v, 0), "YZ": (0, u, v)}[plane]
        out.append((p[0] + c[0], p[1] + c[1], p[2] + c[2]))
    return out

def _loop(V, E, pts, closed=True):
    s = len(V); V += pts; n = len(pts)
    E += [(s + i, s + (i + 1) % n) for i in range(n if closed else n - 1)]

def _wgt(name, V, E, col):
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry(); me.from_pydata(V, E, []); me.update()
    o = bpy.data.objects.get(name) or bpy.data.objects.new(name, me)
    if o.name not in col.objects: col.objects.link(o)
    return o

def make_widgets(col, root_radius):
    W = {}
    V, E = [], []; _loop(V, E, [(x / 2, 0, z / 2) for x, _, z in _circle(1.0, 40)]); _loop(V, E, [(0, 0, 0), (0, 0.25, 0)], False)
    W["disk"] = _wgt("WGT_LGT_Disk", V, E, col)
    V, E = [], []; _loop(V, E, [(-0.5, 0, -0.5), (0.5, 0, -0.5), (0.5, 0, 0.5), (-0.5, 0, 0.5)]); _loop(V, E, [(0, 0, 0), (0, 0.25, 0)], False)
    W["rect"] = _wgt("WGT_LGT_Rect", V, E, col)
    V, E = [], []
    _loop(V, E, _circle(0.06, 16)); _loop(V, E, _circle(0.2, 24, c=(0, 0.3, 0)))
    for k in (0, 4, 8, 12): _loop(V, E, [_circle(0.06, 16)[k], _circle(0.2, 16, c=(0, 0.3, 0))[k]], False)
    W["spot"] = _wgt("WGT_LGT_Spot", V, E, col)
    V, E = [], []
    for pl in ("XY", "XZ", "YZ"): _loop(V, E, _circle(0.1, 20, pl))
    for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        _loop(V, E, [tuple(0.13 * x for x in d), tuple(0.22 * x for x in d)], False)
    W["point"] = _wgt("WGT_LGT_Point", V, E, col)
    V, E = [], []
    for pl in ("XY", "XZ", "YZ"): _loop(V, E, _circle(0.05, 24, pl))
    W["tgt"] = _wgt("WGT_LGT_Target", V, E, col)
    V, E = [], []; _loop(V, E, [(0, 0, 0), (0, 1, 0)], False)
    W["line"] = _wgt("WGT_LGT_Line", V, E, col)
    V, E = [], []
    _loop(V, E, _circle(root_radius, 64, "XY"))
    _loop(V, E, [(0, -root_radius, 0), (0, -root_radius - 0.35, 0)], False)
    _loop(V, E, [(-0.12, -root_radius - 0.2, 0), (0, -root_radius - 0.35, 0), (0.12, -root_radius - 0.2, 0)], False)
    W["root"] = _wgt("WGT_LGT_Root", V, E, col)
    for typ in ("AREA", "POINT"):
        V, E = [], []
        for _, z, _ in ROWS[typ]:
            _loop(V, E, [(-TRAVEL, 0, z), (TRAVEL, 0, z)], False)
            for x in (-TRAVEL, 0.0, TRAVEL):
                k = 0.012 if x else 0.02
                _loop(V, E, [(x, 0, z - k), (x, 0, z + k)], False)
        W["panel_" + typ] = _wgt(f"WGT_LGT_Panel{len(ROWS[typ])}", V, E, col)
    W["panel_SPOT"] = W["panel_AREA"]
    s = 0.022
    V, E = [], []; _loop(V, E, [(0, 0, -s), (s, 0, 0), (0, 0, s), (-s, 0, 0)]); W["diamond"] = _wgt("WGT_LGT_Slider_diamond", V, E, col)
    V, E = [], []; _loop(V, E, _circle(s * 0.8, 16)); W["circle"] = _wgt("WGT_LGT_Slider_circle", V, E, col)
    V, E = [], []; _loop(V, E, [(-s, 0, -s * 0.8), (s, 0, -s * 0.8), (0, 0, s)]); W["triangle"] = _wgt("WGT_LGT_Slider_triangle", V, E, col)
    return W

def area_widget_name(shape_index):
    return "WGT_LGT_Disk" if int(shape_index) in (2, 3) else "WGT_LGT_Rect"


# ---------------- helpers ----------------
def _up(d):
    return Vector((0, 1, 0)) if abs(d.z) > 0.95 else Vector((0, 0, 1))

def _drv(idb, path, expr, variables, index=None):
    # variables: (name, "PROP", id_type, id, data_path) | (name, "LOCX", rig, bone_name)
    try:
        if index is None: idb.driver_remove(path)
        else: idb.driver_remove(path, index)
    except Exception:
        pass
    fc = idb.driver_add(path) if index is None else idb.driver_add(path, index)
    d = fc.driver; d.type = 'SCRIPTED'
    for v in variables:
        var = d.variables.new(); var.name = v[0]
        if v[1] == "PROP":
            var.type = 'SINGLE_PROP'; t = var.targets[0]
            t.id_type = v[2]; t.id = v[3]; t.data_path = v[4]
        else:
            var.type = 'TRANSFORMS'; t = var.targets[0]
            t.id = v[2]; t.bone_target = v[3]; t.transform_type = 'LOC_X'; t.transform_space = 'LOCAL_SPACE'
    d.expression = expr
    return fc

def _prop(pb, key, val, **ui):
    pb[key] = val
    try:
        pb.id_properties_ui(key).update(**ui)
    except Exception:
        pass
    try:
        pb.property_overridable_library_set(f'["{key}"]', True)
    except Exception:
        pass

def _bcoll(arm, name):
    return arm.collections.get(name) or arm.collections.new(name)

def _find_lc(lc, col):
    if lc.collection == col: return lc
    for ch in lc.children:
        x = _find_lc(ch, col)
        if x: return x

def is_rig(ob):
    return ob is not None and ob.type == 'ARMATURE' and bool(ob.get("rost_lightrig") or ob.get("exm_lightrig"))

def slot_bones(rig, group=None):
    return [pb for pb in rig.pose.bones if pb.get("lgt_type") and (group is None or pb.get("lgt_group") == group)]

def slot_of(rig, bone_name):
    best = None
    for pb in slot_bones(rig):
        if bone_name == pb.name or bone_name.startswith(pb.name + "_"):
            if best is None or len(pb.name) > len(best.name): best = pb
    return best

def dome_target(src, aim, dome_c, R, floor_z):
    # first hit of the aim ray with the dome (sphere radius R on the floor centre, upper half)
    a = Vector(aim).normalized(); o = Vector(src) - dome_c
    b = a.dot(o); cc = o.dot(o) - R * R; disc = b * b - cc
    hit = None
    if disc >= 0:
        r = math.sqrt(disc)
        for t in ((-b - r, -b + r) if cc > 0 else (-b + r,)):
            if t > 1e-4:
                p = Vector(src) + a * t
                if p.z >= floor_z + 0.02 * R: hit = p; break
    if hit is None:  # ray misses the dome: closest point of the ray, pushed onto the dome
        t = max(0.0, -b); q = Vector(src) + a * t - dome_c
        q.z = max(q.z, 0.05 * R)
        hit = dome_c + q.normalized() * R
    return hit

def lamp_of(rig, pb):
    for o in rig.children:
        if o.type == 'LIGHT' and o.parent_bone == pb.name: return o


# ---------------- build ----------------
def build(context, center, radius, floor_z=None, slots=None, name="LGT_Rig", parent_col=None, prefix=""):
    scene = context.scene
    slots = slots or default_slots()
    c = Vector(center); radius = max(radius, 0.2); k = radius / 0.9
    floor_z = c.z - radius if floor_z is None else floor_z
    parent_col = parent_col or scene.collection
    root = bpy.data.collections.new(prefix + "LIGHTRIG"); parent_col.children.link(root)
    lcol = bpy.data.collections.new(prefix + "LGT_Lights"); root.children.link(lcol)
    wcol = bpy.data.collections.new(prefix + "LGT_Widgets"); root.children.link(wcol)
    arm = bpy.data.armatures.new(name); rig = bpy.data.objects.new(name, arm); root.objects.link(rig)
    rig["rost_lightrig"] = 1
    rig["lgt_radius"] = float(radius); rig["lgt_center"] = [c.x, c.y, float(floor_z)]
    lamps = {}
    rig.show_in_front = True; arm.display_type = 'WIRE'
    vl = context.view_layer; vl.update()

    win = context.window
    ov = dict(window=win, scene=scene, view_layer=vl, active_object=rig, object=rig,
              selected_objects=[rig], selected_editable_objects=[rig])
    prev_active = vl.objects.active
    vl.objects.active = rig
    with context.temp_override(**ov):
        bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    r = eb.new("LGT_Root"); r.head = (c.x, c.y, floor_z); r.tail = r.head + Vector((0, 0.5, 0)); r.roll = 0
    dome_c = Vector((c.x, c.y, floor_z)); R = radius * TGT_DOME
    for S in slots:
        n = S["name"]; typ = S["type"]
        src = Vector(S["abs_pos"]) if "abs_pos" in S else c + Vector(S["pos"]) * k
        aim = Vector(S["aim"]) if "aim" in S else (c - src)
        if aim.length < 1e-6: aim = Vector((0, 1, 0))
        tgt = dome_target(src, aim, dome_c, R, floor_z)
        d = (tgt - src).normalized()
        b = eb.new(f"LGT_{n}"); b.head = src; b.tail = src + d * 0.2; b.align_roll(_up(d)); b.parent = r
        if typ != "POINT":
            t = eb.new(f"LGT_{n}_TGT"); t.head = tgt; t.tail = tgt + Vector((0, 0, 0.1)); t.parent = r
            ln = eb.new(f"LGT_{n}_LINE"); ln.head = src; ln.tail = tgt; ln.parent = b
        p = eb.new(f"LGT_{n}_PANEL"); p.head = b.head; p.tail = b.tail; p.roll = b.roll; p.parent = r
        zax = p.matrix.to_3x3().col[2]
        for key, z, _ in ROWS[typ]:
            s = eb.new(f"LGT_{n}_{key}"); s.head = p.head + zax * z; s.tail = s.head + d * 0.05
            s.roll = p.roll; s.parent = p
    with context.temp_override(**ov):
        bpy.ops.object.mode_set(mode='OBJECT')

    bc = {kk: _bcoll(arm, v) for kk, v in dict(root="Root", src="Sources", tgt="Targets", sld="Sliders", line="Lines").items()}
    W = make_widgets(wcol, 2.2 * k)
    pbs = rig.pose.bones

    def style(pb, wgt, kind, palette=None):
        pb.custom_shape = wgt; pb.use_custom_shape_bone_size = False
        pb.color.palette = palette or COLORS.get(kind, "THEME03"); bc[kind].assign(pb)

    style(pbs["LGT_Root"], W["root"], "root")
    RIG = ("PROP", 'OBJECT', rig)

    for si, S in enumerate(slots):
        n = S["name"]; typ = S["type"]; pal = SLOT_COLORS[si % len(SLOT_COLORS)]
        ps, pp = pbs[f"LGT_{n}"], pbs[f"LGT_{n}_PANEL"]
        pt = pbs.get(f"LGT_{n}_TGT"); pl = pbs.get(f"LGT_{n}_LINE")
        bp = 'pose.bones["%s"]' % ps.name
        ps["lgt_type"] = typ; ps["lgt_group"] = S["group"]
        shape_i = SHAPES.index(S.get("shape", "DISK"))
        wgt = {"AREA": W["disk"] if shape_i in (2, 3) else W["rect"], "SPOT": W["spot"], "POINT": W["point"]}[typ]
        style(ps, wgt, "src", pal); style(pp, W["panel_" + typ], "sld")
        arm.bones[pp.name].hide_select = True
        for ct in ('COPY_LOCATION', 'COPY_ROTATION'):
            cc = pp.constraints.new(ct); cc.target = rig; cc.subtarget = ps.name
        ps.lock_rotation = (True, True, True)
        if pt:
            style(pt, W["tgt"], "tgt", pal)
            style(pl, W["line"], "line", pal); pl.use_custom_shape_bone_size = True
            arm.bones[pl.name].hide_select = True
            cc = pl.constraints.new('STRETCH_TO'); cc.target = rig; cc.subtarget = pt.name; cc.volume = 'NO_VOLUME' 
            cc = ps.constraints.new('DAMPED_TRACK'); cc.target = rig; cc.subtarget = pt.name; cc.track_axis = 'TRACK_Y'
            pt.lock_rotation = (True, True, True); pt.lock_scale = (True, True, True)
        for key, _, kind in ROWS[typ]:
            sb = pbs[f"LGT_{n}_{key}"]; style(sb, W[kind], "sld")
            sb.lock_location = (False, True, True); sb.lock_rotation = (True, True, True); sb.lock_scale = (True, True, True)
            sb.lock_rotation_w = True
            cc = sb.constraints.new('LIMIT_LOCATION'); cc.owner_space = 'LOCAL'; cc.use_transform_limit = True
            cc.use_min_x = cc.use_max_x = True; cc.min_x, cc.max_x = -TRAVEL, TRAVEL
            cc.use_min_y = cc.use_max_y = cc.use_min_z = cc.use_max_z = True
            sb.location.x = float(S.get("sliders", {}).get(key, 0.0))

        # keyable setup properties (all go into the action)
        _prop(ps, "enabled", bool(S.get("enabled", False)), description="Slot used in this setup (hides rig bones + lamp when off)")
        _prop(ps, "on", bool(S.get("on", True)), description="Light on/off (animatable)")
        _prop(ps, "exposure", float(S.get("exposure", 0.0)), min=-20.0, max=20.0, soft_min=-6.0, soft_max=6.0, description="Base exposure, stops")
        _prop(ps, "temperature", float(S.get("temperature", 6500.0)), min=1000.0, max=12000.0, description="Base colour temperature, K")
        _prop(ps, "power", float(S.get("energy", 100.0)), min=0.0, soft_max=5000.0, description="Lamp power, W")
        _prop(ps, "tint", [float(x) for x in S.get("color", (1, 1, 1))], min=0.0, max=1.0, subtype='COLOR', description="Lamp tint (multiplies the temperature colour)")
        if typ == "AREA":
            _prop(ps, "spread", float(S.get("spread", 180.0)), min=1.0, max=180.0, description="Base spread, degrees")
            _prop(ps, "shape", shape_i, min=0, max=3, description="0 Square, 1 Rectangle, 2 Disk, 3 Ellipse")
            _prop(ps, "size", float(S.get("size", 1.0)), min=0.001, soft_max=10.0, description="Lamp size X, m")
            _prop(ps, "size_y", float(S.get("size_y", S.get("size", 1.0))), min=0.001, soft_max=10.0, description="Lamp size Y (Rectangle / Ellipse), m")
        elif typ == "SPOT":
            _prop(ps, "cone", float(S.get("cone", 40.0)), min=1.0, max=180.0, description="Base cone angle, degrees")
            _prop(ps, "blend", float(S.get("blend", 0.15)), min=0.0, max=1.0, description="Spot blend")
            _prop(ps, "radius", float(S.get("radius", 0.05)), min=0.0, soft_max=2.0, description="Soft shadow radius, m")
        else:
            _prop(ps, "radius", float(S.get("radius", 0.1)), min=0.0, soft_max=2.0, description="Soft shadow radius, m")

        # lamp
        ld = bpy.data.lights.new(f"{prefix}LGT_{n}", typ)
        ld.energy = float(S.get("energy", 100.0)); ld.color = S.get("color", (1, 1, 1))
        if hasattr(ld, "use_temperature"): ld.use_temperature = True
        if hasattr(ld, "normalize"): ld.normalize = True
        lo = bpy.data.objects.new(f"{prefix}LGT_{n}", ld); lcol.objects.link(lo); lo.visible_camera = False; lamps[n] = lo
        lo.parent = rig; lo.parent_type = 'BONE'; lo.parent_bone = ps.name

        P = lambda nm, key: (nm, "PROP", 'OBJECT', rig, bp + '["%s"]' % key)
        _drv(ld, "exposure", f"e + x*{EXP_STOPS / TRAVEL:.4f} + (on - 1)*40", [P("e", "exposure"), P("on", "on"), ("x", "LOCX", rig, f"LGT_{n}_EXP")])
        _drv(ld, "temperature", f"max(1000.0, t + x*{TEMP_RANGE / TRAVEL:.2f})", [P("t", "temperature"), ("x", "LOCX", rig, f"LGT_{n}_TEMP")])
        _drv(ld, "energy", "p", [P("p", "power")])
        for ci in range(3):
            _drv(ld, "color", "v", [("v", "PROP", 'OBJECT', rig, bp + '["tint"][%d]' % ci)], index=ci)
        if typ == "AREA":
            _drv(ld, "spread", f"max(0.0175, min(3.1416, (s + x*{SPREAD_RANGE / TRAVEL:.3f})*0.0174533))", [P("s", "spread"), ("x", "LOCX", rig, f"LGT_{n}_SPREAD")])
            _drv(ld, "shape", "(0, 1, 4, 5)[min(3, max(0, int(sh)))]", [P("sh", "shape")])  # RNA enum values: SQUARE 0, RECT 1, DISK 4, ELLIPSE 5
            _drv(ld, "size", "s", [P("s", "size")])
            _drv(ld, "size_y", "s", [P("s", "size_y")])
            # widget follows the lamp size x margin
            L = lambda nm, path: (nm, "PROP", 'LIGHT', ld, path)
            _drv(ps, "custom_shape_scale_xyz", f"s*{WGT_MARGIN}", [L("s", "size")], index=0)
            _drv(ps, "custom_shape_scale_xyz", f"(sy if sh in (1, 5) else s)*{WGT_MARGIN}", [L("s", "size"), L("sy", "size_y"), L("sh", "shape")], index=2)
        elif typ == "SPOT":
            _drv(ld, "spot_size", f"max(0.0175, min(3.1416, (c + x*{CONE_RANGE / TRAVEL:.3f})*0.0174533))", [P("c", "cone"), ("x", "LOCX", rig, f"LGT_{n}_CONE")])
            _drv(ld, "spot_blend", "b", [P("b", "blend")])
            _drv(ld, "shadow_soft_size", "r", [P("r", "radius")])
        else:
            _drv(ld, "shadow_soft_size", "r", [P("r", "radius")])
        # enabled -> lamp and all slot bones hidden
        for path in ("hide_render", "hide_viewport"):
            _drv(lo, path, "not en", [P("en", "enabled")])
        names = [ps.name, pp.name] + [f"LGT_{n}_{key}" for key, _, _ in ROWS[typ]] + ([pt.name, pl.name] if pt else [])
        for bn in names:
            # Blender 5: viewport (pose / object mode) uses PoseBone.hide; older: Bone.hide
            if hasattr(pbs[bn], "hide"):
                _drv(rig, f'pose.bones["{bn}"].hide', "not en", [P("en", "enabled")])
            else:
                _drv(arm, f'bones["{bn}"].hide', "not en", [P("en", "enabled")])

    # lamps sit exactly on the source bone head, -Z (emission) along bone +Y (towards the target).
    # Bone-parent space starts at the bone TAIL, so offset back by the bone length.
    for S in slots:
        n = S["name"]; lo = lamps[n]
        lo.matrix_parent_inverse.identity()
        lo.location = (0.0, -arm.bones[f"LGT_{n}"].length, 0.0)
        lo.rotation_mode = 'XYZ'; lo.rotation_euler = (math.pi / 2, 0.0, 0.0); lo.scale = (1, 1, 1)
    vl.update()
    for S in slots:
        if "bone_scale" in S: rig.pose.bones[f"LGT_{S['name']}"].scale = S["bone_scale"]

    lc = _find_lc(vl.layer_collection, wcol)
    if lc: lc.exclude = True
    rig.animation_data_create().last_slot_identifier = "OB" + ACTION_SLOT
    if prev_active: vl.objects.active = prev_active
    sync_widgets(rig)
    return rig


def sync_widgets(rig):
    for pb in slot_bones(rig):
        if pb.get("lgt_type") == "AREA":
            w = bpy.data.objects.get(area_widget_name(pb.get("shape", 2)))
            if w and pb.custom_shape != w: pb.custom_shape = w


@persistent
def _sync_handler(scene, depsgraph=None):
    for ob in scene.objects:
        if is_rig(ob):
            sync_widgets(ob)


def model_bounds(context):
    obs = [o for o in context.selected_objects if o.type in ('MESH', 'CURVE', 'EMPTY')] or \
          [o for o in context.visible_objects if o.type == 'MESH' and not o.name.startswith(("WGT_", "WGT-", "ENV_", "EXM_Cyclo", "Cyclo", "Lamp_Sphere"))
           and not any(k in c.name for c in o.users_collection for k in ("Studio", "ENV", "Env", "LIGHTRIG", "Practicals"))]
    pts = []
    for o in obs:
        if o.type == 'EMPTY':
            pts.append(o.matrix_world.translation.copy())
        else:
            pts += [o.matrix_world @ Vector(v) for v in o.bound_box]
    if not pts:
        return Vector((0, 0, 0.5)), 0.9, 0.0
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) / 2, (hi - lo).length / 2, lo.z


# ---------------- operators ----------------
def find_rig(context):
    ob = context.active_object
    if is_rig(ob): return ob
    if ob and ob.type == 'LIGHT' and is_rig(ob.parent): return ob.parent
    for o in context.scene.objects:
        if is_rig(o): return o


class ROSTLGT_OT_add(bpy.types.Operator):
    bl_idname = "rost_lgt.add_rig"; bl_label = "Rost Light Rig"
    bl_description = "Add the light rig around the selected objects (or all visible meshes)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        c, r, fz = model_bounds(context)
        rig = build(context, c, r, fz)
        self.report({'INFO'}, f"{rig.name}: centre {tuple(round(x, 2) for x in c)}, radius {r:.2f} m")
        return {'FINISHED'}


class ROSTLGT_OT_pick(bpy.types.Operator):
    bl_idname = "rost_lgt.pick"; bl_label = "Select slot"; bl_description = "Select this light's source bone and show its settings"
    slot: bpy.props.StringProperty()

    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.rost_lgt_active = self.slot
        rig = find_rig(context)
        pb = rig.pose.bones.get("LGT_" + self.slot) if rig else None
        if pb is None or pb.get("lgt_type") is None:
            return {'FINISHED'}
        # select the source bone in the viewport (enter Pose Mode on the rig if needed)
        if context.mode != 'POSE' or context.active_object != rig:
            if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
            for o in context.selected_objects: o.select_set(False)
            rig.select_set(True); context.view_layer.objects.active = rig
            bpy.ops.object.mode_set(mode='POSE')
        for p in rig.pose.bones:
            if hasattr(p, "select"): p.select = False
            else: rig.data.bones[p.name].select = False
        if hasattr(pb, "select"): pb.select = True
        else: rig.data.bones[pb.name].select = True
        rig.data.bones.active = rig.data.bones[pb.name]
        return {'FINISHED'}


class ROSTLGT_OT_select_lamp(bpy.types.Operator):
    bl_idname = "rost_lgt.select_lamp"; bl_label = "Select lamp"
    bl_description = "Select the lamp object (colour, power, shader nodes)"
    bl_options = {'REGISTER', 'UNDO'}
    slot: bpy.props.StringProperty()

    def execute(self, context):
        rig = find_rig(context); pb = rig.pose.bones.get("LGT_" + self.slot); lo = lamp_of(rig, pb)
        if not lo: return {'CANCELLED'}
        if context.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        for o in context.selected_objects: o.select_set(False)
        lo.select_set(True); context.view_layer.objects.active = lo
        return {'FINISHED'}


class ROSTLGT_OT_shape(bpy.types.Operator):
    bl_idname = "rost_lgt.set_shape"; bl_label = "Lamp shape"; bl_options = {'REGISTER', 'UNDO'}
    slot: bpy.props.StringProperty(); shape: bpy.props.IntProperty()

    @classmethod
    def description(cls, context, props):
        return f"Shape: {SHAPE_LABELS[props.shape]}"

    def execute(self, context):
        rig = find_rig(context); pb = rig.pose.bones["LGT_" + self.slot]
        pb["shape"] = self.shape
        if context.scene.tool_settings.use_keyframe_insert_auto:
            rig.keyframe_insert(f'pose.bones["{pb.name}"]["shape"]')
        sync_widgets(rig); rig.update_tag(); context.view_layer.update()
        return {'FINISHED'}


class ROSTLGT_OT_key(bpy.types.Operator):
    bl_idname = "rost_lgt.key_setup"; bl_label = "KEY ALL"
    bl_description = "Key every slot (enabled, settings, bone positions, sliders) at the current frame, so the action holds the full setup"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig = find_rig(context)
        props = ("enabled", "on", "exposure", "temperature", "power", "tint", "spread", "shape", "size", "size_y", "cone", "blend", "radius")
        n = 0
        for pb in rig.pose.bones:
            for path in ("location", "scale"):
                pb.keyframe_insert(path, group=pb.name); n += 1
            rot = "rotation_quaternion" if pb.rotation_mode == 'QUATERNION' else "rotation_euler"
            pb.keyframe_insert(rot, group=pb.name)
            for k in props:
                if k in pb.keys():
                    rig.keyframe_insert(f'pose.bones["{pb.name}"]["{k}"]', group=pb.name); n += 1
        self.report({'INFO'}, f"Keyed {len(rig.pose.bones)} bones at frame {context.scene.frame_current}")
        return {'FINISHED'}



# ---------------- presets ----------------
# A preset is the rig state on ONE frame (no animation): root transform, every source / target position
# relative to the root, slider positions and all setup properties. Stored as JSON in the presets folder.
PRESET_PROPS = ("enabled", "on", "exposure", "temperature", "power", "tint", "spread", "shape", "size", "size_y", "cone", "blend", "radius")
PRESET_SCALED = ("size", "size_y", "radius")


def preset_dir():
    d = ""
    try:
        d = bpy.context.preferences.addons[__name__].preferences.preset_dir
    except Exception:
        pass
    if not d:
        d = os.path.join(bpy.utils.user_resource('SCRIPTS', path="presets", create=True), "rost_light_rig")
    d = bpy.path.abspath(d)
    os.makedirs(d, exist_ok=True)
    return d

def preset_names():
    try:
        return sorted((f[:-5] for f in os.listdir(preset_dir()) if f.lower().endswith(".json")), key=str.lower)
    except Exception:
        return []

def preset_path(name):
    safe = "".join(ch for ch in name if ch not in '\\/:*?"<>|').strip() or "Preset"
    return os.path.join(preset_dir(), safe + ".json")

def _flat(m):
    return [round(v, 6) for row in m for v in row]

def _mat(L):
    return Matrix([L[0:4], L[4:8], L[8:12], L[12:16]])

def preset_capture(rig):
    """State of the rig as it is now (current frame values)."""
    arm = rig.data; Ri = arm.bones["LGT_Root"].matrix_local.inverted()
    pbs = rig.pose.bones
    rel = lambda pb: _flat(Ri @ arm.bones[pb.name].matrix_local @ pb.matrix_basis)
    data = {"version": 1, "radius": float(rig.get("lgt_radius", 0.0)), "root": _flat(pbs["LGT_Root"].matrix_basis), "slots": {}}
    for pb in slot_bones(rig):
        n = pb.name[4:]; typ = pb["lgt_type"]
        props = {}
        for k in PRESET_PROPS:
            if k in pb.keys():
                v = pb[k]
                props[k] = [float(x) for x in v] if hasattr(v, "__len__") else (bool(v) if isinstance(v, bool) else (int(v) if isinstance(v, int) else float(v)))
        tg = pbs.get(pb.name + "_TGT")
        data["slots"][n] = {"type": typ, "props": props, "src": rel(pb), "tgt": rel(tg) if tg else None,
                            "sliders": {key: round(pbs[f"{pb.name}_{key}"].location.x, 6) for key, _, _ in ROWS[typ] if f"{pb.name}_{key}" in pbs}}
    return data

def preset_apply(rig, data, fit=True):
    """Put the preset on the rig (values only, nothing is keyed here). fit: scale distances, lamp sizes and power to this rig's model size."""
    arm = rig.data; Rrest = arm.bones["LGT_Root"].matrix_local; Ri = Rrest.inverted()
    pbs = rig.pose.bones
    r0 = float(data.get("radius", 0.0)); r1 = float(rig.get("lgt_radius", 0.0))
    f = r1 / r0 if (fit and r0 > 0 and r1 > 0 and abs(r1 / r0 - 1.0) > 0.01) else 1.0
    pbs["LGT_Root"].matrix_basis = _mat(data["root"])
    def put(pb, L):
        M = _mat(L); M.translation = M.translation * f
        pb.matrix_basis = (Ri @ arm.bones[pb.name].matrix_local).inverted() @ M
    n_ok = 0
    for n, S in data.get("slots", {}).items():
        pb = pbs.get("LGT_" + n)
        if pb is None or pb.get("lgt_type") != S.get("type"): continue
        put(pb, S["src"])
        tg = pbs.get(pb.name + "_TGT")
        if tg and S.get("tgt"): put(tg, S["tgt"])
        for key, x in S.get("sliders", {}).items():
            sb = pbs.get(f"{pb.name}_{key}")
            if sb: sb.location.x = x
        for k, v in S.get("props", {}).items():
            if k not in pb.keys(): continue
            if k in PRESET_SCALED: v = v * f
            elif k == "power": v = v * f * f
            pb[k] = v
        n_ok += 1
    sync_widgets(rig); rig.update_tag()
    return n_ok, f

def rig_is_keyed(rig):
    ad = rig.animation_data
    return bool(ad and ad.action)

def key_all(rig):
    for pb in rig.pose.bones:
        for path in ("location", "scale"):
            pb.keyframe_insert(path, group=pb.name)
        pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == 'QUATERNION' else "rotation_euler", group=pb.name)
        for k in PRESET_PROPS:
            if k in pb.keys():
                rig.keyframe_insert(f'pose.bones["{pb.name}"]["{k}"]', group=pb.name)

def preset_save(rig, name, scene=None):
    """Save the rig state of the scene's FIRST frame (animation is not stored)."""
    cur = None
    if scene is not None and rig_is_keyed(rig) and scene.frame_current != scene.frame_start:
        cur = scene.frame_current; scene.frame_set(scene.frame_start)
    data = preset_capture(rig); data["name"] = name
    if cur is not None: scene.frame_set(cur)
    path = preset_path(name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    return path

def preset_load(name):
    with open(preset_path(name), encoding="utf-8") as fh:
        return json.load(fh)

def _preset_items(self, context):
    _preset_items.cache = [(n, n, "") for n in preset_names()] or [("__none__", "— no presets —", "")]
    return _preset_items.cache
_preset_items.cache = []


class ROSTLGT_OT_preset_save(bpy.types.Operator):
    bl_idname = "rost_lgt.preset_save"; bl_label = "Save Light Preset"
    bl_description = "Save the whole setup as a preset: first frame of the scene only, animation is not stored. Same name = overwrite"
    bl_options = {'REGISTER'}
    name: bpy.props.StringProperty(name="Name", default="My setup")

    def invoke(self, context, event):
        cur = context.scene.rost_lgt_preset
        if cur and cur != "__none__": self.name = cur
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        rig = find_rig(context)
        if not rig or not self.name.strip(): return {'CANCELLED'}
        path = preset_save(rig, self.name.strip(), context.scene)
        nm = os.path.basename(path)[:-5]
        try: context.scene.rost_lgt_preset = nm
        except Exception: pass
        self.report({'INFO'}, f"Preset saved: {path}")
        return {'FINISHED'}


class ROSTLGT_OT_preset_apply(bpy.types.Operator):
    bl_idname = "rost_lgt.preset_apply"; bl_label = "Apply Light Preset"
    bl_description = "Put the selected preset on this rig at the current frame. If the rig is already keyed, the frame is keyed too (other keys stay)"
    bl_options = {'REGISTER', 'UNDO'}
    fit: bpy.props.BoolProperty(name="Fit to model size", default=True,
                                description="Scale distances, lamp sizes and power when this rig was built for a bigger / smaller model")

    def execute(self, context):
        rig = find_rig(context); name = context.scene.rost_lgt_preset
        if not rig or not name or name == "__none__": return {'CANCELLED'}
        n, f = preset_apply(rig, preset_load(name), self.fit)
        if rig_is_keyed(rig): key_all(rig)
        context.view_layer.update()
        self.report({'INFO'}, f"Preset '{name}': {n} slots" + (f", scaled x{f:.2f}" if f != 1.0 else ""))
        return {'FINISHED'}


class ROSTLGT_OT_preset_delete(bpy.types.Operator):
    bl_idname = "rost_lgt.preset_delete"; bl_label = "Delete this light preset?"
    bl_description = "Delete the selected preset file"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        name = context.scene.rost_lgt_preset
        if not name or name == "__none__": return {'CANCELLED'}
        try: os.remove(preset_path(name))
        except Exception as e:
            self.report({'ERROR'}, str(e)); return {'CANCELLED'}
        return {'FINISHED'}


# ---------------- UI ----------------
def _slot_items(self, context):
    rig = find_rig(context)
    items = [(pb.name[4:], pb.name[4:], "", TYPE_ICON[pb["lgt_type"]], i) for i, pb in enumerate(slot_bones(rig))] if rig else []
    _slot_items.cache = items or [("", "—", "", 0)]
    return _slot_items.cache
_slot_items.cache = []


def _section(lay, idname, label, icon, closed=True):
    # collapsible sub-section (Blender 4.1+ layout panels); returns the body layout or None when collapsed
    if hasattr(lay, "panel"):
        header, body = lay.panel(idname, default_closed=closed)
        header.label(text=label, icon=icon)
        return body
    box = lay.box(); box.label(text=label, icon=icon)
    return box


class ROSTLGT_PT_panel(bpy.types.Panel):
    bl_label = "Rost Light Rig"; bl_idname = "ROSTLGT_PT_panel"
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = "Rost Tools"

    def draw(self, context):
        lay = self.layout; sc = context.scene
        rig = find_rig(context)
        if not rig:
            lay.label(text="No light rig in this scene")
            lay.operator("rost_lgt.add_rig", icon='LIGHT_AREA', text="Add Light Rig")
            lay.label(text="Centre = selected objects, or all visible meshes", icon='INFO')
            return
        lay.label(text=rig.name, icon='ARMATURE_DATA')
        row = lay.row(); row.scale_y = 2.0
        row.operator("rost_lgt.key_setup", icon='KEY_HLT', text=f"KEY ALL  (frame {sc.frame_current})")
        box = _section(lay, "rostlgt_PRESETS", "Presets", 'PRESET', closed=True)
        if box is not None:
            row = box.row(align=True)
            row.prop(sc, "rost_lgt_preset", text="")
            row.operator("rost_lgt.preset_apply", text="Apply", icon='CHECKMARK')
            row = box.row(align=True)
            row.operator("rost_lgt.preset_save", text="Save (first frame)", icon='ADD')
            row.operator("rost_lgt.preset_delete", text="", icon='TRASH')

        # active slot: active pose bone wins, else last picked
        act = None
        if context.active_pose_bone and context.active_object == rig:
            act = slot_of(rig, context.active_pose_bone.name)
        if act is None:
            act = rig.pose.bones.get("LGT_" + sc.rost_lgt_active)
        act_name = act.name[4:] if act else ""

        for grp, label in GROUPS:
            pbs = slot_bones(rig, grp)
            if not pbs: continue
            on = sum(1 for p in pbs if p["enabled"])
            box = _section(lay, "rostlgt_" + grp, f"{label}   {on}/{len(pbs)}", TYPE_ICON[pbs[0]["lgt_type"]], closed=(grp != "MAIN"))
            if box is None: continue
            if grp == "MAIN":
                col = box.column(align=True)
                for pb in pbs:
                    n = pb.name[4:]; row = col.row(align=True)
                    row.prop(pb, '["enabled"]', text="", toggle=True, icon='HIDE_OFF' if pb["enabled"] else 'HIDE_ON')
                    op = row.operator("rost_lgt.pick", text=n, depress=(n == act_name)); op.slot = n
                    op = row.operator("rost_lgt.select_lamp", text="", icon='RESTRICT_SELECT_OFF'); op.slot = n
            else:
                row = box.row(align=True)
                for i, pb in enumerate(pbs):
                    row.prop(pb, '["enabled"]', text=str(i + 1), toggle=True)
                row = box.row(align=True)
                for i, pb in enumerate(pbs):
                    n = pb.name[4:]
                    op = row.operator("rost_lgt.pick", text="", icon='PREFERENCES' if n == act_name else 'DOT', depress=(n == act_name)); op.slot = n

        if act:
            self.draw_slot(context, lay, rig, act)

    def draw_slot(self, context, lay, rig, pb):
        n = pb.name[4:]; typ = pb["lgt_type"]; lo = lamp_of(rig, pb)
        box = _section(lay, "rostlgt_SLOT", f"Settings: {n}", TYPE_ICON[typ], closed=True)
        if box is None: return
        row = box.row(align=True)
        row.prop(pb, '["enabled"]', text="Enabled", toggle=True)
        row.prop(pb, '["on"]', text="On", toggle=True)
        col = box.column(align=True)
        col.prop(pb, '["exposure"]', text="Exposure")
        col.prop(rig.pose.bones[f"LGT_{n}_EXP"], "location", index=0, text="  slider (±4 st)", slider=True)
        col = box.column(align=True)
        col.prop(pb, '["temperature"]', text="Temperature K")
        col.prop(rig.pose.bones[f"LGT_{n}_TEMP"], "location", index=0, text="  slider (±3800 K)", slider=True)
        if typ == "AREA":
            col = box.column(align=True)
            col.prop(pb, '["spread"]', text="Spread °")
            col.prop(rig.pose.bones[f"LGT_{n}_SPREAD"], "location", index=0, text="  slider (±90°)", slider=True)
            row = box.row(align=True)
            for i, lab in enumerate(SHAPE_LABELS):
                op = row.operator("rost_lgt.set_shape", text=lab, depress=(int(pb["shape"]) == i)); op.slot = n; op.shape = i
            col = box.column(align=True)
            col.prop(pb, '["size"]', text="Size" if int(pb["shape"]) in (0, 2) else "Size X")
            if int(pb["shape"]) in (1, 3):
                col.prop(pb, '["size_y"]', text="Size Y")
        elif typ == "SPOT":
            col = box.column(align=True)
            col.prop(pb, '["cone"]', text="Cone °")
            col.prop(rig.pose.bones[f"LGT_{n}_CONE"], "location", index=0, text="  slider (±60°)", slider=True)
            box.prop(pb, '["blend"]', text="Blend")
            box.prop(pb, '["radius"]', text="Radius")
        else:
            box.prop(pb, '["radius"]', text="Radius")
        col = box.column(align=True)
        col.prop(pb, '["tint"]', text="Tint")
        col.prop(pb, '["power"]', text="Power W")
        if lo:
            op = box.operator("rost_lgt.select_lamp", text="Select lamp (nodes, more)", icon='RESTRICT_SELECT_OFF'); op.slot = n


def _menu(self, context):
    self.layout.separator()
    self.layout.operator("rost_lgt.add_rig", icon='LIGHT_AREA')


lgt_classes = (ROSTLGT_OT_add, ROSTLGT_OT_pick, ROSTLGT_OT_select_lamp, ROSTLGT_OT_shape, ROSTLGT_OT_key,
           ROSTLGT_OT_preset_save, ROSTLGT_OT_preset_apply, ROSTLGT_OT_preset_delete, ROSTLGT_PT_panel)


def lgt_register():
    for c in lgt_classes: bpy.utils.register_class(c)
    bpy.types.Scene.rost_lgt_active = bpy.props.StringProperty(default="Key")
    bpy.types.Scene.rost_lgt_preset = bpy.props.EnumProperty(name="Preset", items=_preset_items)
    bpy.types.VIEW3D_MT_light_add.append(_menu)
    for h in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.frame_change_post):
        for f in [f for f in h if getattr(f, "__name__", "") == "_sync_handler"]: h.remove(f)
        h.append(_sync_handler)


def lgt_unregister():
    for h in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.frame_change_post):
        for f in [f for f in h if getattr(f, "__name__", "") == "_sync_handler"]: h.remove(f)
    bpy.types.VIEW3D_MT_light_add.remove(_menu)
    del bpy.types.Scene.rost_lgt_active
    del bpy.types.Scene.rost_lgt_preset
    for c in reversed(lgt_classes): bpy.utils.unregister_class(c)


# ======================= STEP Pipeline (з exm_pipeline_panel.py 0.4) =======================
# Thin UI over the pipeline scripts in PIPE_DIR (logic stays there, loaded with runpy on each click).

import bpy
import os
import ast
import json
import runpy
import traceback

PIPE_DIR = r"G:\My Drive\WORK\Blender\AssetsLibrary\EXM_Pipeline"


def _pipe(name, run_name):
    return runpy.run_path(os.path.join(PIPE_DIR, name), run_name=run_name)


def _busy(scene):
    st = str(scene.get("exm_status", ""))
    return bool(st) and st != "done" and not st.startswith("error")


# ------------------------------------------------------------------ settings
class EXM_Settings(bpy.types.PropertyGroup):
    step_path: bpy.props.StringProperty(
        name="STEP", subtype="FILE_PATH", default="",
        description="STEP file to import")
    new_scene: bpy.props.BoolProperty(
        name="Нова сцена", default=True,
        description="Імпортувати в нову сцену PIPE_<код> (інакше - в поточну)")
    tessellation: bpy.props.BoolProperty(
        name="Тесселяція 0.4 мм / 12°", default=True,
        description="Імпорт одразу з тесселяцією 0.4 мм / 12° (вимкни - буде налаштування CADder за замовчуванням)")
    retess_lin: bpy.props.FloatProperty(
        name="Відхилення, мм", default=0.05, min=0.005, max=2.0, precision=3, step=1,
        description="Макс. відстань сітки від справжньої поверхні для крупних планів")
    retess_ang: bpy.props.FloatProperty(
        name="Кут, °", default=5.0, min=0.5, max=30.0, precision=1,
        description="Макс. кут між сусідніми гранями сітки")
    do_rig: bpy.props.BoolProperty(
        name="Риг", default=True,
        description="Після матеріалів побудувати риг (CAD Auto-Rig + механіка)")
    show_report: bpy.props.BoolProperty(name="Звіт", default=False)


# ------------------------------------------------------------------ redraw while busy
def _redraw_timer():
    busy = any(_busy(s) for s in bpy.data.scenes)
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    return 1.0 if busy else None


def _start_redraw():
    if not bpy.app.timers.is_registered(_redraw_timer):
        bpy.app.timers.register(_redraw_timer, first_interval=1.0)


# ------------------------------------------------------------------ operators
class EXM_OT_Run(bpy.types.Operator):
    bl_idname = "exm.run"
    bl_label = "Run"
    bl_description = "Імпорт STEP → тесселяція → матеріали → риг"

    def execute(self, context):
        s = context.scene.exm_settings
        path = bpy.path.abspath(s.step_path)
        if not path or not os.path.isfile(path):
            self.report({"WARNING"}, "Вибери STEP-файл")
            return {"CANCELLED"}
        if _busy(context.scene):
            self.report({"WARNING"}, "Ця сцена ще обробляється")
            return {"CANCELLED"}

        if s.new_scene:
            code = os.path.splitext(os.path.basename(path))[0]
            sc = bpy.data.scenes.new("PIPE_" + code)
            sc.exm_settings.step_path = s.step_path
            sc.exm_settings.tessellation = s.tessellation
            sc.exm_settings.do_rig = s.do_rig
            context.window.scene = sc
        elif any(o.type == "MESH" for o in context.scene.objects):
            self.report({"WARNING"}, "Сцена не порожня: увімкни 'Нова сцена' або очисти її")
            return {"CANCELLED"}

        kw = {"do_rig": s.do_rig}
        if not s.tessellation:
            kw["tessellation"] = None
        target = context.window.scene
        target["exm_status"] = "starting"

        # start on the next tick, so the new scene is the context scene for CADder
        def _go():
            try:
                _pipe("exm_pipeline.py", "exm_pipe")["run"](path, **kw)
            except Exception as e:
                traceback.print_exc()
                target["exm_status"] = "error: " + repr(e)
            return None

        bpy.app.timers.register(_go, first_interval=0.2)
        _start_redraw()
        return {"FINISHED"}


class EXM_OT_Materials(bpy.types.Operator):
    bl_idname = "exm.materials"
    bl_label = "Materials only"
    bl_description = "Перепризначити візуальні матеріали всім мешам поточної сцени"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sc = context.scene
        try:
            ns = _pipe("exm_assign_materials.py", "exm_mat")
            sc["exm_report"] = str(ns["assign"](list(sc.objects)))
        except Exception:
            traceback.print_exc()
            self.report({"ERROR"}, "Помилка матеріалів - див. консоль")
            return {"CANCELLED"}
        self.report({"INFO"}, "Матеріали призначено")
        return {"FINISHED"}


class EXM_OT_Rig(bpy.types.Operator):
    bl_idname = "exm.rig"
    bl_label = "Rig only"
    bl_description = "Побудувати риг для поточної сцени (один раз на сцену)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return not context.scene.get("exm_rig_done")

    def execute(self, context):
        sc = context.scene
        try:
            ns = _pipe("exm_rig.py", "exm_rig")
            ns["rig"](sc)
        except Exception as e:
            traceback.print_exc()
            self.report({"ERROR"}, f"Риг: {e}")
            return {"CANCELLED"}
        self.report({"INFO"}, "Риг готовий")
        return {"FINISHED"}


class EXM_OT_Retessellate(bpy.types.Operator):
    bl_idname = "exm.retessellate"
    bl_label = "Перетесселювати виділене"
    bl_description = ("Перебудувати сітку виділених деталей (або всіх деталей під виділеним "
                      "empty) з STEP з вищою точністю. Деталь лишається на місці: риг, анімація, "
                      "матеріали зберігаються; спільний меш оновлюється в усіх шотах")
    bl_options = {"REGISTER", "UNDO"}

    work: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        s = context.scene.exm_settings
        try:
            ns = _pipe("exm_pipeline.py", "exm_pipe")
            lin, ang = ns["WORK_TESSELLATION"] if self.work else (s.retess_lin, s.retess_ang)
            rep = ns["retessellate"](list(context.selected_objects), lin, ang)
        except Exception as e:
            traceback.print_exc()
            self.report({"ERROR"}, f"Тесселяція: {e}")
            return {"CANCELLED"}
        if rep.get("error"):
            self.report({"WARNING"}, rep["error"])
            return {"CANCELLED"}
        context.scene["exm_retess_report"] = json.dumps(rep, ensure_ascii=False)
        self.report({"INFO"}, f"{rep['parts']} дет. · {rep['tess']} · "
                              f"{rep['verts_before']} → {rep['verts_after']} верш. · {rep['sec']} с")
        return {"FINISHED"}


class EXM_OT_ResetPose(bpy.types.Operator):
    bl_idname = "exm.reset_pose"
    bl_label = "Reset rig pose"
    bl_description = "Повернути всі кістки арматури сцени в рест-позу"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = 0
        for o in context.scene.objects:
            if o.type == "ARMATURE":
                for b in o.pose.bones:
                    b.location = (0, 0, 0)
                    b.rotation_euler = (0, 0, 0)
                    b.rotation_quaternion = (1, 0, 0, 0)
                    b.scale = (1, 1, 1)
                n += 1
        context.view_layer.update()
        self.report({"INFO"}, f"Скинуто арматур: {n}")
        return {"FINISHED"}


# ------------------------------------------------------------------ panel
def _draw_report(layout, sc):
    raw = sc.get("exm_report")
    if raw:
        try:
            r = ast.literal_eval(str(raw))
        except Exception:
            r = None
        if isinstance(r, dict):
            col = layout.column(align=True)
            col.label(text=f"Фарба: {r.get('paint_color')} {r.get('paint_finish')}", icon="MATERIAL")
            un = r.get("unmapped_eng_materials") or {}
            if un:
                col.label(text=f"Незмаплені: {len(un)}", icon="ERROR")
                for k, v in list(un.items())[:6]:
                    col.label(text=f"   {k}: {v}")
            else:
                col.label(text="Незмаплених матеріалів немає", icon="CHECKMARK")

    raw = sc.get("exm_rig_report")
    if raw:
        try:
            r = json.loads(raw)
        except Exception:
            r = None
        if isinstance(r, dict):
            col = layout.column(align=True)
            for name, d in r.get("doors", {}).items():
                col.label(text=f"{name}: {d['angle']}°  ({d['limited_by'][:28]})", icon="BONE_DATA")
            col.label(text=f"Замків: {r.get('locks', 0)}", icon="LOCKED")
            for name, g in r.get("springs", {}).items():
                if isinstance(g, dict):
                    col.label(text=f"{name}: {g['Lmax_mm']} мм → {g['stroke_angle']}°",
                              icon="CONSTRAINT_BONE")
                else:
                    col.label(text=f"{name}: {g}", icon="ERROR")


class EXM_PT_Pipeline(bpy.types.Panel):
    bl_label = "STEP Pipeline"
    bl_idname = "EXM_PT_pipeline"
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Rost Tools"

    def draw(self, context):
        layout = self.layout
        sc = context.scene
        s = sc.exm_settings

        box = layout.box()
        box.label(text="Імпорт", icon="IMPORT")
        box.prop(s, "step_path", text="")
        col = box.column(align=True)
        col.prop(s, "new_scene")
        col.prop(s, "tessellation")
        col.prop(s, "do_rig")
        row = box.row()
        row.scale_y = 1.4
        row.enabled = not _busy(sc)
        row.operator("exm.run", icon="PLAY")

        box = layout.box()
        box.label(text="Окремі кроки", icon="TOOL_SETTINGS")
        col = box.column(align=True)
        col.operator("exm.materials", icon="MATERIAL")
        col.operator("exm.rig", icon="ARMATURE_DATA")
        col.operator("exm.reset_pose", icon="LOOP_BACK")

        box = layout.box()
        box.label(text="Деталізація (крупні плани)", icon="MESH_ICOSPHERE")
        col = box.column(align=True)
        col.prop(s, "retess_lin")
        col.prop(s, "retess_ang")
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("exm.retessellate", icon="MOD_SUBSURF")
        op = row.operator("exm.retessellate", text="", icon="LOOP_BACK")
        op.work = True
        raw = sc.get("exm_retess_report")
        if raw:
            try:
                r = json.loads(raw)
                box.label(text=f"Останнє: {r['parts']} дет., {r['tess']}, "
                               f"{r['verts_before']}→{r['verts_after']}")
            except Exception:
                pass

        box = layout.box()
        st = str(sc.get("exm_status", "—"))
        icon = "CHECKMARK" if st == "done" else ("ERROR" if st.startswith("error") else "TIME")
        box.label(text=f"Статус: {st[:40]}", icon=icon)
        if "exm_total_sec" in sc:
            box.label(text=f"Час: {sc['exm_total_sec']} с")
        if sc.get("exm_rig_done"):
            box.label(text="Риг побудовано", icon="ARMATURE_DATA")
        box.prop(s, "show_report", emboss=False,
                 icon="TRIA_DOWN" if s.show_report else "TRIA_RIGHT")
        if s.show_report:
            _draw_report(box, sc)


# ------------------------------------------------------------------ register
EXM_CLASSES = (
    EXM_Settings,
    EXM_OT_Run,
    EXM_OT_Materials,
    EXM_OT_Rig,
    EXM_OT_ResetPose,
    EXM_OT_Retessellate,
    EXM_PT_Pipeline,
)


def exm_register():
    for cls in EXM_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.exm_settings = bpy.props.PointerProperty(type=EXM_Settings)


def exm_unregister():
    if bpy.app.timers.is_registered(_redraw_timer):
        bpy.app.timers.unregister(_redraw_timer)
    del bpy.types.Scene.exm_settings
    for cls in reversed(EXM_CLASSES):
        bpy.utils.unregister_class(cls)


def register():
    bpy.utils.register_class(CADRIG_Settings)
    bpy.types.Scene.cadrig_settings = bpy.props.PointerProperty(type=CADRIG_Settings)
    bpy.types.Scene.fx_original_bg_strength = bpy.props.FloatProperty(name="Original BG Strength", default=1.0)
    bpy.types.Scene.fx_bg_saved = bpy.props.BoolProperty(name="BG Saved Flag", default=False)
    bpy.types.Scene.fx_active_group_name = bpy.props.StringProperty(name="Active Group", default="")
    bpy.types.Scene.fx_active_empty_name = bpy.props.StringProperty(name="Active Empty", default="")
    bpy.types.Scene.fx_instance_picker = bpy.props.EnumProperty(
        name="Instance",
        items=_get_instance_enum_items,
        update=_on_instance_picked,
    )
    for cls in classes:
        bpy.utils.register_class(cls)
    hud_register()
    sec_register()
    vc_register()
    sty_register()
    fui_register()
    lgt_register()
    exm_register()

def unregister():
    exm_unregister()
    lgt_unregister()
    fui_unregister()
    sty_unregister()
    vc_unregister()
    sec_unregister()
    hud_unregister()
    del bpy.types.Scene.fx_original_bg_strength
    del bpy.types.Scene.fx_bg_saved
    del bpy.types.Scene.fx_active_group_name
    del bpy.types.Scene.fx_active_empty_name
    del bpy.types.Scene.fx_instance_picker
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.cadrig_settings
    bpy.utils.unregister_class(CADRIG_Settings)

if __name__ == "__main__":
    register()
