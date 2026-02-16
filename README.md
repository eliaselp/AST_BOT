# 🤖 Bot de Trading Automático - Estrategia de Quiebre

Bot de trading automatizado para MetaTrader 5 que implementa una estrategia de quiebre de velas, con soporte para múltiples cuentas, gestión de riesgo automática y notificaciones por Telegram.

## 📋 Características

- Estrategia de Quiebre: Detecta cuando una vela quiebra el máximo o mínimo de la vela anterior
- Múltiples Cuentas: Soporte para operar en varias cuentas MT5 simultáneamente
- Gestión de Riesgo: Cálculo automático de lotes basado en el balance y riesgo configurado
- Control Temporal: Cierre automático de operaciones por tiempo de exposición
- Notificaciones: Alertas por Telegram de entradas y eventos importantes
- Modo Continuo: Ejecución 24/7 con verificación periódica según temporalidad
- Manejo de Errores: Sistema robusto de reintentos y validaciones

## 🏗️ Estructura del Proyecto

El proyecto está compuesto por varios módulos que trabajan en conjunto:

- Módulo principal que ejecuta el bot en modo continuo
- Módulo de configuración con todos los parámetros ajustables
- Módulo de estrategia que implementa la lógica de quiebre
- Módulo de conexión y operaciones con MetaTrader 5
- Módulo de notificaciones para Telegram
- Módulo de utilidades para manejo de tiempo y husos horarios

## ⚙️ Configuración General

La configuración del bot incluye varios aspectos fundamentales:

- Temporalidad principal de operación, que puede ser de 1 hora, 15 minutos o 5 minutos
- Ratio de riesgo beneficio para definir los take profits
- Porcentaje de riesgo por operación sobre el balance
- Máximo de operaciones simultáneas permitidas por cuenta
- Duración máxima en velas antes del cierre automático
- Modo de operación, pudiendo ser real o simulado para pruebas

## 📈 Estrategia de Trading

### Condiciones de Entrada

Para operaciones de compra o LONG, se requieren tres condiciones:
- La vela anterior debe ser alcista
- La vela actual debe superar el máximo de la vela anterior
- La vela actual debe mantener un soporte superior al mínimo anterior

Para operaciones de venta o SHORT, también se requieren tres condiciones:
- La vela anterior debe ser bajista
- La vela actual debe romper por debajo del mínimo de la vela anterior
- La vela actual debe mantener una resistencia inferior al máximo anterior

### Gestión de Riesgo

El sistema de gestión de riesgo incluye:
- Stop loss ubicado en el mínimo de la vela anterior para largos, o en el máximo para cortos
- Take profit calculado multiplicando la distancia del stop loss por el ratio configurado
- Tamaño de lote calculado automáticamente según el balance y el porcentaje de riesgo
- Cierre automático después de un número determinado de velas

## 🚀 Instalación y Uso

Para poner en funcionamiento el bot, se deben seguir estos pasos:

- Clonar el repositorio desde GitHub
- Instalar las dependencias necesarias
- Configurar los parámetros en el archivo de configuración
- Ejecutar el módulo principal

## 🎯 Temporalidades Soportadas

El bot puede operar en diferentes temporalidades:
- 1 minuto
- 5 minutos
- 15 minutos
- 30 minutos
- 1 hora, que es la recomendada
- 4 horas
- 1 día

## 📊 Notificaciones Telegram

El sistema de notificaciones envía alertas para:
- Inicio del bot
- Nuevas señales de entrada detectadas
- Resumen de operaciones ejecutadas
- Errores importantes durante la ejecución
- Detención del bot

## 🔧 Funcionalidades Técnicas

El bot incorpora varias funcionalidades técnicas avanzadas:

Un sistema de reintentos que realiza hasta mil intentos para abrir una operación, con pausas progresivas entre cada intento y validación de precios en tiempo real.

Un sistema de control de tiempo que cierra automáticamente las operaciones después de un número determinado de velas, con sincronización basada en el huso horario de Nueva York y verificación cada minuto.

Un sistema multi-cuenta que permite operar simultáneamente en múltiples cuentas, con control independiente para cada una y actualización del balance en tiempo real.

## ⚠️ Advertencias Importantes

- El trading automatizado conlleva riesgos y no garantiza ganancias
- Es fundamental probar el bot en cuenta demo antes de usarlo con dinero real
- Se recomienda supervisar el bot regularmente durante las primeras semanas
- Es necesario mantener una conexión estable a Internet y a MetaTrader 5

## 🔒 Seguridad

La seguridad es un aspecto fundamental:
- Las contraseñas se almacenan localmente en el archivo de configuración
- No se debe compartir el archivo de configuración con nadie
- Se recomienda usar cuentas demo para las pruebas iniciales

## 🆘 Soporte

Si se presentan problemas, se recomienda:
- Revisar los logs generados por el bot
- Verificar la conexión a MetaTrader 5
- Confirmar que la configuración de pares y cuentas sea correcta
- Consultar la documentación de cada módulo

## 📝 Consideraciones Finales

Este proyecto está diseñado para uso educativo y personal. El desarrollador no se responsabiliza por pérdidas financieras que puedan ocurrir durante su uso. Es responsabilidad del usuario entender completamente el funcionamiento del bot y los riesgos asociados al trading automatizado antes de utilizarlo.
