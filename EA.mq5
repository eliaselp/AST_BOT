//+------------------------------------------------------------------+
//|                                           JSONFileEA.mq5         |
//|                                      Lectura desde archivo JSON  |
//+------------------------------------------------------------------+
#property copyright "Elias Eduardo Liranza Perez"
#property version   "3.13"
#property strict
#property description "EA que recibe señales vía archivo JSON y ejecuta operaciones"
#property description "con gestión de riesgo y sistema de reintentos"

//--- Input parameters - ARCHIVO
input group "=== CONFIGURACIÓN DE ARCHIVO ==="
input string   JsonFilePath     = "C:\\señales\\senal.json";  // Ruta del archivo JSON
input int      FileCheckInterval = 1;           // Intervalo de revisión (segundos)

//--- Input parameters - GESTIÓN DE RIESGO
input group "=== GESTIÓN DE RIESGO ==="
input double   BalanceReferencia = 0;          // 0 = usar balance real (BalanceReferencia)
input double   RiskPercent       = 1.0;        // % de riesgo por operación (RiskPercent)
input double   MaxRiskMoney      = 0;          // 0 = sin límite máximo (MaxRiskMoney)

//--- Input parameters - EJECUCIÓN
input group "=== CONFIGURACIÓN DE EJECUCIÓN ==="
input bool     AutoTrade         = true;
input int      MaxOpenAttempts    = 10;        // Máx intentos para abrir
input int      MaxModifyAttempts  = 10;        // Máx intentos para SL/TP
input int      Deviation          = 10;         // Desviación permitida
input ENUM_ORDER_TYPE_FILLING FillingType = ORDER_FILLING_FOK;  // Tipo de filling
input int      MagicNumber        = 234000;     // Magic number del EA

//--- Input parameters - VALIDACIONES
input group "=== VALIDACIONES ==="
input bool     ValidateSymbol     = false;       // Validar símbolo de la señal
input double   MinSLPoints        = 0;         // Mínimo SL en puntos
input double   MinTPPoints        = 0;         // Mínimo TP en puntos
input double   MaxSpreadPoints    = 0;          // 0 = sin límite (MaxSpreadPoints)
input bool     CheckFreeMargin    = true;       // Verificar margen libre
input double   MaxMarginUse       = 95.0;       // % Máx de margen a usar

