# BBM
- Better Binary Model (BBM) is a 3D Geometry/Model Format for Embedded Systems and Microcontrollers with very low file-sizes.

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
- Without compression Models are almost always less than 18-19% of the og model file-size `(415kb -> 75kb)`.
- With compression it gets even better with nearly 4-6% of the og model file-size `(415kb -> 18kb)`.

## Rendering Model:
- You can render your compiled model by using command:
```
py renderer.py [inputBbmFile]
```
