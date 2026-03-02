//+------------------------------------------------------------------+
//|                                           JSONFileEA.mq5         |
//|                                      Lectura desde archivo JSON  |
//+------------------------------------------------------------------+
#property copyright "Elias Eduardo Liranza Perez"
#property version   "3.18"
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

//--- Input parameters - EJECUCIÓN
input group "=== CONFIGURACIÓN DE EJECUCIÓN ==="
input ENUM_ORDER_TYPE_FILLING FillingType = ORDER_FILLING_FOK;  // Tipo de filling

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

//--- Variables globales de configuración (antes eran inputs)
double   MaxRiskMoney = 0;          // 0 = sin límite máximo
int      MaxOpenAttempts = 10;      // Máx intentos para abrir
int      MaxModifyAttempts = 10;    // Máx intentos para SL/TP
int      Deviation = 10;            // Desviación permitida
bool     AutoTrade = true;          // Auto trading
int      MagicNumber = 234000;      // Magic number del EA
bool     ValidateSymbol = false;    // Validar símbolo de la señal
double   MinSLPoints = 0;           // Mínimo SL en puntos
double   MinTPPoints = 0;           // Mínimo TP en puntos
double   MaxSpreadPoints = 0;       // 0 = sin límite
bool     CheckFreeMargin = true;    // Verificar margen libre
double   MaxMarginUse = 98.0;       // % Máx de margen a usar

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("╔══════════════════════════════════════════════════════════════════════════╗");
   Print("║                    🚀 JSON FILE EA - VERSIÓN 3.18                        ║");
   Print("║                    📊 LOGS EXHAUSTIVOS - LECTURA BINARIA                 ║");
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
      int testHandle = FileOpen(JsonFilePath, FILE_READ|FILE_BIN);
      if(testHandle != INVALID_HANDLE)
      {
         Print("   ✅ Archivo ABIERTO correctamente para lectura");
         ulong fileSize = FileSize(testHandle);
         Print("   📏 Tamaño del archivo: ", fileSize, " bytes");
         
         if(fileSize > 0)
         {
            uchar bytes[];
            ArrayResize(bytes, (int)MathMin(fileSize, 200));
            FileReadArray(testHandle, bytes, 0, (int)MathMin(fileSize, 200));
            string testContent = CharArrayToString(bytes, 0, WHOLE_ARRAY, CP_UTF8);
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
      int testHandle = FileOpen(JsonFilePath, FILE_READ|FILE_BIN);
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
            uchar bytes[];
            ArrayResize(bytes, (int)MathMin(size, 100));
            FileReadArray(testHandle, bytes, 0, (int)MathMin(size, 100));
            string testContent = CharArrayToString(bytes, 0, WHOLE_ARRAY, CP_UTF8);
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
//| Leer archivo JSON - VERSIÓN CORREGIDA (LECTURA BINARIA)         |
//+------------------------------------------------------------------+
string ReadJsonFile(string filePath)
{
   string content = "";
   datetime now = TimeCurrent();
   string timeStr = TimeToString(now, TIME_SECONDS);
   
   Print("   📖 [", timeStr, "] ReadJsonFile: Intentando FileOpen en modo BINARIO...");
   
   // Abrir en modo BINARIO para leer exactamente todos los bytes
   int fileHandle = FileOpen(filePath, FILE_READ|FILE_BIN);
   
   if(fileHandle != INVALID_HANDLE)
   {
      Print("   ✅ ReadJsonFile: FileOpen EXITOSO. Handle: ", fileHandle);
      
      // Obtener tamaño del archivo
      ulong fileSize = FileSize(fileHandle);
      Print("   📏 ReadJsonFile: FileSize = ", fileSize, " bytes");
      
      if(fileSize > 0)
      {
         // Leer como array de bytes
         Print("   📖 ReadJsonFile: Leyendo ", fileSize, " bytes...");
         uchar bytes[];
         ArrayResize(bytes, (int)fileSize);
         FileReadArray(fileHandle, bytes, 0, (int)fileSize);
         
         // Convertir bytes a string usando UTF-8
         content = CharArrayToString(bytes, 0, WHOLE_ARRAY, CP_UTF8);
         Print("   ✅ ReadJsonFile: Lectura completada. Longitud: ", StringLen(content), " caracteres");
         
         // Mostrar los primeros bytes para debug (solo si DebugMode está activado)
         if(DebugMode)
         {
            string hexDump = "";
            int maxBytes = MathMin(30, (int)fileSize);
            for(int i = 0; i < maxBytes; i++)
            {
               hexDump += StringFormat("%02X ", bytes[i]);
            }
            Print("   🔍 Primeros ", maxBytes, " bytes (hex): ", hexDump);
         }
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
   double ask = SymbolInfoDouble(currentSymbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(currentSymbol, SYMBOL_BID);
   
   // Validar distancias mínimas
   double slPoints = MathAbs(signal.entry - signal.sl) / point;
   double tpPoints = MathAbs(signal.tp - signal.entry) / point;
   
   Print("      Distancia SL: ", slPoints, " puntos (mínimo ", MinSLPoints, ")");
   Print("      Distancia TP: ", tpPoints, " puntos (mínimo ", MinTPPoints, ")");
   Print("      Spread actual: ", spread, " puntos (máx ", MaxSpreadPoints, ")");
   Print("      Ask/Bid: ", ask, " / ", bid);
   
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
//| Extraer valor de JSON - VERSIÓN CORREGIDA (sin StringGetChar)   |
//+------------------------------------------------------------------+
string ExtractJsonValue(string json, string key)
{
   string searchKey = "\"" + key + "\":";
   int pos = StringFind(json, searchKey);
   if(pos < 0) return "";
   
   int start = pos + StringLen(searchKey);
   
   // Saltar espacios en blanco
   while(start < StringLen(json) && (json[start] == ' ' || json[start] == '\t' || 
         json[start] == '\r' || json[start] == '\n'))
      start++;
   
   // Determinar si es string o número
   bool isString = (json[start] == '"');
   if(isString) start++;
   
   int end = start;
   int bracketLevel = 0;
   
   while(end < StringLen(json))
   {
      if(isString)
      {
         if(json[end] == '"' && (end == 0 || json[end-1] != '\\'))
            break;
      }
      else
      {
         // Para números, buscar hasta encontrar separador o fin
         if(json[end] == ',' || json[end] == '}' || json[end] == ']' || 
            json[end] == '\n' || json[end] == '\r')
            break;
      }
      end++;
   }
   
   string result = StringSubstr(json, start, end - start);
   
   // Limpiar espacios
   StringTrimRight(result);
   StringTrimLeft(result);
   
   // Quitar comillas si las tiene (versión corregida sin StringGetChar)
   int resultLen = StringLen(result);
   if(resultLen >= 2)
   {
      // Obtener primer y último carácter como string
      string firstChar = StringSubstr(result, 0, 1);
      string lastChar = StringSubstr(result, resultLen - 1, 1);
      
      if(firstChar == "\"" && lastChar == "\"")
      {
         result = StringSubstr(result, 1, resultLen - 2);
      }
   }
   
   return result;
}

//+------------------------------------------------------------------+
//| Ejecutar orden con sistema de reintentos completo               |
//| MODIFICADO: TP y SL en la misma solicitud de apertura           |
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
   
   // Validar TP respecto a precio actual
   if(isBuy && signal.tp <= entryPrice)
   {
      Print("   ⚠️ TP de compra (", signal.tp, ") debe ser mayor que precio actual (", entryPrice, ")");
      return false;
   }
   if(!isBuy && signal.tp >= entryPrice)
   {
      Print("   ⚠️ TP de venta (", signal.tp, ") debe ser menor que precio actual (", entryPrice, ")");
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
   
   // PASO ÚNICO: Abrir orden con SL y TP incluidos
   Print("   🔄 EJECUTANDO ORDEN COMPLETA CON SL Y TP...");
   ulong ticket = OpenOrderWithSLTP(signal.pair, isBuy, volume, entryPrice, signal.sl, signal.tp);
   
   if(ticket > 0)
   {
      totalTrades++;
      Print("   ✅ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] ORDEN COMPLETA EJECUTADA. Ticket: ", ticket);
      Print("      SL: ", signal.sl, " | TP: ", signal.tp, " incluidos en la orden");
      Print("   ✅ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] EJECUCIÓN COMPLETADA");
      return true;
   }
   
   Print("   ❌ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] EJECUCIÓN FALLIDA");
   return false;
}

//+------------------------------------------------------------------+
//| Abrir orden con SL y TP incluidos en la misma solicitud         |
//+------------------------------------------------------------------+
ulong OpenOrderWithSLTP(string symbol, bool isBuy, double volume, double expectedPrice, double sl, double tp)
{
   Print("      🚀 OpenOrderWithSLTP: Iniciando con SL=", sl, " TP=", tp, " (máx ", MaxOpenAttempts, " intentos)");
   
   for(int attempt = 1; attempt <= MaxOpenAttempts; attempt++)
   {
      Print("      📝 Intento #", attempt, " de ", MaxOpenAttempts);
      
      // Obtener precios actualizados
      double askPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double bidPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
      double price = isBuy ? askPrice : bidPrice;
      double spread = (double)SymbolInfoInteger(symbol, SYMBOL_SPREAD) * SymbolInfoDouble(symbol, SYMBOL_POINT);
      
      Print("         Precios - Ask: ", askPrice, " | Bid: ", bidPrice, " | Spread: $", spread);
      Print("         Precio ejecución: ", price);
      
      // Preparar request con SL y TP incluidos
      MqlTradeRequest request = {};
      MqlTradeResult result = {};
      
      request.action = TRADE_ACTION_DEAL;
      request.symbol = symbol;
      request.volume = volume;
      request.type = isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      request.price = price;
      request.sl = sl;           // Incluir SL directamente
      request.tp = tp;           // Incluir TP directamente
      request.deviation = Deviation;
      request.type_filling = FillingType;
      request.type_time = ORDER_TIME_GTC;
      request.magic = MagicNumber;
      request.comment = "JSON Signal";
      
      if(DebugMode)
      {
         Print("         Request details:");
         Print("            Action: DEAL");
         Print("            Symbol: ", request.symbol);
         Print("            Volume: ", request.volume);
         Print("            Type: ", request.type == ORDER_TYPE_BUY ? "BUY" : "SELL");
         Print("            Price: ", request.price);
         Print("            SL: ", request.sl);
         Print("            TP: ", request.tp);
         Print("            Deviation: ", request.deviation);
         Print("            Filling: ", EnumToString(FillingType));
         Print("            Magic: ", request.magic);
      }
      
      // Verificar margen si está activado
      if(CheckFreeMargin)
      {
         double marginRequired = 0;
         if(!OrderCalcMargin(request.type, symbol, volume, price, marginRequired))
         {
            int error = GetLastError();
            Print("         ⚠️ Error calculando margen: ", error, " - ", GetErrorDescription(error));
            Sleep(100);
            continue;
         }
         
         double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
         double maxAllowedMargin = freeMargin * (MaxMarginUse/100.0);
         
         Print("         Margen requerido: $", DoubleToString(marginRequired, 2));
         Print("         Margen libre: $", DoubleToString(freeMargin, 2));
         Print("         Máx permitido (", MaxMarginUse, "%): $", DoubleToString(maxAllowedMargin, 2));
         
         if(marginRequired > maxAllowedMargin)
         {
            Print("         ⚠️ Margen insuficiente. Requerido: $", marginRequired, 
                  ", Máximo permitido: $", maxAllowedMargin);
            Sleep(100);
            continue;
         }
         
         Print("         ✅ Margen suficiente");
      }
      
      // Verificar que los stops sean válidos para el broker
      double slDistance = MathAbs(price - sl);
      double tpDistance = MathAbs(tp - price);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double slPoints = slDistance / point;
      double tpPoints = tpDistance / point;
      
      int stopLevel = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
      
      if(stopLevel > 0)
      {
         if(slPoints < stopLevel)
            Print("         ⚠️ ADVERTENCIA: SL (", slPoints, " pts) menor que nivel de stops (", stopLevel, " pts)");
         if(tpPoints < stopLevel)
            Print("         ⚠️ ADVERTENCIA: TP (", tpPoints, " pts) menor que nivel de stops (", stopLevel, " pts)");
      }
      
      // Enviar orden
      Print("         Enviando orden con SL y TP incluidos...");
      if(OrderSend(request, result))
      {
         Print("      ✅ Orden completa ejecutada en intento #", attempt);
         Print("         Ticket: ", result.order);
         Print("         Precio de ejecución: ", result.price);
         Print("         Volumen ejecutado: ", result.volume);
         Print("         SL aplicado: ", sl);
         Print("         TP aplicado: ", tp);
         Print("         Comentario: ", result.comment);
         
         if(DebugMode && result.retcode != 10009) // 10009 = TRADE_RETCODE_DONE
         {
            Print("         Código retorno: ", result.retcode, " - ", GetErrorDescription(result.retcode));
         }
         
         return result.order;
      }
      else
      {
         string errorDesc = GetErrorDescription(result.retcode);
         int lastError = GetLastError();
         
         Print("      ❌ Intento ", attempt, " fallido:");
         Print("         Error código: ", result.retcode, " - ", errorDesc);
         if(lastError != 0 && lastError != result.retcode)
            Print("         Último error sistema: ", lastError, " - ", GetErrorDescription(lastError));
         
         // Información adicional del resultado
         if(result.retcode > 0)
         {
            Print("         Detalles del resultado:");
            Print("            Deal: ", result.deal);
            Print("            Order: ", result.order);
            Print("            Volume: ", result.volume);
            Print("            Price: ", result.price);
            Print("            Bid: ", result.bid);
            Print("            Ask: ", result.ask);
         }
         
         if(result.retcode == 10016) // TRADE_RETCODE_INVALID_STOPS
         {
            Print("         ⚠️ Stops inválidos - Posibles causas:");
            Print("            - SL/TP demasiado cerca del precio actual");
            Print("            - SL/TP fuera de los límites permitidos");
            Print("            - Distancia mínima no cumplida");
            Print("            - StopLevel actual: ", SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL), " puntos");
         }
         
         // Sleep fijo de 100ms
         Sleep(100);
      }
   }
   
   Print("      ❌ No se pudo abrir la orden después de ", MaxOpenAttempts, " intentos");
   return 0;
}

//+------------------------------------------------------------------+
//| Calcular volumen óptimo                                         |
//+------------------------------------------------------------------+
double CalculateOptimalVolume(string symbol, double entryPrice, double stopLoss, 
                               double riskPercent, double balance)
{
   Print("      🧮 CalculateOptimalVolume:");
   
   // Obtener información del símbolo
   double volumeMin = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double contractSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   
   Print("         Volume Min: ", volumeMin);
   Print("         Volume Max: ", volumeMax);
   Print("         Volume Step: ", volumeStep);
   Print("         Tick Value: $", tickValue);
   Print("         Tick Size: ", tickSize);
   Print("         Point: ", point);
   Print("         Contract Size: ", contractSize);
   
   // Si tickValue es 0 (puede pasar en algunos brokers), calcularlo
   if(tickValue <= 0)
   {
      tickValue = 1.0;
      Print("         ⚠️ tickValue = 0, usando valor por defecto: $1.0");
      Print("         Esto puede afectar la precisión del cálculo del volumen");
   }
   
   // Calcular riesgo monetario
   double riskMoney = balance * (riskPercent / 100.0);
   Print("         Riesgo calculado: ", riskPercent, "% de $", DoubleToString(balance, 2), " = $", DoubleToString(riskMoney, 2));
   
   // Aplicar límite máximo si está configurado
   if(MaxRiskMoney > 0 && riskMoney > MaxRiskMoney)
   {
      riskMoney = MaxRiskMoney;
      Print("         Aplicando límite máximo de riesgo: $", MaxRiskMoney);
   }
   
   // Calcular distancia en puntos
   double slDistance = MathAbs(entryPrice - stopLoss);
   double slPoints = slDistance / point;
   
   Print("         Distancia SL: ", slPoints, " puntos (", slDistance, " en precio)");
   
   if(slPoints < MinSLPoints)
   {
      Print("         ⚠️ SL demasiado pequeño: ", slPoints, " puntos (mínimo ", MinSLPoints, ")");
      return 0;
   }
   
   // Calcular valor por punto
   double pointValue = tickValue * (slDistance / tickSize);
   double riskPerLot = pointValue;
   
   Print("         Valor por lote: $", DoubleToString(riskPerLot, 2));
   Print("            Tick Value: $", tickValue, " * (", slDistance, " / ", tickSize, ") = $", pointValue);
   
   // Calcular lotes
   double lots = riskMoney / pointValue;
   Print("         Lotes calculados (sin ajustar): ", lots, " ($", riskMoney, " / $", pointValue, ")");
   
   // Ajustar a límites
   lots = MathMax(volumeMin, MathMin(volumeMax, lots));
   Print("         Lotes ajustados a límites: ", lots, " (min: ", volumeMin, ", max: ", volumeMax, ")");
   
   // Aplicar step
   if(volumeStep > 0)
   {
      double originalLots = lots;
      lots = MathFloor(lots / volumeStep) * volumeStep;
      Print("         Lotes ajustados a step: ", lots, " (original: ", originalLots, ", step: ", volumeStep, ")");
   }
   
   // Verificar riesgo real
   double realRisk = lots * pointValue;
   Print("         Riesgo real: $", DoubleToString(realRisk, 2), " (", lots, " * $", pointValue, ")");
   
   if(realRisk > riskMoney * 1.1) // Tolerancia del 10%
   {
      Print("         ⚠️ Riesgo real excede el riesgo calculado en más del 10%");
   }
   
   // Verificación final de margen
   ENUM_ORDER_TYPE orderType = (entryPrice > stopLoss) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double marginRequired = 0;
   
   if(!OrderCalcMargin(orderType, symbol, lots, entryPrice, marginRequired))
   {
      int error = GetLastError();
      Print("         ⚠️ Error calculando margen requerido para verificación final: ", error, " - ", GetErrorDescription(error));
      Print("         Retornando cálculo sin ajuste de margen");
   }
   else
   {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      double maxAllowedMargin = freeMargin * (MaxMarginUse/100.0);
      
      Print("         Verificación final de margen:");
      Print("            Margen requerido: $", DoubleToString(marginRequired, 2));
      Print("            Margen libre: $", DoubleToString(freeMargin, 2));
      Print("            Máximo permitido (", MaxMarginUse, "%): $", DoubleToString(maxAllowedMargin, 2));
      
      if(marginRequired > maxAllowedMargin)
      {
         // Reducir lotes proporcionalmente
         double maxLotsByMargin = (maxAllowedMargin * lots) / marginRequired;
         double originalLots = lots;
         lots = MathFloor(maxLotsByMargin / volumeStep) * volumeStep;
         
         Print("         Margen limitado: ajustando de ", originalLots, " a ", lots);
         
         if(lots < volumeMin)
         {
            Print("         ❌ Volumen ajustado (", lots, ") es menor que el mínimo (", volumeMin, ")");
            return 0;
         }
      }
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
      
      // Errores de archivo (códigos 5000+)
      case 5002:        return "Archivo no encontrado (FILE_ERROR_FILENOTFOUND)";
      case 5004:        return "Demasiados archivos abiertos (FILE_ERROR_TOOMANYOPENED)";
      case 5006:        return "Handle inválido (FILE_ERROR_INVALIDHANDLE)";
      case 5010:        return "Acceso denegado (FILE_ERROR_ACCESS_DENIED)";
      
      // Errores de trading (códigos 10000+)
      case 10000:       return "Sin error";
      case 10001:       return "Resultado desconocido";
      case 10002:       return "Error en la operación";
      case 10003:       return "Formato inválido";
      case 10004:       return "Requote";
      case 10005:       return "Operación rechazada";
      case 10006:       return "Solicitud rechazada";
      case 10007:       return "Solicitud cancelada por el trader";
      case 10008:       return "Orden colocada";
      case 10009:       return "Solicitud completada";
      case 10010:       return "Solo parte de la solicitud fue completada";
      case 10011:       return "Error procesando solicitud";
      case 10012:       return "Solicitud cancelada por timeout";
      case 10013:       return "Solicitud inválida";
      case 10014:       return "Volumen inválido";
      case 10015:       return "Precio inválido";
      case 10016:       return "Stops inválidos";
      case 10017:       return "Trading deshabilitado";
      case 10018:       return "Mercado cerrado";
      case 10019:       return "Dinero insuficiente";
      case 10020:       return "Precios cambiados";
      case 10021:       return "Sin cotizaciones";
      case 10022:       return "Expiración de orden inválida";
      case 10023:       return "Estado de orden cambiado";
      case 10024:       return "Solicitudes demasiado frecuentes";
      case 10025:       return "Sin cambios en la solicitud";
      case 10026:       return "Autotrading deshabilitado por servidor";
      case 10027:       return "Autotrading deshabilitado por terminal";
      case 10028:       return "Solicitud bloqueada";
      case 10029:       return "Orden o posición congelada";
      
      default:          return "Error " + IntegerToString(errorCode);
   }
}
//+------------------------------------------------------------------+