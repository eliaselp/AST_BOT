//+------------------------------------------------------------------+
//|                                           WebSocketNativeEA.mq5 |
//|                                      Conexión WebSocket Nativa  |
//+------------------------------------------------------------------+
#property copyright "Elias Eduardo Liranza Perez"
#property version   "3.00"
#property strict
#property description "EA que recibe señales vía WebSocket y ejecuta operaciones"
#property description "con gestión de riesgo y sistema de reintentos"

// Incluir la librería nativa (sin DLL)
#include <Websocket.mqh>

//--- Input parameters - CONEXIÓN
input group "=== CONFIGURACIÓN DE CONEXIÓN ==="
input string   ServerIP        = "216.226.149.70";
input int      ServerPort      = 8000;
input string   RoomName        = "";
input string   Token           = "";
input int      ReconnectTimer  = 1;           // Timer de reconexión (segundos)

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
input int      Deviation          = 10;         // Desviación permitida
input ENUM_ORDER_TYPE_FILLING FillingType = ORDER_FILLING_FOK;  // Tipo de filling
input int      MagicNumber        = 234000;     // Magic number del EA

//--- Input parameters - VALIDACIONES
input group "=== VALIDACIONES ==="
input bool     ValidateSymbol     = false;       // Validar símbolo de la señal
input double   MinSLPoints        = 0;         // Mínimo SL en puntos
input double   MinTPPoints        = 0;         // Mínimo TP en puntos
input double   MaxSpreadPoints    = 0;          // 0 = sin límite
input bool     CheckFreeMargin    = true;       // Verificar margen libre
input double   MaxMarginUse       = 80.0;       // % Máx de margen a usar

