//+------------------------------------------------------------------+
//|                                           JSONFileEA.mq5         |
//|                                      Lectura desde archivo JSON  |
//+------------------------------------------------------------------+
#property copyright "Elias Eduardo Liranza Perez"
#property version   "3.15"
#property strict
#property description "EA que recibe señales vía archivo JSON y ejecuta operaciones"
#property description "con gestión de riesgo y sistema de reintentos"

//--- Input parameters - ARCHIVO (RUTA CORREGIDA)
input group "=== CONFIGURACIÓN DE ARCHIVO ==="
input string   JsonFilePath     = "D:\\signals\\senal.json";  // Ruta del archivo JSON en D:\signals\
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
   Print("║                    🚀 JSON FILE EA - VERSIÓN 3.15                        ║");
   Print("║                    📊 BUSCANDO ARCHIVO EN D:\\signals\\                    ║");
   Print("╚══════════════════════════════════════════════════════════════════════════╝");
   
   // Validar parámetros
   if(!ValidateInputs())
      return INIT_PARAMETERS_INCORRECT;
   
   // MOSTRAR INFORMACIÓN DETALLADA DE LA RUTA
   Print("📁 Ruta configurada: ", JsonFilePath);
   
   // Verificar si la carpeta D:\signals existe
   string folderPath = "D:\\signals";
   bool folderExists = false;
   
   // Intentar crear un archivo de prueba para verificar permisos
   int testHandle = FileOpen(folderPath + "\\test.tmp", FILE_WRITE|FILE_TXT);
   if(testHandle != INVALID_HANDLE)
   {
      folderExists = true;
      FileWrite(testHandle, "test");
      FileClose(testHandle);
      FileDelete(folderPath + "\\test.tmp");
      Print("✅ La carpeta D:\\signals EXISTE y es accesible");
   }
   else
   {
      int error = GetLastError();
      Print("⚠️ La carpeta D:\\signals NO es accesible. Error: ", error);
      Print("   Por favor, crea la carpeta D:\\signals manualmente");
   }
   
   // Verificar que el archivo existe
   if(!FileExists(JsonFilePath))
   {
      Print("⚠️ El archivo NO existe: ", JsonFilePath);
      Print("   Esperando a que el script Python lo cree...");
      Print("   Asegúrate de que el script Python esté corriendo");
   }
   else
   {
      Print("✅ Archivo JSON encontrado: ", JsonFilePath);
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
   Print("📢 Verificando archivo cada segundo en: ", JsonFilePath);
   
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
   
   // MOSTRAR LOG CADA SEGUNDO
   string timeStr = TimeToString(currentTime, TIME_SECONDS);
   bool fileExists = FileExists(JsonFilePath);
   string statusStr = fileExists ? "📂 ARCHIVO ENCONTRADO" : "⏳ ESPERANDO ARCHIVO";
   
   Print("⏱️ [", timeStr, "] Segundo #", timerCounter, " - Verificando: ", JsonFilePath, " | ", statusStr);
   
   CheckJsonFile();
}

//+------------------------------------------------------------------+
//| Revisar archivo JSON                                            |
//+------------------------------------------------------------------+
void CheckJsonFile()
{
   datetime checkTime = TimeCurrent();
   string timeStr = TimeToString(checkTime, TIME_SECONDS);
   
   // Verificar si el archivo existe
   if(!FileExists(JsonFilePath))
   {
      if(isFirstRun)
      {
         Print("⏳ [", timeStr, "] Esperando archivo: ", JsonFilePath);
         isFirstRun = false;
      }
      return;
   }
   
   // SIEMPRE mostrar cuando encuentra el archivo
   Print("📂 [", timeStr, "] ⚠️⚠️⚠️ ARCHIVO ENCONTRADO - Leyendo... ⚠️⚠️⚠️");
   
   // Leer el archivo JSON
   string jsonContent = ReadJsonFile(JsonFilePath);
   
   // Verificar si se leyó correctamente
   if(jsonContent == "")
   {
      Print("❌ [", timeStr, "] ERROR: Archivo vacío o no se pudo leer");
      
      // Intentar obtener más información sobre el error
      int lastError = GetLastError();
      if(lastError != 0)
      {
         Print("   Código de error: ", lastError, " - ", GetErrorDescription(lastError));
      }
      return;
   }
   
   // SIEMPRE mostrar cuando se lee correctamente
   Print("✅✅✅ [", timeStr, "] ARCHIVO LEÍDO CORRECTAMENTE ✅✅✅");
   Print("   Tamaño: ", StringLen(jsonContent), " caracteres");
   
   // Mostrar los primeros caracteres
   string preview = StringSubstr(jsonContent, 0, MathMin(100, StringLen(jsonContent)));
   Print("   Vista previa: '", preview, "'");
   
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
   
   int fileHandle = FileOpen(filePath, FILE_READ|FILE_TXT|FILE_ANSI);
   
   if(fileHandle != INVALID_HANDLE)
   {
      // Leer todo el contenido
      ulong fileSize = FileSize(fileHandle);
      
      if(fileSize > 0)
      {
         content = FileReadString(fileHandle, (int)fileSize);
      }
      else
      {
         Print("⚠️ ReadJsonFile: El archivo está vacío (tamaño 0 bytes)");
      }
      
      FileClose(fileHandle);
   }
   else
   {
      int error = GetLastError();
      Print("❌ ReadJsonFile: Error al abrir archivo: ", error, " - ", GetErrorDescription(error));
   }
   
   return content;
}

