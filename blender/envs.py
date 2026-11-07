"""Environments: the world, lights and set around a machine. Each takes the scene and returns nothing a shot needs
but the ground height (0).

desert_lot is reference A's: orange sand under a hazy sky, a long fence far off, a few pile stubs about.
workbench is A's opening: a wood block on a black ground under one warm lamp.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Quaternion, Vector

from blender import materials, shapes

HDRIS: dict[str, str] = {}   # Poly Haven HDRI id -> path, set by run.py


def _world(color=(0, 0, 0), hdri: str | None = None, strength=1.0, rotation=0.0, reflect=None, most=None):
    """The sky: an HDRI, or a flat color. `reflect` is a color only reflections see (steel in a black room still
    catches a grey room), while the camera sees `color`. `most`: how bright an HDRI can look to the camera, while what it lights still gets all of it, so a patch of real sky doesn't bloom over what's in front of it."""
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    tree = world.node_tree
    bg = tree.nodes["Background"]
    bg.inputs["Strength"].default_value = strength
    if reflect is not None and not hdri:
        seen = tree.nodes.new("ShaderNodeBackground")
        seen.inputs["Color"].default_value = (*color, 1)
        bg.inputs["Color"].default_value = (*reflect, 1)
        path = tree.nodes.new("ShaderNodeLightPath")
        mix = tree.nodes.new("ShaderNodeMixShader")
        tree.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
        tree.links.new(bg.outputs["Background"], mix.inputs[1])
        tree.links.new(seen.outputs["Background"], mix.inputs[2])
        tree.links.new(mix.outputs["Shader"], tree.nodes["World Output"].inputs["Surface"])
    elif hdri:
        env = tree.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(HDRIS[hdri], check_existing=True)
        mapping = tree.nodes.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value = (0, 0, rotation)
        coords = tree.nodes.new("ShaderNodeTexCoord")
        tree.links.new(coords.outputs["Generated"], mapping.inputs["Vector"])
        tree.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
        if most is None:
            tree.links.new(env.outputs["Color"], bg.inputs["Color"])
        else:
            held = tree.nodes.new("ShaderNodeVectorMath")
            held.operation = "MINIMUM"
            tree.links.new(env.outputs["Color"], held.inputs[0])
            held.inputs[1].default_value = (most, most, most)
            path = tree.nodes.new("ShaderNodeLightPath")
            seen = tree.nodes.new("ShaderNodeMix")
            seen.data_type = "RGBA"
            tree.links.new(path.outputs["Is Camera Ray"], seen.inputs["Factor"])
            tree.links.new(env.outputs["Color"], seen.inputs[6])
            tree.links.new(held.outputs["Vector"], seen.inputs[7])
            tree.links.new(seen.outputs[2], bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = (*color, 1)
    bpy.context.scene.world = world


def _sun(direction_deg=(50, 0, 35), energy=4.0, angle=2.5, color=(1.0, 0.95, 0.88)):
    data = bpy.data.lights.new("Sun", "SUN")
    data.energy = energy
    data.angle = math.radians(angle)
    data.color = color
    sun = bpy.data.objects.new("Sun", data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = tuple(math.radians(a) for a in direction_deg)
    return sun


def desert_lot(seed=7, stubs=14, edge_y=None, stub_size=(0.12, 0.2), stub_spread=(6, 45), cones=0):
    """`edge_y`: the sand ends there on the camera's side, A's finite ground whose cut face (machines'
    ground_section) shows the soil below; stubs and cones stay behind it. Stubs are the old piles' tops."""
    _world(hdri="kloofendal_43d_clear_puresky", strength=1.1, rotation=math.radians(140))
    _sun(energy=3.2)
    ground = _ground(y_from=edge_y)
    # the long fence or bridge on the horizon, a soft line of rails on posts
    posts = [((x, 140, 0), (x, 140, 5.5)) for x in range(-300, 301, 12)]
    rails = [((-300, 140, z), (300, 140, z)) for z in (3.6, 5.5)]
    shapes.rods("FarFence", posts + rails, 0.35, "far", segments=6)
    # pile stubs left in the ground about the lot
    rng = random.Random(seed)
    for i in range(stubs):
        dist, ang = rng.uniform(*stub_spread), rng.uniform(-1.2, 1.2)
        x, y = dist * math.sin(ang), dist * math.cos(ang)
        if (abs(x) < 2.5 and y < 8) or (edge_y is not None and y < edge_y + 1.5):
            continue
        shapes.cylinder(f"Stub{i}", rng.uniform(*stub_size), rng.uniform(0.25, 0.6) * stub_size[1] / 0.2, "dark_steel",
                        at=(x, y, 0), bevel=0.01, segments=24)
    for i in range(cones):
        dist, ang = rng.uniform(*stub_spread), rng.uniform(-1.0, 1.0)
        x, y = dist * math.sin(ang), dist * math.cos(ang) + (edge_y or 0) + 2
        shapes.lathe(f"Cone{i}", [(0, 0), (0.2, 0), (0.035, 0.7), (0, 0.7)], "orange_paint", at=(x, y, 0),
                            segments=24)
    return ground


