//+------------------------------------------------------------------+
//|                                           JSONFileEA.mq5         |
//|                                      Lectura desde archivo JSON  |
//+------------------------------------------------------------------+
#property copyright "Elias Eduardo Liranza Perez"
#property version   "3.16"
#property strict
#property description "EA que recibe señales vía archivo JSON y ejecuta operaciones"
#property description "con gestión de riesgo y sistema de reintentos"

//--- Input parameters - ARCHIVO
input group "=== CONFIGURACIÓN DE ARCHIVO ==="
input string   JsonFilePath     = "D:\\signals\\senal.json";  // Ruta del archivo JSON
input int      FileCheckInterval = 1;           // Intervalo de revisión (segundos)

//--- Input parameters - GESTIÓN DE RIESGO
input group "=== GESTIÓN DE RIESGO ==="
input double   BalanceReferencia = 0;          // 0 = usar balance real
input double   RiskPercent       = 1.0;        // % de riesgo por operación
input double   MaxRiskMoney      = 0;          // 0 = sin límite máximo

//--- Input parameters - EJECUCIÓN
input group "=== CONFIGURACIÓN DE EJECUCIÓN ==="
input bool     AutoTrade         = true;
input int      MaxOpenAttempts    = 10;        // Máx intentos para abrir
input int      MaxModifyAttempts  = 10;        // Máx intentos para SL/TP
input int      Deviation          = 10;        // Desviación permitida
input ENUM_ORDER_TYPE_FILLING FillingType = ORDER_FILLING_FOK;  // Tipo de filling
input int      MagicNumber        = 234000;    // Magic number del EA

//--- Input parameters - VALIDACIONES
input group "=== VALIDACIONES ==="
input bool     ValidateSymbol     = false;     // Validar símbolo de la señal
input double   MinSLPoints        = 0;         // Mínimo SL en puntos
input double   MinTPPoints        = 0;         // Mínimo TP en puntos
input double   MaxSpreadPoints    = 0;         // 0 = sin límite
input bool     CheckFreeMargin    = true;      // Verificar margen libre
input double   MaxMarginUse       = 95.0;      // % Máx de margen a usar

//--- Input parameters - DEBUG
input group "=== CONFIGURACIÓN DE DEBUG ==="
input bool     DebugMode          = true;      // Modo debug con logs detallados
input bool     LogJsonContent     = true;      // Mostrar contenido JSON completo
input bool     LogEverySecond     = true;      // Mostrar log cada segundo

//--- Global variables
string lastSignalUUID = "";  // Variable global para almacenar el último UUID procesado
datetime lastFileCheck = 0;
int totalSignals = 0;
int totalTrades = 0;
bool isFirstRun = true;
int timerCounter = 0;        // Contador para mostrar logs periódicos

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("╔══════════════════════════════════════════════════════════════════════════╗");
   Print("║                    🚀 JSON FILE EA - VERSIÓN 3.16                        ║");
   Print("║                    📊 LOGS EXHAUSTIVOS - TODOS LOS PASOS                 ║");
   Print("╚══════════════════════════════════════════════════════════════════════════╝");
   
   // Validar parámetros
   if(!ValidateInputs())
      return INIT_PARAMETERS_INCORRECT;
   
   // MOSTRAR INFORMACIÓN DETALLADA DE LA RUTA
   Print("📁 RUTA CONFIGURADA: ", JsonFilePath);
   Print("📁 VERIFICANDO EXISTENCIA DEL ARCHIVO...");
   
   // Verificar si el archivo existe
   bool fileExists = FileExists(JsonFilePath);
   Print("   ¿FileIsExist() devuelve? ", fileExists ? "SÍ" : "NO");
   
   if(!fileExists)
   {
      Print("⚠️ El archivo NO existe en la ruta: ", JsonFilePath);
      Print("   Esperando a que el script Python lo cree...");
      Print("   Verifica que:");
      Print("     1. La carpeta D:\\signals existe");
      Print("     2. El script Python está corriendo");
      Print("     3. La ruta en el script Python es exactamente: ", JsonFilePath);
   }
   else
   {
      Print("✅ Archivo JSON ENCONTRADO: ", JsonFilePath);
      
      // Intentar abrir el archivo para verificar permisos
      Print("📁 VERIFICANDO PERMISOS DE LECTURA...");
      int testHandle = FileOpen(JsonFilePath, FILE_READ|FILE_TXT|FILE_ANSI);
      if(testHandle != INVALID_HANDLE)
      {
         Print("   ✅ Archivo ABIERTO correctamente para lectura");
         ulong fileSize = FileSize(testHandle);
         Print("   📏 Tamaño del archivo: ", fileSize, " bytes");
         
         if(fileSize > 0)
         {
            string testContent = FileReadString(testHandle, (int)MathMin(fileSize, 200));
            Print("   📝 Contenido (primeros 200 chars):");
            Print("   '", testContent, "'");
         }
         else
         {
            Print("   ⚠️ El archivo está VACÍO (0 bytes)");
         }
         
         FileClose(testHandle);
         Print("   ✅ Archivo cerrado correctamente");
      }
      else
      {
         int error = GetLastError();
         Print("   ❌ NO se puede abrir el archivo. Error: ", error, " - ", GetErrorDescription(error));
      }
   }
   
   Print("📊 Configuración de riesgo:");
   Print("   Balance referencia: ", (BalanceReferencia > 0 ? DoubleToString(BalanceReferencia, 2) : "Balance real"));
   Print("   Riesgo: ", RiskPercent, "%");
   Print("   Intentos apertura: ", MaxOpenAttempts);
   Print("   Intentos SL/TP: ", MaxModifyAttempts);
   Print("   Archivo JSON: ", JsonFilePath);
   Print("   Modo Debug: ", DebugMode ? "ACTIVADO" : "DESACTIVADO");
   Print("   Log JSON: ", LogJsonContent ? "ACTIVADO" : "DESACTIVADO");
   Print("   Log cada segundo: ", LogEverySecond ? "ACTIVADO" : "DESACTIVADO");
   
   Print("⏱️ Timer configurado cada ", FileCheckInterval, " segundo(s)");
   Print("📢 VERIFICANDO ARCHIVO CADA SEGUNDO EN: ", JsonFilePath);
   
   EventSetTimer(FileCheckInterval);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Validar parámetros de entrada                                   |
