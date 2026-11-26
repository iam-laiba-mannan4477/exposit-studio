"""Optional 3D shots rendered by Blender (installed by the user; never downloaded or installed by the studio).

Blender runs headless only: `blender -b --factory-startup --threads 2 -P <generated script> -- <args.json>`, one
process at a time, with a timeout and a clean kill. The generated script builds the scene from primitives and
procedural materials only (no add-ons, no downloaded models or textures; the globe uses our local NASA texture),
renders a transparent RGBA PNG sequence with EEVEE at 16 samples, and writes the projected screen position of named
anchors for every frame (anchors.json). Text is NEVER rendered in Blender: the skia treatment composites the frames
and draws every label and keyword on top, at the anchors, so they stay sharp and readable.

Shots are cached by a hash of their render spec: <shots dir>/<hash>/f_0001.png ..., anchors.json, done.json,
blender.log. If Blender is missing, the brief says "no 3D", or a render fails or times out, the scene falls back to a
2D treatment (fallback_spec) and the reason is logged; a production never fails because of Blender.

Spec (scene): {"treatment": "blender3d", "shot": one of SHOT_TYPES, "params": {...}, "labels": [{"text", "anchor",
"at", "dx", "dy", "size", "progress"}], "frames": optional, "camera": {"orbit": deg, "dolly": m, "dof": bool},
"palette": optional {"bg", "base", "accent", "glow", "rim", "text"}, "fallback": optional 2D spec}.
"""
from __future__ import annotations
import glob, hashlib, json, os, re, shutil, subprocess, threading, time
from pathlib import Path

from .. import config

SHOT_TYPES = ("layers3d", "path3d", "stack3d", "network3d", "device3d", "globe3d")
CAMERA_DEFAULTS = {"layers3d": {"distance": 9.5, "elevation": 28, "target": (0, 0, 1.1)},
                   "path3d": {"distance": 13.0, "elevation": 38, "target": (0, 5, 0)},
                   "stack3d": {"distance": 8.0, "elevation": 26, "target": (0, 0, 0.8)},
                   "network3d": {"distance": 9.0, "elevation": 30},
                   "device3d": {"distance": 8.5, "elevation": 18, "target": (0, 0, 1.4)},
                   "globe3d": {"distance": 9.0, "elevation": 8, "target": (0, 0, 1.2)}}
SCRIPT_VERSION = "1"
SAMPLES = 8
THREADS = 2
MAX_3D_SIDE = 1280                             # the 3D layer renders at most 720x1280 (9:16) and is upscaled when composited
MAX_RSS_MB = int(config.env("BLENDER_MAX_MB", "2500"))   # the watchdog: above this, the render is aborted (2D fallback)
SEC_PER_FRAME = {540: 1.0, 1080: 2.2}          # EEVEE on this laptop: ~1 s/frame at 540x960 measured; 720x1280 estimated
MAX_SHOTS_PER_MINUTE = 3
_lock = threading.Lock()                       # one Blender process at a time


# ================================================================== detection
def _version_key(p: str) -> tuple:
    m = re.search(r"Blender\s*([\d.]+)", p)
    return tuple(int(x) for x in m.group(1).split(".") if x.isdigit()) if m else ()


def find_blender() -> str | None:
    """BLENDER_PATH in .env, else the newest C:\\Program Files\\Blender Foundation\\Blender*\\blender.exe, else PATH."""
    explicit = config.env("BLENDER_PATH").strip()
    if explicit:
        return explicit if Path(explicit).is_file() else None
    found = glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe")
    if found:
        return sorted(found, key=_version_key)[-1]
    return shutil.which("blender")


_info: dict = {}


def info(refresh: bool = False) -> dict:
    """{"path", "version"} or {"path": None}; cached for the process."""
    if _info and not refresh:
        return _info
    _info.clear()
    path = find_blender()
    _info["path"] = path
    _info["version"] = ""
    if path:
        try:
            r = subprocess.run([path, "-b", "--factory-startup", "--version"], capture_output=True, text=True, timeout=60,
                               encoding="utf-8", errors="replace")
            m = re.search(r"Blender\s+([\d.]+)", r.stdout)
            _info["version"] = m.group(1) if m else ""
        except Exception as e:                           # noqa: BLE001
            _info["error"] = f"{type(e).__name__}: {e}"
    return _info


