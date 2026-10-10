/* Задание 1 (вариант 1). Тест внешнего ОЗУ 8 Кбайт (6264) для МК-51.
 * В каждую из CELLS ячеек, начиная с адреса START_ADDR, записывается
 * тестовый набор TEST_BYTE, затем ячейка читается и сравнивается с
 * записанным значением. При первом несовпадении проверка прекращается
 * и включается светодиод HL1 на выводе P1.0. */
#include <8051.h>

/* ---- параметры задания (при смене варианта менять только их;
        ключом компилятора -D... значение можно переопределить) ---- */
#ifndef TEST_BYTE
#define TEST_BYTE  0xAA     /* XX  - тестовый набор                    */
#endif
#ifndef START_ADDR
#define START_ADDR 0x0800   /* ZZZ - начальный адрес области ОЗУ       */
#endif
#ifndef CELLS
#define CELLS      1024     /* размер области, ячеек (1 Кбайт)         */
#endif

#define LED        P1_0     /* HL1: 1 - горит (ошибка), 0 - погашен    */
#define RES_OK     0
#define RES_ERROR  1

volatile unsigned char result;      /* итог: RES_OK / RES_ERROR           */
volatile unsigned int  checked;     /* сколько ячеек проверено успешно    */
volatile unsigned int  error_addr;  /* адрес первой ячейки с ошибкой      */

void main(void)
{
    unsigned int i;
    unsigned char test;             /* значение, считанное из ячейки      */
    /* Указатель на ячейку внешней памяти данных (XDATA). volatile - иначе
       компилятор заменит чтение ОЗУ только что записанным значением. */
    volatile __xdata unsigned char *ptr;
    /* Тестовый набор. volatile - иначе SDCC свернёт сравнение с
       константой и выбросит команду чтения ОЗУ (проверено по листингу). */
    volatile unsigned char nabor = TEST_BYTE;

    LED = 0;              /* после сброса P1 = FFh: гасим светодиод       */
    result = RES_OK;
    checked = 0;
    error_addr = 0;

    ptr = (volatile __xdata unsigned char *)START_ADDR;
    for (i = 0; i < CELLS; i++) {
        *ptr = nabor;     /* запись: MOVX @DPTR,A (импульс WR, P3.6)      */
        test = *ptr;      /* чтение: MOVX A,@DPTR (импульс RD, P3.7)      */
        if (test != nabor) {    /* считано не то, что записано: ошибка    */
            result = RES_ERROR;
            error_addr = (unsigned int)ptr;
            break;
        }
        checked++;
        ptr++;            /* следующая ячейка                             */
    }

    LED = (result != RES_OK);   /* 1 - ошибка ОЗУ, 0 - ОЗУ исправно       */
    while (1)                   /* конец: остановка для наблюдения        */
        ;
}
