# BBM
- Better Binary Model Format is a Model format that's extremely lightweight, easy-to-use, and resource/storage conscientious.

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
- Even without compression the Models are almost always less than 18-19% of the original model file-size (415kb file to just 75kb).
- With compression it gets even better with nearly 4-6% of the original model file-size (turning a 415kb file to just 18kb).

## Rendering Model:
- You can render your compiled model by using command:
```
py renderer.py [inputBbmFile]
```
