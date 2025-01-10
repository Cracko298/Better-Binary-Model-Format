# BBM
- Better Binary Model (BBM) is a 3D Model/Geometry Format for E.S. & Microcontrollers with very small file-sizes.
- It's also quite versitile, allowing for easy OBJ/PLY conversions, encryption, compression, and multiple models.
- Useful for Geometry as well in Game Development/Engines, and assets that are cruicial for your Game.
- No encryption information is stored in the Header (can affect sizing if enabled).

## Features:
- Easy-To-Understand Header.
- Standard Compression Algorithms or None at all.
- Multi-Model Support (yes it supports multiple models in the same file).
- Insanely small file-sizes (upto `95%` file-sizes reduction).
- No Quality Loss (yes, you heard it correctly).
- Dump Information on Models at Generation to be a Key pratically.
- Ability to encrypt your Models (not headers).

## Roadmap:
- Add Support for BBModel/JSON/BJSON Models.

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
                                                          │                                    ├─ AES      (AES256)
                                                          └─ Compression (Integer):            ├─ XOR      (XoR Cipher)
                                                             ├─ 0 = None                       ├─ ChaCha   (ChaCha20
                                                             ├─ 1 = BZ2                        └─ Blowfish (Blowfish)
                                                             ├─ 2 = LZ4
                                                             ├─ 3 = ZStandard
                                                             ├─ 4 = ZLib
                                                             └─ 5 = LZMA
```
### Example Command(s):
```
python .\generator.py .\model\myCoolTankModel.obj .\tank.bbm 5 "true" aes "myVeryCoolTankEncryptionKey"
python .\generator.py .\model\myCoolTankModel.obj
python .\generator.py .\models\groupOfModels\ .\myTankArmy.bbm 5 "true" xor "myArmyOfTanksWillBeTheCoolestThingSinceToothpaste"
python .\generator.py .\myCoolFolder\withWierdStuff\ C:\Users\Public\Documents\veryCoolModelCompilation.bbm
```

### Header Infomation:
```
00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F | Decoded Text
------------------------------------------------|-----------------
42 42 4D 01 16 1C 00 00 0B 21 00 00 00 00 05 00 | BBM......!......
08 51 01 00 00 00 00 00 84 8C 01 00 00 00 00 00 | .Q......„Œ......
63 61 72 00 00 00 00 00 00 00 00 00 00 00 00 00 | car.............

Bytes 00->02 = Format Tag
Byte  03     = OBJ/PLY/STL File Used
Bytes 04->07 = Vertex Count
Bytes 08->0B = Face Count
Bytes 0C->0D = Compression Mode
Bytes 0E->0F = Number of Models
Bytes 10->17 = Length of Vertex Data
Bytes 18->1F = Length of Face Data
Bytes 20->2F = NameTable
```



## Rendering Model:
- You can render your compiled model by using command:
```
py renderer.py [inputBbmFile]
```
