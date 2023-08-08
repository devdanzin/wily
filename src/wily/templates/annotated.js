disp = false;
first_toggle = true;
function toggle() {
    cy = document.getElementsByClassName("cyclomatic");
    for (let c in cy) {
        if (cy[c].style) {
            cy[c].style.display = (disp ? "block" : "none");
        }
    }
    cy = document.getElementsByClassName("cyclomatic_span");
    for (let c in cy) {
        if (cy[c].style) {
            cy[c].style.display = (disp ? "inline" : "none");
        }
    }
    ha = document.getElementsByClassName("halstead");
    for (let h in ha) {
        if (ha[h].style)
            ha[h].style.display = disp ? "none" : "inline";
    }
    ha = document.getElementsByClassName("halstead_span");
    for (let h in ha) {
        if (ha[h].style)
            ha[h].style.display = disp ? "none" : "inline";
    }
    disp = !disp;
    if (first_toggle) {
        select_metric("h1", true);
        first_toggle = false;
    }
    if (!disp) {
        select_metric("cc_function", false);
    }
    else {
        select_metric("effort", true);
    }
}
halstead_names = ["cc_function", "h1", "h2", "N1", "N2", "vocabulary", "length", "volume", "effort", "difficulty"]

function select_metric(name, show_all) {
    for (let hname in halstead_names) {
        ha = document.getElementsByClassName(halstead_names[hname] + "_val");
        for (let h in ha) {
            if (ha[h].style && halstead_names[hname] != "cc_function")
                ha[h].style.display = show_all ? "inline" : "none";
        }
        hn = document.getElementsByClassName(name + "_val");
        for (let h in hn) {
            if (hn[h].style)
                hn[h].style.display = "inline";
        }
    }
    all_divs = document.querySelectorAll("div");
    var all_classes = [];
    for (let di in all_divs) {
        if (all_divs[di].className) {
            div_classes = all_divs[di].className.split(' ');
            all_classes.push(...div_classes);
        }
    }
    unique_classes = [...new Set(all_classes)]
    unique_metric_classes = unique_classes.filter((element) => element.startsWith(name))
    for (let ci in unique_metric_classes) {
        color_class = unique_metric_classes[ci];
        ha_code = document.getElementsByClassName(color_class);
        for (let hi in ha_code) {
            if (ha_code[hi].style) {
                var val_style_name = color_class.replace("_code", "");
                var val_style_class = document.querySelector("." + val_style_name);
                if (val_style_class) {
                    var val_style = getComputedStyle(val_style_class);
                    ha_code[hi].style.backgroundColor = val_style.backgroundColor;
                }
            }
        }
    }
    all_buttons = document.querySelectorAll("button");
    for (let bi in all_buttons) {
        let btn = all_buttons[bi];
        if (btn.id == name) {
            if (btn.style) {
                btn.style.borderStyle = 'inset';
                btn.style.backgroundColor = "darkgray";
            }
        }
        else {
            if (btn.style){
                btn.style.borderStyle = 'outset';
                btn.style.backgroundColor = "";
            }
        }
    }
}
