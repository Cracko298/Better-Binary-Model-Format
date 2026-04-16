import struct, sys, lzma, bz2, zlib, io
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.pyplot as plt

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
    from Crypto.Util.Padding import unpad
except ImportError:
    AES = Blowfish = ChaCha20 = None
    unpad = None

encryptionList = ['aes', 'xor', 'chacha', 'blowfish']
HEADER_STRUCT = struct.Struct('<4sIIHHQQ16s')
HEADER_SIZE = HEADER_STRUCT.size
multipleModels = []
modelNames = []

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


def decryptor(byteData: bytes, encryptionKey: str = None, encryptionMode: str = None) -> bytes:
    try:
        encryptionType = encryptionMode.lower()
        if encryptionType not in encryptionList or encryptionMode is None or encryptionKey is None:
            return byteData
    except AttributeError:
        return byteData

    key_bytes = encryptionKey.encode()
    if encryptionType in {'aes', 'blowfish', 'chacha'} and (AES is None or Blowfish is None or ChaCha20 is None or unpad is None):
        raise RuntimeError('PyCryptodome is required for aes/blowfish/chacha encryption modes.')

    if encryptionType == 'aes':
        key_bytes = key_bytes.ljust(32, b'\x00')[:32]
        iv = byteData[:16]
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv=iv)
        return unpad(cipher.decrypt(byteData[16:]), AES.block_size)
    if encryptionType == 'blowfish':
        key_bytes = key_bytes[:56]
        iv = byteData[:8]
        cipher = Blowfish.new(key_bytes, Blowfish.MODE_CBC, iv=iv)
        return unpad(cipher.decrypt(byteData[8:]), Blowfish.block_size)
    if encryptionType == 'chacha':
        key_bytes = key_bytes.ljust(32, b'\x00')[:32]
        nonce = byteData[:12]
        cipher = ChaCha20.new(key=key_bytes, nonce=nonce)
        return cipher.decrypt(byteData[12:])

    key_length = len(key_bytes)
    return bytes([byteData[i] ^ key_bytes[i % key_length] for i in range(len(byteData))])


def decompressor(data: bytes, compression_flag: int = 0) -> bytes:
    if compression_flag == 0:
        return data
    if compression_flag == 1:
        return bz2.decompress(data)
    if compression_flag == 2:
        if lz4_block is None:
            raise RuntimeError('lz4 is required to decompress compression mode 2 data.')
        return lz4_block.decompress(data)
    if compression_flag == 3:
        if zstandard is None:
            raise RuntimeError('zstandard is required to decompress compression mode 3 data.')
        return zstandard.ZstdDecompressor().decompress(data)
    if compression_flag == 4:
        return zlib.decompress(data)
    if compression_flag == 5:
        return lzma.decompress(data)
    return data


def readHeader(byteData: bytes):
    format_tag, vertex_count, face_count, compression_flag, numFiles, vertex_len, face_len, modelName = HEADER_STRUCT.unpack(byteData)
    modelName = modelName.decode('utf-8', errors='ignore').replace('\x00', '')
    formatVersion = format_tag[3]
    return modelName, vertex_count, face_count, compression_flag, numFiles, vertex_len, face_len, formatVersion


def byte_unshuffle(data: bytes, element_size: int) -> bytes:
    if not data or element_size <= 1 or len(data) % element_size != 0:
        return data
    count = len(data) // element_size
    out = bytearray(len(data))
    mv = memoryview(data)
    for i in range(element_size):
        out[i::element_size] = mv[i * count:(i + 1) * count]
    return bytes(out)


def _bitunpack(data: bytes, bits_per_value: int, count: int):
    if bits_per_value <= 0:
        return [0] * count
    out = []
    acc = 0
    acc_bits = 0
    mask = (1 << bits_per_value) - 1
    iterator = iter(data)
    while len(out) < count:
        while acc_bits < bits_per_value:
            try:
                acc |= next(iterator) << acc_bits
            except StopIteration:
                break
            acc_bits += 8
        out.append(acc & mask)
        acc >>= bits_per_value
        acc_bits -= bits_per_value
    return out


def zigzag_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def decode_varints(data: bytes):
    values = []
    value = 0
    shift = 0
    for byte in data:
        value |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
            continue
        values.append(value)
        value = 0
        shift = 0
    if shift != 0:
        raise ValueError('Truncated varint data')
    return values


