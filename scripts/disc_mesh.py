"""Bake tilted native ImageWarp meshes into transparent, projected UI layers.

Uses the game's subdivided mesh, not a rectangular resize or an AI reconstruction.
"""
import math

import numpy as np
from PIL import Image


def mesh_vertices(mesh, focal):
    bl, tl, tr, br = np.asarray(mesh['corners'], dtype=float)
    n = mesh['subdivisions']
    uv = np.array([(x/n, y/n) for y in range(n+1) for x in range(n+1)])
    u, v = uv[:, :1], uv[:, 1:]
    points = (1-u)*(1-v)*tl + u*(1-v)*tr + (1-u)*v*bl + u*v*br
    if np.any(focal + points[:, 2] <= 0):
        raise ValueError('Native mesh crosses the camera plane')
    projected = points[:, :2] * (focal/(focal+points[:, 2:3]))
    return uv, projected


def mesh_bounds(mesh, focal):
    _, points = mesh_vertices(mesh, focal)
    lo, hi = points.min(axis=0), points.max(axis=0)
    return {'x': float((lo[0]+hi[0])/2), 'y': float((lo[1]+hi[1])/2),
            'width': float(hi[0]-lo[0]), 'height': float(hi[1]-lo[1]),
            'pivot': {'x': .5, 'y': .5}, 'rotation': 0}


def layer_image(layer, sprite):
    source = sprite.read().image.convert('RGBA')
    mesh = layer.get('native_mesh')
    if not mesh:
        return source
    uv, points = mesh_vertices(mesh, mesh['focal_length'])
    # At least twice the reference Canvas density, including fullscreen displays.
    density = max(2, source.width/layer['width'], source.height/layer['height'])
    width, height = math.ceil(layer['width']*density), math.ceil(layer['height']*density)
    lo, hi = points.min(axis=0), points.max(axis=0)
    points = np.column_stack(((points[:, 0]-lo[0])/(hi[0]-lo[0])*width,
                              (hi[1]-points[:, 1])/(hi[1]-lo[1])*height))
    texture = np.asarray(source, dtype=float)/255
    texture[:, :, :3] *= texture[:, :, 3:4]
    output = np.zeros((height, width, 4), dtype=float)
    n = mesh['subdivisions']
    for y in range(n):
        for x in range(n):
            a = y*(n+1)+x
            for indices in ([a, a+1, a+n+1], [a+1, a+n+2, a+n+1]):
                triangle = points[indices]
                left, top = np.maximum(np.floor(triangle.min(axis=0)).astype(int), 0)
                right, bottom = np.minimum(np.ceil(triangle.max(axis=0)).astype(int), [width, height])
                if right <= left or bottom <= top:
                    continue
                inverse = np.linalg.inv(np.vstack((triangle.T, np.ones(3))))
                yy, xx = np.mgrid[top:bottom, left:right]
                weights = np.stack((xx+.5, yy+.5, np.ones_like(xx)), axis=-1) @ inverse.T
                inside = np.all(weights >= -1e-8, axis=-1)
                coords = weights @ uv[indices]
                sx = np.clip(coords[:, :, 0]*source.width-.5, 0, source.width-1)
                sy = np.clip(coords[:, :, 1]*source.height-.5, 0, source.height-1)
                ix, iy = sx.astype(int), sy.astype(int)
                jx, jy = np.minimum(ix+1, source.width-1), np.minimum(iy+1, source.height-1)
                fx, fy = (sx-ix)[:, :, None], (sy-iy)[:, :, None]
                pixels = ((texture[iy, ix]*(1-fx)+texture[iy, jx]*fx)*(1-fy)
                          +(texture[jy, ix]*(1-fx)+texture[jy, jx]*fx)*fy)
                output[top:bottom, left:right][inside] = pixels[inside]
    alpha = output[:, :, 3:4]
    output[:, :, :3] = np.divide(output[:, :, :3], alpha,
                                  out=np.zeros_like(output[:, :, :3]), where=alpha>0)
    return Image.fromarray(np.uint8(np.clip(output*255+.5, 0, 255)))
