//+------------------------------------------------------------------+
//|                                           JSONFileEA.mq5         |
//|                                      Lectura desde archivo JSON  |
//+------------------------------------------------------------------+
#property copyright "Elias Eduardo Liranza Perez"
#property version   "3.00"
#property strict
#property description "EA que recibe señales vía archivo JSON y ejecuta operaciones"

//--- Input parameters - ARCHIVO
input group "=== CONFIGURACIÓN DE ARCHIVO ==="
input string   JsonFilePath     = "C:\\señales\\senal.json";
input int      FileCheckInterval = 1;

//--- Input parameters - GESTIÓN DE RIESGO
input group "=== GESTIÓN DE RIESGO ==="
input double   BalanceReferencia = 0;
input double   RiskPercent       = 1.0;
input double   MaxRiskMoney      = 0;

//--- Input parameters - EJECUCIÓN
input group "=== CONFIGURACIÓN DE EJECUCIÓN ==="
input bool     AutoTrade         = true;
input int      MaxOpenAttempts    = 10;
input int      MaxModifyAttempts  = 10;
input int      Deviation          = 10;
input ENUM_ORDER_TYPE_FILLING FillingType = ORDER_FILLING_FOK;
input int      MagicNumber        = 234000;

//--- Input parameters - VALIDACIONES
input group "=== VALIDACIONES ==="
input bool     ValidateSymbol     = false;
input double   MinSLPoints        = 0;
input double   MinTPPoints        = 0;
input double   MaxSpreadPoints    = 0;
input bool     CheckFreeMargin    = true;
input double   MaxMarginUse       = 95.0;

//--- Global variables
string lastSignalUUID = "";
datetime lastFileCheck = 0;
int totalSignals = 0;
int totalTrades = 0;
bool isFirstRun = true;
datetime lastFileModTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("╔══════════════════════════════════════════════╗");
   Print("║   🚀 JSON FILE EA - VERSIÓN 2.0            ║");
   Print("╚══════════════════════════════════════════════╝");
   
   if(!ValidateInputs())
      return INIT_PARAMETERS_INCORRECT;
   
   // Mostrar información de la ruta
   Print("📁 Ruta configurada: ", JsonFilePath);
   Print("📁 Directorio de trabajo: ", TerminalInfoString(TERMINAL_DATA_PATH));
   Print("📁 Ruta común: ", TerminalInfoString(TERMINAL_COMMONDATA_PATH));
   
   // Verificar si el archivo existe
   if(FileExists(JsonFilePath))
   {
      Print("✅ Archivo encontrado: ", JsonFilePath);
      lastFileModTime = GetFileModTime(JsonFilePath);
   }
   else
   {
      Print("⚠️ El archivo no existe: ", JsonFilePath);
      Print("   Verifica que la ruta sea correcta");
      Print("   Intenta con: ", "\\Files\\senal.json");
   }
   
   Print("📊 Configuración de riesgo:");
   Print("   Balance referencia: ", (BalanceReferencia > 0 ? DoubleToString(BalanceReferencia, 2) : "Balance real"));
   Print("   Riesgo: ", RiskPercent, "%");
   
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
   
   return valid;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("📊 Estadísticas finales:");
   Print("   Señales recibidas: ", totalSignals);
   Print("   Operaciones ejecutadas: ", totalTrades);
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
   CheckJsonFile();
}