def unpack_vertices_legacy(data: bytes):
    flag = data[0]
    payload = data[1:]
    if flag == VERT_FLOAT16_SHUFFLED:
        payload = byte_unshuffle(payload, 6)
        flag = VERT_FLOAT16
    elif flag == VERT_FLOAT32_SHUFFLED:
        payload = byte_unshuffle(payload, 12)
        flag = VERT_FLOAT32
    if flag == VERT_FLOAT16:
        return [struct.unpack('<eee', payload[i:i + 6]) for i in range(0, len(payload), 6)]
    return [struct.unpack('<fff', payload[i:i + 12]) for i in range(0, len(payload), 12)]


def unpack_vertices(data: bytes, vertex_count: int):
    if not data:
        return []
    flag = data[0]
    if flag in {VERT_FLOAT16, VERT_FLOAT32, VERT_FLOAT16_SHUFFLED, VERT_FLOAT32_SHUFFLED}:
        return unpack_vertices_legacy(data)
    if flag in {VERT_STREAM_FLOAT16, VERT_STREAM_FLOAT32}:
        _, x_len, y_len, z_len = struct.unpack('<BIII', data[:13])
        offset = 13
        xs_raw = data[offset:offset + x_len]
        offset += x_len
        ys_raw = data[offset:offset + y_len]
        offset += y_len
        zs_raw = data[offset:offset + z_len]
        elem_fmt = '<e' if flag == VERT_STREAM_FLOAT16 else '<f'
        elem_size = struct.calcsize(elem_fmt)
        xs = [struct.unpack(elem_fmt, byte_unshuffle(xs_raw, elem_size)[i:i + elem_size])[0] for i in range(0, x_len, elem_size)]
        ys = [struct.unpack(elem_fmt, byte_unshuffle(ys_raw, elem_size)[i:i + elem_size])[0] for i in range(0, y_len, elem_size)]
        zs = [struct.unpack(elem_fmt, byte_unshuffle(zs_raw, elem_size)[i:i + elem_size])[0] for i in range(0, z_len, elem_size)]
        return list(zip(xs, ys, zs))
    if flag == VERT_QUANTIZED:
        _, bits, min_x, max_x, min_y, max_y, min_z, max_z, len_x, len_y, len_z = struct.unpack('<BBffffffIII', data[:38])
        offset = 38
        pack_x = data[offset:offset + len_x]
        offset += len_x
        pack_y = data[offset:offset + len_y]
        offset += len_y
        pack_z = data[offset:offset + len_z]
        max_int = (1 << bits) - 1
        qx = _bitunpack(pack_x, bits, vertex_count)
        qy = _bitunpack(pack_y, bits, vertex_count)
        qz = _bitunpack(pack_z, bits, vertex_count)

        def dequantize(qvals, min_v, max_v):
            if max_int == 0 or max_v == min_v:
                return [min_v] * len(qvals)
            scale = (max_v - min_v) / max_int
            return [min_v + q * scale for q in qvals]

        xs = dequantize(qx, min_x, max_x)
        ys = dequantize(qy, min_y, max_y)
        zs = dequantize(qz, min_z, max_z)
        return list(zip(xs, ys, zs))
    raise ValueError(f'Unknown vertex packing flag: {flag}')


