"""How every machine short is rendered: EEVEE on the GPU, AgX color, soft shadows, a little bloom, and the camera.

Reference A (SHORTS.md) is clean PBR with soft sun shadows, shallow depth of field and gentle highlights, so the
settings aim there and stay the same for every shot; a shot only picks its camera and lights.
"""
from __future__ import annotations

import bpy
from mathutils import Vector


def _cycles(scene, samples: int) -> None:
    """Cycles on the GPU, denoised, for what EEVEE can't make look right (skin, if it does). Without an RTX card it
    runs on the CPU."""
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    gpus = [d for d in prefs.devices if d.type == "OPTIX"]
    for device in prefs.devices:
        device.use = device in gpus
    scene.cycles.device = "GPU" if gpus else "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"


def setup(scene, size=(1080, 1920), fps=30, samples=32, look="AgX - Medium High Contrast", exposure=0.0,
          bloom=0.25, motion_blur=0.5, engine="eevee") -> None:
    scene.render.engine = "BLENDER_EEVEE"
    if engine == "cycles":
        _cycles(scene, samples)
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.render.film_transparent = False
    # A smears fast moves (a hammer swinging in); `motion_blur` is the shutter, in frames (0 for none)
    scene.render.use_motion_blur = motion_blur > 0
    scene.render.motion_blur_shutter = max(motion_blur, 0.01)
    ee = scene.eevee
    ee.taa_render_samples = samples
    ee.use_shadows = True
    ee.shadow_ray_count = 2       # soft shadow edges without grain
    ee.shadow_step_count = 6
    ee.use_raytracing = True      # screen-space reflections on steel and chrome
    ee.use_fast_gi = True         # contact shadows in corners and under parts, the ambient occlusion look
    ee.fast_gi_distance = 0.6
    ee.use_volumetric_shadows = False
    vs = scene.view_settings
    vs.view_transform = "AgX"
    vs.look = look
    vs.exposure = exposure
    image = scene.render.image_settings
    image.file_format = "PNG"
    image.color_mode = "RGB"
    image.color_depth = "8"
    _compositor(scene, bloom)


def _compositor(scene, bloom: float) -> None:
    """A soft bloom on the brightest highlights (an ignition flash, sun on chrome), through Blender 5's compositor
    node group."""
    tree = bpy.data.node_groups.new("Look", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    layers = tree.nodes.new("CompositorNodeRLayers")
    out = tree.nodes.new("NodeGroupOutput")
    if bloom > 0:
        glare = tree.nodes.new("CompositorNodeGlare")
        glare.inputs["Type"].default_value = "Bloom"
        glare.inputs["Quality"].default_value = "High"
        glare.inputs["Threshold"].default_value = 1.8   # only real glow (fire, a flash), not white paint in sun
        glare.inputs["Strength"].default_value = bloom
        glare.inputs["Size"].default_value = 0.5
        tree.links.new(layers.outputs["Image"], glare.inputs["Image"])
        tree.links.new(glare.outputs["Image"], out.inputs["Image"])
    else:
        tree.links.new(layers.outputs["Image"], out.inputs["Image"])
    scene.compositing_node_group = tree


def halo(scene, threshold: float, strength: float, size: float) -> None:
    """How the bloom sits on this scene: only what's brighter than `threshold` gets a halo, so a lit line has one and white
    paint doesn't."""
    glare = next((n for n in scene.compositing_node_group.nodes if n.type == "GLARE"), None)
    if glare is not None:
        glare.inputs["Threshold"].default_value = threshold
        glare.inputs["Strength"].default_value = strength
        glare.inputs["Size"].default_value = size


def camera(scene, at, look_at, lens=35.0, fstop=4.0, focus=None, name="Camera"):
    """A camera at `at` aimed at `look_at` through an empty it tracks, so a shot moves either one by keyframes.
    Depth of field focuses on `focus` (an object) or else on the aim point."""
    target = bpy.data.objects.new(f"{name}.aim", None)
    scene.collection.objects.link(target)
    target.location = Vector(look_at)
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.sensor_fit = "VERTICAL"
    data.sensor_height = 24.0
    data.clip_start = 0.01
    data.clip_end = 2000.0
    data.dof.use_dof = fstop > 0
    data.dof.aperture_fstop = max(fstop, 0.5)
    data.dof.focus_object = focus or target
    cam = bpy.data.objects.new(name, data)
    scene.collection.objects.link(cam)
    cam.location = Vector(at)
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    scene.camera = cam
    return cam, target


def key(obj, frame: int, **values) -> None:
    """Set and keyframe properties on `obj` at `frame`, e.g. key(ram, 10, location=(0, 0, 1.2))."""
    for path, value in values.items():
        setattr(obj, path, value)
        obj.keyframe_insert(data_path=path, frame=frame)


EASES = {"linear": ("LINEAR", "AUTO"), "in": ("QUAD", "EASE_IN"), "out": ("QUAD", "EASE_OUT"),
         "inout": ("BEZIER", "AUTO"), "const": ("CONSTANT", "AUTO")}


def ease(obj, kind="BEZIER") -> None:
    """Interpolation for every key on `obj`: BEZIER (or inout) eases in and out, LINEAR constant speed, in speeds
    up, out slows down."""
    anim = obj.animation_data
    if not anim or not anim.action:
        return
    interpolation, easing = EASES.get(kind, (kind, "AUTO"))
    for curve in _fcurves(anim.action):
        for point in curve.keyframe_points:
            point.interpolation = interpolation
            point.easing = easing


def _fcurves(action):
    """An action's F-curves. Blender 5 keeps them in layered slots; older actions had them directly."""
    if hasattr(action, "layers") and action.layers:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    yield from bag.fcurves
    else:
        yield from getattr(action, "fcurves", [])
