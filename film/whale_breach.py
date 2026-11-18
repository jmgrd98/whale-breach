"""
whale_breach.py : a humpback whale breaches at sunrise.

Every part of the film is made by this file: the whale's body, the sea,
the spray, the sky, the camera move and the colour grade. No models,
no textures, no simulation caches. Blender (bpy) only draws what the
numbers below describe.

  Blender -b -P whale_breach.py -- --still 77 --scale 50 --samples 8
  Blender -b -P whale_breach.py -- --anim 0 107
"""
import bpy, bmesh, sys, os, math, time
import numpy as np
from mathutils import Matrix

# ---------------------------------------------------------------- the shot
FPS, DUR = 24, 9.0                 # nine seconds, 216 frames
G = 4.0                            # gravity in film time (a slow-motion shot)
T_EXIT, T_APEX, T_HIT = 1.0, 3.2, 4.52
Z_APEX, V_FWD = 4.3, 2.6           # height of the centre of mass, forward speed
HEADING = math.radians(-18)        # the whale travels to the right, a little toward us
L = 14.0                           # body length in metres
X0 = 0.40                          # the centre of mass sits 40 % back from the snout
SUN_AZ, SUN_EL = math.radians(88.5), math.radians(3.4)
SUN = np.array([math.cos(SUN_EL) * math.cos(SUN_AZ),
                math.cos(SUN_EL) * math.sin(SUN_AZ), math.sin(SUN_EL)])
SUN_COL = np.array([1.0, 0.60, 0.33])
SKY_COL = np.array([0.36, 0.44, 0.60])
WIND = np.array([0.9, 0.25, 0.0])
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- small maths
def smooth(a, b, x):
    x = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return x * x * (3 - 2 * x)


def spline(t, ts, vs):
    """Smooth curve through the keys (ts, vs). Works on numbers and arrays."""
    ts, vs = np.asarray(ts, float), np.asarray(vs, float)
    t = np.clip(np.asarray(t, float), ts[0], ts[-1])
    m = np.gradient(vs, ts)
    i = np.clip(np.searchsorted(ts, t) - 1, 0, len(ts) - 2)
    h = ts[i + 1] - ts[i]
    s = (t - ts[i]) / h
    return ((2 * s**3 - 3 * s**2 + 1) * vs[i] + (s**3 - 2 * s**2 + s) * h * m[i]
            + (-2 * s**3 + 3 * s**2) * vs[i + 1] + (s**3 - s**2) * h * m[i + 1])


def wobble(x, seed, freqs=(3, 7, 13, 29), amps=(0.30, 0.25, 0.20, 0.15)):
    """Cheap repeatable noise: a few sines with fixed random phases."""
    ph = np.random.default_rng(seed).uniform(0, 6.283, len(freqs))
    return sum(a * np.sin(f * x + p) for f, a, p in zip(freqs, amps, ph))


def rot_zyx(heading, pitch, roll):
    ch, sh, cp, sp = np.cos(heading), np.sin(heading), np.cos(pitch), np.sin(pitch)
    cr, sr = np.cos(roll), np.sin(roll)
    Rz = np.array([[ch, -sh, 0], [sh, ch, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, -sp], [0, 1, 0], [sp, 0, cp]])      # nose up for pitch > 0
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


# ---------------------------------------------------------------- the breach
def whale_state(t):
    """Where the whale is at time t. Ballistic in the air, damped in the water."""
    t = np.asarray(t, float)
    air = np.minimum(t, T_HIT) - T_APEX
    z = Z_APEX - 0.5 * G * air**2
    s = V_FWD * air
    wet = np.maximum(t - T_HIT, 0.0)
    damp = (1 - np.exp(-1.5 * wet)) / 1.5
    z = z - G * (T_HIT - T_APEX) * damp
    s = s + V_FWD * damp
    deg = math.pi / 180
    return dict(
        pos=np.stack([np.cos(HEADING) * s, np.sin(HEADING) * s, z], -1),
        pitch=spline(t, [0, 1.0, 2.0, 3.2, 3.9, 4.52, 5.2, 6.5], [78, 76, 70, 46, 23, 3, -12, -16]) * deg,
        roll=spline(t, [0.8, 1.6, 2.4, 3.2, 4.0, 4.52, 5.6], [25, 8, -22, -56, -112, -152, -172]) * deg,
        arch=spline(t, [1.0, 2.2, 3.2, 4.1, 4.6, 5.6], [0.05, 0.30, 0.42, 0.20, -0.12, 0.0]),
        twist=spline(t, [1.2, 2.4, 3.4, 4.5], [0.0, -0.30, -0.22, 0.0]),
        pec=spline(t, [1.0, 1.9, 2.9, 4.2, 5.2], [0.10, 0.45, 1.0, 1.0, 0.6]),
        pec2=spline(t, [1.0, 2.3, 3.4, 4.3, 5.2], [0.05, 0.22, 0.70, 0.72, 0.35]),
        side=spline(t, [1.0, 2.2, 3.2, 4.2, 4.9], [0.0, 0.22, 0.36, 0.14, 0.0]),
        fluke=spline(t, [1.0, 2.5, 3.4, 4.5], [0.0, 0.35, -0.25, 0.2]),
    )


def whale_frame(t):
    st = whale_state(t)
    return st, st['pos'], rot_zyx(HEADING, st['pitch'], st['roll'])


# ---------------------------------------------------------------- the whale's body
PU = [0.00, 0.05, 0.10, 0.17, 0.25, 0.33, 0.42, 0.52, 0.62, 0.72, 0.82, 0.90, 0.96, 1.00]
PW = [0.84, 1.10, 1.26, 1.42, 1.52, 1.55, 1.48, 1.30, 1.05, 0.74, 0.44, 0.26, 0.17, 0.12]
PD = [0.30, 0.50, 0.66, 0.86, 1.08, 1.26, 1.34, 1.30, 1.14, 0.90, 0.64, 0.44, 0.30, 0.16]
PV = [0.55, 0.95, 1.25, 1.52, 1.70, 1.76, 1.60, 1.34, 1.04, 0.78, 0.56, 0.42, 0.30, 0.16]


def profile(u):
    """Half width, back height and belly depth of the body at station u (0 snout, 1 tail)."""
    blunt = 0.03 + 0.97 * np.sqrt(np.clip(1 - (1 - np.clip(u / 0.035, 0, 1))**2, 0, 1))
    hump = 0.10 * np.exp(-((u - 0.665) / 0.045)**2)
    return spline(u, PU, PW) * blunt, (spline(u, PU, PD) + hump) * blunt, spline(u, PU, PV) * blunt


def mouth_line(u):
    return np.radians(spline(u, [0, 0.04, 0.10, 0.18, 0.24, 0.275], [78, 66, 60, 63, 80, 104]))