//+------------------------------------------------------------------+
bool ValidateInputs()
{
   bool valid = true;
   
   if(RiskPercent <= 0 || RiskPercent > 100)
   {
      Print("❌ RiskPercent debe estar entre 0.01 y 100");
      valid = false;
   }
   
   if(MaxOpenAttempts < 1 || MaxModifyAttempts < 1)
   {
      Print("❌ Los intentos deben ser >= 1");
      valid = false;
   }
   
   if(MinSLPoints < 0 || MinTPPoints < 0)
   {
      Print("❌ MinSLPoints y MinTPPoints no pueden ser negativos");
      valid = false;
   }
   
   if(MaxMarginUse <= 0 || MaxMarginUse > 100)
   {
      Print("❌ MaxMarginUse debe estar entre 1 y 100");
      valid = false;
   }
   
   if(JsonFilePath == "")
   {
      Print("❌ La ruta del archivo JSON no puede estar vacía");
      valid = false;
   }
   
   return valid;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("╔══════════════════════════════════════════════════════════════════════════╗");
   Print("║                           📊 ESTADÍSTICAS FINALES                        ║");
   Print("╠══════════════════════════════════════════════════════════════════════════╣");
   Print("║   Señales recibidas: ", totalSignals);
   Print("║   Operaciones ejecutadas: ", totalTrades);
   Print("║   Último UUID procesado: ", lastSignalUUID);
   Print("║   Razón desinicialización: ", GetDeinitReasonText(reason));
   Print("╚══════════════════════════════════════════════════════════════════════════╝");
}

//+------------------------------------------------------------------+
//| Obtener texto de razón de desinicialización                     |
//+------------------------------------------------------------------+
string GetDeinitReasonText(int reason)
{
   switch(reason)
   {
      case REASON_PROGRAM:     return "Programa terminado";
      case REASON_REMOVE:      return "EA eliminado del gráfico";
      case REASON_RECOMPILE:   return "EA recompilado";
      case REASON_CHARTCHANGE: return "Símbolo o período cambiado";
      case REASON_CHARTCLOSE:  return "Gráfico cerrado";
      case REASON_PARAMETERS:  return "Parámetros de entrada cambiados";
      case REASON_ACCOUNT:     return "Cuenta cambiada";
      default:                  return "Razón " + IntegerToString(reason);
   }
}

//+------------------------------------------------------------------+
//| Timer function - Revisar archivo JSON                           |
//+------------------------------------------------------------------+
void OnTimer()
{
   timerCounter++;
   datetime currentTime = TimeCurrent();
   string timeStr = TimeToString(currentTime, TIME_SECONDS);
   
   // MOSTRAR LOG CADA SEGUNDO SIEMPRE
   if(LogEverySecond || DebugMode)
   {
      bool fileExists = FileExists(JsonFilePath);
      string statusStr = fileExists ? "📂 ARCHIVO ENCONTRADO" : "⏳ ESPERANDO ARCHIVO";
      
      Print("⏱️ [", timeStr, "] Segundo #", timerCounter, 
            " - FileExists('", JsonFilePath, "') = ", fileExists ? "true" : "false",
            " | ", statusStr);
   }
   
   CheckJsonFile();
}