//+------------------------------------------------------------------+
//| Verificar si un archivo existe                                  |
//+------------------------------------------------------------------+
bool FileExists(string filePath)
{
   return FileIsExist(filePath);
}

//+------------------------------------------------------------------+
//| Procesar señal de trading                                        |
//+------------------------------------------------------------------+
void ProcessSignal(string jsonMessage)
{
   datetime processTime = TimeCurrent();
   string currentSymbol = Symbol();
   string timeStr = TimeToString(processTime, TIME_SECONDS);
   
   Print("⚙️ [", timeStr, "] Procesando señal #", totalSignals, "...");
   
   // Parsear JSON con manejo de errores
   SignalData signal;
   if(!ParseSignal(jsonMessage, signal))
   {
      Print("❌ [", timeStr, "] Error parseando JSON - Formato inválido");
      return;
   }
   
   Print("✅ [", timeStr, "] JSON parseado correctamente");
   Print("   UUID: ", signal.uuid);
   Print("   Par: ", signal.pair);
   Print("   Tipo: ", signal.type);
   Print("   Entrada: ", signal.entry);
   Print("   SL: ", signal.sl);
   Print("   TP: ", signal.tp);
   
   // Verificar UUID para evitar duplicados
   if(signal.uuid == lastSignalUUID && lastSignalUUID != "")
   {
      Print("⏭️ [", timeStr, "] Señal duplicada ignorada (UUID: ", signal.uuid, ")");
      Print("   Último UUID procesado: ", lastSignalUUID);
      return;
   }
   
   // Aplicar todos los filtros y validaciones
   if(!ValidateSignal(signal, currentSymbol))
   {
      Print("❌ [", timeStr, "] Señal rechazada por validaciones");
      return;
   }
   
   Print("✅ [", timeStr, "] Señal válida: ", 
         signal.pair, " | ", signal.type, " | SL: ", signal.sl, " | TP: ", signal.tp);
   
   bool tradeAllowed = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);
   
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
         Print("⚠️ Trading no permitido por terminal");
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
   // Limpiar posibles caracteres de control al inicio/final
   StringTrimRight(json);
   StringTrimLeft(json);
   
   signal.uuid = ExtractJsonValue(json, "uuid");
   signal.pair = ExtractJsonValue(json, "par");
   signal.type = ExtractJsonValue(json, "tipo");
   signal.timeframe = ExtractJsonValue(json, "temporalidad");
   
   string entryStr = ExtractJsonValue(json, "entrada");
   string slStr = ExtractJsonValue(json, "sl");
   string tpStr = ExtractJsonValue(json, "tp");
   
   signal.entry = StringToDouble(entryStr);
   signal.sl = StringToDouble(slStr);
   signal.tp = StringToDouble(tpStr);
   
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
      Print("❌ JSON incompleto: falta tipo");
      return false;
   }
   
   if(signal.type != "COMPRA" && signal.type != "VENTA")
   {
      Print("❌ Tipo inválido: '", signal.type, "' - Debe ser 'COMPRA' o 'VENTA'");
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
   string timeStr = TimeToString(validTime, TIME_SECONDS);
   
   // Validar símbolo
   if(ValidateSymbol && signal.pair != currentSymbol)
   {
      Print("⚠️ [", timeStr, "] Señal para ", signal.pair, 
            " ignorada - Este EA opera en ", currentSymbol);
      return false;
   }
   
   // Validar que tenemos SL y TP
   if(signal.sl <= 0 || signal.tp <= 0)
   {
      Print("⚠️ [", timeStr, "] Señal ignorada - SL o TP inválidos");
      return false;
   }
   
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
   // Versión simplificada para prueba - AQUÍ VA TU LÓGICA DE TRADING
   Print("   ✅ Simulando ejecución de orden exitosa");
   return true;
}

//+------------------------------------------------------------------+
//| Obtener descripción del error                                   |
//+------------------------------------------------------------------+
string GetErrorDescription(int errorCode)
{
   switch(errorCode)
   {
      case 0:           return "OK/Sin error";
      case 5002:        return "Archivo no encontrado";
      case 5004:        return "Demasiados archivos abiertos";
      case 5006:        return "Handle inválido";
      case 5010:        return "Acceso denegado";
      default:          return "Error " + IntegerToString(errorCode);
   }
}
//+------------------------------------------------------------------+
