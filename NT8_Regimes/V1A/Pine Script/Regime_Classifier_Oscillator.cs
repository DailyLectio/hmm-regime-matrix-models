// This work is licensed under a Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/
// © aibitcointrend

//@version=6
indicator("Regime Classifier Oscillator (AiBitcoinTrend)")

filter_window_size = input.int(150, "Filter Window Size", tooltip = "Price regime filter lookback", step = 1, minval = 1, group = "Price regime filter")
atr_lookback = input.int(20, "ATR Lookback Size", tooltip = "Price regime ATR calculation lookback (acts as regime threshold)", step = 1, minval = 1, group = "Price regime filter")
window_size = input.int(150, "Window Size", tooltip = "Lookback period of the cluster, volatility classification model", step = 1, minval = 50, group = "Cluster model settings")
refit_interval = input.int(100, "Refit Interval", tooltip = "Controls the refit interval of the model, refitting the model every N bars", step = 1, minval = 1, group = "Cluster model settings")
if filter_window_size % 2 == 0
    filter_window_size += 1

fast_osc_lookback = input.int(20, "Dynamic Cycle Oscillator Lookback", tooltip = "Lookback for the Dynamic Cycle Oscillator", step = 1, minval = 2, group = "Dynamic Cycle Oscillator (DCO)")
cycle_lookback    = input.int(10, "Cycle Lookback", tooltip = "Lookback for cycle component", step = 1, minval = 1, group = "Dynamic Cycle Oscillator (DCO)")
smoothing_factor  = input.float(0.2, "Smoothing Factor", tooltip = "Factor for exponential smoothing (0 to 1)", step = 0.1, minval = 0.1, maxval = 1, group = "Dynamic Cycle Oscillator (DCO)")

adv_col = input.color(color.green, title="", group="Colors", inline="col")
dec_col = input.color(color.red, title="", group="Colors", inline="col")
acc_col = input.color(color.blue, title="", group="Colors", inline="col")
dist_col = input.color(color.yellow, title="", group="Colors", inline="col")
trend_col_up = input.color(color.lime, title="", group="Colors", inline="trend")
trend_col_dn = input.color(color.red, title="", group="Colors", inline="trend")


// === Parameters, variabels, constants and definitions
//@enum     Defines regime types
enum regime_type
    advance = "Advance"
    decline = "Decline"
    accumulation = "Accumulation"
    distribution = "Distribution"

// Colors
var color[] regime_colors = array.new_color(4)
var string[] regime_text = array.new_string(4)
if bar_index == 0
    // Advance
    regime_colors.set(0, color.new(adv_col, 85))
    regime_text.set(0, "🟢")
    // Decline
    regime_colors.set(1, color.new(dec_col, 85))
    regime_text.set(1, "🔴")
    // Accumulation
    regime_colors.set(2, color.new(acc_col, 85))
    regime_text.set(2, "🔵")
    // Distributio
    regime_colors.set(3, color.new(dist_col, 85))
    regime_text.set(3, "🟡")

// Variables
// Regime detector
var float[] preturns = array.new<float>()
var float[] vola = array.new<float>()
var float vol = na
var float last_refit_bar = 0
var float cluster_1 = 1.0
var float cluster_2 = 0.0
var int vol_regime = 0
var int price_regime = 0
var regime_type regime = regime_type.accumulation
var float osc_r = 0.0

// Boxes
var box[] regime_boxes = array.new<box>()
var label[] regime_labels = array.new<label>()
var float regime_start_price = na
var int regime_start_index = na
var box live_box = na
var label live_label = na

// Compute ATR threshold
atr = ta.atr(atr_lookback)

// === Filter helper functions and related ===
md_filter(src, length) =>
    var float[] window = array.new_float(length, na)
    for i = 0 to length - 1
        window.set(i, nz(src[i], na))
    window.sort(order.ascending)
    window.get(length / 2)

sg_filtered = md_filter(close, filter_window_size)

// === Regime detector functions ===
f_cluster(data_window) =>
    // Initialize cluster centers
    center1 = data_window.percentile_linear_interpolation(0.25)
    center2 = data_window.percentile_linear_interpolation(0.75)

    count1 = 0
    count2 = 0
    sum1 = 0.0
    sum2 = 0.0

    for i = 0 to window_size - 1
        el = data_window.get(i)
        dist1 = math.abs(el - center1)
        dist2 = math.abs(el - center2)
        if dist1 < dist2
            sum1 := sum1 + el
            count1 := count1 + 1
        else
            sum2 := sum2 + el
            count2 := count2 + 1

    new_center1 = count1 > 0 ? sum1 / count1 : center1
    new_center2 = count2 > 0 ? sum2 / count2 : center2
    [new_center1, new_center2]

