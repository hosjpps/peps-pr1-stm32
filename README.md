# Программирование электронных приборов и систем — практики

| Папка | Работа | Итог |
|---|---|---|
| `PR1_Proteus/` | ПР1 «Схема ввода-вывода в Proteus», вариант А (STM32F103C8), инд. вариант **1** (вход PA0, выход PA1) | `ПР1_Proteus_отчёт.docx`, `firmware/build/*.hex` |
| `PR1_Multisim/` | ПР1 «Основы Multisim» — схема стенда STM32F103C8 + 4 периферийных модуля (сделано в KiCad, методичка это разрешает) | `ПР1_Multisim_отчёт.docx`, `kicad/stand_stm32.pdf` |
| `tools/` | генератор схем KiCad (`kicad_gen.py`) и оформление отчётов по ГОСТ 7.32 (`report_docx.py`) | — |

Файлы `Практическая работа №4…` (Git/DevOps) и `Практическое занятие №1-2` (ML, kNN) — из других дисциплин, здесь не выполнялись.

## Что осталось сделать руками (Windows + Proteus)

В отчётах красным помечены места `[ВСТАВИТЬ …]`. Для ПР1 Proteus:

1. Proteus → New Project `PR1_STM32_GPIO_IO` (путь без кириллицы и пробелов).
2. Разместить: `STM32F103C8`, `SW-SPDT`, `RES` (220 Ом), `LED-GREEN`, терминалы POWER и GROUND.
3. Соединить как на `PR1_Proteus/kicad/pr1_gpio_io.pdf`: общий контакт SW-SPDT → PA0, верхний → POWER, нижний → GROUND; PA1 → R → анод LED, катод → GROUND; NRST → POWER, BOOT0 → GROUND; VDD/VDDA/VBAT → POWER, VSS/VSSA → GROUND.
4. Двойной щелчок по МК → **Program File** → `PR1_Proteus/firmware/build/PR1_STM32_GPIO_IO.hex` (готовый, CooCox не обязателен; если преподаватель требует сборку в CoIDE — вставить `firmware/src/main.c` в проект CoIDE с компонентами CMSIS, CMSIS BOOT, RCC, GPIO и собрать F7).
5. Запуск ▶, скриншоты: схема, окно Program File, ключ вниз (LED не горит), ключ вверх (LED горит).
6. Доп. задание: заменить SW-SPDT на `BUTTON` между PA0 и GROUND, прошивка `PR1_STM32_GPIO_IO_PULLUP.hex`, скриншот с нажатой кнопкой.

Для ПР1 Multisim: вставить ссылку на репозиторий (`REPO_URL` в `PR1_Multisim/gen_report.py`) и перегенерировать отчёт.

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
