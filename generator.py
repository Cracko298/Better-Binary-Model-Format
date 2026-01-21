import sys, lzma, bz2, lz4.block, zstandard, zlib, struct, os, json
from Crypto.Cipher import AES, Blowfish, ChaCha20
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

encryptionList = ['aes', 'xor', 'chacha', 'blowfish']

def helpMessage():
    print(f"""
    │------------------Required Field-------------------│ │-------------------------Optional Field-------------------------│
    python {os.path.basename(__file__)} [inputObjPlyFile] [outputBbmFile] [compressionMode] [dumpModelKeys] [encryptionMode] [encryptionKey]
    """)
    os.system('pause')
    sys.exit(1)

def encryptor(byteData:bytes, encryptionKey:str=None, encryptionMode:str=None) -> bytes:
    try:
        encryptionType = encryptionMode.lower()
        if encryptionType not in encryptionList or encryptionMode is None or encryptionKey is None:
            return byteData
    except AttributeError:
        return byteData

    key_bytes = encryptionKey.encode()
    encrypted_data = None
    nonce = None
    
    if encryptionType == "aes":
        key_bytes = key_bytes.ljust(32)[:32]
        cipher = AES.new(key_bytes, AES.MODE_CBC)
        encrypted_data = cipher.encrypt(pad(byteData, AES.block_size))
        nonce = cipher.iv
    elif encryptionType == "blowfish":
        key_bytes = key_bytes[:56]
        cipher = Blowfish.new(key_bytes, Blowfish.MODE_CBC)
        encrypted_data = cipher.encrypt(pad(byteData, Blowfish.block_size))
        nonce = cipher.iv
    elif encryptionType == "chacha":
        key_bytes = key_bytes.ljust(32)[:32]
        nonce = get_random_bytes(12) 
        cipher = ChaCha20.new(key=key_bytes, nonce=nonce)
        encrypted_data = cipher.encrypt(byteData)
    else:
        key_length = len(key_bytes)
        encrypted_data = bytes([byteData[i] ^ key_bytes[i % key_length] for i in range(len(byteData))])

    if encryptionType == "chacha":
        return nonce + encrypted_data
    else:
        return encrypted_data

def compressor(byteData:bytes, compression:int=0) -> bytes:
    if compression == 0:
        return byteData
    elif compression == 1:
        return bz2.compress(byteData, 9)
    elif compression == 2:
        return lz4.block.compress(byteData)
    elif compression == 3:
        return zstandard.compress(byteData, 9)
    elif compression == 4:
        return zlib.compress(byteData, 9)
    elif compression == 5:
        return lzma.compress(byteData)
    else:
        return byteData

def optimize_mesh(vertices, faces):
    """Removes duplicate vertices and faces."""
    unique_coords = {} 
    deduped_vertices = []
    for v in vertices:
        if v not in unique_coords:
            unique_coords[v] = len(deduped_vertices)
            deduped_vertices.append(v)
    
    old_idx_to_new_idx = [unique_coords[v] for v in vertices]
    new_faces_set = set()
    final_faces = []
    
    for face in faces:
        new_face = tuple(old_idx_to_new_idx[i] for i in face)
        if len(set(new_face)) < 3:
            continue
            
        if new_face not in new_faces_set:
            new_faces_set.add(new_face)
            final_faces.append(new_face)
            
    print(f"Optimization: Reduced {len(vertices)} verts to {len(deduped_vertices)}. Reduced {len(faces)} faces to {len(final_faces)}.")
    return deduped_vertices, final_faces

def pack_vertices(vertices):
    try:
        packed_data = b"".join([struct.pack("eee", *v) for v in vertices])
        return b'\x01' + packed_data
    except Exception as e:
        print(f"Half-float packing failed (values too large?), reverting to float32: {e}")
        packed_data = b"".join([struct.pack("fff", *v) for v in vertices])
        return b'\x00' + packed_data

def pack_faces(faces, vertex_count):
    if vertex_count < 65535:
        return b'\x01' + b"".join([struct.pack("HHH", *f) for f in faces])
    else:
        return b'\x00' + b"".join([struct.pack("III", *f) for f in faces])

