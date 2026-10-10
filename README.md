# Программирование электронных приборов и систем — практики

Васин С.А., ЭФБО-17-24

| Папка | Работа |
|---|---|
| `PR1_Proteus/` | ПР1 «Создание микроконтроллерной схемы ввода-вывода», вариант А (STM32F103C8), инд. вариант 1: вход PA0, выход PA1 |
| `PR1_Multisim/` | ПР1 «Основы работы с ПО для проектирования схем» — учебный стенд STM32F103C8 + 4 периферийных модуля (схема в KiCad) |
| `PR2_Proteus/` | ПР2 «Подключение внешней памяти и периферии» — STM32F103C8 + EEPROM 24LC64 + DS1307 по I²C, вариант 1 |
| `PR2_Multisim/` | ПР2 «Подключение внешней памяти и её тестирование» — 8051 + внешние ОЗУ и ПЗУ, вариант 1 (ОЗУ) и 7 (ПЗУ) |
| `tools/` | генерация схем и отчётов |

## Состав

- `firmware/src/` — программы на Си, `firmware/build/*.hex` — файлы прошивки.
- `kicad/` — проект и схема KiCad, лист с основной надписью по ГОСТ (`*.pdf`).
- `PR1_Proteus/wokwi/` — модель для симулятора Wokwi и результаты моделирования.

Заголовок `stm32f10x.h` в CooCox CoIDE подключается компонентом CMSIS BOOT. Для сборки вне CoIDE используется официальный CMSIS от ST (`firmware/cmsis/`) через обёртку `firmware/compat/stm32f10x.h` — имена регистров и битов те же.

## Моделирование

Proteus работает только под Windows, поэтому ПР1 смоделирована в [Wokwi](https://wokwi.com) (плата Blue Pill, STM32F103C8) с тем же `.hex`, который указывается в Proteus в поле Program File:

1. Открыть Blue Pill-проект Wokwi, например https://wokwi.com/projects/374772127111874561.
2. Вставить `PR1_Proteus/wokwi/diagram.json` (или `diagram_pullup.json` для доп. задания) во вкладку diagram.json.
3. F1 → «Upload Firmware and Start Simulation…» → `PR1_Proteus/firmware/build/PR1_STM32_GPIO_IO.hex` (или `…_PULLUP.hex`).

## Сборка и проверка

Нужны: arm-none-eabi-gcc, KiCad 10 (kicad-cli), Python 3 с python-docx и Pillow, `uv`.

```sh
# прошивки + проверка на эмуляторе ядра Cortex-M3
cd PR1_Proteus/firmware  && make && uv run --with unicorn --with pyelftools python emulate_gpio.py
cd PR1_Multisim/firmware && make && uv run --with unicorn --with pyelftools python emulate_stand.py
# схемы: построение, сверка списка цепей (netlist) и ERC, экспорт PDF/PNG
cd PR1_Proteus/kicad  && python3 gen_schematic.py
cd PR1_Multisim/kicad && python3 gen_schematic.py
# ПР2: I²C — эмуляция прошивки с моделями шины, временные диаграммы, схема
cd PR2_Proteus/firmware && make && uv run --with unicorn --with pyelftools --with matplotlib python emulate_i2c.py \
  && uv run --with matplotlib python plot_i2c.py
cd ../schematic && python3 draw.py
```

Скрипты схем завершаются с ошибкой, если соединения не совпали с заданными или ERC нашёл нарушения.