def available() -> bool:
    return bool(info().get("path"))


def wanted(brief: dict | None) -> bool:
    """3D is used only when Blender is present and the brief does not say "no 3D"."""
    return available() and str((brief or {}).get("three_d", "auto")).lower() not in ("off", "no", "none", "false")


# ================================================================== the generated bpy script
HEADER = r'''
import bpy, json, math, sys
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
A = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
P = A["palette"]
scn = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
engines = {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
scn.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
def _set(obj, **kw):                                  # set what this Blender version has; ignore the rest
    for k, v in kw.items():
        try:
            setattr(obj, k, v)
        except Exception:
            pass


ev = scn.eevee
_set(ev, taa_render_samples=A["samples"], use_raytracing=False, use_volumetric_shadows=False, use_volumetric_lights=False,
     use_ssr=False, use_ssr_refraction=False, use_gtao=False, use_motion_blur=False, use_shadows=True,
     shadow_cube_size="512", shadow_cascade_size="1024", shadow_pool_size="128", shadow_resolution_scale=0.5,
     volumetric_tile_size="16", volumetric_samples=8, use_bloom=bool(A.get("bloom")))
_set(bpy.context.preferences.system, gl_texture_limit="CLAMP_1024")   # cap texture size on the GPU
_set(scn.render, use_simplify=True, simplify_subdivision_render=1)
scn.render.resolution_x, scn.render.resolution_y, scn.render.resolution_percentage = A["w"], A["h"], 100
scn.render.film_transparent = A["transparent"]
scn.render.use_persistent_data = False
scn.render.image_settings.file_format = "PNG"
scn.render.image_settings.color_mode = "RGBA"
scn.render.fps = A["fps"]
try:
    scn.view_settings.view_transform = "Standard"           # the palette's real colours (AgX/Filmic wash them out)
    scn.view_settings.look = "None"
except Exception:
    pass
scn.frame_start, scn.frame_end = 1, A["frames"]
scn.render.filepath = A["out"] + "/f_"
F = A["frames"]


def lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


world = bpy.data.worlds.new("w")
scn.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (*lin(P["bg"]), 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.25


def mat(name, hexc, emit=0.0, alpha=1.0, rough=0.45, noise=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*lin(hexc), 1)
    b.inputs["Roughness"].default_value = rough
    if noise > 0:                                  # a subtle procedural surface variation (no image textures)
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = 6.0
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = noise
        mix.inputs[6].default_value = (*lin(hexc), 1)
        nt.links.new(n.outputs["Fac"], mix.inputs[7])            # grey, not rainbow
        nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
    if emit > 0:
        key = "Emission Color" if "Emission Color" in b.inputs else "Emission"
        b.inputs[key].default_value = (*lin(hexc), 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def box(name, size, loc, material, bevel=0.06):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)   # real size: anchors are not scaled
    if bevel:
        md = o.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = 3
    o.data.materials.append(material)
    return o


def sphere(name, r, loc, material, seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=seg // 2)
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.shade_smooth()
    o.data.materials.append(material)
    return o


def tube(name, pts, radius, material):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for p, co in zip(sp.bezier_points, pts):
        p.co = co
        p.handle_left_type = p.handle_right_type = "AUTO"
    o = bpy.data.objects.new(name, cu)
    scn.collection.objects.link(o)
    o.data.materials.append(material)
    return o


def key(o, attr, frames_values):
    for f, v in frames_values:
        setattr(o, attr, v)
        o.keyframe_insert(data_path=attr, frame=f)


ANCHORS = {}
OWNER = {}


def anchor(name, loc, parent=None, of=None):
    """A named point for labels. With a parent, loc is in the parent's (real-size) space and follows it. `of` is the
    object whose screen bounds the anchor must stay inside (default: the parent)."""
    e = bpy.data.objects.new("anchor_" + name, None)
    e.location = loc
    scn.collection.objects.link(e)
    if parent is not None:
        e.parent = parent
    ANCHORS[name] = e
    OWNER[name] = of if of is not None else parent
    return e
'''