def parse_obj(file_path):
    vertices = []
    faces = []
    with open(file_path, "r") as file:
        for line in file:
            parts = line.split()
            if line.startswith("#") or not line or not parts:
                continue
            if parts[0] == "v":
                vertices.append(tuple(map(float, parts[1:4])))
            elif parts[0] == "f":
                face_idxs = []
                for p in parts[1:4]:
                    idx = int(p.split('/')[0])
                    face_idxs.append(idx - 1 if idx > 0 else len(vertices) + idx)
                faces.append(tuple(face_idxs))
    return vertices, faces

def parse_ply(file_path):
    vertices = []
    faces = []
    with open(file_path, "r") as file:
        header = True
        vertex_count = 0
        face_count = 0
        for line in file:
            if line.startswith("#") or not line:
                continue
            if header:
                if line.startswith("element vertex"):
                    vertex_count = int(line.split()[-1])
                elif line.startswith("element face"):
                    face_count = int(line.split()[-1])
                elif line.strip() == "end_header":
                    header = False
            else:
                if vertex_count > 0:
                    vertices.append(tuple(map(float, line.split()[:3])))
                    vertex_count -= 1
                elif face_count > 0:
                    face_data = list(map(int, line.split()))
                    if len(face_data) >= 4:
                        faces.append(tuple(face_data[1:4]))
                    face_count -= 1
    return vertices, faces

def is_binary_stl(file_path):
    with open(file_path, "rb") as f:
        header = f.read(80)
        try:
            header.decode('ascii')
            return False
        except UnicodeDecodeError:
            return True

def parse_binary_stl(file_path):
    vertices = []
    faces = []
    with open(file_path, "rb") as f:
        f.seek(80)
        triangle_count_bytes = f.read(4)
        if not triangle_count_bytes: return [], []
        triangle_count = struct.unpack("<I", triangle_count_bytes)[0]
        for _ in range(triangle_count):
            f.read(12)
            v1 = struct.unpack("<fff", f.read(12))
            v2 = struct.unpack("<fff", f.read(12))
            v3 = struct.unpack("<fff", f.read(12))
            base_idx = len(vertices)
            vertices.extend([v1, v2, v3])
            faces.append((base_idx, base_idx+1, base_idx+2))
            f.read(2) # Attribute byte count
    return vertices, faces

def parse_stl(file_path):
    if is_binary_stl(file_path):
        return parse_binary_stl(file_path)
    
    vertices = []
    faces = []
    vertex_map = {}
    
    with open(file_path, "rb") as file:
        header = file.read(80)
        pass 
    return parse_binary_stl(file_path)

def convertFolderToBBM(input_folder:str, output_file:str=None, compression:int=0, dumpKeys:str="False", encryptionKey:str=None, encryptionMode:str=None):
    jsonEntries = []
    fileCounter, bCount = (0, 0)
    print("\n")
    if output_file is None:
        output_file = f".\\{os.path.basename(input_folder)}"

    for model in os.listdir(input_folder):
        exten = model[model.rfind('.'):].lower()
        if exten in ['.obj', '.ply', '.stl']:
            fileCounter += 1
            
    jsonFile = output_file.replace(output_file[output_file.rfind('.'):].lower(), ".json")
    
    with open(output_file, "wb") as f:
        with open(jsonFile, 'w') as dumpJSON:
            for file in os.listdir(input_folder):
                file_ext = file[file.rfind('.'):].lower()
                vertices, faces = [], []
                format_tag = b"BBM\x00"

                if file_ext == ".obj":
                    vertices, faces = parse_obj(f"{input_folder}\\{file}")
                    format_tag = b"BBM\x01"
                elif file_ext == ".ply":
                    vertices, faces = parse_ply(f"{input_folder}\\{file}")
                    format_tag = b"BBM\x02"
                elif file_ext == ".stl":
                    vertices, faces = parse_stl(f"{input_folder}\\{file}")
                    format_tag = b"BBM\x03"
                else:
                    continue
            
                bCount += 1
                if output_file is None:
                    output_file = f".\\{os.path.basename(input_folder)}"

                vertices, faces = optimize_mesh(vertices, faces)
                vertex_count = len(vertices)
                face_count = len(faces)

                packed_verts = pack_vertices(vertices)
                packed_faces = pack_faces(faces, vertex_count)

                vertex_data = encryptor(compressor(packed_verts, compression), encryptionKey, encryptionMode)
                face_data = encryptor(compressor(packed_faces, compression), encryptionKey, encryptionMode)
                
                vLen, fLen = len(vertex_data), len(face_data)
                modelName = file.replace(file_ext, '').encode('utf-8').ljust(0x10, b'\x00')

                header = struct.pack(
                    "4sIIHHQQ16s",
                    format_tag,
                    vertex_count,
                    face_count,
                    compression,
                    fileCounter,
                    vLen,
                    fLen,
                    modelName
                )
                f.write(header)
                f.write(vertex_data)
                f.write(face_data)

                jsonData = {
                    "Model-ID": modelName.decode('utf-8').replace('\x00', ''),
                    "Original-Type": file_ext,
                    "Vertext Count": vertex_count,
                    "Face Count": face_count,
                    "Compression": compression,
                    "Number of Models": fileCounter,
                    "Model Number": bCount,
                    "Vertex Length": vLen,
                    "Face Length": fLen
                }
                print(f"BBM Model #{bCount} ({file}), compiled into: {output_file}")
                jsonEntries.append(jsonData)

            dumpKeys_bool = dumpKeys.lower() == "true"
            if dumpKeys_bool == True:
                json.dump(jsonEntries, dumpJSON, indent=4)

        print("\n")
        sys.exit(1)

