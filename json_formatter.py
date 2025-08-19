from typing import Dict, Any, List
import json
from datetime import datetime
import logging

class JSONFormatter:
    def __init__(self):
        self.currency_symbol = "$"
    
    def format_extraction_results(self, extracted_data: Dict[str, str], 
                                pdf_filename: str = "document.pdf", 
                                excel_filename: str = "attributes.xlsx") -> Dict[str, Any]:
        """
        Format extracted data into a structured JSON response
        """
        try:
            # Clean and format extracted values
            formatted_data = {}
            
            for attribute, value in extracted_data.items():
                formatted_value = self._format_value(value)
                formatted_data[attribute] = formatted_value
            
            # Create the structured response
            result = {
                "success": True,
                "extraction_timestamp": datetime.now().isoformat(),
                "source_files": {
                    "pdf_filename": pdf_filename,
                    "excel_filename": excel_filename
                },
                "extracted_data": formatted_data,
                "summary": self._create_summary(formatted_data),
                "validation": self._validate_data_consistency(formatted_data)
            }
            
            return result
            
        except Exception as e:
            logging.error(f"Error formatting extraction results: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "extraction_timestamp": datetime.now().isoformat(),
                "extracted_data": {},
                "summary": {},
                "validation": {"status": "failed", "errors": [str(e)]}
            }
    
    def _format_value(self, value: str) -> Dict[str, Any]:
        """
        Format individual extracted value with proper typing and metadata
        """
        if not value or value in ["NOT_FOUND", "ERROR", None]:
            return {
                "raw_value": value,
                "formatted_value": None,
                "numeric_value": None,
                "currency": None,
                "status": "not_found"
            }
        
        try:
            # Clean the value
            clean_value = str(value).replace("$", "").replace(",", "").replace("USD", "").replace("US", "").strip()
            
            # Try to convert to numeric
            try:
                numeric_value = float(clean_value)
                formatted_currency = f"${numeric_value:,.2f}" if numeric_value >= 0 else f"-${abs(numeric_value):,.2f}"
                
                return {
                    "raw_value": value,
                    "formatted_value": formatted_currency,
                    "numeric_value": numeric_value,
                    "currency": "USD",
                    "status": "extracted"
                }
                
            except ValueError:
                # If not numeric, return as string
                return {
                    "raw_value": value,
                    "formatted_value": clean_value,
                    "numeric_value": None,
                    "currency": None,
                    "status": "extracted_non_numeric"
                }
                
        except Exception as e:
            logging.error(f"Error formatting value {value}: {str(e)}")
            return {
                "raw_value": value,
                "formatted_value": None,
                "numeric_value": None,
                "currency": None,
                "status": "format_error"
            }
    
    def _create_summary(self, formatted_data: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Create a summary of extracted data
        """
        try:
            total_extracted = 0
            total_attributes = len(formatted_data)
            numeric_values = []
            
            for attr, data in formatted_data.items():
                if data.get("status") == "extracted" and data.get("numeric_value") is not None:
                    total_extracted += 1
                    numeric_values.append({
                        "attribute": attr,
                        "value": data["numeric_value"]
                    })
            
            # Sort by value to identify key amounts
            numeric_values.sort(key=lambda x: x["value"], reverse=True)
            
            summary = {
                "total_attributes_processed": total_attributes,
                "successful_extractions": total_extracted,
                "extraction_rate": f"{(total_extracted/total_attributes*100):.1f}%" if total_attributes > 0 else "0%",
                "top_values": numeric_values[:5],  # Top 5 highest values
                "key_insurance_metrics": self._extract_key_metrics(formatted_data)
            }
            
            return summary
            
        except Exception as e:
            logging.error(f"Error creating summary: {str(e)}")
            return {"error": str(e)}
    
    def _extract_key_metrics(self, formatted_data: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Extract key insurance metrics from the data
        """
        metrics = {}
        
        # Map common insurance terms to standardized keys
        key_mappings = {
            "Total Insured Value": "total_insured_value",
            "Quoted Amount": "quoted_amount",
            "Limit Amount": "limit_amount", 
            "Limit per occurrence": "limit_per_occurrence",
            "Attachment Point": "attachment_point",
            "Annual Premium": "annual_premium",
            "100 % Annual Premium": "full_annual_premium",
            "Premium due": "premium_due",
            "100% layer premium w/o terrorism": "layer_premium_no_terrorism"
        }
        
        for original_key, standard_key in key_mappings.items():
            if original_key in formatted_data:
                data = formatted_data[original_key]
                if data.get("status") == "extracted":
                    metrics[standard_key] = {
                        "value": data.get("numeric_value"),
                        "formatted": data.get("formatted_value")
                    }
        
        return metrics
    
    def _validate_data_consistency(self, formatted_data: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Validate data consistency and relationships
        """
        validation = {
            "status": "passed",
            "warnings": [],
            "errors": [],
            "consistency_checks": []
        }
        
        try:
            # Extract numeric values for validation
            values = {}
            for attr, data in formatted_data.items():
                if data.get("status") == "extracted" and data.get("numeric_value") is not None:
                    values[attr] = data["numeric_value"]
            
            # Check if Quoted Amount equals Limit Amount
            if "Quoted Amount" in values and "Limit Amount" in values:
                if values["Quoted Amount"] == values["Limit Amount"]:
                    validation["consistency_checks"].append({
                        "check": "Quoted Amount vs Limit Amount",
                        "status": "consistent",
                        "message": "Quoted Amount equals Limit Amount as expected"
                    })
                else:
                    validation["warnings"].append(
                        f"Quoted Amount (${values['Quoted Amount']:,.2f}) differs from Limit Amount (${values['Limit Amount']:,.2f})"
                    )
            
            # Check if Premium due matches Annual Premium
            if "Premium due" in values and "Annual Premium" in values:
                if values["Premium due"] == values["Annual Premium"]:
                    validation["consistency_checks"].append({
                        "check": "Premium due vs Annual Premium",
                        "status": "consistent", 
                        "message": "Premium due equals Annual Premium"
                    })
                else:
                    validation["warnings"].append(
                        f"Premium due (${values['Premium due']:,.2f}) differs from Annual Premium (${values['Annual Premium']:,.2f})"
                    )
            
            # Check reasonable value ranges
            if "Total Insured Value" in values:
                tiv = values["Total Insured Value"]
                if tiv < 1000000:  # Less than $1M seems low for commercial insurance
                    validation["warnings"].append(f"Total Insured Value seems low: ${tiv:,.2f}")
                elif tiv > 100000000000:  # More than $100B seems high
                    validation["warnings"].append(f"Total Insured Value seems very high: ${tiv:,.2f}")
            
            # Set overall status
            if validation["errors"]:
                validation["status"] = "failed"
            elif validation["warnings"]:
                validation["status"] = "warnings"
            
        except Exception as e:
            validation["status"] = "error"
            validation["errors"].append(f"Validation error: {str(e)}")
        
        return validation
    
    def create_comparison_report(self, extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a comparison report for multiple extractions
        """
        if len(extractions) < 2:
            return {"error": "Need at least 2 extractions for comparison"}
        
        try:
            comparison = {
                "comparison_timestamp": datetime.now().isoformat(),
                "total_documents": len(extractions),
                "attribute_comparison": {},
                "summary_statistics": {}
            }
            
            # Get all unique attributes
            all_attributes = set()
            for extraction in extractions:
                if "extracted_data" in extraction:
                    all_attributes.update(extraction["extracted_data"].keys())
            
            # Compare each attribute across documents
            for attr in all_attributes:
                attr_data = []
                for i, extraction in enumerate(extractions):
                    if "extracted_data" in extraction and attr in extraction["extracted_data"]:
                        data = extraction["extracted_data"][attr]
                        attr_data.append({
                            "document_index": i,
                            "document_name": extraction.get("source_files", {}).get("pdf_filename", f"document_{i}"),
                            "value": data.get("numeric_value"),
                            "formatted": data.get("formatted_value"),
                            "status": data.get("status")
                        })
                
                comparison["attribute_comparison"][attr] = attr_data
            
            return comparison
            
        except Exception as e:
            return {"error": f"Comparison error: {str(e)}"}
    
    def export_to_excel(self, formatted_data: Dict[str, Any], filename: str = None) -> str:
        """
        Export formatted data to Excel file
        """
        try:
            import pandas as pd
            
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"insurance_extraction_{timestamp}.xlsx"
            
            # Prepare data for Excel export
            export_data = []
            
            if "extracted_data" in formatted_data:
                for attr, data in formatted_data["extracted_data"].items():
                    if isinstance(data, dict):
                        export_data.append({
                            "Attribute": attr,
                            "Raw_Value": data.get("raw_value", ""),
                            "Formatted_Value": data.get("formatted_value", ""),
                            "Numeric_Value": data.get("numeric_value", ""),
                            "Currency": data.get("currency", ""),
                            "Status": data.get("status", "")
                        })
            
            # Create DataFrame and save to Excel
            df = pd.DataFrame(export_data)
            df.to_excel(filename, index=False)
            
            return filename
            
        except Exception as e:
            logging.error(f"Error exporting to Excel: {str(e)}")
            raise e
                    "formatted_value": formatted_currency,
                    "numeric_value": numeric_value,
                    "currency": "USD",
                    "status": "extracted"
                }
                
            except ValueError:
                # If not numeric, return as string
                return {
                    "raw_value": value,
                    "formatted_value": clean_value,
                    "numeric_value": None,
                    "currency": None,
                    "status": "extracted_non_numeric"
                }
                
        except Exception as e:
            logging.error(f"Error formatting value {value}: {str(e)}")
            return {
                "raw_value": value,
                "formatted_value": None,
                "numeric_value": None,
                "currency": None,
                "status": "format_error"
            }
    
    def _create_summary(self, formatted_data: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Create a summary of extracted data
        """
        try:
            total_extracted = 0
            total_attributes = len(formatted_data)
            numeric_values = []
            
            for attr, data in formatted_data.items():
                if data.get("status") == "extracted" and data.get("numeric_value") is not None:
                    total_extracted += 1
                    numeric_values.append({
                        "attribute": attr,
                        "value": data["numeric_value"]
                    })
            
            # Sort by value to identify key amounts
            numeric_values.sort(key=lambda x: x["value"], reverse=True)
            
            summary = {
                "total_attributes_processed": total_attributes,
                "successful_extractions": total_extracted,
                "extraction_rate": f"{(total_extracted/total_attributes*100):.1f}%" if total_attributes > 0 else "0%",
                "top_values": numeric_values[:5],  # Top 5 highest values
                "key_insurance_metrics": self._extract_key_metrics(formatted_data)
            }
            
            return summary
            
        except Exception as e:
            logging.error(f"Error creating summary: {str(e)}")
            return {"error": str(e)}
    
    def _extract_key_metrics(self, formatted_data: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Extract key insurance metrics from the data
        """
        metrics = {}
        
        # Map common insurance terms to standardized keys
        key_mappings = {
            "Total Insured Value": "total_insured_value",
            "Quoted Amount": "quoted_amount",
            "Limit Amount": "limit_amount", 
            "Limit per occurrence": "limit_per_occurrence",
            "Attachment Point": "attachment_point",
            "Annual Premium": "annual_premium",
            "100 % Annual Premium": "full_annual_premium",
            "Premium due": "premium_due",
            "100% layer premium w/o terrorism": "layer_premium_no_terrorism"
        }
        
        for original_key, standard_key in key_mappings.items():
            if original_key in formatted_data:
                data = formatted_data[original_key]
                if data.get("status") == "extracted":
                    metrics[standard_key] = {
                        "value": data.get("numeric_value"),
                        "formatted": data.get("formatted_value")
                    }
        
        return metrics
    
    def _validate_data_consistency(self, formatted_data: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Validate data consistency and relationships
        """
        validation = {
            "status": "passed",
            "warnings": [],
            "errors": [],
            "consistency_checks": []
        }
        
        try:
            # Extract numeric values for validation
            values = {}
            for attr, data in formatted_data.items():
                if data.get("status") == "extracted" and data.get("numeric_value") is not None:
                    values[attr] = data["numeric_value"]
            
            # Check if Quoted Amount equals Limit Amount
            if "Quoted Amount" in values and "Limit Amount" in values:
                if values["Quoted Amount"] == values["Limit Amount"]:
                    validation["consistency_checks"].append({
                        "check": "Quoted Amount vs Limit Amount",
                        "status": "consistent",
                        "message": "Quoted Amount equals Limit Amount as expected"
                    })
                else:
                    validation["warnings"].append(
                        f"Quoted Amount (${values['Quoted Amount']:,.2f}) differs from Limit Amount (${values['Limit Amount']:,.2f})"
                    )
            
            # Check if Premium due matches Annual Premium
            if "Premium due" in values and "Annual Premium" in values:
                if values["Premium due"] == values["Annual Premium"]:
                    validation["consistency_checks"].append({
                        "check": "Premium due vs Annual Premium",
                        "status": "consistent", 
                        "message": "Premium due equals Annual Premium"
                    })
                else:
                    validation["warnings"].append(
                        f"Premium due (${values['Premium due']:,.2f}) differs from Annual Premium (${values['Annual Premium']:,.2f})"
                    )
            
            # Check reasonable value ranges
            if "Total Insured Value" in values:
                tiv = values["Total Insured Value"]
                if tiv < 1000000:  # Less than $1M seems low for commercial insurance
                    validation["warnings"].append(f"Total Insured Value seems low: ${tiv:,.2f}")
                elif tiv > 100000000000:  # More than $100B seems high
                    validation["warnings"].append(f"Total Insured Value seems very high: ${tiv:,.2f}")
            
            # Set overall status
            if validation["errors"]:
                validation["status"] = "failed"
            elif validation["warnings"]:
                validation["status"] = "warnings"
            
        except Exception as e:
            validation["status"] = "error"
            validation["errors"].append(f"Validation error: {str(e)}")
        
        return validation
    
    def export_to_json_file(self, data: Dict[str, Any], filename: str = None) -> str:
        """
        Export formatted data to JSON file
        """
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"insurance_extraction_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return filename
            
        except Exception as e:
            logging.error(f"Error exporting to JSON file: {str(e)}")
            raise e
    
    def create_comparison_report(self, extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a comparison report for multiple extractions
        """
        if len(extractions) < 2:
            return {"error": "Need at least 2 extractions for comparison"}
        
        try:
            comparison = {
                "comparison_timestamp": datetime.now().isoformat(),
                "total_documents": len(extractions),
                "attribute_comparison": {},
                "summary_statistics": {}
            }
            
            # Get all unique attributes
            all_attributes = set()
            for extraction in extractions:
                if "extracted_data" in extraction:
                    all_attributes.update(extraction["extracted_data"].keys())
            
            # Compare each attribute across documents
            for attr in all_attributes:
                attr_data = []
                for i, extraction in enumerate(extractions):
                    if "extracted_data" in extraction and attr in extraction["extracted_data"]:
                        data = extraction["extracted_data"][attr]
                        attr_data.append({
                            "document_index": i,
                            "document_name": extraction.get("source_files", {}).get("pdf_filename", f"document_{i}"),
                            "value": data.get("numeric_value"),
                            "formatted": data.get("formatted_value"),
                            "status": data.get("status")
                        })
                
                comparison["attribute_comparison"][attr] = attr_data
            
            return comparison
            
        except Exception as e:
            return {"error": f"Comparison error: {str(e)}"}

                    