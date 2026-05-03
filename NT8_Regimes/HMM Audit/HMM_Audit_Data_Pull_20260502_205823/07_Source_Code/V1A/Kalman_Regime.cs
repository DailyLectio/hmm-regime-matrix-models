//@version=6
indicator('Kalman Regime', overlay = true, max_bars_back = 500)

// ═══════════════════════════════════════════════════════════════════════════
// INPUTS
// ═══════════════════════════════════════════════════════════════════════════

i_src = input.source(close, 'Price Source', group = 'Kernel ATR Calculation')
i_kernelLen = input.int(33, 'Kernel Length', minval = 5, maxval = 200, group = 'Kernel ATR Calculation', tooltip = 'The horizon the kernel listens to. Longer = steadier, fewer flips')
i_kernelAlpha = input.float(1.0, 'Kernel Alpha', minval = 0.1, maxval = 100, step = 0.1, group = 'Kernel ATR Calculation', tooltip = 'How strongly the kernel prioritizes fresh data. Higher = quicker response')

i_atrPeriod = input.int(14, 'ATR Period', minval = 5, maxval = 50, group = 'Kernel ATR Calculation', tooltip = 'Volatility memory. Shorter = faster reaction')
i_atrFactor = input.float(2.0, 'ATR Factor', minval = 0.5, maxval = 5.0, step = 0.1, group = 'Kernel ATR Calculation', tooltip = 'Envelope strictness. Larger = more tolerance, fewer flips')

i_innerMult = input.float(1.5, 'Inner Band Multiplier', minval = 0.5, step = 0.1, group = 'Band Settings')

i_showInner = input.bool(true, 'Show Inner Bands', inline = 'bands', group = 'Display')
i_paintCandles = input.bool(true, 'Paint Candles According to Trend', group = 'Display')

c_long = input.color(#00ff88, 'Long Color', inline = 'colors', group = 'Display')
c_short = input.color(#ff4444, 'Short Color', inline = 'colors', group = 'Display')
c_inner = input.color(#00BCD4, 'Inner Bands', inline = 'bands_colors', group = 'Display')

// ═══════════════════════════════════════════════════════════════════════════
// KERNEL FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

f_gaussianKernel(series float src, int len, float alpha) =>
    float sum = 0.0
    float weightSum = 0.0
    float center = len / 2.0
    for i = 0 to len - 1 by 1
        float x = float(i)
        float price = src[len - 1 - i]
        float dist = math.abs(x - center)
        float recencyWeight = math.exp(-alpha * (len - 1 - i) / len)
        float localWeight = math.exp(-math.pow(dist / (len / 3), 2))
        float weight = recencyWeight * localWeight
        sum := sum + price * weight
        weightSum := weightSum + weight
        weightSum
    weightSum > 0 ? sum / weightSum : src

// ═══════════════════════════════════════════════════════════════════════════
// ADAPTIVE KALMAN FILTER
// ═══════════════════════════════════════════════════════════════════════════

f_adaptiveKalman(float measurement, float prevState, float prevVariance, float atrVol) =>
    float measurementNoise = atrVol * 0.1
    float processNoise = atrVol * 0.05
    float predictedState = prevState
    float predictedVar = prevVariance + processNoise
    float innovation = measurement - predictedState
    float innovationVar = predictedVar + measurementNoise
    float kalmanGain = predictedVar / innovationVar
    float newState = predictedState + kalmanGain * innovation
    float newVar = (1 - kalmanGain) * predictedVar
    [newState, newVar]

// ═══════════════════════════════════════════════════════════════════════════
// CALCULATION
// ═══════════════════════════════════════════════════════════════════════════

var float kalmanState = na
var float kalmanVar = 1.0

if na(kalmanState)
    kalmanState := i_src
    kalmanVar := 1.0
    kalmanVar

float atr = ta.atr(i_atrPeriod)
float kernelSmoothed = f_gaussianKernel(i_src, i_kernelLen, i_kernelAlpha)

[newState, newVar] = f_adaptiveKalman(kernelSmoothed, kalmanState, kalmanVar, atr)
kalmanState := newState
kalmanVar := newVar

float baseline = kalmanState

float upperEnvelope = baseline + atr * i_atrFactor
float lowerEnvelope = baseline - atr * i_atrFactor

float innerUpper = baseline + atr * i_innerMult
float innerLower = baseline - atr * i_innerMult

// ═══════════════════════════════════════════════════════════════════════════
// REGIME DETECTION
// ═══════════════════════════════════════════════════════════════════════════

var int trendState = 0

bool priceAboveUpper = close > upperEnvelope
bool priceBelowLower = close < lowerEnvelope

float baselineSlope = baseline - baseline[1]

if priceAboveUpper and baselineSlope > 0
    trendState := 1
    trendState
else if priceBelowLower and baselineSlope < 0
    trendState := -1
    trendState
else if close > baseline and trendState != 1 and baselineSlope > atr * 0.1
    trendState := 1
    trendState
else if close < baseline and trendState != -1 and baselineSlope < -atr * 0.1
    trendState := -1
    trendState

color baselineColor = trendState == 1 ? c_long : trendState == -1 ? c_short : color.gray

// ═══════════════════════════════════════════════════════════════════════════
// PLOTTING
// ═══════════════════════════════════════════════════════════════════════════

plot(baseline, 'Baseline', baselineColor, 1, plot.style_line)

pInnerU = plot(i_showInner ? innerUpper : na, 'Inner Upper', color.new(c_inner, 50), 1)
pInnerL = plot(i_showInner ? innerLower : na, 'Inner Lower', color.new(c_inner, 50), 1)

fill(pInnerU, pInnerL, color.new(c_inner, 92), 'Inner Zone')

barcolor(i_paintCandles ? trendState == 1 ? color.new(c_long, 50) : trendState == -1 ? color.new(c_short, 50) : na : na)

// ═══════════════════════════════════════════════════════════════════════════
// ALERTS
// ═══════════════════════════════════════════════════════════════════════════

bool trendUp = trendState == 1 and trendState[1] != 1
bool trendDown = trendState == -1 and trendState[1] != -1

alertcondition(trendUp, 'Trend Up', 'Bullish regime detected')
alertcondition(trendDown, 'Trend Down', 'Bearish regime detected')

plotshape(trendUp, 'Trend Up', shape.triangleup, location.belowbar, color.new(c_long, 0), size = size.tiny)
plotshape(trendDown, 'Trend Down', shape.triangledown, location.abovebar, color.new(c_short, 0), size = size.tiny)
