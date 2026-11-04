"""Code that runs inside Blender (`bpy`), started by render/blender_render.py as
`blender -b --factory-startup --python-exit-code 1 -P blender/run.py -- <job.json>`.

Blender has its own Python, so nothing here imports the app: a job JSON comes in, frames and a tracks JSON go out.
"""
