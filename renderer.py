import struct, sys, lzma, bz2, lz4.block, zstandard, zlib, io
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from Crypto.Cipher import AES, Blowfish, ChaCha20
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import matplotlib.pyplot as plt

encryptionList = ['aes', 'xor', 'chacha', 'blowfish']
HEADER_SIZE = 0x30 # (decimal 48) bytes
multipleModels = []
modelNames = []

def decryptor(byteData:bytes, encryptionKey:str=None, encryptionMode:str=None) -> bytes:
    try:
        encryptionType = encryptionMode.lower()
        if encryptionType not in encryptionList or encryptionMode is None or encryptionKey is None:
            return byteData
    except AttributeError:
        return byteData

    key_bytes = encryptionKey.encode()
    decrypted_data = None
    nonce = None
    if encryptionType == "aes":
        key_bytes = key_bytes.ljust(32)[:32]
        cipher = AES.new(key_bytes, AES.MODE_CBC)
        decrypted_data = unpad(cipher.decrypt(byteData), AES.block_size)
    elif encryptionType == "blowfish":
        key_bytes = key_bytes[:56]
        cipher = Blowfish.new(key_bytes, Blowfish.MODE_CBC)
        decrypted_data = unpad(cipher.decrypt(byteData), Blowfish.block_size)
    elif encryptionType == "chacha":
        key_bytes = key_bytes.ljust(32)[:32]
        nonce = byteData[:12]
        cipher = ChaCha20.new(key=key_bytes, nonce=nonce)
        decrypted_data = cipher.decrypt(byteData[12:])
    else:
        key_length = len(key_bytes)
        decrypted_data = bytes([byteData[i] ^ key_bytes[i % key_length] for i in range(len(byteData))])

    return decrypted_data

def decompressor(data:bytes, compression_flag:int=0) -> bytes:
    if compression_flag == 0:
        return data
    elif compression_flag == 1:
        return bz2.decompress(data)
    elif compression_flag == 2:
        return lz4.block.decompress(data)
    elif compression_flag == 3:
        zstd_decompressor = zstandard.ZstdDecompressor()
        return zstd_decompressor.decompress(data)
    elif compression_flag == 4:
        return zlib.decompress(data)
    elif compression_flag == 5:
        return lzma.decompress(data)
    else:
        return data

def readHeader(byteData: bytes):
    format_tag, vertex_count, face_count, compression_flag, numFiles, vertex_len, face_len, modelName = struct.unpack("4sIIHHQQ16s", byteData)
    modelName = str(modelName.decode('utf-8').replace('\x00', ''))
    formatVersion = int.from_bytes(format_tag[0x02:0x03], 'little')
    return modelName, vertex_count, face_count, compression_flag, numFiles, vertex_len, face_len, formatVersion