def body_surface(u, th):
    """Points on the skin, with the paint that goes with them."""
    w, hd, hv = profile(u)
    e = 0.78 + 0.22 * smooth(0.25, 0.6, u)                     # flat rostrum, round tail stock
    s, c = np.sin(th), np.cos(th)
    y = w * np.sign(s) * np.abs(s)**e
    z = np.where(c >= 0, hd, hv) * np.sign(c) * np.abs(c)**e
    fold = np.arccos(np.clip(c, -1, 1))                        # 0 on the back, pi on the belly
    tm = mouth_line(u)
    head = smooth(0.004, 0.03, u) * (1 - smooth(0.262, 0.285, u))
    upper = (1 - smooth(tm - 0.035, tm + 0.035, fold)) * head  # the rostrum sits inside the lower jaw
    lip = np.exp(-((fold - tm) / 0.035)**2) * head
    k = 1 - 0.09 * upper - 0.04 * lip
    y, z = y * k, z * k
    lo = (tm + 0.22) * (1 - smooth(0.2, 0.3, u)) + 1.75 * smooth(0.2, 0.3, u)
    pleat = smooth(lo, lo + 0.2, fold) * smooth(0.0, 0.04, u) * (1 - smooth(0.44, 0.52, u))
    edge = np.radians(spline(u, [0, 0.3, 0.6, 0.9, 1.0], [100, 118, 125, 150, 160]))
    patch = wobble(u * 9, 3) * (0.6 + wobble(th, 5, (1, 2, 3, 5)))
    white = smooth(edge - 0.30, edge + 0.30, fold + 0.28 * patch)
    co = np.stack([(X0 - u) * L, y, z], -1)
    wa = np.stack([white, pleat, lip, np.ones_like(u)], -1)
    wb = np.stack([c, s, u, np.zeros_like(u)], -1)
    return co, wa, wb


def loft(rings):
    """Quads between a row of closed rings, shape (rows, ring, 3)."""
    nr, nv = rings.shape[:2]
    i, j = np.meshgrid(np.arange(nr - 1), np.arange(nv), indexing='ij')
    j2 = (j + 1) % nv
    return np.stack([i * nv + j, i * nv + j2, (i + 1) * nv + j2, (i + 1) * nv + j], -1).reshape(-1, 4)


def ball(n_lat=5, n_lon=8):
    la = np.linspace(0.12, math.pi - 0.12, n_lat)[:, None]
    lo = np.linspace(0, 2 * math.pi, n_lon, endpoint=False)[None, :]
    return np.stack([np.sin(la) * np.cos(lo), np.sin(la) * np.sin(lo), np.cos(la) * np.ones_like(lo)], -1)


class Parts:
    """Collects the pieces of the whale into one mesh."""
    def __init__(self):
        self.co, self.fa, self.wa, self.wb, self.part, self.xa = [], [], [], [], [], []
        self.n = 0

    def add(self, co, faces, wa, wb, part, xa=None):
        co = co.reshape(-1, 3)
        self.co.append(co)
        self.fa.append(faces + self.n)
        self.wa.append(wa.reshape(-1, 4))
        self.wb.append(wb.reshape(-1, 4))
        self.part.append(np.full(len(co), part))
        self.xa.append(co[:, 0].copy() if xa is None else np.full(len(co), xa))
        self.n += len(co)


PEC_ROOT_U, PEC_LEN = 0.285, 4.6
FLUKE_X = (X0 - 0.975) * L


def build_whale_data():
    P = Parts()
    # body: 230 rings from snout to tail stock
    s = np.linspace(0, 1, 230)
    u = np.append(0.6 * s + 0.4 * (0.5 - 0.5 * np.cos(math.pi * s)), 1.0)[:, None]
    th = np.linspace(0, 2 * math.pi, 144, endpoint=False)[None, :]
    co, wa, wb = body_surface(u * np.ones_like(th), th * np.ones_like(u))
    co[-1, :, 1:] *= 0.05                                      # close the tail stock
    P.add(co, loft(co), wa, wb, 0)

    # tubercles: the knobs on the rostrum and the lower jaw, and two eyes
    spots = [(uu, 0.0) for uu in np.arange(0.025, 0.21, 0.028)]
    spots += [(uu, sg * 0.50) for uu in np.arange(0.035, 0.20, 0.03) for sg in (-1, 1)]
    spots += [(uu, sg * (float(mouth_line(uu)) + 0.20)) for uu in np.arange(0.02, 0.23, 0.026) for sg in (-1, 1)]
    spots += [(uu, sg * (math.pi - 0.5 * k)) for uu in (0.012, 0.03) for sg in (-1, 1) for k in (0, 1, 2)]
    unit = ball()
    for uu, tt in spots + [(0.262, 1.52), (0.262, -1.52)]:
        eye = abs(abs(tt) - 1.52) < 1e-6 and uu > 0.26
        c0, wa0, wb0 = body_surface(np.array([uu]), np.array([tt]))
        nrm = c0[0] * [0, 1, 1]
        nrm /= np.linalg.norm(nrm) + 1e-9
        t1 = np.array([1.0, 0, 0])
        t2 = np.cross(nrm, t1)
        r = 0.075 if eye else rng.uniform(0.07, 0.115)
        v = c0[0] + r * (unit[..., 0:1] * t1 + unit[..., 1:2] * t2 + 0.55 * unit[..., 2:3] * nrm)
        wa1 = np.tile(wa0[0] * [1, 0, 0, 1] + [0.25, 0, 0, 0], (unit.shape[0], unit.shape[1], 1))
        wb1 = np.tile(wb0[0] + [0, 0, 0, 1.0 if eye else 0.0], (unit.shape[0], unit.shape[1], 1))
        P.add(v, loft(v), wa1, wb1, 0)

    # dorsal fin: small and hooked, on its hump two thirds of the way back
    b = np.linspace(0, 1, 26)[:, None]
    k = np.concatenate([np.linspace(0, 1, 9), np.linspace(1, 0, 9)[1:-1]])[None, :]
    side = np.concatenate([np.ones(9), -np.ones(7)])[None, :]
    h = 0.46 * np.sin(math.pi * b**1.6)**0.9
    x = (X0 - 0.675) * L + 0.7 - 1.4 * b - 0.32 * k**2 * (h / 0.46)
    zb = profile(X0 - x / L)[1] - 0.06
    co = np.stack([x, side * (0.09 * (1 - k)**0.8 * np.sin(math.pi * b)**0.5 + 0.008), zb + h * k], -1)
    P.add(co, loft(co), np.tile([0.0, 0, 0, 1], co.shape[:2] + (1,)), np.tile([1.0, 0, 0.67, 0], co.shape[:2] + (1,)), 0)

    # flukes: swept blades with a notch, about a third of the body length across
    sp = np.linspace(-1, 1, 91)[:, None]
    a = np.abs(sp)
    ang = np.linspace(0, 2 * math.pi, 22, endpoint=False)[None, :]
    q, sn = np.cos(ang), np.sin(ang)
    le = 0.45 - 1.25 * a**1.2
    chord = 1.25 * (1 - a)**0.8 * (1 - 0.25 * np.exp(-(a / 0.08)**2)) + 0.03
    te = le - chord + 0.025 * np.sin(sp * 55) * (1 - a)       # a ragged trailing edge
    thick = 0.30 * (1 - a)**0.9 + 0.015
    co = np.stack([FLUKE_X + te + chord * (0.5 + 0.5 * q), sp * 2.35 * np.ones_like(q),
                   0.5 * thick * sn * (0.6 + 0.4 * q)], -1)
    under = (sn < 0) * smooth(0.02, 0.25, 0.5 + 0.5 * q) * (1 - smooth(0.75, 0.95, a))
    wa = np.stack([under, 0 * under, 0 * under, np.ones_like(under)], -1)
    wb = np.stack([sn + 0 * under, q + 0 * under, 1.0 + 0 * under, 0 * under], -1)
    P.add(co, loft(co), wa, wb, 3, xa=FLUKE_X)

    # pectoral fins: a third of the body long, with a knobbed leading edge
    s = np.linspace(0, 1, 70)[:, None]
    chord = spline(s, [0, .08, .3, .6, .85, .96, 1.0], [0.62, 0.90, 1.05, 0.92, 0.66, 0.36, 0.05])
    knob = 0.075 * np.maximum(0, np.sin(2 * math.pi * 6.5 * s))**2 * (1 - 0.3 * s)
    thick = 0.26 * (1 - 0.8 * s) + 0.02
    fin = np.stack([-0.5 * s**2 + 0.5 * chord * q + knob * smooth(0.2, 1, q),
                    s * PEC_LEN * np.ones_like(q), 0.5 * thick * sn * (0.6 + 0.4 * q)], -1)
    top = 0.35 + 0.65 * smooth(0.1, 0.55, s + 0.15 * wobble(s * 9 + ang, 11))
    white = np.where(sn < 0, 1.0, top)
    wa = np.stack([white, 0 * white, 0 * white, np.ones_like(white)], -1)
    wb = np.stack([sn + 0 * white, q + 0 * white, 0.3 + 0 * white, 0 * white], -1)
    for part in (1, 2):
        P.add(fin, loft(fin), wa, wb, part, xa=(X0 - PEC_ROOT_U) * L)

    D = dict(co=np.concatenate(P.co), faces=np.concatenate(P.fa), wa=np.concatenate(P.wa),
             wb=np.concatenate(P.wb), part=np.concatenate(P.part), xa=np.concatenate(P.xa))
    root, _, _ = body_surface(np.array([PEC_ROOT_U]), np.array([math.radians(110)]))
    D['pec_root'] = root[0] * [1, 0.86, 0.86]
    return D


