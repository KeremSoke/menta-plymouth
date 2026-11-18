#!/usr/bin/env python3
"""Procedurally render a fixed-tilt planet logo for a Plymouth boot splash.

The two thick rings and the MATE-inspired triangle are authored in ONE local
(u,v,0) plane. Their 3-D orientation never changes during the animation.
A triangle revolves in that plane and highlights travel around the rings.

Requirements: Python 3 and Pillow (Ubuntu: sudo apt install python3-pil).
Run: python3 generate_frames.py

THis is a GPLv3 script. 
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "orbit-plane"
OUT.mkdir(exist_ok=True)

# ---------------- EDIT THE DESIGN HERE ----------------
SIZE = 512                         # transparent icon dimensions
SUPERSAMPLE = 2                    # 2 or 3 for antialiased output
FRAMES = 60                        # repeatable seamless loop
FRAME_MILLISECONDS = 65            # preview playback rate

# FIXED plane orientation. Animation does NOT touch these values.
TILT_X_DEGREES = 60.0              # ring plane viewed at 30° elevation, for a clear Saturn-style ellipse
TILT_Y_DEGREES = 15.0              # slight secondary 3D twist
ROLL_Z_DEGREES = -22.0             # rotate the projected ellipse on the screen
# If you literally want to rotate the face-on plane just 30°, use 30 here;
# its projected rings will be almost round (minor/major axis ratio cos 30°).

PLANET_RADIUS = 100                # large enough to occupy ring center
INNER_RING_RADIUS = 153            # ring centerlines (not edges)
INNER_RING_WIDTH = 27              # actual filled bands, not hairlines
OUTER_RING_RADIUS = 212
OUTER_RING_WIDTH = 29

# The triangle points RADIAL INWARD (as in the reference MATE-style symbol)
TRIANGLE_TIP_RADIUS = 126          # its point is closer to the planet
TRIANGLE_BASE_RADIUS = 239         # its base reaches outside the outer ring
TRIANGLE_HALF_BASE = 49            # half the base width, measured tangentially
TRIANGLE_START_ANGLE = 190         # initial orbit position in degrees

# Palette: muted MATE greens with a dark green stroke and a lit left/top edge.
INNER_COLOR = (118, 154, 79)
OUTER_COLOR = (123, 160, 82)
RING_DARK_EDGE = (47, 71, 37)
RING_LIGHT_EDGE = (178, 204, 123)
# Gentle continuous shading: no abrupt repeating color blocks.
RING_GRADIENT_STRENGTH = 0.095   # static soft directional gradient
RING_SHEEN_STRENGTH = 0.125      # moving, broad highlight within the fixed plane
BACK_RING_DIMMING = 0.19        # rear sectors gradually darken
FRONT_RING_SHADOW = 0.30       # very soft shadow projected onto the planet
SHADOW_BLUR = 6.0              # original-size pixels
SHADOW_OFFSET = (4, -5)       # towards the sphere from lower-left ring
TRIANGLE_RING_GAP = 1.16      # outline-shaped break in both bands
TRIANGLE_BORDER = (48, 73, 36)
TRIANGLE_RIM = (168, 196, 119)
TRIANGLE_FILL = (151, 183, 101)
TRIANGLE_HIGHLIGHT = (196, 219, 145)
# The triangle uses the ring's SAME plane-lighting model. These parameters add
# gentle local surface reflections as it physically travels around the sphere.
TRIANGLE_GLINT_STRENGTH = 0.075      # restrained highlight during one orbit
TRIANGLE_FACE_GRADIENT = 0.045      # subtle shading across the triangular face
TRIANGLE_GLINT_DIRECTION = 310.0    # fixed light direction in orbital-plane degrees
TRIANGLE_BRIGHTNESS = 0.82          # tone down the pointer relative to the rings
# -------------------------------------------------------

S = SUPERSAMPLE
CANVAS = SIZE * S
C = CANVAS / 2
TAU = math.tau
RX, RY, RZ = map(math.radians,
    (TILT_X_DEGREES, TILT_Y_DEGREES, ROLL_Z_DEGREES))
SX, CX = math.sin(RX), math.cos(RX)
SY, CY = math.sin(RY), math.cos(RY)
SZ, CZ = math.sin(RZ), math.cos(RZ)


def project(u: float, v: float):
    """Orthographic front view of a point on the SAME fixed orbital plane.

    Apply the fixed X tilt (60°), then Y (15°), then screen Z (-22°).
    z is camera depth, positive is closer to the viewer. No time parameter.
    """
    x1, y1, z1 = u, CX*v, SX*v
    x2, y2, z2 = CY*x1 + SY*z1, y1, -SY*x1 + CY*z1
    x3, y3 = CZ*x2 - SZ*y2, SZ*x2 + CZ*y2
    return C + x3*S, C + y3*S, z2


def on_ring(radius, a):
    return project(radius*math.cos(a), radius*math.sin(a))


def ellipse_points(radius, steps=720):
    return [(on_ring(radius, TAU*i/steps)[0],
             on_ring(radius, TAU*i/steps)[1]) for i in range(steps)]


def annulus_mask(radius, width):
    """Filled elliptical band, with a genuine hole (not a thick single line)."""
    mask = Image.new('L', (CANVAS, CANVAS), 0)
    d = ImageDraw.Draw(mask)
    d.polygon(ellipse_points(radius + width/2), fill=255)
    d.polygon(ellipse_points(radius - width/2), fill=0)
    return mask


def front_half_mask(radius, width, steps=720):
    """Only sectors physically in front of the z=0 planet equatorial plane."""
    mask = Image.new('L', (CANVAS, CANVAS), 0)
    d = ImageDraw.Draw(mask)
    r0, r1 = radius-width/2, radius+width/2
    for i in range(steps):
        a0, a1 = TAU*i/steps, TAU*(i+1)/steps
        mid = (a0+a1)*.5
        if on_ring(radius, mid)[2] > 0:
            d.polygon([on_ring(r0, a0)[:2], on_ring(r1, a0)[:2],
                       on_ring(r1, a1)[:2], on_ring(r0, a1)[:2]], fill=255)
    return mask


def triangle_vertices(phi):
    """Triangle in the exact same 3D plane as both rings.

    Tip points inward to the planet; base is broad and outward. The whole
    shape rotates around the planet with phi, with no perspective shortcuts.
    """
    ex, ey = math.cos(phi), math.sin(phi)
    tx, ty = -ey, ex
    tip = (TRIANGLE_TIP_RADIUS*ex, TRIANGLE_TIP_RADIUS*ey)
    base_a = (TRIANGLE_BASE_RADIUS*ex + TRIANGLE_HALF_BASE*tx,
              TRIANGLE_BASE_RADIUS*ey + TRIANGLE_HALF_BASE*ty)
    base_b = (TRIANGLE_BASE_RADIUS*ex - TRIANGLE_HALF_BASE*tx,
              TRIANGLE_BASE_RADIUS*ey - TRIANGLE_HALF_BASE*ty)
    return [project(*p) for p in (tip, base_a, base_b)]


def inset_triangle(points, fraction):
    mx = sum(x for x,y in points)/3
    my = sum(y for x,y in points)/3
    return [(mx+(x-mx)*fraction, my+(y-my)*fraction) for x,y in points]


def expand_polygon(points, fraction):
    """Screen-space expansion used to cut the ring bands around the triangle.

    This intentionally mimics the MATE logo treatment: the rings do not merely
    sit underneath the triangle; they are broken by a slightly larger triangle-
    shaped gap.
    """
    mx = sum(x for x,y in points)/len(points)
    my = sum(y for x,y in points)/len(points)
    return [(mx + (x-mx)*fraction, my + (y-my)*fraction) for x,y in points]


def triangle_cut_mask(points, fraction=TRIANGLE_RING_GAP):
    mask = Image.new('L', (CANVAS, CANVAS), 0)
    d = ImageDraw.Draw(mask)
    d.polygon(expand_polygon(points, fraction), fill=255)
    return mask


def plane_coords_from_screen(x, y):
    """Inverse of the fixed projection, so triangle light is computed in 3D."""
    a = CZ*CY
    b = CZ*SY*SX - SZ*CX
    c = SZ*CY
    d = SZ*SY*SX + CZ*CX
    det = a*d - b*c
    sx, sy = (x-C)/S, (y-C)/S
    u = (d*sx-b*sy)/det
    v = (-c*sx+a*sy)/det
    z = -SY*u + CY*SX*v
    return u, v, z


def orbital_light(phi, z, radius, bevel):
    """Continuous key light and front/back shading shared by rings + pointer."""
    light = math.cos(phi - math.radians(145))
    gain = 0.84 + 0.105*bevel + RING_GRADIENT_STRENGTH*light
    rear = max(0.0, min(1.0, -z/(radius*.40)))
    rear = rear*rear*(3-2*rear)
    return gain * (1 - BACK_RING_DIMMING*rear)


def make_triangle(phi):
    """Draw the shaded MATE-like pointer in the SAME fixed 3D orbital plane.

    Its colors now respond to orbital angle and depth. The fixed light gives
    it a smooth dark-to-light cycle as it orbits, while a brief directional
    glint crosses its face. Its strong MATE-inspired border stays legible.
    """
    points3 = triangle_vertices(phi)
    points = [(x,y) for x,y,z in points3]
    layer = Image.new('RGBA', (CANVAS, CANVAS), (0,0,0,0))

    border_mask = Image.new('L', (CANVAS, CANVAS), 0)
    rim_mask = Image.new('L', (CANVAS, CANVAS), 0)
    face_mask = Image.new('L', (CANVAS, CANVAS), 0)
    ImageDraw.Draw(border_mask).polygon(points, fill=255)
    ImageDraw.Draw(rim_mask).polygon(inset_triangle(points, .93), fill=255)
    ImageDraw.Draw(face_mask).polygon(inset_triangle(points, .84), fill=255)

    bounds = border_mask.getbbox()
    if bounds:
        outer = border_mask.load()
        rim = rim_mask.load()
        face = face_mask.load()
        pixels = layer.load()
        direction = math.radians(TRIANGLE_GLINT_DIRECTION)
        tangent_x, tangent_y = -math.sin(phi), math.cos(phi)
        # Avoid readback of the floating-point projected vertices per pixel;
        # every pixel maps back into the original unrotated orbital plane.
        for y in range(bounds[1], bounds[3]):
            for x in range(bounds[0], bounds[2]):
                if not outer[x,y]:
                    continue
                u, v, z = plane_coords_from_screen(x+.5, y+.5)
                angle = math.atan2(v, u)
                gain = orbital_light(angle, z, TRIANGLE_BASE_RADIUS, 1.0)
                # A small spatial gradient follows the triangle's own axes.
                side = (u*tangent_x + v*tangent_y)/TRIANGLE_HALF_BASE
                gain += TRIANGLE_FACE_GRADIENT * max(-1, min(1, -side))
                # Fixed light in space: the travelling triangle catches it
                # once per revolution, matching the moving material lighting.
                alignment = (1.0 + math.cos(angle-direction))*0.5
                gain += TRIANGLE_GLINT_STRENGTH*(alignment**15)
                if face[x,y]:
                    base = TRIANGLE_FILL
                elif rim[x,y]:
                    base = TRIANGLE_RIM
                    gain *= 1.055
                else:
                    base = TRIANGLE_BORDER
                    gain *= .89
                gain = max(.58, min(1.14, gain)) * TRIANGLE_BRIGHTNESS
                pixels[x,y] = tuple(min(255,round(c*gain)) for c in base)+(255,)

    # Refined inner edge, muted enough to remain compatible with the smooth
    # annular bands. It is composited above the shaded face, not a flat fill.
    d = ImageDraw.Draw(layer)
    tip, a, b = inset_triangle(points, .82)
    inner_points = [tip,a,b]
    lighting_at_tip = orbital_light(phi, sum(z for _,_,z in points3)/3,
                                    TRIANGLE_BASE_RADIUS, 1.0)
    rim_brightness = max(.68,min(1.04,lighting_at_tip)) * TRIANGLE_BRIGHTNESS
    highlight_color = tuple(round(c*rim_brightness) for c in TRIANGLE_HIGHLIGHT)+(70,)
    d.line([a, tip], fill=highlight_color, width=max(1,S), joint='curve')
    return layer, sum(z for x,y,z in points3)/3


def planet_sprite():
    """Hand-defined shaded sphere with a small soft atmospheric halo."""
    r = PLANET_RADIUS*S
    pad = 22*S
    dim = int(2*(r+pad))
    mid = dim/2
    planet = Image.new('RGBA', (dim,dim), (0,0,0,0))
    pix = planet.load()
    for y in range(dim):
        v = (y-mid)/r
        for x in range(dim):
            u = (x-mid)/r
            d = u*u+v*v
            if d >= 1: continue
            z = math.sqrt(1-d)
            lighting = max(0, -.50*u-.47*v+.72*z)
            luminosity = .19+.79*min(1,lighting)
            atmosphere = .18 * (1-z)**2
            bands = .04*math.sin(17*v + 3*math.sin(5*u))
            base = (13, 46, 54)
            lit = (91, 162, 131)
            rgb = tuple(max(0,min(255,int(base[k] + (lit[k]-base[k])*luminosity
                       + 26*atmosphere + bands*25))) for k in range(3))
            pix[x,y] = (*rgb, 255)
    halo_mask = Image.new('L',(dim,dim),0)
    md = ImageDraw.Draw(halo_mask)
    md.ellipse((mid-r,mid-r,mid+r,mid+r), fill=120)
    halo_mask = halo_mask.filter(ImageFilter.GaussianBlur(radius=10*S))
    halo = Image.new('RGBA',(dim,dim),(80,170,130,0))
    halo.putalpha(halo_mask.point(lambda p: int(p*.40)))
    halo.alpha_composite(planet)
    return halo


SPHERE = planet_sprite()
RINGS = ((INNER_RING_RADIUS, INNER_RING_WIDTH, INNER_COLOR),
         (OUTER_RING_RADIUS, OUTER_RING_WIDTH, OUTER_COLOR))
MASKS = [annulus_mask(r,w) for r,w,c in RINGS]
FRONT_MASKS = [front_half_mask(r,w) for r,w,c in RINGS]


def ring_pixel_geometry(radius, width, mask):
    """Cache a screen pixel's inverse projection into the stationary ring plane.

    All shading is smooth and continuous in polar coordinates. Caching keeps the
    60 frame regeneration fast using only Pillow, without NumPy at build time.
    """
    a = CZ*CY
    b = CZ*SY*SX - SZ*CX
    c = SZ*CY
    d = SZ*SY*SX + CZ*CX
    det = a*d-b*c
    m = mask.load()
    x0,y0,x1,y1 = mask.getbbox()
    geometry = []
    for y in range(y0,y1):
        sy=(y-C)/S
        for x in range(x0,x1):
            alpha=m[x,y]
            if not alpha: continue
            sx=(x-C)/S
            u=(d*sx-b*sy)/det
            v=(-c*sx+a*sy)/det
            phi=math.atan2(v,u)
            radial=math.hypot(u,v)
            t=max(0.0,min(1.0,(radial-(radius-width*.5))/width))
            # Rounded, slightly beveled band with neither hard blocks nor steps.
            bevel=math.sin(math.pi*t)**0.68
            z=-SY*u + CY*SX*v
            fixed_gain = orbital_light(phi, z, radius, bevel)
            geometry.append((x,y,alpha,math.cos(phi),math.sin(phi),fixed_gain))
    return geometry


RING_PIXELS = [ring_pixel_geometry(r,w,MASKS[i]) for i,(r,w,base) in enumerate(RINGS)]
SPHERE_DISC_MASK = Image.new('L',(CANVAS,CANVAS),0)
ImageDraw.Draw(SPHERE_DISC_MASK).ellipse((C-PLANET_RADIUS*S, C-PLANET_RADIUS*S,
                                         C+PLANET_RADIUS*S, C+PLANET_RADIUS*S),fill=255)


def render_ring(radius, width, base_color, mask, progress, index):
    """Render continuous light across the whole ring, with moving soft sheen.

    The highlight is a wide cosine-power lobe that circles in the fixed ring
    plane; it replaces the previous sharp alternating polygonal decals.
    """
    ring=Image.new('RGBA',(CANVAS,CANVAS),(0,0,0,0))
    px=ring.load()
    phase=progress*TAU + index*0.38
    cp,sp=math.cos(phase),math.sin(phase)
    for x,y,alpha,ca,sa,fixed_gain in RING_PIXELS[index]:
        angular_closeness=(1 + ca*cp + sa*sp)*.5
        soft_sheen=RING_SHEEN_STRENGTH*(angular_closeness**7)
        gain=fixed_gain+soft_sheen
        px[x,y]=(min(255,int(base_color[0]*gain)),
                 min(255,int(base_color[1]*gain)),
                 min(255,int(base_color[2]*gain)), alpha)
    # Restrained contours make the thick, continuously shaded bands legible.
    edge=Image.new('RGBA',(CANVAS,CANVAS),(0,0,0,0))
    ed=ImageDraw.Draw(edge)
    for boundary, color, opacity in ((radius-width*.5+1.2,RING_DARK_EDGE,83),
                                     (radius+width*.5-1.2,RING_LIGHT_EDGE,70)):
        pts=ellipse_points(boundary)
        ed.line(pts+[pts[0]],fill=(*color,opacity),width=max(1,S),joint='curve')
    ring.alpha_composite(edge)
    ring.putalpha(ImageChops.multiply(ring.getchannel('A'),mask))
    return ring


def add_ring_shadow(composite, foreground):
    """Cast a subdued, soft-edged shadow from front arcs onto the sphere only."""
    source=foreground.getchannel('A')
    shifted=ImageChops.offset(source,SHADOW_OFFSET[0]*S,SHADOW_OFFSET[1]*S)
    soft=shifted.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR*S))
    soft=ImageChops.multiply(soft,SPHERE_DISC_MASK)
    alpha=soft.point(lambda value:int(value*FRONT_RING_SHADOW))
    shadow=Image.new('RGBA',(CANVAS,CANVAS),(4,16,17,0))
    shadow.putalpha(alpha)
    composite.alpha_composite(shadow)


def render_frame(i):
    progress = i / FRAMES
    back = Image.new('RGBA',(CANVAS,CANVAS),(0,0,0,0))
    front = Image.new('RGBA',(CANVAS,CANVAS),(0,0,0,0))

    angle = math.radians(TRIANGLE_START_ANGLE) + TAU*progress
    arrow, arrow_depth = make_triangle(angle)
    cut_mask = triangle_cut_mask([(x,y) for x,y,z in triangle_vertices(angle)], fraction=TRIANGLE_RING_GAP)

    for j,(r,w,base) in enumerate(RINGS):
        layer = render_ring(r,w,base,MASKS[j],progress,j)
        # Break the rings around the triangle, matching the logo treatment.
        layer_alpha = ImageChops.subtract(layer.getchannel('A'), cut_mask)
        layer.putalpha(layer_alpha)
        front_alpha = ImageChops.multiply(layer_alpha, FRONT_MASKS[j])
        front_layer = layer.copy()
        front_layer.putalpha(front_alpha)
        back_layer = layer.copy()
        back_layer.putalpha(ImageChops.subtract(layer_alpha,front_alpha))
        back.alpha_composite(back_layer)
        front.alpha_composite(front_layer)
    result = back
    if arrow_depth <= 0:
        result.alpha_composite(arrow)
    pos = (round(C-SPHERE.width/2), round(C-SPHERE.height/2))
    result.alpha_composite(SPHERE, pos)
    add_ring_shadow(result,front)
    result.alpha_composite(front)
    if arrow_depth > 0:
        result.alpha_composite(arrow)
    return result.resize((SIZE,SIZE), Image.Resampling.LANCZOS)


def background(size):
    w,h = size
    bg = Image.new('RGB',(w,h))
    pixels = bg.load()
    for y in range(h):
        dy = (y-h/2)/(h/2)
        for x in range(w):
            dx = (x-w/2)/(h/2)
            glow = max(0,1-(dx*dx+dy*dy))**2
            t = y/max(1,h-1)
            pixels[x,y] = (int(5+12*glow+5*(1-t)),
                           int(10+25*glow+7*(1-t)),
                           int(22+38*glow+9*(1-t)))
    rng = random.Random(17)
    draw = ImageDraw.Draw(bg)
    for _ in range(75):
        x,y = rng.randrange(w),rng.randrange(h)
        a = rng.randrange(35,105)
        draw.point((x,y),fill=(a,a+10,a+28))
    return bg


def main():
    frames=[]
    bg=background((660,500)).convert('RGBA')
    for i in range(FRAMES):
        logo=render_frame(i)
        logo.save(OUT / f'frame-{i}.png', optimize=True)
        display=bg.copy()
        logo=logo.resize((450,450),Image.Resampling.LANCZOS)
        display.alpha_composite(logo,(105,25))
        frames.append(display.convert('RGB'))
    frames[0].save(ROOT/'preview.gif',save_all=True,
        append_images=frames[1:],duration=FRAME_MILLISECONDS,loop=0,optimize=True)
    frames[0].save(ROOT/'preview.png')
    indexes=[0,7,15,22,30,37,45,52]
    contact=Image.new('RGB',(4*330,2*250),(5,12,25))
    for k,index in enumerate(indexes):
        shot=frames[index].resize((330,250),Image.Resampling.LANCZOS)
        contact.paste(shot,((k%4)*330,(k//4)*250))
    contact.save(ROOT/'contact.png')
    print(f'Created {FRAMES} PNGs, preview.gif, preview.png, contact.png')
    print(f'Fixed plane: X={TILT_X_DEGREES}°, Y={TILT_Y_DEGREES}°, screen Z={ROLL_Z_DEGREES}°')

if __name__ == '__main__':
    main()
