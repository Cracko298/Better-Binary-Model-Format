# BBM
- Better Binary Model (BBM) is a 3D Model Format for E.S. and Microcontrollers with very small file-sizes.
- It's also quite versitile, allowing for easy OBJ/PLY conversions.

## Features:
- Easy-To-Understand Header.
- Standard Compression Algorithms or None at all.
- Multi-Model Support (yes it supports multiple models in the same file).
- Insanely small file-sizes (`5-20%` of original file-sizes).
- No Quality Loss (yes, you heard it correctly).

## Compiling Models:
- You can compile your model into the format by using the following command:
```
py main.py [inputObjPlyFile] [outputBbmFile] [compressionMode]
                                              Integer (Compression):
                                                0 = None
                                                1 = BZ2
                                                2 = LZ4
                                                3 = ZStandard
                                                4 = ZLib
                                                5 = LZMA
```

## Rendering Model:
- You can render your compiled model by using command:
```
py renderer.py [inputBbmFile]
```