def pose_whale(D, st):
    """Bend the rest shape into the pose st: fins, flukes, arch and twist."""
    co, part = D['co'].copy(), D['part']
    # pectoral fins swing from swept back (0) to spread wide (1)
    for pid, sg, sp in ((1, 1.0, st['pec']), (2, -1.0, st['pec2'])):
        m = part == pid
        d = (1 - sp) * np.array([-0.80, 0.42, -0.42]) + sp * np.array([-0.10, 0.93, 0.36])
        d = d * [1, sg, 1] / np.linalg.norm(d)
        c = np.array([1.0, 0, 0.15]) - np.dot([1.0, 0, 0.15], d) * d
        c /= np.linalg.norm(c)
        n = np.cross(c, d) * sg
        f = D['co'][m]
        co[m] = D['pec_root'] * [1, sg, 1] + f[:, 0:1] * c + f[:, 1:2] * d + f[:, 2:3] * n * sg
    # flukes pitch about the end of the tail stock
    m = part == 3
    ca, sa = math.cos(st['fluke']), math.sin(st['fluke'])
    dx, dz = co[m, 0] - FLUKE_X, co[m, 2]
    co[m, 0], co[m, 2] = FLUKE_X + ca * dx - sa * dz, sa * dx + ca * dz
    xa = D['xa']
    tw = st['twist'] * xa / 6.0                                 # the head leads the roll
    y = co[:, 1] * np.cos(tw) - co[:, 2] * np.sin(tw)
    co[:, 2] = co[:, 1] * np.sin(tw) + co[:, 2] * np.cos(tw)
    co[:, 1] = y
    return spine_bend(spine_bend(co, xa, st['arch'], 2), xa, st['side'], 1)


def spine_bend(co, xa, amount, axis):
    """Curve the body along its length. The curvature gathers in the tail stock and the neck."""
    xs = np.linspace(-9.6, 6.0, 240)
    step = xs[1] - xs[0]
    kap = amount * (0.035 + 0.11 * smooth(-1.0, -7.5, xs) + 0.03 * smooth(1.0, 4.5, xs))
    phi = np.cumsum(kap) * step
    phi -= np.interp(0.0, xs, phi)
    cx, cz = np.cumsum(np.cos(phi)) * step, np.cumsum(np.sin(phi)) * step
    cx, cz = cx - np.interp(0.0, xs, cx), cz - np.interp(0.0, xs, cz)
    ph = np.interp(xa, xs, phi)
    dx, z = co[:, 0] - xa, co[:, axis]
    out = co.copy()
    out[:, 0] = np.interp(xa, xs, cx) + dx * np.cos(ph) - z * np.sin(ph)
    out[:, axis] = np.interp(xa, xs, cz) + dx * np.sin(ph) + z * np.cos(ph)
    return out


def mesh_from(name, co, faces):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.loops.add(faces.size)
    me.polygons.add(len(faces))
    me.vertices.foreach_set('co', co.ravel())
    me.loops.foreach_set('vertex_index', faces.ravel())
    me.polygons.foreach_set('loop_start', np.arange(0, faces.size, 4))
    try:
        me.polygons.foreach_set('loop_total', np.full(len(faces), 4))
    except Exception:
        pass
    me.update(calc_edges=True)
    me.validate()
    return me


def set_attr(me, name, kind, values, domain='POINT'):
    a = me.attributes.get(name) or me.attributes.new(name, kind, domain)
    a.data.foreach_set({'FLOAT_COLOR': 'color', 'FLOAT_VECTOR': 'vector', 'FLOAT': 'value'}[kind], values.ravel())


