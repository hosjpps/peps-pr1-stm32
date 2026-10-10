/* Задание 2 (вариант 7). Тест внешнего ПЗУ 8 Кбайт (27C64) для МК-51.
 * Подсчитывается контрольная сумма (сумма байт по модулю 256) области из
 * ROM_SIZE байт, начиная с адреса ROM_START, и сравнивается с эталоном
 * ROM_CHECKSUM, записанным в резидентной памяти программ МК (__code).
 * Совпала - ПЗУ исправно, иначе включается светодиод HL1 (P1.0).
 * Допущение: вывод OE ПЗУ подключён к RD (P3.7), поэтому ПЗУ читается
 * командой MOVX как внешняя память данных (так же, как ОЗУ). */
#include <8051.h>
#include "rom_checksum.h"   /* ROM_CHECKSUM - считает gen_rom.py по образу */

/* ---- параметры задания (при смене варианта менять только их) ---- */
#define ROM_START  0x0800   /* ZZZ - начальный адрес области ПЗУ       */
#define ROM_SIZE   100      /* K   - размер области, байт              */

#define LED        P1_0     /* HL1: 1 - горит (ошибка), 0 - погашен    */
#define RES_OK     0
#define RES_ERROR  1

/* эталон контрольной суммы - в резидентной памяти программ МК */
__code const unsigned char etalon = ROM_CHECKSUM;

volatile unsigned char result;      /* итог: RES_OK / RES_ERROR           */
volatile unsigned char calc_sum;    /* подсчитанная контрольная сумма     */

void main(void)
{
    unsigned int i;
    unsigned char sum = 0;  /* сумма по модулю 256 (перенос отбрасывается) */
    volatile __xdata unsigned char *ptr;  /* volatile: каждое чтение - RD */

    LED = 0;                /* после сброса P1 = FFh: гасим светодиод     */

    ptr = (volatile __xdata unsigned char *)ROM_START;
    for (i = 0; i < ROM_SIZE; i++) {
        sum += *ptr;        /* чтение байта ПЗУ: MOVX A,@DPTR (импульс RD) */
        ptr++;
    }
    calc_sum = sum;

    if (sum == etalon) {    /* сравнение с константой из резидентного ПЗУ */
        result = RES_OK;
        LED = 0;            /* контрольная сумма совпала: тест успешен    */
    } else {
        result = RES_ERROR;
        LED = 1;            /* не совпала: включить светодиод             */
    }
    while (1)
        ;
}
