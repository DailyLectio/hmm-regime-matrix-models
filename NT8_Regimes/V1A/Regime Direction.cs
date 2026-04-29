// This source code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © CapovexIntech

//@version=6

indicator(title = 'Regime Direction', overlay = true, max_labels_count = 500)

// Bollinger Bands
length = 20
src = close
mult = 2
basis = ta.sma(src, length)
dev = mult * ta.stdev(src, length)
upper = basis + dev
lower = basis - dev
offset = 0 //input.int(0, "Offset", minval = -500, maxval = 500)
plot(basis, 'Basis', color = color.new(#FF6D00, 0), offset = offset)
p1 = plot(upper, 'Upper', color = color.new(#2962FF, 0), offset = offset)
p2 = plot(lower, 'Lower', color = color.new(#2962FF, 0), offset = offset)
fill(p1, p2, title = 'Background', color = color.rgb(33, 150, 243, 95))

// Stop Loss

lengtha = 14
smoothing = input.string(title = 'Smoothing', defval = 'RMA', options = ['RMA', 'SMA', 'EMA', 'WMA'], group = 'Stop Loss')
ma_function(source, lengtha) =>
    switch smoothing
        'RMA' => ta.rma(source, lengtha)
        'SMA' => ta.sma(source, lengtha)
        'EMA' => ta.ema(source, lengtha)
        => ta.wma(source, lengtha)

atr = ma_function(ta.tr(true), lengtha)
x = input.float(2.0, title = 'Float Value', group = 'Stop Loss')
chigh = high - atr * x // buy sl
clow = low + atr * x //sell sl

// Moving Averages

ema9 = ta.ema(close, 9)
ema14 = ta.ema(close, 14)
ema21 = ta.ema(close, 21)

uptrend = ema9 < low and ema14 < low // green
downtrend = ema14 > high and ema21 > high // red

sideway = ema9 < high and ema9 > low //Yellow
sideway1 = ema21 > low and ema21 < high //Yellow

//  DEMA

lengthd = 100
srcd = close
e1 = ta.ema(srcd, lengthd)
e2 = ta.ema(e1, lengthd)
dema = 2 * e1 - e2

length2 = 200
src2 = close
e12 = ta.ema(src2, length2)
e22 = ta.ema(e12, length2)
dema2 = 2 * e12 - e22


Bullish = dema > dema2
Bearish = dema < dema2

// SuperTrend

//@version=6

atrPeriod = 10
factor = 1

[supertrend, direction] = ta.supertrend(factor, atrPeriod)

upTrend1 = direction < 0
downTrend1 = direction > 0


// Volatility 

// ADX

len = 14
th = 14

TrueRange = math.max(math.max(high - low, math.abs(high - nz(close[1]))), math.abs(low - nz(close[1])))
DirectionalMovementPlus = high - nz(high[1]) > nz(low[1]) - low ? math.max(high - nz(high[1]), 0) : 0
DirectionalMovementMinus = nz(low[1]) - low > high - nz(high[1]) ? math.max(nz(low[1]) - low, 0) : 0

SmoothedTrueRange = 0.0
SmoothedTrueRange := nz(SmoothedTrueRange[1]) - nz(SmoothedTrueRange[1]) / len + TrueRange

SmoothedDirectionalMovementPlus = 0.0
SmoothedDirectionalMovementPlus := nz(SmoothedDirectionalMovementPlus[1]) - nz(SmoothedDirectionalMovementPlus[1]) / len + DirectionalMovementPlus

SmoothedDirectionalMovementMinus = 0.0
SmoothedDirectionalMovementMinus := nz(SmoothedDirectionalMovementMinus[1]) - nz(SmoothedDirectionalMovementMinus[1]) / len + DirectionalMovementMinus

DIPlus = SmoothedDirectionalMovementPlus / SmoothedTrueRange * 100
DIMinus = SmoothedDirectionalMovementMinus / SmoothedTrueRange * 100
DX = math.abs(DIPlus - DIMinus) / (DIPlus + DIMinus) * 100
ADX = ta.sma(DX, len)

lowvol = ADX > 0 and ADX <= 20 //Low Volatile-red
medvol = ADX > 20 and ADX <= 30 //Medium Volatile-green
highvol = ADX > 30 and ADX <= 40 //High Volatile-yellow
vhighvol = ADX > 40 and ADX <= 75 //Very High Volatile-red
extremevol = ADX > 75 and ADX <= 100 //Extreme Volatile-red

// Relative Strength Index (RSI)


ma(source, length, type) =>
    switch type
        'SMA' => ta.sma(source, length)
        'Bollinger Bands' => ta.sma(source, length)
        'EMA' => ta.ema(source, length)
        'SMMA (RMA)' => ta.rma(source, length)
        'WMA' => ta.wma(source, length)
        'VWMA' => ta.vwma(source, length)

rsiLengthInput = 14
rsiSourceInput = close
maTypeInput = 'SMA'
maLengthInput = 14

up = ta.rma(math.max(ta.change(rsiSourceInput), 0), rsiLengthInput)
down = ta.rma(-math.min(ta.change(rsiSourceInput), 0), rsiLengthInput)
rsi = down == 0 ? 100 : up == 0 ? 0 : 100 - 100 / (1 + up / down)
rsiMA = ma(rsi, maLengthInput, maTypeInput)

overbought = rsi > 75
oversold = rsi < 25

//MACD Formula

fast_length = 12
slow_length = 26
signal_length = 9

// Calculating

fast_ma = ta.ema(src, fast_length)
slow_ma = ta.ema(src, slow_length)
macd = fast_ma - slow_ma
signal = ta.ema(macd, signal_length)
hist = macd - signal

/// Table

greenc = color.green
redc = color.red
yellowc = color.yellow

///// -- Table Inputs

dash_loc = input.session('Bottom Right', 'Bank Dashboard Location', options = ['Top Right', 'Bottom Right', 'Top Left', 'Bottom Left', 'Middle Right', 'Bottom Center'], group = 'Dashboard Settings')

text_size = input.session('Small', 'Dashboard Size', options = ['Tiny', 'Small', 'Normal', 'Large'], group = 'Dashboard Settings')

max = 120
min = 10

// Prepare table

var table testTable = table.new(position.top_right, 5, 4, border_width = 1)
f_fillCell(_table, _column, _row, _title, _value, _bgcolor, _txtcolor) =>
    _cellText = _title + '\n' + _value
    table.cell(_table, _column, _row, _cellText, bgcolor = _bgcolor, text_color = _txtcolor)

// Draw table

var bgcolorgreen = color.new(color.green, 0)
var bgcolorred = color.new(color.red, 0)
var bgcolorgray = color.new(color.gray, 0)
var bgcolorblack = color.new(color.black, 100)
var bgcoloryellow = color.new(color.yellow, 40)

truncate(_number, _decimalPlaces) =>
    _factor = math.pow(10, _decimalPlaces)
    int(_number * _factor) / _factor


/// -------------- Table Start -------------------

txt_col = color.white
var table_position = dash_loc == 'Top Left' ? position.top_left : dash_loc == 'Bottom Left' ? position.bottom_left : dash_loc == 'Middle Right' ? position.middle_right : dash_loc == 'Bottom Center' ? position.bottom_center : dash_loc == 'Top Right' ? position.top_right : position.bottom_right

var table_text_size = text_size == 'Tiny' ? size.tiny : text_size == 'Small' ? size.small : text_size == 'Normal' ? size.normal : size.large

var t = table.new(table_position, 8, math.abs(max - min) + 2, frame_color = txt_col, frame_width = 0, border_color = txt_col, border_width = 0)


table.cell(t, 0, 0, '⚠️ Volalility', text_color = color.white, bgcolor = bgcolorblack, text_size = table_text_size)

table.cell(t, 0, 1, '📈 Trend', text_color = color.white, bgcolor = bgcolorblack, text_size = table_text_size)

table.cell(t, 0, 2, '💹 Direction', text_color = color.white, bgcolor = bgcolorblack, text_size = table_text_size)

table.cell(t, 0, 3, '🏁 Strength', text_color = color.white, bgcolor = bgcolorblack, text_size = table_text_size)

table.cell(t, 1, 0, lowvol ? 'Low' : medvol ? 'Medium ' : highvol ? 'High ' : vhighvol ? 'Very High' : extremevol ? 'Extreme' : '-', bgcolor = bgcolorblack, text_color = lowvol ? color.red : medvol ? color.green : highvol ? color.green : color.red, text_size = table_text_size)

table.cell(t, 1, 1, uptrend ? 'Up-Trend' : downtrend ? 'Down-Trend' : sideway or sideway1 ? 'Sideway ' : '-', bgcolor = bgcolorblack, text_color = uptrend ? greenc : downtrend ? redc : sideway or sideway1 ? yellowc : color.yellow, text_size = table_text_size)

table.cell(t, 1, 2, Bullish ? 'Bullish' : 'Bearish', bgcolor = bgcolorblack, text_color = Bullish ? color.green : color.red, text_size = table_text_size)

table.cell(t, 1, 3, overbought ? 'Overbought' : oversold ? 'Oversold' : 'Normal', bgcolor = bgcolorblack, text_color = overbought ? redc : oversold ? greenc : color.white, text_size = table_text_size)


// Signal Strategy

longcondition = ta.crossover(rsi, rsiMA) and hist > hist[1] and upTrend1 and ADX > 20
shortcondition = ta.crossover(rsiMA, rsi) and hist[1] > hist and downTrend1 and ADX > 20

if longcondition
    a = label.new(bar_index, low, yloc = yloc.belowbar, text = 'Go long\n' + 'SL : ' + str.tostring(chigh, '#.#') + '\n', textcolor = color.green, style = label.style_label_up, color = color.new(color.green, 100), size = size.normal)
    a

plotshape(longcondition, title = 'B', text = 'B', style = shape.labelup, location = location.belowbar, color = color.new(color.green, 0), textcolor = color.new(color.white, 0), size = size.tiny)

if shortcondition
    a = label.new(bar_index, high, yloc = yloc.abovebar, text = 'Go Short\n' + 'SL : ' + str.tostring(clow, '#.#') + '\n', textcolor = color.red, style = label.style_label_up, color = color.new(color.red, 100), size = size.normal)
    a

plotshape(shortcondition, title = 'S', text = 'S', style = shape.labeldown, location = location.abovebar, color = color.new(color.red, 0), textcolor = color.new(color.white, 0), size = size.tiny)