//--- Global variables
CWebsocket ws;
bool isConnected = false;
datetime lastSignalTime = 0;
int totalSignals = 0;
int totalTrades = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("╔══════════════════════════════════════════════╗");
   Print("║   🚀 WebSocket EA - VERSIÓN ROBUSTA 2.0     ║");
   Print("╚══════════════════════════════════════════════╝");
   
   // Validar parámetros
   if(!ValidateInputs())
      return INIT_PARAMETERS_INCORRECT;
   
   Print("📊 Configuración de riesgo:");
   Print("   Balance referencia: ", (BalanceReferencia > 0 ? DoubleToString(BalanceReferencia, 2) : "Balance real"));
   Print("   Riesgo: ", RiskPercent, "%");
   Print("   Intentos apertura: ", MaxOpenAttempts);
   Print("   Intentos SL/TP: ", MaxModifyAttempts);
   
   // Inicializar WebSocket
   if(ws.Init() < 0)
   {
      Print("❌ Error al inicializar WebSocket");
      return INIT_FAILED;
   }
   
   // Conectar al servidor
   if(!ConnectToServer())
      return INIT_FAILED;
   
   EventSetTimer(ReconnectTimer);
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
//| Conectar al servidor WebSocket                                  |
//+------------------------------------------------------------------+
bool ConnectToServer()
{
   string url = StringFormat("ws://%s:%d/ws/room/%s/%s/", 
                ServerIP, ServerPort, RoomName, Token);
   
   Print("🔄 Conectando a: ", url);
   
   // CORREGIDO: Usar ClientConnect con IP y Puerto
   int ret = ws.ClientConnect(ServerIP, ServerPort);
   if(ret < 0)
   {
      Print("❌ Error de conexión: ", ws.GetError());
      return false;
   }
   
   isConnected = true;
   Print("✅ Conectado correctamente");
   return true;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   if(isConnected)
   {
      ws.ClientDisconnect();
      ws.Deinit();
      Print("📊 Estadísticas finales:");
      Print("   Señales recibidas: ", totalSignals);
      Print("   Operaciones ejecutadas: ", totalTrades);
      Print("🔌 Desconectado");
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!isConnected) return;
   
   // Procesar mensajes entrantes
   string message = ws.Receive();
   if(message != "")
   {
      totalSignals++;
      lastSignalTime = TimeCurrent();
      ProcessSignal(message);
   }
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
   if(!isConnected)
   {
      Print("🔄 Intentando reconectar...");
      if(ConnectToServer())
      {
         Print("✅ Reconectado!");
      }
   }
   else
   {
      // Verificar salud de la conexión
      static datetime lastCheck = 0;
      if(TimeCurrent() - lastCheck > 60) // Cada minuto
      {
         lastCheck = TimeCurrent();
         if(TimeCurrent() - lastSignalTime > 300) // 5 minutos sin señal
         {
            Print("⚠️ ", (TimeCurrent() - lastSignalTime), " segundos sin recibir señales");
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Procesar señal de trading                                        |
//+------------------------------------------------------------------+
void ProcessSignal(string jsonMessage)
{
   Print("📩 Señal #", totalSignals, " recibida: ", jsonMessage);
   
   // Obtener el símbolo del gráfico actual
   string currentSymbol = Symbol();
   
   // Parsear JSON con manejo de errores
   SignalData signal;
   if(!ParseSignal(jsonMessage, signal))
   {
      Print("❌ Error parseando JSON");
      return;
   }
   
   // Aplicar todos los filtros y validaciones
   if(!ValidateSignal(signal, currentSymbol))
      return;
   
   Print("📊 Señal válida: ", signal.pair, " | ", signal.type, " | SL: ", signal.sl, " | TP: ", signal.tp);
   
   // CORREGIDO: En MQL5 usamos TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) en lugar de IsTradeAllowed()
   if(AutoTrade && TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
   {
      ExecuteTradeWithRetry(signal);
   }
}

//+------------------------------------------------------------------+
//| Estructura para datos de señal                                  |
//+------------------------------------------------------------------+
struct SignalData
{
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
   signal.pair = ExtractJsonValue(json, "par");
   signal.type = ExtractJsonValue(json, "tipo");
   signal.timeframe = ExtractJsonValue(json, "temporalidad");
   signal.entry = StringToDouble(ExtractJsonValue(json, "entrada"));
   signal.sl = StringToDouble(ExtractJsonValue(json, "sl"));
   signal.tp = StringToDouble(ExtractJsonValue(json, "tp"));
   signal.pips_sl = StringToDouble(ExtractJsonValue(json, "pips_sl"));
   signal.ratio = StringToDouble(ExtractJsonValue(json, "ratio"));
   
   // Validar campos obligatorios
   if(signal.pair == "" || signal.type == "")
   {
      Print("❌ JSON incompleto: falta par o tipo");
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Validar señal contra filtros                                    |
//+------------------------------------------------------------------+
bool ValidateSignal(SignalData &signal, string currentSymbol)
{
   // Validar símbolo
   if(ValidateSymbol && signal.pair != currentSymbol)
   {
      Print("⚠️ Señal para ", signal.pair, " ignorada - Este EA opera en ", currentSymbol);
      return false;
   }
   
   // Validar que tenemos SL y TP
   if(signal.sl <= 0 || signal.tp <= 0)
   {
      Print("⚠️ Señal ignorada - SL o TP inválidos (<=0)");
      return false;
   }
   
   // Validar distancias mínimas
   double point = SymbolInfoDouble(currentSymbol, SYMBOL_POINT);
   double slPoints = MathAbs(signal.entry - signal.sl) / point;
   double tpPoints = MathAbs(signal.tp - signal.entry) / point;
   
   if(slPoints < MinSLPoints)
   {
      Print("⚠️ Señal ignorada - SL demasiado pequeño: ", slPoints, " puntos (mínimo ", MinSLPoints, ")");
      return false;
   }
   
   if(tpPoints < MinTPPoints)
   {
      Print("⚠️ Señal ignorada - TP demasiado pequeño: ", tpPoints, " puntos (mínimo ", MinTPPoints, ")");
      return false;
   }
   
   // Validar spread
   if(MaxSpreadPoints > 0)
   {
      long spread = SymbolInfoInteger(currentSymbol, SYMBOL_SPREAD);
      if(spread > MaxSpreadPoints)
      {
         Print("⚠️ Señal ignorada - Spread muy alto: ", spread, " puntos (máx ", MaxSpreadPoints, ")");
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
         if(json[end] == ',' || json[end] == '}' || json[end] == ']') break;
      }
      end++;
   }
   
   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Ejecutar orden con sistema de reintentos completo               |
//+------------------------------------------------------------------+
void ExecuteTradeWithRetry(SignalData &signal)
{
   // Obtener balance para gestión de riesgo
   double balance = (BalanceReferencia > 0) ? BalanceReferencia : AccountInfoDouble(ACCOUNT_BALANCE);
   
   // Obtener precios actuales
   double askPrice = SymbolInfoDouble(signal.pair, SYMBOL_ASK);
   double bidPrice = SymbolInfoDouble(signal.pair, SYMBOL_BID);
   
   // Determinar dirección
   bool isBuy = (signal.type == "COMPRA");
   double entryPrice = isBuy ? askPrice : bidPrice;
   
   // Validar SL respecto a precio actual
   if(isBuy && signal.sl >= entryPrice)
   {
      Print("⚠️ SL de compra (", signal.sl, ") debe ser menor que precio actual (", entryPrice, ")");
      return;
   }
   if(!isBuy && signal.sl <= entryPrice)
   {
      Print("⚠️ SL de venta (", signal.sl, ") debe ser mayor que precio actual (", entryPrice, ")");
      return;
   }
   
   // Calcular volumen
   double volume = CalculateOptimalVolume(signal.pair, entryPrice, signal.sl, 
                                         RiskPercent, balance);
   
   if(volume <= 0)
   {
      Print("❌ Volumen inválido: ", volume);
      return;
   }
   
   Print("📊 Preparando orden:");
   Print("   Símbolo: ", signal.pair);
   Print("   Tipo: ", isBuy ? "COMPRA" : "VENTA");
   Print("   Volumen: ", volume);
   Print("   Riesgo: ", RiskPercent, "% (", DoubleToString(balance * RiskPercent/100.0, 2), ")");
   
   // PASO 1: Abrir orden con reintentos
   ulong ticket = OpenOrderWithRetry(signal.pair, isBuy, volume, entryPrice);
   
   if(ticket > 0)
   {
      totalTrades++;
      Print("✅ Orden abierta exitosamente. Ticket: ", ticket);
      
      // PASO 2: Establecer SL/TP con reintentos
      if(!ModifyPositionSLTPWithRetry(ticket, signal.sl, signal.tp))
      {
         Print("⚠️ CRÍTICO: Operación ", ticket, " abierta SIN PROTECCIÓN");
         Print("   Por favor, revise manualmente la operación");
      }
   }
}

//+------------------------------------------------------------------+
//| Abrir orden con reintentos (sleep máximo 1 segundo)            |
//+------------------------------------------------------------------+
ulong OpenOrderWithRetry(string symbol, bool isBuy, double volume, double expectedPrice)
{
   Print("🚀 Iniciando apertura de orden (máx ", MaxOpenAttempts, " intentos)...");
   
   for(int attempt = 1; attempt <= MaxOpenAttempts; attempt++)
   {
      // Obtener precios actualizados
      double askPrice = SymbolInfoDouble(symbol, SYMBOL_ASK);
      double bidPrice = SymbolInfoDouble(symbol, SYMBOL_BID);
      double price = isBuy ? askPrice : bidPrice;
      
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
      request.comment = "WebSocket Signal";
      
      Print("📝 Intento #", attempt, " - Precio: ", price);
      
      // Verificar margen si está activado
      if(CheckFreeMargin)
      {
         double marginRequired = 0;
         // CORREGIDO: OrderCalcMargin devuelve bool
         if(OrderCalcMargin(request.type, symbol, volume, price, marginRequired))
         {
            double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
         
            if(marginRequired > freeMargin * (MaxMarginUse/100.0))
            {
               Print("⚠️ Intento ", attempt, ": Margen insuficiente");
               Sleep(100); // Sleep fijo de 100ms (máximo 1 segundo)
               continue;
            }
         }
      }
      
      // Enviar orden
      if(OrderSend(request, result))
      {
         Print("✅ Orden ejecutada en intento #", attempt);
         Print("   Ticket: ", result.order, " | Precio: ", result.price);
         return result.order;
      }
      else
      {
         string errorDesc = GetErrorDescription(result.retcode);
         Print("❌ Intento ", attempt, " fallido: ", errorDesc, " (", result.retcode, ")");
         
         // Sleep fijo de 100ms (no más de 1 segundo)
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
      // Verificar que la posición aún existe
      if(!PositionSelectByTicket(ticket))
      {
         Print("⚠️ Intento ", attempt, ": La posición ", ticket, " ya no existe");
         return false;
      }
      
      // Obtener tipo de posición
      long positionType = PositionGetInteger(POSITION_TYPE);
      string symbol = PositionGetString(POSITION_SYMBOL);
      
      // Validar SL/TP
      double currentPrice = (positionType == POSITION_TYPE_BUY) ? 
                            SymbolInfoDouble(symbol, SYMBOL_BID) : 
                            SymbolInfoDouble(symbol, SYMBOL_ASK);
      
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
      
      // Enviar modificación
      if(OrderSend(request, result))
      {
         Print("✅ SL/TP establecidos en intento ", attempt);
         Print("   SL: ", sl, " | TP: ", tp);
         return true;
      }
      else
      {
         string errorDesc = GetErrorDescription(result.retcode);
         Print("⚠️ Intento ", attempt, ": Error ", errorDesc, " (", result.retcode, ")");
         
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
   // Obtener información del símbolo
   double volumeMin = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   
   // Si tickValue es 0 (puede pasar en algunos brokers), calcularlo
   if(tickValue <= 0)
   {
      tickValue = 1.0; // Valor por defecto, pero deberías ajustar según tu broker
      Print("⚠️ Advertencia: tickValue = 0, usando valor por defecto");
   }
   
   // Calcular riesgo monetario
   double riskMoney = balance * (riskPercent / 100.0);
   
   // Aplicar límite máximo si está configurado
   if(MaxRiskMoney > 0 && riskMoney > MaxRiskMoney)
   {
      riskMoney = MaxRiskMoney;
      Print("   Aplicando límite máximo de riesgo: $", MaxRiskMoney);
   }
   
   // Calcular distancia en puntos
   double slDistance = MathAbs(entryPrice - stopLoss);
   double slPoints = slDistance / point;
   
   if(slPoints < MinSLPoints)
   {
      Print("⚠️ SL demasiado pequeño: ", slPoints, " puntos (mínimo ", MinSLPoints, ")");
      return 0;
   }
   
   // Calcular valor por punto
   double pointValue = tickValue * (slDistance / tickSize);
   
   // Calcular lotes
   double lots = riskMoney / pointValue;
   
   // Ajustar a límites
   lots = MathMax(volumeMin, MathMin(volumeMax, lots));
   
   // Aplicar step
   if(volumeStep > 0)
   {
      lots = MathFloor(lots / volumeStep) * volumeStep;
   }
   
   // CORREGIDO: Cast explícito de long a double
   double marginRequired = 0;
   ENUM_ORDER_TYPE orderType = (entryPrice > stopLoss) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   
   if(OrderCalcMargin(orderType, symbol, lots, entryPrice, marginRequired))
   {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      
      if(marginRequired > freeMargin * (MaxMarginUse/100.0))
      {
         // Reducir lotes proporcionalmente
         if(marginRequired > 0)
         {
            double maxLotsByMargin = (freeMargin * (MaxMarginUse/100.0) * lots) / marginRequired;
            lots = MathFloor(maxLotsByMargin / volumeStep) * volumeStep;
            
            Print("   Margen limitado: ajustando a ", lots);
         }
      }
   }
   
   return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| Obtener descripción del error                                   |
//+------------------------------------------------------------------+
string GetErrorDescription(int errorCode)
{
   switch(errorCode)
   {
      case 0:           return "OK";
      case 10004:       return "Requote";
      case 10006:       return "Request rejected";
      case 10007:       return "Request canceled by trader";
      case 10008:       return "Order placed";
      case 10009:       return "Request completed";
      case 10010:       return "Only part of the request was completed";
      case 10011:       return "Request processing error";
      case 10012:       return "Request canceled by timeout";
      case 10013:       return "Invalid request";
      case 10014:       return "Invalid volume";
      case 10015:       return "Invalid price";
      case 10016:       return "Invalid stops";
      case 10017:       return "Trade is disabled";
      case 10018:       return "Market is closed";
      case 10019:       return "Not enough money";
      case 10020:       return "Prices changed";
      case 10021:       return "No quotes";
      case 10022:       return "Invalid order expiration";
      case 10023:       return "Order state changed";
      case 10024:       return "Too frequent requests";
      case 10025:       return "No changes in request";
      case 10026:       return "Autotrading disabled by server";
      case 10027:       return "Autotrading disabled by client terminal";
      case 10028:       return "Request locked";
      case 10029:       return "Order or position frozen";
      default:          return "Unknown error: " + IntegerToString(errorCode);
   }
}
