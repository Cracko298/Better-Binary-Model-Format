import sys, lzma, bz2, zlib, struct, os, json, math

try:
    import lz4.block as lz4_block
except ImportError:
    lz4_block = None

try:
    import zstandard
except ImportError:
    zstandard = None

try:
    from Crypto.Cipher import AES, Blowfish, ChaCha20
    from Crypto.Random import get_random_bytes
    from Crypto.Util.Padding import pad
except ImportError:
    AES = Blowfish = ChaCha20 = None
    get_random_bytes = None
    pad = None

encryptionList = ['aes', 'xor', 'chacha', 'blowfish']
COMPRESSOR_IDS = [0, 1, 2, 3, 4, 5]
HEADER_STRUCT = struct.Struct('<4sIIHHQQ16s')
HEADER_SIZE = HEADER_STRUCT.size

VERT_FLOAT32 = 0
VERT_FLOAT16 = 1
VERT_FLOAT32_SHUFFLED = 2
VERT_FLOAT16_SHUFFLED = 3

VERT_STREAM_FLOAT16 = 4
VERT_STREAM_FLOAT32 = 5
VERT_QUANTIZED = 6

FACE_UINT32 = 0
FACE_UINT16 = 1
FACE_DELTA_INT32 = 2
FACE_DELTA_INT16 = 3

FACE_BITPACKED = 4
FACE_DELTA_VARINT = 5

def helpMessage():
    print(f'''
    │------------------Required Field-------------------│ │----------------------------Optional Fields----------------------------│
    python {os.path.basename(__file__)} [inputModelOrFolder] [outputBbmFile] [compressionMode] [dumpModelKeys] [encryptionMode] [encryptionKey] [vertexMode] [quantBits]

    Compression modes:
      0 = none
      1 = bz2
      2 = lz4
      3 = zstd
      4 = zlib
      5 = lzma
      6 = auto-pick smallest packed result

    Vertex modes:
      lossless  = exact restoration, stores split X/Y/Z streams (default)
      quantized = lossy integer grid inside mesh bounds for much smaller files

    Quant bits:
      Used only when vertexMode=quantized. Valid range: 1-24. Good starting values: 12, 14, 16
    ''')
    sys.exit(1)


def encryptor(byteData: bytes, encryptionKey: str = None, encryptionMode: str = None) -> bytes:
    try:
        encryptionType = encryptionMode.lower()
        if encryptionType not in encryptionList or encryptionMode is None or encryptionKey is None:
            return byteData
    except AttributeError:
        return byteData

    key_bytes = encryptionKey.encode()
    if encryptionType in {'aes', 'blowfish', 'chacha'} and (AES is None or Blowfish is None or ChaCha20 is None or get_random_bytes is None or pad is None):
        raise RuntimeError('PyCryptodome is required for aes/blowfish/chacha encryption modes.')

    if encryptionType == 'aes':
        key_bytes = key_bytes.ljust(32, b'\x00')[:32]
        cipher = AES.new(key_bytes, AES.MODE_CBC)
        return cipher.iv + cipher.encrypt(pad(byteData, AES.block_size))
    if encryptionType == 'blowfish':
        key_bytes = key_bytes[:56]
        cipher = Blowfish.new(key_bytes, Blowfish.MODE_CBC)
        return cipher.iv + cipher.encrypt(pad(byteData, Blowfish.block_size))
    if encryptionType == 'chacha':
        key_bytes = key_bytes.ljust(32, b'\x00')[:32]
        nonce = get_random_bytes(12)
        cipher = ChaCha20.new(key=key_bytes, nonce=nonce)
        return nonce + cipher.encrypt(byteData)

    key_length = len(key_bytes)
    return bytes([byteData[i] ^ key_bytes[i % key_length] for i in range(len(byteData))])


def compress_with_mode(byteData: bytes, compression: int = 0) -> bytes:
    if compression == 0:
        return byteData
    if compression == 1:
        return bz2.compress(byteData, 9)
    if compression == 2:
        if lz4_block is None:
            return byteData
        return lz4_block.compress(byteData)
    if compression == 3:
        if zstandard is None:
            return byteData
        cctx = zstandard.ZstdCompressor(level=19)
        return cctx.compress(byteData)
    if compression == 4:
        return zlib.compress(byteData, 9)
    if compression == 5:
        return lzma.compress(byteData)
    return byteData


