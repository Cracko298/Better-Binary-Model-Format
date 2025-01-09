import struct, sys, lzma, bz2, lz4.block, zstandard, zlib
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.pyplot as plt

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

def parse_bbm(file_path):
    with open(file_path, "rb") as f:
        header = f.read(0x30)
        format_tag, vertex_count, face_count, compression_flag, numFiles, vertexLen, faceLen, modelName = struct.unpack("4sIIHHQQ16s", header)
        print(f"Format Tag: {format_tag}, Vertex Count: {vertex_count}, Face Count: {face_count}, Compression: {compression_flag}")
        print(vertexLen)

        f.seek(0x30)
        compressed_vertex_data = f.read(vertexLen)
        vertex_data = decompressor(compressed_vertex_data, compression_flag)
        vertices = [struct.unpack("fff", vertex_data[i:i + 12]) for i in range(0, len(vertex_data), 12)]
        f.seek(0x30+vertexLen)
        compressed_face_data = f.read(faceLen)
        face_data = decompressor(compressed_face_data, compression_flag)
        faces = [struct.unpack("III", face_data[i:i + 12]) for i in range(0, len(face_data), 12)]

    print(f"Parsed {len(vertices)} vertices and {len(faces)} faces.")
    return vertices, faces

def render_bbm_model(file_path):
    vertices, faces = parse_bbm(file_path)
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

file = str(sys.argv[1])
render_bbm_model(file)
