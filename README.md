# BBM
- Better Binary Model (BBM) is a 3D Model/Geometry Format for E.S. & Microcontrollers with very small file-sizes.
- It's also quite versitile, allowing for easy OBJ/PLY conversions, encryption, compression, and multiple models.
- Useful for Geometry as well in Game Development/Engines, and assets that are cruicial for your Game.
- No encryption information is stored in the Header.

## Features:
- Easy-To-Understand Header.
- Standard Compression Algorithms or None at all.
- Multi-Model Support (yes it supports multiple models in the same file).
- Insanely small file-sizes (upto `95%` file-sizes reduction).
- No Quality Loss (yes, you heard it correctly).

## Roadmap:
- Add Support for BBModel/JSON/BJSON Models.
- Add AES/XOR/Blowfish/ChaCha20 Encryption Support per-model (with the same key).
- Export Model-Keys (basically position of model in file with name).

## Compiling Models:
- You can compile your model into the format by using the following command:
```
    │------------------Required Field-------------------│ │-------------------------Optional Field-------------------------│
    python generator.py [inputObjPlyFile] [outputBbmFile] [compressionMode] [dumpModelKeys] [encryptionMode] [encryptionKey]
                                                          │                 │               |
                                                          │                 └─ Dump-Keys (Boolean):
                                                          │                    ├─ True      |
                                                          │                    └─ False     |
                                                          │                                 └─ Encryption (String):
                                                          │                                    ├─ AES
                                                          └─ Compression (Integer):            ├─ XOR
                                                             ├─ 0 = None                       ├─ ChaCha
                                                             ├─ 1 = BZ2                        └─ Blowfish
                                                             ├─ 2 = LZ4
                                                             ├─ 3 = ZStandard
                                                             ├─ 4 = ZLib
                                                             └─ 5 = LZMA
```

## Rendering Model:
- You can render your compiled model by using command:
```
py renderer.py [inputBbmFile]
```