FOOTER = r'''
# lights: a soft area key and a rim light
for nm, loc, energy, col, size in (("key", (4, -5, 6), 900, "#FFFFFF", 6), ("rim", (-5, 6, 4), 700, P["rim"], 4)):
    ld = bpy.data.lights.new(nm, "AREA")
    ld.energy, ld.size, ld.color = energy, size, lin(col)
    lo = bpy.data.objects.new(nm, ld)
    lo.location = loc
    scn.collection.objects.link(lo)
    tc = lo.constraints.new("TRACK_TO")
    tgt = bpy.data.objects.new(nm + "_t", None)
    scn.collection.objects.link(tgt)
    tc.target = tgt
# camera: a slow orbit + dolly with ease-in-out (Bezier) keys, looking at the target
C = A["camera"]
target = bpy.data.objects.new("cam_target", None)
target.location = C.get("target", (0, 0, 0.6))
scn.collection.objects.link(target)
pivot = bpy.data.objects.new("cam_pivot", None)
pivot.location = target.location
scn.collection.objects.link(pivot)
cd = bpy.data.cameras.new("cam")
cd.lens = C.get("lens", 40)
cd.sensor_fit = "HORIZONTAL" if A["h"] > A["w"] else "AUTO"
cam = bpy.data.objects.new("cam", cd)
scn.collection.objects.link(cam)
cam.parent = pivot
dist, elev = C.get("distance", 9.0), math.radians(C.get("elevation", 24))
d0, d1 = dist, dist - C.get("dolly", 0.8)
key(cam, "location", [(1, (0, -d0 * math.cos(elev), d0 * math.sin(elev))), (F, (0, -d1 * math.cos(elev), d1 * math.sin(elev)))])
o0 = math.radians(C.get("orbit_from", -12)); o1 = o0 + math.radians(C.get("orbit", 24))
key(pivot, "rotation_euler", [(1, (0, 0, o0)), (F, (0, 0, o1))])
tc = cam.constraints.new("TRACK_TO")
tc.target = target
scn.camera = cam
if C.get("dof"):
    cd.dof.use_dof = True
    cd.dof.focus_object = target
    cd.dof.aperture_fstop = C.get("fstop", 4.0)
# anchors: the projected screen position of each named point, every frame (y down, 0..1)
out = {"frames": F, "anchors": {k: [] for k in ANCHORS}, "bounds": {k: [] for k in ANCHORS}, "progress": []}
for f in range(1, F + 1):
    scn.frame_set(f)
    deps = bpy.context.evaluated_depsgraph_get()            # evaluated: follow-path, parents and keys included
    ce = cam.evaluated_get(deps)
    for k, e in ANCHORS.items():
        fn = globals().get("POSITION", {}).get(k)
        wpos = fn(f) if fn else e.evaluated_get(deps).matrix_world.translation
        v = world_to_camera_view(scn, ce, wpos)
        out["anchors"][k].append([round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)])
        ow = OWNER.get(k)
        if fn:                                               # bounds: the block's size around the computed point
            pts2 = [world_to_camera_view(scn, ce, wpos + Vector((dx, dy, dz))) for dx in (-0.3, 0.3) for dy in (-0.3, 0.3) for dz in (-0.3, 0.3)]
            xs, ys = [p.x for p in pts2], [1 - p.y for p in pts2]
            out["bounds"][k].append([round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)])
        elif ow is not None:
            oe = ow.evaluated_get(deps)
            pts = [world_to_camera_view(scn, ce, oe.matrix_world @ Vector(c)) for c in oe.bound_box]
            xs, ys = [p.x for p in pts], [1 - p.y for p in pts]
            out["bounds"][k].append([round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)])
    out["progress"].append(round(PROGRESS(f), 4) if "PROGRESS" in globals() else round((f - 1) / max(1, F - 1), 4))
json.dump(out, open(A["out"] + "/anchors.json", "w"))
bpy.ops.render.render(animation=True)
'''