def build_whale(D):
    me = mesh_from('Whale', pose_whale(D, whale_state(3.0)), D['faces'])
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    set_attr(me, 'wa', 'FLOAT_COLOR', D['wa'])
    set_attr(me, 'wb', 'FLOAT_COLOR', D['wb'])
    set_attr(me, 'rest', 'FLOAT_VECTOR', D['co'] + (D['part'][:, None] * [0, 20.0, 0]))
    ob = bpy.data.objects.new('Whale', me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------- node helper
class Nodes:
    """Tiny wrapper so shader graphs read like formulas."""
    def __init__(self, tree):
        self.t = tree
        tree.nodes.clear()

    def new(self, kind, out=0, i=None, **props):
        n = self.t.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (i or {}).items():
            if isinstance(v, bpy.types.NodeSocket):
                self.t.links.new(v, n.inputs[k])
            else:
                n.inputs[k].default_value = v
        return n.outputs[out] if out is not None else n

    def m(self, op, a, b=None, c=None):
        i = {0: a}
        if b is not None: i[1] = b
        if c is not None: i[2] = c
        return self.new('ShaderNodeMath', operation=op, i=i)

    def v(self, op, a, b=None, out=0):
        i = {0: a}
        if b is not None: i[1] = b
        return self.new('ShaderNodeVectorMath', out=out, operation=op, i=i)

    def mix(self, f, a, b, blend='MIX'):
        return self.new('ShaderNodeMix', out=2, data_type='RGBA', blend_type=blend, i={0: f, 6: a, 7: b})

    def ramp(self, x, lo, hi, a=0.0, b=1.0):
        return self.new('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', i={0: x, 1: lo, 2: hi, 3: a, 4: b})

    def noise(self, vec, scale, detail=4.0, rough=0.55, w=None, dist=0.0):
        i = {'Vector': vec, 'Scale': scale, 'Detail': detail, 'Roughness': rough, 'Distortion': dist}
        if w is not None:
            i['W'] = w
        return self.new('ShaderNodeTexNoise', noise_dimensions='4D' if w is not None else '3D', i=i)


def rgb(r, g, b):
    return (r, g, b, 1.0)


def new_material(name):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    return mat, Nodes(mat.node_tree)


# ---------------------------------------------------------------- skin
def whale_material():
    mat, N = new_material('Skin')
    wa = N.new('ShaderNodeAttribute', out=None, attribute_name='wa')
    wb = N.new('ShaderNodeAttribute', out=None, attribute_name='wb')
    rest = N.new('ShaderNodeAttribute', out=1, attribute_name='rest')
    a = N.new('ShaderNodeSeparateColor', out=None, i={0: wa.outputs[0]})
    b = N.new('ShaderNodeSeparateColor', out=None, i={0: wb.outputs[0]})
    white, pleat, lip = a.outputs[0], a.outputs[1], a.outputs[2]
    eye = wb.outputs[3]
    big = N.noise(rest, 0.55, 5.0, 0.6)
    fine = N.noise(rest, 6.0, 6.0, 0.65)
    # throat pleats: narrow grooves that run from the chin to the navel
    theta = N.m('ARCTAN2', b.outputs[1], b.outputs[0])
    wave = N.m('SINE', N.m('ADD', N.m('MULTIPLY', theta, 40.0), N.m('MULTIPLY', big, 2.2)))     # no two grooves alike
    groove = N.m('MULTIPLY', N.m('MULTIPLY', N.ramp(wave, 0.45, 1.0), pleat), N.ramp(fine, 0.25, 0.6, 0.55, 1.0))
    # black back, white belly, a torn edge between them
    tear = N.m('ADD', N.m('MULTIPLY', N.m('SUBTRACT', big, 0.5), 0.6), N.m('MULTIPLY', N.m('SUBTRACT', fine, 0.5), 0.3))
    belly = N.ramp(N.m('ADD', white, tear), 0.43, 0.57)
    col = N.mix(belly, rgb(0.016, 0.019, 0.024), rgb(0.80, 0.79, 0.75))
    col = N.mix(N.m('MULTIPLY', N.ramp(fine, 0.60, 0.72), 0.35), col, rgb(0.42, 0.42, 0.40))   # scars and barnacles
    col = N.mix(N.m('MULTIPLY', groove, 0.6), col, rgb(0.10, 0.07, 0.07))
    col = N.mix(N.m('MAXIMUM', lip, eye), col, rgb(0.004, 0.004, 0.005))
    height = N.m('ADD', N.m('MULTIPLY', groove, -1.0), N.m('MULTIPLY', fine, 0.12))
    bump = N.new('ShaderNodeBump', i={'Strength': 0.4, 'Distance': 0.05, 'Height': height})
    rough = N.m('ADD', 0.16, N.m('MULTIPLY', big, 0.22))
    bsdf = N.new('ShaderNodeBsdfPrincipled', i={'Base Color': col, 'Roughness': rough, 'Normal': bump,
                                                'Coat Weight': 0.5, 'Coat Roughness': 0.06, 'IOR': 1.45})
    N.new('ShaderNodeOutputMaterial', out=None, i={0: bsdf})
    return mat


# ---------------------------------------------------------------- the sea
def build_sea():
    """One sheet of water: fine near the action, coarser toward the horizon."""
    def axis(lo, hi, step, far):
        mid = np.arange(lo, hi + 1e-6, step)
        out, x, d = [], 0.0, step
        while x < far:
            d *= 1.07
            x += d
            out.append(x)
        out = np.array(out)
        return np.concatenate([lo - out[::-1], mid, hi + out])
    xs, ys = axis(-34, 40, 0.28, 9000), axis(-36, 26, 0.28, 9000)
    X, Y = np.meshgrid(xs, ys)
    co = np.stack([X, Y, np.zeros_like(X)], -1)
    nx, ny = len(xs), len(ys)
    i, j = np.meshgrid(np.arange(ny - 1), np.arange(nx - 1), indexing='ij')
    faces = np.stack([i * nx + j, i * nx + j + 1, (i + 1) * nx + j + 1, (i + 1) * nx + j], -1).reshape(-1, 4)
    me = mesh_from('Sea', co.reshape(-1, 3), faces)
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    ob = bpy.data.objects.new('Sea', me)
    bpy.context.scene.collection.objects.link(ob)
    mods = []
    for name, size, res, wind, scale, small, seed, foam in (('Chop', 53.0, 16, 6.5, 0.9, 0.02, 3, True),
                                                           ('Swell', 211.0, 13, 11.0, 1.05, 1.5, 9, False)):
        m = ob.modifiers.new(name, 'OCEAN')
        m.geometry_mode = 'DISPLACE'
        m.spatial_size, m.resolution, m.size = int(size), res, 1.0
        m.wind_velocity, m.wave_scale, m.wave_scale_min = wind, scale, small
        m.choppiness, m.wave_alignment, m.wave_direction = 1.1, 0.35, math.radians(60)
        m.depth, m.random_seed = 200.0, seed
        if foam:
            m.use_foam, m.foam_coverage, m.foam_layer_name = True, 0.08, 'foam'
        mods.append(m)
    return ob, mods


def sea_material(exit_xy, slam_xy):
    mat, N = new_material('Water')
    V = {k: N.new('ShaderNodeValue', out=None) for k in ('time', 'exit_r', 'exit_i', 'slam_r', 'slam_i')}
    P = N.new('ShaderNodeNewGeometry', out=0)
    dist = N.new('ShaderNodeCameraData', out=2)
    t = V['time'].outputs[0]
    # small ripples that the mesh cannot hold, fading with distance
    r1 = N.noise(N.v('MULTIPLY', P, (1.0, 0.45, 1.0)), 1.7, 5.0, 0.62, w=t)
    r2 = N.noise(P, 9.0, 3.0, 0.6, w=N.m('MULTIPLY', t, 1.7))
    near = N.m('POWER', 2.718, N.m('MULTIPLY', dist, -1 / 350.0))
    bump = N.new('ShaderNodeBump', i={'Strength': N.m('MULTIPLY', near, 0.55), 'Distance': 0.12,
                                      'Height': N.m('ADD', r1, N.m('MULTIPLY', r2, 0.25))})

    def patch(centre, angle, ax, ay, radius):
        q = N.v('SUBTRACT', P, (centre[0], centre[1], 0.0))
        q = N.new('ShaderNodeVectorRotate', rotation_type='Z_AXIS', i={'Vector': q, 'Angle': -angle})
        d = N.v('LENGTH', N.v('MULTIPLY', q, (1 / ax, 1 / ay, 0.0)), out=1)
        return N.m('DIVIDE', d, radius)

    lace = N.noise(P, 0.3, 6.0, 0.7, w=N.m('MULTIPLY', t, 0.3), dist=0.8)
    cells = N.noise(P, 1.3, 5.0, 0.7, w=N.m('MULTIPLY', t, 0.5))
    foam = 0.0
    for key, centre, ang, ax, ay in (('exit', exit_xy, 0.0, 1.0, 1.0), ('slam', slam_xy, HEADING, 7.5, 3.4)):
        d = patch(centre, ang, ax, ay, V[key + '_r'].outputs[0])
        d = N.m('ADD', d, N.m('MULTIPLY', N.m('SUBTRACT', lace, 0.5), 0.9))
        m = N.m('MULTIPLY', N.ramp(d, 1.0, 0.35), V[key + '_i'].outputs[0])
        foam = N.m('MAXIMUM', foam, m)
    caps = N.new('ShaderNodeSeparateColor', i={0: N.new('ShaderNodeAttribute', attribute_name='foam')})
    white = N.ramp(N.m('SUBTRACT', N.m('ADD', foam, 0.25), N.m('MULTIPLY', cells, 1.1)), 0.30, 0.75)
    white = N.m('MAXIMUM', white, N.ramp(N.m('SUBTRACT', caps, N.m('MULTIPLY', cells, 0.5)), 0.05, 0.4))
    # deep water, greener on the crests, milky green where the splash has filled it with air
    z = N.new('ShaderNodeSeparateXYZ', out=2, i={0: P})
    col = N.mix(N.ramp(z, -0.3, 0.7), rgb(0.004, 0.022, 0.034), rgb(0.012, 0.075, 0.085))
    col = N.mix(N.ramp(foam, 0.0, 0.6), col, rgb(0.05, 0.30, 0.30))
    col = N.mix(white, col, rgb(0.86, 0.88, 0.90))
    rough = N.m('ADD', 0.045, N.m('MULTIPLY', white, 0.55))
    bsdf = N.new('ShaderNodeBsdfPrincipled', i={'Base Color': col, 'Roughness': rough, 'IOR': 1.333, 'Normal': bump,
                                                'Emission Color': rgb(0.9, 0.85, 0.82), 'Emission Strength': N.m('MULTIPLY', white, 0.15)})
    N.new('ShaderNodeOutputMaterial', out=None, i={0: bsdf})
    return mat, V


# ---------------------------------------------------------------- sky and sun
def build_sky():
    world = bpy.data.worlds.new('Sunrise')
    try:
        world.use_nodes = True
    except Exception:
        pass
    N = Nodes(world.node_tree)
    D = N.v('NORMALIZE', N.new('ShaderNodeTexCoord', out=0))
    xyz = N.new('ShaderNodeSeparateXYZ', out=None, i={0: D})
    e = xyz.outputs[2]
    up = N.m('MAXIMUM', e, 0.0)
    c = N.m('MAXIMUM', N.v('DOT_PRODUCT', D, tuple(SUN), out=1), 0.0)
    grad = N.new('ShaderNodeValToRGB', out=None, i={0: N.m('POWER', up, 0.5)})
    stops = [(0.0, (0.90, 0.36, 0.10)), (0.16, (0.80, 0.38, 0.20)), (0.33, (0.42, 0.28, 0.34)),
             (0.55, (0.12, 0.18, 0.36)), (0.80, (0.04, 0.09, 0.26)), (1.0, (0.02, 0.05, 0.18))]
    el = grad.color_ramp.elements
    for k, (p, col) in enumerate(stops):
        s = el[k] if k < 2 else el.new(p)
        s.position, s.color = p, rgb(*col)
    sky = grad.outputs[0]
    # the side of the sky away from the sun is cooler and dimmer
    side = N.ramp(N.v('DOT_PRODUCT', D, tuple(SUN), out=1), -0.3, 0.9)
    sky = N.mix(side, N.mix(1.0, sky, rgb(0.42, 0.48, 0.62), 'MULTIPLY'), sky)
    glow = N.m('ADD', N.m('MULTIPLY', N.m('POWER', c, 6.0), 0.45),
               N.m('ADD', N.m('MULTIPLY', N.m('POWER', c, 60.0), 2.0), N.m('MULTIPLY', N.m('POWER', c, 900.0), 9.0)))
    sky = N.mix(1.0, sky, N.mix(glow, rgb(0, 0, 0), rgb(1.0, 0.52, 0.18)), 'ADD')
    # long streaks of cloud, lit from underneath
    inv = N.m('DIVIDE', 1.0, N.m('ADD', up, 0.07))
    uv = N.new('ShaderNodeCombineXYZ', i={0: N.m('MULTIPLY', xyz.outputs[0], inv), 1: N.m('MULTIPLY', xyz.outputs[1], inv)})
    uv = N.new('ShaderNodeMapping', i={'Vector': uv, 'Rotation': (0, 0, 0.5), 'Scale': (1.0, 0.28, 1.0)})
    n = N.m('ADD', N.m('MULTIPLY', N.noise(uv, 0.42, 8.0, 0.62, dist=0.7), 0.78),
            N.m('MULTIPLY', N.noise(uv, 2.4, 5.0, 0.6), 0.22))
    mask = N.m('MULTIPLY', N.ramp(n, 0.45, 0.62), N.m('MULTIPLY', N.ramp(e, 0.012, 0.09), 0.92))
    lit = N.m('MINIMUM', 1.0, N.m('ADD', N.m('MULTIPLY', N.m('POWER', c, 3.0), 1.3),
                                  N.m('MULTIPLY', N.ramp(n, 0.82, 0.55), 0.45)))
    cloud = N.mix(lit, rgb(0.10, 0.09, 0.16), rgb(1.6, 0.55, 0.20))
    sky = N.mix(mask, sky, cloud)
    disc = N.m('MULTIPLY', N.ramp(c, math.cos(math.radians(0.74)), math.cos(math.radians(0.36))),
               N.m('SUBTRACT', 1.0, N.m('MULTIPLY', mask, 0.8)))
    sky = N.mix(1.0, sky, N.mix(disc, rgb(0, 0, 0), rgb(16.0, 11.0, 6.0)), 'ADD')
    sky = N.mix(N.ramp(e, -0.04, 0.0), rgb(0.015, 0.035, 0.055), sky)      # below the horizon: the sea
    bg = N.new('ShaderNodeBackground', i={0: sky, 1: 1.0})
    N.new('ShaderNodeOutputWorld', out=None, i={0: bg})
    bpy.context.scene.world = world

    def lamp(name, direction, energy, colour, angle, shadow=True, spec=1.0):
        li = bpy.data.lights.new(name, 'SUN')
        li.energy, li.color, li.angle, li.use_shadow, li.specular_factor = energy, colour, angle, shadow, spec
        ob = bpy.data.objects.new(name, li)
        d = np.asarray(direction, float) / np.linalg.norm(direction)
        x = np.cross([0, 0, 1.0], d)
        x /= np.linalg.norm(x)
        ob.matrix_world = Matrix(np.column_stack([np.append(x, 0), np.append(np.cross(d, x), 0),
                                                  np.append(d, 0), [0, 0, 0, 1]]).tolist())
        bpy.context.scene.collection.objects.link(ob)
    lamp('Sun', SUN, 4.2, (1.0, 0.58, 0.32), math.radians(1.6))
    lamp('SkyFill', (-0.55, -0.75, 0.55), 1.0, (0.55, 0.66, 1.0), math.radians(60), shadow=False, spec=0.25)


# ---------------------------------------------------------------- spray
def make_spray():
    """Every drop is launched once and then follows a closed formula, so any frame can be drawn alone."""
    _, hit, _ = whale_frame(T_HIT)
    hit = hit * [1, 1, 0]
    ah = np.array([math.cos(HEADING), math.sin(HEADING), 0.0])
    nh = np.array([-ah[1], ah[0], 0.0])
    up = np.array([0, 0, 1.0])
    sets = []

    def emit(p0, v0, t0, k, r, a, life, grow=0.0, delay=0.0):
        n = len(p0)
        f = lambda x: np.broadcast_to(np.asarray(x, float), (n,)).copy()
        sets.append(dict(p0=p0, v0=v0, t0=f(t0), k=f(k), r=f(r), a=f(a), life=f(life), grow=f(grow), delay=f(delay)))

    def U(n, a=0.0, b=1.0):
        return rng.uniform(a, b, n)

    # 1. the crown: water dragged up around the body as it leaves the sea
    for n, mist in ((90000, False), (8000, True)):
        t0 = T_EXIT - 0.05 + 1.95 * U(n)**1.5
        st = whale_state(t0)
        axis = np.stack([np.cos(st['pitch']) * ah[0], np.cos(st['pitch']) * ah[1], np.sin(st['pitch'])], -1)
        sw = -st['pos'][:, 2] / np.maximum(np.sin(st['pitch']), 0.3)
        centre = st['pos'] + sw[:, None] * axis
        w = profile(np.clip(X0 - sw / L, 0.0, 1.0))[0]
        ph = U(n, 0, 6.283)
        rad = np.stack([np.cos(ph), np.sin(ph), 0 * ph], -1)
        rise = np.maximum(G * (T_APEX - t0), 0.0)
        fing = np.clip(0.6 + wobble(ph, 21), 0.15, 1.4)
        p0 = centre + rad * (w * 1.05 + 0.25 * U(n))[:, None] + up * 0.1
        v0 = (rad * ((1.0 + 2.6 * U(n)) * fing)[:, None] + ah * V_FWD
              + up * (rise * (0.2 + 0.62 * U(n)**0.8) * fing)[:, None])
        if mist:
            emit(p0, v0 * 0.7, t0, 2.5 + 3 * U(n), 0.3 + 0.4 * U(n), 0.035, 3.5 + 2 * U(n), 1.0)
        else:
            emit(p0, v0, t0, 0.2 + 0.5 * U(n), 0.006 + 0.022 * U(n)**2, 0.6, 2.8)

    # 2. veils of water that pour off the fins, the flukes and the chin while the whale is in the air
    n = 130000
    body = pose_whale(WD, dict(whale_state(3.0), arch=0.0, twist=0.0, side=0.0))
    wet = np.nonzero((WD['part'] > 0) | (WD['wb'][:, 2] < 0.2))[0]
    pick = body[rng.choice(wet, n)]
    t0 = np.round((T_EXIT + 0.15 + (T_HIT - T_EXIT - 0.1) * U(n)**1.3) * 40) / 40
    p0, v0 = np.zeros((n, 3)), np.zeros((n, 3))
    for tq in np.unique(t0):
        m = t0 == tq
        (_, pa, Ra), (_, pb, Rb) = whale_frame(tq), whale_frame(tq + 0.03)
        p0[m] = pa + pick[m] @ Ra.T
        v0[m] = ((pb + pick[m] @ Rb.T) - p0[m]) / 0.03
    emit(p0, v0 * 0.75 + rng.normal(0, 0.14, (n, 3)), t0 + U(n, 0, 0.025), 0.3 + 0.7 * U(n),
         0.004 + 0.007 * U(n)**2, 0.30, np.where(p0[:, 2] > 0.4, 2.4, 0.0), delay=0.10)

    # 3. the wall: the body slams down, tail first, and throws two sheets of water sideways
    def slam(n, xr, side, beta, speed, jitter):
        w = profile(np.clip(X0 - xr / L, 0, 1))[0]
        ends = smooth(3.5, 5.7, xr) - smooth(-6.0, -8.4, xr)
        direction = (nh * (side * np.cos(beta))[:, None] + up * np.sin(beta)[:, None]
                     + ah * (jitter * rng.normal(0, 1, n) + 0.8 * ends)[:, None])
        p0 = hit + ah * xr[:, None] + nh * (side * (0.6 * w + 0.3 * U(n)))[:, None] + up * 0.05
        t0 = T_HIT - 0.42 + 0.30 * (xr + 8.4) / 14.1 + 0.08 * U(n)**2
        return p0, direction * (speed * (0.5 + 0.5 * w / 1.55))[:, None] + ah * V_FWD * 0.5, t0

    for n, mist in ((400000, False), (20000, True)):
        xr, side = U(n, -8.4, 5.7), np.where(U(n) < 0.5, -1.0, 1.0)
        fing = np.clip(0.62 + wobble(xr * 0.9 + side * 17, 31), 0.12, 1.4)
        low = U(n) < 0.22
        beta = np.radians(np.where(low, U(n, 12, 36), 38 + 44 * U(n)**0.7))
        p0, v0, t0 = slam(n, xr, side, beta, np.where(low, 0.75, 1.0) * 16.0 * fing * U(n)**0.4, 0.28)
        if mist:
            emit(p0 + v0 * 0.10, v0 * 0.9, t0 + 0.05 + 0.4 * U(n), 0.8 + 1.5 * U(n), 0.3 + 0.4 * U(n), 0.02,
                 4 + 2.5 * U(n), 0.6)
        else:
            emit(p0, v0, t0, np.where(U(n) < 0.12, 0.15, 0.7 + 2.2 * U(n)), 0.007 + 0.03 * U(n)**3, 0.6, 2.8 + 2.0 * U(n))   # fine drops hang, heavy ones fly
    jets, per = 60, 700                                         # fingers that outrun the sheet
    n = jets * per
    one = lambda lo, hi: np.repeat(rng.uniform(lo, hi, jets), per)
    p0, v0, t0 = slam(n, one(-8.0, 5.5), np.repeat(np.where(rng.uniform(0, 1, jets) < 0.5, -1.0, 1.0), per),
                      np.radians(one(48, 80)), one(13.0, 19.0) * U(n)**0.4, 0.04)
    emit(p0, v0 + rng.normal(0, 0.25, (n, 3)), t0, 0.1 + 0.3 * U(n)**2, 0.010 + 0.04 * U(n)**3, 0.6, 4.4)

    # 4. the rebound: the hollow behind the body closes and shoots a column up
    n = 40000
    p0 = hit + ah * (-1.4 + 1.3 * rng.normal(0, 1, n))[:, None] + nh * (0.6 * rng.normal(0, 1, n))[:, None]
    v0 = up * (6.0 + 7.0 * U(n)**0.5)[:, None] + rng.normal(0, 1.0, (n, 3)) * [1, 1, 0.3]
    emit(p0, v0, T_HIT + 0.4 + 0.55 * U(n), 0.15 + 0.4 * U(n), 0.007 + 0.03 * U(n)**3, 0.6, 4.0)

    # 5. white water: low churned-up foam and vapour that hugs the surface where the body went in
    n = 11000
    p0 = (hit + ah * (-1.4 + 8.5 * U(n, -1, 1))[:, None] + nh * (3.0 * rng.normal(0, 1, n))[:, None]
          + up * U(n, 0.0, 1.2)[:, None])
    v0 = rng.normal(0, 1.2, (n, 3)) * [1, 1, 0.5] + up * 0.8
    emit(p0, v0, T_HIT - 0.25 + 1.6 * U(n)**1.5, 3 + 4 * U(n), 0.25 + 0.35 * U(n), 0.045, 3.0 + 2.0 * U(n), 0.7)

    S = {k: np.concatenate([s[k] for s in sets]) for k in sets[0]}
    S['seed'] = rng.uniform(0.75, 1.0, len(S['t0']))
    return S


def build_spray(S):
    n = len(S['t0'])
    faces = np.arange(n * 4).reshape(n, 4)
    me = mesh_from('Spray', np.zeros((n * 4, 3)), faces)
    uv = me.uv_layers.new(name='UVMap')
    corners = np.tile(np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float), (n, 1))
    try:
        uv.uv.foreach_set('vector', corners.ravel())
    except Exception:
        uv.data.foreach_set('uv', corners.ravel())
    me.attributes.new('pcol', 'FLOAT_COLOR', 'POINT')
    mat, N = new_material('Spray')
    q = N.v('SUBTRACT', N.new('ShaderNodeUVMap', uv_map='UVMap'), (0.5, 0.5, 0.0))
    soft = N.ramp(N.v('LENGTH', q, out=1), 0.5, 0.08)
    att = N.new('ShaderNodeAttribute', out=None, attribute_name='pcol')
    alpha = N.m('MULTIPLY', soft, att.outputs[3])
    sh = N.new('ShaderNodeMixShader', i={0: alpha, 1: N.new('ShaderNodeBsdfTransparent'),
                                        2: N.new('ShaderNodeEmission', i={0: att.outputs[0], 1: 1.0})})
    N.new('ShaderNodeOutputMaterial', out=None, i={0: sh})
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    ob = bpy.data.objects.new('Spray', me)
    ob.data.materials.append(mat)
    ob.visible_shadow = False
    bpy.context.scene.collection.objects.link(ob)
    return ob


