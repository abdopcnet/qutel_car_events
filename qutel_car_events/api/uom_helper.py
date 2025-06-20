# Copyright (c) 2025, Qutel and contributors
# License: MIT

"""
UOM Helper API for Qutel Car Events system

This module provides helper functions for fetching and managing UOM (Unit of Measure)
and conversion factors instead of relying on client-side cache, improving performance and reliability.
"""

import frappe
from frappe import _
from typing import Dict, List, Optional, Any


@frappe.whitelist()
def get_item_uoms_with_conversion(item_code: str) -> Dict[str, Any]:
    """
    Fetch all available UOMs for item with conversion factors
    
    Args:
        item_code (str): Item code
        
    Returns:
        Dict[str, Any]: Dictionary containing UOM information and conversion factors
    """
    if not item_code:
        return {"success": False, "message": _("Item Code is required")}
    
    try:
        # Fetch basic item information
        item = frappe.get_cached_doc("Item", item_code)
        if not item:
            return {"success": False, "message": _("Item not found")}
        
        # Check Stock Settings configuration
        allow_uom_conversion = frappe.db.get_single_value(
            "Stock Settings", 
            "allow_uom_with_conversion_rate_defined_in_item"
        )
        
        result = {
            "success": True,
            "item_code": item_code,
            "stock_uom": item.stock_uom,
            "uoms": [],
            "default_uom": item.stock_uom,
            "allow_uom_conversion": allow_uom_conversion or False
        }
        
        if allow_uom_conversion and item.uoms:
            # Use UOM Conversion Detail if allowed
            uom_list = []
            for uom_detail in item.uoms:
                uom_list.append({
                    "uom": uom_detail.uom,
                    "conversion_factor": uom_detail.conversion_factor,
                    "is_stock_uom": uom_detail.uom == item.stock_uom
                })
            
            # Sort by idx (order defined in item)
            result["uoms"] = sorted(uom_list, key=lambda x: x["is_stock_uom"], reverse=True)
            
        else:
            # Traditional method - fetch stock_uom only
            result["uoms"] = [{
                "uom": item.stock_uom,
                "conversion_factor": 1.0,
                "is_stock_uom": True
            }]
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Error in get_item_uoms_with_conversion: {str(e)}")
        return {
            "success": False, 
            "message": _("Error fetching UOM data: {0}").format(str(e))
        }


@frappe.whitelist()
def get_uom_conversion_factor(item_code: str, uom: str) -> Dict[str, Any]:
    """
    Fetch conversion factor for a specific unit of measure
    
    Args:
        item_code (str): Item code
        uom (str): Unit of measure
        
    Returns:
        Dict[str, Any]: Conversion factor and additional information
    """
    if not item_code or not uom:
        return {"success": False, "message": _("Item Code and UOM are required")}
    
    try:
        # Use standard ERPNext function
        from erpnext.stock.get_item_details import get_conversion_factor
        
        result = get_conversion_factor(item_code, uom)
        
        if result and "conversion_factor" in result:
            return {
                "success": True,
                "item_code": item_code,
                "uom": uom,
                "conversion_factor": result["conversion_factor"]
            }
        else:
            return {
                "success": False,
                "message": _("Conversion factor not found for {0} in {1}").format(uom, item_code)
            }
            
    except Exception as e:
        frappe.log_error(f"Error in get_uom_conversion_factor: {str(e)}")
        return {
            "success": False,
            "message": _("Error fetching conversion factor: {0}").format(str(e))
        }