BUILDERS = {
 "test": r'''
box("cube", (1.4, 1.4, 1.4), (0, 0, 0.7), mat("m", P["accent"]))
anchor("cube", (0, 0, 0), parent=bpy.data.objects["cube"])
''',
 "layers3d": r'''
L = A["params"].get("layers", [{"name": "top"}, {"name": "middle", "glow": True}, {"name": "bottom"}])
n = len(L)
for i, l in enumerate(L):
    m = mat("slab%d" % i, l.get("color", P["glow"] if l.get("glow") else P["base"]), emit=1.0 if l.get("glow") else 0.0,
            alpha=0.82, noise=0.08)
    z_end = (n - 1 - i) * 1.15
    o = box("slab_" + l["name"], (5.2, 3.4, 0.22), (0, 0, z_end * 0.45), m, bevel=0.08)
    key(o, "location", [(1, (0, 0, z_end * 0.45)), (int(F * 0.45), (0, 0, z_end))])     # gentle separation
    anchor(l["name"], (2.4, -1.5, 0.0), parent=o)            # inside the slab's front-right corner
bottom = (0, 0, 0)
for j in range(A["params"].get("sink", 7)):          # tangled tool blocks sink into the bottom slab
    ang = j * 2.39996
    loc0 = (math.cos(ang) * 1.6, math.sin(ang) * 1.0, 2.6 + 0.35 * j)
    o = box("tool%d" % j, (0.36, 0.36, 0.36), loc0, mat("tool%d" % j, P["rim"], noise=0.1), bevel=0.04)
    o.rotation_euler = (ang, ang * 0.5, ang * 0.3)
    key(o, "location", [(int(F * 0.2) + j * 3, loc0), (int(F * 0.75) + j * 2, (loc0[0] * 0.7, loc0[1] * 0.7, -0.05))])
    key(o, "scale", [(int(F * 0.7) + j * 2, (1.0, 1.0, 1.0)), (int(F * 0.85) + j * 2, (0.0, 0.0, 0.0))])
''',
 "path3d": r'''
rng = [((i * 7919) % 101) / 101 for i in range(400)]
k = 0
for gx in range(-6, 7):                               # a low-poly landscape of blocks
    for gy in range(-3, 14):
        h = 0.15 + 0.9 * rng[k % 400] ** 2
        k += 1
        if abs(gx - math.sin(gy * 0.45) * 2.2) < 1.3:
            continue                                   # keep the road clear
        box("blk%d_%d" % (gx, gy), (0.9, 0.9, h), (gx, gy, h / 2), mat("blk%d" % (k % 6), P["base"], noise=0.15), bevel=0.03)
pts = [(math.sin(y * 0.45) * 2.2, y, 0.04) for y in range(-3, 14)]
road = tube("road", pts, 0.0, mat("road", P["glow"], emit=1.0))
road.data.extrude = 0.42
road.data.bevel_depth = 0.0
road.data.fill_mode = "FULL"
mover = box("mover", (0.6, 0.6, 0.6), pts[0], mat("mover", P["accent"], emit=0.6), bevel=0.08)
fp = mover.constraints.new("FOLLOW_PATH")
fp.target = road
fp.use_fixed_location = True
fp.use_curve_follow = True
mover.location = (0, 0, 0.36)
fp.offset_factor = 0.0
fp.keyframe_insert("offset_factor", frame=int(F * 0.1))
fp.offset_factor = 1.0
fp.keyframe_insert("offset_factor", frame=int(F * 0.92))


def PROGRESS(f):
    return fp.offset_factor


_seg = [(Vector(a), Vector(b)) for a, b in zip(pts, pts[1:])]
_len = [(b - a).length for a, b in _seg]
_tot = sum(_len)


def MOVER_AT(f):
    """Where the block is: the point at the animated progress along the road (by arc length), at the block's height.
    Follow-path positions are not reliably evaluated while stepping frames in a background script."""
    d = max(0.0, min(1.0, fp.offset_factor)) * _tot
    for (a, b), L in zip(_seg, _len):
        if d <= L or L == _len[-1]:
            return a.lerp(b, min(1.0, d / L if L else 0.0)) + Vector((0, 0, 0.36))
        d -= L
    return Vector(pts[-1]) + Vector((0, 0, 0.36))


POSITION = {"mover": MOVER_AT}


anchor("start", pts[3], of=road)                             # further along: the road's first points are out of frame
anchor("end", pts[-1], of=road)
anchor("mover", (0, 0, 0), parent=mover)
''',
 "stack3d": r'''
cards = A["params"].get("cards", ["a", "b", "c", "d", "e"])
for i, nm in enumerate(cards):
    z = 0.18 + i * 0.32
    o = box("card%d" % i, (3.2, 2.0, 0.22), (0, 0, z + 6), mat("card%d" % i, P["glow"] if i == len(cards) - 1 else P["base"], noise=0.06), bevel=0.06)
    if i == 0:                                       # the first card is already resting: frame 1 is never empty
        o.location = (0, 0, z)
    else:
        f0 = 1 + int(i * F * 0.12)
        key(o, "location", [(f0, (0, 0, z + 6)), (f0 + 14, (0, 0, z - 0.05)), (f0 + 18, (0, 0, z + 0.06)), (f0 + 21, (0, 0, z))])
    anchor(nm, (1.4, -0.85, 0), parent=o)
''',
 "network3d": r'''
nodes = A["params"].get("nodes", [{"name": "hub", "pos": [0, 0, 1]}, {"name": "a", "pos": [-2.5, 1, 0.6]},
                                  {"name": "b", "pos": [2.5, 1, 0.6]}, {"name": "c", "pos": [0, -2.2, 0.6]}])
links = A["params"].get("links", [["hub", "a"], ["hub", "b"], ["hub", "c"]])
pos = {}
for i, nd in enumerate(nodes):
    p = tuple(nd["pos"])
    pos[nd["name"]] = p
    nobj = sphere("node_" + nd["name"], 0.45 if i == 0 else 0.34, p, mat("node%d" % i, P["accent"] if i == 0 else P["base"], emit=0.8 if i == 0 else 0.0))
    anchor(nd["name"], (0, 0, 0), parent=nobj)
for j, (a, b) in enumerate(links):
    pa, pb = Vector(pos[a]), Vector(pos[b])
    mid = (pa + pb) / 2 + Vector((0, 0, 0.5))
    t = tube("link%d" % j, [tuple(pa), tuple(mid), tuple(pb)], 0.05, mat("link%d" % j, P["rim"], emit=0.5))
    for q in range(2):                                 # pulses travelling along the link
        s = sphere("pulse%d_%d" % (j, q), 0.11, tuple(pa), mat("pulse", P["glow"], emit=4.0), seg=12)
        c = s.constraints.new("FOLLOW_PATH")
        c.target = t
        c.use_fixed_location = True
        s.location = (0, 0, 0)
        for f in range(1 + q * 20, F + 1, 40):
            c.offset_factor = 0.0
            c.keyframe_insert("offset_factor", frame=f)
            c.offset_factor = 1.0
            c.keyframe_insert("offset_factor", frame=min(F, f + 36))
''',
 "device3d": r'''
kind = A["params"].get("device", "phone")
if kind == "phone":
    body = box("phone", (1.6, 0.16, 3.2), (0, 0, 1.6), mat("body", P["base"], rough=0.3), bevel=0.18)
    box("screen", (1.42, 0.02, 2.95), (0, -0.09, 1.6), mat("screen", P["accent"], emit=0.6), bevel=0.05)
    anchor("device", (0, 0, 0), parent=body)
elif kind == "laptop":
    box("base", (3.6, 2.4, 0.14), (0, 0, 0.07), mat("base", P["base"], rough=0.3), bevel=0.06)
    lid = bpy.data.objects.new("hinge", None)
    lid.location = (0, 1.2, 0.14)
    scn.collection.objects.link(lid)
    scr = box("lid", (3.6, 0.1, 2.3), (0, 0, 1.15), mat("lid", P["base"], rough=0.3), bevel=0.06)
    scr.parent = lid
    face = box("screen", (3.3, 0.02, 2.05), (0, -0.06, 1.15), mat("screen", P["accent"], emit=0.6), bevel=0.02)
    face.parent = lid
    key(lid, "rotation_euler", [(1, (math.radians(-95), 0, 0)), (int(F * 0.5), (math.radians(-8), 0, 0))])
    anchor("device", (0, 0, 0), parent=scr)
else:
    rack = box("rack", (1.6, 1.4, 3.6), (0, 0, 1.8), mat("rack", P["base"], rough=0.35), bevel=0.05)
    for u in range(8):
        box("unit%d" % u, (1.4, 0.04, 0.32), (0, -0.72, 0.4 + u * 0.4), mat("unit", P["rim"], rough=0.5), bevel=0.02)
        sphere("led%d" % u, 0.035, (0.55, -0.75, 0.4 + u * 0.4), mat("led", P["glow"], emit=5.0), seg=8)
    anchor("device", (0, 0, 0), parent=rack)
''',
 "globe3d": r'''
g = sphere("globe", 2.0, (0, 0, 1.2), mat("globe", P["base"]), seg=64)
tex = A["params"].get("texture")
if tex:                                               # the studio's local NASA image (no download)
    m = g.data.materials[0]
    nt = m.node_tree
    im = nt.nodes.new("ShaderNodeTexImage")
    im.image = bpy.data.images.load(tex)
    nt.links.new(im.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
key(g, "rotation_euler", [(1, (0, 0, 0)), (F, (0, 0, math.radians(A["params"].get("spin", 40))))])
anchor("globe", (0, 0, 0), parent=g)
''',
}