def sun_shade(p, weight):
    """How much sunlight reaches each drop through the drops in front of it."""
    e1 = np.cross(SUN, [0, 0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(SUN, e1)
    cell = 0.6
    key = (np.floor(p @ e1 / cell).astype(np.int64) + 2048) * 4096 + np.floor(p @ e2 / cell).astype(np.int64) + 2048
    order = np.lexsort((-(p @ SUN), key))
    ks, ws = key[order], weight[order]
    cs = np.cumsum(ws)
    first = np.r_[True, ks[1:] != ks[:-1]]
    base = np.maximum.accumulate(np.where(first, cs - ws, 0.0))
    tau = np.empty_like(cs)
    tau[order] = cs - ws - base
    return np.exp(-0.6 * tau)


def spray_frame(S, t, cam_pos, right, upv, fwd, shutter=1 / 48):
    tau = t - S['t0']
    idx = np.nonzero((tau > 0) & (tau < S['life']))[0]
    tau, k = tau[idx], S['k'][idx][:, None]
    vt = WIND + np.array([0, 0, -G]) / k
    e = np.exp(-k * tau[:, None])
    p = S['p0'][idx] + vt * tau[:, None] + (S['v0'][idx] - vt) * (1 - e) / k
    v = vt + (S['v0'][idx] - vt) * e
    keep = p[:, 2] > -0.1
    idx, tau, p, v = idx[keep], tau[keep], p[keep], v[keep]
    r = S['r'][idx] * (1 + S['grow'][idx] * tau)
    life = S['life'][idx]
    alpha = S['a'][idx] * np.clip((tau - S['delay'][idx]) / 0.08, 0, 1) * np.clip((life - tau) / (0.4 * life), 0, 1)
    lit = sun_shade(p, alpha * math.pi * r * r / 0.36)
    col = (np.array([0.82, 0.88, 1.0]) * 1.25 + SUN_COL * (0.25 + 2.2 * lit[:, None])) * S['seed'][idx][:, None]
    # streak each drop along its motion on screen, as an open shutter would
    sr, su = (v @ right) * shutter * 0.5, (v @ upv) * shutter * 0.5
    ln = np.hypot(sr, su)
    dr, du = np.where(ln > 1e-5, sr / (ln + 1e-9), 1.0), np.where(ln > 1e-5, su / (ln + 1e-9), 0.0)
    along = (right * dr[:, None] + upv * du[:, None]) * (ln + r)[:, None]
    across = (right * -du[:, None] + upv * dr[:, None]) * r[:, None]
    alpha = alpha * r / (ln + r)
    order = np.argsort(-((p - cam_pos) @ fwd))
    p, along, across = p[order], along[order], across[order]
    quad = np.stack([p - along - across, p + along - across, p + along + across, p - along + across], 1)
    rgba = np.repeat(np.concatenate([col[order], alpha[order][:, None]], 1), 4, axis=0)
    return quad.reshape(-1, 3), rgba


# ---------------------------------------------------------------- camera
def camera_state(t):
    pos = np.array([spline(t, [0, 9], [-6.5, -3.2]), spline(t, [0, 9], [-57.0, -52.5]),
                    spline(t, [0, 4.5, 9], [3.6, 3.9, 3.8])])
    aim = np.array([spline(t, [0, 2, 4.5, 9], [2.6, 3.2, 4.3, 5.0]), 0.0,
                    spline(t, [0, 1.0, 2.4, 3.3, 4.6, 6, 9], [1.7, 2.1, 4.4, 4.9, 4.0, 3.7, 3.5])])
    hand = 0.10 * np.array([wobble(t * 0.9, 41, (1, 2.3, 3.7, 5.1)), 0, wobble(t * 0.9, 43, (1, 2.3, 3.7, 5.1))])
    jolt = max(t - T_HIT - 0.12, 0.0)
    hand[2] += 0.32 * math.exp(-3.2 * jolt) * math.sin(2 * math.pi * 4.6 * jolt) * (jolt > 0)
    fwd = aim + hand - pos
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 0, 1.0])
    right /= np.linalg.norm(right)
    return pos, right, np.cross(right, fwd), fwd, float(spline(t, [0, 3.2, 9], [72, 80, 84]))