// Calculate slope's R-value (oscillator component)
f_calc_slope_r(src, length) =>
    avg_x = (length - 1) / 2
    avg_y = math.sum(src, length) / length //array.sum(src) / length
    num = 0.0
    den_x = 0.0
    den_y = 0.0
    for i = 0 to length - 1
        x = i - avg_x
        y = src[i] - avg_y
        num := num + x * y
        den_x := den_x + math.pow(x, 2)
        den_y := den_y + math.pow(y, 2)
    r_value = -num / math.sqrt(den_x * den_y)  // Corrected sign for proper slope direction
    r_value

osc_r := f_calc_slope_r(sg_filtered, filter_window_size)

// Calculate Dynamic Cycle Oscillator (DCO)
calc_DCO_osc(src, length, cycle_length, smoothing) =>
    max_val = ta.highest(src, length)
    min_val = ta.lowest(src, length)
    normalized = (src - min_val) / (max_val - min_val) * 2.4 - 1.2
    cycle_component = math.sin(2 * math.pi * bar_index / cycle_length)
    std_dev = ta.stdev(src, length)
    weighted_osc = normalized * (1 + 0.5 * cycle_component + 0.3 * std_dev / (max_val - min_val))
    smoothed_osc = 0.0
    smoothed_osc := na(smoothed_osc[1]) ? weighted_osc : smoothed_osc[1] * (1 - smoothing) + weighted_osc * smoothing
    math.min(1.2, math.max(-1.2, smoothed_osc))

fast_osc = calc_DCO_osc(close, fast_osc_lookback, cycle_lookback, smoothing_factor)

// === Regime classification ===
if barstate.isconfirmed and bar_index > 10
    if preturns.size() >= window_size
        preturns.shift()

    preturns.push(close/close[1]-1)

    if vola.size() >= window_size
        vola.shift()

    if preturns.size() >= window_size
        vola.push(preturns.stdev())

    if vola.size() >= window_size and bar_index - last_refit_bar >= refit_interval
        [cluster_1_tmp, cluster_2_tmp] = f_cluster(vola)
        cluster_1 := cluster_1_tmp
        cluster_2 := cluster_2_tmp
        last_refit_bar := bar_index
        
    if vola.size() >= window_size
        vol := vola.get(vola.size()-1)
        vol_regime := math.abs(vol - cluster_1) < math.abs(vol - cluster_2) ? 0 : 1
    
    if price_regime == 0 and close <= sg_filtered - atr
        price_regime := 1
    else if price_regime == 1 and close >= sg_filtered + atr
        price_regime := 0

    if vol_regime == 0 and price_regime == 0
        regime := regime_type.advance
    else if vol_regime == 1 and price_regime == 0
        regime := regime_type.accumulation
    else if vol_regime == 0 and price_regime == 1
        regime := regime_type.distribution
    else
        regime := regime_type.decline

// === UI and plotting ===
cur_regime_bgcolor = switch(regime)
    regime_type.advance => regime_colors.get(0)
    regime_type.decline => regime_colors.get(1)
    regime_type.accumulation => regime_colors.get(2)
    regime_type.distribution => regime_colors.get(3)

cur_regime_label = switch regime
    regime_type.advance => regime_text.get(0)
    regime_type.decline => regime_text.get(1)
    regime_type.accumulation => regime_text.get(2)
    regime_type.distribution => regime_text.get(3)

if not na(regime) and bar_index > 10 and regime != regime[1]
    if not na(live_box)
        live_box.set_right(bar_index[1])
        regime_boxes.push(live_box)

        // Finalize the label
        if not na(live_label)
            live_label.set_x(bar_index[1] - ((bar_index[1] - regime_start_index) / 2)) 
            regime_labels.push(live_label)

    regime_start_price := low
    regime_start_index := bar_index[1]

    live_box := box.new(left=regime_start_index, bottom=regime_start_price, right=na, top=high, xloc=xloc.bar_index, border_width=1, border_color=color.new(color.gray, 50), bgcolor = cur_regime_bgcolor, force_overlay = true)
    // Create a label for the current regime
    live_label := label.new(x=regime_start_index, y=high + (high - low) * 0.1, text=cur_regime_label, xloc=xloc.bar_index, style=label.style_none, color=color.new(color.white, 0), textcolor=color.new(color.white, 0),  size=size.small, force_overlay=true)

