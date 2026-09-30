# Программирование электронных приборов и систем — практики

| Папка | Работа | Итог |
|---|---|---|
| `PR1_Proteus/` | ПР1 «Схема ввода-вывода в Proteus», вариант А (STM32F103C8), инд. вариант **1** (вход PA0, выход PA1) | `ПР1_Proteus_отчёт.docx`, `firmware/build/*.hex` |
| `PR1_Multisim/` | ПР1 «Основы Multisim» — схема стенда STM32F103C8 + 4 периферийных модуля (сделано в KiCad, методичка это разрешает) | `ПР1_Multisim_отчёт.docx`, `kicad/stand_stm32.pdf` |
| `tools/` | генератор схем KiCad (`kicad_gen.py`) и оформление отчётов по ГОСТ 7.32 (`report_docx.py`) | — |

Файлы `Практическая работа №4…` (Git/DevOps) и `Практическое занятие №1-2` (ML, kNN) — из других дисциплин, здесь не выполнялись.

## Моделирование без Windows

Proteus работает только под Windows, поэтому ПР1 смоделирована в [Wokwi](https://wokwi.com) (модель Blue Pill, тот же STM32F103C8): `PR1_Proteus/wokwi/diagram.json` (SA1 + светодиод) и `diagram_pullup.json` (кнопка, доп. задание). Как повторить: открыть любой Blue Pill-проект Wokwi (например, https://wokwi.com/projects/374772127111874561), вставить содержимое diagram.json во вкладку diagram.json, F1 → «Upload Firmware and Start Simulation…» → выбрать `firmware/build/*.hex`, щёлкать переключатель/кнопку.

Грабли Wokwi: нижний вывод `3V3.1` платы в модели не питается — брать `3V3.2` и `GND.2/GND.3` (верхний ряд).

Если нужен именно Proteus: схема по `PR1_Proteus/kicad/pr1_gpio_io.pdf`, в поле Program File — тот же `.hex`.

ФИО, группа, преподаватель — константы в начале каждого `gen_report.py`; «Разраб.» в основной надписи схем — второй элемент `comments=[...]` в `kicad/gen_schematic.py`.

## Пересборка

Нужны: KiCad 10 (`~/Applications/KiCad`), Arm GNU Toolchain (`~/tools/armgcc/pkg/Payload/bin` в PATH), `uv`, `pdftoppm`, python-docx, Pillow.

```sh
# прошивки + проверка на эмуляторе Cortex-M3
cd PR1_Proteus/firmware  && make && uv run --with unicorn --with pyelftools python emulate_gpio.py
cd PR1_Multisim/firmware && make && uv run --with unicorn --with pyelftools python emulate_stand.py
# схемы: генерация + сверка netlist + ERC + PDF/PNG
cd PR1_Proteus/kicad  && python3 gen_schematic.py
cd PR1_Multisim/kicad && python3 gen_schematic.py
# отчёты
python3 PR1_Proteus/gen_report.py && python3 PR1_Multisim/gen_report.py
```

## Решения, которые не видны из кода

- **Вариант 1** выбран, потому что номер варианта неизвестен, а базовая схема и код преподавателя — ровно PA0/PA1. Смена варианта: пины в `firmware/src/main.c` (CRL для линий 0–7, CRH для 8–15, тактирование нужного порта) и в `kicad/gen_schematic.py`.
- **CMSIS:** в CooCox используется `stm32f10x.h` (StdPeriph v3.5), для сборки вне CoIDE — официальный `cmsis_device_f1` от ST через обёртку `compat/stm32f10x.h`; имена регистров/битов совпадают. Найденные на GitHub «stm32f10x.h» оказались самодельными урезанными копиями — не брать.
- **Линкер:** шаблон ST `STM32F103XB_FLASH.ld` рассчитан на 128 КБ; для C8 исправлено на 64 КБ. Ключ `-nostartfiles` ломает `__libc_init_array` (нет `_init`).
- **Схемы проверяются по netlist, не по картинке:** `gen_schematic.py` падает с кодом 1, если цепи не совпали с ожидаемыми или ERC нашёл ошибку. Символ STM32F103C8Tx в библиотеке KiCad наследуется (`extends`), поэтому встраивается базовый `STM32F103C_8-B_Tx`.
