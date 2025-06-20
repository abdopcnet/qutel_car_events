// Copyright (c) 2025, Qutel and contributors
// License: MIT

/*
 * Enhanced custom script for Opportunity in Qutel Car Events system
 * 
 * Uses the same ERPNext core logic with improvements:
 * - Implements Stock Settings.allow_uom_with_conversion_rate_defined_in_item logic
 * - Uses standard get_item_uom_query from queries.py
 * - Calculates conversion_factor using get_conversion_factor from get_item_details.py
 * - Uses custom fields custom_stock_qty and custom_stock_uom_rate
 * - Unified UOM logic without conflicts or duplication
 * 
 * Features:
 * - People quantity calculation with maximum limit validation
 * - Event dates management and duration calculation
 * - UOM and conversion factors calculation compatible with ERPNext
 * - Robust error handling with fallback mechanisms
 */

// --- Helper calculation functions ---
function calculate_total_people_qty(frm) {
    let total = 0;
    if (frm.doc.items && frm.doc.items.length) {
        frm.doc.items.forEach(row => {
            if (row.custom__people_qty) {
                total += row.custom__people_qty;
            }
        });
    }
    frm.set_value('custom_total_people_qty_till_now', total);
    let max_people = frm.doc.custom_opportunity_people_qty || 0;
    if (total > max_people) {
        frappe.msgprint(__('Total people quantity (' + total + ') exceeds maximum allowed (' + max_people + ').'));
    }
}

function validate_dates_and_calculate(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let parent_start = frm.doc.custom_opportunity_start_date;
    let parent_end = frm.doc.expected_closing;
    
    if (row.custom_event_start_date) {
        if (parent_start && frappe.datetime.str_to_obj(row.custom_event_start_date) < frappe.datetime.str_to_obj(parent_start)) {
            frappe.msgprint(__('Error: Event start date cannot be before opportunity start date.'));
            frappe.model.set_value(cdt, cdn, 'custom_event_start_date', null);
            frappe.model.set_value(cdt, cdn, 'custom_event_duration', 0);
            return;
        }
    }
    
    if (row.custom_event_end_date) {
        if (parent_end && frappe.datetime.str_to_obj(row.custom_event_end_date) > frappe.datetime.str_to_obj(parent_end)) {
            frappe.msgprint(__('Error: Event end date cannot be after opportunity expected closing date.'));
            frappe.model.set_value(cdt, cdn, 'custom_event_end_date', null);
            frappe.model.set_value(cdt, cdn, 'custom_event_duration', 0);
            return;
        }
    }
    
    if (row.custom_event_start_date && row.custom_event_end_date) {
        let diff = frappe.datetime.get_day_diff(row.custom_event_end_date, row.custom_event_start_date);
        frappe.model.set_value(cdt, cdn, 'custom_event_duration', diff >= 0 ? diff : 0);
    } else {
        frappe.model.set_value(cdt, cdn, 'custom_event_duration', 0);
    }
}

function calculate_duration(frm) {
    let start_date = frm.doc.custom_opportunity_start_date;
    let end_date = frm.doc.expected_closing;
    if(start_date && end_date) {
        let diff = frappe.datetime.get_day_diff(end_date, start_date);
        frm.set_value('custom_opportunity_duration', diff >= 0 ? diff + 1 : 0);
    } else {
        frm.set_value('custom_opportunity_duration', 0);
    }
}

// --- Central function for calculating conversion factors and quantities (enhanced and ERPNext-compatible) ---
async function fetch_and_set_uoms(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row || !row.item_code) return;
    
    try {
        // Use helper API first
        let res = await frappe.call({
            method: "qutel_car_events.api.uom_helper.get_item_uoms_and_conversion",
            args: {
                item_code: row.item_code,
                uom: row.uom || null
            }
        });
        
        if (res && res.message && res.message.success) {
            let data = res.message;
            
            // Set conversion factor
            if (data.conversion_factor) {
                frappe.model.set_value(cdt, cdn, "conversion_factor", data.conversion_factor);
            }
            
            // Set stock_uom for reference if not defined
            if (data.stock_uom) {
                frappe.model.set_value(cdt, cdn, "stock_uom", data.stock_uom);
            }
            
            // Recalculate quantities
            calculate_amounts_and_quantities(frm, cdt, cdn);
            
        } else {
            // Fallback to ERPNext standard method
            await fetch_conversion_factor_fallback(frm, cdt, cdn);
        }
        
    } catch (error) {
        console.error("Error in fetch_and_set_uoms:", error);
        // Fallback to standard method
        await fetch_conversion_factor_fallback(frm, cdt, cdn);
    }
}

// Fallback function using ERPNext standard logic
async function fetch_conversion_factor_fallback(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row || !row.item_code) return;
    
    try {
        let res = await frappe.call({
            method: "erpnext.stock.get_item_details.get_conversion_factor",
            args: {
                item_code: row.item_code,
                uom: row.uom || row.stock_uom
            }
        });
        
        if (res && res.message && res.message.conversion_factor) {
            frappe.model.set_value(cdt, cdn, "conversion_factor", res.message.conversion_factor);
            calculate_amounts_and_quantities(frm, cdt, cdn);
        } else {
            // Set default value
            frappe.model.set_value(cdt, cdn, "conversion_factor", 1.0);
            calculate_amounts_and_quantities(frm, cdt, cdn);
        }
        
    } catch (fallback_error) {
        console.error("Fallback also failed:", fallback_error);
        frappe.model.set_value(cdt, cdn, "conversion_factor", 1.0);
        calculate_amounts_and_quantities(frm, cdt, cdn);
    }
}

