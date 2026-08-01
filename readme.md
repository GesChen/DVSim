# Dynamic Vision Simulator (DVSim)
is a Unity-based Event Camera simulator

# Requirements
- Python 3.13.0
- Unity Editor 2022.3.62f2
- Packages in requirements.txt
- ffmpeg
- Blender 5.2.0 (optional)

# Setup
```sh
cd any SSD based drive
git clone https://github.com/GesChen/DVSim.git
cd DVSim
py setup.py
```
Follow setup recommendations, then open Unity Hub -> Add -> Add project from disk -> Open the entire DVSim folder
- A shader error may occur, this can be ignored.
Then, open the "Main" scene for the simulator

# Usage
## Assets file structure
- *Some assets are gitignored because of large file size and/or to not redistribute them without permission
- **Assets:** Contains all 3D models and recordings
	- Animated armature FBXs
		- `captury`, `freemocap`, `MotionBERT` - mostly straight from the source with some preprocessing into clean FBXs
		- `cmu mocap bvhs` - bvhs from the cmu motion capture dataset
		`BVH` - FBX converted BVHs from cmu ds
	- `exterior scenes`, `Replica` - environments, Replica is from the Replica indoor dataset
	- `.blend` files are development places, live work on models is performed in there
- **Materials** (self explanatory) 
	- `unity_texture_packer` - py script that converts multiple texture maps into unity's mask
- **Scenes** - only Main is important, the others can be ignored
- **Settings** - contain URP/rendering assets
	- PC_Renderer - the Depth/ID render feature is set in there, modification to it can be done that way
- **Scripts**
	- `Camera` - all sensor/camera related scripts
		- Simulation - `DVS` (most important), `DVSMemory`, (not used/unfinished ->)`DVSIO`, `DVSFasterMemory`
		- Camera motion - Anything starting in DVM + DVMotion
		- `PreviewCamera` - Editor utility to preview a specific sensor
	- `Objects` - any physical object that appears in the scene is a DVObject (DVO)
		- Anything starting in DVO_ is a component for an object
			- Every object in the scene that is rendered must have only one DVO component attached to it
		- `GetBones`, `GrassScatterer`, `Poses` - helper classes
	- `Shaders` - compute and fragment shaders used for event simulation
		-  Compute shaders:
			- `common.hlsl` - shared methods
			- `Imperfection` - Initial generator for threshold variation + noise rate combined texture
			- `FrameCapture` - Packs color, depth, and ID Segmentation map into one structured compute buffer for simultaneous readout by CPU
			- `DVCalc` - Most important shader- calculates diff, low pass filter, leak, photoreceptor noise, into an event texture
		- ObjectIdDepth + feature - Custom render feature for generating global textures for depth and a uint hash based segmentation mask using each DVObject's internal ID value on each pixel that it appears, no AA
	- `Util` - utility classes used the the other scripts
	- `DVConfig` - Main config file, most all settings are stored and configurable in there
	- `DVManager` - Scene orchestrator, handles everything in the scene and the actual simulation process itself
	- `DVPermutationGroup` - Marker for parent gameobjects containing multiple child permutation gameobjects, makes more sense if you just read the source 
	- `SceneManager` - Handles actual Unity scene objects 
	- `postprocessoutput.py` - post processes all output data
		- converts binary event stream object into event npz file
		- converts separate color frame hdrs into sdr mp4 video with auto exposure and linear color transformation
		- converts data frame hdrs into lossess 16 bit ffv1 mkv for compression of temporally similar data across frames
		- filters and processes raw bounding box output json data
		- logs all console output to `postprocessoutput.log`

## Output
 All output goes into `Assets/.Output/Permutations/permutation_code/camera name/.`
 - `bboxes.json` - 2D screen space object bounds
```
[  
      {
        "time": time in ns,
        "bboxes": [ {
                "id": object ID in unity,
                "label": object name in unity,
                "min": [ x, y ],
                "max": [ x, y ],
                "dist": distance from the sensor,
                "visible": is this object visible at this time?
            }, 
            ...other objects... 
        ]
    },
    ...other timestamps... 
]
```
- `cameraroute.json`
```
[
    [
        time in ns,  
        [ x, y, z ], position
        [ x, y, z, w ] rotation quaternion
    ],
    ...other timestamps...
]
```
- `color.mp4` - RGB output video
- `data.mkv` - ffv1 mkv- read with `/Python/events/mkvreadback.py`
	- R channel - depth * 1000, then quantized to ints
	- G channel - integer object IDS - mapped from `Assets/.Output/allids.json`
- `events.npz` - load with `np.load .. [arr_0]` - just an array of event objects
```python
event_dtype = np.dtype([
    ("x", np.uint16),
    ("y", np.uint16),
    ("t", np.uint64),
    ("p", bool),
], align=False)
```
- `meta.json`
	- Metadata regarding simulation run, should be self explanatory to read
	- Also exports current configuration as defined in DVConfig.cs

## To Run:
### For manual single test simulations
- Enable `PermZeroTestRun` in the manager object
- Move all desired DVObjects to the top of their respective permutation group parent objects
- Start the scene
- Scene will auto stop on the completion of the armature animation, or can be manually interrupted by stopping the scene

**To make a new sensor/camera:** 
1. Duplicate a preexisting camera object 
	1. Or make a new camera, then attach the `DVS` component to it
2. Configure the camera's motion
	1. Remove unwanted `DVMotion` components
	2. Add desired `DVMotion` components
	3. For static cameras, just remove all components other than `Camera` and `DVS`
3. Add the camera to the Manager object's `Sensors` list (this may be automated in the future)

**To import a new skeleton animation** (captury only for now)
- Copy captury out folder into `Python/motion/captury/input` 
- Run `exportall.bat`, or manually `py export_armature.py <input-folder-name>`
- Make a new empty object in the `Animation` permutation group in Unity with a `DVO_PoseAnim` component
	- Set `Anim Obj Asset Path` accordingly. Look at a preexisting animation object for reference
	- For captury recordings, `Scale=1` should be good
	- If auto-grounding is disabled, the offset will be used, otherwise the target armature will auto snap its feet to the ground
	- Set `Target Armature Type=CPTY` for captury recordings

**To add new objects in other permutation groups**
Reference the preexisting objects in those folders for guidance
- All Environments use `DVO_Environment` 
- All lighting objects use `DVO_Lighting`
- All weather objects use `DVO_Weather`
- Read `!! armature requirement` and `!! to add new armatures` in `Assets/Assets/humans/` if you want to add your own armatures
	- Any rigged mesh using that armature MUST use the EXACT armature that the `DVO_Armature` object is defined with

### For full permutation runs
- not implemented yet

> TODO: more in depth readme TBD