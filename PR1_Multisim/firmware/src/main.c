/*
 * Практическая работа № 1. Учебный стенд на STM32F103C8 (схема ПР1.ПЭПС.002 Э3).
 *
 * Периферия:
 *   PA0  (цепь 1) — кнопка SB1 на GND, внешняя подтяжка R3 10 кОм к +3V3;
 *   PA1  (цепь 2) — светодиод HL1 через R4 330 Ом;
 *   PA2  (цепь 3) — светодиод HL2 через R5 330 Ом;
 *   PA4  (цепь 4) — движок потенциометра RP1, канал ADC1_IN4;
 *   PA8  (цепь 5) — база ключа VT1 через R6 1 кОм, выход TIM1_CH1 (ШИМ зуммера HA1).
 *
 * Логика:
 *   кнопка нажата  -> HL1 горит, зуммер звучит; тон задаётся потенциометром
 *                     (от ~1 кГц до ~4 кГц);
 *   RP1 выше середины шкалы (АЦП > 2047) -> HL2 горит.
 *
 * Частота ядра берётся из SystemCoreClock: при сборке с system_stm32f1xx.c от ST
 * это HSI 8 МГц, в CooCox (system_stm32f10x.c, SYSCLK_FREQ_72MHz) — HSE 8 МГц (ZQ1)
 * через PLL = 72 МГц. Делители АЦП и TIM1 рассчитываются так, чтобы работа
 * не зависела от этого выбора.
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

#define ADC_MID        2047U
#define TIM1_TICK_HZ   1000000U   /* SystemCoreClock / (PSC + 1) */

static void gpio_init(void)
{
    SET_BIT(RCC->APB2ENR, RCC_APB2ENR_IOPAEN);

    /* PA0 — плавающий вход (подтяжка внешняя, R3): MODE0 = 00, CNF0 = 01 */
    MODIFY_REG(GPIOA->CRL, GPIO_CRL_MODE0 | GPIO_CRL_CNF0, GPIO_CRL_CNF0_0);

    /* PA1, PA2 — выходы push-pull 2 МГц: MODE = 10, CNF = 00 */
    MODIFY_REG(GPIOA->CRL, GPIO_CRL_MODE1 | GPIO_CRL_CNF1, GPIO_CRL_MODE1_1);
    MODIFY_REG(GPIOA->CRL, GPIO_CRL_MODE2 | GPIO_CRL_CNF2, GPIO_CRL_MODE2_1);

    /* PA4 — аналоговый вход: MODE4 = 00, CNF4 = 00 */
    CLEAR_BIT(GPIOA->CRL, GPIO_CRL_MODE4 | GPIO_CRL_CNF4);

    /* PA8 — альтернативная функция push-pull 2 МГц (TIM1_CH1): MODE8 = 10, CNF8 = 10 */
    MODIFY_REG(GPIOA->CRH, GPIO_CRH_MODE8 | GPIO_CRH_CNF8, GPIO_CRH_MODE8_1 | GPIO_CRH_CNF8_1);

    GPIOA->BSRR = GPIO_BSRR_BR1 | GPIO_BSRR_BR2;
}

static void adc_init(void)
{
    /* ADCCLK = PCLK2 / 6: 12 МГц при 72 МГц, 1.33 МГц при 8 МГц (допустимо не более 14 МГц) */
    MODIFY_REG(RCC->CFGR, RCC_CFGR_ADCPRE, RCC_CFGR_ADCPRE_DIV6);
    SET_BIT(RCC->APB2ENR, RCC_APB2ENR_ADC1EN);

    /* Канал 4 — единственный в последовательности, время выборки 239.5 такта */
    ADC1->SQR3 = 4U;
    MODIFY_REG(ADC1->SMPR2, ADC_SMPR2_SMP4, ADC_SMPR2_SMP4);

    volatile uint32_t i;
    SET_BIT(ADC1->CR2, ADC_CR2_ADON);
    for (i = 0; i < 100U; i++) { }   /* t_STAB >= 1 мкс */

    SET_BIT(ADC1->CR2, ADC_CR2_CAL);
    while (READ_BIT(ADC1->CR2, ADC_CR2_CAL) != 0U) { }
}

static uint16_t adc_read(void)
{
    /* Повторная запись ADON при включённом АЦП запускает преобразование */
    SET_BIT(ADC1->CR2, ADC_CR2_ADON);
    while (READ_BIT(ADC1->SR, ADC_SR_EOC) == 0U) { }
    return (uint16_t)ADC1->DR;   /* чтение DR сбрасывает EOC */
}

static void pwm_init(void)
{
    SET_BIT(RCC->APB2ENR, RCC_APB2ENR_TIM1EN);

    /* TIM1 тактируется от PCLK2 = HCLK (делитель APB2 = 1 в обоих вариантах SystemInit) */
    TIM1->PSC = (SystemCoreClock / TIM1_TICK_HZ) - 1U;
    TIM1->ARR = 499U;                      /* 2 кГц до первого чтения АЦП */
    TIM1->CCR1 = 250U;

    /* Канал 1 — ШИМ режим 1 с предзагрузкой CCR1 */
    MODIFY_REG(TIM1->CCMR1, TIM_CCMR1_OC1M | TIM_CCMR1_CC1S,
               TIM_CCMR1_OC1M_2 | TIM_CCMR1_OC1M_1 | TIM_CCMR1_OC1PE);
    SET_BIT(TIM1->CR1, TIM_CR1_ARPE);

    /* У расширенного таймера TIM1 выходы разрешаются ещё и битом MOE */
    SET_BIT(TIM1->BDTR, TIM_BDTR_MOE);
    SET_BIT(TIM1->EGR, TIM_EGR_UG);
    SET_BIT(TIM1->CR1, TIM_CR1_CEN);
}

static void buzzer(uint32_t on, uint16_t adc)
{
    if (on != 0U)
    {
        /* Период 1000..250 мкс -> тон 1..4 кГц, скважность 50 % */
        uint32_t period = 1000U - ((uint32_t)adc * 750U) / 4095U;
        TIM1->ARR = period - 1U;
        TIM1->CCR1 = period / 2U;
        SET_BIT(TIM1->CCER, TIM_CCER_CC1E);
    }
    else
    {
        CLEAR_BIT(TIM1->CCER, TIM_CCER_CC1E);
    }
}

int main(void)
{
    SystemCoreClockUpdate();
    gpio_init();
    adc_init();
    pwm_init();

    while (1)
    {
        uint16_t pot = adc_read();
        uint32_t pressed = (READ_BIT(GPIOA->IDR, GPIO_IDR_IDR0) == 0U);

        GPIOA->BSRR = pressed ? GPIO_BSRR_BS1 : GPIO_BSRR_BR1;
        GPIOA->BSRR = (pot > ADC_MID) ? GPIO_BSRR_BS2 : GPIO_BSRR_BR2;
        buzzer(pressed, pot);
    }
}