# ---------------------------------------------------------------- colour grade
def build_grade(scene):
    """Bloom on the sun and the spray, teal shadows, warm highlights, a soft vignette."""
    g = bpy.data.node_groups.new('Grade', 'CompositorNodeTree')
    g.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    src = g.nodes.new('CompositorNodeRLayers')
    out = g.nodes.new('NodeGroupOutput')

    def menu(node, name, *choices):
        for c in choices:
            try:
                node.inputs[name].default_value = c
                return
            except Exception:
                pass

    glare = g.nodes.new('CompositorNodeGlare')
    menu(glare, 'Type', 'Bloom', 'Fog Glow')
    menu(glare, 'Quality', 'High')
    for k, v in (('Threshold', 2.4), ('Smoothness', 0.4), ('Strength', 0.8), ('Size', 0.75), ('Clamp', True), ('Maximum', 8.0)):
        glare.inputs[k].default_value = v
    bal = g.nodes.new('CompositorNodeColorBalance')
    menu(bal, 'Type', 'Lift/Gamma/Gain')
    for k, (v, col) in {'Lift': (0.0, (0.93, 1.0, 1.06)), 'Gamma': (1.0, (1.0, 0.99, 0.98)),
                        'Gain': (1.04, (1.06, 1.0, 0.92))}.items():
        scal, colr = [s for s in bal.inputs if s.name == k]
        scal.default_value, colr.default_value = v, rgb(*col)
    sat = g.nodes.new('CompositorNodeHueSat')
    sat.inputs['Saturation'].default_value = 1.12
    lens = g.nodes.new('CompositorNodeLensdist')
    lens.inputs['Distortion'].default_value, lens.inputs['Dispersion'].default_value = 0.01, 0.008
    lens.inputs['Fit'].default_value = True
    mask = g.nodes.new('CompositorNodeEllipseMask')
    mask.inputs['Size'].default_value = (1.08, 1.02)
    blur = g.nodes.new('CompositorNodeBlur')
    blur.inputs['Size'].default_value = (380.0 * scene.render.resolution_percentage / 100,) * 2
    dark = g.nodes.new('ShaderNodeMix')
    dark.data_type, dark.blend_type = 'RGBA', 'MULTIPLY'
    dark.inputs[0].default_value = 0.55
    L = g.links.new
    L(src.outputs[0], glare.inputs[0]); L(glare.outputs[0], lens.inputs[0]); L(lens.outputs[0], bal.inputs[0])
    L(bal.outputs[0], sat.inputs[0]); L(sat.outputs[0], dark.inputs[6])
    L(mask.outputs[0], blur.inputs[0]); L(blur.outputs[0], dark.inputs[7]); L(dark.outputs[2], out.inputs[0])
    scene.compositing_node_group = g
    scene.render.use_compositing = True


