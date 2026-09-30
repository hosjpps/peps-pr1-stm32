/*
 * Сборка вне CooCox CoIDE. В CoIDE заголовок stm32f10x.h приходит с
 * компонентом CMSIS BOOT (StdPeriph v3.5). Здесь его роль играет официальный
 * CMSIS от ST (cmsis_device_f1): имена регистров и битов в нём те же.
 */
#ifndef STM32F10X_COMPAT_H
#define STM32F10X_COMPAT_H
#include "stm32f1xx.h"
#endif
