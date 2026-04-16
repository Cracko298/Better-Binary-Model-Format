# BBM Data Storage Specification

This document explains how BBM stores geometry data internally, including headers, vertex encoding, face encoding, and compression behavior.

---

## Overview

BBM is designed around one core idea:

> Store geometry in a way that is both **small in raw form** and **highly compressible**

To achieve this, BBM uses:
- Structured binary layout
- Stream separation
- Optional quantization
- Bit-packing and delta encoding
- Standard compression algorithms

---

## File Layout

A BBM file is structured as:

```
[Header][Vertex Data][Face Data] (repeated for each model)
```

---

## Header Structure (0x30 bytes)

```
Bytes 00->02 = Format Tag ("BBM")
Byte  03     = Format Version / Source Type
Bytes 04->07 = Vertex Count
Bytes 08->0B = Face Count
Bytes 0C->0D = Compression Mode
Bytes 0E->0F = Number of Models
Bytes 10->17 = Vertex Data Length
Bytes 18->1F = Face Data Length
Bytes 20->2F = Model Name (16 bytes)
```

Notes:
- Header is **never compressed or encrypted**
- All sizes are stored before compression/encryption

---

## Vertex Data Storage

### Lossless Mode

Vertices are stored as **separate streams**:

```
[X Stream][Y Stream][Z Stream]
```

Each stream:
- Contains all values for one axis
- Uses half-floats (16-bit) or float32 fallback
- Is optionally byte-shuffled for better compression

Example:
```
X: x0 x1 x2 x3 ...
Y: y0 y1 y2 y3 ...
Z: z0 z1 z2 z3 ...
```

Why:
- Improves compression (patterns align per axis)
- Reduces entropy

---

### Quantized Mode

Vertices are:
1. Normalized within mesh bounds
2. Converted to integers
3. Bit-packed

Example:
```
value = (position - min) / range
quantized = int(value * (2^bits - 1))
```

Stored as:
- Bit-packed integer stream
- Exact bit width (e.g. 12 bits per coordinate)

Benefits:
- Much smaller storage
- Slight precision loss

---

## Face Data Storage

Faces are triangles stored as indices.

### Raw Mode
```
(i0, i1, i2)
```

Stored as:
- 16-bit if possible
- 32-bit otherwise

---

### Delta Encoding

Faces are reordered for locality, then stored as deltas:

```
i0, (i1 - i0), (i2 - i1)
```

Small numbers = better compression

---

### Bit-Packed Indices

Instead of fixed 16/32-bit:
```
bits = ceil(log2(vertex_count))
```

Each index is stored using exactly the required bits.

---

### Variable-Length Encoding

Small values are encoded using:
- Varints
- Zigzag encoding (for signed deltas)

This reduces storage for small differences.

---

## Compression Layer

After encoding, data is passed to a compressor:

```
Compressed(Vertex Stream)
Compressed(Face Stream)
```

Supported:
- None
- BZ2
- LZ4
- ZStandard
- ZLib
- LZMA
- Auto (selects smallest)

Important:
- Compression happens **after encoding**
- Structured data improves compression ratio significantly

---

## Encryption Layer

If enabled:

```
Encrypt(Compressed(Data))
```

- Applied after compression
- Header remains unencrypted
- Supported:
  - AES
  - XOR
  - ChaCha20
  - Blowfish

---

## Multi-Model Support

Multiple models are stored sequentially:

```
[Header][Data][Header][Data]...
```

Header field defines:
- Total number of models
- Each model can be accessed independently

---

## Why This Works

BBM achieves high compression by combining:

1. **Data Structuring**
   - Separate streams
   - Reordering

2. **Mathematical Encoding**
   - Delta encoding
   - Quantization

3. **Bit-Level Optimization**
   - Exact bit packing
   - No wasted bits

4. **Final Compression**
   - Standard algorithms exploit patterns

---

## Key Insight

> Compression works best on structured, predictable data.

BBM transforms geometry into:
- Predictable
- Low-entropy
- Pattern-rich streams

This allows standard compressors to achieve extremely high ratios.

---

## Summary

| Feature              | Purpose |
|---------------------|--------|
| Stream Separation   | Improve compression |
| Delta Encoding      | Reduce value size |
| Bit Packing         | Remove unused bits |
| Quantization        | Reduce precision (optional) |
| Compression         | Final size reduction |
| Encryption          | Security (optional) |

---

## Final Notes

- Lossless mode preserves exact geometry
- Quantized mode provides best size reduction
- Auto compression ensures optimal output size
- Format is designed for performance + size balance