//+------------------------------------------------------------------+
//| Revisar archivo JSON                                            |
//+------------------------------------------------------------------+
void CheckJsonFile()
{
   datetime checkTime = TimeCurrent();
   string timeStr = TimeToString(checkTime, TIME_SECONDS);
   
   // PASO 1: Verificar si el archivo existe con FileIsExist
   Print("🔍 [", timeStr, "] PASO 1: Llamando a FileExists('", JsonFilePath, "')");
   bool fileExists = FileExists(JsonFilePath);
   Print("   FileExists devuelve: ", fileExists ? "true" : "false");
   
   if(!fileExists)
   {
      if(isFirstRun)
      {
         Print("⏳ [", timeStr, "] Archivo NO existe aún. Esperando...");
         isFirstRun = false;
      }
      return;
   }
   
   // PASO 2: El archivo existe, intentar abrirlo
   Print("📂 [", timeStr, "] PASO 2: Archivo ENCONTRADO. Intentando abrir...");
   
   // PASO 3: Leer el archivo
   string jsonContent = ReadJsonFile(JsonFilePath);
   
   // PASO 4: Verificar resultado de la lectura
   if(jsonContent == "")
   {
      Print("❌ [", timeStr, "] PASO 4: ERROR - ReadJsonFile devolvió cadena vacía");
      
      // Obtener el último error
      int lastError = GetLastError();
      Print("   GetLastError() = ", lastError, " - ", GetErrorDescription(lastError));
      
      // Verificar permisos AHORA MISMO
      Print("   🔍 Verificando acceso al archivo AHORA:");
      int testHandle = FileOpen(JsonFilePath, FILE_READ|FILE_TXT|FILE_ANSI);
      if(testHandle == INVALID_HANDLE)
      {
         int error = GetLastError();
         Print("   ❌ FileOpen AHORA MISMO falló. Error: ", error, " - ", GetErrorDescription(error));
      }
      else
      {
         ulong size = FileSize(testHandle);
         Print("   ✅ FileOpen AHORA MISMO EXITOSO. Tamaño: ", size, " bytes");
         
         if(size > 0)
         {
            string testContent = FileReadString(testHandle, (int)MathMin(size, 100));
            Print("   Contenido AHORA MISMO (primeros 100 chars): '", testContent, "'");
         }
         else
         {
            Print("   ⚠️ El archivo está VACÍO (0 bytes) AHORA MISMO");
         }
         
         FileClose(testHandle);
      }
      return;
   }
   
   // PASO 5: Archivo leído correctamente
   Print("✅ [", timeStr, "] PASO 5: Archivo LEÍDO correctamente");
   Print("   Longitud del contenido: ", StringLen(jsonContent), " caracteres");
   Print("   Contenido COMPLETO: '", jsonContent, "'");
   
   totalSignals++;
   lastFileCheck = checkTime;
   Print("📩 [", timeStr, "] Señal #", totalSignals, " recibida");
   
   ProcessSignal(jsonContent);
}

//+------------------------------------------------------------------+
//| Leer archivo JSON                                               |
//+------------------------------------------------------------------+
string ReadJsonFile(string filePath)
{
   string content = "";
   datetime now = TimeCurrent();
   string timeStr = TimeToString(now, TIME_SECONDS);
   
   Print("   📖 [", timeStr, "] ReadJsonFile: Intentando FileOpen...");
   
   int fileHandle = FileOpen(filePath, FILE_READ|FILE_TXT|FILE_ANSI);
   
   if(fileHandle != INVALID_HANDLE)
   {
      Print("   ✅ ReadJsonFile: FileOpen EXITOSO. Handle: ", fileHandle);
      
      // Obtener tamaño del archivo
      ulong fileSize = FileSize(fileHandle);
      Print("   📏 ReadJsonFile: FileSize = ", fileSize, " bytes");
      
      if(fileSize > 0)
      {
         // Leer el contenido
         Print("   📖 ReadJsonFile: Leyendo ", fileSize, " bytes...");
         content = FileReadString(fileHandle, (int)fileSize);
         Print("   ✅ ReadJsonFile: Lectura completada. Longitud: ", StringLen(content), " caracteres");
      }
      else
      {
         Print("⚠️ ReadJsonFile: El archivo está vacío (tamaño 0 bytes)");
      }
      
      // Cerrar el archivo
      FileClose(fileHandle);
      Print("   ✅ ReadJsonFile: Archivo cerrado");
   }
   else
   {
      int error = GetLastError();
      Print("❌ ReadJsonFile: FileOpen FALLÓ. Error: ", error, " - ", GetErrorDescription(error));
      
      // Información específica según el error
      switch(error)
      {
         case 5002:
            Print("   Error 5002: Archivo no encontrado (FILE_ERROR_FILENOTFOUND)");
            break;
         case 5004:
            Print("   Error 5004: Demasiados archivos abiertos (FILE_ERROR_TOOMANYOPENED)");
            break;
         case 5006:
            Print("   Error 5006: Handle inválido (FILE_ERROR_INVALIDHANDLE)");
            break;
         case 5010:
            Print("   Error 5010: Acceso denegado (FILE_ERROR_ACCESS_DENIED)");
            Print("   Posible causa: El archivo está abierto por otro proceso (Python)");
            break;
         default:
            Print("   Error desconocido");
      }
   }
   
   return content;
}

