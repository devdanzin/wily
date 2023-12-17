"use strict";

let disp = "cyclomatic";
let first_toggle = true;
let last_shown_halstead = "effort";
let last_shown_raw = "loc";

/**
 * Toggles visibility of metric spans and buttons, displaying last shown metric.
 */
function toggle() {
    // Set cycling order: cyclomatic -> halstead -> raw -> cyclomatic
    if ("cyclomatic" === disp) {
        disp = "halstead";
    } else if ("halstead" === disp) {
        disp = "raw";
    } else if ("raw" === disp) {
        disp = "cyclomatic";
    }

    // Toggle element visibility
    toggle_elements("raw", false);
    toggle_elements("raw_span", false);
    toggle_elements("cyclomatic", true);
    toggle_elements("cyclomatic_span", false);
    toggle_elements("halstead", false);
    toggle_elements("halstead_span", false);

    // Pick a Halstead metric the first time we toggle to them
    if (first_toggle) {
        select_metric("h1", true);
        first_toggle = false;
    }

    // Pick either the CC metric or the last Halstead metric shown
    if ("cyclomatic" === disp) {
        select_metric("cc_function", false);
    } else if ("halstead" === disp) {
        select_metric(last_shown_halstead, false);
    } else if ("raw" === disp) {
        select_metric(last_shown_raw, false);
    }
}

/**
 * Toggles visibility of elements matching classname, allowing to choose block or inline.
 * @param {string} classname
 * @param {boolean} block
 */
function toggle_elements(classname, block) {
    let style = "inline";
    if (block === true) {
        style = "block";
    }
    let display_name = classname.split("_")[0];
    let spans = document.getElementsByClassName(classname);
    for (let si in spans) {
        if (spans[si].style)
            {
              spans[si].style.display =
                display_name === disp ? style : "none";
            }
    }
}

/**
 * Applies background colors from span classes to corresponding div classes.
 * @param {string[]} all_classes
 * @param {string} name
 */
function metric_style_to_code_style(all_classes, name) {
    let unique_classes = [...new Set(all_classes)];
    let unique_metric_classes = unique_classes.filter((element) =>
        element.startsWith(name),
    );
    for (let ci in unique_metric_classes) {
        let color_class = unique_metric_classes[ci];
        let code_divs = document.getElementsByClassName(color_class);
        for (let hi in code_divs) {
            let code_div = code_divs[hi];
            if (code_div.style) {
                let metric_span_class_name = color_class.replace("_code", "");
                let metric_span_class = document.querySelector(
                    "." + metric_span_class_name,
                );
                if (metric_span_class) {
                    let metric_span_style = getComputedStyle(metric_span_class);
                    code_div.style.backgroundColor =
                        metric_span_style.backgroundColor;
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
        if (halstead_names.includes(name)) {
            name = last_shown_halstead;
        } else if (raw_names.includes(name)) {
            name = last_shown_raw;
        }
    }
    // Update last shown metric
    if (halstead_names.includes(name)) {
        last_shown_halstead = name;
    } else if (raw_names.includes(name)) {
        last_shown_raw = name;
    }
    display_or_hide_metrics(name, show_all);
    let all_classes = get_div_classes();
    metric_style_to_code_style(all_classes, name);
    update_buttons(name);
}

let cc_names = ["cc_function"];

let halstead_names = [
    "h1",
    "h2",
    "N1",
    "N2",
    "vocabulary",
    "length",
    "volume",
    "effort",
    "difficulty",
];

let raw_names = [
    "loc",
    "lloc",
    "sloc",
    "comments",
    "multi",
    "blank",
    "single_comments",
];

let metric_names = cc_names.concat(halstead_names, raw_names);

/**
 * Displays or hides metric spans.
 * @param {boolean} show_all
 * @param {string} name
 */
function display_or_hide_metrics(name, show_all) {
    for (let mni in metric_names) {
        let spans_to_display_or_hide = document.getElementsByClassName(
            metric_names[mni] + "_val",
        );
        for (let si in spans_to_display_or_hide) {
            if (
                spans_to_display_or_hide[si].style &&
                "halstead" === disp &&
                halstead_names.includes(metric_names[mni])
            ) {
                spans_to_display_or_hide[si].style.display = show_all
                    ? "inline"
                    : "none";
            } else if (
                spans_to_display_or_hide[si].style &&
                "raw" === disp &&
                raw_names.includes(metric_names[mni])
            ) {
                spans_to_display_or_hide[si].style.display = show_all
                    ? "inline"
                    : "none";
            }
        }
    }
    let spans_to_display = document.getElementsByClassName(name + "_val");
    for (let si in spans_to_display) {
        if (spans_to_display[si].style)
            {
              spans_to_display[si].style.display = "inline";
            }
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
            let div_classes = all_divs[di].className.split(" ");
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
                btn.style.borderStyle = "inset";
                btn.style.backgroundColor = "darkgray";
            }
        } else {
            if (btn.style) {
                btn.style.borderStyle = "outset";
                btn.style.backgroundColor = "";
            }
        }
    }
}