def parseBbm(file_path:str, fileToView:int=0, encryptionKey:str=None, encryptionMode:str=None) -> bytes:
    entryCount = 0
    baseNumber = 0
    with open(file_path, 'rb') as f:
        modelName, vertexCount, faceCount, compression, numFiles, vertexLen, faceLen, formatVersion = readHeader(f.read(HEADER_SIZE))
        f.seek(0x00)
        if numFiles == 1:
            f.seek(HEADER_SIZE)
            decryptedVertextData = decryptor(f.read(vertexLen), encryptionKey, encryptionMode); decompressedVertexData = decompressor(decryptedVertextData, compression)
            vertexData = [struct.unpack("fff", decompressedVertexData[i:i + 12]) for i in range(0, len(decompressedVertexData), 12)]
            f.seek(HEADER_SIZE+vertexLen)
            decryptedFaceData = decryptor(f.read(faceLen), encryptionKey, encryptionMode); decompressedFaceData = decompressor(decryptedFaceData, compression)
            faceData = [struct.unpack("III", decompressedFaceData[i:i + 12]) for i in range(0, len(decompressedFaceData), 12)]
            print(f"Model ID: {modelName}\nFormat Tag: {formatVersion}\nVertex Count: {vertexCount}\nFace Count: {faceCount}\nCompression: {compression}")
            print(f"Parsed {len(vertexData)} vertices and {len(faceData)} faces.")
            return vertexData, faceData
        else:
            multipleModels.append(io.BytesIO(f.read(HEADER_SIZE+vertexLen+faceLen)))
            entryCount += 1
            modelNames.append(modelName)
            baseNumber += (HEADER_SIZE+vertexLen+faceLen)
            for i in range(0, numFiles-1):
                f.seek(baseNumber)
                modelName, vertexCount, faceCount, compression, numFiles, vertexLen, faceLen, formatVersion = readHeader(f.read(HEADER_SIZE))
                f.seek(baseNumber)
                multipleModels.append(io.BytesIO(f.read(HEADER_SIZE+vertexLen+faceLen)))
                modelNames.append(modelName)
                baseNumber += (HEADER_SIZE+vertexLen+faceLen)
                entryCount += 1
            selectedModel =  multipleModels[fileToView] if entryCount >= fileToView else multipleModels[0]
            with selectedModel as f:
                modelName, vertexCount, faceCount, compression, numFiles, vertexLen, faceLen, formatVersion = readHeader(f.read(HEADER_SIZE))
                f.seek(HEADER_SIZE)
                decryptedVertexData = decryptor(f.read(vertexLen), encryptionKey, encryptionMode); decompressedVertexData = decompressor(decryptedVertexData, compression)
                vertexData = [struct.unpack("fff", decompressedVertexData[i:i + 12]) for i in range(0, len(decompressedVertexData), 12)]
                f.seek(HEADER_SIZE+vertexLen)
                decryptedFaceData = decryptor(f.read(faceLen), encryptionKey, encryptionMode); decompressedFaceData = decompressor(decryptedFaceData, compression)
                faceData = [struct.unpack("III", decompressedFaceData[i:i + 12]) for i in range(0, len(decompressedFaceData), 12)]
                print(f"Model ID: {modelName}\nFormat Tag: {formatVersion}\nVertex Count: {vertexCount}\nFace Count: {faceCount}\nCompression: {compression}")
                print(f"Parsed {len(vertexData)} vertices and {len(faceData)} faces.")
                return vertexData, faceData
            
def renderBbmModel(file_path, fileToView:int=0, encryptionKey:str=None, encryptionMode:str=None):
    vertices, faces = parseBbm(file_path, fileToView, encryptionKey, encryptionMode)
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    mesh = Poly3DCollection(
        [[vertices[face[i]] for i in range(3)] for face in faces],
        edgecolor='k', alpha=0.5, linewidths=0.5
    )
    ax.add_collection3d(mesh)
    vertices_array = list(zip(*vertices))
    x_limits = (min(vertices_array[0]), max(vertices_array[0]))
    y_limits = (min(vertices_array[1]), max(vertices_array[1]))
    z_limits = (min(vertices_array[2]), max(vertices_array[2]))
    max_range = max(
        x_limits[1] - x_limits[0],
        y_limits[1] - y_limits[0],
        z_limits[1] - z_limits[0]
    ) / 2.0

    x_mid = (x_limits[0] + x_limits[1]) / 2.0
    y_mid = (y_limits[0] + y_limits[1]) / 2.0
    z_mid = (z_limits[0] + z_limits[1]) / 2.0
    ax.set_xlim(x_mid - max_range, x_mid + max_range)
    ax.set_ylim(y_mid - max_range, y_mid + max_range)
    ax.set_zlim(z_mid - max_range, z_mid + max_range)
    ax.set_xlabel("X-axis")
    ax.set_ylabel("Y-axis")
    ax.set_zlabel("Z-axis")
    plt.show()

try:
    file = str(sys.argv[1])
    fileToView = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    encryptionKey = str(sys.argv[4]) if len(sys.argv) > 4 else None
    encryptionMode = str(sys.argv[3]) if len(sys.argv) > 3 else None
    renderBbmModel(file, fileToView, encryptionKey, encryptionMode)
except IndexError:
    sys.exit(1)