//+------------------------------------------------------------------+
//| Verificar si un archivo existe                                  |
//+------------------------------------------------------------------+
bool FileExists(string filePath)
{
   bool exists = FileIsExist(filePath);
   return exists;
}

//+------------------------------------------------------------------+
//| Procesar señal de trading                                        |
//+------------------------------------------------------------------+
void ProcessSignal(string jsonMessage)
{
   datetime processTime = TimeCurrent();
   string currentSymbol = Symbol();
   string timeStr = TimeToString(processTime, TIME_SECONDS);
   
   Print("⚙️ [", timeStr, "] PASO 6: Procesando señal #", totalSignals);
   Print("   JSON recibido: '", jsonMessage, "'");
   
   // PASO 7: Parsear JSON
   Print("🔍 [", timeStr, "] PASO 7: Parseando JSON...");
   SignalData signal;
   if(!ParseSignal(jsonMessage, signal))
   {
      Print("❌ [", timeStr, "] PASO 7: ERROR - ParseSignal falló");
      return;
   }
   
   Print("✅ [", timeStr, "] PASO 7: JSON parseado correctamente");
   Print("   UUID: '", signal.uuid, "'");
   Print("   Par: '", signal.pair, "'");
   Print("   Tipo: '", signal.type, "'");
   Print("   Timeframe: '", signal.timeframe, "'");
   Print("   Entrada: ", signal.entry);
   Print("   SL: ", signal.sl);
   Print("   TP: ", signal.tp);
   Print("   Pips SL: ", signal.pips_sl);
   Print("   Ratio: ", signal.ratio);
   
   // PASO 8: Verificar UUID duplicado
   Print("🔍 [", timeStr, "] PASO 8: Verificando UUID duplicado");
   Print("   UUID actual: '", signal.uuid, "'");
   Print("   Último UUID: '", lastSignalUUID, "'");
   
   if(signal.uuid == lastSignalUUID && lastSignalUUID != "")
   {
      Print("⏭️ [", timeStr, "] PASO 8: Señal DUPLICADA ignorada");
      return;
   }
   
   // PASO 9: Validar señal
   Print("🔍 [", timeStr, "] PASO 9: Validando señal...");
   if(!ValidateSignal(signal, currentSymbol))
   {
      Print("❌ [", timeStr, "] PASO 9: Validación FALLÓ");
      return;
   }
   
   Print("✅ [", timeStr, "] PASO 9: Validación EXITOSA");
   
   // PASO 10: Verificar si se puede tradear
   bool tradeAllowed = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);
   Print("🔍 [", timeStr, "] PASO 10: Verificando condiciones de trading");
   Print("   AutoTrade = ", AutoTrade ? "true" : "false");
   Print("   TERMINAL_TRADE_ALLOWED = ", tradeAllowed ? "true" : "false");
   
   if(AutoTrade && tradeAllowed)
   {
      Print("🚀 [", timeStr, "] PASO 11: Ejecutando orden...");
      if(ExecuteTradeWithRetry(signal))
      {
         // Actualizar UUID solo si la operación fue exitosa
         lastSignalUUID = signal.uuid;
         Print("✅ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] PASO 12: UUID actualizado a: ", lastSignalUUID);
         Print("   totalTrades ahora = ", totalTrades);
      }
      else
      {
         Print("❌ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] PASO 12: Ejecución FALLÓ");
      }
   }
   else
   {
      Print("⚠️ [", timeStr, "] PASO 11: No se ejecuta la orden porque:");
      if(!AutoTrade) Print("   - AutoTrade está desactivado");
      if(!tradeAllowed) Print("   - Trading no permitido por terminal");
   }
}

