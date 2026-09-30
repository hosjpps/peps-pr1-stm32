/*
 * Практическая работа № 1. Дополнительное задание:
 * сравнение плавающего входа и входа с подтягивающим резистором.
 *
 * Схема (как в базовой схеме преподавателя): кнопка BUTTON без фиксации
 * замыкает PA0 на GND, светодиод через резистор 220 Ом на PA1.
 * Кнопка при отпускании оставляет вход неподключённым, поэтому PA0
 * настроен как вход с внутренней подтяжкой к VDD (~40 кОм).
 *
 * Логика инверсная по входу: кнопка отпущена -> PA0 = 1 -> светодиод погашен;
 * кнопка нажата -> PA0 = 0 -> светодиод горит.
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
    SET_BIT(RCC->APB2ENR, RCC_APB2ENR_IOPAEN);

    /*
     * PA0 — вход с подтяжкой: MODE0 = 00, CNF0 = 10.
     * Направление подтяжки на STM32F1 задаёт бит ODR0: 1 — к VDD, 0 — к GND.
     */
    MODIFY_REG(GPIOA->CRL,
               GPIO_CRL_MODE0 | GPIO_CRL_CNF0,
               GPIO_CRL_CNF0_1);
    GPIOA->BSRR = GPIO_BSRR_BS0;

    /* PA1 — выход push-pull 2 МГц: MODE1 = 10, CNF1 = 00. */
    MODIFY_REG(GPIOA->CRL,
               GPIO_CRL_MODE1 | GPIO_CRL_CNF1,
               GPIO_CRL_MODE1_1);
    GPIOA->BSRR = GPIO_BSRR_BR1;

    while (1)
    {
        if (READ_BIT(GPIOA->IDR, GPIO_IDR_IDR0) == 0U)
        {
            GPIOA->BSRR = GPIO_BSRR_BS1;
        }
        else
        {
            GPIOA->BSRR = GPIO_BSRR_BR1;
        }
    }
}
