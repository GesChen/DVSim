"""
Reconstruct a ReplicaCAD scene in Blender from a *.scene_instance.json file.

Run in Blender UI:
    1. Set CONFIG_PATH below.
    2. Open this file in Blender's Scripting workspace and Run Script.

Run from a shell:
    blender --background --python reconstruct_replicacad.py -- \
        ".../configs/scenes/apt_0.scene_instance.json" \
        --save ".../apt_0.blend" \
        --fbx ".../apt_0.fbx"

No third-party Python packages are required. The script supports:
- stage instances
- rigid object instances
- uniform/non-uniform template scaling
- Habitat [w, x, y, z] quaternions
- Habitat Y-up -> Blender Z-up conversion
- basic URDF articulated objects, including link/joint hierarchy
- optional .blend and FBX output

Lighting and physics metadata are intentionally not recreated.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import bpy
from mathutils import Matrix, Quaternion, Vector


# Used when running from Blender's Text Editor without command-line arguments.
CONFIG_PATH = r""
SAVE_BLEND_PATH = r""
EXPORT_FBX_PATH = r""

CLEAR_SCENE = True
IMPORT_ARTICULATED = True
STRICT_MISSING_ASSETS = False


# glTF is Y-up. Blender's glTF importer converts it to Z-up using this basis.
# ReplicaCAD transforms must undergo the same basis conversion.
HABITAT_TO_BLENDER = Matrix.Rotation(math.radians(90.0), 4, "X")


@dataclass
class ImportResult:
    root: bpy.types.Object
    objects: list[bpy.types.Object]


@dataclass
class UrdfJoint:
    name: str
    joint_type: str
    parent: str
    child: str
    origin: Matrix
    axis: Vector
    value: float = 0.0


def log(message: str) -> None:
    print(f"[ReplicaCAD] {message}")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_cli() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("config", nargs="?", default=CONFIG_PATH)
    parser.add_argument("--save", default=SAVE_BLEND_PATH)
    parser.add_argument("--fbx", default=EXPORT_FBX_PATH)
    parser.add_argument("--keep-scene", action="store_true")
    parser.add_argument("--skip-articulated", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def find_dataset_root(config_path: Path) -> Path:
    config_path = config_path.resolve()
    candidates = [config_path.parent, *config_path.parents]

    for p in candidates:
        if (p / "replicaCAD.scene_dataset_config.json").is_file():
            return p

    # Standard layout: <root>/configs/scenes/file.scene_instance.json
    for p in candidates:
        if p.name == "configs":
            return p.parent

    raise FileNotFoundError(
        "Could not find the ReplicaCAD dataset root. Expected "
        "replicaCAD.scene_dataset_config.json above the scene config."
    )


def clear_scene() -> None:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    # Remove unused data left by prior imports.
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def ensure_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(collection)
    return collection


def link_only_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)


def snapshot_objects() -> set[bpy.types.Object]:
    return set(bpy.data.objects)


def imported_since(before: set[bpy.types.Object]) -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj not in before]


def make_root(name: str, collection: bpy.types.Collection) -> bpy.types.Object:
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.25
    collection.objects.link(root)
    return root


def parent_imported_roots(objects: Iterable[bpy.types.Object], parent: bpy.types.Object) -> None:
    imported_set = set(objects)
    for obj in imported_set:
        if obj.parent not in imported_set:
            obj.parent = parent
            obj.matrix_parent_inverse = Matrix.Identity(4)


def import_mesh_file(path: Path, name: str, collection: bpy.types.Collection) -> ImportResult:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    before = snapshot_objects()
    ext = path.suffix.lower()

    if ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(path))
        else:
            bpy.ops.import_scene.obj(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext == ".dae":
        bpy.ops.wm.collada_import(filepath=str(path))
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path))
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=str(path))
    else:
        raise ValueError(f"Unsupported mesh format: {path}")

    objects = imported_since(before)
    root = make_root(name, collection)
    parent_imported_roots(objects, root)

    for obj in objects:
        link_only_to_collection(obj, collection)

    return ImportResult(root=root, objects=objects)


def habitat_vector(v: Iterable[float]) -> Vector:
    x, y, z = (float(n) for n in v)
    return (HABITAT_TO_BLENDER @ Vector((x, y, z, 1.0))).to_3d()


def habitat_rotation(q: Iterable[float]) -> Matrix:
    w, x, y, z = (float(n) for n in q)
    r_h = Quaternion((w, x, y, z)).normalized().to_matrix().to_4x4()
    return HABITAT_TO_BLENDER @ r_h @ HABITAT_TO_BLENDER.inverted()


def habitat_transform(instance: dict[str, Any]) -> Matrix:
    translation = habitat_vector(instance.get("translation", (0.0, 0.0, 0.0)))
    rotation = habitat_rotation(instance.get("rotation", (1.0, 0.0, 0.0, 0.0)))

    scale_value = instance.get("scale")
    if scale_value is None:
        s = float(instance.get("uniform_scale", 1.0))
        scale = Vector((s, s, s))
    elif isinstance(scale_value, (int, float)):
        s = float(scale_value)
        scale = Vector((s, s, s))
    else:
        sx, sy, sz = (float(n) for n in scale_value)
        # Scale axes are transformed by the same Y-up -> Z-up basis.
        scale = Vector((sx, sz, sy))

    return Matrix.Translation(translation) @ rotation @ Matrix.Diagonal((*scale, 1.0))


def normalize_handle(handle: str) -> str:
    return handle.replace("\\", "/").strip().removesuffix(".json")


def candidate_template_configs(root: Path, handle: str, kind: str) -> list[Path]:
    h = normalize_handle(handle)
    basename = Path(h).name
    suffix = "stage_config.json" if kind == "stage" else "object_config.json"

    candidates = [
        root / "configs" / f"{h}.{suffix}",
        root / "configs" / kind.replace("stage", "stages").replace("object", "objects") / f"{basename}.{suffix}",
        root / f"{h}.{suffix}",
    ]

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(p.resolve() for p in candidates))


def find_template_config(root: Path, handle: str, kind: str) -> Path | None:
    for path in candidate_template_configs(root, handle, kind):
        if path.is_file():
            return path

    basename = Path(normalize_handle(handle)).name
    pattern = f"{basename}.{'stage_config.json' if kind == 'stage' else 'object_config.json'}"
    matches = list((root / "configs").rglob(pattern))
    return matches[0].resolve() if matches else None


def resolve_path(value: str, bases: Iterable[Path], extensions: Iterable[str] = ()) -> Path | None:
    raw = Path(value.replace("\\", "/"))
    variants = [raw]
    if not raw.suffix:
        variants.extend(raw.with_suffix(ext) for ext in extensions)

    for base in bases:
        for variant in variants:
            path = variant if variant.is_absolute() else base / variant
            if path.is_file():
                return path.resolve()
    return None


def resolve_rigid_asset(root: Path, handle: str, kind: str) -> tuple[Path, dict[str, Any]]:
    config_path = find_template_config(root, handle, kind)
    template: dict[str, Any] = {}

    if config_path:
        template = load_json(config_path)
        asset_value = (
            template.get("render_asset")
            or template.get("render_asset_handle")
            or template.get("asset")
        )
        if asset_value:
            asset = resolve_path(
                str(asset_value),
                (config_path.parent, root),
                (".glb", ".gltf", ".obj", ".ply"),
            )
            if asset:
                return asset, template

    h = normalize_handle(handle)
    basename = Path(h).name
    search_dirs = [root, root / ("stages" if kind == "stage" else "objects")]
    direct = resolve_path(h, search_dirs, (".glb", ".gltf", ".obj", ".ply"))
    if direct:
        return direct, template

    for ext in (".glb", ".gltf", ".obj", ".ply"):
        matches = list(root.rglob(basename + ext))
        if matches:
            return matches[0].resolve(), template

    raise FileNotFoundError(f"Could not resolve {kind} template '{handle}'")


def template_scale_matrix(template: dict[str, Any]) -> Matrix:
    scale_value = template.get("scale", template.get("uniform_scale", 1.0))
    if isinstance(scale_value, (int, float)):
        s = float(scale_value)
        return Matrix.Diagonal((s, s, s, 1.0))

    sx, sy, sz = (float(n) for n in scale_value)
    return Matrix.Diagonal((sx, sz, sy, 1.0))


def import_rigid_instance(
    root: Path,
    instance: dict[str, Any],
    kind: str,
    index: int,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    handle = instance["template_name"]
    asset_path, template = resolve_rigid_asset(root, handle, kind)
    name = f"{kind}_{index:03d}_{Path(handle).name}"
    result = import_mesh_file(asset_path, name, collection)

    result.root.matrix_world = habitat_transform(instance) @ template_scale_matrix(template)
    result.root["replicacad_template"] = handle
    result.root["replicacad_motion_type"] = instance.get("motion_type", "")
    result.root["replicacad_asset"] = str(asset_path)
    return result.root


def parse_xyz(text: str | None, default=(0.0, 0.0, 0.0)) -> Vector:
    if not text:
        return Vector(default)
    return Vector(tuple(float(x) for x in text.split()))


def rpy_matrix(rpy: Vector) -> Matrix:
    # URDF fixed-axis roll-pitch-yaw: Rz(yaw) @ Ry(pitch) @ Rx(roll)
    rx = Matrix.Rotation(rpy.x, 4, "X")
    ry = Matrix.Rotation(rpy.y, 4, "Y")
    rz = Matrix.Rotation(rpy.z, 4, "Z")
    return rz @ ry @ rx


def urdf_origin_matrix(element: ET.Element | None) -> Matrix:
    if element is None:
        return Matrix.Identity(4)
    xyz = parse_xyz(element.get("xyz"))
    rpy = parse_xyz(element.get("rpy"))
    return Matrix.Translation(xyz) @ rpy_matrix(rpy)


def resolve_urdf(root: Path, handle: str) -> Path | None:
    h = normalize_handle(handle)
    basename = Path(h).name

    direct = resolve_path(h, (root, root / "urdf"), (".urdf",))
    if direct:
        return direct

    matches = list((root / "urdf").rglob(basename + ".urdf")) if (root / "urdf").exists() else []
    return matches[0].resolve() if matches else None


def resolve_urdf_mesh(urdf_path: Path, filename: str, dataset_root: Path) -> Path | None:
    value = filename.replace("package://", "").replace("\\", "/")
    return resolve_path(value, (urdf_path.parent, dataset_root, dataset_root / "urdf"))


def joint_motion_matrix(joint: UrdfJoint) -> Matrix:
    if joint.joint_type in {"revolute", "continuous"}:
        return Matrix.Rotation(joint.value, 4, joint.axis.normalized())
    if joint.joint_type == "prismatic":
        return Matrix.Translation(joint.axis.normalized() * joint.value)
    return Matrix.Identity(4)


def parse_joint_values(instance: dict[str, Any], joints: list[UrdfJoint]) -> None:
    values = instance.get("joint_positions", instance.get("joint_pose"))
    if values is None:
        return

    if isinstance(values, dict):
        for joint in joints:
            if joint.name in values:
                joint.value = float(values[joint.name])
    elif isinstance(values, list):
        movable = [j for j in joints if j.joint_type not in {"fixed", "floating"}]
        for joint, value in zip(movable, values):
            joint.value = float(value)


def compute_link_transforms(link_names: set[str], joints: list[UrdfJoint]) -> tuple[dict[str, Matrix], str]:
    child_names = {j.child for j in joints}
    roots = sorted(link_names - child_names)
    root_link = roots[0] if roots else sorted(link_names)[0]

    children: dict[str, list[UrdfJoint]] = {}
    for joint in joints:
        children.setdefault(joint.parent, []).append(joint)

    transforms = {root_link: Matrix.Identity(4)}
    stack = [root_link]
    while stack:
        parent = stack.pop()
        for joint in children.get(parent, []):
            transforms[joint.child] = transforms[parent] @ joint.origin @ joint_motion_matrix(joint)
            stack.append(joint.child)

    for name in link_names:
        transforms.setdefault(name, Matrix.Identity(4))
    return transforms, root_link


def aggregate_urdf_com(
    robot: ET.Element,
    link_transforms: dict[str, Matrix],
) -> Vector:
    weighted = Vector((0.0, 0.0, 0.0))
    total_mass = 0.0

    for link in robot.findall("link"):
        inertial = link.find("inertial")
        if inertial is None:
            continue
        mass_el = inertial.find("mass")
        if mass_el is None or mass_el.get("value") is None:
            continue
        mass = float(mass_el.get("value"))
        local_com = urdf_origin_matrix(inertial.find("origin")).translation
        world_com = link_transforms[link.get("name")] @ local_com
        weighted += world_com * mass
        total_mass += mass

    return weighted / total_mass if total_mass > 0.0 else Vector((0.0, 0.0, 0.0))


def import_urdf_instance(
    dataset_root: Path,
    instance: dict[str, Any],
    index: int,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    handle = instance["template_name"]
    urdf_path = resolve_urdf(dataset_root, handle)
    if urdf_path is None:
        raise FileNotFoundError(f"Could not resolve URDF template '{handle}'")

    robot = ET.parse(urdf_path).getroot()
    links = {link.get("name"): link for link in robot.findall("link") if link.get("name")}
    joints: list[UrdfJoint] = []

    for joint_el in robot.findall("joint"):
        parent_el = joint_el.find("parent")
        child_el = joint_el.find("child")
        if parent_el is None or child_el is None:
            continue
        axis_el = joint_el.find("axis")
        axis = parse_xyz(axis_el.get("xyz") if axis_el is not None else None, (1.0, 0.0, 0.0))
        joints.append(
            UrdfJoint(
                name=joint_el.get("name", "joint"),
                joint_type=joint_el.get("type", "fixed"),
                parent=parent_el.get("link"),
                child=child_el.get("link"),
                origin=urdf_origin_matrix(joint_el.find("origin")),
                axis=axis,
            )
        )

    parse_joint_values(instance, joints)
    link_transforms, root_link_name = compute_link_transforms(set(links), joints)

    assembly = make_root(f"articulated_{index:03d}_{Path(handle).name}", collection)
    assembly["replicacad_template"] = handle
    assembly["replicacad_urdf"] = str(urdf_path)

    link_roots: dict[str, bpy.types.Object] = {}
    for link_name in links:
        link_root = make_root(link_name, collection)
        link_root.parent = assembly
        link_root.matrix_parent_inverse = Matrix.Identity(4)
        link_root.matrix_local = HABITAT_TO_BLENDER @ link_transforms[link_name] @ HABITAT_TO_BLENDER.inverted()
        link_roots[link_name] = link_root

    # Imported glTF/OBJ geometry is already converted to Blender's coordinates.
    # Convert only each URDF visual's origin and scale.
    for link_name, link_el in links.items():
        for visual_index, visual in enumerate(link_el.findall("visual")):
            geometry = visual.find("geometry")
            mesh_el = geometry.find("mesh") if geometry is not None else None
            if mesh_el is None or not mesh_el.get("filename"):
                continue

            mesh_path = resolve_urdf_mesh(urdf_path, mesh_el.get("filename"), dataset_root)
            if mesh_path is None:
                log(f"Missing URDF mesh: {mesh_el.get('filename')}")
                continue

            imported = import_mesh_file(
                mesh_path,
                f"{link_name}_visual_{visual_index:02d}",
                collection,
            )
            imported.root.parent = link_roots[link_name]
            imported.root.matrix_parent_inverse = Matrix.Identity(4)

            visual_origin = urdf_origin_matrix(visual.find("origin"))
            converted_origin = HABITAT_TO_BLENDER @ visual_origin @ HABITAT_TO_BLENDER.inverted()

            mesh_scale = parse_xyz(mesh_el.get("scale"), (1.0, 1.0, 1.0))
            converted_scale = Matrix.Diagonal((mesh_scale.x, mesh_scale.z, mesh_scale.y, 1.0))
            imported.root.matrix_local = converted_origin @ converted_scale

    instance_matrix = habitat_transform(instance)
    if instance.get("translation_origin", "").upper() == "COM":
        local_com_h = aggregate_urdf_com(robot, link_transforms)
        local_com_b = (HABITAT_TO_BLENDER @ Vector((*local_com_h, 1.0))).to_3d()
        # Place the local COM at the requested instance translation.
        instance_matrix = instance_matrix @ Matrix.Translation(-local_com_b)

    assembly.matrix_world = instance_matrix
    return assembly


def import_scene(config_path: Path, args: argparse.Namespace) -> None:
    dataset_root = find_dataset_root(config_path)
    scene_data = load_json(config_path)

    log(f"Config: {config_path}")
    log(f"Dataset root: {dataset_root}")

    if CLEAR_SCENE and not args.keep_scene:
        clear_scene()

    master = ensure_collection(f"ReplicaCAD_{config_path.stem}")
    stage_collection = ensure_collection("Stage", master)
    rigid_collection = ensure_collection("Rigid Objects", master)
    articulated_collection = ensure_collection("Articulated Objects", master)

    failures: list[str] = []

    stage = scene_data.get("stage_instance")
    if stage:
        try:
            import_rigid_instance(dataset_root, stage, "stage", 0, stage_collection)
            log(f"Imported stage: {stage.get('template_name')}")
        except Exception as exc:
            failures.append(f"stage {stage.get('template_name')}: {exc}")
            log(f"FAILED stage {stage.get('template_name')}: {exc}")

    rigid_instances = scene_data.get("object_instances", [])
    for index, instance in enumerate(rigid_instances):
        try:
            import_rigid_instance(dataset_root, instance, "object", index, rigid_collection)
        except Exception as exc:
            failures.append(f"object {instance.get('template_name')}: {exc}")
            log(f"FAILED object {instance.get('template_name')}: {exc}")

    articulated_instances = scene_data.get("articulated_object_instances", [])
    if IMPORT_ARTICULATED and not args.skip_articulated:
        for index, instance in enumerate(articulated_instances):
            try:
                import_urdf_instance(dataset_root, instance, index, articulated_collection)
            except Exception as exc:
                failures.append(f"articulated {instance.get('template_name')}: {exc}")
                log(f"FAILED articulated {instance.get('template_name')}: {exc}")

    bpy.context.view_layer.update()

    if args.save:
        save_path = Path(args.save).expanduser().resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(save_path))
        log(f"Saved Blend: {save_path}")

    if args.fbx:
        fbx_path = Path(args.fbx).expanduser().resolve()
        fbx_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.fbx(
            filepath=str(fbx_path),
            use_selection=False,
            apply_unit_scale=True,
            bake_space_transform=False,
            path_mode="COPY",
            embed_textures=True,
            add_leaf_bones=False,
        )
        log(f"Exported FBX: {fbx_path}")

    log(
        f"Finished: {len(rigid_instances)} rigid instances, "
        f"{len(articulated_instances)} articulated instances, "
        f"{len(failures)} failures."
    )

    if failures:
        print("\n[ReplicaCAD] Failures:")
        for failure in failures:
            print("  -", failure)
        if args.strict or STRICT_MISSING_ASSETS:
            raise RuntimeError(f"Scene reconstruction completed with {len(failures)} failures")


def main() -> None:
    args = parse_cli()
    if not args.config:
        raise ValueError(
            "No scene config supplied. Set CONFIG_PATH near the top of the script "
            "or pass a config after '--'."
        )

    config_path = Path(args.config).expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(config_path)

    import_scene(config_path, args)


if __name__ == "__main__":
    main()