//+------------------------------------------------------------------+
//| Obtener tiempo de modificación del archivo                      |
//+------------------------------------------------------------------+
datetime GetFileModTime(string filePath)
{
   datetime modTime = 0;
   int fileHandle = FileOpen(filePath, FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   
   if(fileHandle != INVALID_HANDLE)
   {
      modTime = FileGetInteger(fileHandle, FILE_MODIFY_DATE);
      FileClose(fileHandle);
   }
   
   return modTime;
}

//+------------------------------------------------------------------+
//| Revisar archivo JSON                                            |
//+------------------------------------------------------------------+
void CheckJsonFile()
{
   // Verificar si el archivo existe
   if(!FileExists(JsonFilePath))
   {
      if(isFirstRun)
      {
         Print("⏳ Esperando archivo: ", JsonFilePath);
         isFirstRun = false;
      }
      return;
   }
   
   // Verificar si el archivo ha sido modificado
   datetime currentModTime = GetFileModTime(JsonFilePath);
   
   // Si es la primera vez o el archivo ha cambiado
   if(currentModTime > lastFileModTime)
   {
      Print("📝 Archivo modificado: ", TimeToString(currentModTime));
      lastFileModTime = currentModTime;
      
      // Leer el archivo JSON
      string jsonContent = ReadJsonFile(JsonFilePath);
      if(jsonContent != "")
      {
         totalSignals++;
         lastFileCheck = TimeCurrent();
         ProcessSignal(jsonContent);
      }
      else
      {
         Print("❌ Error al leer el archivo JSON");
      }
   }
}

//+------------------------------------------------------------------+
//| Leer archivo JSON con mejor manejo de errores                   |
//+------------------------------------------------------------------+
string ReadJsonFile(string filePath)
{
   string content = "";
   
   // Usar FILE_SHARE_READ para permitir que otros procesos lean el archivo
   int fileHandle = FileOpen(filePath, FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
   
   if(fileHandle != INVALID_HANDLE)
   {
      // Leer todo el contenido
      ulong fileSize = FileSize(fileHandle);
      if(fileSize > 0)
      {
         content = FileReadString(fileHandle, (int)fileSize);
         Print("📖 Archivo leído: ", fileSize, " bytes");
      }
      else
      {
         Print("⚠️ Archivo vacío");
      }
      
      FileClose(fileHandle);
   }
   else
   {
      int error = GetLastError();
      Print("❌ Error al abrir archivo: ", error);
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
   Print("📩 Señal #", totalSignals, " recibida");
   Print("📄 Contenido: ", jsonMessage);
   
   string currentSymbol = Symbol();
   
   SignalData signal;
   if(!ParseSignal(jsonMessage, signal))
   {
      Print("❌ Error parseando JSON");
      return;
   }
   
   if(signal.uuid == lastSignalUUID)
   {
      Print("⏭️ Señal duplicada ignorada (UUID: ", signal.uuid, ")");
      return;
   }
   
   Print("📊 Nueva señal con UUID: ", signal.uuid);
   Print("   Par: ", signal.pair, " | Tipo: ", signal.type);
   
   if(!ValidateSignal(signal, currentSymbol))
      return;
   
   if(AutoTrade && TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
   {
      if(ExecuteTradeWithRetry(signal))
      {
         lastSignalUUID = signal.uuid;
         Print("✅ UUID actualizado a: ", lastSignalUUID);
      }
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
   signal.uuid = ExtractJsonValue(json, "uuid");
   signal.pair = ExtractJsonValue(json, "par");
   signal.type = ExtractJsonValue(json, "tipo");
   signal.timeframe = ExtractJsonValue(json, "temporalidad");
   
   string entryStr = ExtractJsonValue(json, "entrada");
   string slStr = ExtractJsonValue(json, "sl");
   string tpStr = ExtractJsonValue(json, "tp");
   string pipsSlStr = ExtractJsonValue(json, "pips_sl");
   string ratioStr = ExtractJsonValue(json, "ratio");
   
   signal.entry = StringToDouble(entryStr);
   signal.sl = StringToDouble(slStr);
   signal.tp = StringToDouble(tpStr);
   signal.pips_sl = StringToDouble(pipsSlStr);
   signal.ratio = StringToDouble(ratioStr);
   
   if(signal.uuid == "")
   {
      Print("❌ JSON incompleto: falta uuid");
      return false;
   }
   
   if(signal.pair == "" || signal.type == "")
   {
      Print("❌ JSON incompleto: falta par o tipo");
      return false;
   }
   
   if(signal.entry == 0 || signal.sl == 0 || signal.tp == 0)
   {
      Print("❌ JSON incompleto: valores numéricos inválidos");
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Validar señal contra filtros                                    |
//+------------------------------------------------------------------+
bool ValidateSignal(SignalData &signal, string currentSymbol)
{
   if(ValidateSymbol && signal.pair != currentSymbol)
   {
      Print("⚠️ Señal para ", signal.pair, " ignorada - Este EA opera en ", currentSymbol);
      return false;
   }
   
   if(signal.sl <= 0 || signal.tp <= 0)
   {
      Print("⚠️ Señal ignorada - SL o TP inválidos (<=0)");
      return false;
   }
   
   double point = SymbolInfoDouble(currentSymbol, SYMBOL_POINT);
   double slPoints = MathAbs(signal.entry - signal.sl) / point;
   double tpPoints = MathAbs(signal.tp - signal.entry) / point;
   
   if(slPoints < MinSLPoints)
   {
      Print("⚠️ Señal ignorada - SL demasiado pequeño: ", slPoints, " puntos");
      return false;
   }
   
   if(tpPoints < MinTPPoints)
   {
      Print("⚠️ Señal ignorada - TP demasiado pequeño: ", tpPoints, " puntos");
      return false;
   }
   
   if(MaxSpreadPoints > 0)
   {
      long spreadLong = SymbolInfoInteger(currentSymbol, SYMBOL_SPREAD);
      double spread = (double)spreadLong;
      if(spread > MaxSpreadPoints)
      {
         Print("⚠️ Señal ignorada - Spread muy alto: ", spread, " puntos");
         return false;
      }
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
         if(json[end] == ',' || json[end] == '}' || json[end] == ']' || json[end] == ' ')
            break;
      }
      end++;
   }
   
   string result = StringSubstr(json, start, end - start);
   StringTrimLeft(result);
   StringTrimRight(result);
   
   return result;
}

//+------------------------------------------------------------------+
//| Ejecutar orden con sistema de reintentos                        |
//+------------------------------------------------------------------+
bool ExecuteTradeWithRetry(SignalData &signal)
{
   double balance = (BalanceReferencia > 0) ? BalanceReferencia : AccountInfoDouble(ACCOUNT_BALANCE);
   
   double askPrice = SymbolInfoDouble(signal.pair, SYMBOL_ASK);
   double bidPrice = SymbolInfoDouble(signal.pair, SYMBOL_BID);
   
   bool isBuy = (signal.type == "COMPRA");
   double entryPrice = isBuy ? askPrice : bidPrice;
   
   if(isBuy && signal.sl >= entryPrice)
   {
      Print("⚠️ SL de compra (", signal.sl, ") debe ser menor que precio actual (", entryPrice, ")");
      return false;
   }
   if(!isBuy && signal.sl <= entryPrice)
   {
      Print("⚠️ SL de venta (", signal.sl, ") debe ser mayor que precio actual (", entryPrice, ")");
      return false;
   }
   
   double volume = CalculateOptimalVolume(signal.pair, entryPrice, signal.sl, RiskPercent, balance);
   
   if(volume <= 0)
   {
      Print("❌ Volumen inválido: ", volume);
      return false;
   }
   
   Print("📊 Preparando orden: ", signal.pair, " ", isBuy ? "COMPRA" : "VENTA", " ", volume);
   
   ulong ticket = OpenOrderWithRetry(signal.pair, isBuy, volume, entryPrice);
   
   if(ticket > 0)
   {
      totalTrades++;
      Print("✅ Orden abierta. Ticket: ", ticket);
      
      if(!ModifyPositionSLTPWithRetry(ticket, signal.sl, signal.tp))
      {
         Print("⚠️ Operación sin SL/TP: ", ticket);
      }
      return true;
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Abrir orden con reintentos                                      |
//+------------------------------------------------------------------+
ulong OpenOrderWithRetry(string symbol, bool isBuy, double volume, double expectedPrice)
{
   for(int attempt = 1; attempt <= MaxOpenAttempts; attempt++)
   {
      double askPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double bidPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
      double price = isBuy ? askPrice : bidPrice;
      
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
      
      if(OrderSend(request, result))
      {
         return result.order;
      }
      
      Sleep(100);
   }
   
   return 0;
}

//+------------------------------------------------------------------+
//| Modificar SL/TP con reintentos                                  |
//+------------------------------------------------------------------+
bool ModifyPositionSLTPWithRetry(ulong ticket, double sl, double tp)
{
   for(int attempt = 1; attempt <= MaxModifyAttempts; attempt++)
   {
      if(!PositionSelectByTicket(ticket))
         return false;
      
      string symbol = PositionGetString(POSITION_SYMBOL);
      
      MqlTradeRequest request = {};
      MqlTradeResult result = {};
      
      request.action = TRADE_ACTION_SLTP;
      request.position = ticket;
      request.symbol = symbol;
      request.sl = sl;
      request.tp = tp;
      request.magic = MagicNumber;
      
      if(OrderSend(request, result))
         return true;
      
      Sleep(100);
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Calcular volumen óptimo                                         |
//+------------------------------------------------------------------+
double CalculateOptimalVolume(string symbol, double entryPrice, double stopLoss, 
                               double riskPercent, double balance)
{
   double volumeMin = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   
   if(tickValue <= 0) tickValue = 1.0;
   
   double riskMoney = balance * (riskPercent / 100.0);
   
   if(MaxRiskMoney > 0 && riskMoney > MaxRiskMoney)
      riskMoney = MaxRiskMoney;
   
   double slDistance = MathAbs(entryPrice - stopLoss);
   double pointValue = tickValue * (slDistance / tickSize);
   
   double lots = riskMoney / pointValue;
   lots = MathMax(volumeMin, MathMin(volumeMax, lots));
   
   if(volumeStep > 0)
      lots = MathFloor(lots / volumeStep) * volumeStep;
   
   return NormalizeDouble(lots, 2);
}