def palette_for(spec: dict, tpl=None) -> dict:
    """Hex colours for the scene: the spec's own, else the active template's."""
    if tpl is None:
        from . import design
        tpl = design.active()
    T = tpl.T
    base = {"bg": T["bg0"], "base": T.get("panel", T["bg1"]), "accent": tpl.conn.get("active", T["accent"]),
            "glow": T.get("amber", T["accent"]), "rim": T.get("text2", "#8899AA"), "text": T["text"]}
    base.update(spec.get("palette") or {})
    return base


def render_size(w: int, h: int) -> tuple[int, int]:
    """The 3D layer's size for an output of w x h: scaled down so the long side is at most MAX_3D_SIDE."""
    k = min(1.0, MAX_3D_SIDE / max(w, h))
    return int(round(w * k / 2) * 2), int(round(h * k / 2) * 2)


def frames_for(spec: dict, fps: int = 30) -> int:
    return int(spec.get("frames") or max(30, round(float(spec.get("seconds", 3.0)) * fps)))


def script_for(spec: dict) -> str:
    shot = spec.get("shot", "test")
    if shot not in BUILDERS:
        raise ValueError(f"Unknown 3D shot type: {shot}")
    return HEADER + BUILDERS[shot] + FOOTER


def render_args(spec: dict, w: int, h: int, out: Path, fps: int = 30) -> dict:
    cam = {"orbit": 20, "dolly": 0.8, "distance": 9.0, "elevation": 24}
    cam.update(CAMERA_DEFAULTS.get(spec.get("shot"), {}))
    cam.update(spec.get("camera") or {})
    return {"palette": palette_for(spec), "samples": SAMPLES, "w": int(w), "h": int(h), "fps": fps, "bloom": bool(spec.get("bloom")),
            "frames": frames_for(spec, fps), "transparent": bool(spec.get("transparent", True)), "camera": cam,
            "params": spec.get("params") or {}, "out": str(out).replace("\\", "/")}