// Unified function for calculating all amounts and quantities
function calculate_amounts_and_quantities(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row) return;
    
    let qty = flt(row.qty) || 0;
    let rate = flt(row.rate) || 0;
    let conversion_factor = flt(row.conversion_factor) || 1;
    
    // Calculate stock_qty using conversion factor (ERPNext standard logic)
    let stock_qty = qty * conversion_factor;
    
    // Determine precision safely
    let stock_qty_precision = 3;
    let currency_precision = 2;
    
    try {
        if (window.precision && typeof window.precision === 'function') {
            stock_qty_precision = window.precision("stock_qty", row) || 3;
            currency_precision = window.precision("rate", row) || 2;
        }
    } catch (e) {
        // Use default values
        stock_qty_precision = 3;
        currency_precision = 2;
    }
    
    // Set stock_qty in standard field (if available)
    if (row.hasOwnProperty('stock_qty')) {
        frappe.model.set_value(cdt, cdn, "stock_qty", flt(stock_qty, stock_qty_precision));
    }
    
    // Set custom_stock_qty for custom field
    frappe.model.set_value(cdt, cdn, "custom_stock_qty", flt(stock_qty, stock_qty_precision));
    
    // Calculate custom_stock_uom_rate
    let stock_uom_rate = conversion_factor > 0 ? (rate / conversion_factor) : 0;
    frappe.model.set_value(cdt, cdn, "custom_stock_uom_rate", flt(stock_uom_rate, currency_precision));
    
    // Calculate amount using stock_qty (correct ERPNext logic)
    let amount = stock_qty * rate;
    frappe.model.set_value(cdt, cdn, "amount", flt(amount, currency_precision));
    
    // Calculate base amounts (base currency)
    let conversion_rate = flt(frm.doc.conversion_rate) || 1;
    frappe.model.set_value(cdt, cdn, "base_rate", flt(conversion_rate * rate, currency_precision));
    frappe.model.set_value(cdt, cdn, "base_amount", flt(conversion_rate * amount, currency_precision));
    
    // Update total people
    calculate_total_people_qty(frm);
    
    // Update overall totals for opportunity
    frm.trigger("calculate_totals");
}

// --- Custom form modifications ---
frappe.ui.form.on('Opportunity', {
    // --- Calculate opportunity duration ---
    custom_opportunity_start_date: function(frm) {
        calculate_duration(frm);
    },
    expected_closing: function(frm) {
        calculate_duration(frm);
    },
    
    onload: function(frm) {
        // Setup UOM query using ERPNext standard
        setup_uom_query(frm);
    }
});

// Function to setup get_query for UOM field (using ERPNext standard)
function setup_uom_query(frm) {
    if (frm.fields_dict.items && frm.fields_dict.items.grid) {
        let uom_field = frm.fields_dict.items.grid.get_field('uom');
        if (uom_field) {
            uom_field.get_query = function(doc, cdt, cdn) {
                let row = locals[cdt][cdn];
                if (!row || !row.item_code) {
                    return { filters: { name: ['in', []] } };
                }
                
                // Use same ERPNext logic from queries.py
                return {
                    query: "erpnext.controllers.queries.get_item_uom_query",
                    filters: {
                        "item_code": row.item_code
                    }
                };
            };
        }
    }
}

frappe.ui.form.on('Opportunity Item', {
    // --- People quantity aggregation and limit validation ---
    custom__people_qty: function(frm, cdt, cdn) {
        calculate_total_people_qty(frm);
    },
    
    items_remove: function(frm) {
        calculate_total_people_qty(frm);
    },
    
    // --- Event dates validation and duration calculation ---
    custom_event_start_date: function(frm, cdt, cdn) {
        validate_dates_and_calculate(frm, cdt, cdn);
    },
    
    custom_event_end_date: function(frm, cdt, cdn) {
        validate_dates_and_calculate(frm, cdt, cdn);
    },
    
    // --- Unified UOM and calculations logic ---
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row && row.item_code) {
            // Fetch UOM and conversion factors
            fetch_and_set_uoms(frm, cdt, cdn);
        }
    },
    
    uom: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row && row.item_code && row.uom) {
            // Fetch conversion factor for new UOM
            fetch_and_set_uoms(frm, cdt, cdn);
        }
    },
    
    qty: function(frm, cdt, cdn) {
        calculate_amounts_and_quantities(frm, cdt, cdn);
    },
    
    rate: function(frm, cdt, cdn) {
        calculate_amounts_and_quantities(frm, cdt, cdn);
    },
    
    conversion_factor: function(frm, cdt, cdn) {
        calculate_amounts_and_quantities(frm, cdt, cdn);
    }
});

