### **Estrategia de Trading Algorítmico: "Reversión por Divergencia RSI Confirmada v1.0"**

**Filosofía:** Identificar y operar reversiones alcistas de alta probabilidad en mercados volátiles. La estrategia se basa en la detección de agotamiento del momentum vendedor (Divergencia RSI) y exige múltiples confirmaciones de calidad (extremo estadístico, volumen y calidad de la entrada) antes de arriesgar capital.

---

### **I. Parámetros y Configuración**

- **Activo:** BTC/USD (o similar)
- **Timeframe de Operación:** H1 / M15
- **Comisión del Exchange (por transacción):** fee_rate = 0.001 (equivalente al 0.1%)

**A. Indicadores Base:**

- RSI: rsi_period = 14
- Bandas de Bollinger (BB): bb_period = 20, bb_std_dev = 2
- Average True Range (ATR): atr_period = 14
- Media Móvil Exponencial (EMA): ema_period = 200
- Indicador %B: Derivado de las Bandas de Bollinger.

**B. Parámetros de Detección de Pivotes:**

- Ventana de Búsqueda de Pivote RSI: pivot_lookback_window = 12
- Velas de Confirmación de Pivote de Precio: confirmation_wait_candles = 3
- Distancia Mínima entre Pivotes: min_distance_between_pivots = 20

---

### **II. Lógica de Entrada: Cascada de Filtros**

Una orden de compra se considera **potencialmente válida** únicamente si se cumplen secuencialmente **todos** los siguientes filtros:

1. **Filtro 1: Detección de la Divergencia:** El algoritmo confirma una **Divergencia Alcista Clásica** válida en el RSI según los parámetros definidos. Se identifica un Pivote A y un Pivote B (el más reciente).
2. **Filtro 2: Extremo Estadístico (%B):** El valor del indicador %B en la vela del Pivote B debe haber sido **menor o igual a 0.1**.
    - Formula: %B_at_Pivot_B <= 0.1
3. **Filtro 3: Confirmación de Volumen:** Dentro de las confirmation_wait_candles usadas para validar el precio del Pivote B, debe haber aparecido al menos una vela alcista (verde) cuyo volumen sea superior a 1.5 veces el volumen promedio de las últimas 5 velas bajistas (rojas).
    - Formula: Volumen_Vela_Verde > 1.5 * Promedio(Volumen_5_Velas_Rojas_Anteriores)
4. **Filtro 4: Tendencia Mayor (Opcional - Perfil Conservador):** El precio en el momento de la señal debe estar por encima de la EMA de 200. Activar este filtro reduce el riesgo, pero también el número de operaciones.

Si todos estos filtros son positivos, el bot procede a la fase de **Gestión de Riesgo Pre-Operación**.

---

### **III. Gestión de Riesgo Pre-Operación**

Antes de ejecutar cualquier orden, el bot debe validar que la operación es económicamente viable.

**A. Definición de Parámetros de la Operación Potencial:**

- Precio_Entrada: Precio de cierre de la última vela de confirmación.
- Precio_SL_Teorico: Precio Mínimo del Pivote B - Valor del ATR(14) en ese momento.
- Precio_TP1_Teorico: Valor actual de la Banda Central de Bollinger (SMA 20).
- Riesgo_Maximo_Por_Operacion: risk_percentage = 0.01 (1% del capital total).

**B. Filtro de Calidad (Ratio Riesgo/Beneficio Real):**

Esta es la prueba final de viabilidad. Se deben incluir las comisiones para una evaluación honesta.

1. **Cálculo del Riesgo Real por Unidad:**
    - Costo_Total_Entrada = Precio_Entrada * (1 + fee_rate)
    - Ingreso_Neto_SL = Precio_SL_Teorico * (1 - fee_rate)
    - Riesgo_Real = Costo_Total_Entrada - Ingreso_Neto_SL
2. **Cálculo de la Recompensa Real por Unidad (hasta TP1):**
    - Ingreso_Neto_TP1 = Precio_TP1_Teorico * (1 - fee_rate)
    - Recompensa_Real = Ingreso_Neto_TP1 - Costo_Total_Entrada
3. **Decisión Final de Entrada:**
    - Ratio_RR_Real = Recompensa_Real / Riesgo_Real
    - **Regla:** La operación se ejecuta **únicamente si Ratio_RR_Real >= 1.5**. De lo contrario, la señal se descarta por ser de baja calidad económica.

**C. Cálculo del Tamaño de la Posición:**

Si la operación pasa el filtro de calidad, se calcula el tamaño de la posición.

- Capital_Total: El capital actual de la cuenta.
- Riesgo_en_USD = Capital_Total * risk_percentage
- **Fórmula Tamaño de Posición (en BTC):** Tamaño_Posicion = Riesgo_en_USD / Riesgo_Real

---

### **IV. Gestión de la Operación Activa**

Una vez la orden se ha ejecutado, se aplican las siguientes reglas de salida:

**A. Stop Loss Inicial:**

- El Stop Loss se coloca inmediatamente en el Precio_SL_Teorico calculado anteriormente.

**B. Estrategia de Take Profit Híbrida:**

- **Fase 1: Asegurar Ganancias (TP1):**
    - **Objetivo:** La Banda Central de Bollinger (SMA 20).
    - **Acción:** Cuando el precio toque la banda central, **vender el 50% de la posición**.
    - **Movimiento Clave (Breakeven Real):** Inmediatamente después, mover el Stop Loss del 50% restante a un precio que cubra los costos de transacción.
        - **Fórmula SL Breakeven:** SL_Breakeven = (Precio_Entrada * (1 + fee_rate)) / (1 - fee_rate)
- **Fase 2: Maximizar Potencial (TP2):**
    - **Objetivo:** La Banda Superior de Bollinger (o %B >= 1).
    - **Acción:** Cuando el precio toque este objetivo, cerrar el 50% restante de la posición.

**C. Salida por Tiempo (Time Stop):**

- **Regla de Seguridad:** Para evitar que una operación quede estancada indefinidamente, se establece una salida por tiempo.
    - **Parámetro:** max_candles_open = 48 (ej. 48 velas en H1 = 2 días).
    - **Acción:** Si la operación no ha alcanzado ni el SL ni el TP2 después de max_candles_open, se cierra manualmente al precio de mercado. Se recomienda un análisis posterior de estas operaciones para refinar la estrategia.