//--- Input parameters - DEBUG
input group "=== CONFIGURACIÓN DE DEBUG ==="
input bool     DebugMode          = true;       // Modo debug con logs detallados
input bool     LogJsonContent     = true;       // Mostrar contenido JSON completo
input bool     LogEverySecond     = true;       // Mostrar log cada segundo (aunque no haya archivo)
input bool     LogFileOperations  = true;       // Mostrar operaciones de archivo detalladas

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
   Print("║                    🚀 JSON FILE EA - VERSIÓN 3.13                        ║");
   Print("║                    📊 MODO DEBUG EXTREMO - LOGS DETALLADOS               ║");
   Print("╚══════════════════════════════════════════════════════════════════════════╝");
   
   // Validar parámetros
   if(!ValidateInputs())
      return INIT_PARAMETERS_INCORRECT;
   
   // Verificar que el archivo existe
   if(!FileExists(JsonFilePath))
   {
      Print("⚠️ El archivo no existe: ", JsonFilePath);
      Print("   Se creará cuando llegue la primera señal");
   }
   else
   {
      Print("✅ Archivo JSON encontrado: ", JsonFilePath);
      
      // Mostrar información del archivo
      if(LogFileOperations)
      {
         Print("📁 Información del archivo:");
         Print("   Ruta absoluta: ", JsonFilePath);
         Print("   ¿Existe?: Sí");
         
         // Intentar abrir el archivo para ver permisos
         int testHandle = FileOpen(JsonFilePath, FILE_READ|FILE_TXT|FILE_ANSI);
         if(testHandle != INVALID_HANDLE)
         {
            Print("   ✅ Se puede abrir el archivo para lectura");
            FileClose(testHandle);
         }
         else
         {
            int error = GetLastError();
            Print("   ❌ NO se puede abrir el archivo. Error: ", error, " - ", GetErrorDescription(error));
         }
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
   Print("   Log operaciones archivo: ", LogFileOperations ? "ACTIVADO" : "DESACTIVADO");
   
   Print("⏱️ Timer configurado cada ", FileCheckInterval, " segundo(s)");
   Print("📢 IMPORTANTE: Mostrando logs CADA SEGUNDO como solicitaste");
   
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
   timerCounter++; // Incrementar contador cada segundo
   datetime currentTime = TimeCurrent();
   
   // MOSTRAR LOG CADA SEGUNDO - Esto es lo que pediste
   if(LogEverySecond || DebugMode)
   {
      string timeStr = TimeToString(currentTime, TIME_SECONDS);
      bool fileExists = FileExists(JsonFilePath);
      string statusStr = fileExists ? "📂 ARCHIVO ENCONTRADO" : "⏳ ESPERANDO ARCHIVO";
      
      Print("⏱️ [", timeStr, "] Segundo #", timerCounter, " - Verificando: ", JsonFilePath, " | ", statusStr);
   }
   
   CheckJsonFile();
}

//+------------------------------------------------------------------+
//| Revisar archivo JSON                                            |
//+------------------------------------------------------------------+
void CheckJsonFile()
{
   datetime checkTime = TimeCurrent();
   
   // Verificar si el archivo existe
   if(!FileExists(JsonFilePath))
   {
      if(isFirstRun)
      {
         Print("⏳ [", TimeToString(checkTime, TIME_SECONDS), "] Esperando archivo: ", JsonFilePath);
         isFirstRun = false;
      }
      else if(LogFileOperations)
      {
         // Log periódico de que sigue esperando (cada 30 segundos)
         static datetime lastWaitLog = 0;
         if(checkTime - lastWaitLog >= 30)
         {
            Print("⏳ [", TimeToString(checkTime, TIME_SECONDS), "] Aún esperando archivo: ", JsonFilePath);
            lastWaitLog = checkTime;
         }
      }
      return;
   }
   
   if(DebugMode || LogFileOperations)
   {
      Print("📂 [", TimeToString(checkTime, TIME_SECONDS), "] Archivo encontrado, intentando leer contenido...");
   }
   
   // Leer el archivo JSON
   string jsonContent = ReadJsonFile(JsonFilePath);
   
   // Verificar si se leyó correctamente
   if(jsonContent == "")
   {
      Print("❌ [", TimeToString(checkTime, TIME_SECONDS), "] Error al leer el archivo JSON - Archivo vacío o corrupto");
      
      // Intentar obtener más información sobre el error
      int lastError = GetLastError();
      if(lastError != 0)
      {
         Print("   Código de error: ", lastError, " - ", GetErrorDescription(lastError));
      }
      
      // Verificar permisos del archivo
      if(LogFileOperations)
      {
         int testHandle = FileOpen(JsonFilePath, FILE_READ|FILE_TXT|FILE_ANSI);
         if(testHandle == INVALID_HANDLE)
         {
            int error = GetLastError();
            Print("   ❌ No se puede abrir el archivo. Error: ", error, " - ", GetErrorDescription(error));
         }
         else
         {
            Print("   ✅ El archivo se puede abrir pero está vacío o tiene formato incorrecto");
            FileClose(testHandle);
         }
      }
      return;
   }
   
   // Mostrar información del archivo leído
   Print("📖 [", TimeToString(checkTime, TIME_SECONDS), "] Archivo leído correctamente. Tamaño: ", StringLen(jsonContent), " caracteres");
   
   // Mostrar los primeros caracteres para verificar
   if(LogFileOperations)
   {
      string preview = StringSubstr(jsonContent, 0, MathMin(100, StringLen(jsonContent)));
      Print("   Vista previa (primeros 100 chars): '", preview, "'");
   }
   
   // Mostrar el JSON completo si está activado
   if(LogJsonContent)
   {
      Print("📄 [", TimeToString(checkTime, TIME_SECONDS), "] CONTENIDO JSON COMPLETO:");
      Print("╔══════════════════════════════════════════════════════════════════════════╗");
      
      // Dividir el JSON en líneas para mejor visualización
      string jsonLines[];
      int lines = ExplodeString(jsonContent, "\n", jsonLines);
      
      if(lines == 0)
      {
         // Si no hay saltos de línea, mostrar el contenido completo
         string line = jsonContent;
         if(StringLen(line) > 200)
            line = StringSubstr(line, 0, 200) + "... (truncado)";
         Print("║ ", line);
      }
      else
      {
         for(int i = 0; i < lines; i++)
         {
            // Limitar longitud para no saturar el log
            string line = jsonLines[i];
            if(StringLen(line) > 200)
               line = StringSubstr(line, 0, 200) + "... (truncado)";
            Print("║ ", line);
         }
      }
      
      Print("╚══════════════════════════════════════════════════════════════════════════╝");
   }
   
   totalSignals++;
   lastFileCheck = checkTime;
   Print("📩 [", TimeToString(checkTime, TIME_SECONDS), "] Señal #", totalSignals, " recibida (tamaño: ", StringLen(jsonContent), " bytes)");
   
   ProcessSignal(jsonContent);
}

//+------------------------------------------------------------------+
//| Función auxiliar para dividir string en líneas                  |
//+------------------------------------------------------------------+
int ExplodeString(string str, string delimiter, string &result[])
{
   ArrayResize(result, 0);
   int pos = 0;
   int found = 0;
   
   while((found = StringFind(str, delimiter, pos)) != -1)
   {
      int size = ArraySize(result);
      ArrayResize(result, size + 1);
      result[size] = StringSubstr(str, pos, found - pos);
      pos = found + StringLen(delimiter);
   }
   
   if(pos < StringLen(str))
   {
      int size = ArraySize(result);
      ArrayResize(result, size + 1);
      result[size] = StringSubstr(str, pos);
   }
   
   return ArraySize(result);
}

//+------------------------------------------------------------------+
//| Leer archivo JSON                                               |
//+------------------------------------------------------------------+
string ReadJsonFile(string filePath)
{
   string content = "";
   
   if(LogFileOperations)
   {
      Print("   Intentando abrir archivo: ", filePath);
   }
   
   int fileHandle = FileOpen(filePath, FILE_READ|FILE_TXT|FILE_ANSI);
   
   if(fileHandle != INVALID_HANDLE)
   {
      if(LogFileOperations)
      {
         Print("   ✅ Archivo abierto correctamente. Handle: ", fileHandle);
      }
      
      // Leer todo el contenido
      ulong fileSize = FileSize(fileHandle);
      if(LogFileOperations)
      {
         Print("   Tamaño del archivo: ", fileSize, " bytes");
      }
      
      if(fileSize > 0)
      {
         content = FileReadString(fileHandle, (int)fileSize);
         
         if(DebugMode)
         {
            Print("   📖 Archivo leído. Longitud del contenido: ", StringLen(content), " caracteres");
         }
      }
      else
      {
         Print("⚠️ El archivo está vacío (tamaño 0 bytes)");
      }
      
      FileClose(fileHandle);
      if(LogFileOperations)
      {
         Print("   Archivo cerrado");
      }
   }
   else
   {
      int error = GetLastError();
      Print("❌ Error al abrir archivo: ", error, " - ", GetErrorDescription(error));
      
      // Información adicional sobre el error
      if(error == 5002) // FILE_ERROR_FILENOTFOUND
      {
         Print("   El archivo no existe en la ruta especificada");
      }
      else if(error == 5004) // FILE_ERROR_TOOMANYOPENED
      {
         Print("   Demasiados archivos abiertos");
      }
      else if(error == 5006) // FILE_ERROR_INVALIDHANDLE
      {
         Print("   Handle inválido");
      }
      else if(error == 5010) // FILE_ERROR_ACCESS_DENIED
      {
         Print("   Acceso denegado - Verificar permisos del archivo");
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
   
   if(LogFileOperations && !exists)
   {
      static datetime lastFileCheckLog = 0;
      datetime currentTime = TimeCurrent();
      
      if(currentTime - lastFileCheckLog >= 30) // Log cada 30 segundos
      {
         Print("🔍 Verificando existencia de archivo: ", filePath, " -> ", exists ? "EXISTE" : "NO EXISTE");
         lastFileCheckLog = currentTime;
      }
   }
   
   return exists;
}

//+------------------------------------------------------------------+
//| Procesar señal de trading                                        |
//+------------------------------------------------------------------+
void ProcessSignal(string jsonMessage)
{
   datetime processTime = TimeCurrent();
   string currentSymbol = Symbol();
   
   Print("⚙️ [", TimeToString(processTime, TIME_SECONDS), "] Procesando señal #", totalSignals, "...");
   
   // Parsear JSON con manejo de errores
   SignalData signal;
   if(!ParseSignal(jsonMessage, signal))
   {
      Print("❌ [", TimeToString(processTime, TIME_SECONDS), "] Error parseando JSON - Formato inválido");
      
      if(DebugMode)
      {
         Print("🔍 Primeros 200 caracteres del JSON problemático:");
         Print("   ", StringSubstr(jsonMessage, 0, 200));
         
         // Intentar identificar el problema
         if(StringFind(jsonMessage, "{") < 0)
            Print("   ⚠️ El JSON no comienza con '{'");
         if(StringFind(jsonMessage, "}") < 0)
            Print("   ⚠️ El JSON no termina con '}'");
         if(StringFind(jsonMessage, "uuid") < 0)
            Print("   ⚠️ No se encuentra el campo 'uuid'");
         if(StringFind(jsonMessage, "par") < 0)
            Print("   ⚠️ No se encuentra el campo 'par'");
         if(StringFind(jsonMessage, "tipo") < 0)
            Print("   ⚠️ No se encuentra el campo 'tipo'");
      }
      return;
   }
   
   Print("✅ [", TimeToString(processTime, TIME_SECONDS), "] JSON parseado correctamente");
   Print("   UUID: ", signal.uuid);
   Print("   Par: ", signal.pair);
   Print("   Tipo: ", signal.type);
   Print("   Entrada: ", signal.entry);
   Print("   SL: ", signal.sl);
   Print("   TP: ", signal.tp);
   
   // Verificar UUID para evitar duplicados
   if(signal.uuid == lastSignalUUID && lastSignalUUID != "")
   {
      Print("⏭️ [", TimeToString(processTime, TIME_SECONDS), "] Señal duplicada ignorada (UUID: ", signal.uuid, ")");
      Print("   Último UUID procesado: ", lastSignalUUID);
      return;
   }
   
   Print("📊 Nueva señal con UUID: ", signal.uuid);
   Print("   Último UUID procesado: ", lastSignalUUID == "" ? "NINGUNO" : lastSignalUUID);
   
   // Aplicar todos los filtros y validaciones
   if(!ValidateSignal(signal, currentSymbol))
   {
      Print("❌ [", TimeToString(processTime, TIME_SECONDS), "] Señal rechazada por validaciones");
      return;
   }
   
   Print("✅ [", TimeToString(processTime, TIME_SECONDS), "] Señal válida: ", 
         signal.pair, " | ", signal.type, " | SL: ", signal.sl, " | TP: ", signal.tp);
   
   bool tradeAllowed = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);
   Print("📊 Estado AutoTrade: ", AutoTrade ? "ACTIVADO" : "DESACTIVADO");
   Print("📊 Trading permitido por terminal: ", tradeAllowed ? "SÍ" : "NO");
   
   if(AutoTrade && tradeAllowed)
   {
      Print("🚀 Ejecutando orden...");
      if(ExecuteTradeWithRetry(signal))
      {
         // Actualizar UUID solo si la operación fue exitosa
         lastSignalUUID = signal.uuid;
         Print("✅ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] UUID actualizado a: ", lastSignalUUID);
      }
      else
      {
         Print("❌ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] Falló la ejecución de la orden");
      }
   }
   else
   {
      if(!AutoTrade)
         Print("⚠️ AutoTrade desactivado - Señal ignorada");
      if(!tradeAllowed)
         Print("⚠️ Trading no permitido por terminal - Verificar conexión y configuración");
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
   // CORRECCIÓN: StringTrimLeft y StringTrimRight modifican la variable original
   StringTrimRight(json);
   StringTrimLeft(json);
   
   if(DebugMode)
   {
      Print("🔍 Parseando JSON...");
   }
   
   signal.uuid = ExtractJsonValue(json, "uuid");
   signal.pair = ExtractJsonValue(json, "par");
   signal.type = ExtractJsonValue(json, "tipo");
   signal.timeframe = ExtractJsonValue(json, "temporalidad");
   
   string entryStr = ExtractJsonValue(json, "entrada");
   string slStr = ExtractJsonValue(json, "sl");
   string tpStr = ExtractJsonValue(json, "tp");
   string pipsSlStr = ExtractJsonValue(json, "pips_sl");
   string ratioStr = ExtractJsonValue(json, "ratio");
   
   if(DebugMode)
   {
      Print("   Valores extraídos (raw):");
      Print("   uuid: '", signal.uuid, "'");
      Print("   par: '", signal.pair, "'");
      Print("   tipo: '", signal.type, "'");
      Print("   entrada: '", entryStr, "'");
      Print("   sl: '", slStr, "'");
      Print("   tp: '", tpStr, "'");
   }
   
   signal.entry = StringToDouble(entryStr);
   signal.sl = StringToDouble(slStr);
   signal.tp = StringToDouble(tpStr);
   signal.pips_sl = StringToDouble(pipsSlStr);
   signal.ratio = StringToDouble(ratioStr);
   
   // Validar campos obligatorios
   if(signal.uuid == "")
   {
      Print("❌ JSON incompleto: falta uuid");
      return false;
   }
   
   if(signal.pair == "")
   {
      Print("❌ JSON incompleto: falta par");
      return false;
   }
   
   if(signal.type == "")
   {
      Print("❌ JSON incompleto: falta tipo (debe ser 'COMPRA' o 'VENTA')");
      return false;
   }
   
   if(signal.type != "COMPRA" && signal.type != "VENTA")
   {
      Print("❌ Tipo inválido: '", signal.type, "' - Debe ser 'COMPRA' o 'VENTA'");
      return false;
   }
   
   if(signal.entry <= 0)
   {
      Print("❌ Precio de entrada inválido: ", signal.entry);
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Validar señal contra filtros                                    |
//+------------------------------------------------------------------+
bool ValidateSignal(SignalData &signal, string currentSymbol)
{
   datetime validTime = TimeCurrent();
   
   Print("🔍 [", TimeToString(validTime, TIME_SECONDS), "] Validando señal...");
   
   // Validar símbolo
   if(ValidateSymbol && signal.pair != currentSymbol)
   {
      Print("⚠️ [", TimeToString(validTime, TIME_SECONDS), "] Señal para ", signal.pair, 
            " ignorada - Este EA opera en ", currentSymbol);
      return false;
   }
   
   // Validar que tenemos SL y TP
   if(signal.sl <= 0)
   {
      Print("⚠️ [", TimeToString(validTime, TIME_SECONDS), "] Señal ignorada - SL inválido (<=0): ", signal.sl);
      return false;
   }
   
   if(signal.tp <= 0)
   {
      Print("⚠️ [", TimeToString(validTime, TIME_SECONDS), "] Señal ignorada - TP inválido (<=0): ", signal.tp);
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
   
   Print("   Distancia SL: ", slPoints, " puntos");
   Print("   Distancia TP: ", tpPoints, " puntos");
   Print("   Spread actual: ", spread, " puntos");
   Print("   Ask/Bid: ", ask, " / ", bid);
   
   if(slPoints < MinSLPoints)
   {
      Print("⚠️ [", TimeToString(validTime, TIME_SECONDS), "] Señal ignorada - SL demasiado pequeño: ", 
            slPoints, " puntos (mínimo ", MinSLPoints, ")");
      return false;
   }
   
   if(tpPoints < MinTPPoints)
   {
      Print("⚠️ [", TimeToString(validTime, TIME_SECONDS), "] Señal ignorada - TP demasiado pequeño: ", 
            tpPoints, " puntos (mínimo ", MinTPPoints, ")");
      return false;
   }
   
   // Validar spread
   if(MaxSpreadPoints > 0 && spread > MaxSpreadPoints)
   {
      Print("⚠️ [", TimeToString(validTime, TIME_SECONDS), "] Señal ignorada - Spread muy alto: ", 
            spread, " puntos (máx ", MaxSpreadPoints, ")");
      return false;
   }
   
   Print("✅ [", TimeToString(validTime, TIME_SECONDS), "] Todas las validaciones superadas");
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
   Print("🚀 [", TimeToString(execTime, TIME_SECONDS), "] INICIANDO EJECUCIÓN DE ORDEN");
   
   // Obtener balance para gestión de riesgo
   double balance = (BalanceReferencia > 0) ? BalanceReferencia : AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   
   Print("📊 Estado de cuenta:");
   Print("   Balance: $", DoubleToString(balance, 2));
   Print("   Equity: $", DoubleToString(equity, 2));
   Print("   Margen libre: $", DoubleToString(freeMargin, 2));
   
   // Obtener precios actuales
   double askPrice = SymbolInfoDouble(signal.pair, SYMBOL_ASK);
   double bidPrice = SymbolInfoDouble(signal.pair, SYMBOL_BID);
   
   Print("💱 Precios de mercado para ", signal.pair, ":");
   Print("   Ask: ", askPrice);
   Print("   Bid: ", bidPrice);
   
   // Determinar dirección
   bool isBuy = (signal.type == "COMPRA");
   double entryPrice = isBuy ? askPrice : bidPrice;
   
   Print("   Dirección: ", isBuy ? "COMPRA" : "VENTA");
   Print("   Precio de entrada estimado: ", entryPrice);
   
   // Validar SL respecto a precio actual
   if(isBuy && signal.sl >= entryPrice)
   {
      Print("⚠️ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] SL de compra (", signal.sl, 
            ") debe ser menor que precio actual (", entryPrice, ")");
      return false;
   }
   if(!isBuy && signal.sl <= entryPrice)
   {
      Print("⚠️ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] SL de venta (", signal.sl, 
            ") debe ser mayor que precio actual (", entryPrice, ")");
      return false;
   }
   
   // Calcular volumen
   Print("🧮 Calculando volumen óptimo...");
   double volume = CalculateOptimalVolume(signal.pair, entryPrice, signal.sl, 
                                         RiskPercent, balance);
   
   if(volume <= 0)
   {
      Print("❌ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] Volumen inválido: ", volume);
      return false;
   }
   
   double riskAmount = balance * RiskPercent / 100.0;
   if(MaxRiskMoney > 0 && riskAmount > MaxRiskMoney)
      riskAmount = MaxRiskMoney;
   
   Print("📊 Preparando orden:");
   Print("   Símbolo: ", signal.pair);
   Print("   Tipo: ", isBuy ? "COMPRA" : "VENTA");
   Print("   Volumen: ", volume);
   Print("   Riesgo: ", RiskPercent, "% ($", DoubleToString(riskAmount, 2), ")");
   Print("   SL: ", signal.sl);
   Print("   TP: ", signal.tp);
   
   // PASO 1: Abrir orden con reintentos
   Print("🔄 PASO 1: Abriendo orden...");
   ulong ticket = OpenOrderWithRetry(signal.pair, isBuy, volume, entryPrice);
   
   if(ticket > 0)
   {
      totalTrades++;
      Print("✅ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] PASO 1 COMPLETADO - Orden abierta. Ticket: ", ticket);
      
      // PASO 2: Establecer SL/TP con reintentos
      Print("🔄 PASO 2: Estableciendo SL/TP...");
      if(!ModifyPositionSLTPWithRetry(ticket, signal.sl, signal.tp))
      {
         Print("⚠️ CRÍTICO [", TimeToString(TimeCurrent(), TIME_SECONDS), "] Operación ", ticket, " abierta SIN PROTECCIÓN");
         Print("   Por favor, revise manualmente la operación");
         Print("   SL deseado: ", signal.sl);
         Print("   TP deseado: ", signal.tp);
         return true; // La orden se abrió, aunque sin SL/TP
      }
      
      Print("✅ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] EJECUCIÓN COMPLETADA EXITOSAMENTE");
      return true;
   }
   
   Print("❌ [", TimeToString(TimeCurrent(), TIME_SECONDS), "] EJECUCIÓN FALLIDA - No se pudo abrir la orden");
   return false;
}

//+------------------------------------------------------------------+
//| Abrir orden con reintentos (sleep máximo 1 segundo)            |
//+------------------------------------------------------------------+
ulong OpenOrderWithRetry(string symbol, bool isBuy, double volume, double expectedPrice)
{
   Print("🚀 Iniciando apertura de orden (máx ", MaxOpenAttempts, " intentos)...");
   
   for(int attempt = 1; attempt <= MaxOpenAttempts; attempt++)
   {
      Print("📝 Intento #", attempt, " de ", MaxOpenAttempts);
      
      // Obtener precios actualizados
      double askPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double bidPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
      double price = isBuy ? askPrice : bidPrice;
      double spread = (double)SymbolInfoInteger(symbol, SYMBOL_SPREAD) * SymbolInfoDouble(symbol, SYMBOL_POINT);
      
      Print("   Precios actuales - Ask: ", askPrice, " | Bid: ", bidPrice, " | Spread: $", spread);
      Print("   Precio de ejecución: ", price);
      
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
      
      if(DebugMode)
      {
         Print("   Request details:");
         Print("      Action: DEAL");
         Print("      Symbol: ", request.symbol);
         Print("      Volume: ", request.volume);
         Print("      Type: ", request.type == ORDER_TYPE_BUY ? "BUY" : "SELL");
         Print("      Price: ", request.price);
         Print("      Deviation: ", request.deviation);
         Print("      Filling: ", EnumToString(FillingType));
         Print("      Magic: ", request.magic);
      }
      
      // Verificar margen si está activado
      if(CheckFreeMargin)
      {
         double marginRequired = 0;
         if(!OrderCalcMargin(request.type, symbol, volume, price, marginRequired))
         {
            int error = GetLastError();
            Print("⚠️ Error calculando margen requerido: ", error, " - ", GetErrorDescription(error));
            Sleep(100);
            continue;
         }
         
         double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
         double maxAllowedMargin = freeMargin * (MaxMarginUse/100.0);
         
         Print("   Verificación de margen:");
         Print("      Margen requerido: $", DoubleToString(marginRequired, 2));
         Print("      Margen libre: $", DoubleToString(freeMargin, 2));
         Print("      Máximo permitido (", MaxMarginUse, "%): $", DoubleToString(maxAllowedMargin, 2));
         
         if(marginRequired > maxAllowedMargin)
         {
            Print("⚠️ Intento ", attempt, ": Margen insuficiente. Requerido: $", marginRequired, 
                  ", Máximo permitido: $", maxAllowedMargin);
            Sleep(100);
            continue;
         }
         
         Print("   ✅ Margen suficiente");
      }
      
      // Enviar orden
      Print("   Enviando orden...");
      if(OrderSend(request, result))
      {
         Print("✅ Orden ejecutada en intento #", attempt);
         Print("   Ticket: ", result.order);
         Print("   Precio de ejecución: ", result.price);
         Print("   Volumen ejecutado: ", result.volume);
         Print("   Comentario: ", result.comment);
         
         if(DebugMode && result.retcode != 10009) // 10009 = TRADE_RETCODE_DONE
         {
            Print("   Código retorno: ", result.retcode, " - ", GetErrorDescription(result.retcode));
         }
         
         return result.order;
      }
      else
      {
         string errorDesc = GetErrorDescription(result.retcode);
         int lastError = GetLastError();
         
         Print("❌ Intento ", attempt, " fallido:");
         Print("   Error código: ", result.retcode, " - ", errorDesc);
         if(lastError != 0 && lastError != result.retcode)
            Print("   Último error sistema: ", lastError, " - ", GetErrorDescription(lastError));
         
         // Información adicional del resultado
         if(result.retcode > 0)
         {
            Print("   Detalles del resultado:");
            Print("      Deal: ", result.deal);
            Print("      Order: ", result.order);
            Print("      Volume: ", result.volume);
            Print("      Price: ", result.price);
            Print("      Bid: ", result.bid);
            Print("      Ask: ", result.ask);
         }
         
         // Sleep fijo de 100ms
         Sleep(100);
      }
   }
   
   Print("❌ No se pudo abrir la orden después de ", MaxOpenAttempts, " intentos");
   return 0;
}

//+------------------------------------------------------------------+
//| Modificar SL/TP con reintentos (sleep máximo 500ms)            |
//+------------------------------------------------------------------+
bool ModifyPositionSLTPWithRetry(ulong ticket, double sl, double tp)
{
   Print("🔄 Intentando establecer SL/TP para ticket ", ticket, " (máx ", MaxModifyAttempts, " intentos)");
   
   for(int attempt = 1; attempt <= MaxModifyAttempts; attempt++)
   {
      Print("📝 Intento #", attempt, " de ", MaxModifyAttempts);
      
      // Verificar que la posición aún existe
      if(!PositionSelectByTicket(ticket))
      {
         int error = GetLastError();
         Print("⚠️ Intento ", attempt, ": La posición ", ticket, " ya no existe");
         Print("   Error: ", error, " - ", GetErrorDescription(error));
         return false;
      }
      
      // Obtener información de la posición
      long positionType = PositionGetInteger(POSITION_TYPE);
      string symbol = PositionGetString(POSITION_SYMBOL);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentVolume = PositionGetDouble(POSITION_VOLUME);
      
      Print("   Posición actual:");
      Print("      Símbolo: ", symbol);
      Print("      Tipo: ", positionType == POSITION_TYPE_BUY ? "BUY" : "SELL");
      Print("      Precio apertura: ", openPrice);
      Print("      Volumen: ", currentVolume);
      Print("      SL actual: ", currentSL > 0 ? DoubleToString(currentSL) : "NO DEFINIDO");
      Print("      TP actual: ", currentTP > 0 ? DoubleToString(currentTP) : "NO DEFINIDO");
      
      // Obtener precio actual
      double currentPrice = (positionType == POSITION_TYPE_BUY) ? 
                            SymbolInfoDouble(symbol, SYMBOL_BID) : 
                            SymbolInfoDouble(symbol, SYMBOL_ASK);
      
      Print("   Precio actual: ", currentPrice);
      Print("   SL deseado: ", sl);
      Print("   TP deseado: ", tp);
      
      // Verificar que SL tiene sentido
      if((positionType == POSITION_TYPE_BUY && sl >= currentPrice) ||
         (positionType == POSITION_TYPE_SELL && sl <= currentPrice))
      {
         Print("⚠️ Intento ", attempt, ": SL inválido para la posición actual");
         Print("   Precio actual: ", currentPrice, " | SL: ", sl);
         Sleep(100);
         continue;
      }
      
      // Preparar request de modificación
      MqlTradeRequest request = {};
      MqlTradeResult result = {};
      
      request.action = TRADE_ACTION_SLTP;
      request.position = ticket;
      request.symbol = symbol;
      request.sl = sl;
      request.tp = tp;
      request.magic = MagicNumber;
      
      if(DebugMode)
      {
         Print("   Request details:");
         Print("      Action: SLTP");
         Print("      Position: ", request.position);
         Print("      Symbol: ", request.symbol);
         Print("      SL: ", request.sl);
         Print("      TP: ", request.tp);
         Print("      Magic: ", request.magic);
      }
      
      // Enviar modificación
      Print("   Enviando modificación...");
      if(OrderSend(request, result))
      {
         Print("✅ SL/TP establecidos en intento ", attempt);
         Print("   SL: ", sl);
         Print("   TP: ", tp);
         Print("   Código retorno: ", result.retcode, " - ", GetErrorDescription(result.retcode));
         return true;
      }
      else
      {
         string errorDesc = GetErrorDescription(result.retcode);
         int lastError = GetLastError();
         
         Print("⚠️ Intento ", attempt, ": Error en modificación:");
         Print("   Código: ", result.retcode, " - ", errorDesc);
         if(lastError != 0 && lastError != result.retcode)
            Print("   Último error sistema: ", lastError, " - ", GetErrorDescription(lastError));
         
         if(result.retcode == 10016) // Invalid stops
         {
            Print("   Posibles causas:");
            Print("      - SL/TP demasiado cerca del precio actual");
            Print("      - SL/TP fuera de los límites permitidos por el broker");
            Print("      - Requisitos de distancia mínima no cumplidos");
         }
         
         // Sleep fijo de 100ms
         Sleep(100);
      }
   }
   
   Print("❌ No se pudo establecer SL/TP después de ", MaxModifyAttempts, " intentos");
   return false;
}

//+------------------------------------------------------------------+
//| Calcular volumen óptimo con múltiples validaciones              |
//+------------------------------------------------------------------+
double CalculateOptimalVolume(string symbol, double entryPrice, double stopLoss, 
                               double riskPercent, double balance)
{
   Print("🧮 Cálculo de volumen óptimo:");
   
   // Obtener información del símbolo
   double volumeMin = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double contractSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   
   Print("   Información del símbolo:");
   Print("      Volume Min: ", volumeMin);
   Print("      Volume Max: ", volumeMax);
   Print("      Volume Step: ", volumeStep);
   Print("      Tick Value: $", tickValue);
   Print("      Tick Size: ", tickSize);
   Print("      Point: ", point);
   Print("      Contract Size: ", contractSize);
   
   // Si tickValue es 0 (puede pasar en algunos brokers), calcularlo
   if(tickValue <= 0)
   {
      tickValue = 1.0;
      Print("⚠️ Advertencia: tickValue = 0, usando valor por defecto: $1.0");
      Print("   Esto puede afectar la precisión del cálculo del volumen");
   }
   
   // Calcular riesgo monetario
   double riskMoney = balance * (riskPercent / 100.0);
   Print("   Riesgo calculado: ", riskPercent, "% de $", DoubleToString(balance, 2), " = $", DoubleToString(riskMoney, 2));
   
   // Aplicar límite máximo si está configurado
   if(MaxRiskMoney > 0 && riskMoney > MaxRiskMoney)
   {
      riskMoney = MaxRiskMoney;
      Print("   Aplicando límite máximo de riesgo: $", MaxRiskMoney);
   }
   
   // Calcular distancia en puntos
   double slDistance = MathAbs(entryPrice - stopLoss);
   double slPoints = slDistance / point;
   
   Print("   Distancia SL: ", slPoints, " puntos (", slDistance, " en precio)");
   
   if(slPoints < MinSLPoints)
   {
      Print("⚠️ SL demasiado pequeño: ", slPoints, " puntos (mínimo ", MinSLPoints, ")");
      return 0;
   }
   
   // Calcular valor por punto
   double pointValue = tickValue * (slDistance / tickSize);
   double riskPerLot = pointValue;
   
   Print("   Valor por lote: $", DoubleToString(riskPerLot, 2));
   Print("      Tick Value: $", tickValue, " * (", slDistance, " / ", tickSize, ") = $", pointValue);
   
   // Calcular lotes
   double lots = riskMoney / pointValue;
   Print("   Lotes calculados (sin ajustar): ", lots, " ($", riskMoney, " / $", pointValue, ")");
   
   // Ajustar a límites
   lots = MathMax(volumeMin, MathMin(volumeMax, lots));
   Print("   Lotes ajustados a límites: ", lots, " (min: ", volumeMin, ", max: ", volumeMax, ")");
   
   // Aplicar step
   if(volumeStep > 0)
   {
      double originalLots = lots;
      lots = MathFloor(lots / volumeStep) * volumeStep;
      Print("   Lotes ajustados a step: ", lots, " (original: ", originalLots, ", step: ", volumeStep, ")");
   }
   
   // Verificar riesgo real
   double realRisk = lots * pointValue;
   Print("   Riesgo real: $", DoubleToString(realRisk, 2), " (", lots, " * $", pointValue, ")");
   
   if(realRisk > riskMoney * 1.1) // Tolerancia del 10%
   {
      Print("⚠️ Riesgo real excede el riesgo calculado en más del 10%");
   }
   
   // Verificación final de margen
   ENUM_ORDER_TYPE orderType = (entryPrice > stopLoss) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double marginRequired = 0;
   
   if(!OrderCalcMargin(orderType, symbol, lots, entryPrice, marginRequired))
   {
      int error = GetLastError();
      Print("⚠️ Error calculando margen requerido para verificación final: ", error, " - ", GetErrorDescription(error));
      Print("   Retornando cálculo sin ajuste de margen");
   }
   else
   {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      double maxAllowedMargin = freeMargin * (MaxMarginUse/100.0);
      
      Print("   Verificación final de margen:");
      Print("      Margen requerido: $", DoubleToString(marginRequired, 2));
      Print("      Margen libre: $", DoubleToString(freeMargin, 2));
      Print("      Máximo permitido (", MaxMarginUse, "%): $", DoubleToString(maxAllowedMargin, 2));
      
      if(marginRequired > maxAllowedMargin)
      {
         // Reducir lotes proporcionalmente
         double maxLotsByMargin = (maxAllowedMargin * lots) / marginRequired;
         double originalLots = lots;
         lots = MathFloor(maxLotsByMargin / volumeStep) * volumeStep;
         
         Print("   Margen limitado: ajustando de ", originalLots, " a ", lots);
         
         if(lots < volumeMin)
         {
            Print("❌ Volumen ajustado (", lots, ") es menor que el mínimo (", volumeMin, ")");
            return 0;
         }
      }
   }
   
   double normalizedLots = NormalizeDouble(lots, 2);
   Print("✅ Volumen final: ", normalizedLots);
   
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
      
      default:          return "Error desconocido: " + IntegerToString(errorCode);
   }
}
//+------------------------------------------------------------------+