# ---------------------------------------------------------------- putting it together
def setup(scale, samples):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, scale
    sc.render.fps, sc.frame_start, sc.frame_end = FPS, 0, int(DUR * FPS) - 1
    sc.render.image_settings.file_format, sc.render.image_settings.compression = 'PNG', 20
    ev = sc.eevee
    ev.taa_render_samples, ev.use_raytracing, ev.use_shadows = samples, True, True
    try:
        ev.ray_tracing_options.resolution_scale = '2'
        ev.ray_tracing_options.screen_trace_quality = 0.3
        ev.shadow_ray_count, ev.shadow_step_count = 2, 6
    except Exception as err:
        print('eevee option skipped:', err)
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.exposure = 0.0
    for look in ('AgX - Punchy', 'AgX - Medium High Contrast'):
        try:
            sc.view_settings.look = look
            break
        except Exception:
            pass
    return sc


def build_all(scale, samples):
    global WD
    sc = setup(scale, samples)
    WD = build_whale_data()
    whale = build_whale(WD)
    whale.data.materials.append(whale_material())
    sea, oceans = build_sea()
    st = whale_state(T_EXIT + 0.7)
    exit_xy = st['pos'] - st['pos'][2] / math.sin(st['pitch']) * np.array(
        [math.cos(st['pitch']) * math.cos(HEADING), math.cos(st['pitch']) * math.sin(HEADING), math.sin(st['pitch'])])
    _, hit, Rh = whale_frame(T_HIT)
    water, V = sea_material(exit_xy, hit + Rh @ np.array([-1.4, 0, 0]))
    sea.data.materials.append(water)
    build_sky()
    S = make_spray()
    spray = build_spray(S)
    cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    cam.data.sensor_width, cam.data.clip_start, cam.data.clip_end = 36.0, 0.5, 20000.0
    sc.collection.objects.link(cam)
    sc.camera = cam
    try:
        build_grade(sc)
    except Exception as err:
        print('grade skipped:', err)
    return dict(sc=sc, whale=whale, sea=sea, oceans=oceans, V=V, S=S, spray=spray, cam=cam)