def choose_best_compression(vertex_block: bytes, face_block: bytes, compression: int):
    if compression != 6:
        return compression, compress_with_mode(vertex_block, compression), compress_with_mode(face_block, compression)

    best = None
    for mode in COMPRESSOR_IDS:
        cverts = compress_with_mode(vertex_block, mode)
        cfaces = compress_with_mode(face_block, mode)
        total = len(cverts) + len(cfaces)
        if best is None or total < best[0]:
            best = (total, mode, cverts, cfaces)
    print(f'Auto compression selected mode {best[1]} (vertex={len(best[2])} bytes, face={len(best[3])} bytes)')
    return best[1], best[2], best[3]


def optimize_mesh(vertices, faces):
    """Removes duplicate vertices and degenerate/exact duplicate faces."""
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

    print(f'Optimization: Reduced {len(vertices)} verts to {len(deduped_vertices)}. Reduced {len(faces)} faces to {len(final_faces)}.')
    return deduped_vertices, final_faces


def reorder_vertices_for_locality(vertices, faces):
    remap = {}
    reordered_vertices = []
    reordered_faces = []
    for face in faces:
        new_face = []
        for idx in face:
            if idx not in remap:
                remap[idx] = len(reordered_vertices)
                reordered_vertices.append(vertices[idx])
            new_face.append(remap[idx])
        reordered_faces.append(tuple(new_face))
    if len(reordered_vertices) < len(vertices):
        for idx, vertex in enumerate(vertices):
            if idx not in remap:
                remap[idx] = len(reordered_vertices)
                reordered_vertices.append(vertex)
    return reordered_vertices, reordered_faces


def rotate_face_to_smallest(face):
    a, b, c = face
    if a <= b and a <= c:
        return (a, b, c)
    if b <= a and b <= c:
        return (b, c, a)
    return (c, a, b)


def reorder_faces_for_locality(faces):
    rotated = [rotate_face_to_smallest(face) for face in faces]
    return sorted(rotated)


def byte_plane_shuffle(data: bytes, element_size: int) -> bytes:
    if not data or element_size <= 1 or len(data) % element_size != 0:
        return data
    count = len(data) // element_size
    out = bytearray(len(data))
    mv = memoryview(data)
    for i in range(element_size):
        out[i * count:(i + 1) * count] = mv[i::element_size]
    return bytes(out)


def _bitpack(values, bits_per_value):
    if bits_per_value <= 0:
        return b''
    out = bytearray()
    acc = 0
    acc_bits = 0
    mask = (1 << bits_per_value) - 1
    for value in values:
        if value < 0 or value > mask:
            raise ValueError(f'Value {value} cannot fit in {bits_per_value} bits')
        acc |= (value & mask) << acc_bits
        acc_bits += bits_per_value
        while acc_bits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            acc_bits -= 8
    if acc_bits:
        out.append(acc & 0xFF)
    return bytes(out)


def zigzag_encode(value: int) -> int:
    return (value << 1) ^ (value >> 63)


def zigzag_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def encode_varints(values):
    out = bytearray()
    for value in values:
        while value >= 0x80:
            out.append((value & 0x7F) | 0x80)
            value >>= 7
        out.append(value)
    return bytes(out)


def component_stream_bytes(values, fmt):
    raw = b''.join(struct.pack(fmt, v) for v in values)
    return byte_plane_shuffle(raw, struct.calcsize(fmt))


def pack_vertices_lossless(vertices):
    try:
        fmt = '<e'
        flag = VERT_STREAM_FLOAT16
        xs = component_stream_bytes([v[0] for v in vertices], fmt)
        ys = component_stream_bytes([v[1] for v in vertices], fmt)
        zs = component_stream_bytes([v[2] for v in vertices], fmt)
    except Exception as exc:
        print(f'Half-float stream packing failed, reverting to float32 split streams: {exc}')
        fmt = '<f'
        flag = VERT_STREAM_FLOAT32
        xs = component_stream_bytes([v[0] for v in vertices], fmt)
        ys = component_stream_bytes([v[1] for v in vertices], fmt)
        zs = component_stream_bytes([v[2] for v in vertices], fmt)

    header = struct.pack('<BIII', flag, len(xs), len(ys), len(zs))
    return header + xs + ys + zs


