# BBM
- You can look at the Spec of the Data [Here](https://github.com/Cracko298/Better-Binary-Model-Format/blob/main/BBM_SPEC_SHEET.md).
- Better Binary Model (BBM) is an Insanely lightweight 3D Model and Geometry format (upto 1.3% of the original file-size). With support for Lossy, and Lossless Compression, and Compression algorithms. For Game Engines, Embedded Systems and Microcontrollers with limited resources and/or no storage.

- It is highly versatile, supporting OBJ/PLY/STL conversion, encryption, compression, and multiple models.
- Designed for efficient geometry storage in game engines and real-time applications.
- No encryption information is stored in the Header (keeps header minimal).

---

## Features:
- Easy-To-Understand Header.
- Standard Compression Algorithms or None at all.
- **Auto Compression Mode (mode 6, selects smallest result automatically).**
- Multi-Model Support (multiple models per file).
- Insanely small file-sizes (up to `98%+` reduction).
- **Lossless Mode (exact geometry, no precision loss).**
- **Quantized Mode (ultra-small with near-identical visual quality).**
- **Bit-Packed Geometry (exact-bit index + coordinate packing).**
- **Separate Vertex Streams (X/Y/Z for better compression).**
- Dump Information on Models at Generation (acts like a key).
- Ability to encrypt your Models (not headers).

---

## Geometry Modes:
- `lossless`
  - Exact vertex data
  - Stream-separated (X/Y/Z)
  - Optimized for compression
- `quantized [bits]`
  - Fixed-bit coordinate storage (e.g. 12-bit, 14-bit)
  - Much smaller, slight precision tradeoff

---

## Compression Modes:
```
0 = None
1 = BZ2
2 = LZ4 (optional)
3 = ZStandard (optional)
4 = ZLib
5 = LZMA
6 = Auto (selects smallest result)
```

---

## Compiling Models:
```
│------------------Required Field-------------------│ │------------------------------Optional Field------------------------------│
python generator.py [input] [output] [compression] [dumpKeys] [encryptionMode] [encryptionKey] [geometryMode] [quantBits]
```

---

### Example Command(s):
```
# Lossless (recommended)
python generator.py model.obj model.bbm 6 false None None lossless

# Quantized (smaller)
python generator.py model.obj model_q.bbm 6 false None None quantized 12

# Encrypted
python generator.py model.obj secure.bbm 6 true aes "MyKey123" lossless

# Multi-model folder
python generator.py models/ army.bbm 6 true xor "TankArmyKey" lossless
```

---

## Header Information:
```
00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F | Decoded Text 
------------------------------------------------|-----------------
42 42 4D 01 ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? | BBM.............
?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? | ................ 
6D 6F 64 65 6C 00 00 00 00 00 00 00 00 00 00 00 | model...........
```


```
Bytes 00->02 = Format Tag ("BBM")
Byte  03     = Format Version / Source Type
Bytes 04->07 = Vertex Count
Bytes 08->0B = Face Count
Bytes 0C->0D = Compression Mode
Bytes 0E->0F = Number of Models
Bytes 10->17 = Vertex Data Length
Bytes 18->1F = Face Data Length
Bytes 20->2F = Model Name
```

### Notes:
- Vertex/Face data may be:
  - Delta encoded
  - Bit-packed
  - Quantized (if enabled)
- Header is NOT compressed or encrypted

---

## Rendering Model:
```
│---------------Required Field----------------│ │--------Optional Field--------│
python renderer.py [inputBbmFile] [modelNumber] [encryptionMode] [encryptionKey]
```

---

## Important Notes:
- Mode `6` will automatically choose the smallest compression algorithm.
- Lossless mode may compress better than quantized due to higher pattern repetition.
- Quantized mode produces the smallest raw data, but may compress less efficiently.
- LZ4 and ZStandard are optional dependencies.

---

## Roadmap:
- Support for BBModel / JSON / BJSON
- Normal / UV compression
- Animation / skeletal support
- Advanced topology encoding (triangle strips / edge compression)