@frappe.whitelist()
def get_opportunity_calculations(items_data: str) -> Dict[str, Any]:
    """
    Calculate all amounts and quantities for opportunity items - fully compatible with ERPNext logic
    
    Args:
        items_data (str): JSON string containing items data
        
    Returns:
        Dict[str, Any]: Calculated results for all items
    """
    try:
        import json
        from frappe.utils import flt
        
        items = json.loads(items_data) if isinstance(items_data, str) else items_data
        
        if not isinstance(items, list):
            return {"success": False, "message": _("Invalid items data format")}
        
        results = []
        total_people = 0
        total_amount = 0
        
        for item in items:
            item_code = item.get("item_code")
            qty = flt(item.get("qty", 0))
            rate = flt(item.get("rate", 0))
            conversion_factor = flt(item.get("conversion_factor", 1))
            people_qty = flt(item.get("custom__people_qty", 0))
            
            # Calculate quantities using standard ERPNext logic
            stock_qty = qty * conversion_factor
            
            # Calculate amount using stock_qty (as in ERPNext)
            amount = stock_qty * rate
            
            # Calculate stock_uom_rate
            stock_uom_rate = rate / conversion_factor if conversion_factor > 0 else 0
            
            # Sum people quantities and amounts
            total_people += people_qty
            total_amount += amount
            
            results.append({
                "item_code": item_code,
                "qty": qty,
                "rate": rate,
                "conversion_factor": conversion_factor,
                "stock_qty": stock_qty,
                "amount": amount,
                "stock_uom_rate": stock_uom_rate,
                "custom__people_qty": people_qty
            })
        
        return {
            "success": True,
            "items": results,
            "total_people_qty": total_people,
            "total_amount": total_amount
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_opportunity_calculations: {str(e)}", "UOM Helper Error")
        return {
            "success": False,
            "message": _("Error calculating amounts: {0}").format(str(e))
        }


@frappe.whitelist()
def validate_opportunity_data(opportunity_data: str) -> Dict[str, Any]:
    """
    Validate opportunity data (dates, people count, etc.)
    
    Args:
        opportunity_data (str): JSON string containing opportunity data
        
    Returns:
        Dict[str, Any]: Validation results with error messages if any
    """
    try:
        import json
        from frappe.utils import getdate, date_diff
        
        data = json.loads(opportunity_data) if isinstance(opportunity_data, str) else opportunity_data
        
        errors = []
        warnings = []
        
        # Check opportunity dates
        opp_start_date = data.get("custom_opportunity_start_date")
        opp_end_date = data.get("expected_closing")
        max_people = flt(data.get("custom_opportunity_people_qty", 0))
        
        if opp_start_date and opp_end_date:
            if getdate(opp_start_date) > getdate(opp_end_date):
                errors.append(_("Opportunity start date cannot be after expected closing date"))
        
        # Check opportunity items
        items = data.get("items", [])
        total_people = 0
        
        for idx, item in enumerate(items, 1):
            event_start = item.get("custom_event_start_date")
            event_end = item.get("custom_event_end_date")
            people_qty = flt(item.get("custom__people_qty", 0))
            
            total_people += people_qty
            
            # Check event dates
            if event_start and opp_start_date:
                if getdate(event_start) < getdate(opp_start_date):
                    errors.append(_("Row {0}: Event start date cannot be before opportunity start date").format(idx))
            
            if event_end and opp_end_date:
                if getdate(event_end) > getdate(opp_end_date):
                    errors.append(_("Row {0}: Event end date cannot be after opportunity expected closing").format(idx))
            
            if event_start and event_end:
                if getdate(event_start) > getdate(event_end):
                    errors.append(_("Row {0}: Event start date cannot be after event end date").format(idx))
        
        # Check people count
        if max_people > 0 and total_people > max_people:
            warnings.append(_("Total people quantity ({0}) exceeds maximum allowed ({1})").format(total_people, max_people))
        
        return {
            "success": True,
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_people_qty": total_people
        }
        
    except Exception as e:
        frappe.log_error(f"Error in validate_opportunity_data: {str(e)}")
        return {
            "success": False,
            "message": _("Error validating data: {0}").format(str(e))
        }


@frappe.whitelist()
def get_item_uoms_and_conversion(item_code, uom=None):
    """
    Fetch available item UOMs (with conversion factor) according to Stock Settings
    and return required conversion factor and stock_uom - fully compatible with ERPNext
    
    Args:
        item_code (str): Item code
        uom (str, optional): Required unit of measure
        
    Returns:
        dict: UOM data and conversion factor
    """
    try:
        if not item_code:
            return {
                "success": False,
                "message": _("Item Code is required"),
                "uoms": [],
                "conversion_factor": 1.0,
                "stock_uom": None
            }

        # Fetch basic item information
        item_doc = frappe.get_cached_doc("Item", item_code)
        if not item_doc:
            return {
                "success": False,
                "message": _("Item {0} not found").format(item_code),
                "uoms": [],
                "conversion_factor": 1.0,
                "stock_uom": None
            }

        stock_uom = item_doc.stock_uom
        conversion_factor = 1.0
        uoms = []

        # Check Stock Settings configuration
        allow_custom_uom = frappe.db.get_single_value(
            "Stock Settings", 
            "allow_uom_with_conversion_rate_defined_in_item"
        )
        
        if allow_custom_uom and item_doc.uoms:
            # Use UOM Conversion Detail defined in item
            for uom_detail in item_doc.uoms:
                uoms.append({
                    "uom": uom_detail.uom,
                    "conversion_factor": uom_detail.conversion_factor,
                    "is_stock_uom": uom_detail.uom == stock_uom
                })
            
            # Search for conversion factor for required UOM
            if uom:
                for uom_detail in item_doc.uoms:
                    if uom_detail.uom == uom:
                        conversion_factor = uom_detail.conversion_factor
                        break
                else:
                    # If UOM not found in item list, check stock_uom
                    if uom == stock_uom:
                        conversion_factor = 1.0
                    else:
                        # Use standard ERPNext function as fallback
                        from erpnext.stock.get_item_details import get_conversion_factor
                        result = get_conversion_factor(item_code, uom)
                        if result and "conversion_factor" in result:
                            conversion_factor = result["conversion_factor"]
        else:
            # If custom UOM not allowed, use stock_uom only
            uoms = [{
                "uom": stock_uom, 
                "conversion_factor": 1.0,
                "is_stock_uom": True
            }]
            conversion_factor = 1.0 if not uom or uom == stock_uom else 1.0

        return {
            "success": True,
            "uoms": uoms,
            "conversion_factor": conversion_factor,
            "stock_uom": stock_uom,
            "allow_custom_uom": allow_custom_uom
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_item_uoms_and_conversion: {str(e)}", "UOM Helper Error")
        return {
            "success": False,
            "message": _("Error fetching UOM data: {0}").format(str(e)),
            "uoms": [],
            "conversion_factor": 1.0,
            "stock_uom": None
        }


@frappe.whitelist()
def validate_integration_status():
    """
    Function to check integration status between custom system and ERPNext
    
    Returns:
        dict: Comprehensive integration status report
    """
    try:
        status_report = {
            "success": True,
            "integration_status": "healthy",
            "checks": {},
            "warnings": [],
            "errors": []
        }
        
        # Check Stock Settings
        stock_settings = frappe.get_single("Stock Settings")
        status_report["checks"]["stock_settings"] = {
            "allow_uom_conversion": stock_settings.allow_uom_with_conversion_rate_defined_in_item,
            "status": "OK"
        }
        
        # Check for custom fields existence
        custom_fields_check = frappe.db.sql("""
            SELECT fieldname, dt 
            FROM `tabCustom Field` 
            WHERE dt = 'Opportunity Item' 
            AND fieldname IN ('custom_stock_qty', 'custom_stock_uom_rate', 'custom__people_qty')
        """, as_dict=True)
        
        expected_fields = ['custom_stock_qty', 'custom_stock_uom_rate', 'custom__people_qty']
        found_fields = [f['fieldname'] for f in custom_fields_check]
        missing_fields = set(expected_fields) - set(found_fields)
        
        if missing_fields:
            status_report["errors"].append(f"Missing custom fields: {', '.join(missing_fields)}")
            status_report["integration_status"] = "error"
        
        status_report["checks"]["custom_fields"] = {
            "expected": expected_fields,
            "found": found_fields,
            "missing": list(missing_fields),
            "status": "OK" if not missing_fields else "ERROR"
        }
        
        # Check for UOM Conversion Detail existence
        sample_items = frappe.get_all("Item", 
                                     filters={"has_variants": 0}, 
                                     fields=["name", "stock_uom"], 
                                     limit=5)
        
        uom_conversion_status = []
        for item in sample_items:
            conversions = frappe.get_all("UOM Conversion Detail",
                                       filters={"parent": item.name},
                                       fields=["uom", "conversion_factor"])
            uom_conversion_status.append({
                "item": item.name,
                "stock_uom": item.stock_uom,
                "conversions_count": len(conversions)
            })
        
        status_report["checks"]["uom_conversions"] = {
            "sample_items": uom_conversion_status,
            "status": "OK"
        }
        
        # Check API endpoints validity
        try:
            test_result = get_item_uoms_and_conversion("", None)
            if test_result.get("success") == False and "required" in test_result.get("message", "").lower():
                status_report["checks"]["api_endpoints"] = {"status": "OK"}
            else:
                status_report["warnings"].append("API endpoint validation inconclusive")
        except Exception as e:
            status_report["warnings"].append(f"API endpoint test failed: {str(e)}")
        
        # Final validation
        if status_report["errors"]:
            status_report["integration_status"] = "error"
        elif status_report["warnings"]:
            status_report["integration_status"] = "warning"
        
        return status_report
        
    except Exception as e:
        frappe.log_error(f"Error in validate_integration_status: {str(e)}", "Integration Validation Error")
        return {
            "success": False,
            "integration_status": "error",
            "message": _("Error validating integration: {0}").format(str(e))
        }