//+------------------------------------------------------------------+
//| Estructura para datos de señal                                  |
//+------------------------------------------------------------------+
struct SignalData
{
   string uuid;
   string pair;
   string type;
   string timeframe;
   double entry;
   double sl;
   double tp;
   double pips_sl;
   double ratio;
   
   SignalData()
   {
      uuid = "";
      pair = "";
      type = "";
      timeframe = "";
      entry = 0;
      sl = 0;
      tp = 0;
      pips_sl = 0;
      ratio = 0;
   }
};

//+------------------------------------------------------------------+
//| Parsear JSON a estructura                                       |
//+------------------------------------------------------------------+
bool ParseSignal(string json, SignalData &signal)
{
   // Limpiar espacios
   StringTrimRight(json);
   StringTrimLeft(json);
   
   Print("   🔍 ParseSignal: Extrayendo valores...");
   
   signal.uuid = ExtractJsonValue(json, "uuid");
   signal.pair = ExtractJsonValue(json, "par");
   signal.type = ExtractJsonValue(json, "tipo");
   signal.timeframe = ExtractJsonValue(json, "temporalidad");
   
   string entryStr = ExtractJsonValue(json, "entrada");
   string slStr = ExtractJsonValue(json, "sl");
   string tpStr = ExtractJsonValue(json, "tp");
   string pipsSlStr = ExtractJsonValue(json, "pips_sl");
   string ratioStr = ExtractJsonValue(json, "ratio");
   
   Print("   Valores extraídos (raw):");
   Print("      uuid: '", signal.uuid, "'");
   Print("      par: '", signal.pair, "'");
   Print("      tipo: '", signal.type, "'");
   Print("      entrada: '", entryStr, "'");
   Print("      sl: '", slStr, "'");
   Print("      tp: '", tpStr, "'");
   
   signal.entry = StringToDouble(entryStr);
   signal.sl = StringToDouble(slStr);
   signal.tp = StringToDouble(tpStr);
   signal.pips_sl = StringToDouble(pipsSlStr);
   signal.ratio = StringToDouble(ratioStr);
   
   // Validar campos obligatorios
   if(signal.uuid == "")
   {
      Print("   ❌ ParseSignal: falta uuid");
      return false;
   }
   
   if(signal.pair == "")
   {
      Print("   ❌ ParseSignal: falta par");
      return false;
   }
   
   if(signal.type == "")
   {
      Print("   ❌ ParseSignal: falta tipo");
      return false;
   }
   
   if(signal.type != "COMPRA" && signal.type != "VENTA")
   {
      Print("   ❌ ParseSignal: tipo inválido '", signal.type, "'");
      return false;
   }
   
   Print("   ✅ ParseSignal: todos los campos obligatorios presentes");
   return true;
}

//+------------------------------------------------------------------+
//| Validar señal contra filtros                                    |
//+------------------------------------------------------------------+
bool ValidateSignal(SignalData &signal, string currentSymbol)
{
   datetime validTime = TimeCurrent();
   string timeStr = TimeToString(validTime, TIME_SECONDS);
   
   Print("   🔍 ValidateSignal: Aplicando filtros...");
   
   // Validar símbolo
   if(ValidateSymbol)
   {
      Print("      Validando símbolo: señal.pair='", signal.pair, "' vs currentSymbol='", currentSymbol, "'");
      if(signal.pair != currentSymbol)
      {
         Print("      ⚠️ Símbolo no coincide");
         return false;
      }
   }
   
   // Validar que tenemos SL y TP
   if(signal.sl <= 0)
   {
      Print("      ⚠️ SL inválido: ", signal.sl);
      return false;
   }
   
   if(signal.tp <= 0)
   {
      Print("      ⚠️ TP inválido: ", signal.tp);
      return false;
   }
   
   // Obtener información del símbolo
   double point = SymbolInfoDouble(currentSymbol, SYMBOL_POINT);
   double spread = (double)SymbolInfoInteger(currentSymbol, SYMBOL_SPREAD);
   
   // Validar distancias mínimas
   double slPoints = MathAbs(signal.entry - signal.sl) / point;
   double tpPoints = MathAbs(signal.tp - signal.entry) / point;
   
   Print("      Distancia SL: ", slPoints, " puntos (mínimo ", MinSLPoints, ")");
   Print("      Distancia TP: ", tpPoints, " puntos (mínimo ", MinTPPoints, ")");
   Print("      Spread actual: ", spread, " puntos (máx ", MaxSpreadPoints, ")");
   
   if(slPoints < MinSLPoints)
   {
      Print("      ⚠️ SL demasiado pequeño");
      return false;
   }
   
   if(tpPoints < MinTPPoints)
   {
      Print("      ⚠️ TP demasiado pequeño");
      return false;
   }
   
   // Validar spread
   if(MaxSpreadPoints > 0 && spread > MaxSpreadPoints)
   {
      Print("      ⚠️ Spread demasiado alto");
      return false;
   }
   
   Print("      ✅ Todos los filtros superados");
   return true;
}