def _ground(size=800.0, y_from=None):
    """A flat ground at z 0, `size` across; with `y_from`, only the part beyond y_from (the camera's side cut off)."""
    bm = bmesh.new()
    if y_from is None:
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    else:
        h = size / 2
        verts = [bm.verts.new(v) for v in ((-h, y_from, 0), (h, y_from, 0), (h, y_from + size, 0),
                                           (-h, y_from + size, 0))]
        bm.faces.new(verts)
    return shapes._link("Ground", bm, "sand", smooth=False)


def engine_void(target=(0, 0, 0.22), scale=1.0):
    """A's car engine: a black void, warm orange rim lights from behind on both sides, a soft key from the front
    left, so a cut-open engine floats glowing at its edges. `scale` sizes the rig to the machine (1: half a metre)."""
    _world(color=(0.0004, 0.0004, 0.0005), reflect=(0.06, 0.035, 0.02))
    t = Vector(target)
    for name, at, energy, color in (("RimL", (-0.8, 0.9, 0.5), 60.0, (1.0, 0.45, 0.15)),
                                    ("RimR", (0.9, 0.8, 0.45), 55.0, (1.0, 0.5, 0.2)),
                                    ("Key", (-0.5, -1.0, 0.7), 18.0, (1.0, 0.92, 0.85))):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy * scale * scale
        data.size = 0.6 * scale
        data.color = color
        light = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(light)
        light.location = t + Vector(at) * scale
        track = light.constraints.new("TRACK_TO")
        aim = bpy.data.objects.new(f"{name}.aim", None)
        bpy.context.scene.collection.objects.link(aim)
        aim.location = t
        track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"


def _sky_picture(tree):
    """The sky set's gradient, fixed to the picture, in a node tree: blue, paler toward the horizon, a darker line, pale ground."""
    coords = tree.nodes.new("ShaderNodeTexCoord")
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(coords.outputs["Window"], split.inputs[0])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    tree.links.new(split.outputs["Y"], ramp.inputs["Fac"])
    stops = ((0.0, SKY_GROUND), (0.27, SKY_GROUND), (0.345, SKY_LINE), (0.365, SKY_LOW), (0.55, SKY_LOW),
             (1.0, SKY_TOP))
    elements = ramp.color_ramp.elements
    while len(elements) < len(stops):
        elements.new(0.5)
    for element, (at, color) in zip(elements, stops):
        element.position = at
        element.color = (*color, 1)
    return ramp


