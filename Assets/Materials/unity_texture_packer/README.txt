Unity URP Texture Packer

Run pack_unity_textures.bat.
Drag a texture file into the console at each prompt, then press Enter.
Press Enter on an empty prompt to skip that map.

Outputs:
- *_BaseMap.png: RGB base color + alpha opacity
- *_MaskMap.png: R metallic, G ambient occlusion, B unused, A smoothness
- *_Normal.png: optional converted normal map
- *_Height.png: optional converted height map

Missing-channel defaults:
- Base color: white
- Opacity: opaque
- Metallic: 0
- Ambient occlusion: 1
- Smoothness: 0.5

All supplied textures are resized to the dimensions of the first supplied texture.
For Unity, disable sRGB on MaskMap and Height. Set Normal texture type to Normal map.