//+------------------------------------------------------------------+
//| Extraer valor de JSON                                            |
//+------------------------------------------------------------------+
string ExtractJsonValue(string json, string key)
{
   string searchKey = "\"" + key + "\":";
   int pos = StringFind(json, searchKey);
   if(pos < 0) return "";
   
   int start = pos + StringLen(searchKey);
   while(start < StringLen(json) && json[start] == ' ') start++;
   
   bool isString = (json[start] == '"');
   if(isString) start++;
   
   int end = start;
   while(end < StringLen(json))
   {
      if(isString)
      {
         if(json[end] == '"' && json[end-1] != '\\') break;
      }
      else
      {
         if(json[end] == ',' || json[end] == '}' || json[end] == ']' || json[end] == '\n' || json[end] == '\r') break;
      }
      end++;
   }
   
   string result = StringSubstr(json, start, end - start);
   StringTrimRight(result);
   StringTrimLeft(result);
   
   return result;
}

//+------------------------------------------------------------------+
//| Ejecutar orden con sistema de reintentos completo               |
//+------------------------------------------------------------------+
bool ExecuteTradeWithRetry(SignalData &signal)
{
   datetime execTime = TimeCurrent();
   string timeStr = TimeToString(execTime, TIME_SECONDS);
   
   Print("   🚀 [", timeStr, "] ExecuteTradeWithRetry: INICIANDO");
   
   // Obtener balance para gestión de riesgo
   double balance = (BalanceReferencia > 0) ? BalanceReferencia : AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   
   Print("   📊 Estado de cuenta:");
   Print("      Balance: $", DoubleToString(balance, 2));
   Print("      Equity: $", DoubleToString(equity, 2));
   Print("      Margen libre: $", DoubleToString(freeMargin, 2));
   
   // Obtener precios actuales
   double askPrice = SymbolInfoDouble(signal.pair, SYMBOL_ASK);
   double bidPrice = SymbolInfoDouble(signal.pair, SYMBOL_BID);
   
   Print("   💱 Precios de mercado para ", signal.pair, ":");
   Print("      Ask: ", askPrice);
   Print("      Bid: ", bidPrice);
   
   // Determinar dirección
   bool isBuy = (signal.type == "COMPRA");
   double entryPrice = isBuy ? askPrice : bidPrice;
   
   Print("   Dirección: ", isBuy ? "COMPRA" : "VENTA");
   Print("   Precio de entrada estimado: ", entryPrice);
   
   // Validar SL respecto a precio actual
   if(isBuy && signal.sl >= entryPrice)
   {
      Print("   ⚠️ SL de compra (", signal.sl, ") debe ser menor que precio actual (", entryPrice, ")");
      return false;
   }
   if(!isBuy && signal.sl <= entryPrice)
   {
      Print("   ⚠️ SL de venta (", signal.sl, ") debe ser mayor que precio actual (", entryPrice, ")");
      return false;
   }
   
   // Calcular volumen
   Print("   🧮 Calculando volumen óptimo...");
   double volume = CalculateOptimalVolume(signal.pair, entryPrice, signal.sl, 
                                         RiskPercent, balance);
   
   if(volume <= 0)
   {
      Print("   ❌ Volumen inválido: ", volume);
      return false;
   }
   
   double riskAmount = balance * RiskPercent / 100.0;
   if(MaxRiskMoney > 0 && riskAmount > MaxRiskMoney)
      riskAmount = MaxRiskMoney;
   
   Print("   📊 Preparando orden:");
   Print("      Símbolo: ", signal.pair);
   Print("      Tipo: ", isBuy ? "COMPRA" : "VENTA");
   Print("      Volumen: ", volume);
   Print("      Riesgo: ", RiskPercent, "% ($", DoubleToString(riskAmount, 2), ")");
   Print("      SL: ", signal.sl);
   Print("      TP: ", signal.tp);
   
   // PASO 1: Abrir orden con reintentos
   Print("   🔄 PASO 1: Abriendo orden...");
   ulong ticket = OpenOrderWithRetry(signal.pair, isBuy, volume, entryPrice);
   
   if(ticket > 0)
   {
      totalTrades++;
      Print("   ✅ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] PASO 1 COMPLETADO - Orden abierta. Ticket: ", ticket);
      
      // PASO 2: Establecer SL/TP con reintentos
      Print("   🔄 PASO 2: Estableciendo SL/TP...");
      if(!ModifyPositionSLTPWithRetry(ticket, signal.sl, signal.tp))
      {
         Print("   ⚠️ CRÍTICO: Operación ", ticket, " abierta SIN PROTECCIÓN");
         Print("      SL deseado: ", signal.sl);
         Print("      TP deseado: ", signal.tp);
         return true;
      }
      
      Print("   ✅ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] EJECUCIÓN COMPLETADA");
      return true;
   }
   
   Print("   ❌ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] EJECUCIÓN FALLIDA");
   return false;
}