def quantize_component(values, bits):
    min_v = min(values) if values else 0.0
    max_v = max(values) if values else 0.0
    if max_v == min_v:
        return min_v, max_v, [0] * len(values)
    max_int = (1 << bits) - 1
    scale = max_int / (max_v - min_v)
    quantized = []
    for value in values:
        q = int(round((value - min_v) * scale))
        if q < 0:
            q = 0
        elif q > max_int:
            q = max_int
        quantized.append(q)
    return min_v, max_v, quantized


def pack_vertices_quantized(vertices, quant_bits):
    if not (1 <= quant_bits <= 24):
        raise ValueError('quantBits must be between 1 and 24')
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    min_x, max_x, qx = quantize_component(xs, quant_bits)
    min_y, max_y, qy = quantize_component(ys, quant_bits)
    min_z, max_z, qz = quantize_component(zs, quant_bits)
    packed_x = _bitpack(qx, quant_bits)
    packed_y = _bitpack(qy, quant_bits)
    packed_z = _bitpack(qz, quant_bits)
    header = struct.pack(
        '<BBffffffIII',
        VERT_QUANTIZED,
        quant_bits,
        min_x,
        max_x,
        min_y,
        max_y,
        min_z,
        max_z,
        len(packed_x),
        len(packed_y),
        len(packed_z),
    )
    return header + packed_x + packed_y + packed_z


def pack_vertices(vertices, vertex_mode='lossless', quant_bits=14):
    if vertex_mode.lower() == 'quantized':
        return pack_vertices_quantized(vertices, quant_bits)
    return pack_vertices_lossless(vertices)


def pack_faces_raw_bitpacked(faces, vertex_count):
    max_index = max((max(face) for face in faces), default=0)
    bits = max(1, max_index.bit_length())
    flat = [idx for face in faces for idx in face]
    payload = _bitpack(flat, bits)
    header = struct.pack('<BBI', FACE_BITPACKED, bits, len(flat))
    return header + payload


def pack_faces_delta_varint(faces):
    flat = [idx for face in faces for idx in face]
    prev = 0
    zz = []
    for idx in flat:
        delta = idx - prev
        zz.append(zigzag_encode(delta))
        prev = idx
    payload = encode_varints(zz)
    header = struct.pack('<BI', FACE_DELTA_VARINT, len(flat))
    return header + payload


def pack_faces(faces, vertex_count):
    candidates = []
    if vertex_count <= 0xFFFF:
        raw16 = b''.join(struct.pack('<HHH', *f) for f in faces)
        candidates.append(bytes([FACE_UINT16]) + raw16)
    else:
        raw32 = b''.join(struct.pack('<III', *f) for f in faces)
        candidates.append(bytes([FACE_UINT32]) + raw32)

    flat = [idx for face in faces for idx in face]
    deltas = []
    prev = 0
    min_delta = 0
    max_delta = 0
    for idx in flat:
        delta = idx - prev
        deltas.append(delta)
        prev = idx
        min_delta = min(min_delta, delta)
        max_delta = max(max_delta, delta)
    if -32768 <= min_delta <= 32767 and -32768 <= max_delta <= 32767:
        candidates.append(bytes([FACE_DELTA_INT16]) + b''.join(struct.pack('<h', d) for d in deltas))
    candidates.append(bytes([FACE_DELTA_INT32]) + b''.join(struct.pack('<i', d) for d in deltas))
    candidates.append(pack_faces_raw_bitpacked(faces, vertex_count))
    candidates.append(pack_faces_delta_varint(faces))
    return min(candidates, key=len)


