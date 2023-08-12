let disp = false;
let first_toggle = true;
let last_shown_halstead = "effort";

/**
 * Toggles visibility of metric spans and buttons, displaying last shown metric.
 */
function toggle() {
    let cy_divs = document.getElementsByClassName("cyclomatic");
    for (let ci in cy_divs) {
        if (cy_divs[ci].style) {
            cy_divs[ci].style.display = (disp ? "block" : "none");
        }
    }
    let cy_spans = document.getElementsByClassName("cyclomatic_span");
    for (let ci in cy_spans) {
        if (cy_spans[ci].style) {
            cy_spans[ci].style.display = (disp ? "inline" : "none");
        }
    }
    let ha_divs = document.getElementsByClassName("halstead");
    for (let hi in ha_divs) {
        if (ha_divs[hi].style)
            ha_divs[hi].style.display = disp ? "none" : "inline";
    }
    let ha_spans = document.getElementsByClassName("halstead_span");
    for (let hi in ha_spans) {
        if (ha_spans[hi].style)
            ha_spans[hi].style.display = disp ? "none" : "inline";
    }
    disp = !disp;

    // Pick a Halstead metric the first time we toggle to them
    if (first_toggle) {
        select_metric("h1", true);
        first_toggle = false;
    }

    // Pick either the CC metric or the last Halstead metric shown
    if (!disp) {
        select_metric("cc_function", false);
    } else {
        select_metric(last_shown_halstead, false);
    }
}


/**
 * Applies background colors from span classes to corresponding div classes.
 * @param {string[]} all_classes
 * @param {string} name
 */
function metric_style_to_code_style(all_classes, name) {
    let unique_classes = [...new Set(all_classes)]
    let unique_metric_classes = unique_classes.filter((element) => element.startsWith(name))
    for (let ci in unique_metric_classes) {
        let color_class = unique_metric_classes[ci];
        let ha_code = document.getElementsByClassName(color_class);
        for (let hi in ha_code) {
            if (ha_code[hi].style) {
                let val_style_name = color_class.replace("_code", "");
                let val_style_class = document.querySelector("." + val_style_name);
                if (val_style_class) {
                    let val_style = getComputedStyle(val_style_class);
                    ha_code[hi].style.backgroundColor = val_style.backgroundColor;
                }
            }
        }
    }
}


/**
 * Selects a metric to display, hiding others.
 * @param {string} name
 * @param {boolean} show_all
 */
function select_metric(name, show_all) {
    // When displaying all Halstead metrics, use the last shown one to color code.
    if (show_all) {
        name = last_shown_halstead;
    }
    // Update last shown Halstead metric
    if (name !== "cc_function") {
        last_shown_halstead = name;
    }
    display_or_hide_metrics(name, show_all);
    let all_classes = get_div_classes();
    metric_style_to_code_style(all_classes, name);
    update_buttons(name);
}


metric_names = ["cc_function", "h1", "h2", "N1", "N2", "vocabulary", "length", "volume", "effort", "difficulty"]
/**
 * Displays or hides metric spans.
 * @param {boolean} show_all
 * @param {string} name
 */
function display_or_hide_metrics(name, show_all) {
    for (let mni in metric_names) {
        let spans_to_display_or_hide = document.getElementsByClassName(metric_names[mni] + "_val");
        for (let si in spans_to_display_or_hide) {
            if (spans_to_display_or_hide[si].style && metric_names[mni] !== "cc_function")
                spans_to_display_or_hide[si].style.display = show_all ? "inline" : "none";
        }
    }
    let spans_to_display = document.getElementsByClassName(name + "_val");
    for (let si in spans_to_display) {
        if (spans_to_display[si].style)
            spans_to_display[si].style.display = "inline";
    }
}


/**
 * Gets CSS classes from all divs
 * @returns {string[]}
 */
function get_div_classes() {
    let all_divs = document.querySelectorAll("div");
    let all_classes = [];
    for (let di in all_divs) {
        if (all_divs[di].className) {
            let div_classes = all_divs[di].className.split(' ');
            all_classes.push(...div_classes);
        }
    }
    return all_classes;
}


/**
 * Updates buttons, making selected metric button look pressed.
 * @param {string} name
 */
function update_buttons(name) {
    let all_buttons = document.querySelectorAll("button");
    for (let bi in all_buttons) {
        let btn = all_buttons[bi];
        if (btn.id === name) {
            if (btn.style) {
                btn.style.borderStyle = 'inset';
                btn.style.backgroundColor = "darkgray";
            }
        } else {
            if (btn.style) {
                btn.style.borderStyle = 'outset';
                btn.style.backgroundColor = "";
            }
        }
    }
}