def shot_hash(spec: dict, w: int, h: int, fps: int = 30) -> str:
    keep = {k: spec.get(k) for k in ("shot", "params", "camera", "frames", "seconds", "transparent")}
    keep["palette"] = palette_for(spec)
    code = hashlib.sha256((HEADER + BUILDERS.get(spec.get("shot", "test"), "") + FOOTER).encode()).hexdigest()[:8]
    blob = json.dumps([keep, w, h, fps, SCRIPT_VERSION, SAMPLES, code], sort_keys=True)   # a builder change re-renders only its shots
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def estimate_seconds(spec: dict, h: int = 1920, fps: int = 30) -> float:
    per = SEC_PER_FRAME[1080 if h >= 1500 else 540]
    return frames_for(spec, fps) * per + 8.0             # plus Blender's start-up


def timeout_for(spec: dict, h: int, fps: int = 30) -> int:
    return int(min(1800, max(90, estimate_seconds(spec, h, fps) * 4)))


def _frames_ok(d: Path, n: int) -> tuple[bool, str]:
    """Every frame exists and has visible (non-transparent) content."""
    from PIL import Image
    for i in range(1, n + 1):
        f = d / f"f_{i:04d}.png"
        if not f.exists():
            return False, f"frame {i} missing"
        with Image.open(f) as im:
            a = im.getchannel("A") if im.mode == "RGBA" else None
            if a is not None:
                cover = sum(a.point(lambda v: 255 if v > 8 else 0).histogram()[255:]) / (im.width * im.height)
                if cover < 0.01:
                    return False, f"frame {i} is transparent-only"
    return True, ""


