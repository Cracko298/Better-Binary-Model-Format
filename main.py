import sys, lzma, bz2, lz4, zstandard, zlib, struct, lz4.frame, os

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
                faces.append(tuple(int(p.split('/')[0]) - 1 for p in parts[1:4]))
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
        triangle_count = struct.unpack("<I", f.read(4))[0]
        for _ in range(triangle_count):
            f.read(12)
            vertices.append(tuple(struct.unpack("<fff", f.read(12))))
            vertices.append(tuple(struct.unpack("<fff", f.read(12))))
            vertices.append(tuple(struct.unpack("<fff", f.read(12))))
            faces.append((len(vertices) - 3, len(vertices) - 2, len(vertices) - 1))
            f.read(2)
    return vertices, faces

def parse_stl(file_path):
    if is_binary_stl(file_path):
        return parse_binary_stl(file_path)
    vertices = []
    faces = []
    vertex_map = {}
    
    with open(file_path, "rb") as file:
        header = file.read(80)
        if len(header) != 80:
            raise ValueError("STL file header is not 80 bytes.")

        num_faces = struct.unpack("I", file.read(4))[0]
        
        print(f"Number of faces: {num_faces}")

        for _ in range(num_faces):
            face_data = file.read(50)
            if len(face_data) != 50:
                continue

            normal = struct.unpack("3f", face_data[:12])
            
            face_vertices = struct.unpack("3f", face_data[12:24])
            face_vertices += struct.unpack("3f", face_data[24:36])
            face_vertices += struct.unpack("3f", face_data[36:48])
            file.read(2)
            for vertex in [face_vertices[:3], face_vertices[3:6], face_vertices[6:]]:
                if vertex not in vertex_map:
                    vertex_map[vertex] = len(vertices)
                    vertices.append(vertex)

            faces.append((
                vertex_map[face_vertices[:3]], 
                vertex_map[face_vertices[3:6]], 
                vertex_map[face_vertices[6:]]
            ))

    return vertices, faces

def convertFolderToBBM(input_folder:str, output_file:str = None, compression:int = 0):
    fileCounter, bCount = (0, 0)
    print("\n")
    if output_file is None:
        output_file = f".\\{os.path.basename(input_folder)}"

    for model in os.listdir(input_folder):
        exten = model[model.rfind('.'):].lower()
        if exten == '.obj' or exten == '.ply':
            fileCounter += 1
    
    with open(output_file, "wb") as f:
        for file in os.listdir(input_folder):
            file_ext = file[file.rfind('.'):].lower()
            if file_ext == ".obj":
                vertices, faces = parse_obj(f"{input_folder}\\{file}")
                format_tag = b"BBM\x01"
            elif file_ext == ".ply":
                vertices, faces = parse_ply(f"{input_folder}\\{file}")
                format_tag = b"BBM\x02"
            else:
                continue
            
            bCount += 1
            if output_file is None:
                output_file = f".\\{os.path.basename(input_folder)}"

            vertex_count = len(vertices)
            face_count = len(faces)
            vertex_data = compressor(b"".join([struct.pack("fff", *v) for v in vertices]), compression)
            face_data = compressor(b"".join([struct.pack("III", *f) for f in faces]), compression)
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

            print(f"BBM Model #{bCount} ({file}), compiled into: {output_file}")
    print("\n")
    sys.exit(1)

def convertFileToBBM(input_file:str, output_file:str=None, compression:int=0):
    if os.path.isdir(input_file):
        convertFolderToBBM(input_file, output_file, compression)

    file_ext = input_file[input_file.rfind('.'):].lower()
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

    vertex_count = len(vertices)
    face_count = len(faces)
    vertex_data = compressor(b"".join([struct.pack("fff", *v) for v in vertices]), compression)
    face_data = compressor(b"".join([struct.pack("III", *f) for f in faces]), compression)
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

if __name__ == "__main__":
    try:convertFileToBBM(str(sys.argv[1]), str(sys.argv[2]), int(sys.argv[3]))
    except IndexError:
        try:convertFileToBBM(str(sys.argv[1]), str(sys.argv[2]))
        except IndexError: convertFileToBBM(str(sys.argv[1]))