if not na(live_box)
    live_box.set_right(bar_index)
    live_box.set_top(math.max(high, live_box.get_top()))
    live_box.set_bottom(math.min(low, live_box.get_bottom()))

if not na(live_label)
    live_label.set_x(regime_start_index + (bar_index - regime_start_index) / 2) 
    live_label.set_y((live_box.get_top() + live_box.get_bottom()) / 2) 

// Clean up old boxes to optimize performance
if regime_boxes.size() > 200
    box.delete(regime_boxes.shift())

if regime_labels.size() > 200
    label.delete(regime_labels.shift())

// Plot tables
if barstate.islast
    var table regime_table = table.new(position.top_right, 1, 1, border_width=1, border_color=color.gray, bgcolor=color.new(color.black, 90))
    table.cell(regime_table, 0, 0, str.tostring(regime), text_size=size.normal, bgcolor = color.black, text_color = color.white)

    var table legend = table.new(position.top_right, 4, 2, border_color=color.gray, border_width=1, force_overlay = true)
    table.cell(legend, 0, 0, regime_text.get(0), bgcolor=regime_colors.get(0), text_color=color.white, text_size=size.normal)
    table.cell(legend, 0, 1, "Advance", text_color=color.white, bgcolor = color.new(color.gray, 0))
    table.cell(legend, 1, 0, regime_text.get(1), bgcolor=regime_colors.get(1), text_color=color.white, text_size=size.normal)
    table.cell(legend, 1, 1, "Decline", text_color=color.white, bgcolor = color.new(color.gray, 0))
    table.cell(legend, 2, 0, regime_text.get(2), bgcolor=regime_colors.get(2), text_color=color.white, text_size=size.normal)
    table.cell(legend, 2, 1, "Accumulation", text_color=color.white, bgcolor = color.new(color.gray, 0))
    table.cell(legend, 3, 0, regime_text.get(3), bgcolor=regime_colors.get(3), text_color=color.white, text_size=size.normal)
    table.cell(legend, 3, 1, "Distribution", text_color=color.white, bgcolor = color.new(color.gray, 0))

// PLot oscillator
zero_line = plot(-1.2, title="-1.2", color=color.white, display = display.none)
top_line = plot(1.2,title="1.2", color=color.white,display = display.none)
mid_line = plot(0.0, title="0",color=color.white,display = display.none)

fill(top_line, zero_line, 1.2, -1.2, color.new(cur_regime_bgcolor, 50), na)
fill(mid_line, zero_line, 0.0, -1.2, color.new(cur_regime_bgcolor, 50), na)
plot(osc_r,title="Regime Classifier (Histogram)", style=plot.style_histogram, linewidth = 1, color=color.new(cur_regime_bgcolor, 0))
plot(osc_r,title="Regime Classifier (Line)", linewidth = 1, color=color.new(cur_regime_bgcolor, 0))

if not na(regime) and bar_index > 10 and regime != regime[1]
    line.new(bar_index-1, 0.0, bar_index-1, 1.2, color = color.new(cur_regime_bgcolor, 50), style=line.style_dashed)

// Fast Oscillator
calc_gradient_color(value) =>
    if value > 0.8
        color.new(color.green, 0)
    else if value > 0.4
        color.new(color.lime, 0)
    else if value > 0
        color.new(color.yellow, 0)
    else if value > -0.4
        color.new(color.orange, 0)
    else if value > -0.8
        color.new(color.red, 0)
    else
        color.new(color.maroon, 0)

// PLot Dynamic Cycle Oscillator (DCO)
gradient_color = calc_gradient_color(fast_osc)
plot(fast_osc, title="Dynamic Cycle Oscillator (DCO)", color=gradient_color, linewidth=2)

// Plot Trend
trend_col = close>sg_filtered?trend_col_up:trend_col_dn
plot(sg_filtered, title="Trend Line", color=trend_col, linewidth = 2, force_overlay = true)