def parse_obj(file_path):
    vertices = []
    faces = []
    with open(file_path, 'r') as file:
        for line in file:
            parts = line.split()
            if line.startswith('#') or not line or not parts:
                continue
            if parts[0] == 'v':
                vertices.append(tuple(map(float, parts[1:4])))
            elif parts[0] == 'f':
                indices = []
                parts_face = parts[1:]
                if len(parts_face) < 3:
                    continue
                parsed = []
                for p in parts_face:
                    idx = int(p.split('/')[0])
                    parsed.append(idx - 1 if idx > 0 else len(vertices) + idx)
                for i in range(1, len(parsed) - 1):
                    faces.append((parsed[0], parsed[i], parsed[i + 1]))
    return vertices, faces


def parse_ply(file_path):
    vertices = []
    faces = []
    with open(file_path, 'r') as file:
        header = True
        vertex_count = 0
        face_count = 0
        for line in file:
            if line.startswith('#') or not line:
                continue
            if header:
                if line.startswith('element vertex'):
                    vertex_count = int(line.split()[-1])
                elif line.startswith('element face'):
                    face_count = int(line.split()[-1])
                elif line.strip() == 'end_header':
                    header = False
            else:
                if vertex_count > 0:
                    vertices.append(tuple(map(float, line.split()[:3])))
                    vertex_count -= 1
                elif face_count > 0:
                    face_data = list(map(int, line.split()))
                    if len(face_data) >= 4:
                        count = face_data[0]
                        idxs = face_data[1:1 + count]
                        for i in range(1, len(idxs) - 1):
                            faces.append((idxs[0], idxs[i], idxs[i + 1]))
                    face_count -= 1
    return vertices, faces


def is_binary_stl(file_path):
    with open(file_path, 'rb') as f:
        f.seek(80)
        count = f.read(4)
        if len(count) != 4:
            return False
        tri_count = struct.unpack('<I', count)[0]
        file_size = os.path.getsize(file_path)
        return 84 + tri_count * 50 == file_size


def parse_binary_stl(file_path):
    vertices = []
    faces = []
    with open(file_path, 'rb') as f:
        f.seek(80)
        triangle_count_bytes = f.read(4)
        if not triangle_count_bytes:
            return [], []
        triangle_count = struct.unpack('<I', triangle_count_bytes)[0]
        for _ in range(triangle_count):
            f.read(12)
            v1 = struct.unpack('<fff', f.read(12))
            v2 = struct.unpack('<fff', f.read(12))
            v3 = struct.unpack('<fff', f.read(12))
            base_idx = len(vertices)
            vertices.extend([v1, v2, v3])
            faces.append((base_idx, base_idx + 1, base_idx + 2))
            f.read(2)
    return vertices, faces


def parse_ascii_stl(file_path):
    vertices = []
    faces = []
    vertex_map = {}
    current = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            parts = raw.strip().split()
            if len(parts) >= 4 and parts[0].lower() == 'vertex':
                vertex = tuple(map(float, parts[1:4]))
                idx = vertex_map.setdefault(vertex, len(vertices))
                if idx == len(vertices):
                    vertices.append(vertex)
                current.append(idx)
                if len(current) == 3:
                    faces.append(tuple(current))
                    current = []
    return vertices, faces


def parse_stl(file_path):
    return parse_binary_stl(file_path) if is_binary_stl(file_path) else parse_ascii_stl(file_path)


def parse_model(file_path):
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext == '.obj':
        return parse_obj(file_path), b'BBM\x01'
    if file_ext == '.ply':
        return parse_ply(file_path), b'BBM\x02'
    if file_ext == '.stl':
        return parse_stl(file_path), b'BBM\x03'
    raise ValueError(f'Unsupported file format: {file_ext}')