//+------------------------------------------------------------------+
//| Abrir orden con reintentos                                      |
//+------------------------------------------------------------------+
ulong OpenOrderWithRetry(string symbol, bool isBuy, double volume, double expectedPrice)
{
   Print("      🚀 OpenOrderWithRetry: Iniciando (máx ", MaxOpenAttempts, " intentos)");
   
   for(int attempt = 1; attempt <= MaxOpenAttempts; attempt++)
   {
      Print("      📝 Intento #", attempt, " de ", MaxOpenAttempts);
      
      // Obtener precios actualizados
      double askPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double bidPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
      double price = isBuy ? askPrice : bidPrice;
      
      Print("         Precios - Ask: ", askPrice, " | Bid: ", bidPrice);
      Print("         Precio ejecución: ", price);
      
      // Preparar request
      MqlTradeRequest request = {};
      MqlTradeResult result = {};
      
      request.action = TRADE_ACTION_DEAL;
      request.symbol = symbol;
      request.volume = volume;
      request.type = isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      request.price = price;
      request.deviation = Deviation;
      request.type_filling = FillingType;
      request.type_time = ORDER_TIME_GTC;
      request.magic = MagicNumber;
      request.comment = "JSON Signal";
      
      // Verificar margen si está activado
      if(CheckFreeMargin)
      {
         double marginRequired = 0;
         if(!OrderCalcMargin(request.type, symbol, volume, price, marginRequired))
         {
            int error = GetLastError();
            Print("         ⚠️ Error calculando margen: ", error);
            Sleep(100);
            continue;
         }
         
         double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
         double maxAllowedMargin = freeMargin * (MaxMarginUse/100.0);
         
         Print("         Margen requerido: $", DoubleToString(marginRequired, 2));
         Print("         Margen libre: $", DoubleToString(freeMargin, 2));
         Print("         Máx permitido: $", DoubleToString(maxAllowedMargin, 2));
         
         if(marginRequired > maxAllowedMargin)
         {
            Print("         ⚠️ Margen insuficiente");
            Sleep(100);
            continue;
         }
      }
      
      // Enviar orden
      Print("         Enviando orden...");
      if(OrderSend(request, result))
      {
         Print("      ✅ Orden ejecutada en intento #", attempt);
         Print("         Ticket: ", result.order);
         Print("         Precio: ", result.price);
         return result.order;
      }
      else
      {
         string errorDesc = GetErrorDescription(result.retcode);
         Print("      ❌ Intento ", attempt, " fallido: ", errorDesc, " (", result.retcode, ")");
         Sleep(100);
      }
   }
   
   Print("      ❌ No se pudo abrir la orden después de ", MaxOpenAttempts, " intentos");
   return 0;
}

//+------------------------------------------------------------------+
//| Modificar SL/TP con reintentos                                  |
//+------------------------------------------------------------------+
bool ModifyPositionSLTPWithRetry(ulong ticket, double sl, double tp)
{
   Print("      🔧 ModifyPositionSLTPWithRetry: Ticket ", ticket, " (máx ", MaxModifyAttempts, " intentos)");
   
   for(int attempt = 1; attempt <= MaxModifyAttempts; attempt++)
   {
      Print("      📝 Intento #", attempt);
      
      if(!PositionSelectByTicket(ticket))
      {
         Print("      ⚠️ La posición ", ticket, " ya no existe");
         return false;
      }
      
      long positionType = PositionGetInteger(POSITION_TYPE);
      string symbol = PositionGetString(POSITION_SYMBOL);
      
      // Preparar request
      MqlTradeRequest request = {};
      MqlTradeResult result = {};
      
      request.action = TRADE_ACTION_SLTP;
      request.position = ticket;
      request.symbol = symbol;
      request.sl = sl;
      request.tp = tp;
      request.magic = MagicNumber;
      
      Print("         Enviando modificación SL=", sl, " TP=", tp);
      
      if(OrderSend(request, result))
      {
         Print("      ✅ SL/TP establecidos en intento ", attempt);
         return true;
      }
      else
      {
         Print("      ⚠️ Intento ", attempt, " fallido: ", GetErrorDescription(result.retcode));
         Sleep(100);
      }
   }
   
   Print("      ❌ No se pudo establecer SL/TP");
   return false;
}

