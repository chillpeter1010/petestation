"""Author a baseball material variant of the CC0 Quaternius skinned male.

No renderer, images, screenshots or source Statcast data are touched.
The generated glTF is editable in any glTF DCC; GLB is the same runtime asset.
"""
import copy
import hashlib
import json
import struct
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "output/ballpark/f2-character-source-v1"
RUNTIME = ROOT / "frontend/assets/ballpark/characters3d"


def build():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    original = json.loads((SOURCE / "original-male.gltf").read_text(encoding="utf-8"))
    gltf = copy.deepcopy(original)
    data = bytearray((SOURCE / original["buffers"][0]["uri"]).read_bytes())
    types = {5121: "u1", 5123: "<u2", 5126: "<f4"}
    sizes = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

    def values(index):
        a = original["accessors"][index]
        view = original["bufferViews"][a["bufferView"]]
        dtype = np.dtype(types[a["componentType"]])
        n = sizes[a["type"]]
        return np.ndarray((a["count"], n), dtype=dtype, buffer=data,
                          offset=view.get("byteOffset", 0)+a.get("byteOffset", 0),
                          strides=(view.get("byteStride", n*dtype.itemsize), dtype.itemsize)).copy()

    def append(array, component, kind, target=None):
        while len(data) % 4:
            data.append(0)
        view = {"buffer": 0, "byteOffset": len(data), "byteLength": array.nbytes}
        if target:
            view["target"] = target
        gltf["bufferViews"].append(view)
        data.extend(array.tobytes())
        a = {"bufferView": len(gltf["bufferViews"])-1, "componentType": component,
             "count": len(array), "type": kind}
        if component == 5126:
            a["min"] = array.min(axis=0).reshape(-1).tolist()
            a["max"] = array.max(axis=0).reshape(-1).tolist()
        gltf["accessors"].append(a)
        return len(gltf["accessors"])-1

    # Keep only the three available colour textures. Optional source normal-map
    # URI mismatches are deliberately not carried into the runtime export.
    image_names = ["T_Hair_1_BaseColor.png", "T_Eye_Brown.png", "T_Superhero_Male_Dark.png"]
    gltf["images"] = [{"uri": n, "mimeType": "image/png"} for n in image_names]
    gltf["textures"] = [{"source": i} for i in range(3)]
    gltf["materials"] = [
        {"name": n, "pbrMetallicRoughness": {"baseColorTexture": {"index": i}, "metallicFactor": 0, "roughnessFactor": .76}, "doubleSided": True}
        for i, n in enumerate(["hair", "eyes", "skin"])
    ]
    for name, color in [("uniform_jersey", [.94, .95, .94, 1]), ("uniform_pants", [.92, .93, .92, 1]),
                        ("socks", [.025, .06, .10, 1]), ("cleats", [.025, .03, .04, 1])]:
        gltf["materials"].append({"name": name, "pbrMetallicRoughness": {"baseColorFactor": color, "metallicFactor": 0, "roughnessFactor": .9}, "doubleSided": True})
    body = gltf["meshes"][-1]["primitives"][0]
    attrs = {k: v for k, v in body["attributes"].items() if not k.startswith("COLOR")}
    pos = values(attrs["POSITION"])
    triangles = values(body["indices"]).reshape(-1, 3)
    centers = pos[triangles].mean(axis=1)
    material_indices = []
    for x, y, z in centers:
        if y < .15:
            material = 6
        elif y < .33:
            material = 5
        elif y < .99:
            material = 4
        elif y > 1.56 or abs(x) > .53:
            material = 2
        else:
            material = 3
        # A cuff is a band of the sleeve's existing faces, never a rigid ring
        # following only one forearm bone beside a blended skinned sleeve.
        if material == 3 and abs(x) > .48:
            material = 10
        material_indices.append(material)
    material_indices = np.array(material_indices)
    # Derive the garment from the same indexed mother surface. Shared seam
    # vertices retain EXACTLY the same positions, joints and weights on both
    # skin and cloth primitives; no nearest-neighbour cylinder skin transfer.
    dressed = pos.copy()
    for i, (x, y, z) in enumerate(pos):
        if .33 < y < .99:
            hip = np.clip((y-.74)/.13, 0, 1)
            cx = (.114 if x >= 0 else -.114)*(1-hip)
            width = (.072 + .036*np.clip((y-.33)/.45,0,1))*(1-hip)+.195*hip
            depth = (.082 + .028*np.clip((y-.33)/.45,0,1))*(1-hip)+.143*hip
            radius = np.sqrt(((x-cx)/width)**2+(z/depth)**2)
            blend = min(1, (y-.33)/.065)
            if radius > 1e-5:
                scale = 1 + blend*(np.clip(1/radius,.88,1.32)-1)
                dressed[i,0] = cx+(x-cx)*scale
                dressed[i,2] = z*scale
        elif .99 <= y < 1.56 and abs(x) < .32:
            width = np.interp(y,[.99,1.16,1.36,1.46,1.56],[.208,.218,.267,.25,.105])
            depth = np.interp(y,[.99,1.16,1.36,1.46,1.56],[.155,.178,.195,.175,.105])
            radius = np.sqrt((x/width)**2+(z/depth)**2)
            blend = min(1,(1.56-y)/.06)*min(1,(.32-abs(x))/.04)
            if radius > 1e-5:
                scale = 1 + blend*(np.clip(1/radius,1,1.85)-1)
                dressed[i,0], dressed[i,2] = x*scale,z*scale
        elif 1.25 < y < 1.55 and .32 <= abs(x) < .55:
            blend = min(1,(.55-abs(x))/.05)
            dressed[i,1] += (y-1.415)*.22*blend
            dressed[i,2] *= 1+.22*blend
    normals = np.zeros_like(dressed)
    a,b,c = (dressed[triangles[:,i]] for i in range(3))
    face_normals = np.cross(b-a,c-a)
    for corner in range(3):
        np.add.at(normals,triangles[:,corner],face_normals)
    normals /= np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-9)
    attrs['POSITION'] = append(dressed.astype('<f4'),5126,'VEC3',34962)
    attrs['NORMAL'] = append(normals.astype('<f4'),5126,'VEC3',34962)
    def pieces(materials):
        return [{'attributes':attrs,'indices':append(triangles[material_indices==m].astype('<u2').reshape(-1,1),5123,'SCALAR',34963),'material':m} for m in materials]
    gltf['meshes'][-1]['name']='BaseballMaleSkinned'
    # Discard the bare-foot triangles. Cleats below are actual closed footwear,
    # not a dark material over the source toes.
    gltf['meshes'][-1]['primitives']=pieces([2,5])
    gltf['meshes'].append({'name':'IndependentBaseballGarments','primitives':pieces([3,4,10])})
    gltf['nodes'].append({'name':'IndependentBaseballGarments','mesh':len(gltf['meshes'])-1,'skin':0})
    armature=next(n for n in gltf['nodes'] if n.get('name')=='Armature')
    armature.setdefault('children',[]).append(len(gltf['nodes'])-1)
    joints = {gltf['nodes'][n]['name']: i for i,n in enumerate(gltf['skins'][0]['joints'])}
    for name,color in [('cleat_outsole',[.035,.045,.06,1]),('cleat_laces',[.8,.83,.85,1]),('cleat_studs',[.30,.34,.38,1])]:
        gltf['materials'].append({'name':name,'pbrMetallicRoughness':{'baseColorFactor':color,'metallicFactor':.15 if name=='cleat_studs' else 0,'roughnessFactor':.65}})
    gltf['materials'].append({'name':'uniform_cuff','pbrMetallicRoughness':{'baseColorFactor':[.05,.15,.20,1],'metallicFactor':0,'roughnessFactor':.9},'doubleSided':True})

    def rigid_skin_mesh(name,vertices,faces,material,joint):
        vertices=np.asarray(vertices,dtype='<f4');faces=np.asarray(faces,dtype='<u2')
        normal=np.zeros_like(vertices)
        fn=np.cross(vertices[faces[:,1]]-vertices[faces[:,0]],vertices[faces[:,2]]-vertices[faces[:,0]])
        for k in range(3):np.add.at(normal,faces[:,k],fn)
        normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-9)
        ji=np.zeros((len(vertices),4),dtype='u1');ji[:,0]=joints[joint]
        we=np.zeros((len(vertices),4),dtype='<f4');we[:,0]=1
        attributes={'POSITION':append(vertices,5126,'VEC3',34962),'NORMAL':append(normal,5126,'VEC3',34962),
                    'JOINTS_0':append(ji,5121,'VEC4',34962),'WEIGHTS_0':append(we,5126,'VEC4',34962)}
        gltf['meshes'].append({'name':name,'primitives':[{'attributes':attributes,'indices':append(faces.reshape(-1,1),5123,'SCALAR',34963),'material':material}]})
        gltf['nodes'].append({'name':name,'mesh':len(gltf['meshes'])-1,'skin':0})
        armature['children'].append(len(gltf['nodes'])-1)

    def loft(rings):
        v=np.asarray(rings);n=v.shape[1];f=[]
        for r in range(len(rings)-1):
            for k in range(n):
                a=r*n+k;b=r*n+(k+1)%n;c=b+n;d=a+n
                f.extend([[a,b,c],[a,c,d]])
        for k in range(1,n-1):f.extend([[0,k+1,k],[(len(rings)-1)*n,(len(rings)-1)*n+k,(len(rings)-1)*n+k+1]])
        return v.reshape(-1,3),f

    for side,sign in [('l',1),('r',-1)]:
        cx=sign*.131;bone='foot_'+side
        # Cross sections describe a broad closed toe box, raised heel/tongue
        # and an ankle collar. All vertices use the SAME foot joint bind frame.
        profile=[(-.158,.012,.07),(-.14,.056,.155),(-.075,.063,.164),(-.015,.064,.11),(.065,.064,.073),(.126,.052,.060),(.151,.018,.044)]
        rings=[[[cx+width*np.cos(t),.018+(top-.018)*(np.sin(t)+1)/2,z] for t in np.linspace(0,2*np.pi,16,endpoint=False)] for z,width,top in profile]
        v,f=loft(rings);rigid_skin_mesh('cleat-upper-'+side,v,f,6,bone)
        outline=[(cx-w,z) for z,w,_ in profile]+[(cx+w,z) for z,w,_ in reversed(profile)]
        v,f=loft([[[x,y,z] for x,z in outline] for y in [-.002,.021]])
        rigid_skin_mesh('cleat-outsole-'+side,v,f,7,bone)
        # Separate lace cords over the instep; visible volume, not a texture.
        for k,z in enumerate([-.033,-.008,.017,.042]):
            y=float(np.interp(z,[p[0] for p in profile],[p[2] for p in profile]))+.004
            a=np.array([cx-.033,y,z-.008]);b=np.array([cx+.033,y,z+.008]);d=(b-a);d/=np.linalg.norm(d)
            u=np.cross(d,[0,1,0]);u/=np.linalg.norm(u);w=np.cross(d,u)
            v,f=loft([[p+.0035*(u*np.cos(t)+w*np.sin(t)) for t in np.linspace(0,2*np.pi,6,endpoint=False)] for p in [a,b]])
            rigid_skin_mesh('cleat-lace-'+side+'-'+str(k),v,f,8,bone)
        for k,(x,z) in enumerate([(-.032,-.115),(.032,-.115),(-.037,-.065),(.037,-.065),(-.036,.035),(.036,.035),(-.026,.105),(.026,.105)]):
            v,f=loft([[[cx+x+radius*np.cos(t),y,z+radius*np.sin(t)] for t in np.linspace(0,-2*np.pi,6,endpoint=False)] for y,radius in [(-.012,.006),(.001,.009)]])
            rigid_skin_mesh('cleat-stud-'+side+'-'+str(k),v,f,9,bone)
    # Explicit neutral ready and subtle breathing clips, not real-player motion.
    pelvis = next(i for i, n in enumerate(gltf["nodes"]) if n.get("name") == "pelvis")
    rest = np.array(gltf["nodes"][pelvis]["translation"], dtype="<f4")
    t = append(np.array([[0], [.6], [1.2], [1.8], [2.4]], dtype="<f4"), 5126, "SCALAR")
    gltf["animations"] = []
    for name, amplitude in [("ready", 0), ("idle", .003)]:
        poses = np.array([rest + [0, 0, amplitude*v] for v in [0, 1, 0, -1, 0]], dtype="<f4")
        output = append(poses, 5126, "VEC3")
        gltf["animations"].append({"name": name, "samplers": [{"input": t, "output": output, "interpolation": "LINEAR"}],
                                   "channels": [{"sampler": 0, "target": {"node": pelvis, "path": "translation"}}]})
    gltf["asset"]["generator"] = "Petehub build_replay_character.py v1; CC0 Quaternius source"
    gltf["asset"]["copyright"] = "Quaternius CC0 1.0; Petehub material segmentation/idle authoring"
    gltf.setdefault("extras", {}).update({"kind": "generic_baseball_rig_not_player_scan", "base_height_m": 1.819586383,
        "source_url": "https://quaternius.itch.io/universal-base-characters", "license": "CC0-1.0",
        "pose_recipe": "frontend/components/charts/replay3d/createReplayActors.ts"})
    gltf["buffers"] = [{"uri": "actor-base-v1.bin", "byteLength": len(data)}]
    (SOURCE / "actor-base-v1.bin").write_bytes(data)
    (SOURCE / "actor-base-v1.gltf").write_text(json.dumps(gltf, separators=(",", ":")), encoding="utf-8")
    # GLB packs the identical colour images without modifying their bytes.
    runtime = copy.deepcopy(gltf)
    for image in runtime["images"]:
        while len(data) % 4:
            data.append(0)
        content = (SOURCE / image.pop("uri")).read_bytes()
        runtime["bufferViews"].append({"buffer": 0, "byteOffset": len(data), "byteLength": len(content)})
        image["bufferView"] = len(runtime["bufferViews"])-1
        data.extend(content)
    while len(data) % 4:
        data.append(0)
    runtime["buffers"] = [{"byteLength": len(data)}]
    js = json.dumps(runtime, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    glb = struct.pack('<III', 0x46546c67, 2, 12+8+len(js)+8+len(data)) + struct.pack('<II', len(js), 0x4e4f534a) + js + struct.pack('<II', len(data), 0x004e4942) + data
    target = RUNTIME / "actor-base-v1.glb"
    target.write_bytes(glb)
    manifest = {"version": "replay_actor_v1", "author": "Quaternius; Petehub adaptations", "license": "CC0-1.0",
        "source_url": "https://quaternius.itch.io/universal-base-characters", "license_file": str((SOURCE/'LICENSE-Quaternius.txt').relative_to(ROOT)),
        "editable_source": str((SOURCE/'actor-base-v1.gltf').relative_to(ROOT)), "builder": str(Path(__file__).relative_to(ROOT)),
        "runtime": str(target.relative_to(ROOT)), "sha256": hashlib.sha256(glb).hexdigest(), "bytes": len(glb),
        "triangles": sum(gltf['accessors'][p['indices']]['count']//3 for m in gltf['meshes'] for p in m['primitives']),
        "joints": len(gltf['skins'][0]['joints']), "units": "metres/Y-up/+Z-front", "clips": ["ready", "idle"],
        "source_variant": "Superhero male (free tier); not the paid Regular male", "model_scope": "generic, no player-specific face likeness",
        "modifications": "Loose jersey and cuff bands use the same indexed sleeve surface, seam positions and skin weights; no rigid cuff rings. Bare-foot faces removed; independent closed cleat uppers, outsoles, four lace cords and eight studs per foot, bound to the respective foot joint. Collar and placket piping in editable TypeScript equipment recipe. Preserve corrected palm-socket grip and generic ready/idle; no individual face or historical uniform edition.",
        "lod": "single 14k-class source mesh, no production LOD certification", "visual_status": "pending_user",
        "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.iterdir() if p.is_file()}}
    (ROOT/'data/sample/petehub_replay_actor_manifest_v1.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding="utf-8")
    print(json.dumps({k:manifest[k] for k in ['runtime','bytes','triangles','joints','clips']}))


if __name__ == "__main__":
    build()
    subprocess.run(["node", str(ROOT / "frontend/scripts/bake-replay-actors.mjs")], cwd=ROOT / "frontend", check=True)