def unpack_faces(data: bytes):
    if not data:
        return []
    flag = data[0]
    payload = data[1:]
    if flag == FACE_UINT16:
        return [struct.unpack('<HHH', payload[i:i + 6]) for i in range(0, len(payload), 6)]
    if flag == FACE_UINT32:
        return [struct.unpack('<III', payload[i:i + 12]) for i in range(0, len(payload), 12)]
    if flag in {FACE_DELTA_INT16, FACE_DELTA_INT32}:
        step = 2 if flag == FACE_DELTA_INT16 else 4
        fmt = '<h' if flag == FACE_DELTA_INT16 else '<i'
        deltas = [struct.unpack(fmt, payload[i:i + step])[0] for i in range(0, len(payload), step)]
        indices = []
        prev = 0
        for delta in deltas:
            value = prev + delta
            indices.append(value)
            prev = value
        return [tuple(indices[i:i + 3]) for i in range(0, len(indices), 3)]
    if flag == FACE_BITPACKED:
        _, bits, flat_count = struct.unpack('<BBI', data[:6])
        flat = _bitunpack(data[6:], bits, flat_count)
        return [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
    if flag == FACE_DELTA_VARINT:
        _, flat_count = struct.unpack('<BI', data[:5])
        zz = decode_varints(data[5:])
        indices = []
        prev = 0
        for encoded in zz[:flat_count]:
            value = prev + zigzag_decode(encoded)
            indices.append(value)
            prev = value
        return [tuple(indices[i:i + 3]) for i in range(0, len(indices), 3)]
    raise ValueError(f'Unknown face packing flag: {flag}')


def parseBbm(file_path: str, fileToView: int = 0, encryptionKey: str = None, encryptionMode: str = None):
    multipleModels.clear()
    modelNames.clear()
    with open(file_path, 'rb') as f:
        header = f.read(HEADER_SIZE)
        modelName, vertexCount, faceCount, compression, numFiles, vertexLen, faceLen, formatVersion = readHeader(header)
        f.seek(0)
        target_model_data = None
        if numFiles == 1:
            target_model_data = f
        else:
            base = 0
            for _ in range(numFiles):
                f.seek(base)
                sub_header = f.read(HEADER_SIZE)
                name, v_count, f_count, comp, _, v_len, f_len, fmt_ver = readHeader(sub_header)
                f.seek(base)
                blob = f.read(HEADER_SIZE + v_len + f_len)
                multipleModels.append(io.BytesIO(blob))
                modelNames.append(name)
                base += HEADER_SIZE + v_len + f_len
            target_model_data = multipleModels[fileToView] if 0 <= fileToView < len(multipleModels) else multipleModels[0]

        with target_model_data as stream:
            if isinstance(stream, io.BytesIO):
                stream.seek(0)
            header = stream.read(HEADER_SIZE)
            modelName, vertexCount, faceCount, compression, numFiles, vertexLen, faceLen, formatVersion = readHeader(header)
            vertex_blob = decryptor(stream.read(vertexLen), encryptionKey, encryptionMode)
            face_blob = decryptor(stream.read(faceLen), encryptionKey, encryptionMode)
            vertexData = unpack_vertices(decompressor(vertex_blob, compression), vertexCount)
            faceData = unpack_faces(decompressor(face_blob, compression))
            print(f'Model ID: {modelName}\nFormat Tag: {formatVersion}\nVertex Count: {vertexCount}\nFace Count: {faceCount}\nCompression: {compression}')
            print(f'Parsed {len(vertexData)} vertices and {len(faceData)} faces.')
            return vertexData, faceData


def renderBbmModel(file_path, fileToView: int = 0, encryptionKey: str = None, encryptionMode: str = None):
    vertices, faces = parseBbm(file_path, fileToView, encryptionKey, encryptionMode)
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    mesh = Poly3DCollection([[vertices[face[i]] for i in range(3)] for face in faces], edgecolor='k', alpha=0.5, linewidths=0.5)
    ax.add_collection3d(mesh)
    vertices_array = list(zip(*vertices))
    x_limits = (min(vertices_array[0]), max(vertices_array[0]))
    y_limits = (min(vertices_array[1]), max(vertices_array[1]))
    z_limits = (min(vertices_array[2]), max(vertices_array[2]))
    max_range = max(x_limits[1] - x_limits[0], y_limits[1] - y_limits[0], z_limits[1] - z_limits[0]) / 2.0
    x_mid = (x_limits[0] + x_limits[1]) / 2.0
    y_mid = (y_limits[0] + y_limits[1]) / 2.0
    z_mid = (z_limits[0] + z_limits[1]) / 2.0
    ax.set_xlim(x_mid - max_range, x_mid + max_range)
    ax.set_ylim(y_mid - max_range, y_mid + max_range)
    ax.set_zlim(z_mid - max_range, z_mid + max_range)
    ax.set_xlabel('X-axis')
    ax.set_ylabel('Y-axis')
    ax.set_zlabel('Z-axis')
    plt.show()


if __name__ == '__main__':
    try:
        file = str(sys.argv[1])
        fileToView = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        encryptionMode = str(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != 'None' else None
        encryptionKey = str(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != 'None' else None
        renderBbmModel(file, fileToView, encryptionKey, encryptionMode)
    except IndexError:
        sys.exit(1)
