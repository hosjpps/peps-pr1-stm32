/*
 * Практическая работа № 1. Схема ввода-вывода в Proteus.
 * Вариант А (STM32F1), индивидуальный вариант 1:
 *   PA0 — вход от переключателя SW-SPDT (порт GPIOA, регистр CRL);
 *   PA1 — выход на светодиод через резистор 220 Ом (порт GPIOA, регистр CRL).
 * Логика: на PA0 логическая 1 -> светодиод горит, логический 0 -> погашен
 * (активный высокий уровень: анод через резистор к PA1, катод на GND).
 */
#include "stm32f10x.h"

#ifndef SET_BIT
#define SET_BIT(REG, BIT)     ((REG) |= (BIT))
#endif

#ifndef CLEAR_BIT
#define CLEAR_BIT(REG, BIT)   ((REG) &= ~(BIT))
#endif

#ifndef READ_BIT
#define READ_BIT(REG, BIT)    ((REG) & (BIT))
#endif

#ifndef MODIFY_REG
#define MODIFY_REG(REG, CLEARMASK, SETMASK) \
    do {                                     \
        CLEAR_BIT((REG), (CLEARMASK));       \
        SET_BIT((REG), (SETMASK));           \
    } while (0)
#endif

int main(void)
{
    /* Тактирование порта GPIOA: без него запись в CRL/BSRR игнорируется. */
    SET_BIT(RCC->APB2ENR, RCC_APB2ENR_IOPAEN);

    /*
     * PA0 — плавающий цифровой вход: MODE0 = 00, CNF0 = 01.
     * Подтяжка не нужна: SW-SPDT всегда явно подаёт на вход VDD или GND.
     */
    MODIFY_REG(GPIOA->CRL,
               GPIO_CRL_MODE0 | GPIO_CRL_CNF0,
               GPIO_CRL_CNF0_0);

    /* PA1 — выход push-pull 2 МГц: MODE1 = 10, CNF1 = 00. */
    MODIFY_REG(GPIOA->CRL,
               GPIO_CRL_MODE1 | GPIO_CRL_CNF1,
               GPIO_CRL_MODE1_1);

    /* Исходное состояние — светодиод погашен. */
    GPIOA->BSRR = GPIO_BSRR_BR1;

    while (1)
    {
        /* BSRR атомарно ставит/сбрасывает один вывод без чтения ODR. */
        if (READ_BIT(GPIOA->IDR, GPIO_IDR_IDR0) != 0U)
        {
            GPIOA->BSRR = GPIO_BSRR_BS1;
        }
        else
        {
            GPIOA->BSRR = GPIO_BSRR_BR1;
        }
    }
}