def encode_model(input_file, output_handle, file_counter, model_number, compression, encryptionKey, encryptionMode, vertex_mode, quant_bits):
    (vertices, faces), format_tag = parse_model(input_file)
    vertices, faces = optimize_mesh(vertices, faces)
    vertices, faces = reorder_vertices_for_locality(vertices, faces)
    faces = reorder_faces_for_locality(faces)

    vertex_count = len(vertices)
    face_count = len(faces)
    vertex_block = pack_vertices(vertices, vertex_mode, quant_bits)
    face_block = pack_faces(faces, vertex_count)
    actual_compression, compressed_vertex_block, compressed_face_block = choose_best_compression(vertex_block, face_block, compression)
    vertex_data = encryptor(compressed_vertex_block, encryptionKey, encryptionMode)
    face_data = encryptor(compressed_face_block, encryptionKey, encryptionMode)

    modelName = os.path.splitext(os.path.basename(input_file))[0].encode('utf-8')[:16].ljust(16, b'\x00')
    header = HEADER_STRUCT.pack(format_tag, vertex_count, face_count, actual_compression, file_counter, len(vertex_data), len(face_data), modelName)
    output_handle.write(header)
    output_handle.write(vertex_data)
    output_handle.write(face_data)

    return {
        'Model-ID': modelName.decode('utf-8').replace('\x00', ''),
        'Original-Type': os.path.splitext(input_file)[1].lower(),
        'Vertex Count': vertex_count,
        'Face Count': face_count,
        'Compression': actual_compression,
        'Vertex Mode': vertex_mode,
        'Quant Bits': quant_bits if vertex_mode.lower() == 'quantized' else None,
        'Number of Models': file_counter,
        'Model Number': model_number,
        'Vertex Length': len(vertex_data),
        'Face Length': len(face_data),
    }


def convertFolderToBBM(input_folder: str, output_file: str = None, compression: int = 0, dumpKeys: str = 'False', encryptionKey: str = None, encryptionMode: str = None, vertex_mode: str = 'lossless', quant_bits: int = 14):
    model_paths = [os.path.join(input_folder, name) for name in os.listdir(input_folder) if os.path.splitext(name)[1].lower() in {'.obj', '.ply', '.stl'}]
    fileCounter = len(model_paths)
    if output_file is None:
        output_file = os.path.join('.', os.path.basename(input_folder) + '.bbm')
    jsonFile = os.path.splitext(output_file)[0] + '.json'

    jsonEntries = []
    with open(output_file, 'wb') as f:
        for idx, model_path in enumerate(model_paths, start=1):
            metadata = encode_model(model_path, f, fileCounter, idx, compression, encryptionKey, encryptionMode, vertex_mode, quant_bits)
            print(f'BBM Model #{idx} ({os.path.basename(model_path)}), compiled into: {output_file}')
            jsonEntries.append(metadata)

    if dumpKeys.lower() == 'true':
        with open(jsonFile, 'w') as dumpJSON:
            json.dump(jsonEntries, dumpJSON, indent=4)


def convertFileToBBM(input_file: str, output_file: str = None, compression: int = 0, dumpKeys: str = 'False', encryptionKey: str = None, encryptionMode: str = None, vertex_mode: str = 'lossless', quant_bits: int = 14):
    if os.path.isdir(input_file):
        return convertFolderToBBM(input_file, output_file, compression, dumpKeys, encryptionKey, encryptionMode, vertex_mode, quant_bits)

    if output_file is None:
        root, _ = os.path.splitext(input_file)
        output_file = root + '.bbm'

    with open(output_file, 'wb') as f:
        metadata = encode_model(input_file, f, 1, 1, compression, encryptionKey, encryptionMode, vertex_mode, quant_bits)

    if dumpKeys.lower() == 'true':
        jsonFile = os.path.splitext(output_file)[0] + '.json'
        with open(jsonFile, 'w') as dumpJSON:
            json.dump(metadata, dumpJSON, indent=4)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        helpMessage()
    inputModel = str(sys.argv[1])
    outputBbmFile = str(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != 'None' else None
    compressionMode = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    dumpModelKeys = str(sys.argv[4]) if len(sys.argv) > 4 else 'False'
    encryptionMode = str(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != 'None' else None
    encryptionKey = str(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] != 'None' else None
    vertexMode = str(sys.argv[7]) if len(sys.argv) > 7 else 'lossless'
    quantBits = int(sys.argv[8]) if len(sys.argv) > 8 else 14
    convertFileToBBM(inputModel, outputBbmFile, compressionMode, dumpModelKeys, encryptionKey, encryptionMode, vertexMode, quantBits)
