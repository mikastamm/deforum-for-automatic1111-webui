from glob import glob
from tkinter import N
from pydantic import BaseModel, Field
import math
from modules.script_callbacks import on_app_started

def live_edit_on_app_start(demo, app):
    app.add_api_route("/deforum/live-edit/look-at", live_edit_look_at, methods=["POST"])

def init_live_edit():
    on_app_started(live_edit_on_app_start)
init_live_edit()

class LiveEditRequest(BaseModel):
    x: float = Field(default=None, title="Target point x", description="X location of the point in the image to move to / look at. (0-1)")
    y: float = Field(default=None, title="Target point y", description="Y location of the point in the image to move to / look at. (0-1) ")

#Called when the user clicks on the image to move the camera to that point
def live_edit_look_at(req: LiveEditRequest):
    print("Received lookat request, settign target point", req)
    global alignment_target_point_01
    alignment_target_point_01 = (req.x, req.y)
    
def rotate_to_align(targetPoint, toPoint, nearplaneDistance):
    # Get the angle between the two points
    radsY = math.atan((targetPoint[1] - toPoint[1]) / nearplaneDistance)
    radsX = math.atan((targetPoint[0] - toPoint[0]) / nearplaneDistance)
    return (radsX, radsY)

#Set when the user calls the API to move the camera to a point
alignment_target_point_01 = None

#Set on the next frame after alignment_target_point_01 is set
rad_distance_to_target = (0,0)
start_frame = None
look_at_duration = None

#Call to start smoothly aligning the camera to the target point
def rotate_to_align_smoothly(targetPoint, toPoint, nearplaneDistance, frame_idx):
    global rad_distance_to_target
    global alignment_duration_in_frames
    global start_frame
    global look_at_duration
    start_frame = frame_idx
    rad_distance_to_target = rotate_to_align(targetPoint, toPoint, nearplaneDistance)

def easeInOutQuad(x):
    return 2 * x ** 2 if x < 0.5 else 1 - ((-2 * x + 2) ** 2) / 2
def easeInOutSine(x: float) -> float:
    return -(math.cos(math.pi * x) - 1) / 2
def easeInOutCubic(x: float) -> float:
    return 4 * x**3 if x < 0.5 else 1 - ((-2 * x + 2) ** 3) / 2
def easeOutCubic(x: float) -> float:
    return 1 - (1 - x) ** 3
def easeOutQuad(x: float) -> float:
    return 1 - (1 - x) ** 2
def easeInQuad(x: float) -> float:
    return x ** 2
def easeInSine(x: float) -> float:
    return 1 - math.cos((x * math.pi) / 2)

def live_edit_get_rotation_speed(prev_img_cv2, anim_args, keys, frame_idx):
    global rad_distance_to_target
    global start_frame
    global look_at_duration
    global alignment_target_point_01
    if alignment_target_point_01 is None:
        print("No realgnment requested, not rotating")
        return (0,0,0)
    if start_frame is None:
        #print("Found a requested realignment but anim was not started, starting rotation")
        #start the rotation
        start_frame = frame_idx
        look_at_duration = 60 #TODO make this a parameter in keys
        alignment_to_point01 = (0.5,0.5)
        nearplane_width = 2 * keys.near_series[frame_idx] * math.tan(math.radians(keys.fov_series[frame_idx]) / 2)
        nearplane_height = nearplane_width / (prev_img_cv2.shape[1] / prev_img_cv2.shape[0])
        alignment_target_point = (alignment_target_point_01[0] * nearplane_width, alignment_target_point_01[1] * nearplane_height)
        to_point_nearplane_space = (alignment_to_point01[0] * nearplane_width, alignment_to_point01[1] * nearplane_height)
        #print(f"--From: {alignment_target_point}")
        #print(f"--To: {to_point_nearplane_space}")
        rotate_to_align_smoothly(alignment_target_point, to_point_nearplane_space, keys.near_series[frame_idx], frame_idx)

    startedNFramesAgo = frame_idx - start_frame
    interpolationProgress = easeInOutSine(startedNFramesAgo / look_at_duration)
    interpolationProgressSpeed =  easeInOutSine(startedNFramesAgo / look_at_duration) - easeInOutSine((startedNFramesAgo - 1) / look_at_duration)
    rotation_speed_cur_frame = (rad_distance_to_target[0] * interpolationProgressSpeed, rad_distance_to_target[1] * interpolationProgressSpeed, 0)
    print(f"Rotating to align to {alignment_target_point_01} ({startedNFramesAgo}/{look_at_duration}) - total rotation: {rad_distance_to_target}")
    #print(f"--Rotation speed this frame: {rotation_speed_cur_frame}")
    #print(f"--Rotation progress: {interpolationProgress}")
    #print(f"--Rotation progress speed: {interpolationProgressSpeed}")
    #print(f"--Nearplane: {keys.near_series[frame_idx]}")

    if startedNFramesAgo+1 > look_at_duration:
        print("Finished rotation")
         # we are aligned now
        start_frame = None
        look_at_duration = None
        alignment_target_point_01 = None
        rad_distance_to_target = (0,0)
    
    return rotation_speed_cur_frame
    

def get_translation_until(frame_idx, current_frame_idx, anim_args, keys):
    return (0,0,0.5)