def convertFileToBBM(input_file:str, output_file:str=None, compression:int=0, dumpKeys:str="False", encryptionKey:str=None, encryptionMode:str=None):
    if os.path.isdir(input_file):
        convertFolderToBBM(input_file, output_file, compression, dumpKeys, encryptionKey, encryptionMode)

    file_ext = input_file[input_file.rfind('.'):].lower()
    vertices, faces = [], []
    format_tag = b"BBM\x00"

    if file_ext == ".obj":
        vertices, faces = parse_obj(input_file)
        format_tag = b"BBM\x01"
    elif file_ext == ".ply":
        vertices, faces = parse_ply(input_file)
        format_tag = b"BBM\x02"
    elif file_ext == ".stl":
        vertices, faces = parse_stl(input_file)
        format_tag = b"BBM\x03"
    else:
        print(f"Unsupported file format: {file_ext}")
        return

    if output_file is None:
        output_file = f".\\{input_file.replace(file_ext,'.bbm')}"

    vertices, faces = optimize_mesh(vertices, faces)
    vertex_count = len(vertices)
    face_count = len(faces)
    packed_verts = pack_vertices(vertices)
    packed_faces = pack_faces(faces, vertex_count)
    vertex_data = encryptor(compressor(packed_verts, compression), encryptionKey, encryptionMode)
    face_data = encryptor(compressor(packed_faces, compression), encryptionKey, encryptionMode)
    modelName = input_file.replace(file_ext, '').encode('utf-8').ljust(0x10, b'\x00')
    vLen, fLen = len(vertex_data), len(face_data)
    
    header = struct.pack(
        "4sIIHHQQ16s", 
        format_tag, 
        vertex_count, 
        face_count, 
        compression,
        1,
        vLen, 
        fLen, 
        modelName
    )
    with open(output_file, "wb") as f:
        f.write(header)
        f.write(vertex_data)
        f.write(face_data)
    
    jsonFile = output_file.replace(output_file[output_file.rfind('.'):].lower(), ".json")
    jsonData = {
        "Model-ID": modelName.decode('utf-8').replace('\x00', ''),
        "Original-Type": file_ext,
        "Vertext Count": vertex_count,
        "Face Count": face_count,
        "Compression": compression,
        "Number of Models": 1,
        "Model Number": 1,
        "Vertex Length": vLen,
        "Face Length": fLen
    }

    dumpKeys_bool = dumpKeys.lower() == "true"
    if dumpKeys_bool == True:
        with open(jsonFile, 'w') as dumpJSON:
            json.dump(jsonData, dumpJSON, indent=4)

if __name__ == "__main__":
    lnth = len(sys.argv)
    if lnth < 2:
        helpMessage()
    inputObjPlyFile = str(sys.argv[1])
    outputBbmFile = str(sys.argv[2]) if len(sys.argv) > 2 else None
    compressionMode = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    dumpModelKeys = str(sys.argv[4]) if len(sys.argv) > 4 else "False"
    encryptionMode = str(sys.argv[5]) if len(sys.argv) > 5 else None
    encryptionKey = str(sys.argv[6]) if len(sys.argv) > 6 else None
    convertFileToBBM(inputObjPlyFile, outputBbmFile, compressionMode, dumpModelKeys, encryptionKey, encryptionMode)