def _hidden_floor(reach=300.0):
    """A floor nobody can see, at z 0: it shows exactly the picture behind it, so all it does is hide what's planted below the ground, such
    as the buried end of a tree, which the set's floor, being only a picture, wouldn't."""
    mesh = bpy.data.meshes.new("hidden_floor")
    mesh.from_pydata([(-reach, -reach, 0), (reach, -reach, 0), (reach, reach, 0), (-reach, reach, 0)], [], [[0, 1, 2, 3]])
    floor = bpy.data.objects.new("hidden_floor", mesh)
    bpy.context.scene.collection.objects.link(floor)
    floor.visible_shadow = False
    mat = bpy.data.materials.new("hidden_floor")
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    shown = tree.nodes.new("ShaderNodeEmission")
    tree.links.new(_sky_picture(tree).outputs["Color"], shown.inputs["Color"])
    shown.inputs["Strength"].default_value = SKY_STRENGTH
    tree.links.new(shown.outputs["Emission"], tree.nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    mesh.materials.append(mat)


PLACE_SKY_MOST = 1.1     # how bright a place's sky can look: above this, it blooms over what's in front of it


def place(sky: str, ground: str | None = None, turn: float = 0.0, bright: float = 1.0, tile: float = 2.0, reach: float = 26.0, shade: float = 1.0):
    """A real place: a Poly Haven sky all round, which moves with the camera as a real one does, so a shot that travels shows it. And real ground under
    it, `tile` meters a repeat, out to `reach` meters, where it fades into the ground in the picture. `turn` swings the place round, in degrees, and `bright`
    is how strongly it lights things, and `shade` darkens the ground, for a place that's darker than what lights it."""
    _world(hdri=sky, strength=bright, rotation=math.radians(turn), most=PLACE_SKY_MOST)
    bpy.context.scene.world.use_sun_shadow = True
    if ground:
        _fading_ground(ground, tile, reach, shade)


def room_behind(sky: str, turn: float = 0.0, bright: float = 1.0) -> None:
    """A real room behind a set with its own lighting, for what the camera sees past it: a counter in a lab. What lights the things on it stays as it was."""
    tree = bpy.context.scene.world.node_tree
    mix = next(n for n in tree.nodes if n.type == "MIX_SHADER")
    env = tree.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRIS[sky], check_existing=True)
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (0, 0, math.radians(turn))
    coords = tree.nodes.new("ShaderNodeTexCoord")
    tree.links.new(coords.outputs["Generated"], mapping.inputs["Vector"])
    tree.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    held = tree.nodes.new("ShaderNodeVectorMath")
    held.operation = "MINIMUM"
    tree.links.new(env.outputs["Color"], held.inputs[0])
    held.inputs[1].default_value = (PLACE_SKY_MOST, PLACE_SKY_MOST, PLACE_SKY_MOST)
    seen = tree.nodes.new("ShaderNodeBackground")
    seen.inputs["Strength"].default_value = bright
    tree.links.new(held.outputs["Vector"], seen.inputs["Color"])
    tree.links.new(seen.outputs[0], mix.inputs[2])