//+------------------------------------------------------------------+
//| Calcular volumen óptimo                                         |
//+------------------------------------------------------------------+
double CalculateOptimalVolume(string symbol, double entryPrice, double stopLoss, 
                               double riskPercent, double balance)
{
   Print("      🧮 CalculateOptimalVolume:");
   
   double volumeMin = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   
   Print("         Volume Min: ", volumeMin);
   Print("         Volume Max: ", volumeMax);
   Print("         Volume Step: ", volumeStep);
   
   if(tickValue <= 0)
   {
      tickValue = 1.0;
      Print("         ⚠️ tickValue=0, usando 1.0");
   }
   
   double riskMoney = balance * (riskPercent / 100.0);
   Print("         Riesgo monetario: $", DoubleToString(riskMoney, 2));
   
   if(MaxRiskMoney > 0 && riskMoney > MaxRiskMoney)
   {
      riskMoney = MaxRiskMoney;
      Print("         Aplicando límite máximo: $", MaxRiskMoney);
   }
   
   double slDistance = MathAbs(entryPrice - stopLoss);
   double slPoints = slDistance / point;
   Print("         Distancia SL: ", slPoints, " puntos");
   
   double pointValue = tickValue * (slDistance / tickSize);
   Print("         Valor por lote: $", DoubleToString(pointValue, 2));
   
   double lots = riskMoney / pointValue;
   Print("         Lotes calculados: ", lots);
   
   lots = MathMax(volumeMin, MathMin(volumeMax, lots));
   Print("         Lotes ajustados a límites: ", lots);
   
   if(volumeStep > 0)
   {
      lots = MathFloor(lots / volumeStep) * volumeStep;
      Print("         Lotes ajustados a step: ", lots);
   }
   
   double normalizedLots = NormalizeDouble(lots, 2);
   Print("         ✅ Volumen final: ", normalizedLots);
   
   return normalizedLots;
}

//+------------------------------------------------------------------+
//| Obtener descripción del error                                   |
//+------------------------------------------------------------------+
string GetErrorDescription(int errorCode)
{
   switch(errorCode)
   {
      case 0:           return "OK/Sin error";
      case 1:           return "Error de ejecución";
      case 2:           return "Error genérico";
      case 3:           return "Parámetros incorrectos";
      case 4:           return "Servidor ocupado";
      case 5:           return "Conexión perdida";
      case 6:           return "No hay conexión";
      case 7:           return "Memoria insuficiente";
      case 8:           return "Archivo no encontrado";
      case 9:           return "Formato de archivo incorrecto";
      case 10:          return "Archivo demasiado grande";
      case 5002:        return "Archivo no encontrado (FILE_ERROR_FILENOTFOUND)";
      case 5004:        return "Demasiados archivos abiertos (FILE_ERROR_TOOMANYOPENED)";
      case 5006:        return "Handle inválido (FILE_ERROR_INVALIDHANDLE)";
      case 5010:        return "Acceso denegado (FILE_ERROR_ACCESS_DENIED)";
      case 10004:       return "Requote";
      case 10006:       return "Solicitud rechazada";
      case 10007:       return "Solicitud cancelada";
      case 10008:       return "Orden colocada";
      case 10009:       return "Solicitud completada";
      case 10013:       return "Solicitud inválida";
      case 10014:       return "Volumen inválido";
      case 10015:       return "Precio inválido";
      case 10016:       return "Stops inválidos";
      case 10017:       return "Trading deshabilitado";
      case 10018:       return "Mercado cerrado";
      case 10019:       return "Dinero insuficiente";
      case 10020:       return "Precios cambiados";
      case 10021:       return "Sin cotizaciones";
      case 10024:       return "Solicitudes demasiado frecuentes";
      case 10026:       return "Autotrading deshabilitado por servidor";
      case 10027:       return "Autotrading deshabilitado por terminal";
      default:          return "Error " + IntegerToString(errorCode);
   }
}
//+------------------------------------------------------------------+
