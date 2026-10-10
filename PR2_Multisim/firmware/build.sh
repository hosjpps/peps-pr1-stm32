#!/bin/sh
# Сборка обоих тестов компилятором SDCC (модель small, МК-51). Запуск: sh build.sh
cd "$(dirname "$0")" || exit 1
python3 gen_rom.py || exit 1
mkdir -p build
for n in ram_test rom_test; do
    sdcc -mmcs51 --model-small -Isrc --std-sdcc11 -o build/$n.ihx src/$n.c || exit 1
done
# вариант теста ОЗУ с другим тестовым набором (демонстрация параметризации)
sdcc -mmcs51 --model-small -Isrc --std-sdcc11 -DTEST_BYTE=0x55 -o build/ram_test_55.ihx src/ram_test.c || exit 1
rm -f build/*.asm build/*.lk build/*.mem build/*.rel build/*.rst build/*.sym build/*.cdb build/*.omf build/*.adb
for f in build/*.ihx; do cp "$f" "${f%.ihx}.hex"; done   # те же файлы с расширением .hex (Intel HEX)
ls -l build