def _fading_ground(texture: str, tile: float, reach: float, shade: float = 1.0) -> None:
    n = 64
    mesh = bpy.data.meshes.new("Ground")
    mesh.from_pydata([(reach * math.cos(i * math.tau / n), reach * math.sin(i * math.tau / n), 0) for i in range(n)], [], [list(range(n))])
    floor = bpy.data.objects.new("Ground", mesh)
    bpy.context.scene.collection.objects.link(floor)
    mat = bpy.data.materials.new("Ground")
    mat.use_nodes = True
    mat.surface_render_method = "BLENDED"
    tree = mat.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    picture = materials._textured(tree, bsdf, texture, scale=1 / tile)
    darker = tree.nodes.new("ShaderNodeVectorMath")
    darker.operation = "SCALE"
    tree.links.new(picture.outputs["Color"], darker.inputs[0])
    darker.inputs["Scale"].default_value = shade
    tree.links.new(darker.outputs["Vector"], bsdf.inputs["Base Color"])
    coords = tree.nodes.new("ShaderNodeTexCoord")
    far = tree.nodes.new("ShaderNodeVectorMath")
    far.operation = "LENGTH"
    tree.links.new(coords.outputs["Object"], far.inputs[0])
    fade = tree.nodes.new("ShaderNodeMapRange")
    fade.interpolation_type = "SMOOTHERSTEP"
    fade.inputs["From Min"].default_value, fade.inputs["From Max"].default_value = reach * 0.3, reach * 0.95
    fade.inputs["To Min"].default_value, fade.inputs["To Max"].default_value = 1.0, 0.0
    tree.links.new(far.outputs["Value"], fade.inputs["Value"])
    mix = tree.nodes.new("ShaderNodeMixShader")
    tree.links.new(fade.outputs["Result"], mix.inputs[0])
    tree.links.new(tree.nodes.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    tree.links.new(bsdf.outputs[0], mix.inputs[2])
    tree.links.new(mix.outputs[0], tree.nodes["Material Output"].inputs["Surface"])
    mesh.materials.append(mat)


def sky_set(strength=0.7, ambient=(0.62, 0.74, 0.90)):
    """A clean sky behind a person, as in the character reference: blue, paler toward the horizon, with a soft darker
    line low in the picture and pale ground below it. The camera sees the gradient, fixed to the picture so a move
    can't shift it; everything else is lit by an even pale sky. Colors are chosen to come out right through AgX."""
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    tree = world.node_tree
    lit = tree.nodes["Background"]
    lit.inputs["Color"].default_value = (*ambient, 1)
    lit.inputs["Strength"].default_value = strength
    ramp = _sky_picture(tree)
    _hidden_floor()
    seen = tree.nodes.new("ShaderNodeBackground")
    tree.links.new(ramp.outputs["Color"], seen.inputs["Color"])
    seen.inputs["Strength"].default_value = SKY_STRENGTH
    path = tree.nodes.new("ShaderNodeLightPath")
    mix = tree.nodes.new("ShaderNodeMixShader")
    tree.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    tree.links.new(lit.outputs["Background"], mix.inputs[1])
    tree.links.new(seen.outputs["Background"], mix.inputs[2])
    tree.links.new(mix.outputs["Shader"], tree.nodes["World Output"].inputs["Surface"])
    bpy.context.scene.world = world


def sky_counter(depth: float = 1.0):
    """A clean blue backdrop behind a matte wooden counter, level across the picture, for showing things up close. The counter's
    top is at z 0, and it goes `depth` meters back. The backdrop is fixed to the picture and is what the camera sees past the counter; everything else, reflections
    included, sees a studio: a bright soft overhead, a pale band at the horizon, darker warm below, with broad soft stripes around
    it so steel has something to mirror. No people-flattering front light: things are lit from above and to the side, so a shape
    reads. Its colors go straight to the screen (the Standard view), matched to the reference's by number."""
    scene = bpy.context.scene
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    tree = world.node_tree
    lit = tree.nodes["Background"]
    coords = tree.nodes.new("ShaderNodeTexCoord")
    way = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(coords.outputs["Generated"], way.inputs[0])
    height = tree.nodes.new("ShaderNodeMapRange")
    height.inputs["From Min"].default_value, height.inputs["From Max"].default_value = -1.0, 1.0
    tree.links.new(way.outputs["Z"], height.inputs["Value"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    tree.links.new(height.outputs["Result"], ramp.inputs["Fac"])
    stops = ((0.0, (0.2, 0.17, 0.15)), (0.46, (0.66, 0.6, 0.56)), (0.53, (0.95, 1.0, 1.1)), (0.66, (0.30, 0.36, 0.46)),
             (0.73, (0.5, 0.52, 0.58)), (0.79, (1.7, 1.7, 1.75)), (0.85, (0.34, 0.34, 0.38)), (1.0, (0.42, 0.42, 0.46)))
    elements = ramp.color_ramp.elements
    while len(elements) < len(stops):
        elements.new(0.5)
    for element, (at, color) in zip(elements, stops):
        element.position = at
        element.color = (*color, 1)
    round_it = tree.nodes.new("ShaderNodeMath")
    round_it.operation = "ARCTAN2"
    tree.links.new(way.outputs["Y"], round_it.inputs[0])
    tree.links.new(way.outputs["X"], round_it.inputs[1])
    stripes = tree.nodes.new("ShaderNodeMath")
    stripes.operation = "SINE"
    times = tree.nodes.new("ShaderNodeMath")
    times.operation = "MULTIPLY"
    times.inputs[1].default_value = 5.0
    tree.links.new(round_it.outputs[0], times.inputs[0])
    tree.links.new(times.outputs[0], stripes.inputs[0])
    band = tree.nodes.new("ShaderNodeMapRange")
    band.inputs["From Min"].default_value, band.inputs["From Max"].default_value = -1.0, 1.0
    band.inputs["To Min"].default_value, band.inputs["To Max"].default_value = 0.55, 1.2
    tree.links.new(stripes.outputs[0], band.inputs["Value"])
    shade = tree.nodes.new("ShaderNodeVectorMath")
    shade.operation = "SCALE"
    tree.links.new(ramp.outputs["Color"], shade.inputs[0])
    tree.links.new(band.outputs["Result"], shade.inputs["Scale"])
    tree.links.new(shade.outputs["Vector"], lit.inputs["Color"])
    lit.inputs["Strength"].default_value = 0.55
    # what the camera sees past the counter: the reference's blue, lighter toward the middle of the picture
    window = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(coords.outputs["Window"], window.inputs[0])
    across = tree.nodes.new("ShaderNodeMath")
    across.operation = "SUBTRACT"
    across.inputs[1].default_value = 0.5
    tree.links.new(window.outputs["X"], across.inputs[0])
    narrow = tree.nodes.new("ShaderNodeMath")
    narrow.operation = "MULTIPLY"
    narrow.inputs[1].default_value = 0.5625
    tree.links.new(across.outputs[0], narrow.inputs[0])
    up = tree.nodes.new("ShaderNodeMath")
    up.operation = "SUBTRACT"
    up.inputs[1].default_value = 0.6
    tree.links.new(window.outputs["Y"], up.inputs[0])
    both = tree.nodes.new("ShaderNodeCombineXYZ")
    tree.links.new(narrow.outputs[0], both.inputs["X"])
    tree.links.new(up.outputs[0], both.inputs["Y"])
    far = tree.nodes.new("ShaderNodeVectorMath")
    far.operation = "LENGTH"
    tree.links.new(both.outputs[0], far.inputs[0])
    fall = tree.nodes.new("ShaderNodeMapRange")
    fall.inputs["From Min"].default_value, fall.inputs["From Max"].default_value = 0.02, 0.42
    tree.links.new(far.outputs["Value"], fall.inputs["Value"])
    sky = tree.nodes.new("ShaderNodeValToRGB")
    tree.links.new(fall.outputs["Result"], sky.inputs["Fac"])
    sky.color_ramp.interpolation = "EASE"
    sky.color_ramp.elements[0].color = (0.235, 0.46, 0.62, 1)   # the reference's middle, (129, 180, 204)
    sky.color_ramp.elements[1].color = (0.060, 0.29, 0.62, 1)   # and its edge, (71, 147, 205)
    seen = tree.nodes.new("ShaderNodeBackground")
    tree.links.new(sky.outputs["Color"], seen.inputs["Color"])
    path = tree.nodes.new("ShaderNodeLightPath")
    mix = tree.nodes.new("ShaderNodeMixShader")
    tree.links.new(path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    tree.links.new(lit.outputs["Background"], mix.inputs[1])
    tree.links.new(seen.outputs["Background"], mix.inputs[2])
    tree.links.new(mix.outputs["Shader"], tree.nodes["World Output"].inputs["Surface"])
    scene.world = world
    top = shapes.box("Counter", (8.0, depth, 0.05), "counter_wood", at=(0, -0.08 + (depth - 1.0) / 2, -0.025), bevel=0.003)
    front = shapes.box("Cabinet", (8.0, 0.95, 1.2), None, at=(0, -0.055, -0.65))
    materials.custom("cabinet", color=(0.16, 0.10, 0.07), rough=0.55)
    materials.assign(front, "cabinet")
    for name, at, energy, size, shine in (("Key", (-0.75, -1.05, 1.45), 42.0, 2.4, 0.16), ("Fill", (1.25, -0.9, 0.75), 11.0, 2.6, 0.12),
                                          ("Back", (0.2, 1.25, 1.1), 16.0, 2.0, 0.5)):
        data = bpy.data.lights.new(name, "AREA")
        data.shape = "DISK"
        data.energy = energy
        data.size = size
        data.specular_factor = shine
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = at
        aim = bpy.data.objects.new(f"{name}.aim", None)
        scene.collection.objects.link(aim)
        aim.location = (0, 0, 0.12)
        track = light.constraints.new("TRACK_TO")
        track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
    return [top, front]


SHADOW_RADIUS = 0.62     # how far a patch of shadow under someone reaches (m)


def floor_shadow(name, at, radius=SHADOW_RADIUS, darkness=0.5):
    """A soft dark patch on the ground under someone, on a set with no floor to catch a real shadow, so feet touch it."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(radius * math.cos(i * math.tau / 48), radius * math.sin(i * math.tau / 48), 0) for i in range(48)], [],
                     [list(range(48))])
    disc = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(disc)
    disc.location = (at[0], at[1], 0.002)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.surface_render_method = "BLENDED"
    tree = mat.node_tree
    tree.nodes.clear()
    coords = tree.nodes.new("ShaderNodeTexCoord")
    length = tree.nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    tree.links.new(coords.outputs["Object"], length.inputs[0])
    fade = tree.nodes.new("ShaderNodeMapRange")
    fade.interpolation_type = "SMOOTHERSTEP"
    fade.inputs["From Min"].default_value, fade.inputs["From Max"].default_value = 0.0, radius
    fade.inputs["To Min"].default_value, fade.inputs["To Max"].default_value = darkness, 0.0
    tree.links.new(length.outputs["Value"], fade.inputs["Value"])
    mix = tree.nodes.new("ShaderNodeMixShader")
    tree.links.new(fade.outputs["Result"], mix.inputs[0])
    tree.links.new(tree.nodes.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[1])
    dark = tree.nodes.new("ShaderNodeEmission")
    dark.inputs["Color"].default_value = (0.02, 0.04, 0.09, 1)
    tree.links.new(dark.outputs[0], mix.inputs[2])
    tree.links.new(mix.outputs[0], tree.nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    mesh.materials.append(mat)
    return disc


# in linear color, times SKY_STRENGTH. AgX washes out strong blue, so these overshoot what they're meant to look like
SKY_STRENGTH = 1.6
SKY_TOP = (0.0, 0.34, 0.70)       # the sky at the top of the picture
SKY_LOW = (0.10, 0.60, 1.0)       # near the horizon
SKY_LINE = (0.06, 0.26, 0.56)     # the soft dark line
SKY_GROUND = (0.32, 0.50, 0.78)   # the pale ground below it


def portrait_lights(face, key=125.0, fill=55.0, rim=45.0, reach=1.0, facing=0.0):
    """Big soft lights on a person's face at the world point `face`, bright as the reference is: a key from the front
    left and above, a fill from the front right, and a rim from behind to lift the hair off the sky. They're round, so
    a catchlight in an eye looks like one. `reach` moves them out and brightens them to match, for something bigger. `facing`
    is the way they face, in degrees, as a person's is: the lights come from in front of them, whichever way that is.
    Returns the lights and what they aim at, for moving them with someone."""
    made = []
    turn = Quaternion((0, 0, 1), math.radians(facing))
    for name, at, energy, size in (("Key", (-1.1, -2.2, 1.0), key, 2.4), ("Fill", (1.8, -2.0, 0.1), fill, 3.0),
                                   ("Rim", (0.8, 1.8, 1.2), rim, 1.6)):
        data = bpy.data.lights.new(name, "AREA")
        data.shape = "DISK"
        data.energy = energy * reach * reach
        data.size = size * reach
        light = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(light)
        light.location = Vector(face) + turn @ (Vector(at) * reach)
        aim = bpy.data.objects.new(f"{name}.aim", None)
        bpy.context.scene.collection.objects.link(aim)
        aim.location = face
        track = light.constraints.new("TRACK_TO")
        track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
        made += [light, aim]
    return made


def _gym_wall(at, along, length, height=9.0):
    """One wall: blue paint, a dark band low down with slats, tall pale panels with thin bars, and wood posts between
    them. `at` is its middle on the floor, `along` (x or y) the way it runs. Everything's a little out of focus in a shot,
    so this is only as detailed as a blurred wall needs to be."""
    def box(name, size, offset, material):
        sx, sd, sz = size
        ox, od, oz = offset
        real = (sx, sd, sz) if along == "x" else (sd, sx, sz)
        place = (at[0] + ox, at[1] + od, oz) if along == "x" else (at[0] + od, at[1] + ox, oz)
        shapes.box(name, real, material, at=place)

    tag = f"{at[0]:.0f}_{at[1]:.0f}"
    box(f"Wall{tag}", (length, 0.2, height), (0, 0, height / 2), "gym_wall")
    for z in (0.28, 0.5, 0.72, 0.94):
        box(f"Slat{tag}_{z}", (length, 0.28, 0.1), (0, 0, z), "gym_panel")
    count = int(length / 2.6)
    for i in range(count):
        x = (i - (count - 1) / 2) * 2.6
        box(f"Panel{tag}_{i}", (2.1, 0.26, 2.3), (x, 0, 2.35), "gym_panel")
        for b in range(1, 6):
            box(f"Bar{tag}_{i}_{b}", (0.035, 0.3, 2.3), (x - 1.05 + b * 0.35, 0, 2.35), "gym_trim")
        box(f"Post{tag}_{i}", (0.2, 0.34, height), (x + 1.3, 0, height / 2), "wood")


def gym(size=26.0):
    """A training hall, as in the character reference: a dark board floor, blue walls with tall pale panels, and two
    wooden training posts behind where a person stands. Bright and even: a person adds envs.portrait_lights()."""
    _world(color=(0.60, 0.70, 0.84), strength=0.75)
    floor = _ground(size)
    materials.assign(floor, "floorboards")
    _gym_wall((0, 4.6, 0), "x", 18.0)
    _gym_wall((0, -7.0, 0), "x", 18.0)
    _gym_wall((-8.0, -1.2, 0), "y", 13.0)
    _gym_wall((8.0, -1.2, 0), "y", 13.0)
    for i, x in enumerate((-1.7, 1.7)):
        shapes.cylinder(f"Dummy{i}", 0.11, 1.75, "wood", at=(x, 2.1, 0), segments=24)
        for k, z in enumerate((1.45, 1.2, 0.9)):
            arm = shapes.cylinder(f"DummyArm{i}_{k}", 0.028, 0.42, "wood", at=(x, 2.1, z), segments=12)
            arm.rotation_euler = (math.radians(90), 0, math.radians(35 - 70 * k / 2))


def studio(size=40.0):
    """A soft grey studio for model sheets: a pale floor, an even grey sky, a key light and a fill, so every part
    reads clearly from any side."""
    _world(color=(0.42, 0.44, 0.47), strength=0.7)
    floor = _ground(size)
    materials.assign(floor, "white_paint")
    for name, rot, energy in (("Key", (50, 0, -35), 3.0), ("Rim", (60, 0, 150), 1.2)):
        data = bpy.data.lights.new(name, "SUN")
        data.energy = energy
        data.angle = math.radians(8)
        sun = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(sun)
        sun.rotation_euler = tuple(math.radians(a) for a in rot)


def workbench(block=(0.5, 0.26, 0.12), target=(0.0, 0.0, 0.12), elevation=54.0, azimuth=37.0, distance=0.5):
    """A pale wood block on black under one warm spot. A's light, read from its nail's shadow: about 54 degrees up,
    in front and 37 degrees to the left. So the top is brighter than a face toward the camera, a face toward the
    right is in shadow, and a nail's shadow falls back and to the right across the top. The spot is aimed at
    `target` from `distance` meters, and its pool fades to black at the edges. Returns the block, standing on z 0
    with its middle at x 0, y 0."""
    _world(color=(0.0005, 0.0005, 0.0006), reflect=(0.09, 0.08, 0.07))
    floor = _ground(40.0)
    materials.assign(floor, "rubber")
    wood = shapes.box("Block", block, "pale_wood", at=(0, 0, block[2] / 2), bevel=0.002) if block else None
    data = bpy.data.lights.new("Lamp", "SPOT")
    data.energy = 18.0
    data.color = (1.0, 0.78, 0.55)
    data.spot_size = math.radians(40)   # the pool fades out before the block's back edge
    data.spot_blend = 0.85
    data.shadow_soft_size = 0.006   # a crisp nail shadow
    lamp = bpy.data.objects.new("Lamp", data)
    bpy.context.scene.collection.objects.link(lamp)
    up, around = math.radians(elevation), math.radians(azimuth)
    flat = distance * math.cos(up)
    lamp.location = Vector(target) + Vector((-flat * math.sin(around), -flat * math.cos(around),
                                             distance * math.sin(up)))
    aim = bpy.data.objects.new("Lamp.aim", None)
    bpy.context.scene.collection.objects.link(aim)
    aim.location = target
    track = lamp.constraints.new("TRACK_TO")
    track.target = aim
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    return wood