def apply_time(W, t, everything=True):
    """Set the whole scene to time t (seconds). Nothing is keyframed; this is the animation."""
    st, pos, R = whale_frame(t)
    W['whale'].data.vertices.foreach_set('co', pose_whale(WD, st).ravel())
    W['whale'].data.update()
    W['whale'].matrix_world = Matrix(np.vstack([np.column_stack([R, pos]), [0, 0, 0, 1]]).tolist())
    cpos, right, upv, fwd, lens = camera_state(t)
    W['cam'].matrix_world = Matrix(np.column_stack([np.append(right, 0), np.append(upv, 0),
                                                    np.append(-fwd, 0), np.append(cpos, 1)]).tolist())
    W['cam'].data.lens = lens
    if not everything:                                          # shutter sub-steps only need the whale and the camera
        return
    for m in W['oceans']:
        m.time = 3.0 + t * 0.62
    quad, rgba = spray_frame(W['S'], t, cpos, right, upv, fwd)
    me = W['spray'].data
    co = np.zeros((len(me.vertices), 3))
    co[:, 2] = -60.0
    co[:len(quad)] = quad
    col = np.zeros((len(me.vertices), 4))
    col[:len(rgba)] = rgba
    me.vertices.foreach_set('co', co.ravel())
    me.attributes['pcol'].data.foreach_set('color', col.ravel())
    me.update()
    V = W['V']
    V['time'].outputs[0].default_value = t * 0.55
    a, b = t - T_EXIT, t - T_HIT
    V['exit_r'].outputs[0].default_value = 1.4 + 2.3 * max(a, 0) - 0.12 * max(a, 0)**2
    V['exit_i'].outputs[0].default_value = float(smooth(-0.25, 0.25, a))
    V['slam_r'].outputs[0].default_value = 0.75 + 1.05 * (1 - math.exp(-1.1 * max(b, 0))) + 0.05 * max(b, 0)
    V['slam_i'].outputs[0].default_value = float(smooth(-0.3, 0.2, b))


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    opt = dict(scale=100, samples=20, grade=1, blur=1, out=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frames'))
    frames = []
    i = 0
    while i < len(argv):
        if argv[i] == '--still':
            frames = [int(f) for f in argv[i + 1].split(',')]; i += 2
        elif argv[i] == '--anim':
            frames = list(range(int(argv[i + 1]), int(argv[i + 2]) + 1)); i += 3
        else:
            opt[argv[i][2:]] = type(opt[argv[i][2:]])(argv[i + 1]); i += 2
    W = build_all(opt['scale'], opt['samples'])
    W['sc'].render.use_compositing = bool(opt['grade'])
    os.makedirs(opt['out'], exist_ok=True)
    if opt['blur']:
        # open the shutter for a third of a frame; Blender asks for the scene at the in-between times
        W['sc'].render.use_motion_blur, W['sc'].render.motion_blur_shutter = True, 0.35
        bpy.app.handlers.frame_change_pre.append(
            lambda scene, *_: apply_time(W, (scene.frame_current + scene.frame_subframe) / FPS,
                                         abs(scene.frame_subframe) < 1e-4))
    for f in frames:
        t0 = time.time()
        W['sc'].frame_set(f)
        apply_time(W, f / FPS)
        W['sc'].render.filepath = os.path.join(opt['out'], 'f_%04d.png' % f)
        bpy.ops.render.render(write_still=True)
        print('FRAME %d done in %.1f s' % (f, time.time() - t0), flush=True)


main()
