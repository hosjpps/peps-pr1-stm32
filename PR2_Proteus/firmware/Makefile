# Сборка прошивок STM32F103C8 для Proteus: make  ->  build/*.hex
CC      = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy
SIZE    = arm-none-eabi-size

CFLAGS  = -mcpu=cortex-m3 -mthumb -O0 -g -Wall -Wextra -std=c11 \
          -DSTM32F103xB -Icompat -Icmsis
LDFLAGS = -mcpu=cortex-m3 -mthumb -TSTM32F103C8_FLASH.ld \
          --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections

COMMON  = cmsis/startup_stm32f103xb.s cmsis/system_stm32f1xx.c
TARGETS = PR2_STM32_I2C

all: $(TARGETS:%=build/%.hex)

build/PR2_STM32_I2C.elf: src/main.c $(COMMON)

build/%.elf:
	@mkdir -p build
	$(CC) $(CFLAGS) $(LDFLAGS) $^ -o $@ -Wl,-Map=$(@:.elf=.map)
	$(SIZE) $@

build/%.hex: build/%.elf
	$(OBJCOPY) -O ihex $< $@

clean:
	rm -rf build

.PHONY: all clean