def render_shot(spec: dict, base_dir: Path, w: int, h: int, fps: int = 30, log=print) -> Path | None:
    """Renders (or reuses) a shot. Returns its folder, or None when Blender is missing or the render failed."""
    path = info().get("path")
    if not path:
        log("3D: Blender not found; using the 2D fallback.")
        return None
    w, h = render_size(w, h)
    hsh = shot_hash(spec, w, h, fps)
    d = Path(base_dir) / hsh
    n = frames_for(spec, fps)
    if (d / "done.json").exists():
        return d                                         # cache hit
    d.mkdir(parents=True, exist_ok=True)
    (d / "scene.py").write_text(script_for(spec), encoding="utf-8")
    (d / "args.json").write_text(json.dumps(render_args(spec, w, h, d, fps)), encoding="utf-8")
    cmd = [path, "-b", "--factory-startup", "--threads", str(THREADS), "-P", str(d / "scene.py"), "--", str(d / "args.json")]
    t0 = time.time()
    limit = timeout_for(spec, h, fps)
    peak = 0
    with _lock, open(d / "blender.log", "w", encoding="utf-8", errors="replace") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
        rc = None
        while rc is None:                                 # poll: the timeout, and the peak memory for the report
            try:
                rc = proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                peak = max(peak, _rss(getattr(proc, "pid", None)))
                if peak > MAX_RSS_MB * 1e6:
                    proc.kill()
                    proc.wait(timeout=30)
                    log(f"3D: Blender used {peak / 1e9:.1f} GB (limit {MAX_RSS_MB / 1000:.1f} GB) on {spec.get('shot')}; "
                        f"aborted, using the 2D fallback.")
                    return None
                if time.time() - t0 > limit:
                    proc.kill()
                    proc.wait(timeout=30)
                    log(f"3D: Blender timed out after {limit} s on {spec.get('shot')}; using the 2D fallback.")
                    return None
    ok, why = _frames_ok(d, n) if rc == 0 else (False, f"Blender exited with code {rc}")
    if not ok or not (d / "anchors.json").exists():
        log(f"3D: {spec.get('shot')} failed ({why or 'no anchors'}); using the 2D fallback. Log: {d / 'blender.log'}")
        return None
    (d / "done.json").write_text(json.dumps({"seconds": round(time.time() - t0, 1), "frames": n, "w": w, "h": h,
                                             "peak_rss_mb": round(peak / 1e6)}), encoding="utf-8")
    return d


def _rss(pid) -> int:
    """Resident memory of the Blender process (bytes), 0 if unknown."""
    try:
        import psutil
        pr = psutil.Process(pid)
        return pr.memory_info().rss + sum(ch.memory_info().rss for ch in pr.children(recursive=True))
    except Exception:                                      # noqa: BLE001
        return 0


def cache_dir() -> Path:
    return config.DATA / "cache" / "blender"


def fallback_spec(spec: dict) -> dict:
    """The 2D version of a 3D shot: the spec's own "fallback", else stacking cards built from its labels."""
    if spec.get("fallback"):
        return dict(spec["fallback"], id=spec.get("id"), title=spec.get("title", ""), pad_start=spec.get("pad_start", 0.4),
                    pad_end=spec.get("pad_end", 0.5))
    items = [{"title": l["text"], "at": l.get("at")} for l in spec.get("labels", []) if l.get("text")][:4] or [{"title": spec.get("title", "")}]
    keep = {k: spec[k] for k in ("id", "title", "heading", "pad_start", "pad_end", "cues", "transition", "theme") if k in spec}
    return dict(keep, treatment="motion", effect="stacking_cards", items=items, _fallback_of=spec.get("shot"))


def test_render(log=print) -> tuple[bool, str]:
    """The doctor's check: a 1-frame 64x64 cube with EEVEE, headless."""
    import tempfile
    if not available():
        return False, "Blender not found"
    with tempfile.TemporaryDirectory() as tmp:
        d = render_shot({"shot": "test", "frames": 1, "palette": {"bg": "#101010", "base": "#334455", "accent": "#D97757",
                                                                   "glow": "#FFD37A", "rim": "#8899AA", "text": "#FFFFFF"}},
                        Path(tmp), 64, 64, 30, log)
        return (d is not None), ("1 frame rendered" if d else "test render failed; see the log above")
